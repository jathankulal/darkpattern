"""Tests for Phase 7 Financial Commitment Timeline & Annualized Projections."""

from decimal import Decimal
from pathlib import Path
import re
import pytest
from fastapi.testclient import TestClient

from app.analyzer import (
    build_financial_timeline,
    build_plan_timeline,
    calculate_annualized_cost,
)
from app.extraction import run_deterministic_analysis
from app.main import app
from app.schemas import (
    CommitmentMap,
    MoneyKind,
    MoneyValue,
    PlanSummary,
    PriceIntegrity,
    PriceIntegrityReason,
    TimelineValueType,
)

FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent / "fixtures"


def _extract_text_from_html(html_content: str) -> str:
    """Basic extraction simulating browser visible text extraction from HTML fixture."""
    clean = re.sub(r"(?is)<(script|style).*?>.*?</\1>", "", html_content)
    clean = re.sub(r"(?i)<br\s*/?>", "\n", clean)
    clean = re.sub(r"(?i)</(?:p|div|h1|h2|h3|li|tr|header)>", "\n", clean)
    clean = re.sub(r"<[^>]+>", " ", clean)
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in clean.splitlines()]
    return "\n".join(l for l in lines if l)


# ---------------------------------------------------------------------------
# 1. Decimal Annualized Cost Calculation Tests
# ---------------------------------------------------------------------------

def test_annualized_cost_monthly():
    charge = MoneyValue(amount="49.99", currency="USD", kind=MoneyKind.RECURRING, interval="monthly")
    cost, assumptions = calculate_annualized_cost(charge)
    assert cost is not None
    assert cost.amount == "599.88"
    assert cost.currency == "USD"
    assert cost.interval == "annually"
    assert "12 × USD 49.99" in assumptions


def test_annualized_cost_monthly_with_introductory_rate():
    intro = MoneyValue(amount="1.00", currency="USD", kind=MoneyKind.RECURRING, interval="monthly")
    regular = MoneyValue(amount="19.99", currency="USD", kind=MoneyKind.RECURRING, interval="monthly")
    cost, assumptions = calculate_annualized_cost(regular, introductory=intro)
    assert cost is not None
    # 1.00 + 11 * 19.99 = 1.00 + 219.89 = 220.89
    assert cost.amount == "220.89"
    assert "1 initial charge of USD 1.00" in assumptions
    assert "11 regular recurring charges of USD 19.99" in assumptions


def test_annualized_cost_other_intervals():
    intervals = [
        ("quarterly", "100.00", "400.00"),
        ("weekly", "10.00", "520.00"),
        ("biweekly", "50.00", "1300.00"),
        ("annually", "120.00", "120.00"),
        ("daily", "2.00", "730.00"),
        ("biannually", "200.00", "400.00"),
    ]
    for interval, amount, expected_annual in intervals:
        charge = MoneyValue(amount=amount, currency="USD", kind=MoneyKind.RECURRING, interval=interval)
        cost, assumptions = calculate_annualized_cost(charge)
        assert cost is not None
        assert cost.amount == expected_annual
        assert cost.currency == "USD"


def test_annualized_cost_rejects_non_recurring_and_invalid():
    # One-time payment
    one_time = MoneyValue(amount="49.99", currency="USD", kind=MoneyKind.ONE_TIME, interval="monthly")
    assert calculate_annualized_cost(one_time) == (None, None)

    # Missing interval
    no_interval = MoneyValue(amount="49.99", currency="USD", kind=MoneyKind.RECURRING, interval=None)
    assert calculate_annualized_cost(no_interval) == (None, None)

    # Unknown interval
    unknown_int = MoneyValue(amount="49.99", currency="USD", kind=MoneyKind.RECURRING, interval="hourly")
    assert calculate_annualized_cost(unknown_int) == (None, None)

    # Zero or negative amount
    zero_amt = MoneyValue(amount="0.00", currency="USD", kind=MoneyKind.RECURRING, interval="monthly")
    assert calculate_annualized_cost(zero_amt) == (None, None)


# ---------------------------------------------------------------------------
# 2. Plan Timeline Tests
# ---------------------------------------------------------------------------

