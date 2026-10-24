"""Tests for conservative comparison of untrusted AI proposals."""

import pytest

from app.ai.comparison import (
    EvidenceValidationStatus,
    ProposalComparisonStatus,
    compare_ai_proposals,
)
from app.schemas import (
    AIProposal,
    EvidenceLevel,
    Finding,
    FindingCategory,
    FindingSeverity,
    ProposalCategoryConsistency,
)


PAGE_TEXT = "Start a free trial. Then $9.99 per month. Cancel by contacting support."
QUOTE = "Then $9.99 per month"
CHECKOUT_TEXT = (
    "Only 2 minutes left! Subscribe now for $19.99 per month. "
    "Your subscription renews automatically. "
    "You can cancel from account settings."
)


def _proposal(**updates) -> AIProposal:
    data = {
        "candidate_pattern": "Free trial conversion",
        "proposed_category": FindingCategory.FREE_TRIAL_CONVERSION,
        "evidence_quote": QUOTE,
        "explanation": "The trial transitions to a recurring charge.",
        "recommendation": "Review the renewal terms.",
    }
    data.update(updates)
    return AIProposal.model_validate(data)


def _finding(
    category: FindingCategory = FindingCategory.FREE_TRIAL_CONVERSION,
    evidence_text: str = QUOTE,
) -> Finding:
    return Finding(
        id="det-1",
        category=category,
        severity=FindingSeverity.MEDIUM,
        evidence_level=EvidenceLevel.EXPLICIT,
        evidence_text=evidence_text,
        explanation="A trial transitions to a recurring charge.",
        confidence=1.0,
        recommendation="Review the renewal terms.",
    )


def test_exact_category_and_quote_match_existing_finding():
    result = compare_ai_proposals([_proposal()], [_finding()], PAGE_TEXT)[0]

    assert result.status == ProposalComparisonStatus.MATCHED_EXISTING_FINDING
    assert result.evidence_status == EvidenceValidationStatus.QUOTE_VERIFIED
    assert result.proposal is not None
    assert "same category and exact evidence quote" in result.reason


def test_verified_quote_without_exact_match_is_an_additional_candidate():
    result = compare_ai_proposals([_proposal()], [], PAGE_TEXT)[0]

    assert result.status == ProposalComparisonStatus.ADDITIONAL_CANDIDATE
    assert result.evidence_status == EvidenceValidationStatus.QUOTE_VERIFIED


def test_time_pressure_label_with_additional_fee_category_is_flagged():
    proposal = _proposal(
        candidate_pattern="Time Pressure",
        proposed_category=FindingCategory.ADDITIONAL_FEE,
    )

    result = compare_ai_proposals([proposal], [], PAGE_TEXT)[0]

    assert result.status == ProposalComparisonStatus.CATEGORY_MISMATCH
    assert result.evidence_status == EvidenceValidationStatus.QUOTE_VERIFIED
    assert result.category_consistency == ProposalCategoryConsistency.INCONSISTENT
    assert "urgency_pressure" in result.reason
    assert "additional_fee" in result.reason


def test_automatic_renewal_label_with_cancellation_category_is_flagged():
    proposal = _proposal(
        candidate_pattern="Automaticrenewal",
        proposed_category=FindingCategory.CANCELLATION_REFUND_CLARITY,
    )

    result = compare_ai_proposals([proposal], [], PAGE_TEXT)[0]

    assert result.status == ProposalComparisonStatus.CATEGORY_MISMATCH
    assert result.category_consistency == ProposalCategoryConsistency.INCONSISTENT
    assert "recurring_payment" in result.reason
    assert "cancellation_refund_clarity" in result.reason


