"""Automated test suite verifying the 4 judge-ready demo HTML fixtures."""

import os
import re
from pathlib import Path
import pytest
from app.analyzer import analyze_page_content
from app.config import Settings
from app.schemas import AnalyzeRequest, AnalyzeStatus, FindingCategory, PriceIntegrityReason

FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent / "fixtures"
settings = Settings(environment="test", llm_api_key=None)


def _extract_text_from_html(html_content: str) -> str:
    """Basic extraction simulating browser visible text extraction from HTML fixture."""
    # Strip script/style
    clean = re.sub(r"(?is)<(script|style).*?>.*?</\1>", "", html_content)
    # Strip HTML tags but preserve line breaks
    clean = re.sub(r"(?i)<br\s*/?>", "\n", clean)
    clean = re.sub(r"(?i)</(?:p|div|h1|h2|h3|li|tr|header)>", "\n", clean)
    clean = re.sub(r"<[^>]+>", " ", clean)
    # Normalize spaces per line
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in clean.splitlines()]
    return "\n".join(l for l in lines if l)


def test_fixture_1_subscription_trial():
    html_path = FIXTURES_DIR / "1_subscription_trial.html"
    assert html_path.exists(), f"Fixture missing: {html_path}"
    page_text = _extract_text_from_html(html_path.read_text(encoding="utf-8"))

    req = AnalyzeRequest(
        page_title="StreamCloud Pro - Free Trial",
        page_url="http://localhost:8080/1_subscription_trial.html",
        page_text=page_text,
    )
    res = analyze_page_content(req, settings)

    assert res.status == AnalyzeStatus.OK
    assert res.commitment_map.trial_duration == "14 days"
    assert res.commitment_map.future_charge is not None
    assert res.commitment_map.future_charge.amount == "29.00"
    assert res.commitment_map.future_charge.interval == "monthly"
    assert res.commitment_map.amount_due_now is not None
    assert res.commitment_map.amount_due_now.amount == "0"
    assert any(f.category == FindingCategory.FREE_TRIAL_CONVERSION for f in res.findings)
    assert any("calendar reminder" in item.lower() for item in res.checklist)


def test_fixture_2_transparent_checkout():
    html_path = FIXTURES_DIR / "2_transparent_checkout.html"
    assert html_path.exists(), f"Fixture missing: {html_path}"
    page_text = _extract_text_from_html(html_path.read_text(encoding="utf-8"))

    req = AnalyzeRequest(
        page_title="Apex Gear Supply - Checkout",
        page_url="http://localhost:8080/2_transparent_checkout.html",
        page_text=page_text,
    )
    res = analyze_page_content(req, settings)

    assert res.status == AnalyzeStatus.OK
    assert res.price_integrity is not None
    assert res.price_integrity.reason == PriceIntegrityReason.DISCLOSED_TAX_OR_SHIPPING
    assert res.price_integrity.unexplained_difference is None
    assert len(res.price_integrity.explicit_fees) == 2
    assert len(res.findings) == 0, "Transparent checkout should have no false-positive findings"


def test_fixture_3_unexplained_fee_checkout():
    html_path = FIXTURES_DIR / "3_unexplained_fee_checkout.html"
    assert html_path.exists(), f"Fixture missing: {html_path}"
    page_text = _extract_text_from_html(html_path.read_text(encoding="utf-8"))

    req = AnalyzeRequest(
        page_title="QuickTicket Express - Order Review",
        page_url="http://localhost:8080/3_unexplained_fee_checkout.html",
        page_text=page_text,
    )
    res = analyze_page_content(req, settings)

    assert res.status == AnalyzeStatus.PARTIAL
    assert res.price_integrity is not None
    assert res.price_integrity.reason == PriceIntegrityReason.UNCLEAR
    assert res.price_integrity.unexplained_difference is not None
    assert res.price_integrity.unexplained_difference.amount == "8.00"
    assert any(f.id == "finding-unexplained-checkout-difference" for f in res.findings)


def test_fixture_4_multi_plan_pricing():
    html_path = FIXTURES_DIR / "4_multi_plan_pricing.html"
    assert html_path.exists(), f"Fixture missing: {html_path}"
    page_text = _extract_text_from_html(html_path.read_text(encoding="utf-8"))

    req = AnalyzeRequest(
        page_title="TaskFlow Workspace - Plans & Pricing",
        page_url="http://localhost:8080/4_multi_plan_pricing.html",
        page_text=page_text,
    )
    res = analyze_page_content(req, settings)

    assert len(res.plans) == 3
    plan_names = [p.plan_name for p in res.plans]
    assert "Starter" in plan_names
    assert "Professional" in plan_names
    assert "Enterprise" in plan_names

    # Top-level should not assume one plan is chosen
    assert res.commitment_map.amount_due_now is None
    assert res.commitment_map.future_charge is None

    # Professional plan specifically should reflect 7-day trial
    pro_plan = next(p for p in res.plans if p.plan_name == "Professional")
    assert pro_plan.trial_duration == "7 days"
    assert pro_plan.future_charge is not None
    assert pro_plan.future_charge.amount == "35.00"
