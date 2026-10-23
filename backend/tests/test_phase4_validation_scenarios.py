"""Phase 4: Real-World Validation Scenarios A-I."""

import json
import pytest
from fastapi.testclient import TestClient

from app.analyzer import analyze_page_content
from app.config import Settings
from app.extraction import run_deterministic_analysis, validate_verbatim_evidence
from app.main import app
from app.schemas import (
    AnalyzeRequest,
    AnalyzeStatus,
    FindingCategory,
    FindingSeverity,
    MoneyKind,
    PriceIntegrityReason,
)

default_settings = Settings(environment="test", llm_api_key=None)
client = TestClient(app)


# ---------------------------------------------------------------------------
# Scenario A: Free trial with renewal charge and cancellation deadline
# ---------------------------------------------------------------------------
def test_scenario_a_free_trial_with_cancellation_deadline():
    page_text = (
        "Start your free 7-day trial. Then Rs.999 per month automatically. "
        "Cancel at least 24 hours before renewal."
    )
    req = AnalyzeRequest(
        page_title="StreamPro Signup",
        page_url="https://streampro.example/signup",
        page_text=page_text,
    )
    res = analyze_page_content(req, default_settings)

    assert res.status in (AnalyzeStatus.OK, AnalyzeStatus.PARTIAL)
    assert res.commitment_map.trial_duration == "7 days"
    assert res.commitment_map.future_charge is not None
    assert res.commitment_map.future_charge.amount == "999"
    assert res.commitment_map.future_charge.currency == "INR"
    assert res.commitment_map.future_charge.interval == "monthly"

    # "free" must NOT be detected as a standalone plan tier
    plan_names_lower = [p.plan_name.lower() for p in res.plans]
    assert "free" not in plan_names_lower, (
        f"free should not be a tier header; got plans: {[p.plan_name for p in res.plans]}"
    )

    # Summary must use grammatically correct interval
    assert "per month" in res.summary, f"Expected per month in summary: {res.summary!r}"
    assert "per monthly" not in res.summary

    # FREE_TRIAL_CONVERSION finding with verbatim evidence
    trial_findings = [f for f in res.findings if f.category == FindingCategory.FREE_TRIAL_CONVERSION]
    assert trial_findings, "Expected a FREE_TRIAL_CONVERSION finding"
    for f in trial_findings:
        assert validate_verbatim_evidence(f.evidence_text, page_text), (
            f"Evidence not verbatim: {f.evidence_text!r}"
        )

    # Cancellation deadline detected via extract_cancellation_terms
    from app.extraction import extract_cancellation_terms
    cancel = extract_cancellation_terms(page_text)
    assert cancel is not None, "Expected cancellation terms to be extracted"
    assert cancel.deadline is not None, "Expected a deadline within cancellation terms"
    assert "24" in cancel.deadline


# ---------------------------------------------------------------------------
# Scenario B: Transparent checkout - no unexplained discrepancy
# ---------------------------------------------------------------------------
def test_scenario_b_transparent_checkout_no_discrepancy():
    page_text = (
        "Cart Summary\n"
        "Subtotal: $50.00\n"
        "Shipping: $5.00\n"
        "Estimated Tax: $4.00\n"
        "Order Total: $59.00\n"
    )
    req = AnalyzeRequest(
        page_title="Transparent Checkout",
        page_url="https://store.example/checkout",
        page_text=page_text,
    )
    res = analyze_page_content(req, default_settings)

    assert res.price_integrity is not None
    assert res.price_integrity.unexplained_difference is None, (
        f"Unexpected discrepancy: {res.price_integrity.unexplained_difference}"
    )
    assert res.price_integrity.reason == PriceIntegrityReason.DISCLOSED_TAX_OR_SHIPPING

    additional_fee_findings = [f for f in res.findings if f.category == FindingCategory.ADDITIONAL_FEE]
    assert not additional_fee_findings, f"False-positive ADDITIONAL_FEE: {additional_fee_findings}"

    assert res.price_integrity.difference is not None
    assert res.price_integrity.difference.amount == "9.00"


# ---------------------------------------------------------------------------
# Scenario C: Unexplained checkout discrepancy
# ---------------------------------------------------------------------------
def test_scenario_c_unexplained_checkout_discrepancy():
    page_text = (
        "Cart Summary\n"
        "Subtotal: $50.00\n"
        "Shipping: $5.00\n"
        "Estimated Tax: $4.00\n"
        "Order Total: $65.00\n"
    )
    req = AnalyzeRequest(
        page_title="Discrepant Checkout",
        page_url="https://store.example/checkout",
        page_text=page_text,
    )
    res = analyze_page_content(req, default_settings)

    assert res.price_integrity is not None
    assert res.price_integrity.reason == PriceIntegrityReason.UNCLEAR

    assert res.price_integrity.difference is not None
    assert res.price_integrity.difference.amount == "15.00", (
        f"difference should be 15.00 (total - subtotal), got {res.price_integrity.difference.amount}"
    )

    assert res.price_integrity.unexplained_difference is not None
    assert res.price_integrity.unexplained_difference.amount == "6.00", (
        f"unexplained should be 6.00, got {res.price_integrity.unexplained_difference.amount}"
    )

    unexplained_findings = [
        f for f in res.findings if f.id == "finding-unexplained-checkout-difference"
    ]
    assert unexplained_findings, "Expected finding-unexplained-checkout-difference"
    uf = unexplained_findings[0]
    assert uf.severity == FindingSeverity.HIGH
    assert validate_verbatim_evidence(uf.evidence_text, page_text)
    assert "exceeds base price plus disclosed adjustments" in uf.explanation