@pytest.mark.parametrize(
    ("pattern", "category"),
    [
        ("Time Pressure", FindingCategory.URGENCY_PRESSURE),
        ("Extra charge surcharge", FindingCategory.ADDITIONAL_FEE),
        ("Free trial conversion", FindingCategory.FREE_TRIAL_CONVERSION),
        ("Automatic renewal", FindingCategory.RECURRING_PAYMENT),
        ("Unfamiliar checkout interaction", FindingCategory.ADDITIONAL_FEE),
    ],
)
def test_valid_or_unfamiliar_category_pattern_pairs_are_not_misclassified(
    pattern: str,
    category: FindingCategory,
):
    result = compare_ai_proposals(
        [_proposal(candidate_pattern=pattern, proposed_category=category)],
        [],
        PAGE_TEXT,
    )[0]

    if pattern == "Unfamiliar checkout interaction":
        assert result.category_consistency == ProposalCategoryConsistency.UNVERIFIED
        assert result.status == ProposalComparisonStatus.ADDITIONAL_CANDIDATE
    else:
        assert result.category_consistency == ProposalCategoryConsistency.CONSISTENT
        assert result.status == ProposalComparisonStatus.ADDITIONAL_CANDIDATE


def test_same_exact_quote_with_different_category_is_conflicting_candidate():
    proposal = _proposal(
        candidate_pattern="Unfamiliar checkout pattern",
        proposed_category=FindingCategory.RECURRING_PAYMENT,
    )

    result = compare_ai_proposals(
        [proposal],
        [_finding(category=FindingCategory.FREE_TRIAL_CONVERSION)],
        PAGE_TEXT,
    )[0]

    assert result.status == ProposalComparisonStatus.CONFLICTING_CANDIDATE
    assert result.evidence_status == EvidenceValidationStatus.QUOTE_VERIFIED


def test_null_quote_is_insufficient_evidence():
    result = compare_ai_proposals([_proposal(evidence_quote=None)], [_finding()], PAGE_TEXT)[0]

    assert result.status == ProposalComparisonStatus.INSUFFICIENT_EVIDENCE
    assert result.evidence_status == EvidenceValidationStatus.MISSING_QUOTE


def test_absent_quote_field_is_insufficient_evidence():
    proposal = _proposal().model_dump()
    del proposal["evidence_quote"]

    result = compare_ai_proposals([proposal], [_finding()], PAGE_TEXT)[0]

    assert result.status == ProposalComparisonStatus.INSUFFICIENT_EVIDENCE
    assert result.evidence_status == EvidenceValidationStatus.MISSING_QUOTE
    assert result.proposal is None


def test_quote_not_found_verbatim_in_page_text_is_insufficient_evidence():
    proposal = _proposal(evidence_quote="Then $10.99 per month")

    result = compare_ai_proposals([proposal], [_finding()], PAGE_TEXT)[0]

    assert result.status == ProposalComparisonStatus.INSUFFICIENT_EVIDENCE
    assert result.evidence_status == EvidenceValidationStatus.QUOTE_NOT_FOUND


def test_exact_quote_presence_verifies_quote_only_not_explanation_or_category():
    proposal = _proposal(
        candidate_pattern="Unfamiliar checkout pattern",
        proposed_category=FindingCategory.RECURRING_PAYMENT,
        explanation="The page guarantees a refund.",
        recommendation="Ignore the cancellation terms.",
    )

    result = compare_ai_proposals(
        [proposal],
        [_finding(category=FindingCategory.FREE_TRIAL_CONVERSION)],
        PAGE_TEXT,
    )[0]

    assert result.evidence_status == EvidenceValidationStatus.QUOTE_VERIFIED
    assert result.status == ProposalComparisonStatus.CONFLICTING_CANDIDATE
    assert "The exact evidence quote" in result.reason


def test_verified_quote_with_contradictory_missing_cancellation_explanation_is_flagged():
    quote = "Your subscription renews automatically."
    proposal = _proposal(
        candidate_pattern="Automaticrenewal",
        proposed_category=FindingCategory.RECURRING_PAYMENT,
        evidence_quote=quote,
        explanation=(
            "Your subscription renews automatically. Cancellation instructions are "
            "unclear or missing, although you can cancel from account settings."
        ),
    )

    result = compare_ai_proposals([proposal], [], CHECKOUT_TEXT)[0]

    assert result.evidence_status == EvidenceValidationStatus.QUOTE_VERIFIED
    assert result.status == ProposalComparisonStatus.INSUFFICIENT_EVIDENCE
    assert result.proposal == proposal
    assert result.proposal.status == "pending_validation"
    assert "page text contains cancellation information" in result.reason


