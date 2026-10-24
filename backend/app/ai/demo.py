"""Explicit offline demonstration of proposal comparison and candidate storage."""

import json
from pathlib import Path
from typing import Optional, Union

from app.ai.knowledge_base import CandidateKnowledgeBase
from app.ai.proposals import MockAIProposalProvider
from app.analyzer import analyze_page_with_proposal_comparison
from app.config import Settings
from app.schemas import AnalyzeRequest


DEMO_PAGE_TEXT = (
    "Only 3 seats left! "
    "Your subscription renews at $19.99 per month. "
    "Cancel by calling customer service."
)


def run_offline_demo(
    database_path: Optional[Union[Path, str]] = None,
) -> dict:
    """Run synthetic, deterministic examples and persist only candidate records."""
    request = AnalyzeRequest(
        page_title="Synthetic offline demonstration",
        page_url="https://demo.invalid/checkout",
        page_text=DEMO_PAGE_TEXT,
        locale="en",
    )
    result = analyze_page_with_proposal_comparison(
        request=request,
        settings=Settings(environment="demo"),
        ai_proposal_provider=MockAIProposalProvider(),
    )
    knowledge_base = CandidateKnowledgeBase(database_path)
    stored_candidates = []
    for comparison in result.ai_comparison.results:
        if comparison.proposal is not None:
            stored_candidates.append(
                knowledge_base.add_proposal(comparison.proposal, source_type="mock")
            )

    return {
        "source": "offline_mock",
        "notice": "Synthetic mock proposals; not a trained model or real AI analysis.",
        "analysis": result.analysis.model_dump(mode="json"),
        "ai_comparison": result.ai_comparison.model_dump(mode="json"),
        "retrieved_knowledge": [
            entry.model_dump(mode="json")
            for entry in knowledge_base.retrieve_relevant(DEMO_PAGE_TEXT)
        ],
        "stored_candidates": [
            record.model_dump(mode="json") for record in stored_candidates
        ],
        "database_path": str(knowledge_base.database_path),
    }


def main() -> None:
    print(json.dumps(run_offline_demo(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
