"""Conservative comparison and evidence checks for untrusted AI proposals."""

import re
from typing import Iterable, Sequence

from pydantic import ValidationError

from app.extraction import extract_cancellation_terms, extract_prices_from_text
from app.schemas import (
    AIProposal,
    AIProposalComparisonResult,
    EvidenceValidationStatus,
    Finding,
    FindingCategory,
    ProposalComparisonStatus,
    ProposalCategoryConsistency,
)

_MISSING_CANCELLATION_CLAIM_PATTERNS = (
    re.compile(
        r"\bno\s+(?:clear\s+)?(?:cancell?ation\s+)?"
        r"(?:instructions?|information|method|process|terms?)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bcancell?ation\s+(?:instructions?|information|method|process|terms?)"
        r"\s+(?:(?:are|is|remain|seem|appear)\s+)?"
        r"(?:missing|unclear|absent|unavailable|"
        r"not\s+(?:provided|stated|mentioned|specified|disclosed))\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:the\s+)?(?:page|text)\s+(?:does\s+not|doesn't|fails\s+to)\s+"
        r"(?:provide|state|mention|specify|disclose|include)\s+"
        r"(?:any\s+)?(?:cancell?ation|how\s+to\s+cancel)\b",
        re.IGNORECASE,
    ),
)
_MISSING_PRICE_CLAIM_PATTERNS = (
    re.compile(
        r"\bno\s+(?:clear\s+)?(?:price|pricing|cost|amount|fee)"
        r"(?:\s+information)?\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:price|pricing|cost|amount|fee)\s+"
        r"(?:(?:is|are|remains|seems|appears)\s+)?"
        r"(?:missing|unclear|absent|unavailable|"
        r"not\s+(?:provided|stated|mentioned|specified|disclosed))\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:the\s+)?(?:page|text)\s+(?:does\s+not|doesn't|fails\s+to)\s+"
        r"(?:provide|state|mention|specify|disclose|include)\s+"
        r"(?:(?:a|the|any)\s+)?(?:price|pricing|cost|amount|fee)\b",
        re.IGNORECASE,
    ),
)

_CATEGORY_CUES: dict[FindingCategory, tuple[str, ...]] = {
    FindingCategory.RECURRING_PAYMENT: (
        "recurring payment",
        "recurring billing",
        "subscription renewal",
        "automatic renewal",
        "auto renewal",
    ),
    FindingCategory.FREE_TRIAL_CONVERSION: (
        "free trial",
        "trial conversion",
        "trial-to-paid",
        "trial renewal",
    ),
    FindingCategory.FUTURE_CHARGE_DISCLOSURE: (
        "future charge",
        "renewal disclosure",
        "billing date",
        "renewal amount",
    ),
    FindingCategory.ADDITIONAL_FEE: (
        "additional fee",
        "extra fee",
        "surcharge",
        "service fee",
        "hidden fee",
        "extra charge",
    ),
    FindingCategory.CANCELLATION_REFUND_CLARITY: (
        "cancellation",
        "cancel method",
        "refund policy",
    ),
    FindingCategory.URGENCY_PRESSURE: (
        "urgency",
        "time pressure",
        "scarcity",
        "countdown",
        "limited time",
        "limited availability",
    ),
    FindingCategory.MISSING_COMMITMENT_INFO: (
        "missing commitment information",
        "undisclosed commitment term",
        "missing cancellation terms",
    ),
}


def _pattern_category_cues(pattern: str) -> set[FindingCategory]:
    """Return categories signaled by curated, token-based pattern concepts."""
    readable_pattern = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", pattern)
    tokens = re.findall(r"[a-z0-9]+", readable_pattern.casefold())
    compact_pattern = "".join(tokens)
    categories: set[FindingCategory] = set()
    for category, cues in _CATEGORY_CUES.items():
        for cue in cues:
            cue_tokens = re.findall(r"[a-z0-9]+", cue.casefold())
            cue_length = len(cue_tokens)
            cue_matches = cue_length and (
                any(
                    tokens[index : index + cue_length] == cue_tokens
                    for index in range(len(tokens) - cue_length + 1)
                )
                or "".join(cue_tokens) in compact_pattern
            )
            if cue_matches:
                categories.add(category)
                break
    return categories


