import sqlite3

import pytest
from pydantic import ValidationError

from app.ai.knowledge_base import (
    CandidateKnowledgeBase,
    CandidateNotFoundError,
    CandidateStatus,
    InvalidCandidateTransitionError,
    KnowledgeBaseCorruptError,
)
from app.schemas import AIProposal


@pytest.fixture
def knowledge_base(tmp_path):
    return CandidateKnowledgeBase(tmp_path / "candidates.sqlite3")


def _proposal(**updates):
    data = {
        "candidate_pattern": "unclear cancellation flow",
        "proposed_category": None,
        "evidence_quote": "Cancel by calling customer service.",
        "explanation": "The page describes a phone-only cancellation process.",
        "recommendation": "Review the available cancellation methods.",
    }
    data.update(updates)
    return AIProposal.model_validate(data)


def test_proposal_persists_across_reload_with_stable_id_and_no_page_fields(tmp_path):
    database_path = tmp_path / "persisted.sqlite3"
    store = CandidateKnowledgeBase(database_path)
    original = store.add_proposal(_proposal())

    reloaded = CandidateKnowledgeBase(database_path).get_candidate(original.candidate_id)

    assert reloaded == original
    assert reloaded.status == CandidateStatus.CANDIDATE
    assert reloaded.source_type == "ai"
    with sqlite3.connect(database_path) as connection:
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(candidates)")
        }
    assert "page_text" not in columns
    assert "page_url" not in columns
    assert "page_title" not in columns


def test_duplicate_proposal_is_idempotent_and_does_not_reset_lifecycle(knowledge_base):
    first = knowledge_base.add_proposal(_proposal())
    validated = knowledge_base.validate_candidate(
        first.candidate_id,
        actor="reviewer",
        rationale="Reviewed the displayed cancellation flow and supporting context.",
        evidence_supports_pattern=True,
    )

    duplicate = knowledge_base.add_proposal(_proposal())

    assert duplicate.candidate_id == first.candidate_id
    assert duplicate.status == CandidateStatus.VALIDATED
    assert duplicate.review_history == validated.review_history
    assert len(knowledge_base.list_candidates()) == 1


def test_malformed_proposal_is_rejected_without_persisting(knowledge_base):
    with pytest.raises(ValidationError):
        knowledge_base.add_proposal(
            {
                "candidate_pattern": " ",
                "evidence_quote": None,
                "explanation": "Blank label is invalid.",
                "provenance": "ai",
                "status": "pending_validation",
            }
        )

    assert knowledge_base.list_candidates() == []


def test_review_validate_and_promote_require_explicit_lifecycle_actions(knowledge_base):
    candidate = knowledge_base.add_proposal(_proposal())
    reviewed = knowledge_base.review_candidate(
        candidate.candidate_id,
        actor="reviewer",
        rationale="Reviewed the complete synthetic checkout excerpt.",
    )
    assert reviewed.status == CandidateStatus.CANDIDATE
    assert reviewed.review_history[-1].provenance == "manual_review"

    with pytest.raises(InvalidCandidateTransitionError):
        knowledge_base.promote_candidate(
            candidate.candidate_id,
            actor="reviewer",
            rationale="Attempted before validation.",
        )

    with pytest.raises(InvalidCandidateTransitionError):
        knowledge_base.validate_candidate(
            candidate.candidate_id,
            actor="reviewer",
            rationale="The quote exists, so this must not validate.",
            evidence_supports_pattern=False,
        )

    validated = knowledge_base.validate_candidate(
        candidate.candidate_id,
        actor="reviewer",
        rationale="Independent review supports the described cancellation friction.",
        evidence_supports_pattern=True,
    )
    assert validated.status == CandidateStatus.VALIDATED
    assert validated.review_history[-1].rationale.startswith("Independent review")
    assert validated.review_history[-1].evidence_supports_pattern is True

    promoted = knowledge_base.promote_candidate(
        candidate.candidate_id,
        actor="maintainer",
        rationale="Approved for advisory knowledge-base use only.",
    )
    assert promoted.status == CandidateStatus.PROMOTED
    assert promoted.review_history[-1].provenance == "manual_review"
    assert not isinstance(promoted, AIProposal)


