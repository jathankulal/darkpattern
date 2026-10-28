"""Core financial commitment analyzer for Dark Pattern Guardian.

Combines deterministic extraction baseline with optional AI interpretation layer.
"""

import re
from decimal import Decimal
from typing import List, Optional

from app.ai.base import AIInterpreter, NullAIInterpreter
from app.ai.comparison import compare_ai_proposals
from app.ai.proposals import AIProposalProvider, NullAIProposalProvider
from app.config import Settings
from app.extraction import (
    ExtractedCancellation,
    detect_recurring_signals,
    extract_cancellation_terms,
    extract_prices_from_text,
    run_deterministic_analysis,
)
from app.schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    AnalyzeWithComparisonResponse,
    AIProposalComparison,
    AIProposalProviderStatus,
    AnalyzeStatus,
    CommitmentMap,
    EvidenceLevel,
    FinancialTimeline,
    Finding,
    FindingCategory,
    MoneyKind,
    MoneyValue,
    MAX_ANALYZE_PLANS,
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


def _find_price_evidence(amount: Optional[MoneyValue], page_text: str) -> str:
    """Find the verbatim extracted price snippet matching a monetary value."""
    if amount is None:
        return ""
    for price in extract_prices_from_text(page_text):
        if price.amount == amount.amount and price.currency == amount.currency:
            evidence = _find_matching_evidence([price.raw_snippet], page_text)
            if evidence:
                return evidence
    return ""


def _find_price_context_evidence(amount: Optional[MoneyValue], page_text: str) -> str:
    """Find a bounded verbatim sentence containing the extracted price."""
    price_evidence = _find_price_evidence(amount, page_text)
    if not price_evidence:
        return ""
    for sentence in re.split(r"(?<=[.!?])\s+|\n+", page_text):
        sentence = sentence.strip()
        if price_evidence in sentence and len(sentence) <= 1000:
            return sentence
    return price_evidence


