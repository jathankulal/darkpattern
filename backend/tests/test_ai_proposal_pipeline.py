"""Integration tests for the opt-in independent AI proposal pipeline."""

from typing import Iterable, Optional

from fastapi.testclient import TestClient

from app.ai.base import NullAIInterpreter
from app.ai.proposals import AIProposalProvider, NullAIProposalProvider
from app.analyzer import analyze_page_content, analyze_page_with_proposal_comparison
from app.config import Settings
from app.main import app
from app.schemas import (
    AIProposal,
    AIProposalProviderStatus,
    AnalyzeRequest,
    AnalyzeResponse,
    EvidenceValidationStatus,
    Finding,
    FindingCategory,
    ProposalComparisonStatus,
)


PAGE_TEXT = "Start a free 7-day trial. Then $9.99 per month automatically."
QUOTE = "7-day trial"
REQUEST = AnalyzeRequest(
    page_title="Streaming Checkout",
    page_url="https://example.test/checkout",
    page_text=PAGE_TEXT,
    locale="en",
)
SETTINGS = Settings(environment="test", openai_api_key=None)
client = TestClient(app)


def _proposal(
    evidence_quote: Optional[str] = QUOTE,
    category: Optional[FindingCategory] = FindingCategory.FREE_TRIAL_CONVERSION,
) -> AIProposal:
    return AIProposal(
        candidate_pattern="Free trial conversion",
        proposed_category=category,
        evidence_quote=evidence_quote,
        explanation="The trial transitions to a recurring charge.",
        recommendation="Review the renewal terms.",
    )


class MockProposalProvider(AIProposalProvider):
    def __init__(self, proposals: Iterable[AIProposal], configured: bool = True):
        self._proposals = proposals
        self._configured = configured
        self.calls = 0

    @property
    def is_configured(self) -> bool:
        return self._configured

    def propose(
        self,
        page_title: str,
        page_url: str,
        page_text: str,
        locale: Optional[str] = None,
    ) -> Iterable[AIProposal]:
        self.calls += 1
        return self._proposals


class RaisingProposalProvider(AIProposalProvider):
    @property
    def is_configured(self) -> bool:
        return True

    def propose(
        self,
        page_title: str,
        page_url: str,
        page_text: str,
        locale: Optional[str] = None,
    ) -> Iterable[AIProposal]:
        raise RuntimeError("sensitive provider details")


class RaisingProposalIterableProvider(AIProposalProvider):
    @property
    def is_configured(self) -> bool:
        return True

    def propose(
        self,
        page_title: str,
        page_url: str,
        page_text: str,
        locale: Optional[str] = None,
    ) -> Iterable[AIProposal]:
        def broken_proposals() -> Iterable[AIProposal]:
            yield _proposal()
            raise RuntimeError("sensitive comparison details")

        return broken_proposals()


def test_unconfigured_proposal_provider_is_noop_and_makes_no_call():
    provider = MockProposalProvider([], configured=False)

    result = analyze_page_with_proposal_comparison(REQUEST, SETTINGS, provider)

    assert provider.calls == 0
    assert result.ai_comparison.status == AIProposalProviderStatus.UNCONFIGURED
    assert result.ai_comparison.results == []


def test_default_null_provider_is_unconfigured_and_returns_no_proposals():
    provider = NullAIProposalProvider()

    assert provider.is_configured is False
    assert provider.propose(
        REQUEST.page_title,
        REQUEST.page_url,
        REQUEST.page_text,
        REQUEST.locale,
    ) == ()
    result = analyze_page_with_proposal_comparison(REQUEST, SETTINGS)
    assert result.ai_comparison.status == AIProposalProviderStatus.UNCONFIGURED


def test_mock_proposals_produce_comparison_results_separate_from_findings():
    provider = MockProposalProvider([_proposal()])

    result = analyze_page_with_proposal_comparison(REQUEST, SETTINGS, provider)

    assert result.ai_comparison.status == AIProposalProviderStatus.ACTIVE
    assert len(result.ai_comparison.results) == 1
    comparison = result.ai_comparison.results[0]
    assert comparison.status == ProposalComparisonStatus.MATCHED_EXISTING_FINDING
    assert comparison.evidence_status == EvidenceValidationStatus.QUOTE_VERIFIED
    assert comparison.proposal == _proposal()
    assert all(isinstance(finding, Finding) for finding in result.analysis.findings)
    assert all(finding is not comparison.proposal for finding in result.analysis.findings)


def test_active_comparison_limitations_describe_proposal_path_without_stale_ai_claim():
    result = analyze_page_with_proposal_comparison(
        REQUEST,
        SETTINGS,
        MockProposalProvider([_proposal()]),
    )

    assert result.ai_comparison.status == AIProposalProviderStatus.ACTIVE
    assert not any(
        "AI contextual interpretation not configured" in limitation
        for limitation in result.analysis.limitations
    )
    assert any(
        "Trusted findings and financial calculations remain deterministic" in limitation
        and "untrusted candidates" in limitation
        and "do not validate or modify them" in limitation
        for limitation in result.analysis.limitations
    )