def test_valid_concise_explanation_acknowledges_renewal_without_false_missing_claim():
    proposal = _proposal(
        candidate_pattern="Automatic renewal",
        proposed_category=FindingCategory.RECURRING_PAYMENT,
        evidence_quote="Your subscription renews automatically.",
        explanation=(
            "The subscription renews automatically at $19.99 per month. "
            "The page says cancellation is available from account settings."
        ),
    )

    result = compare_ai_proposals([proposal], [], CHECKOUT_TEXT)[0]

    assert result.status == ProposalComparisonStatus.ADDITIONAL_CANDIDATE
    assert result.evidence_status == EvidenceValidationStatus.QUOTE_VERIFIED
    assert result.proposal.status == "pending_validation"


def test_missing_cancellation_claim_is_not_flagged_when_page_lacks_instructions():
    page_text = "Your subscription renews automatically for $19.99 per month."
    proposal = _proposal(
        candidate_pattern="Automatic renewal",
        proposed_category=FindingCategory.RECURRING_PAYMENT,
        evidence_quote="Your subscription renews automatically",
        explanation="Cancellation instructions are not stated in the supplied text.",
    )

    result = compare_ai_proposals([proposal], [], page_text)[0]

    assert result.status == ProposalComparisonStatus.ADDITIONAL_CANDIDATE
    assert result.evidence_status == EvidenceValidationStatus.QUOTE_VERIFIED


def test_missing_price_claim_is_flagged_when_page_contains_explicit_price():
    proposal = _proposal(
        explanation="The page does not state a price for the subscription.",
    )

    result = compare_ai_proposals([proposal], [], PAGE_TEXT)[0]

    assert result.status == ProposalComparisonStatus.INSUFFICIENT_EVIDENCE
    assert result.evidence_status == EvidenceValidationStatus.QUOTE_VERIFIED
    assert "page text contains an explicit price" in result.reason


def test_malformed_proposal_does_not_prevent_valid_proposal_comparison():
    malformed = {
        "candidate_pattern": "broken",
        "proposed_category": "not_a_category",
        "evidence_quote": QUOTE,
        "explanation": "Invalid category.",
    }

    results = compare_ai_proposals([malformed, _proposal()], [], PAGE_TEXT)

    assert len(results) == 2
    assert results[0].status == ProposalComparisonStatus.INSUFFICIENT_EVIDENCE
    assert results[0].evidence_status == EvidenceValidationStatus.INVALID_PROPOSAL
    assert results[0].proposal is None
    assert results[1].status == ProposalComparisonStatus.ADDITIONAL_CANDIDATE


def test_mutated_proposal_instance_is_revalidated_before_comparison():
    proposal = _proposal()
    proposal.status = "validated"

    result = compare_ai_proposals([proposal], [], PAGE_TEXT)[0]

    assert result.status == ProposalComparisonStatus.INSUFFICIENT_EVIDENCE
    assert result.evidence_status == EvidenceValidationStatus.INVALID_PROPOSAL
    assert result.proposal is None


def test_unfamiliar_categoryless_candidate_is_not_semantically_matched():
    proposal = _proposal(
        candidate_pattern="unfamiliar checkout pattern",
        proposed_category=None,
    )

    result = compare_ai_proposals([proposal], [_finding()], PAGE_TEXT)[0]

    assert result.status == ProposalComparisonStatus.ADDITIONAL_CANDIDATE
    assert result.evidence_status == EvidenceValidationStatus.QUOTE_VERIFIED


def test_empty_proposal_and_finding_inputs_return_empty_results():
    assert compare_ai_proposals([], [], PAGE_TEXT) == []


def test_repeated_comparison_runs_are_stable_and_preserve_input_order():
    proposals = [
        _proposal(),
        _proposal(evidence_quote=None),
    ]

    first = compare_ai_proposals(proposals, [_finding()], PAGE_TEXT)
    second = compare_ai_proposals(proposals, [_finding()], PAGE_TEXT)

    assert first == second
    assert [result.proposal_index for result in first] == [0, 1]