def test_rejected_candidate_requires_new_review_then_validation_before_promotion(
    knowledge_base,
):
    candidate = knowledge_base.add_proposal(_proposal())
    rejected = knowledge_base.reject_candidate(
        candidate.candidate_id,
        actor="reviewer",
        rationale="Current evidence does not support the proposed pattern.",
    )
    assert rejected.status == CandidateStatus.REJECTED

    with pytest.raises(InvalidCandidateTransitionError):
        knowledge_base.promote_candidate(
            candidate.candidate_id,
            actor="maintainer",
            rationale="Cannot skip reconsideration.",
        )

    reopened = knowledge_base.review_candidate(
        candidate.candidate_id,
        actor="reviewer",
        rationale="New manual review explicitly reopens this candidate.",
    )
    assert reopened.status == CandidateStatus.CANDIDATE

    validated = knowledge_base.validate_candidate(
        candidate.candidate_id,
        actor="reviewer",
        rationale="New evidence supports the described pattern.",
        evidence_supports_pattern=True,
    )
    assert validated.status == CandidateStatus.VALIDATED
    assert knowledge_base.promote_candidate(
        candidate.candidate_id,
        actor="maintainer",
        rationale="Promoted after the new explicit review.",
    ).status == CandidateStatus.PROMOTED


def test_invalid_persisted_record_is_reported_not_silently_accepted(
    knowledge_base,
):
    candidate = knowledge_base.add_proposal(_proposal())
    with sqlite3.connect(knowledge_base.database_path) as connection:
        connection.execute("PRAGMA ignore_check_constraints = ON")
        connection.execute(
            "UPDATE candidates SET status = 'trusted' WHERE candidate_id = ?",
            (candidate.candidate_id,),
        )

    with pytest.raises(KnowledgeBaseCorruptError):
        knowledge_base.get_candidate(candidate.candidate_id)


def test_missing_candidate_raises_a_clear_not_found_error(knowledge_base):
    with pytest.raises(CandidateNotFoundError):
        knowledge_base.get_candidate("cand_" + "0" * 64)


@pytest.mark.parametrize(
    ("page_text", "entry_id", "category"),
    [
        (
            "Start a free 7-day trial; then billing begins.",
            "free-trial-conversion",
            "free_trial_conversion",
        ),
        (
            "Your subscription renews automatically every month.",
            "recurring-payments",
            "recurring_payment",
        ),
        (
            "A separate service fee is added at checkout.",
            "additional-fees",
            "additional_fee",
        ),
        (
            "Cancel by calling customer service.",
            "cancellation-friction",
            "cancellation_refund_clarity",
        ),
        (
            "Only 2 seats left! Offer ends in 5 minutes.",
            "urgency-pressure",
            "urgency_pressure",
        ),
    ],
)
def test_retrieves_relevant_starter_guidance_with_cautions(
    knowledge_base,
    page_text,
    entry_id,
    category,
):
    entries = knowledge_base.retrieve_relevant(page_text)

    match = next(entry for entry in entries if entry.entry_id == entry_id)
    assert match.source == "curated"
    assert match.category.value == category
    assert match.evidence_signals
    assert match.caution


def test_retrieval_returns_empty_for_blank_or_unrelated_text(knowledge_base):
    assert knowledge_base.retrieve_relevant("") == []
    assert knowledge_base.retrieve_relevant("Ordinary product details.") == []


def test_retrieval_is_bounded_and_excludes_unpromoted_candidates(knowledge_base):
    page_text = "Your subscription renews at $19.99 per month."
    proposal = _proposal(
        candidate_pattern="Automatic renewal",
        proposed_category="recurring_payment",
        evidence_quote=page_text,
        explanation="An earlier candidate described recurring billing.",
        recommendation="Check the stated renewal terms.",
    )
    candidate = knowledge_base.add_proposal(proposal)

    assert all(
        entry.entry_id != candidate.candidate_id
        for entry in knowledge_base.retrieve_relevant(page_text, limit=50)
    )

    knowledge_base.validate_candidate(
        candidate.candidate_id,
        actor="reviewer",
        rationale="Reviewed the prior evidence and candidate independently.",
        evidence_supports_pattern=True,
    )
    knowledge_base.promote_candidate(
        candidate.candidate_id,
        actor="maintainer",
        rationale="Promoted as advisory prior guidance after review.",
    )

    entries = knowledge_base.retrieve_relevant(page_text, limit=50)
    prior = next(entry for entry in entries if entry.entry_id == candidate.candidate_id)
    assert len(entries) <= 10
    assert prior.source == "promoted_candidate"
    assert prior.prior_evidence_quote == page_text
    assert "not evidence from the current page" in prior.caution