def _check_category_consistency(
    proposal: AIProposal,
) -> tuple[ProposalCategoryConsistency, set[FindingCategory]]:
    """Flag only recognized label/category contradictions; unknowns stay unverified."""
    if proposal.proposed_category is None:
        return ProposalCategoryConsistency.UNVERIFIED, set()
    categories = _pattern_category_cues(proposal.candidate_pattern)
    if len(categories) != 1:
        return ProposalCategoryConsistency.UNVERIFIED, set()
    if categories == {proposal.proposed_category}:
        return ProposalCategoryConsistency.CONSISTENT, categories
    return ProposalCategoryConsistency.INCONSISTENT, categories


def _invalid_proposal_evidence_status(raw_proposal: object) -> EvidenceValidationStatus:
    """Identify missing quote data separately from other malformed proposal data."""
    if not isinstance(raw_proposal, dict):
        return EvidenceValidationStatus.INVALID_PROPOSAL
    quote = raw_proposal.get("evidence_quote")
    if not isinstance(quote, str) or not quote.strip():
        return EvidenceValidationStatus.MISSING_QUOTE
    return EvidenceValidationStatus.INVALID_PROPOSAL


def _known_explanation_contradiction(
    proposal: AIProposal,
    page_text: str,
) -> str | None:
    """Flag only curated missing-information claims contradicted by extracted facts."""
    explanation = proposal.explanation
    if extract_cancellation_terms(page_text) and any(
        pattern.search(explanation)
        for pattern in _MISSING_CANCELLATION_CLAIM_PATTERNS
    ):
        return (
            "The explanation says cancellation instructions are missing or unclear, "
            "but the page text contains cancellation information; human review is required."
        )

    if extract_prices_from_text(page_text) and any(
        pattern.search(explanation) for pattern in _MISSING_PRICE_CLAIM_PATTERNS
    ):
        return (
            "The explanation says price information is missing or unclear, "
            "but the page text contains an explicit price; human review is required."
        )

    return None


def _classify_verified_proposal(
    proposal: AIProposal,
    deterministic_findings: Sequence[Finding],
) -> tuple[ProposalComparisonStatus, str]:
    """Match only exact quote and category pairs; do not infer semantic similarity."""
    same_quote = [
        finding
        for finding in deterministic_findings
        if isinstance(finding, Finding) and finding.evidence_text == proposal.evidence_quote
    ]

    if proposal.proposed_category is not None and any(
        finding.category == proposal.proposed_category for finding in same_quote
    ):
        return (
            ProposalComparisonStatus.MATCHED_EXISTING_FINDING,
            "An existing finding has the same category and exact evidence quote.",
        )

    if proposal.proposed_category is not None and any(
        finding.category != proposal.proposed_category for finding in same_quote
    ):
        return (
            ProposalComparisonStatus.CONFLICTING_CANDIDATE,
            "The exact evidence quote is associated with a different finding category.",
        )

    return (
        ProposalComparisonStatus.ADDITIONAL_CANDIDATE,
        "The quote exists in page text, but no exact category-and-quote match was established.",
    )


