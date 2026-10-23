"""Core financial commitment analyzer for Dark Pattern Guardian.

Combines deterministic extraction baseline with optional AI interpretation layer.
"""

from decimal import Decimal
from typing import List, Optional

from app.ai.base import AIInterpreter, NullAIInterpreter
from app.config import Settings
from app.extraction import extract_cancellation_terms, run_deterministic_analysis
from app.schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    AnalyzeStatus,
    CommitmentMap,
    EvidenceLevel,
    FinancialTimeline,
    Finding,
    FindingCategory,
    MoneyKind,
    MoneyValue,
    PlanSummary,
    PriceIntegrity,
    PriceIntegrityReason,
    PriceObservation,
    TimelineEvent,
    TimelineValueType,
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

INTERVAL_ANNUAL_MULTIPLIERS: dict[str, int] = {
    "monthly": 12,
    "month": 12,
    "annually": 1,
    "yearly": 1,
    "year": 1,
    "quarterly": 4,
    "quarter": 4,
    "biannually": 2,
    "semi-annually": 2,
    "bi-annually": 2,
    "weekly": 52,
    "week": 52,
    "biweekly": 26,
    "bi-weekly": 26,
    "daily": 365,
    "day": 365,
}


def calculate_annualized_cost(
    charge: Optional[MoneyValue],
    introductory: Optional[MoneyValue] = None,
) -> tuple[Optional[MoneyValue], Optional[str]]:
    """Deterministically calculate annualized recurring cost using Python Decimal.

    Returns (annualized_money_value, assumptions_string).
    Never calculates for one-time payments or missing/unsupported intervals.
    """
    if not charge or not charge.amount or not charge.interval:
        return None, None
    if charge.kind not in (MoneyKind.RECURRING, MoneyKind.FEE):
        return None, None

    raw_int = charge.interval.lower().replace("per ", "").replace("/", "").strip()
    multiplier = INTERVAL_ANNUAL_MULTIPLIERS.get(raw_int)
    if not multiplier:
        return None, None

    try:
        charge_dec = Decimal(charge.amount)
        if charge_dec <= 0:
            return None, None

        if introductory and introductory.amount and introductory.currency == charge.currency:
            intro_dec = Decimal(introductory.amount)
            if multiplier > 1:
                annual_dec = intro_dec + (charge_dec * Decimal(multiplier - 1))
                assumptions = (
                    f"Calculated as 1 initial charge of {introductory.currency} {introductory.amount} "
                    f"plus {multiplier - 1} regular recurring charges of {charge.currency} {charge.amount} over 12 months."
                )
            else:
                annual_dec = intro_dec
                assumptions = f"Calculated as initial charge of {introductory.currency} {introductory.amount} for the first year."
        else:
            annual_dec = charge_dec * Decimal(multiplier)
            assumptions = (
                f"Calculated deterministically as {multiplier} × {charge.currency} {charge.amount} "
                f"({raw_int} charges) over a 12-month period."
            )

        formatted_amount = f"{annual_dec:.2f}" if "." in charge.amount else str(annual_dec)
        cost = MoneyValue(
            amount=formatted_amount,
            currency=charge.currency,
            kind=MoneyKind.RECURRING,
            interval="annually",
        )
        return cost, assumptions
    except Exception:
        return None, None


def _find_matching_evidence(candidates: List[Optional[str]], page_text: str) -> str:
    """Find the first non-empty candidate string present verbatim in page_text."""
    for c in candidates:
        if c and c in page_text:
            return c
    return ""