def test_build_plan_timeline_trial_with_renewal():
    plan = PlanSummary(
        plan_name="Pro",
        amount_due_now=MoneyValue(amount="0", currency="USD", kind=MoneyKind.TRIAL),
        future_charge=MoneyValue(amount="29.99", currency="USD", kind=MoneyKind.RECURRING, interval="monthly"),
        billing_interval="monthly",
        trial_duration="14 days",
        cancellation_terms="Cancel 24 hours prior",
        is_ambiguous=False,
        evidence_text="Pro: 14 days free, then $29.99/mo. Cancel 24 hours prior.",
    )
    timeline = build_plan_timeline(plan, plan.evidence_text)
    assert timeline is not None
    assert len(timeline.events) == 4
    # Event 1: Trial Start
    assert timeline.events[0].title == "Pro Trial Begins"
    assert timeline.events[0].value_type == TimelineValueType.OBSERVED
    # Event 2: Cancellation deadline
    assert timeline.events[1].title == "Cancellation Deadline"
    assert timeline.events[1].is_critical_action is True
    # Event 3: First recurring charge
    assert timeline.events[2].title == "First Recurring Charge"
    assert timeline.events[2].amount.amount == "29.99"
    # Event 4: 12-Month Projection
    assert timeline.events[3].title == "Annualized Recurring Commitment"
    assert timeline.events[3].value_type == TimelineValueType.CALCULATED
    assert timeline.annualized_cost.amount == "359.88"


def test_build_plan_timeline_trial_without_renewal():
    plan = PlanSummary(
        plan_name="Starter",
        amount_due_now=MoneyValue(amount="0", currency="USD", kind=MoneyKind.TRIAL),
        future_charge=None,
        billing_interval=None,
        trial_duration="7 days",
        cancellation_terms=None,
        is_ambiguous=False,
        evidence_text="Starter: 7 days free trial.",
    )
    timeline = build_plan_timeline(plan, plan.evidence_text)
    assert timeline is not None
    assert len(timeline.events) == 2
    assert timeline.events[1].title == "Renewal Charge Amount (Undisclosed)"
    assert timeline.events[1].value_type == TimelineValueType.UNRESOLVED
    assert timeline.events[1].is_critical_action is True
    assert timeline.annualized_cost is None


# ---------------------------------------------------------------------------
# 3. Primary Financial Timeline Logic Tests
# ---------------------------------------------------------------------------

def test_build_financial_timeline_multi_plan():
    det = run_deterministic_analysis(
        page_title="Multi-Tier Pricing",
        page_url="https://example.com/pricing",
        page_text="Basic plan is $10/mo. Premium plan is $30/mo.",
    )
    commitment_map = CommitmentMap(
        amount_due_now=None,
        future_charge=None,
        billing_interval=None,
        trial_duration=None,
        future_charge_trigger=None,
        cancellation_terms=None,
        unknowns=[],
    )
    price_integrity = PriceIntegrity(observations=[], reason=PriceIntegrityReason.UNCLEAR)
    timeline = build_financial_timeline(det, commitment_map, price_integrity, "Basic plan is $10/mo. Premium plan is $30/mo.")

    assert len(timeline.events) == 0
    assert "Multiple pricing plans detected" in timeline.note


def test_build_financial_timeline_conflicts():
    text = "Plan costs $29.99/month. Same plan costs $49.99/month."
    det = run_deterministic_analysis(
        page_title="Conflicting Pricing",
        page_url="https://example.com/item",
        page_text=text,
    )
    assert len(det.conflicts_detected) > 0
    commitment_map = CommitmentMap(unknowns=det.unknowns)
    price_integrity = PriceIntegrity(observations=[], reason=PriceIntegrityReason.UNCLEAR)
    timeline = build_financial_timeline(det, commitment_map, price_integrity, text)

    assert len(timeline.events) == 1
    assert timeline.events[0].title == "Conflicting Price Terms"
    assert timeline.events[0].value_type == TimelineValueType.UNRESOLVED
    assert timeline.events[0].is_critical_action is True
    assert "conflicting pricing terms" in timeline.note.lower()


# ---------------------------------------------------------------------------
# 4. End-to-End Fixture Timeline Integration Tests
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    return TestClient(app)