def _cancellation_timeline_event(
    cancellation: Optional[ExtractedCancellation],
    *,
    page_text: str,
    timepoint: str,
) -> TimelineEvent:
    """Describe cancellation wording without inferring an unstated cutoff."""
    evidence = (
        cancellation.terms
        if cancellation and cancellation.terms in page_text
        else ""
    )
    if cancellation and cancellation.deadline:
        return TimelineEvent(
            timepoint=timepoint,
            title="Cancellation Cutoff Deadline",
            amount=None,
            value_type=TimelineValueType.OBSERVED,
            description=(
                f"The page states: {cancellation.deadline}. The calendar cutoff "
                "depends on the stated renewal or trial timing."
            ),
            evidence_text=evidence,
            is_critical_action=True,
        )
    if cancellation and cancellation.timing_unclear:
        return TimelineEvent(
            timepoint="Cancellation timing unclear",
            title="Cancellation Timing Is Unclear",
            amount=None,
            value_type=TimelineValueType.UNRESOLVED,
            description=(
                "The page refers to the billing cycle but does not say when it "
                "ends, so the exact cancellation cutoff cannot be determined."
            ),
            evidence_text=evidence,
            is_critical_action=False,
        )
    if cancellation:
        return TimelineEvent(
            timepoint=timepoint,
            title="Cancellation Instructions",
            amount=None,
            value_type=TimelineValueType.OBSERVED,
            description=(
                "Cancellation instructions appear on the page, but no cutoff "
                "deadline is stated."
            ),
            evidence_text=evidence,
            is_critical_action=False,
        )
    return TimelineEvent(
        timepoint=timepoint,
        title="Cancellation Cutoff Not Stated",
        amount=None,
        value_type=TimelineValueType.UNRESOLVED,
        description=(
            "No cancellation cutoff was found in the text checked. Whether "
            "cancellation is needed to prevent renewal is not stated."
        ),
        evidence_text="",
        is_critical_action=False,
    )


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
        cancellation = extract_cancellation_terms(page_text)
        if plan.cancellation_terms and cancellation and cancellation.deadline:
            events.append(
                _cancellation_timeline_event(
                    cancellation,
                    page_text=page_text,
                    timepoint="Before stated renewal cutoff",
                )
            )
        elif plan.cancellation_terms:
            events.append(
                _cancellation_timeline_event(
                    cancellation,
                    page_text=page_text,
                    timepoint="During trial",
                )
            )
        if plan.future_charge:
            is_one_time = plan.future_charge.kind == MoneyKind.ONE_TIME
            events.append(
                TimelineEvent(
                    timepoint=f"After {plan.trial_duration}",
                    title=(
                        "Post-Trial One-Time Payment"
                        if is_one_time
                        else "First Recurring Charge"
                    ),
                    amount=plan.future_charge,
                    value_type=TimelineValueType.OBSERVED,
                    description=(
                        f"{plan.plan_name} has a one-time payment of "
                        f"{plan.future_charge.currency} {plan.future_charge.amount} "
                        "after the trial."
                        if is_one_time
                        else f"{plan.plan_name} renews at {plan.future_charge.currency} {plan.future_charge.amount}{_interval_label(plan.future_charge.interval)}."
                    ),
                    evidence_text=plan.evidence_text,
                    is_critical_action=False,
                )
            )
            if is_one_time:
                return FinancialTimeline(events=events, annualized_cost=None)
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
            ambiguous_payment = any(
                "Post-trial payment terms are unclear" in unknown
                for unknown in plan.unknowns
            )
            events.append(
                TimelineEvent(
                    timepoint=f"After {plan.trial_duration}",
                    title=(
                        "Post-Trial Billing Terms Unresolved"
                        if ambiguous_payment
                        else "Renewal Charge Amount (Undisclosed)"
                    ),
                    amount=None,
                    value_type=TimelineValueType.UNRESOLVED,
                    description=(
                        f"The post-trial amount is present for {plan.plan_name}, but "
                        "the page does not establish whether it is one-time or "
                        "recurring, or state a billing frequency."
                        if ambiguous_payment
                        else f"Renewal price after {plan.trial_duration} trial is not disclosed for {plan.plan_name}."
                    ),
                    evidence_text=plan.evidence_text if ambiguous_payment else "",
                    is_critical_action=False,
                )
            )
            return FinancialTimeline(
                events=events,
                annualized_cost=None,
                note=(
                    "A post-trial amount is present, but recurrence and billing "
                    "frequency are not established."
                    if ambiguous_payment
                    else "Renewal price after trial is not stated on this page."
                ),
            )

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
                _cancellation_timeline_event(
                    cancellation,
                    page_text=page_text,
                    timepoint="Before stated renewal cutoff",
                )
            )
        else:
            events.append(
                _cancellation_timeline_event(
                    cancellation,
                    page_text=page_text,
                    timepoint="During trial",
                )
            )

        # Milestone 3: First Future Charge (or Unresolved Renewal Price)
        if commitment_map.future_charge:
            future_snip = _find_price_context_evidence(
                commitment_map.future_charge, page_text
            )
            is_one_time = commitment_map.future_charge.kind == MoneyKind.ONE_TIME
            events.append(
                TimelineEvent(
                    timepoint=f"After {det_result.trial_duration}",
                    title=(
                        "Post-Trial One-Time Payment"
                        if is_one_time
                        else "First Recurring Charge"
                    ),
                    amount=commitment_map.future_charge,
                    value_type=TimelineValueType.OBSERVED,
                    description=(
                        f"The trial is followed by a one-time payment of "
                        f"{commitment_map.future_charge.currency} "
                        f"{commitment_map.future_charge.amount}."
                        if is_one_time
                        else f"Trial transitions to recurring charge of {commitment_map.future_charge.currency} {commitment_map.future_charge.amount}{_interval_label(commitment_map.future_charge.interval)} unless cancelled."
                    ),
                    evidence_text=future_snip,
                    is_critical_action=False,
                )
            )

            if is_one_time:
                return FinancialTimeline(events=events, annualized_cost=None)

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
            ambiguous_payment = any(
                "Post-trial payment terms are unclear" in unknown
                for unknown in det_result.unknowns
            )
            ambiguous_evidence = ""
            if ambiguous_payment:
                post_trial_prices = [
                    price
                    for price in extract_prices_from_text(page_text)
                    if price.amount not in ("0", "0.0", "0.00")
                ]
                ambiguous_evidence = _find_matching_evidence(
                    [price.raw_snippet for price in post_trial_prices], page_text
                )
            events.append(
                TimelineEvent(
                    timepoint=f"After {det_result.trial_duration}",
                    title=(
                        "Post-Trial Billing Terms Unresolved"
                        if ambiguous_payment
                        else "Renewal Charge Amount (Undisclosed)"
                    ),
                    amount=None,
                    value_type=TimelineValueType.UNRESOLVED,
                    description=(
                        "A post-trial amount is present, but the page does not "
                        "establish whether it is one-time or recurring or specify "
                        "a billing frequency."
                        if ambiguous_payment
                        else "The renewal charge amount upon trial expiration is not disclosed in the visible text."
                    ),
                    evidence_text=ambiguous_evidence,
                    is_critical_action=False,
                )
            )
            return FinancialTimeline(
                events=events,
                annualized_cost=None,
                note=(
                    "A post-trial amount is present, but recurrence and billing "
                    "frequency are not established."
                    if ambiguous_payment
                    else "Renewal price after trial is not stated on this page."
                ),
            )

    # Case 4: Subscription with Upfront/Recurring Charges (No Trial)
    if commitment_map.future_charge:
        price_snip = _find_price_evidence(commitment_map.future_charge, page_text)
        recurring_signal, recurring_evidence = detect_recurring_signals(page_text)
        renewal_snip = (
            _find_matching_evidence([recurring_evidence], page_text)
            if recurring_signal
            else ""
        )

        if commitment_map.amount_due_now:
            due_snip = _find_price_evidence(commitment_map.amount_due_now, page_text)
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
                _cancellation_timeline_event(
                    cancellation,
                    page_text=page_text,
                    timepoint="Before stated renewal cutoff",
                )
            )
        elif cancellation:
            events.append(
                _cancellation_timeline_event(
                    cancellation,
                    page_text=page_text,
                    timepoint="Cancellation",
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
                evidence_text=renewal_snip,
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
                evidence_text=renewal_snip,
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
                    description=(
                        f"Calculated 12-month projection of {annual_cost.currency} "
                        f"{annual_cost.amount} from the stated recurring price and billing "
                        "interval; this is not a directly observed charge."
                    ),
                    evidence_text=price_snip,
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
        ot_snip = _find_price_context_evidence(one_time_amount, page_text)
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
        if "post-trial payment terms are unclear" in u_lower:
            checklist.append(
                "Confirm whether the post-trial amount is one-time or recurring and, if recurring, how often it is billed"
            )
        elif "renewal" in u_lower or "future" in u_lower:
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

    elif (
        amount_due_now
        and future_charge
        and amount_due_now.kind == MoneyKind.TRIAL
        and future_charge.kind == MoneyKind.ONE_TIME
    ):
        observations.append(
            PriceObservation(
                stage="trial",
                amount=amount_due_now,
                context="Free trial period",
            )
        )
        observations.append(
            PriceObservation(
                stage="post-trial",
                amount=future_charge,
                context="One-time payment after trial",
            )
        )
        reason = PriceIntegrityReason.KNOWN

    elif (
        amount_due_now
        and future_charge
        and amount_due_now.kind == MoneyKind.TRIAL
        and future_charge.kind == MoneyKind.RECURRING
    ):
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
    unknowns: Optional[List[str]] = None,
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
        if future.kind == MoneyKind.ONE_TIME:
            return (
                f"Free trial lasting {trial} followed by a one-time payment of "
                f"{future.currency} {future.amount}; recurring billing is not stated."
            )
        interval_str = _interval_label(future.interval)
        return (
            f"Free trial lasting {trial} converting to a recurring charge of "
            f"{future.currency} {future.amount}{interval_str}."
        )

    if trial and not future:
        if any(
            "Post-trial payment terms are unclear" in unknown
            for unknown in (unknowns or [])
        ):
            return (
                f"A free trial of {trial} was identified. A post-trial amount "
                "is stated, but whether it is one-time or recurring and its "
                "billing frequency are not clear from the page."
            )
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

    # 3. Trusted findings come only from deterministic analysis.
    findings = list(det_result.findings)

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
        has_recurring=det_result.is_recurring
        or bool(
            det_result.future_charge
            and det_result.future_charge.kind == MoneyKind.RECURRING
        ),
        has_trial=any(bool(p.trial_duration) for p in det_result.plans) if det_result.plans else bool(det_result.trial_duration),
    )

    # 7. Disclose Boundaries and Limitations
    limitations: List[str] = [
        "Analysis based strictly on bounded visible text submitted by browser extension.",
    ]
    if ai_result.ai_status == "active":
        limitations.append(
            "The optional AI interpreter ran, but its findings are not included in "
            "trusted results; findings and financial calculations remain deterministic."
        )
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
        unknowns=commitment_map.unknowns,
    )

    status = AnalyzeStatus.OK
    has_ambiguity = any(p.is_ambiguous for p in det_result.plans)
    has_unexplained = price_integrity.unexplained_difference is not None
    if det_result.conflicts_detected or (det_result.trial_duration and not det_result.future_charge) or has_ambiguity or has_unexplained:
        status = AnalyzeStatus.PARTIAL

    # 9. Build timelines for the bounded response copy, preserving extracted plans.
    response_plans = [
        p.model_copy(
            deep=True,
            update={"timeline": build_plan_timeline(p, request.page_text)},
        )
        for p in det_result.plans[:MAX_ANALYZE_PLANS]
    ]

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
        plans=response_plans,
        price_integrity=price_integrity,
        checklist=checklist,
        limitations=limitations,
        timeline=timeline,
    )