def compare_ai_proposals(
    proposals: Iterable[object],
    deterministic_findings: Sequence[Finding],
    page_text: str,
) -> list[AIProposalComparisonResult]:
    """Validate and compare proposals independently, preserving input order.

    A matching quote proves only that the quoted text occurs in ``page_text``.
    It does not verify the proposal's explanation, category, or recommendation.
    Deterministic comparison requires an exact evidence-quote and category match;
    no semantic-equivalence inference is attempted. Invalid proposals produce an
    insufficient-evidence result without preventing subsequent proposals from
    being processed.
    """
    source_text = page_text if isinstance(page_text, str) else ""
    results: list[AIProposalComparisonResult] = []

    for index, raw_proposal in enumerate(proposals):
        try:
            proposal = (
                AIProposal.model_validate(raw_proposal.model_dump())
                if isinstance(raw_proposal, AIProposal)
                else AIProposal.model_validate(raw_proposal)
            )
        except (ValidationError, TypeError, ValueError):
            evidence_status = _invalid_proposal_evidence_status(raw_proposal)
            if evidence_status == EvidenceValidationStatus.MISSING_QUOTE:
                reason = "The proposal has no usable evidence quote."
            else:
                reason = "The proposal is malformed and cannot be compared."
            results.append(
                AIProposalComparisonResult(
                    proposal_index=index,
                    proposal=None,
                    status=ProposalComparisonStatus.INSUFFICIENT_EVIDENCE,
                    category_consistency=ProposalCategoryConsistency.UNVERIFIED,
                    evidence_status=evidence_status,
                    reason=reason,
                )
            )
            continue

        quote = proposal.evidence_quote
        if quote is None or not quote.strip():
            results.append(
                AIProposalComparisonResult(
                    proposal_index=index,
                    proposal=proposal,
                    status=ProposalComparisonStatus.INSUFFICIENT_EVIDENCE,
                    category_consistency=ProposalCategoryConsistency.UNVERIFIED,
                    evidence_status=EvidenceValidationStatus.MISSING_QUOTE,
                    reason="The proposal has no usable evidence quote.",
                )
            )
            continue

        if quote not in source_text:
            results.append(
                AIProposalComparisonResult(
                    proposal_index=index,
                    proposal=proposal,
                    status=ProposalComparisonStatus.INSUFFICIENT_EVIDENCE,
                    category_consistency=ProposalCategoryConsistency.UNVERIFIED,
                    evidence_status=EvidenceValidationStatus.QUOTE_NOT_FOUND,
                    reason="The proposed quote was not found verbatim in page text.",
                )
            )
            continue

        contradiction = _known_explanation_contradiction(proposal, source_text)
        if contradiction:
            category_consistency, _ = _check_category_consistency(proposal)
            results.append(
                AIProposalComparisonResult(
                    proposal_index=index,
                    proposal=proposal,
                    status=ProposalComparisonStatus.INSUFFICIENT_EVIDENCE,
                    category_consistency=category_consistency,
                    evidence_status=EvidenceValidationStatus.QUOTE_VERIFIED,
                    reason=contradiction,
                )
            )
            continue

        category_consistency, suggested_categories = _check_category_consistency(proposal)
        if category_consistency == ProposalCategoryConsistency.INCONSISTENT:
            expected = sorted(category.value for category in suggested_categories)
            expected_categories = ", ".join(expected)
            results.append(
                AIProposalComparisonResult(
                    proposal_index=index,
                    proposal=proposal,
                    status=ProposalComparisonStatus.CATEGORY_MISMATCH,
                    category_consistency=ProposalCategoryConsistency.INCONSISTENT,
                    evidence_status=EvidenceValidationStatus.QUOTE_VERIFIED,
                    reason=(
                        f"The pattern label suggests {expected_categories}, but the "
                        f"proposal category is {proposal.proposed_category.value}; "
                        "human review is required."
                    ),
                )
            )
            continue

        comparison_status, reason = _classify_verified_proposal(
            proposal,
            deterministic_findings,
        )
        results.append(
            AIProposalComparisonResult(
                proposal_index=index,
                proposal=proposal,
                status=comparison_status,
                category_consistency=category_consistency,
                evidence_status=EvidenceValidationStatus.QUOTE_VERIFIED,
                reason=reason,
            )
        )

    return results