# ---------------------------------------------------------------------------
# Scenario D: Two distinct fees with same amount - both retained
# ---------------------------------------------------------------------------
def test_scenario_d_distinct_fees_same_amount_both_retained():
    page_text = (
        "Order Summary\n"
        "Subtotal: $50.00\n"
        "Shipping: $5.00\n"
        "Service Fee: $5.00\n"
        "Order Total: $60.00\n"
    )
    req = AnalyzeRequest(
        page_title="Two Same-Amount Fees",
        page_url="https://store.example/order",
        page_text=page_text,
    )
    res = analyze_page_content(req, default_settings)

    assert res.price_integrity is not None
    fee_names = [f.name.lower() for f in res.price_integrity.explicit_fees]
    assert "shipping" in fee_names, f"Shipping missing: {fee_names}"
    assert "service fee" in fee_names, f"Service Fee missing: {fee_names}"
    assert len(res.price_integrity.explicit_fees) == 2, (
        f"Expected 2 fees, got {len(res.price_integrity.explicit_fees)}: {fee_names}"
    )
    assert res.price_integrity.unexplained_difference is None
    assert res.price_integrity.reason == PriceIntegrityReason.DISCLOSED_TAX_OR_SHIPPING


# ---------------------------------------------------------------------------
# Scenario E: Multiple pricing plans - no implicit selection
# ---------------------------------------------------------------------------
def test_scenario_e_multiple_plans_no_implicit_selection():
    page_text = (
        "Basic: Rs.499/month\n"
        "Pro: Rs.999/month, with a 7-day free trial\n"
        "Premium: Rs.1,499/month\n"
    )
    req = AnalyzeRequest(
        page_title="Pricing Plans",
        page_url="https://saas.example/pricing",
        page_text=page_text,
    )
    res = analyze_page_content(req, default_settings)

    assert len(res.plans) == 3, f"Expected 3 plans, got {len(res.plans)}: {[p.plan_name for p in res.plans]}"

    plan_map = {p.plan_name.lower(): p for p in res.plans}
    assert "basic" in plan_map
    assert "pro" in plan_map
    assert "premium" in plan_map

    assert res.commitment_map.amount_due_now is None, (
        f"amount_due_now should be None; got {res.commitment_map.amount_due_now}"
    )
    assert res.commitment_map.future_charge is None, (
        f"future_charge should be None; got {res.commitment_map.future_charge}"
    )
    assert res.commitment_map.trial_duration is None, (
        f"trial_duration should be None at top level; got {res.commitment_map.trial_duration}"
    )

    assert "3 pricing plans" in res.summary


# ---------------------------------------------------------------------------
# Scenario F: Fixed discount - correct calculation, no double-counting
# ---------------------------------------------------------------------------
def test_scenario_f_fixed_discount_reconciles():
    page_text = (
        "Cart Summary\n"
        "Subtotal: $50.00\n"
        "Discount: -$10.00\n"
        "Shipping: $5.00\n"
        "Order Total: $45.00\n"
    )
    req = AnalyzeRequest(
        page_title="Discounted Cart",
        page_url="https://store.example/cart",
        page_text=page_text,
    )
    res = analyze_page_content(req, default_settings)

    assert res.price_integrity is not None
    assert res.price_integrity.unexplained_difference is None, (
        f"False positive discrepancy: {res.price_integrity.unexplained_difference}; "
        f"fees: {[(f.name, f.amount.amount) for f in res.price_integrity.explicit_fees]}"
    )
    assert res.price_integrity.reason in (
        PriceIntegrityReason.DISCLOSED_TAX_OR_SHIPPING,
        PriceIntegrityReason.KNOWN,
    )

    fee_names = [f.name.lower() for f in res.price_integrity.explicit_fees]
    assert "discount" in fee_names, f"Discount missing from fees: {fee_names}"
    discount_fee = next(f for f in res.price_integrity.explicit_fees if "discount" in f.name.lower())
    assert discount_fee.amount.amount.startswith("-"), (
        f"Discount amount should be negative, got {discount_fee.amount.amount!r}"
    )

    additional_fee_findings = [f for f in res.findings if f.category == FindingCategory.ADDITIONAL_FEE]
    assert not additional_fee_findings, f"False-positive ADDITIONAL_FEE: {additional_fee_findings}"