def build_plan_timeline(plan: PlanSummary, page_text: str) -> FinancialTimeline:
    """Construct a plan-specific financial commitment timeline."""
    events: List[TimelineEvent] = []

    if plan.trial_duration:
        due_now = plan.amount_due_now or MoneyValue(
            amount="0",
            currency=plan.future_charge.currency if plan.future_charge else "USD",
            kind=MoneyKind.TRIAL,
        )
        events.append(
            TimelineEvent(
                timepoint="Today",
                title=f"{plan.plan_name} Trial Begins",
                amount=due_now,
                value_type=TimelineValueType.OBSERVED,
                description=f"Start of {plan.trial_duration} trial period for {plan.plan_name}.",
                evidence_text=plan.evidence_text,
                is_critical_action=False,
            )
        )
        if plan.cancellation_terms:
            events.append(
                TimelineEvent(
                    timepoint="Before Trial Ends",
                    title="Cancellation Deadline",
                    amount=None,
                    value_type=TimelineValueType.OBSERVED,
                    description=f"Cancellation notice terms: {plan.cancellation_terms}.",
                    evidence_text=plan.cancellation_terms if plan.cancellation_terms in page_text else plan.evidence_text,
                    is_critical_action=True,
                )
            )
        if plan.future_charge:
            events.append(
                TimelineEvent(
                    timepoint=f"After {plan.trial_duration}",
                    title="First Recurring Charge",
                    amount=plan.future_charge,
                    value_type=TimelineValueType.OBSERVED,
                    description=f"{plan.plan_name} renews at {plan.future_charge.currency} {plan.future_charge.amount}{_interval_label(plan.future_charge.interval)}.",
                    evidence_text=plan.evidence_text,
                    is_critical_action=False,
                )
            )
            annual_cost, assumptions = calculate_annualized_cost(plan.future_charge)
            if annual_cost:
                events.append(
                    TimelineEvent(
                        timepoint="12-Month Projection",
                        title="Annualized Recurring Commitment",
                        amount=annual_cost,
                        value_type=TimelineValueType.CALCULATED,
                        description=f"Projected 12-month recurring expenditure for {plan.plan_name}.",
                        evidence_text=plan.evidence_text,
                        is_critical_action=False,
                    )
                )
            return FinancialTimeline(
                events=events,
                annualized_cost=annual_cost,
                annualized_cost_assumptions=assumptions,
            )
        else:
            events.append(
                TimelineEvent(
                    timepoint=f"After {plan.trial_duration}",
                    title="Renewal Charge Amount (Undisclosed)",
                    amount=None,
                    value_type=TimelineValueType.UNRESOLVED,
                    description=f"Renewal price after {plan.trial_duration} trial is not disclosed for {plan.plan_name}.",
                    evidence_text="",
                    is_critical_action=True,
                )
            )
            return FinancialTimeline(events=events, annualized_cost=None)

    elif plan.future_charge:
        if plan.amount_due_now:
            events.append(
                TimelineEvent(
                    timepoint="Today",
                    title="Initial Payment Due Now",
                    amount=plan.amount_due_now,
                    value_type=TimelineValueType.OBSERVED,
                    description=f"Initial charge of {plan.amount_due_now.currency} {plan.amount_due_now.amount} for {plan.plan_name}.",
                    evidence_text=plan.evidence_text,
                    is_critical_action=False,
                )
            )
        interval_name = _INTERVAL_NOUN.get(plan.billing_interval or "", plan.billing_interval or "period")
        events.append(
            TimelineEvent(
                timepoint=f"Every {interval_name}",
                title=f"{plan.plan_name} Recurring Charge",
                amount=plan.future_charge,
                value_type=TimelineValueType.OBSERVED,
                description=f"Billed at {plan.future_charge.currency} {plan.future_charge.amount} per {interval_name}.",
                evidence_text=plan.evidence_text,
                is_critical_action=False,
            )
        )
        annual_cost, assumptions = calculate_annualized_cost(
            plan.future_charge, introductory=plan.amount_due_now
        )
        if annual_cost:
            events.append(
                TimelineEvent(
                    timepoint="12-Month Projection",
                    title="Annualized Recurring Commitment",
                    amount=annual_cost,
                    value_type=TimelineValueType.CALCULATED,
                    description=f"Projected 12-month recurring expenditure for {plan.plan_name}.",
                    evidence_text=plan.evidence_text,
                    is_critical_action=False,
                )
            )
        return FinancialTimeline(
            events=events,
            annualized_cost=annual_cost,
            annualized_cost_assumptions=assumptions,
        )

    return FinancialTimeline(events=events, annualized_cost=None)