def test_fixture_1_subscription_trial_timeline(client):
    html_content = (FIXTURES_DIR / "1_subscription_trial.html").read_text(encoding="utf-8")
    page_text = _extract_text_from_html(html_content)
    resp = client.post("/api/v1/analyze", json={
        "page_title": "StreamCloud Pro - Free Trial",
        "page_url": "https://example.com/trial",
        "page_text": page_text,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "timeline" in data
    tl = data["timeline"]
    assert tl is not None
    assert len(tl["events"]) >= 4

    # Milestone 1: Start of trial
    assert tl["events"][0]["title"] == "Free Trial Begins"
    assert tl["events"][0]["amount"]["amount"] == "0"
    assert tl["events"][0]["value_type"] == "observed"

    # Milestone 2: Cancellation deadline
    cancel_event = next(e for e in tl["events"] if "Cancellation" in e["title"])
    assert cancel_event["is_critical_action"] is True

    # Milestone 3: First recurring charge
    charge_event = next(e for e in tl["events"] if e["title"] == "First Recurring Charge")
    assert charge_event["amount"]["amount"] == "29.00"
    assert charge_event["amount"]["currency"] == "USD"

    # Milestone 4: Annualized projection
    assert tl["annualized_cost"] is not None
    assert tl["annualized_cost"]["amount"] == "348.00"
    assert "12 × USD 29.00" in tl["annualized_cost_assumptions"]


def test_fixture_2_transparent_checkout_timeline(client):
    html_content = (FIXTURES_DIR / "2_transparent_checkout.html").read_text(encoding="utf-8")
    page_text = _extract_text_from_html(html_content)
    resp = client.post("/api/v1/analyze", json={
        "page_title": "Apex Gear Supply - Checkout",
        "page_url": "https://example.com/checkout",
        "page_text": page_text,
    })
    assert resp.status_code == 200
    data = resp.json()
    tl = data["timeline"]
    assert tl is not None
    assert len(tl["events"]) == 2
    assert tl["events"][0]["title"] == "One-Time Payment Due Now"
    assert tl["events"][0]["amount"]["amount"] == "73.00"
    assert tl["events"][1]["title"] == "No Recurring Charges"
    assert tl["annualized_cost"] is None
    assert "one-time transaction" in tl["note"].lower()


def test_fixture_3_unexplained_checkout_timeline(client):
    html_content = (FIXTURES_DIR / "3_unexplained_fee_checkout.html").read_text(encoding="utf-8")
    page_text = _extract_text_from_html(html_content)
    resp = client.post("/api/v1/analyze", json={
        "page_title": "QuickTicket Express - Order Review",
        "page_url": "https://example.com/order",
        "page_text": page_text,
    })
    assert resp.status_code == 200
    data = resp.json()
    tl = data["timeline"]
    assert tl is not None
    assert tl["events"][0]["amount"]["amount"] == "65.00"
    assert tl["annualized_cost"] is None


def test_fixture_4_multi_plan_pricing_timeline(client):
    html_content = (FIXTURES_DIR / "4_multi_plan_pricing.html").read_text(encoding="utf-8")
    page_text = _extract_text_from_html(html_content)
    resp = client.post("/api/v1/analyze", json={
        "page_title": "TaskFlow Workspace - Plans & Pricing",
        "page_url": "https://example.com/pricing",
        "page_text": page_text,
    })
    assert resp.status_code == 200
    data = resp.json()
    # Top level has multi-plan note
    assert "Multiple pricing plans detected" in data["timeline"]["note"]
    assert data["timeline"]["events"] == []

    # Individual tiers have tier-specific timelines
    assert len(data["plans"]) == 3
    for plan in data["plans"]:
        assert "timeline" in plan
        assert plan["timeline"] is not None
        if plan["plan_name"] == "Starter":
            # Starter is $15/mo -> annualized $180.00
            assert plan["timeline"]["annualized_cost"]["amount"] == "180.00"
        elif plan["plan_name"] == "Professional":
            # Professional is $35/mo with 7-day trial -> annualized $420.00
            assert plan["timeline"]["annualized_cost"]["amount"] == "420.00"
        elif plan["plan_name"] == "Enterprise":
            # Enterprise is $75/mo -> annualized $900.00
            assert plan["timeline"]["annualized_cost"]["amount"] == "900.00"