# ---------------------------------------------------------------------------
# Scenario G: Currency mismatch - must not perform invalid arithmetic
# ---------------------------------------------------------------------------
def test_scenario_g_currency_mismatch_not_comparable():
    page_text = (
        "Subtotal: $50.00\n"
        "Handling Fee: EUR 5.00\n"
        "Total: $55.00\n"
    )
    req = AnalyzeRequest(
        page_title="Cross-Currency Checkout",
        page_url="https://border.example/checkout",
        page_text=page_text,
    )
    res = analyze_page_content(req, default_settings)

    assert res.price_integrity is not None
    assert res.price_integrity.reason == PriceIntegrityReason.NOT_COMPARABLE, (
        f"Expected NOT_COMPARABLE for currency mismatch, got {res.price_integrity.reason}"
    )
    assert res.price_integrity.difference is None
    assert res.price_integrity.unexplained_difference is None


# ---------------------------------------------------------------------------
# Scenario H: Incomplete evidence - no base subtotal
# ---------------------------------------------------------------------------
def test_scenario_h_incomplete_evidence_no_subtotal():
    page_text = (
        "Shipping: $5.00\n"
        "Estimated Tax: $4.00\n"
        "Order Total: $59.00\n"
    )
    req = AnalyzeRequest(
        page_title="Partial Checkout",
        page_url="https://store.example/partial",
        page_text=page_text,
    )
    res = analyze_page_content(req, default_settings)

    assert res.price_integrity is not None, (
        "price_integrity should not be None when fees + total are present"
    )
    assert res.price_integrity.reason == PriceIntegrityReason.NOT_COMPARABLE, (
        f"Expected NOT_COMPARABLE for incomplete evidence, got {res.price_integrity.reason}"
    )
    assert res.price_integrity.unexplained_difference is None
    assert res.price_integrity.note is not None, "A note should explain why comparison is not possible"
    assert "subtotal" in res.price_integrity.note.lower() or "base" in res.price_integrity.note.lower()


# ---------------------------------------------------------------------------
# Scenario I: Dynamic pricing - only captured state analyzed
# ---------------------------------------------------------------------------
def test_scenario_i_monthly_captured_no_annual_fabrication():
    page_text = "Monthly Plan: $12.99/month\nStart your subscription today.\n"
    req = AnalyzeRequest(
        page_title="Pricing Page",
        page_url="https://sub.example/pricing",
        page_text=page_text,
    )
    res = analyze_page_content(req, default_settings)

    assert res.commitment_map.future_charge is not None
    assert res.commitment_map.future_charge.interval == "monthly"
    assert res.commitment_map.future_charge.amount == "12.99"

    summary_lower = res.summary.lower()
    assert "annual" not in summary_lower, (
        f"annual should not appear when only monthly was captured: {res.summary!r}"
    )
    for finding in res.findings:
        assert "annual" not in finding.explanation.lower()


def test_scenario_i_annual_captured_no_monthly_fabrication():
    page_text = "Annual Plan: $99.99/year\nSave 33 percent with annual billing.\n"
    req = AnalyzeRequest(
        page_title="Pricing Page Annual",
        page_url="https://sub.example/pricing",
        page_text=page_text,
    )
    res = analyze_page_content(req, default_settings)

    assert res.commitment_map.future_charge is not None
    assert res.commitment_map.future_charge.interval in ("annually", "yearly")
    assert res.commitment_map.future_charge.amount == "99.99"

    assert "per annually" not in res.summary
    assert "per year" in res.summary or "annually" in res.summary.lower()


# ---------------------------------------------------------------------------
# Live API response capture: Scenario B and C
# ---------------------------------------------------------------------------
def test_api_response_scenario_b_transparent(capsys):
    payload = {
        "page_title": "Transparent Checkout",
        "page_url": "https://store.example/checkout",
        "page_text": "Cart Summary\nSubtotal: $50.00\nShipping: $5.00\nEstimated Tax: $4.00\nOrder Total: $59.00\n",
    }
    resp = client.post("/api/v1/analyze", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    pi = data["price_integrity"]
    assert pi["reason"] == "disclosed_tax_or_shipping"
    assert pi["unexplained_difference"] is None
    with capsys.disabled():
        print("\n=== Scenario B API Response ===")
        print(json.dumps(data, indent=2, ensure_ascii=False))


def test_api_response_scenario_c_discrepant(capsys):
    payload = {
        "page_title": "Discrepant Checkout",
        "page_url": "https://store.example/checkout",
        "page_text": "Cart Summary\nSubtotal: $50.00\nShipping: $5.00\nEstimated Tax: $4.00\nOrder Total: $65.00\n",
    }
    resp = client.post("/api/v1/analyze", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    pi = data["price_integrity"]
    assert pi["reason"] == "unclear"
    assert pi["unexplained_difference"]["amount"] == "6.00"
    assert pi["difference"]["amount"] == "15.00"
    with capsys.disabled():
        print("\n=== Scenario C API Response ===")
        print(json.dumps(data, indent=2, ensure_ascii=False))
