from app.ai.demo import DEMO_PAGE_TEXT, run_offline_demo
from app.ai.proposals import MockAIProposalProvider
from app.schemas import AnalyzeResponse


def test_mock_provider_is_stable_and_only_quotes_text_present_in_input():
    provider = MockAIProposalProvider()

    first = provider.propose("title", "https://demo.invalid", DEMO_PAGE_TEXT)
    second = provider.propose("title", "https://demo.invalid", DEMO_PAGE_TEXT)
    unrelated = provider.propose("title", "https://demo.invalid", "Ordinary checkout.")

    assert provider.is_configured
    assert first == second
    assert len(first) == 3
    assert all(proposal.evidence_quote in DEMO_PAGE_TEXT for proposal in first)
    assert unrelated == ()


def test_offline_demo_runs_pipeline_and_persists_advisory_candidates(tmp_path):
    result = run_offline_demo(tmp_path / "demo.sqlite3")

    assert result["source"] == "offline_mock"
    assert "not a trained model or real AI" in result["notice"]
    AnalyzeResponse.model_validate(result["analysis"])
    assert len(result["stored_candidates"]) == 3
    assert all(record["status"] == "candidate" for record in result["stored_candidates"])
    assert all(record["provenance"] == "ai" for record in result["stored_candidates"])
    assert all(record["source_type"] == "mock" for record in result["stored_candidates"])
    assert all("page_text" not in record for record in result["stored_candidates"])
    assert {
        entry["entry_id"] for entry in result["retrieved_knowledge"]
    } == {
        "recurring-payments",
        "cancellation-friction",
        "urgency-pressure",
    }

    repeated = run_offline_demo(tmp_path / "demo.sqlite3")
    assert repeated["stored_candidates"] == result["stored_candidates"]