def build_financial_timeline(
    det_result,
    commitment_map: CommitmentMap,
    price_integrity: PriceIntegrity,
    page_text: str,
) -> FinancialTimeline:
    """Construct an empirical, chronological timeline of commitments and deadlines."""
    events: List[TimelineEvent] = []

    # Case 1: Multiple plans without an established selection
    if len(det_result.plans) > 1:
        return FinancialTimeline(
            events=[],
            annualized_cost=None,
            note=f"Multiple pricing plans detected ({len(det_result.plans)} tiers). Plan selection is not established; see individual plan breakdown for tier-specific timelines.",
        )

    # Case 2: Conflicting price terms detected
    if det_result.conflicts_detected:
        ev_snip = _find_matching_evidence(det_result.conflicts_detected + det_result.evidence_snippets, page_text)
        events.append(
            TimelineEvent(
                timepoint="At Checkout / Unresolved",
                title="Conflicting Price Terms",
                amount=None,
                value_type=TimelineValueType.UNRESOLVED,
                description=f"Conflicting pricing mentions detected ({', '.join(det_result.conflicts_detected)}). Final charge terms cannot be deterministically resolved.",
                evidence_text=ev_snip,
                is_critical_action=True,
            )
        )
        return FinancialTimeline(
            events=events,
            annualized_cost=None,
            note="Timeline cannot be established due to conflicting pricing terms on page.",
        )

    cancellation = extract_cancellation_terms(page_text)

    # Case 3: Free Trial with or without subsequent renewal
    if det_result.trial_duration:
        trial_snip = _find_matching_evidence(
            det_result.evidence_snippets + [det_result.trial_duration], page_text
        )

        # Milestone 1: Start of Trial (Due Now)
        due_now_amt = commitment_map.amount_due_now
        if not due_now_amt:
            curr = commitment_map.future_charge.currency if commitment_map.future_charge else "USD"
            due_now_amt = MoneyValue(amount="0", currency=curr, kind=MoneyKind.TRIAL)

        events.append(
            TimelineEvent(
                timepoint="Today",
                title="Free Trial Begins",
                amount=due_now_amt,
                value_type=TimelineValueType.OBSERVED,
                description=f"Start of {det_result.trial_duration} trial period.",
                evidence_text=trial_snip,
                is_critical_action=False,
            )
        )

        # Milestone 2: Cancellation Deadline
        if cancellation and cancellation.deadline:
            events.append(
                TimelineEvent(
                    timepoint="Before Trial Ends",
                    title="Cancellation Cutoff Deadline",
                    amount=None,
                    value_type=TimelineValueType.OBSERVED,
                    description=f"Cancellation required ({cancellation.deadline}) to prevent auto-renewal charge.",
                    evidence_text=cancellation.deadline,
                    is_critical_action=True,
                )
            )
        else:
            cancel_snip = cancellation.terms if cancellation and cancellation.terms in page_text else ""
            events.append(
                TimelineEvent(
                    timepoint="Before Trial Ends",
                    title="Cancellation Deadline (Unspecified)",
                    amount=None,
                    value_type=TimelineValueType.UNRESOLVED,
                    description="Exact cancellation cutoff deadline is not disclosed on page. Review account settings prior to expiration.",
                    evidence_text=cancel_snip,
                    is_critical_action=True,
                )
            )

        # Milestone 3: First Future Charge (or Unresolved Renewal Price)
        if commitment_map.future_charge:
            future_snip = _find_matching_evidence(
                [det_result.future_charge_trigger] + det_result.evidence_snippets, page_text
            ) or trial_snip
            events.append(
                TimelineEvent(
                    timepoint=f"After {det_result.trial_duration}",
                    title="First Recurring Charge",
                    amount=commitment_map.future_charge,
                    value_type=TimelineValueType.OBSERVED,
                    description=f"Trial transitions to recurring charge of {commitment_map.future_charge.currency} {commitment_map.future_charge.amount}{_interval_label(commitment_map.future_charge.interval)} unless cancelled.",
                    evidence_text=future_snip,
                    is_critical_action=False,
                )
            )

            # Milestone 4: Ongoing Billing
            interval_str = _interval_label(commitment_map.future_charge.interval)
            events.append(
                TimelineEvent(
                    timepoint=f"Every {_INTERVAL_NOUN.get(commitment_map.future_charge.interval or '', commitment_map.future_charge.interval or 'period')} thereafter",
                    title="Ongoing Subscription",
                    amount=commitment_map.future_charge,
                    value_type=TimelineValueType.OBSERVED,
                    description=f"Recurring subscription bills {commitment_map.future_charge.currency} {commitment_map.future_charge.amount}{interval_str} automatically.",
                    evidence_text=future_snip,
                    is_critical_action=False,
                )
            )

            # Annualized Cost Calculation
            annual_cost, assumptions = calculate_annualized_cost(commitment_map.future_charge)
            if annual_cost:
                events.append(
                    TimelineEvent(
                        timepoint="12-Month Projection",
                        title="Annualized Recurring Commitment",
                        amount=annual_cost,
                        value_type=TimelineValueType.CALCULATED,
                        description=f"Projected 12-month recurring expenditure of {annual_cost.currency} {annual_cost.amount} based on stated interval.",
                        evidence_text=future_snip,
                        is_critical_action=False,
                    )
                )
            return FinancialTimeline(
                events=events,
                annualized_cost=annual_cost,
                annualized_cost_assumptions=assumptions,
            )
        else:
            # Trial without stated renewal price
            events.append(
                TimelineEvent(
                    timepoint=f"After {det_result.trial_duration}",
                    title="Renewal Charge Amount (Undisclosed)",
                    amount=None,
                    value_type=TimelineValueType.UNRESOLVED,
                    description="The renewal charge amount upon trial expiration is not disclosed in the visible text.",
                    evidence_text="",
                    is_critical_action=True,
                )
            )
            return FinancialTimeline(
                events=events,
                annualized_cost=None,
                note="Renewal price after trial is not stated on this page.",
            )

    # Case 4: Subscription with Upfront/Recurring Charges (No Trial)
    if commitment_map.future_charge:
        future_snip = _find_matching_evidence(
            det_result.evidence_snippets + [det_result.future_charge_trigger], page_text
        )

        if commitment_map.amount_due_now:
            due_snip = _find_matching_evidence(
                det_result.evidence_snippets, page_text
            ) or future_snip
            events.append(
                TimelineEvent(
                    timepoint="Today",
                    title="Initial Payment Due Now",
                    amount=commitment_map.amount_due_now,
                    value_type=TimelineValueType.OBSERVED,
                    description=f"Initial charge of {commitment_map.amount_due_now.currency} {commitment_map.amount_due_now.amount} due immediately.",
                    evidence_text=due_snip,
                    is_critical_action=False,
                )
            )

        if cancellation and cancellation.deadline:
            events.append(
                TimelineEvent(
                    timepoint="Before Renewal",
                    title="Cancellation Cutoff Deadline",
                    amount=None,
                    value_type=TimelineValueType.OBSERVED,
                    description=f"Notice required ({cancellation.deadline}) to prevent renewal.",
                    evidence_text=cancellation.deadline,
                    is_critical_action=True,
                )
            )

        interval_name = _INTERVAL_NOUN.get(
            commitment_map.future_charge.interval or "", commitment_map.future_charge.interval or "period"
        )
        events.append(
            TimelineEvent(
                timepoint=f"Next Billing Period ({interval_name})",
                title="Next Recurring Charge",
                amount=commitment_map.future_charge,
                value_type=TimelineValueType.OBSERVED,
                description=f"Subsequent recurring charge of {commitment_map.future_charge.currency} {commitment_map.future_charge.amount}.",
                evidence_text=future_snip,
                is_critical_action=False,
            )
        )

        events.append(
            TimelineEvent(
                timepoint=f"Every {interval_name} thereafter",
                title="Ongoing Subscription",
                amount=commitment_map.future_charge,
                value_type=TimelineValueType.OBSERVED,
                description=f"Renews automatically at {commitment_map.future_charge.currency} {commitment_map.future_charge.amount} per {interval_name} until cancelled.",
                evidence_text=future_snip,
                is_critical_action=False,
            )
        )

        annual_cost, assumptions = calculate_annualized_cost(
            commitment_map.future_charge, introductory=commitment_map.amount_due_now
        )
        if annual_cost:
            events.append(
                TimelineEvent(
                    timepoint="12-Month Projection",
                    title="Annualized Recurring Commitment",
                    amount=annual_cost,
                    value_type=TimelineValueType.CALCULATED,
                    description=f"Projected 12-month recurring expenditure of {annual_cost.currency} {annual_cost.amount}.",
                    evidence_text=future_snip,
                    is_critical_action=False,
                )
            )

        return FinancialTimeline(
            events=events,
            annualized_cost=annual_cost,
            annualized_cost_assumptions=assumptions,
        )

    # Case 5: One-Time Purchase (No Recurring Commitment)
    one_time_amount = price_integrity.final_total or commitment_map.amount_due_now
    if one_time_amount:
        ot_snip = _find_matching_evidence(
            det_result.evidence_snippets + [one_time_amount.amount], page_text
        )
        events.append(
            TimelineEvent(
                timepoint="Today (Checkout)",
                title="One-Time Payment Due Now",
                amount=one_time_amount,
                value_type=TimelineValueType.OBSERVED,
                description=f"Single purchase payment of {one_time_amount.currency} {one_time_amount.amount} payable at checkout.",
                evidence_text=ot_snip,
                is_critical_action=False,
            )
        )
        events.append(
            TimelineEvent(
                timepoint="Future Obligations",
                title="No Recurring Charges",
                amount=None,
                value_type=TimelineValueType.OBSERVED,
                description="One-time transaction with no ongoing subscription or recurring billing commitments.",
                evidence_text=ot_snip,
                is_critical_action=False,
            )
        )
        return FinancialTimeline(
            events=events,
            annualized_cost=None,
            note="One-time transaction. Annualized cost is not applicable.",
        )

    # Case 6: Empty / No commercial terms found
    return FinancialTimeline(
        events=[],
        annualized_cost=None,
        note="No financial commitment terms or recurring charges detected in visible text.",
    )


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
        locale=request.locale,
    )

    # 3. Combine findings (deterministic takes priority; AI findings appended if grounded)
    findings = list(det_result.findings)
    for ai_f in ai_result.additional_findings:
        # Avoid duplicate findings for same category
        if not any(f.category == ai_f.category for f in findings):
            findings.append(ai_f)

    # Post-validation: ensure explicit findings have evidence grounded in page text
    validated_findings: List[Finding] = []
    for f in findings:
        if f.evidence_level == EvidenceLevel.EXPLICIT:
            if not f.evidence_text or f.evidence_text not in request.page_text:
                if f.category == FindingCategory.MISSING_COMMITMENT_INFO:
                    f = f.model_copy(update={"evidence_level": EvidenceLevel.UNKNOWN, "evidence_text": ""})
                else:
                    continue
        validated_findings.append(f)
    findings = validated_findings

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

    # 9. Build Plan Timelines (if plans detected)
    for p in det_result.plans:
        p.timeline = build_plan_timeline(p, request.page_text)

    # 10. Build Primary Financial Commitment Timeline (Phase 7)
    timeline = build_financial_timeline(
        det_result=det_result,
        commitment_map=commitment_map,
        price_integrity=price_integrity,
        page_text=request.page_text,
    )

    return AnalyzeResponse(
        status=status,
        summary=summary,
        findings=findings,
        commitment_map=commitment_map,
        plans=det_result.plans,
        price_integrity=price_integrity,
        checklist=checklist,
        limitations=limitations,
        timeline=timeline,
    )
