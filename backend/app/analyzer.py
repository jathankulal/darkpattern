"""Core financial commitment analyzer for Dark Pattern Guardian.

Combines deterministic extraction baseline with optional AI interpretation layer.
"""

from decimal import Decimal
from typing import List, Optional

from app.ai.base import AIInterpreter, NullAIInterpreter
from app.config import Settings
from app.extraction import run_deterministic_analysis
from app.schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    AnalyzeStatus,
    CommitmentMap,
    MoneyKind,
    MoneyValue,
    PriceIntegrity,
    PriceIntegrityReason,
    PriceObservation,
)

# Mapping from billing interval adjective (stored in MoneyValue.interval) to a noun
# that reads naturally after "per" (e.g. "per month", "per year").
_INTERVAL_NOUN: dict[str, str] = {
    "monthly": "month",
    "annually": "year",
    "yearly": "year",
    "quarterly": "quarter",
    "weekly": "week",
    "daily": "day",
    "biannually": "6 months",
    "biweekly": "2 weeks",
}


def _interval_label(interval: Optional[str]) -> str:
    """Convert a billing interval adjective to a readable 'per <noun>' string."""
    if not interval:
        return ""
    noun = _INTERVAL_NOUN.get(interval.lower(), interval)
    return f" per {noun}"



def generate_checklist(unknowns: List[str], has_recurring: bool, has_trial: bool) -> List[str]:
    """Generate dynamic, contextual checklist items based on missing or explicit terms."""
    checklist: List[str] = []

    if has_trial:
        checklist.append("Set a calendar reminder before the free trial period ends")
    if has_recurring:
        checklist.append("Check where and how cancellation can be performed in account settings")

    for u in unknowns:
        u_lower = u.lower()
        if "renewal" in u_lower or "future" in u_lower:
            checklist.append("Confirm the regular renewal price on the payment page before confirming")
        elif "cancellation" in u_lower:
            checklist.append("Review merchant refund and cancellation policies before purchase")
        elif "interval" in u_lower:
            checklist.append("Verify the recurring billing frequency (monthly, annually, etc.)")
        elif "conflicting" in u_lower:
            checklist.append("Clarify conflicting price mentions with the merchant before paying")

    if not checklist:
        checklist.append("Review order summary and total price before final payment")

    # Limit to max 10 checklist items
    return checklist[:10]


def build_price_integrity(
    amount_due_now: Optional[MoneyValue],
    future_charge: Optional[MoneyValue],
    introductory_price: Optional[MoneyValue],
    renewal_price: Optional[MoneyValue],
) -> PriceIntegrity:
    """Build the Price Integrity Trail based only on verifiable comparable observations."""
    observations: List[PriceObservation] = []
    difference: Optional[MoneyValue] = None
    reason = PriceIntegrityReason.UNCLEAR

    if introductory_price and renewal_price:
        observations.append(
            PriceObservation(
                stage="introductory",
                amount=introductory_price,
                context="Introductory or initial rate stated on page",
            )
        )
        observations.append(
            PriceObservation(
                stage="renewal",
                amount=renewal_price,
                context="Subsequent recurring charge stated on page",
            )
        )

        # Compute price difference if currencies match
        if introductory_price.currency == renewal_price.currency:
            try:
                intro_dec = Decimal(introductory_price.amount)
                renew_dec = Decimal(renewal_price.amount)
                diff_dec = renew_dec - intro_dec
                difference = MoneyValue(
                    amount=str(diff_dec),
                    currency=introductory_price.currency,
                    kind=MoneyKind.FEE if diff_dec > 0 else MoneyKind.ONE_TIME,
                )
                reason = PriceIntegrityReason.KNOWN
            except Exception:
                reason = PriceIntegrityReason.UNCLEAR

    elif amount_due_now and future_charge and amount_due_now.kind == MoneyKind.TRIAL and future_charge:
        observations.append(
            PriceObservation(
                stage="trial",
                amount=amount_due_now,
                context="Free trial period",
            )
        )
        observations.append(
            PriceObservation(
                stage="renewal",
                amount=future_charge,
                context="Subsequent recurring charge after trial",
            )
        )
        if amount_due_now.currency == future_charge.currency:
            difference = future_charge
            reason = PriceIntegrityReason.KNOWN

    elif amount_due_now:
        observations.append(
            PriceObservation(
                stage="initial",
                amount=amount_due_now,
                context="Stated purchase price",
            )
        )
        reason = PriceIntegrityReason.KNOWN

    return PriceIntegrity(
        observations=observations,
        difference=difference,
        reason=reason,
    )


