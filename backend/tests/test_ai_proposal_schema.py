"""Contract tests for the separate, untrusted AI proposal schema."""

import pytest
from pydantic import ValidationError

from app.schemas import (
    AIProposal,
    AnalyzeRequest,
    AnalyzeResponse,
    AnalyzeStatus,
    EvidenceLevel,
    Finding,
    FindingCategory,
    FindingSeverity,
)


def _valid_proposal_data() -> dict:
    return {
        "candidate_pattern": "unclear cancellation path",
        "proposed_category": FindingCategory.CANCELLATION_REFUND_CLARITY,
        "evidence_quote": "Cancel by contacting support",
        "explanation": "The cancellation process may require contacting support.",
    }


_PROPOSAL_FIELD_MAX_LENGTHS = {
    "candidate_pattern": 500,
    "evidence_quote": 1_000,
    "explanation": 2_000,
    "recommendation": 2_000,
}


def test_valid_ai_proposal_is_accepted_with_untrusted_defaults():
    proposal = AIProposal.model_validate(_valid_proposal_data())

    assert proposal.candidate_pattern == "unclear cancellation path"
    assert proposal.proposed_category == FindingCategory.CANCELLATION_REFUND_CLARITY
    assert proposal.evidence_quote == "Cancel by contacting support"
    assert proposal.recommendation is None
    assert proposal.provenance == "ai"
    assert proposal.status == "pending_validation"


@pytest.mark.parametrize(
    "field",
    ["candidate_pattern", "evidence_quote", "explanation"],
)
def test_ai_proposal_rejects_missing_required_fields(field: str):
    data = _valid_proposal_data()
    del data[field]

    with pytest.raises(ValidationError):
        AIProposal.model_validate(data)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("candidate_pattern", "   "),
        ("evidence_quote", ""),
        ("explanation", " "),
        ("proposed_category", "unapproved_category"),
        ("provenance", "deterministic"),
    ],
)
def test_ai_proposal_rejects_invalid_required_or_constrained_values(field: str, value: str):
    data = _valid_proposal_data()
    data[field] = value

    with pytest.raises(ValidationError):
        AIProposal.model_validate(data)


@pytest.mark.parametrize("status", ["trusted", "validated", "promoted"])
def test_ai_proposal_cannot_be_assigned_a_trusted_status(status: str):
    data = _valid_proposal_data()
    data["status"] = status

    with pytest.raises(ValidationError):
        AIProposal.model_validate(data)


def test_ai_proposal_rejects_extra_trust_fields():
    data = _valid_proposal_data()
    data["trusted"] = True

    with pytest.raises(ValidationError):
        AIProposal.model_validate(data)


def test_ai_proposal_supports_unfamiliar_candidate_without_expanding_category_enum():
    data = _valid_proposal_data()
    data["candidate_pattern"] = "unfamiliar checkout interaction"
    data["proposed_category"] = None

    proposal = AIProposal.model_validate(data)

    assert proposal.candidate_pattern == "unfamiliar checkout interaction"
    assert proposal.proposed_category is None


def test_ai_proposal_can_explicitly_represent_an_unavailable_evidence_quote():
    data = _valid_proposal_data()
    data["evidence_quote"] = None

    proposal = AIProposal.model_validate(data)

    assert proposal.evidence_quote is None


@pytest.mark.parametrize(("field", "max_length"), _PROPOSAL_FIELD_MAX_LENGTHS.items())
def test_ai_proposal_text_fields_enforce_maximum_length(field: str, max_length: int):
    data = _valid_proposal_data()
    data[field] = "x" * max_length

    proposal = AIProposal.model_validate(data)

    assert len(getattr(proposal, field)) == max_length

    data[field] += "x"
    with pytest.raises(ValidationError):
        AIProposal.model_validate(data)


def test_ai_proposal_allows_null_recommendation():
    data = _valid_proposal_data()
    data["recommendation"] = None

    proposal = AIProposal.model_validate(data)

    assert proposal.recommendation is None


def test_finding_and_analyze_response_contracts_remain_unchanged():
    finding = Finding(
        id="det-1",
        category=FindingCategory.RECURRING_PAYMENT,
        severity=FindingSeverity.INFO,
        evidence_level=EvidenceLevel.EXPLICIT,
        evidence_text="$9.99 per month",
        explanation="A recurring payment is stated.",
        confidence=1.0,
        recommendation="Review the renewal terms.",
    )
    assert set(finding.model_dump()) == {
        "id",
        "category",
        "severity",
        "evidence_level",
        "evidence_text",
        "explanation",
        "confidence",
        "missing_information",
        "recommendation",
    }

    response = AnalyzeResponse.model_validate(
        {
            "status": "ok",
            "summary": "Subscription terms found.",
            "findings": [finding.model_dump()],
            "commitment_map": {"unknowns": []},
            "price_integrity": {"observations": [], "reason": "known"},
        }
    )
    assert response.status == AnalyzeStatus.OK
    assert response.findings == [finding]
    assert "ai_proposals" not in response.model_dump()

    request = AnalyzeRequest(
        page_title="Checkout",
        page_url="https://example.test/checkout",
        page_text="$9.99 per month",
    )
    assert set(request.model_dump()) == {
        "page_title",
        "page_url",
        "page_text",
        "scan_id",
        "locale",
    }
