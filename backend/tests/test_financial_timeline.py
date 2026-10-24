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
        cancellation_terms="Cancel at least 24 hours before renewal",
        is_ambiguous=False,
        evidence_text="Pro: 14 days free, then $29.99/mo. Cancel at least 24 hours before renewal.",
    )
    timeline = build_plan_timeline(plan, plan.evidence_text)
    assert timeline is not None
    assert len(timeline.events) == 4
    # Event 1: Trial Start
    assert timeline.events[0].title == "Pro Trial Begins"
    assert timeline.events[0].value_type == TimelineValueType.OBSERVED
    # Event 2: Cancellation deadline
    assert timeline.events[1].title == "Cancellation Cutoff Deadline"
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
    assert timeline.events[1].is_critical_action is False
    assert timeline.annualized_cost is None


def test_cancel_anytime_is_not_misrepresented_as_a_required_deadline():
    page_text = "Pro: 7-day free trial, then $29.99/month. Cancel anytime."
    plan = PlanSummary(
        plan_name="Pro",
        future_charge=MoneyValue(
            amount="29.99",
            currency="USD",
            kind=MoneyKind.RECURRING,
            interval="monthly",
        ),
        billing_interval="monthly",
        trial_duration="7 days",
        cancellation_terms="Cancel anytime",
        is_ambiguous=False,
        evidence_text=page_text,
    )

    timeline = build_plan_timeline(plan, page_text)
    cancellation_event = next(
        event for event in timeline.events if "Cancellation" in event.title
    )

    assert cancellation_event.title == "Cancellation Instructions"
    assert cancellation_event.value_type == TimelineValueType.OBSERVED
    assert cancellation_event.evidence_text == "Cancel anytime"
    assert cancellation_event.is_critical_action is False


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

    # A billing-cycle reference does not establish a concrete cutoff.
    cancel_event = next(e for e in tl["events"] if "Cancellation" in e["title"])
    assert cancel_event["title"] == "Cancellation Timing Is Unclear"
    assert cancel_event["value_type"] == TimelineValueType.UNRESOLVED.value
    assert cancel_event["is_critical_action"] is False
    assert cancel_event["evidence_text"] == (
        "Cancel at least 24 hours before your billing cycle"
    )

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


def test_subscription_timeline_uses_price_and_renewal_evidence_separately(client):
    price_evidence = "$19.99 per month"
    renewal_evidence = "renews automatically"
    page_text = (
        "Only 2 minutes left! Subscribe now for $19.99 per month. "
        "Your subscription renews automatically. "
        "You can cancel from account settings."
    )
    response = client.post(
        "/api/v1/analyze",
        json={
            "page_title": "Checkout",
            "page_url": "https://example.test/checkout",
            "page_text": page_text,
        },
    )

    assert response.status_code == 200
    timeline = response.json()["timeline"]
    events = {event["title"]: event for event in timeline["events"]}

    initial = events["Initial Payment Due Now"]
    next_charge = events["Next Recurring Charge"]
    ongoing = events["Ongoing Subscription"]
    annualized = events["Annualized Recurring Commitment"]

    assert initial["evidence_text"] == price_evidence
    assert initial["value_type"] == TimelineValueType.OBSERVED.value
    assert next_charge["evidence_text"] == renewal_evidence
    assert next_charge["value_type"] == TimelineValueType.OBSERVED.value
    assert ongoing["evidence_text"] == renewal_evidence
    assert ongoing["value_type"] == TimelineValueType.OBSERVED.value
    assert annualized["evidence_text"] == price_evidence
    assert annualized["value_type"] == TimelineValueType.CALCULATED.value
    assert "calculated" in annualized["description"].lower()
    assert "not a directly observed charge" in annualized["description"].lower()