def analyze_page_with_proposal_comparison(
    request: AnalyzeRequest,
    settings: Settings,
    ai_proposal_provider: Optional[AIProposalProvider] = None,
) -> AnalyzeWithComparisonResponse:
    """Run deterministic analysis and an isolated, opt-in proposal comparison."""
    analysis = analyze_page_content(
        request=request,
        settings=settings,
        ai_interpreter=NullAIInterpreter(),
    )
    analysis.limitations = [
        limitation
        for limitation in analysis.limitations
        if limitation
        != "Deterministic extraction applied; AI contextual interpretation not configured."
    ]
    provider = (
        ai_proposal_provider
        if ai_proposal_provider is not None
        else NullAIProposalProvider()
    )

    try:
        if not provider.is_configured:
            comparison = AIProposalComparison(
                status=AIProposalProviderStatus.UNCONFIGURED,
            )
            analysis.limitations.append(
                "Trusted findings and financial calculations remain deterministic; "
                "the AI proposal provider is not configured."
            )
        else:
            proposals = provider.propose(
                page_title=request.page_title,
                page_url=request.page_url,
                page_text=request.page_text,
                locale=request.locale,
            )
            results = compare_ai_proposals(
                proposals=proposals,
                deterministic_findings=analysis.findings,
                page_text=request.page_text,
            )
            comparison = AIProposalComparison(
                status=AIProposalProviderStatus.ACTIVE,
                results=results,
            )
            analysis.limitations.append(
                "Trusted findings and financial calculations remain deterministic; AI "
                "proposals are separate untrusted candidates and do not validate or modify them."
            )
    except Exception:
        comparison = AIProposalComparison(
            status=AIProposalProviderStatus.FAILED,
        )
        analysis.limitations.append(
            "Trusted findings and financial calculations remain deterministic; AI proposal "
            "analysis failed and was not applied."
        )

    return AnalyzeWithComparisonResponse(
        analysis=analysis,
        ai_comparison=comparison,
    )