def test_proposal_pipeline_preserves_deterministic_findings_and_financials():
    baseline = analyze_page_content(
        REQUEST,
        SETTINGS,
        ai_interpreter=NullAIInterpreter(),
    )
    result = analyze_page_with_proposal_comparison(
        REQUEST,
        SETTINGS,
        MockProposalProvider([_proposal()]),
    )

    assert result.analysis.findings == baseline.findings
    assert result.analysis.commitment_map == baseline.commitment_map
    assert result.analysis.price_integrity == baseline.price_integrity
    assert result.analysis.timeline == baseline.timeline
    assert result.analysis.checklist == baseline.checklist


def test_invalid_provider_proposal_is_reported_without_crashing_or_promotion():
    invalid_proposal = _proposal()
    invalid_proposal.status = "validated"

    result = analyze_page_with_proposal_comparison(
        REQUEST,
        SETTINGS,
        MockProposalProvider([invalid_proposal]),
    )

    assert result.ai_comparison.status == AIProposalProviderStatus.ACTIVE
    comparison = result.ai_comparison.results[0]
    assert comparison.status == ProposalComparisonStatus.INSUFFICIENT_EVIDENCE
    assert comparison.evidence_status == EvidenceValidationStatus.INVALID_PROPOSAL
    assert comparison.proposal is None
    assert result.analysis.findings == analyze_page_content(
        REQUEST,
        SETTINGS,
        ai_interpreter=NullAIInterpreter(),
    ).findings


def test_provider_exception_fails_safely_without_exposing_exception_details():
    result = analyze_page_with_proposal_comparison(
        REQUEST,
        SETTINGS,
        RaisingProposalProvider(),
    )

    assert result.ai_comparison.status == AIProposalProviderStatus.FAILED
    assert result.ai_comparison.results == []
    assert "sensitive provider details" not in str(result.model_dump())
    assert result.analysis.findings == analyze_page_content(
        REQUEST,
        SETTINGS,
        ai_interpreter=NullAIInterpreter(),
    ).findings


def test_comparison_exception_fails_safely_and_retains_deterministic_findings():
    result = analyze_page_with_proposal_comparison(
        REQUEST,
        SETTINGS,
        RaisingProposalIterableProvider(),
    )

    assert result.ai_comparison.status == AIProposalProviderStatus.FAILED
    assert result.ai_comparison.results == []
    assert "sensitive comparison details" not in str(result.model_dump())
    assert result.analysis.findings == analyze_page_content(
        REQUEST,
        SETTINGS,
        ai_interpreter=NullAIInterpreter(),
    ).findings


def test_quote_validation_states_are_returned_in_opt_in_pipeline():
    result = analyze_page_with_proposal_comparison(
        REQUEST,
        SETTINGS,
        MockProposalProvider(
            [
                _proposal(),
                _proposal(evidence_quote=None),
                _proposal(evidence_quote="Not present in source"),
            ]
        ),
    )

    comparisons = result.ai_comparison.results
    assert [item.evidence_status for item in comparisons] == [
        EvidenceValidationStatus.QUOTE_VERIFIED,
        EvidenceValidationStatus.MISSING_QUOTE,
        EvidenceValidationStatus.QUOTE_NOT_FOUND,
    ]
    assert comparisons[1].status == ProposalComparisonStatus.INSUFFICIENT_EVIDENCE
    assert comparisons[2].status == ProposalComparisonStatus.INSUFFICIENT_EVIDENCE
    assert all(item.proposal not in result.analysis.findings for item in comparisons)


def test_repeated_mock_runs_are_stable():
    first = analyze_page_with_proposal_comparison(
        REQUEST,
        SETTINGS,
        MockProposalProvider([_proposal()]),
    )
    second = analyze_page_with_proposal_comparison(
        REQUEST,
        SETTINGS,
        MockProposalProvider([_proposal()]),
    )

    assert first == second


def test_existing_analyze_endpoint_remains_compatible(monkeypatch):
    payload = REQUEST.model_dump()
    monkeypatch.setattr(
        "app.main.settings",
        Settings(environment="test", openai_api_key=None),
    )
    original_response = client.post("/api/v1/analyze", json=payload)
    assert original_response.status_code == 200
    original_data = original_response.json()
    AnalyzeResponse.model_validate(original_data)

    provider = MockProposalProvider([_proposal()])
    monkeypatch.setattr("app.main.get_ai_proposal_provider", lambda: provider)
    comparison_response = client.post("/api/v1/analyze/compare", json=payload)

    assert comparison_response.status_code == 200
    comparison_data = comparison_response.json()
    assert set(original_data) == set(comparison_data["analysis"])
    assert "ai_comparison" not in original_data
    assert comparison_data["ai_comparison"]["status"] == "active"
    assert comparison_data["analysis"]["findings"] == original_data["findings"]


def test_opt_in_endpoint_reports_unconfigured_without_api_key(monkeypatch):
    provider = MockProposalProvider([], configured=False)
    monkeypatch.setattr("app.main.get_ai_proposal_provider", lambda: provider)

    response = client.post("/api/v1/analyze/compare", json=REQUEST.model_dump())

    assert response.status_code == 200
    assert response.json()["ai_comparison"] == {
        "status": "unconfigured",
        "results": [],
    }
    assert provider.calls == 0