def build_summary(
    commitment_map: CommitmentMap,
    findings_count: int,
    conflicts_detected: List[str],
    plans_count: int = 0,
    plan_names: Optional[List[str]] = None,
    unexplained_difference: Optional[MoneyValue] = None,
) -> str:
    """Produce an objective, calm, plain-language summary of the financial terms."""
    if unexplained_difference:
        return f"Warning: Unexplained checkout price difference of {unexplained_difference.currency} {unexplained_difference.amount} detected."

    if conflicts_detected:
        return f"Warning: Conflicting pricing terms detected ({', '.join(conflicts_detected)}). Verify the final order amount carefully."

    if plans_count > 1 and plan_names:
        return f"{plans_count} pricing plans detected ({', '.join(plan_names)}). Review individual plan terms below."

    due = commitment_map.amount_due_now
    future = commitment_map.future_charge
    trial = commitment_map.trial_duration

    if trial and future:
        interval_str = _interval_label(future.interval)
        return (
            f"Free trial lasting {trial} converting to a recurring charge of "
            f"{future.currency} {future.amount}{interval_str}."
        )

    if trial and not future:
        return (
            f"A free trial of {trial} was identified, but the renewal charge upon "
            "trial expiration is not disclosed on this page."
        )

    if future and due and due.amount != future.amount:
        return (
            f"Initial charge of {due.currency} {due.amount} followed by subsequent "
            f"recurring charge of {future.currency} {future.amount}."
        )

    if future:
        interval_str = _interval_label(future.interval)
        return f"Recurring subscription of {future.currency} {future.amount}{interval_str}."

    if due:
        return f"One-time purchase of {due.currency} {due.amount} with no recurring charges detected."

    if findings_count > 0:
        return "Financial terms or conditions detected with potential areas of uncertainty. Review the findings below."

    return "No recurring commitments or pricing terms detected in the analyzed visible text."


def analyze_page_content(
    request: AnalyzeRequest,
    settings: Settings,
    ai_interpreter: Optional[AIInterpreter] = None,
) -> AnalyzeResponse:
    """Analyze page text and metadata, returning a complete AnalyzeResponse."""
    # 1. Run deterministic baseline extraction
    det_result = run_deterministic_analysis(
        page_title=request.page_title,
        page_url=request.page_url,
        page_text=request.page_text,
    )

    # 2. Run optional AI interpretation layer if configured
    interpreter = ai_interpreter or NullAIInterpreter()
    ai_result = interpreter.interpret(
        page_title=request.page_title,
        page_url=request.page_url,
        page_text=request.page_text,
        deterministic_context={
            "amount_due_now": det_result.amount_due_now.model_dump() if det_result.amount_due_now else None,
            "future_charge": det_result.future_charge.model_dump() if det_result.future_charge else None,
            "trial_duration": det_result.trial_duration,
            "is_recurring": det_result.is_recurring,
        },
    )

    # 3. Combine findings (deterministic takes priority; AI findings appended if grounded)
    findings = list(det_result.findings)
    for ai_f in ai_result.additional_findings:
        # Avoid duplicate findings for same category
        if not any(f.category == ai_f.category for f in findings):
            findings.append(ai_f)

    # 4. Construct CommitmentMap
    commitment_map = CommitmentMap(
        amount_due_now=det_result.amount_due_now,
        future_charge=det_result.future_charge,
        billing_interval=det_result.billing_interval,
        trial_duration=det_result.trial_duration,
        future_charge_trigger=det_result.future_charge_trigger,
        cancellation_terms=det_result.cancellation_terms,
        unknowns=det_result.unknowns,
    )

    # 5. Build Price Integrity Trail (prefer checkout comparison if detected)
    if det_result.checkout_comparison:
        price_integrity = det_result.checkout_comparison
    else:
        price_integrity = build_price_integrity(
            amount_due_now=det_result.amount_due_now,
            future_charge=det_result.future_charge,
            introductory_price=det_result.introductory_price,
            renewal_price=det_result.renewal_price,
        )

    # 6. Generate Checklist ("Ask Before You Pay")
    checklist = generate_checklist(
        unknowns=commitment_map.unknowns,
        has_recurring=det_result.is_recurring or bool(det_result.future_charge),
        has_trial=any(bool(p.trial_duration) for p in det_result.plans) if det_result.plans else bool(det_result.trial_duration),
    )

    # 7. Disclose Boundaries and Limitations
    limitations: List[str] = [
        "Analysis based strictly on bounded visible text submitted by browser extension.",
    ]
    if ai_result.ai_status == "active":
        limitations.append("Contextual AI interpretation layer active.")
    elif ai_result.ai_status == "unconfigured":
        limitations.append("Deterministic extraction applied; AI contextual interpretation not configured.")
    elif ai_result.ai_status == "failed":
        limitations.append("AI interpretation was unavailable; full deterministic results applied.")

    # 8. Formulate Summary
    summary = build_summary(
        commitment_map=commitment_map,
        findings_count=len(findings),
        conflicts_detected=det_result.conflicts_detected,
        plans_count=len(det_result.plans),
        plan_names=[p.plan_name for p in det_result.plans],
        unexplained_difference=price_integrity.unexplained_difference,
    )

    status = AnalyzeStatus.OK
    has_ambiguity = any(p.is_ambiguous for p in det_result.plans)
    has_unexplained = price_integrity.unexplained_difference is not None
    if det_result.conflicts_detected or (det_result.trial_duration and not det_result.future_charge) or has_ambiguity or has_unexplained:
        status = AnalyzeStatus.PARTIAL

    return AnalyzeResponse(
        status=status,
        summary=summary,
        findings=findings,
        commitment_map=commitment_map,
        plans=det_result.plans,
        price_integrity=price_integrity,
        checklist=checklist,
        limitations=limitations,
    )
