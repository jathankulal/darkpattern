"""Local persistent store and explicit lifecycle for untrusted AI candidates."""

import hashlib
import json
import os
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Iterator, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.schemas import AIProposal, FindingCategory


class CandidateStatus(str, Enum):
    CANDIDATE = "candidate"
    VALIDATED = "validated"
    REJECTED = "rejected"
    PROMOTED = "promoted"


class CandidateReviewAction(str, Enum):
    REVIEWED = "reviewed"
    VALIDATED = "validated"
    REJECTED = "rejected"
    PROMOTED = "promoted"


class CandidateReviewEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: CandidateReviewAction
    actor: str = Field(min_length=1, max_length=100)
    rationale: str = Field(min_length=1, max_length=2_000)
    provenance: Literal["manual_review"] = "manual_review"
    evidence_supports_pattern: Optional[bool] = None
    timestamp: datetime

    @field_validator("actor", "rationale")
    @classmethod
    def reject_blank_review_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Review text must not be blank")
        return value


class CandidateRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str = Field(pattern=r"^cand_[a-f0-9]{64}$")
    candidate_pattern: str = Field(min_length=1, max_length=500)
    proposed_category: Optional[FindingCategory] = None
    evidence_quote: Optional[str] = Field(default=None, max_length=1_000)
    explanation: str = Field(min_length=1, max_length=2_000)
    recommendation: Optional[str] = Field(default=None, max_length=2_000)
    provenance: Literal["ai"] = "ai"
    source_type: Literal["ai", "mock"] = "ai"
    status: CandidateStatus = CandidateStatus.CANDIDATE
    created_at: datetime
    updated_at: datetime
    review_history: list[CandidateReviewEvent] = Field(default_factory=list)

    @field_validator("candidate_pattern", "explanation")
    @classmethod
    def reject_blank_candidate_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Candidate text must not be blank")
        return value

    @field_validator("evidence_quote", "recommendation")
    @classmethod
    def reject_blank_optional_text(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and not value.strip():
            raise ValueError("Optional text must be non-blank when supplied")
        return value


class RetrievedKnowledgeEntry(BaseModel):
    """Bounded advisory context; never an authoritative finding."""

    entry_id: str = Field(min_length=1, max_length=100)
    source: Literal["curated", "promoted_candidate"]
    category: Optional[FindingCategory] = None
    candidate_pattern: Optional[str] = Field(default=None, max_length=500)
    evidence_signals: list[str] = Field(default_factory=list, max_length=8)
    prior_evidence_quote: Optional[str] = Field(default=None, max_length=1_000)
    guidance: str = Field(min_length=1, max_length=500)
    caution: str = Field(min_length=1, max_length=500)


class KnowledgeBaseError(RuntimeError):
    """Base error for persistent candidate knowledge-base operations."""


class KnowledgeBaseCorruptError(KnowledgeBaseError):
    """Raised when persisted data cannot be safely validated or read."""


class CandidateNotFoundError(KnowledgeBaseError):
    """Raised when a requested candidate identifier does not exist."""


class InvalidCandidateTransitionError(KnowledgeBaseError):
    """Raised when a lifecycle action is not allowed from the current status."""


def default_knowledge_base_path() -> Path:
    """Resolve the local store path without placing user data in the repository."""
    configured_path = os.environ.get("DPG_KNOWLEDGE_BASE_PATH")
    if configured_path and configured_path.strip():
        return Path(configured_path).expanduser()
    return Path.home() / ".darkpattern-guardian" / "candidate_knowledge_base.sqlite3"


def _now() -> datetime:
    return datetime.now(timezone.utc)


_STARTER_GUIDANCE = (
    {
        "entry_id": "free-trial-conversion",
        "category": FindingCategory.FREE_TRIAL_CONVERSION,
        "keywords": ("free trial", "trial period", "trial ends", "after trial", "trial"),
        "evidence_signals": ("trial duration", "post-trial price", "renewal timing"),
        "guidance": (
            "Check whether the trial duration, post-trial charge, and renewal timing "
            "are stated in the submitted text."
        ),
        "caution": (
            "A clearly disclosed trial-to-paid transition is not by itself evidence "
            "of deception; do not infer missing terms."
        ),
    },
    {
        "entry_id": "recurring-payments",
        "category": FindingCategory.RECURRING_PAYMENT,
        "keywords": ("subscription", "renews", "renewal", "automatically", "per month", "per year"),
        "evidence_signals": ("recurring interval", "renewal wording", "recurring amount"),
        "guidance": (
            "Identify only the recurring interval, amount, and renewal wording that "
            "the submitted text actually states."
        ),
        "caution": (
            "Automatic renewal alone is not proof of a deceptive pattern; distinguish "
            "the observed billing term from any possible risk."
        ),
    },
    {
        "entry_id": "additional-fees",
        "category": FindingCategory.ADDITIONAL_FEE,
        "keywords": ("fee", "fees", "surcharge", "shipping", "service charge", "extra charge", "tax"),
        "evidence_signals": ("fee amount", "checkout total", "price difference"),
        "guidance": (
            "Look for an explicitly stated extra charge or a stated price difference "
            "between checkout stages."
        ),
        "caution": (
            "Do not infer a hidden fee from a fee mention alone; taxes, shipping, and "
            "clearly disclosed optional charges are not automatically deceptive."
        ),
    },
    {
        "entry_id": "cancellation-friction",
        "category": FindingCategory.CANCELLATION_REFUND_CLARITY,
        "keywords": ("cancel", "cancellation", "customer service", "calling", "phone", "contact"),
        "evidence_signals": ("cancellation method", "steps required", "stated deadline"),
        "guidance": (
            "Describe only cancellation methods or steps stated in the submitted text."
        ),
        "caution": (
            "A stated phone or support route is not proof that cancellation is impossible; "
            "do not claim instructions are absent when present."
        ),
    },
    {
        "entry_id": "urgency-pressure",
        "category": FindingCategory.URGENCY_PRESSURE,
        "keywords": (
            "limited time",
            "minutes left",
            "countdown",
            "limited quantity",
            "seats left",
            "spots left",
            "items left",
            "remaining",
            "offer ends",
        ),
        "evidence_signals": ("countdown wording", "limited quantity wording", "offer deadline"),
        "guidance": (
            "Quote the exact urgency or scarcity wording and describe it as a message "
            "shown on the page."
        ),
        "caution": (
            "The wording alone does not verify a deadline or inventory level; a genuine "
            "limited offer is not automatically deceptive."
        ),
    },
)


def _matching_keyword_count(text: str, keywords: tuple[str, ...]) -> int:
    normalized_text = " ".join(text.casefold().split())
    return sum(
        1
        for keyword in keywords
        if re.search(
            rf"(?<!\w){re.escape(keyword.casefold())}(?!\w)",
            normalized_text,
        )
    )


class CandidateKnowledgeBase:
    """SQLite-backed store for candidate proposals; never stores submitted pages."""

    _SCHEMA_VERSION = 1

    def __init__(self, database_path: Optional[Union[Path, str]] = None):
        self.database_path = Path(database_path) if database_path is not None else default_knowledge_base_path()
        self.database_path = self.database_path.expanduser().resolve()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=5.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _initialize(self) -> None:
        try:
            with self._connection() as connection:
                version = connection.execute("PRAGMA user_version").fetchone()[0]
                if version > self._SCHEMA_VERSION:
                    raise KnowledgeBaseError(
                        "The candidate store was created by a newer application version."
                    )
                connection.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS candidates (
                        candidate_id TEXT PRIMARY KEY,
                        candidate_pattern TEXT NOT NULL,
                        proposed_category TEXT,
                        evidence_quote TEXT,
                        explanation TEXT NOT NULL,
                        recommendation TEXT,
                        provenance TEXT NOT NULL CHECK (provenance = 'ai'),
                        source_type TEXT NOT NULL CHECK (source_type IN ('ai', 'mock')),
                        status TEXT NOT NULL CHECK (
                            status IN ('candidate', 'validated', 'rejected', 'promoted')
                        ),
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS candidate_review_events (
                        event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        candidate_id TEXT NOT NULL REFERENCES candidates(candidate_id),
                        action TEXT NOT NULL CHECK (
                            action IN ('reviewed', 'validated', 'rejected', 'promoted')
                        ),
                        actor TEXT NOT NULL,
                        rationale TEXT NOT NULL,
                        provenance TEXT NOT NULL CHECK (provenance = 'manual_review'),
                        evidence_supports_pattern INTEGER CHECK (
                            evidence_supports_pattern IN (0, 1)
                            OR evidence_supports_pattern IS NULL
                        ),
                        timestamp TEXT NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS idx_candidates_status_created
                        ON candidates(status, created_at, candidate_id);
                    """
                )
                connection.execute(f"PRAGMA user_version = {self._SCHEMA_VERSION}")
        except sqlite3.DatabaseError as exc:
            raise KnowledgeBaseCorruptError(
                "The candidate store could not be initialized or read safely."
            ) from exc

    @staticmethod
    def _candidate_id(proposal: AIProposal, source_type: str) -> str:
        candidate_data = proposal.model_dump(mode="json")
        candidate_data["source_type"] = source_type
        canonical = json.dumps(
            candidate_data,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        return "cand_" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def _proposal_data(proposal: AIProposal, source_type: str) -> dict:
        return {
            "candidate_pattern": proposal.candidate_pattern,
            "proposed_category": proposal.proposed_category,
            "evidence_quote": proposal.evidence_quote,
            "explanation": proposal.explanation,
            "recommendation": proposal.recommendation,
            "provenance": proposal.provenance,
            "source_type": source_type,
        }

    @staticmethod
    def _read_record(connection: sqlite3.Connection, row: sqlite3.Row) -> CandidateRecord:
        event_rows = connection.execute(
            """
            SELECT action, actor, rationale, provenance, evidence_supports_pattern, timestamp
            FROM candidate_review_events
            WHERE candidate_id = ?
            ORDER BY event_id
            """,
            (row["candidate_id"],),
        ).fetchall()
        record_data = dict(row)
        record_data["review_history"] = [
            {
                "action": event["action"],
                "actor": event["actor"],
                "rationale": event["rationale"],
                "provenance": event["provenance"],
                "evidence_supports_pattern": (
                    None
                    if event["evidence_supports_pattern"] is None
                    else bool(event["evidence_supports_pattern"])
                ),
                "timestamp": event["timestamp"],
            }
            for event in event_rows
        ]
        try:
            return CandidateRecord.model_validate(record_data)
        except ValidationError as exc:
            raise KnowledgeBaseCorruptError(
                "A candidate record failed contract validation."
            ) from exc

    @staticmethod
    def _fetch_record(
        connection: sqlite3.Connection,
        candidate_id: str,
    ) -> CandidateRecord:
        row = connection.execute(
            "SELECT * FROM candidates WHERE candidate_id = ?",
            (candidate_id,),
        ).fetchone()
        if row is None:
            raise CandidateNotFoundError("Candidate was not found.")
        return CandidateKnowledgeBase._read_record(connection, row)

    def add_proposal(
        self,
        raw_proposal: AIProposal | object,
        source_type: Literal["ai", "mock"] = "ai",
    ) -> CandidateRecord:
        """Validate and persist one proposal idempotently, without storing page data."""
        raw = raw_proposal.model_dump() if isinstance(raw_proposal, AIProposal) else raw_proposal
        proposal = AIProposal.model_validate(raw)
        if source_type not in ("ai", "mock"):
            raise ValueError("Candidate source type must be 'ai' or 'mock'.")
        candidate_id = self._candidate_id(proposal, source_type)
        proposal_data = self._proposal_data(proposal, source_type)
        timestamp = _now().isoformat()

        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT * FROM candidates WHERE candidate_id = ?",
                (candidate_id,),
            ).fetchone()
            if existing is not None:
                record = self._read_record(connection, existing)
                if any(
                    getattr(record, field) != value
                    for field, value in proposal_data.items()
                ):
                    raise KnowledgeBaseCorruptError(
                        "A candidate identifier conflicts with stored proposal data."
                    )
                return record

            connection.execute(
                """
                INSERT INTO candidates (
                    candidate_id, candidate_pattern, proposed_category, evidence_quote,
                    explanation, recommendation, provenance, source_type, status,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    candidate_id,
                    proposal_data["candidate_pattern"],
                    (
                        proposal_data["proposed_category"].value
                        if proposal_data["proposed_category"] is not None
                        else None
                    ),
                    proposal_data["evidence_quote"],
                    proposal_data["explanation"],
                    proposal_data["recommendation"],
                    proposal_data["provenance"],
                    proposal_data["source_type"],
                    CandidateStatus.CANDIDATE.value,
                    timestamp,
                    timestamp,
                ),
            )
            return self._fetch_record(connection, candidate_id)

    def get_candidate(self, candidate_id: str) -> CandidateRecord:
        with self._connection() as connection:
            return self._fetch_record(connection, candidate_id)

    def list_candidates(
        self,
        status: Optional[CandidateStatus] = None,
    ) -> list[CandidateRecord]:
        with self._connection() as connection:
            if status is None:
                rows = connection.execute(
                    "SELECT * FROM candidates ORDER BY created_at, candidate_id"
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT * FROM candidates
                    WHERE status = ?
                    ORDER BY created_at, candidate_id
                    """,
                    (status.value,),
                ).fetchall()
            return [self._read_record(connection, row) for row in rows]

    def retrieve_relevant(
        self,
        page_text: str,
        limit: int = 5,
    ) -> list[RetrievedKnowledgeEntry]:
        """Return relevant curated guidance and manually promoted prior examples.

        Historical quotes are labeled as prior evidence and must never be used as
        evidence for the page currently being analyzed.
        """
        if not isinstance(page_text, str) or not page_text.strip() or limit <= 0:
            return []
        bounded_limit = min(limit, 10)
        ranked: list[tuple[int, int, RetrievedKnowledgeEntry]] = []
        matched_categories: set[FindingCategory] = set()

        for order, entry in enumerate(_STARTER_GUIDANCE):
            score = _matching_keyword_count(page_text, entry["keywords"])
            if score:
                matched_categories.add(entry["category"])
                ranked.append(
                    (
                        score,
                        -order,
                        RetrievedKnowledgeEntry(
                            entry_id=entry["entry_id"],
                            source="curated",
                            category=entry["category"],
                            evidence_signals=list(entry["evidence_signals"]),
                            guidance=entry["guidance"],
                            caution=entry["caution"],
                        ),
                    )
                )

        if matched_categories:
            promoted = self.list_candidates(CandidateStatus.PROMOTED)
            for record in promoted:
                if record.proposed_category not in matched_categories:
                    continue
                relevance_text = " ".join(
                    value
                    for value in (
                        record.candidate_pattern,
                        record.evidence_quote or "",
                    )
                )
                score = _matching_keyword_count(
                    page_text,
                    tuple(
                        word
                        for word in re.findall(r"[a-z0-9$]+", relevance_text.casefold())
                        if len(word) > 3
                    ),
                )
                if score:
                    ranked.append(
                        (
                            score,
                            0,
                            RetrievedKnowledgeEntry(
                                entry_id=record.candidate_id,
                                source="promoted_candidate",
                                category=record.proposed_category,
                                candidate_pattern=record.candidate_pattern,
                                prior_evidence_quote=record.evidence_quote,
                                guidance=record.explanation[:500],
                                caution=(
                                    "This is a manually promoted prior example, not "
                                    "evidence from the current page or an automatic finding."
                                ),
                            ),
                        )
                    )

        ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return [entry for _, _, entry in ranked[:bounded_limit]]

    def _record_action(
        self,
        candidate_id: str,
        allowed_statuses: set[CandidateStatus],
        new_status: CandidateStatus,
        action: CandidateReviewAction,
        actor: str,
        rationale: str,
        evidence_supports_pattern: Optional[bool] = None,
    ) -> CandidateRecord:
        event = CandidateReviewEvent(
            action=action,
            actor=actor,
            rationale=rationale,
            evidence_supports_pattern=evidence_supports_pattern,
            timestamp=_now(),
        )
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            current = self._fetch_record(connection, candidate_id)
            if current.status not in allowed_statuses:
                raise InvalidCandidateTransitionError(
                    f"Cannot {action.value} a candidate in {current.status.value} status."
                )
            updated_at = event.timestamp.isoformat()
            connection.execute(
                "UPDATE candidates SET status = ?, updated_at = ? WHERE candidate_id = ?",
                (new_status.value, updated_at, candidate_id),
            )
            connection.execute(
                """
                INSERT INTO candidate_review_events (
                    candidate_id, action, actor, rationale, provenance,
                    evidence_supports_pattern, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    candidate_id,
                    action.value,
                    event.actor,
                    event.rationale,
                    event.provenance,
                    (
                        None
                        if evidence_supports_pattern is None
                        else int(evidence_supports_pattern)
                    ),
                    updated_at,
                ),
            )
            return self._fetch_record(connection, candidate_id)

    def review_candidate(
        self,
        candidate_id: str,
        actor: str,
        rationale: str,
    ) -> CandidateRecord:
        """Record an explicit review; reviewing a rejected item reopens it."""
        current = self.get_candidate(candidate_id)
        if current.status == CandidateStatus.REJECTED:
            allowed = {CandidateStatus.REJECTED}
            next_status = CandidateStatus.CANDIDATE
        else:
            allowed = {CandidateStatus.CANDIDATE}
            next_status = CandidateStatus.CANDIDATE
        return self._record_action(
            candidate_id,
            allowed,
            next_status,
            CandidateReviewAction.REVIEWED,
            actor,
            rationale,
        )

    def validate_candidate(
        self,
        candidate_id: str,
        actor: str,
        rationale: str,
        evidence_supports_pattern: bool,
    ) -> CandidateRecord:
        """Validate only after an explicit reviewer assertion beyond quote presence."""
        if evidence_supports_pattern is not True:
            raise InvalidCandidateTransitionError(
                "Validation requires an explicit assessment that evidence supports the pattern."
            )
        return self._record_action(
            candidate_id,
            {CandidateStatus.CANDIDATE},
            CandidateStatus.VALIDATED,
            CandidateReviewAction.VALIDATED,
            actor,
            rationale,
            evidence_supports_pattern=True,
        )

    def reject_candidate(
        self,
        candidate_id: str,
        actor: str,
        rationale: str,
    ) -> CandidateRecord:
        return self._record_action(
            candidate_id,
            {CandidateStatus.CANDIDATE, CandidateStatus.VALIDATED},
            CandidateStatus.REJECTED,
            CandidateReviewAction.REJECTED,
            actor,
            rationale,
        )

    def promote_candidate(
        self,
        candidate_id: str,
        actor: str,
        rationale: str,
    ) -> CandidateRecord:
        """Mark validated knowledge as advisory; never changes detector rules."""
        return self._record_action(
            candidate_id,
            {CandidateStatus.VALIDATED},
            CandidateStatus.PROMOTED,
            CandidateReviewAction.PROMOTED,
            actor,
            rationale,
        )