def test_trial_timeline_quotes_the_observed_recurring_price(client):
    renewal_evidence = (
        "After the trial, your subscription renews at $29.00 per month "
        "automatically unless cancelled."
    )
    response = client.post(
        "/api/v1/analyze",
        json={
            "page_title": "Subscription Trial",
            "page_url": "https://example.test/trial",
            "page_text": (
                "Start your 14-day free trial for $0.00.\n"
                f"{renewal_evidence}\n"
                "Cancel at least 24 hours before your billing cycle."
            ),
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["commitment_map"]["future_charge"]["amount"] == "29.00"
    assert data["commitment_map"]["future_charge"]["interval"] == "monthly"
    assert data["timeline"]["annualized_cost"]["amount"] == "348.00"
    events = {event["title"]: event for event in data["timeline"]["events"]}
    for title in (
        "First Recurring Charge",
        "Ongoing Subscription",
        "Annualized Recurring Commitment",
    ):
        assert events[title]["evidence_text"] == renewal_evidence
    assert events["First Recurring Charge"]["evidence_text"] != "14-day free trial"


def test_trial_with_cancel_anytime_in_account_settings_has_no_cutoff(client):
    cancellation = "Cancel anytime from your account settings"
    response = client.post(
        "/api/v1/analyze",
        json={
            "page_title": "Subscription Trial",
            "page_url": "https://example.test/trial",
            "page_text": (
                "Enjoy a 14-day free trial.\n"
                "After the trial, your subscription renews at $29.00 per month "
                "automatically unless cancelled.\n"
                f"{cancellation}."
            ),
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["commitment_map"]["cancellation_terms"] == cancellation
    event = next(
        event for event in data["timeline"]["events"]
        if "Cancellation" in event["title"]
    )
    assert event["title"] == "Cancellation Instructions"
    assert event["value_type"] == TimelineValueType.OBSERVED.value
    assert event["evidence_text"] == cancellation
    assert event["is_critical_action"] is False


def test_billing_cycle_cancellation_wording_is_unresolved_not_a_deadline(client):
    cancellation = "Cancel at least 24 hours before your billing cycle"
    response = client.post(
        "/api/v1/analyze",
        json={
            "page_title": "Subscription Trial",
            "page_url": "https://example.test/trial",
            "page_text": (
                "Enjoy a 14-day free trial.\n"
                "After the trial, your subscription renews at $29.00 per month "
                "automatically unless cancelled.\n"
                f"{cancellation}."
            ),
        },
    )

    assert response.status_code == 200
    event = next(
        event for event in response.json()["timeline"]["events"]
        if "Cancellation" in event["title"]
    )
    assert event["title"] == "Cancellation Timing Is Unclear"
    assert event["value_type"] == TimelineValueType.UNRESOLVED.value
    assert event["evidence_text"] == cancellation
    assert event["is_critical_action"] is False


def test_explicit_trial_end_deadline_remains_actionable(client):
    cancellation = "Cancel at least 24 hours before the trial ends"
    response = client.post(
        "/api/v1/analyze",
        json={
            "page_title": "Subscription Trial",
            "page_url": "https://example.test/trial",
            "page_text": (
                "Enjoy a 14-day free trial. "
                "After the trial, your subscription renews at $29.00 per month "
                "automatically unless cancelled. "
                f"{cancellation}."
            ),
        },
    )

    assert response.status_code == 200
    event = next(
        event for event in response.json()["timeline"]["events"]
        if "Cancellation" in event["title"]
    )
    assert event["title"] == "Cancellation Cutoff Deadline"
    assert event["value_type"] == TimelineValueType.OBSERVED.value
    assert event["evidence_text"] == cancellation
    assert event["is_critical_action"] is True
    assert event["timepoint"] == "Before stated renewal cutoff"


def test_checkout_summary_uses_final_total_and_preserves_subtotal_arithmetic(client):
    page_text = (
        "Cart Summary\n"
        "Subtotal: $50.00\n"
        "Processing Fee: $4.00\n"
        "Service Fee: $3.00\n"
        "Order Total: $65.00\n"
        "Non-refundable ticket reservation."
    )
    response = client.post(
        "/api/v1/analyze",
        json={
            "page_title": "QuickTicketExpress Checkout",
            "page_url": "https://tickets.example/checkout",
            "page_text": page_text,
        },
    )

    assert response.status_code == 200
    data = response.json()
    commitment = data["commitment_map"]
    integrity = data["price_integrity"]

    assert commitment["amount_due_now"]["amount"] == "65.00"
    assert integrity["checkout_subtotal"]["amount"] == "50.00"
    assert sum(Decimal(fee["amount"]["amount"]) for fee in integrity["explicit_fees"]) == Decimal("7.00")
    assert integrity["difference"]["amount"] == "15.00"
    assert integrity["unexplained_difference"]["amount"] == "8.00"
    assert commitment["cancellation_terms"] == "Non-refundable ticket reservation."
    assert commitment["future_charge"] is None
    assert commitment["billing_interval"] is None

    payment_event = next(
        event for event in data["timeline"]["events"]
        if event["title"] == "One-Time Payment Due Now"
    )
    assert payment_event["amount"]["amount"] == "65.00"
    assert payment_event["evidence_text"] == "Order Total: $65.00"

    finding = next(
        finding for finding in data["findings"]
        if finding["id"] == "finding-unexplained-checkout-difference"
    )
    assert "USD 8.00" in finding["explanation"]
    assert "itemized charges detected in the scanned text (USD 57.00)" in finding["explanation"]
    assert "not proof of deception" in finding["explanation"].lower()


def test_unresolved_trial_terms_are_not_labeled_action_required(client):
    response = client.post(
        "/api/v1/analyze",
        json={
            "page_title": "Trial",
            "page_url": "https://example.test/trial",
            "page_text": "Start your free 7-day trial. Cancel anytime.",
        },
    )

    assert response.status_code == 200
    events = response.json()["timeline"]["events"]
    cancellation = next(
        event for event in events if event["title"] == "Cancellation Instructions"
    )
    renewal = next(
        event for event in events if event["title"] == "Renewal Charge Amount (Undisclosed)"
    )

    assert cancellation["value_type"] == TimelineValueType.OBSERVED.value
    assert cancellation["evidence_text"] == "Cancel anytime"
    assert cancellation["is_critical_action"] is False
    assert "no cutoff deadline is stated" in cancellation["description"].lower()
    assert "no cutoff deadline is stated" in cancellation["description"].lower()
    assert renewal["value_type"] == TimelineValueType.UNRESOLVED.value
    assert renewal["is_critical_action"] is False


def test_analyze_endpoint_caps_response_plans_without_losing_analysis(client):
    plan_names = [
        "Basic", "Starter", "Standard", "Pro", "Professional",
        "Premium", "Enterprise", "Business", "Personal", "Individual",
        "Team", "Ultimate", "Plus", "Lite", "Family",
    ]
    page_text = "Hurry! Sale ends in 15 minutes.\n" + "\n".join(
        f"{name} Plan: ${index + 9}.99 per month."
        for index, name in enumerate(plan_names)
    )

    response = client.post(
        "/api/v1/analyze",
        json={
            "page_title": "Plans",
            "page_url": "https://example.test/plans",
            "page_text": page_text,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["plans"]) == 10
    assert [plan["plan_name"] for plan in data["plans"]] == [
        f"{name} Plan" for name in plan_names[:10]
    ]
    assert all(plan["future_charge"] is not None for plan in data["plans"])
    assert all(plan["timeline"] is not None for plan in data["plans"])
    assert data["plans"][0]["future_charge"]["amount"] == "9.99"
    assert data["plans"][0]["future_charge"]["currency"] == "USD"
    assert data["plans"][0]["timeline"]["annualized_cost"]["amount"] == "119.88"
    assert data["plans"][-1]["future_charge"]["amount"] == "18.99"
    assert "Multiple pricing plans detected (15 tiers)" in data["timeline"]["note"]
    assert any(finding["category"] == "urgency_pressure" for finding in data["findings"])
