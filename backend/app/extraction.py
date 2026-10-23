"""Deterministic extraction rules and evidence validation for Dark Pattern Guardian.

Enforces:
- Currency and amount parsing (INR / Rupee, USD, EUR, GBP, JPY, etc.)
- Exclusion of percentages (e.g. '20% off'), model numbers, dates, and non-price digits
- Trial duration extraction vs Money-Back Guarantee distinction
- Recurring billing, intervals, renewal triggers, and cancellation deadlines
- Verbatim evidence verification (verifying evidence is an exact substring of page text)
- Conflict and uncertainty preservation
"""

import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Optional, Set, Tuple

from app.schemas import (
    EvidenceLevel,
    FeeItem,
    Finding,
    FindingCategory,
    FindingSeverity,
    MoneyKind,
    MoneyValue,
    PlanSummary,
    PriceIntegrity,
    PriceIntegrityReason,
    PriceObservation,
)


# ---------------------------------------------------------------------------
# Currency Symbol / Code Normalization
# ---------------------------------------------------------------------------

CURRENCY_SYMBOLS: Dict[str, str] = {
    "₹": "INR",
    "rs.": "INR",
    "rs": "INR",
    "inr": "INR",
    "$": "USD",
    "usd": "USD",
    "€": "EUR",
    "eur": "EUR",
    "£": "GBP",
    "gbp": "GBP",
    "¥": "JPY",
    "jpy": "JPY",
}

# Regex to detect currency prefixes or suffixes
CURRENCY_PATTERN = r"(?:₹|Rs\.?|INR|\$|USD|€|EUR|£|GBP|¥|JPY)"


# ---------------------------------------------------------------------------
# Data classes for intermediate extraction
# ---------------------------------------------------------------------------

@dataclass
class ExtractedPrice:
    amount: str
    currency: str
    raw_snippet: str
    kind: MoneyKind = MoneyKind.ONE_TIME
    interval: Optional[str] = None
    context: str = ""
    start_pos: int = -1
    end_pos: int = -1


@dataclass
class ExtractedTrial:
    duration_str: str
    raw_snippet: str
    is_free: bool = True
    start_pos: int = -1
    end_pos: int = -1


@dataclass
class ExtractedCancellation:
    terms: str
    raw_snippet: str
    deadline: Optional[str] = None
    start_pos: int = -1
    end_pos: int = -1


@dataclass
class DeterministicExtractionResult:
    amount_due_now: Optional[MoneyValue] = None
    future_charge: Optional[MoneyValue] = None
    billing_interval: Optional[str] = None
    trial_duration: Optional[str] = None
    future_charge_trigger: Optional[str] = None
    cancellation_terms: Optional[str] = None
    unknowns: List[str] = field(default_factory=list)
    findings: List[Finding] = field(default_factory=list)
    introductory_price: Optional[MoneyValue] = None
    renewal_price: Optional[MoneyValue] = None
    is_recurring: bool = False
    evidence_snippets: List[str] = field(default_factory=list)
    conflicts_detected: List[str] = field(default_factory=list)
    plans: List[PlanSummary] = field(default_factory=list)
    checkout_comparison: Optional[PriceIntegrity] = None


# ---------------------------------------------------------------------------
# Verbatim Evidence Validation Helper
# ---------------------------------------------------------------------------

def validate_verbatim_evidence(snippet: str, source_text: str) -> bool:
    """Return True if snippet is a verbatim non-empty substring of source_text."""
    if not snippet or not source_text:
        return False
    return snippet in source_text


def find_snippet_in_text(snippet: str, source_text: str) -> str:
    """Return snippet if found in source_text, otherwise empty string."""
    if snippet and snippet in source_text:
        return snippet
    return ""


# ---------------------------------------------------------------------------
# Number and Currency Parsing
# ---------------------------------------------------------------------------

def parse_decimal_amount(raw_num: str) -> Optional[str]:
    """Parse a number string (handling standard and Indian comma separators) into Decimal string."""
    try:
        # Strip commas
        cleaned = raw_num.replace(",", "").strip()
        val = Decimal(cleaned)
        if not val.is_finite():
            return None
        return str(val)
    except (InvalidOperation, ValueError):
        return None


def extract_prices_from_text(text: str) -> List[ExtractedPrice]:
    """Extract candidate prices that have explicit currency indicators.

    Strictly ignores:
    - Percentages (e.g. 20% off, 50% discount)
    - Year numbers or model numbers without currency (e.g. 2024, Model 5000)
    - Plain numbers without currency symbols or codes
    """
    prices: List[ExtractedPrice] = []
    if not text:
        return prices

    # Pattern 1: Currency prefix, e.g.: ₹999, ₹ 999.00, Rs. 4,999, $14.99, USD 29.99
    # Pattern 2: Currency suffix, e.g.: 999 INR, 49.99 USD, 15€
    # Note: Negative lookahead ensures we do NOT match percentage like '20%'
    regex_prefix = re.compile(
        r"(?P<prefix>" + CURRENCY_PATTERN + r")\s*(?P<amount>\d{1,3}(?:,\d{2,3})*(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?)(?!\s*%)",
        re.IGNORECASE,
    )
    regex_suffix = re.compile(
        r"(?<![%\w])(?P<amount>\d{1,3}(?:,\d{2,3})*(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?)\s*(?P<suffix>" + CURRENCY_PATTERN + r")(?!\s*%)",
        re.IGNORECASE,
    )

    matches: List[Tuple[int, int, str, str, str]] = []

    for m in regex_prefix.finditer(text):
        raw_snippet = m.group(0)
        curr = m.group("prefix").strip()
        amt = m.group("amount").strip()
        matches.append((m.start(), m.end(), curr, amt, raw_snippet))

    for m in regex_suffix.finditer(text):
        raw_snippet = m.group(0)
        curr = m.group("suffix").strip()
        amt = m.group("amount").strip()
        matches.append((m.start(), m.end(), curr, amt, raw_snippet))

    # Sort matches by position in text
    matches.sort(key=lambda x: x[0])

    for start_pos, end_pos, curr_str, amt_str, snippet in matches:
        # Check surrounding window for discount indicators (e.g., "save ₹500", "₹500 off")
        window_start = max(0, start_pos - 40)
        window_end = min(len(text), end_pos + 60)
        window = text[window_start:window_end]

        # Ignore if explicit discount amount, e.g. "Save $10", "₹500 off", "discount of ₹100"
        if re.search(r"(?:save|discount of|off)\s*" + re.escape(snippet), window, re.IGNORECASE) or \
           re.search(re.escape(snippet) + r"\s*(?:off|discount|cashback)", window, re.IGNORECASE):
            continue

        normalized_curr = CURRENCY_SYMBOLS.get(curr_str.lower(), curr_str.upper())
        dec_amount = parse_decimal_amount(amt_str)
        if not dec_amount:
            continue

        # Check for billing interval in immediate following window
        interval = None
        after_window = text[end_pos : min(len(text), end_pos + 40)]
        if re.search(r"/(?:mo|month)|per\s+month|monthly", after_window, re.IGNORECASE):
            interval = "monthly"
        elif re.search(r"/(?:yr|year)|per\s+year|annually|annual|yearly", after_window, re.IGNORECASE):
            interval = "annually"
        elif re.search(r"/(?:wk|week)|per\s+week|weekly", after_window, re.IGNORECASE):
            interval = "weekly"
        elif re.search(r"/(?:qtr|quarter)|per\s+quarter|quarterly", after_window, re.IGNORECASE):
            interval = "quarterly"

        # Determine price kind from context
        kind = MoneyKind.ONE_TIME
        if interval or re.search(r"renews?|recurring|subscription|billed\s+(?:monthly|annually|each)", window, re.IGNORECASE):
            kind = MoneyKind.RECURRING

        # Check if trial price (e.g. ₹0 or free)
        if dec_amount in ("0", "0.0", "0.00") and re.search(r"trial|free", window, re.IGNORECASE):
            kind = MoneyKind.TRIAL

        # Expand snippet to include interval if adjacent, e.g. "₹999 per month"
        expanded_snippet = snippet
        interval_match = re.search(r"^(\s*(?:/(?:mo|month|yr|year|wk|week)|per\s+(?:month|year|week|quarter)|monthly|annually))", after_window, re.IGNORECASE)
        if interval_match:
            expanded_snippet = text[start_pos : end_pos + interval_match.end()]

        prices.append(
            ExtractedPrice(
                amount=dec_amount,
                currency=normalized_curr,
                raw_snippet=expanded_snippet,
                kind=kind,
                interval=interval,
                context=window.strip(),
                start_pos=start_pos,
                end_pos=end_pos,
            )
        )

    return prices


# ---------------------------------------------------------------------------
# Trial Extraction vs Money-Back Guarantee
# ---------------------------------------------------------------------------

def extract_trial_terms(text: str) -> Optional[ExtractedTrial]:
    """Extract free trial period while explicitly ignoring money-back guarantees.

    A 30-day money-back guarantee is NOT a trial.
    A 7-day free trial IS a trial.
    """
    if not text:
        return None

    # First, locate money-back guarantees so we don't confuse them
    mbg_pattern = re.compile(
        r"\b(?:\d+[\s-]*(?:day|month|year)[\s-]*)?(?:money[\s-]*back|satisfaction|risk[\s-]*free)[\s-]*(?:guarantee|warranty)\b",
        re.IGNORECASE,
    )

    # Free trial pattern: e.g. "7-day free trial", "free trial for 14 days", "try free for 30 days"
    trial_pattern = re.compile(
        r"(?:(?:free\s+trial\s+(?:of|for)\s+)?(?P<num>\d+)[\s-]*(?P<unit>days?|weeks?|months?)[\s-]*(?:free\s+trial|trial)|(?:free\s+trial\s*(?:for|of)\s*(?P<num2>\d+)[\s-]*(?P<unit2>days?|weeks?|months?))|(?:try\s+(?:it\s+)?free\s+for\s+(?P<num3>\d+)[\s-]*(?P<unit3>days?|weeks?|months?))|(?:start\s+(?:your\s+)?free\s+(?P<num4>\d+)[\s-]*(?P<unit4>days?|weeks?|months?)[\s-]*(?:free\s+trial|trial)))",
        re.IGNORECASE,
    )

    for m in trial_pattern.finditer(text):
        snippet = m.group(0).strip()
        # Verify it's not actually part of a money back guarantee
        window_start = max(0, m.start() - 30)
        window_end = min(len(text), m.end() + 30)
        window = text[window_start:window_end]

        if mbg_pattern.search(window):
            # Check if "guarantee" is directly connected to this span
            if "guarantee" in window.lower() and "free trial" not in snippet.lower():
                continue

        num = m.group("num") or m.group("num2") or m.group("num3") or m.group("num4")
        unit = m.group("unit") or m.group("unit2") or m.group("unit3") or m.group("unit4")
        if num and unit:
            u_clean = unit.lower()
            if num != "1" and not u_clean.endswith("s"):
                u_clean += "s"
            elif num == "1" and u_clean.endswith("s"):
                u_clean = u_clean[:-1]
            duration = f"{num} {u_clean}"
            return ExtractedTrial(
                duration_str=duration,
                raw_snippet=snippet,
                is_free=True,
                start_pos=m.start(),
                end_pos=m.end(),
            )

    # General trial indicator without specific duration
    generic_match = re.search(r"\b(?:free\s+trial|start\s+(?:your\s+)?trial)\b", text, re.IGNORECASE)
    if generic_match:
        # Check not money back
        window = text[max(0, generic_match.start() - 30) : min(len(text), generic_match.end() + 30)]
        if not mbg_pattern.search(window):
            return ExtractedTrial(
                duration_str="Unspecified duration",
                raw_snippet=generic_match.group(0).strip(),
                is_free=True,
                start_pos=generic_match.start(),
                end_pos=generic_match.end(),
            )

    return None


# ---------------------------------------------------------------------------
# Cancellation Terms Extraction
# ---------------------------------------------------------------------------

def extract_cancellation_terms(text: str) -> Optional[ExtractedCancellation]:
    """Extract cancellation conditions, refund rules, and deadline requirements."""
    if not text:
        return None

    # Patterns with explicit deadlines (e.g. "cancel at least 24 hours before renewal")
    deadline_pattern = re.compile(
        r"cancel\s+(?:at\s+least\s+)?(?:\d+\s+(?:hours?|days?|hrs?))\s+before\s+(?:renewal|the\s+trial\s+ends?|next\s+billing|billing)",
        re.IGNORECASE,
    )
    m = deadline_pattern.search(text)
    if m:
        snippet = m.group(0).strip()
        return ExtractedCancellation(
            terms=snippet,
            raw_snippet=snippet,
            deadline=snippet,
            start_pos=m.start(),
            end_pos=m.end(),
        )

    # "Cancel anytime before trial ends" / "cancel anytime"
    anytime_pattern = re.compile(
        r"cancel\s+(?:online\s+)?anytime(?:\s+before\s+(?:trial\s+ends?|renewal|billing\s+date))?",
        re.IGNORECASE,
    )
    m = anytime_pattern.search(text)
    if m:
        snippet = m.group(0).strip()
        return ExtractedCancellation(
            terms=snippet,
            raw_snippet=snippet,
            start_pos=m.start(),
            end_pos=m.end(),
        )

    # General cancellation mentions
    general_pattern = re.compile(
        r"(?:non-refundable|refund\s+policy|cancellation\s+policy|cancel\s+(?:your\s+)?subscription)",
        re.IGNORECASE,
    )
    m = general_pattern.search(text)
    if m:
        # Grab surrounding sentence / phrase
        window_start = max(0, m.start() - 20)
        window_end = min(len(text), m.end() + 40)
        snippet = text[m.start(): min(len(text), m.end() + 25)].strip()
        return ExtractedCancellation(
            terms=snippet,
            raw_snippet=snippet,
            start_pos=m.start(),
            end_pos=m.end(),
        )

    return None


# ---------------------------------------------------------------------------
# Recurring Signals & Billing Intervals
# ---------------------------------------------------------------------------

def extract_billing_interval(text: str) -> Optional[str]:
    """Detect overall billing frequency from text."""
    if not text:
        return None

    if re.search(r"\b(?:monthly|per\s+month|/mo|every\s+month|billed\s+monthly)\b", text, re.IGNORECASE):
        return "monthly"
    if re.search(r"\b(?:annually|annual|per\s+year|/yr|yearly|every\s+year|billed\s+annually)\b", text, re.IGNORECASE):
        return "annually"
    if re.search(r"\b(?:weekly|per\s+week|/wk|every\s+week|billed\s+weekly)\b", text, re.IGNORECASE):
        return "weekly"
    if re.search(r"\b(?:quarterly|per\s+quarter|every\s+3\s+months|billed\s+quarterly)\b", text, re.IGNORECASE):
        return "quarterly"

    return None


def detect_recurring_signals(text: str) -> Tuple[bool, Optional[str]]:
    """Check if the text exhibits recurring commitment language.

    Returns (is_recurring, matching_evidence_snippet).
    """
    if not text:
        return False, None

    patterns = [
        r"(?:renews?\s+automatically|auto-renews?|automatic\s+renewal|recurring\s+(?:billing|charge|payment))",
        r"(?:renews?\s+unless\s+cancelled|cancel\s+anytime|subscription\s+renews?)",
        r"(?:billed\s+(?:monthly|annually|yearly|each\s+month|every\s+month))",
        r"(?:then\s+(?:₹|Rs\.?|INR|\$|USD|€|EUR|£)\s*\d+.*(?:per\s+month|/mo|monthly|annually))",
    ]

    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            return True, m.group(0).strip()

    return False, None


# ---------------------------------------------------------------------------
# Plan Extraction and Segmentation Logic (Phase 3)
# ---------------------------------------------------------------------------

FALSE_PLAN_WORDS: Set[str] = {
    "floor", "payment", "action", "lesson", "diet", "financial",
    "workout", "meal", "business plan", "strategic", "retirement",
    "insurance", "savings", "pension", "health",
    "recurring", "subscription", "membership", "billing",
}

TIER_NAMES: List[str] = [
    "basic", "starter", "standard", "pro", "professional", "premium",
    "enterprise", "business", "personal", "individual", "team", "ultimate",
    "plus", "lite", "family", "student", "developer", "growth", "free",
    "vip", "tier 1", "tier 2", "tier 3", "tier 4", "tier 5",
    "plan a", "plan b", "plan c", "silver", "gold", "platinum", "diamond",
]


def find_plan_headers(text: str) -> List[Tuple[int, int, str]]:
    """Locate candidate pricing plan headers in text.

    Returns a sorted list of (start_idx, end_idx, plan_name).
    """
    if not text:
        return []

    headers: List[Tuple[int, int, str]] = []
    seen_spans: Set[Tuple[int, int]] = set()

    # Pattern 1: Explicit "[Name] Plan/Tier/Package/Edition/Membership"
    p1 = re.compile(
        r"(?i)\b(?P<name>[A-Za-z0-9\s-]{2,25})\s+(?:Plan|Tier|Package|Edition|Membership)\b"
    )
    for m in p1.finditer(text):
        name_clean = m.group("name").strip()
        lower_name = name_clean.lower()
        if any(f in lower_name for f in FALSE_PLAN_WORDS):
            continue
        name_clean = re.sub(
            r"^(?:our|the|your|this|each|any|choose\s+a|choose\s+your|select\s+your|select\s+a|view|all)\b\s*",
            "",
            name_clean,
            flags=re.IGNORECASE,
        ).strip()
        if len(name_clean) >= 2:
            span = (m.start(), m.end())
            if span not in seen_spans:
                seen_spans.add(span)
                full_label = (
                    f"{name_clean.title()} Plan"
                    if not name_clean.lower().endswith("plan")
                    else name_clean.title()
                )
                headers.append((m.start(), m.end(), full_label))

    # Pattern 2: Known tier names (e.g. Basic, Pro, Premium, Starter, Enterprise)
    tier_pattern = "|".join(re.escape(t) for t in TIER_NAMES)
    p2 = re.compile(
        r"(?i)\b(?P<name>"
        + tier_pattern
        + r")\b(?:\s+(?:Plans?|Tiers?|Packages?|Editions?))?(?=[,\s]+(?:and\s+|or\s+)?(?:"
        + tier_pattern
        + r"|tiers?|plans?|for\s+|[:\-—|\n]|\$|₹|€|£|Rs|try|free|start)|(?:\s*[:\-—|]|\s*\n|\s+(?="
        + CURRENCY_PATTERN
        + r"|\d|try|free|start)))",
    )
    for m in p2.finditer(text):
        name_clean = m.group("name").strip().title()
        start = m.start("name")
        end = m.end("name")
        # Skip "free" when it is part of a trial description (e.g. "free 7-day trial"),
        # not a tier heading like "Free Plan".
        if name_clean.lower() == "free":
            tail = text[end:end + 40]
            if re.match(r"\s*\d+[-\s]+(?:day|week|month)s?\s+trial", tail, re.IGNORECASE):
                continue
            if re.match(r"\s+trial\b", tail, re.IGNORECASE):
                continue
        if not any(s <= start < e or s < end <= e for s, e in seen_spans):
            seen_spans.add((start, end))
            headers.append((start, end, name_clean))

    # Pattern 3: Billing interval plans (Monthly Plan vs Annual Plan)
    p3 = re.compile(
        r"(?i)(?:^|[\n\r]|[-*#\s])(?P<name>Monthly|Annual|Yearly|Quarterly)(?:\s+(?:Plan|Billing|Subscription|Option))?(?:\s*[:\-—|]|\s*\n|\s+(?="
        + CURRENCY_PATTERN
        + r"|\d))",
    )
    for m in p3.finditer(text):
        name_clean = f"{m.group('name').strip().title()} Plan"
        start = m.start("name")
        end = m.end("name")
        if not any(s <= start < e or s < end <= e for s, e in seen_spans):
            seen_spans.add((start, end))
            headers.append((start, end, name_clean))

    # Sort headers chronologically
    headers.sort(key=lambda x: x[0])

    # De-duplicate headers with the same name that are adjacent
    dedup: List[Tuple[int, int, str]] = []
    for h in headers:
        if dedup and dedup[-1][2].lower() == h[2].lower() and (h[0] - dedup[-1][1]) < 30:
            continue
        dedup.append(h)

    return dedup


def _build_plan_summary(
    plan_name: str,
    plan_block: str,
    full_text: str,
    block_offset: int,
) -> PlanSummary:
    """Extract financial terms isolated strictly to this plan's text block."""
    prices = extract_prices_from_text(plan_block)
    trial = extract_trial_terms(plan_block)
    cancellation = extract_cancellation_terms(plan_block)
    interval = extract_billing_interval(plan_block)
    is_recurring, recurring_evidence = detect_recurring_signals(plan_block)

    amount_due_now: Optional[MoneyValue] = None
    future_charge: Optional[MoneyValue] = None
    future_charge_trigger: Optional[str] = None
    trial_duration: Optional[str] = None
    cancellation_terms: Optional[str] = cancellation.terms if cancellation else None
    unknowns: List[str] = []
    is_ambiguous = False
    ambiguity_reason: Optional[str] = None

    # Determine trial
    if trial:
        trial_duration = trial.duration_str
        curr = prices[0].currency if prices else "INR"
        amount_due_now = MoneyValue(amount="0", currency=curr, kind=MoneyKind.TRIAL)

    # Classify prices
    recurring_prices = [p for p in prices if p.kind == MoneyKind.RECURRING or p.interval]
    one_time_prices = [
        p for p in prices if p.kind == MoneyKind.ONE_TIME and p.amount not in ("0", "0.0", "0.00")
    ]

    if trial:
        if recurring_prices:
            renewal = recurring_prices[-1]
            future_charge = MoneyValue(
                amount=renewal.amount,
                currency=renewal.currency,
                kind=MoneyKind.RECURRING,
                interval=renewal.interval or interval or "monthly",
            )
            future_charge_trigger = f"After {trial_duration} trial ends"
        elif one_time_prices:
            renewal = one_time_prices[-1]
            future_charge = MoneyValue(
                amount=renewal.amount,
                currency=renewal.currency,
                kind=MoneyKind.RECURRING,
                interval=interval or "monthly",
            )
            future_charge_trigger = f"After {trial_duration} trial ends"
        else:
            unknowns.append("Renewal price after trial is not stated for this plan")
            is_ambiguous = True
            ambiguity_reason = "Trial offered without disclosed renewal charge"

    elif recurring_prices:
        if len(recurring_prices) > 1 and recurring_prices[0].amount != recurring_prices[1].amount:
            # Introductory + renewal
            intro = recurring_prices[0]
            renewal = recurring_prices[1]
            amount_due_now = MoneyValue(
                amount=intro.amount,
                currency=intro.currency,
                kind=MoneyKind.RECURRING,
                interval=intro.interval or interval,
            )
            future_charge = MoneyValue(
                amount=renewal.amount,
                currency=renewal.currency,
                kind=MoneyKind.RECURRING,
                interval=renewal.interval or interval,
            )
            future_charge_trigger = "Upon expiration of introductory discount period"
        else:
            p = recurring_prices[0]
            amount_due_now = MoneyValue(
                amount=p.amount,
                currency=p.currency,
                kind=MoneyKind.RECURRING,
                interval=p.interval or interval,
            )
            future_charge = MoneyValue(
                amount=p.amount,
                currency=p.currency,
                kind=MoneyKind.RECURRING,
                interval=p.interval or interval,
            )
            future_charge_trigger = f"Renews every {p.interval or interval or 'period'} automatically"

    elif one_time_prices:
        p = one_time_prices[0]
        amount_due_now = MoneyValue(
            amount=p.amount,
            currency=p.currency,
            kind=MoneyKind.ONE_TIME,
            interval=None,
        )
        if is_recurring:
            future_charge = MoneyValue(
                amount=p.amount,
                currency=p.currency,
                kind=MoneyKind.RECURRING,
                interval=interval or "monthly",
            )
            future_charge_trigger = f"Renews every {interval or 'period'} automatically"

    else:
        # No prices found in this plan block
        is_ambiguous = True
        ambiguity_reason = f"No explicit price found for {plan_name} in page text"
        unknowns.append(f"Price for {plan_name} is not disclosed")

    # Conflict check within THIS plan:
    monthly_prices = [p for p in prices if p.interval == "monthly"]
    distinct_monthly = {p.amount for p in monthly_prices}
    if len(distinct_monthly) > 1 and not re.search(r"then\s+", plan_block, re.IGNORECASE):
        is_ambiguous = True
        ambiguity_reason = f"Conflicting monthly prices found for {plan_name}: {', '.join(sorted(distinct_monthly))}"
        unknowns.append(ambiguity_reason)

    # Verbatim snippet for evidence
    snippet = plan_block.strip()
    if len(snippet) > 500:
        lines = [line.strip() for line in snippet.splitlines() if line.strip()]
        snippet = "\n".join(lines[:4])

    if snippet not in full_text:
        snippet = plan_block[:min(len(plan_block), 200)].strip()
        if snippet not in full_text:
            snippet = plan_name

    return PlanSummary(
        plan_name=plan_name,
        amount_due_now=amount_due_now,
        future_charge=future_charge,
        billing_interval=interval or (future_charge.interval if future_charge else None),
        trial_duration=trial_duration,
        future_charge_trigger=future_charge_trigger,
        cancellation_terms=cancellation_terms,
        unknowns=unknowns,
        is_ambiguous=is_ambiguous,
        ambiguity_reason=ambiguity_reason,
        evidence_text=snippet,
    )


def extract_plans_from_text(page_text: str) -> List[PlanSummary]:
    """Segment page text by plan boundaries and extract isolated plan commitments."""
    headers = find_plan_headers(page_text)
    if not headers or len(headers) < 2:
        if len(headers) == 1:
            h_start, h_end, h_name = headers[0]
            plan_block = page_text[h_start:]
            p_summary = _build_plan_summary(h_name, plan_block, page_text, h_start)
            return [p_summary] if p_summary else []
        return []

    # Check if multiple headers appear in close proximity without intervening individual prices
    all_prices = extract_prices_from_text(page_text)
    header_distance = headers[-1][1] - headers[0][0]
    if header_distance < 120 and len(all_prices) == 1:
        shared_price = all_prices[0]
        plans: List[PlanSummary] = []
        for _, _, h_name in headers:
            plans.append(
                PlanSummary(
                    plan_name=h_name,
                    amount_due_now=MoneyValue(
                        amount=shared_price.amount,
                        currency=shared_price.currency,
                        kind=shared_price.kind,
                        interval=shared_price.interval,
                    ),
                    future_charge=MoneyValue(
                        amount=shared_price.amount,
                        currency=shared_price.currency,
                        kind=shared_price.kind,
                        interval=shared_price.interval,
                    )
                    if shared_price.interval
                    else None,
                    billing_interval=shared_price.interval,
                    trial_duration=None,
                    unknowns=["Price is not unambiguously attributed to this specific plan"],
                    is_ambiguous=True,
                    ambiguity_reason=f"Price of {shared_price.currency} {shared_price.amount} is not unambiguously attributed to {h_name} (shared across {', '.join(h[2] for h in headers)}).",
                    evidence_text=page_text[headers[0][0] : min(len(page_text), headers[-1][1] + 60)],
                )
            )
        return plans

    # Segment text into regions per plan
    plans = []
    footer_match = re.search(
        r"(?i)\n(?:frequently\s+asked\s+questions|faq|footer|terms\s+(?:&|and)\s+conditions|all\s+rights\s+reserved)",
        page_text,
    )
    end_of_plans = footer_match.start() if footer_match else len(page_text)

    for i in range(len(headers)):
        start_pos = headers[i][0]
        end_pos = headers[i + 1][0] if (i + 1 < len(headers)) else end_of_plans
        plan_name = headers[i][2]
        plan_block = page_text[start_pos:end_pos]

        p_summary = _build_plan_summary(plan_name, plan_block, page_text, start_pos)
        if p_summary:
            plans.append(p_summary)

    return plans


# ---------------------------------------------------------------------------
# Checkout Price Comparison Logic (Phase 3)
# ---------------------------------------------------------------------------

def extract_checkout_price_comparison(
    page_text: str,
) -> Optional[Tuple[PriceIntegrity, List[Finding]]]:
    """Extract advertised price, checkout subtotal, explicit fees, and final total.

    Performs safe Decimal comparison:
    - Verifies currencies match before comparison
    - Verifies billing intervals match (or both one-time)
    - Compares actual_total with expected_total (subtotal + sum(fees))
    - Identifies unexplained differences without assuming deception
    """
    if not page_text:
        return None

    # 1. Advertised / list / original price
    advertised_price: Optional[MoneyValue] = None
    adv_match = re.search(
        r"(?i)\b(?:advertised|original|item|list|base|regular)\s*(?:price|rate|cost|amount)?\s*[:\-—]?\s*(?P<snippet>(?:"
        + CURRENCY_PATTERN
        + r"\s*\d+(?:,\d{2,3})*(?:\.\d{1,2})?|\d+(?:,\d{2,3})*(?:\.\d{1,2})?\s*"
        + CURRENCY_PATTERN
        + r"))",
        page_text,
    )
    if not adv_match:
        adv_match = re.search(
            r"(?i)\bwas\s+(?P<snippet>" + CURRENCY_PATTERN + r"\s*\d+(?:,\d{2,3})*(?:\.\d{1,2})?)",
            page_text,
        )
    if adv_match:
        prices = extract_prices_from_text(adv_match.group("snippet"))
        if prices:
            advertised_price = MoneyValue(
                amount=prices[0].amount,
                currency=prices[0].currency,
                kind=prices[0].kind,
                interval=prices[0].interval,
            )

    # 2. Checkout Subtotal
    checkout_subtotal: Optional[MoneyValue] = None
    sub_match = re.search(
        r"(?i)\b(?:sub-?total|items?\s+subtotal|cart\s+subtotal|products?\s+total|order\s+subtotal)\s*[:\-—]?\s*(?P<snippet>(?:"
        + CURRENCY_PATTERN
        + r"\s*\d+(?:,\d{2,3})*(?:\.\d{1,2})?|\d+(?:,\d{2,3})*(?:\.\d{1,2})?\s*"
        + CURRENCY_PATTERN
        + r"))",
        page_text,
    )
    if sub_match:
        prices = extract_prices_from_text(sub_match.group("snippet"))
        if prices:
            checkout_subtotal = MoneyValue(
                amount=prices[0].amount,
                currency=prices[0].currency,
                kind=prices[0].kind,
                interval=prices[0].interval,
            )

    # 3. Final Total
    final_total: Optional[MoneyValue] = None
    tot_match = re.search(
        r"(?i)\b(?P<name>(?:order|final|grand|cart|checkout)?\s*total|amount\s+to\s+pay|total\s+amount|total\s+due|you\s+pay)\s*[:\-—]?\s*(?P<snippet>(?:"
        + CURRENCY_PATTERN
        + r"\s*\d+(?:,\d{2,3})*(?:\.\d{1,2})?|\d+(?:,\d{2,3})*(?:\.\d{1,2})?\s*"
        + CURRENCY_PATTERN
        + r"))",
        page_text,
    )
    if tot_match:
        prices = extract_prices_from_text(tot_match.group("snippet"))
        if prices:
            final_total = MoneyValue(
                amount=prices[0].amount,
                currency=prices[0].currency,
                kind=prices[0].kind,
                interval=prices[0].interval,
            )

    # 4. Explicit Fees & Taxes & Discounts
    explicit_fees: List[FeeItem] = []
    fee_patterns = [
        (
            r"(?i)\b(?P<name>shipping(?:\s+(?:&|and)\s+handling)?|delivery(?:\s+fee)?|freight|postage)\s*[:\-—]?\s*(?P<snippet>(?:"
            + CURRENCY_PATTERN
            + r"\s*\d+(?:,\d{2,3})*(?:\.\d{1,2})?|\d+(?:,\d{2,3})*(?:\.\d{1,2})?\s*"
            + CURRENCY_PATTERN
            + r"))",
            "Shipping & Delivery",
        ),
        (
            r"(?i)\b(?P<name>(?:estimated\s+)?(?:tax|taxes|sales\s+tax|gst(?:\s*\(\d+%\))?|vat(?:\s*\(\d+%\))?))\s*[:\-—]?\s*(?P<snippet>(?:"
            + CURRENCY_PATTERN
            + r"\s*\d+(?:,\d{2,3})*(?:\.\d{1,2})?|\d+(?:,\d{2,3})*(?:\.\d{1,2})?\s*"
            + CURRENCY_PATTERN
            + r"))",
            "Taxes",
        ),
        (
            r"(?i)\b(?P<name>(?:service|handling|convenience|processing|platform|booking|payment|transaction|bag|regulatory|environmental?|packaging|cleaning|resort|facility|destination|admin(?:istration)?|tip|gratuity)\s*(?:fee|charge)?)\s*[:\-—]?\s*(?P<snippet>(?:"
            + CURRENCY_PATTERN
            + r"\s*\d+(?:,\d{2,3})*(?:\.\d{1,2})?|\d+(?:,\d{2,3})*(?:\.\d{1,2})?\s*"
            + CURRENCY_PATTERN
            + r"))",
            "Fees",
        ),
        (
            r"(?i)\b(?P<name>discount|coupon|promo(?:\s+code)?|voucher|savings)\s*[:\-—]?\s*-?\s*(?P<snippet>(?:"
            + CURRENCY_PATTERN
            + r"\s*\d+(?:,\d{2,3})*(?:\.\d{1,2})?|\d+(?:,\d{2,3})*(?:\.\d{1,2})?\s*"
            + CURRENCY_PATTERN
            + r"))",
            "Discounts",
        ),
    ]

    seen_spans: List[Tuple[int, int]] = []
    if adv_match:
        seen_spans.append(adv_match.span())
    if sub_match:
        seen_spans.append(sub_match.span())
    if tot_match:
        seen_spans.append(tot_match.span())

    seen_fee_signatures: Set[Tuple[str, str, str]] = set()

    for pattern, category_label in fee_patterns:
        for m in re.finditer(pattern, page_text):
            span_start, span_end = m.span()
            if any(max(span_start, s_start) < min(span_end, s_end) for s_start, s_end in seen_spans):
                continue

            raw_name = m.group("name").strip()
            raw_snip = m.group("snippet").strip()
            p_list = extract_prices_from_text(raw_snip)
            if not p_list:
                continue

            p = p_list[0]
            is_discount = any(
                word in raw_name.lower() for word in ("discount", "coupon", "saving", "promo", "voucher")
            )
            amount_str = p.amount
            if is_discount and not amount_str.startswith("-"):
                amount_str = f"-{amount_str}"

            norm_name = re.sub(r"\s+", " ", raw_name.lower())
            sig = (norm_name, amount_str, p.currency)
            if sig in seen_fee_signatures:
                continue

            seen_spans.append((span_start, span_end))
            seen_fee_signatures.add(sig)

            explicit_fees.append(
                FeeItem(
                    name=raw_name.title(),
                    amount=MoneyValue(
                        amount=amount_str,
                        currency=p.currency,
                        kind=MoneyKind.FEE,
                        interval=p.interval,
                    ),
                    context=f"{category_label}: {m.group(0).strip()}",
                )
            )

    # Multi-quantity scenario: When advertised item price exists without subtotal
    if advertised_price and not checkout_subtotal and final_total:
        qty_match = re.search(
            r"(?i)\b(?:qty|quantity)\s*[:\-—]?\s*(\d+)\b|(?:\b(\d+)\s*(?:x|items?|units?)\b)",
            page_text,
        )
        if qty_match:
            try:
                qty_val = int(qty_match.group(1) or qty_match.group(2) or "1")
                if qty_val > 1:
                    adv_dec = Decimal(advertised_price.amount)
                    computed_subtotal = adv_dec * qty_val
                    checkout_subtotal = MoneyValue(
                        amount=str(computed_subtotal),
                        currency=advertised_price.currency,
                        kind=MoneyKind.ONE_TIME,
                    )
            except Exception:
                pass

    if not final_total and not (advertised_price and checkout_subtotal):
        return None

    points = [p for p in (advertised_price, checkout_subtotal, final_total) if p]
    if len(points) < 2 and not (final_total and explicit_fees):
        return None

    observations: List[PriceObservation] = []
    findings: List[Finding] = []

    if advertised_price:
        observations.append(
            PriceObservation(
                stage="advertised", amount=advertised_price, context="Advertised base price"
            )
        )
    if checkout_subtotal:
        observations.append(
            PriceObservation(
                stage="subtotal", amount=checkout_subtotal, context="Order subtotal before fees"
            )
        )
    for fee in explicit_fees:
        observations.append(
            PriceObservation(stage=fee.name.lower(), amount=fee.amount, context=fee.context)
        )
    if final_total:
        observations.append(
            PriceObservation(
                stage="total", amount=final_total, context="Final displayed checkout total"
            )
        )

    base = checkout_subtotal or advertised_price
    if not base or not final_total:
        # Scenario H: final total visible with explicit fees but no base subtotal.
        # We cannot compute an expected total, so return NOT_COMPARABLE rather than None
        # to preserve observations and avoid a silent no-result.
        if final_total and explicit_fees and not base:
            return (
                PriceIntegrity(
                    observations=observations,
                    difference=None,
                    reason=PriceIntegrityReason.NOT_COMPARABLE,
                    advertised_price=advertised_price,
                    checkout_subtotal=checkout_subtotal,
                    explicit_fees=explicit_fees,
                    final_total=final_total,
                    unexplained_difference=None,
                    note=(
                        "A final total and itemized fees were found but no base subtotal is present. "
                        "Cannot verify whether the total matches the disclosed components."
                    ),
                ),
                findings,
            )
        if advertised_price and checkout_subtotal:
            if advertised_price.currency != checkout_subtotal.currency:
                return (
                    PriceIntegrity(
                        observations=observations,
                        difference=None,
                        reason=PriceIntegrityReason.NOT_COMPARABLE,
                        advertised_price=advertised_price,
                        checkout_subtotal=checkout_subtotal,
                        explicit_fees=explicit_fees,
                        final_total=final_total,
                        unexplained_difference=None,
                    ),
                    findings,
                )
            adv_dec = Decimal(advertised_price.amount)
            sub_dec = Decimal(checkout_subtotal.amount)
            diff_dec = sub_dec - adv_dec
            diff_money = MoneyValue(
                amount=str(abs(diff_dec)),
                currency=advertised_price.currency,
                kind=MoneyKind.FEE if diff_dec > 0 else MoneyKind.ONE_TIME,
            )
            reason = PriceIntegrityReason.UNCLEAR if diff_dec > 0 else PriceIntegrityReason.KNOWN
            unexplained = diff_money if diff_dec > 0 else None
            return (
                PriceIntegrity(
                    observations=observations,
                    difference=diff_money,
                    reason=reason,
                    advertised_price=advertised_price,
                    checkout_subtotal=checkout_subtotal,
                    explicit_fees=explicit_fees,
                    final_total=final_total,
                    unexplained_difference=unexplained,
                ),
                findings,
            )
        return None

    # Currency match check across all components
    if base.currency != final_total.currency or any(fee.amount.currency != base.currency for fee in explicit_fees):
        return (
            PriceIntegrity(
                observations=observations,
                difference=None,
                reason=PriceIntegrityReason.NOT_COMPARABLE,
                advertised_price=advertised_price,
                checkout_subtotal=checkout_subtotal,
                explicit_fees=explicit_fees,
                final_total=final_total,
                unexplained_difference=None,
            ),
            findings,
        )

    # Billing intervals match check
    if base.interval and final_total.interval and base.interval != final_total.interval:
        return (
            PriceIntegrity(
                observations=observations,
                difference=None,
                reason=PriceIntegrityReason.NOT_COMPARABLE,
                advertised_price=advertised_price,
                checkout_subtotal=checkout_subtotal,
                explicit_fees=explicit_fees,
                final_total=final_total,
                unexplained_difference=None,
            ),
            findings,
        )

    # Decimal arithmetic calculation
    try:
        base_dec = Decimal(base.amount)
        total_dec = Decimal(final_total.amount)

        sum_fees_dec = Decimal(0)
        for fee in explicit_fees:
            fee_amt = Decimal(fee.amount.amount)
            sum_fees_dec += fee_amt

        expected_total_dec = base_dec + sum_fees_dec
        net_diff_dec = total_dec - base_dec
        difference_money = MoneyValue(
            amount=str(abs(net_diff_dec)),
            currency=base.currency,
            kind=MoneyKind.FEE if net_diff_dec > 0 else MoneyKind.ONE_TIME,
        )

        if total_dec == expected_total_dec:
            reason = (
                PriceIntegrityReason.DISCLOSED_TAX_OR_SHIPPING
                if explicit_fees
                else PriceIntegrityReason.KNOWN
            )
            return (
                PriceIntegrity(
                    observations=observations,
                    difference=difference_money,
                    reason=reason,
                    advertised_price=advertised_price,
                    checkout_subtotal=checkout_subtotal,
                    explicit_fees=explicit_fees,
                    final_total=final_total,
                    unexplained_difference=None,
                ),
                findings,
            )

        elif total_dec > expected_total_dec:
            unexplained_dec = total_dec - expected_total_dec
            unexplained_money = MoneyValue(
                amount=str(unexplained_dec),
                currency=base.currency,
                kind=MoneyKind.FEE,
            )
            reason = PriceIntegrityReason.UNCLEAR

            evidence_text = tot_match.group(0).strip() if tot_match else ""
            findings.append(
                Finding(
                    id="finding-unexplained-checkout-difference",
                    category=FindingCategory.ADDITIONAL_FEE,
                    severity=FindingSeverity.HIGH,
                    evidence_level=EvidenceLevel.EXPLICIT,
                    evidence_text=find_snippet_in_text(evidence_text, page_text),
                    explanation=f"Final checkout total ({final_total.currency} {final_total.amount}) exceeds base price plus disclosed adjustments ({base.currency} {expected_total_dec}) by an unexplained {base.currency} {unexplained_dec}.",
                    confidence=0.95,
                    missing_information=["Itemized disclosure for the additional charge amount"],
                    recommendation="Inspect payment breakdown or ask support to explain the extra charge before paying.",
                )
            )

            return (
                PriceIntegrity(
                    observations=observations,
                    difference=difference_money,
                    reason=reason,
                    advertised_price=advertised_price,
                    checkout_subtotal=checkout_subtotal,
                    explicit_fees=explicit_fees,
                    final_total=final_total,
                    unexplained_difference=unexplained_money,
                ),
                findings,
            )

        else:
            reason = PriceIntegrityReason.DISCLOSED_TAX_OR_SHIPPING
            return (
                PriceIntegrity(
                    observations=observations,
                    difference=difference_money,
                    reason=reason,
                    advertised_price=advertised_price,
                    checkout_subtotal=checkout_subtotal,
                    explicit_fees=explicit_fees,
                    final_total=final_total,
                    unexplained_difference=None,
                ),
                findings,
            )

    except (InvalidOperation, ValueError):
        return (
            PriceIntegrity(
                observations=observations,
                difference=None,
                reason=PriceIntegrityReason.UNCLEAR,
                advertised_price=advertised_price,
                checkout_subtotal=checkout_subtotal,
                explicit_fees=explicit_fees,
                final_total=final_total,
                unexplained_difference=None,
            ),
            findings,
        )


# ---------------------------------------------------------------------------
# Main Deterministic Analyzer Logic
# ---------------------------------------------------------------------------

def run_deterministic_analysis(
    page_title: str,
    page_url: str,
    page_text: str,
) -> DeterministicExtractionResult:
    """Run full deterministic extraction over the given page text and metadata.

    Preserves exact evidence substrings and strictly distinguishes:
    - Trials vs money-back guarantees
    - Due now vs future charges
    - Disclosed vs undisclosed terms (unknowns)
    - Plan-specific terms (Phase 3)
    - Checkout price comparison (Phase 3)
    """
    result = DeterministicExtractionResult()
    combined_text = f"{page_title}\n{page_text}"

    if not page_text or len(page_text.strip()) == 0:
        result.unknowns.append("No readable webpage text provided for analysis")
        return result

    # 1. Plan Extraction (Phase 3)
    plans = extract_plans_from_text(page_text)
    result.plans = plans

    # 2. Checkout Price Comparison (Phase 3)
    checkout_res = extract_checkout_price_comparison(page_text)
    if checkout_res:
        checkout_integrity, checkout_findings = checkout_res
        result.checkout_comparison = checkout_integrity
        result.findings.extend(checkout_findings)

    # 3. If multiple plans exist, populate page-level commitments and findings cleanly
    if len(plans) > 1:
        # Do not imply the first plan is selected. Page-level commitment map summarizes
        # shared/general terms only; plan-specific commitments are in result.plans.
        result.amount_due_now = None
        result.future_charge = None
        result.trial_duration = None
        result.future_charge_trigger = None

        # Check if all plans share the exact same billing interval
        intervals = {p.billing_interval for p in plans if p.billing_interval}
        result.billing_interval = intervals.pop() if len(intervals) == 1 else None

        # Check for global page-level cancellation policy
        cancellation = extract_cancellation_terms(page_text)
        if cancellation:
            result.cancellation_terms = cancellation.terms
            result.evidence_snippets.append(cancellation.raw_snippet)

        result.is_recurring = any(p.future_charge is not None for p in plans)

        for p in plans:
            if p.trial_duration and p.future_charge:
                ev = find_snippet_in_text(p.evidence_text, page_text) or find_snippet_in_text(p.plan_name, page_text)
                result.findings.append(
                    Finding(
                        id=f"finding-trial-{p.plan_name.lower().replace(' ', '-')}",
                        category=FindingCategory.FREE_TRIAL_CONVERSION,
                        severity=FindingSeverity.INFO,
                        evidence_level=EvidenceLevel.EXPLICIT,
                        evidence_text=ev,
                        explanation=f"{p.plan_name}: Free trial lasting {p.trial_duration} transitions to recurring charge of {p.future_charge.currency} {p.future_charge.amount} ({p.future_charge.interval or 'monthly'}).",
                        confidence=0.95,
                        missing_information=[],
                        recommendation="Set a calendar reminder before the trial ends if you do not wish to be billed automatically.",
                    )
                )
            elif p.trial_duration and not p.future_charge:
                ev = find_snippet_in_text(p.evidence_text, page_text) or find_snippet_in_text(p.plan_name, page_text)
                result.findings.append(
                    Finding(
                        id=f"finding-trial-no-renewal-{p.plan_name.lower().replace(' ', '-')}",
                        category=FindingCategory.FUTURE_CHARGE_DISCLOSURE,
                        severity=FindingSeverity.HIGH,
                        evidence_level=EvidenceLevel.EXPLICIT,
                        evidence_text=ev,
                        explanation=f"{p.plan_name} includes a {p.trial_duration} trial, but the renewal charge upon expiration is not stated.",
                        confidence=0.9,
                        missing_information=["Renewal price after trial expiration"],
                        recommendation="Verify the post-trial renewal amount before submitting payment details.",
                    )
                )

        plan_names_str = ", ".join(p.plan_name for p in plans)
        result.unknowns.append(
            f"Multiple pricing plans detected ({plan_names_str}). Plan selection has not been established; see plan breakdown for individual tier pricing and trial terms."
        )

        for p in plans:
            if p.is_ambiguous and p.ambiguity_reason:
                result.unknowns.append(f"Ambiguous terms for {p.plan_name}: {p.ambiguity_reason}")

        return result

    # 4. Single Plan or General Page Extraction
    extracted_prices = extract_prices_from_text(page_text)

    trial = extract_trial_terms(page_text)
    if trial:
        result.trial_duration = trial.duration_str
        result.evidence_snippets.append(trial.raw_snippet)

    cancellation = extract_cancellation_terms(page_text)
    if cancellation:
        result.cancellation_terms = cancellation.terms
        result.evidence_snippets.append(cancellation.raw_snippet)

    is_recurring, recurring_evidence = detect_recurring_signals(page_text)
    result.is_recurring = is_recurring
    if recurring_evidence:
        result.evidence_snippets.append(recurring_evidence)

    billing_interval = extract_billing_interval(page_text)
    if billing_interval:
        result.billing_interval = billing_interval

    then_match = re.search(r"then\s+(?P<snippet>" + CURRENCY_PATTERN + r"\s*\d+(?:\.\d{2})?)", page_text, re.IGNORECASE)

    recurring_prices = [p for p in extracted_prices if p.kind == MoneyKind.RECURRING or p.interval]
    trial_prices = [p for p in extracted_prices if p.kind == MoneyKind.TRIAL or p.amount in ("0", "0.0", "0.00")]
    one_time_prices = [p for p in extracted_prices if p.kind == MoneyKind.ONE_TIME and p.amount not in ("0", "0.0", "0.00")]

    monthly_prices = [p for p in extracted_prices if p.interval == "monthly"]
    distinct_monthly_amounts = {p.amount for p in monthly_prices}
    if len(distinct_monthly_amounts) > 1 and not then_match:
        conflict_msg = f"Multiple conflicting monthly prices found: {', '.join(sorted(distinct_monthly_amounts))}"
        result.conflicts_detected.append(conflict_msg)
        result.unknowns.append(conflict_msg)

    # Case A: Free trial exists
    if trial:
        # Amount due now is 0 (or trial price)
        curr = extracted_prices[0].currency if extracted_prices else "INR"
        result.amount_due_now = MoneyValue(
            amount="0",
            currency=curr,
            kind=MoneyKind.TRIAL,
            interval=None,
        )

        # Check for renewal price
        if recurring_prices:
            # Pick the price associated with renewal / then
            renewal = recurring_prices[-1]
            result.future_charge = MoneyValue(
                amount=renewal.amount,
                currency=renewal.currency,
                kind=MoneyKind.RECURRING,
                interval=renewal.interval or result.billing_interval or "monthly",
            )
            result.future_charge_trigger = f"After {result.trial_duration} trial ends"
            result.renewal_price = result.future_charge
        elif one_time_prices and then_match:
            # "then ₹999" where interval was parsed globally
            renewal_candidate = one_time_prices[-1]
            result.future_charge = MoneyValue(
                amount=renewal_candidate.amount,
                currency=renewal_candidate.currency,
                kind=MoneyKind.RECURRING,
                interval=result.billing_interval or "monthly",
            )
            result.future_charge_trigger = f"After {result.trial_duration} trial ends"
            result.renewal_price = result.future_charge
        else:
            # Trial exists but NO future charge disclosed!
            result.unknowns.append("Future renewal charge after trial is not disclosed in page text")
            result.findings.append(
                Finding(
                    id="finding-trial-undisclosed-renewal",
                    category=FindingCategory.FUTURE_CHARGE_DISCLOSURE,
                    severity=FindingSeverity.HIGH,
                    evidence_level=EvidenceLevel.EXPLICIT,
                    evidence_text=find_snippet_in_text(trial.raw_snippet, page_text),
                    explanation="A free trial is offered, but the regular price charged upon trial expiration is not clearly stated.",
                    confidence=0.9,
                    missing_information=["Renewal price after trial expiration", "Billing frequency after conversion"],
                    recommendation="Verify the post-trial renewal amount before submitting payment details.",
                )
            )

    # Case B: Recurring subscription without trial
    elif is_recurring or recurring_prices:
        if recurring_prices:
            primary_recurring = recurring_prices[0]
            # Check if there is an introductory price separate from renewal
            if len(recurring_prices) > 1 and recurring_prices[0].amount != recurring_prices[1].amount:
                intro = recurring_prices[0]
                renewal = recurring_prices[1]
                result.amount_due_now = MoneyValue(
                    amount=intro.amount,
                    currency=intro.currency,
                    kind=MoneyKind.RECURRING,
                    interval=intro.interval or result.billing_interval,
                )
                result.future_charge = MoneyValue(
                    amount=renewal.amount,
                    currency=renewal.currency,
                    kind=MoneyKind.RECURRING,
                    interval=renewal.interval or result.billing_interval,
                )
                result.introductory_price = result.amount_due_now
                result.renewal_price = result.future_charge
                result.future_charge_trigger = "Upon expiration of introductory discount period"
            else:
                result.amount_due_now = MoneyValue(
                    amount=primary_recurring.amount,
                    currency=primary_recurring.currency,
                    kind=MoneyKind.RECURRING,
                    interval=primary_recurring.interval or result.billing_interval,
                )
                result.future_charge = MoneyValue(
                    amount=primary_recurring.amount,
                    currency=primary_recurring.currency,
                    kind=MoneyKind.RECURRING,
                    interval=primary_recurring.interval or result.billing_interval,
                )
                result.future_charge_trigger = f"Renews every {result.billing_interval or 'billing period'} automatically"
        elif one_time_prices:
            # Price mentioned with recurring billing text
            p = one_time_prices[0]
            result.amount_due_now = MoneyValue(
                amount=p.amount,
                currency=p.currency,
                kind=MoneyKind.RECURRING,
                interval=result.billing_interval or "monthly",
            )
            result.future_charge = MoneyValue(
                amount=p.amount,
                currency=p.currency,
                kind=MoneyKind.RECURRING,
                interval=result.billing_interval or "monthly",
            )
            result.future_charge_trigger = f"Renews every {result.billing_interval or 'billing cycle'} automatically"
        else:
            # Recurring mentioned, but NO price stated anywhere!
            result.unknowns.append("Recurring billing is mentioned, but no explicit subscription price was found")
            if recurring_evidence:
                result.findings.append(
                    Finding(
                        id="finding-recurring-no-amount",
                        category=FindingCategory.RECURRING_PAYMENT,
                        severity=FindingSeverity.MEDIUM,
                        evidence_level=EvidenceLevel.EXPLICIT,
                        evidence_text=find_snippet_in_text(recurring_evidence, page_text),
                        explanation="Page text references automatic renewal or recurring payments, but the exact billing amount is not specified.",
                        confidence=0.85,
                        missing_information=["Specific recurring charge amount", "Currency of recurring charge"],
                        recommendation="Check the payment screen to confirm the exact recurring charge amount before paying.",
                    )
                )

    # Case C: One-time purchase
    elif one_time_prices:
        p = one_time_prices[0]
        result.amount_due_now = MoneyValue(
            amount=p.amount,
            currency=p.currency,
            kind=MoneyKind.ONE_TIME,
            interval=None,
        )

    # 6. Build Evidence-Backed Findings for identified commitments
    # Finding 1: Trial Conversion
    if trial and result.future_charge:
        ev = find_snippet_in_text(trial.raw_snippet, page_text)
        result.findings.append(
            Finding(
                id="finding-trial-conversion",
                category=FindingCategory.FREE_TRIAL_CONVERSION,
                severity=FindingSeverity.INFO,
                evidence_level=EvidenceLevel.EXPLICIT,
                evidence_text=ev,
                explanation=f"Free trial lasting {result.trial_duration} transitions to a recurring charge of {result.future_charge.currency} {result.future_charge.amount} ({result.future_charge.interval or 'monthly'}).",
                confidence=0.95,
                missing_information=[],
                recommendation="Set a calendar reminder before the trial ends if you do not wish to be billed automatically.",
            )
        )

    # Finding 2: Recurring Payment
    if is_recurring and result.future_charge and not trial:
        ev = find_snippet_in_text(recurring_evidence or "", page_text)
        result.findings.append(
            Finding(
                id="finding-recurring-payment",
                category=FindingCategory.RECURRING_PAYMENT,
                severity=FindingSeverity.INFO,
                evidence_level=EvidenceLevel.EXPLICIT,
                evidence_text=ev,
                explanation=f"Commitment includes automatic renewal at {result.future_charge.currency} {result.future_charge.amount} per {result.future_charge.interval or 'period'}.",
                confidence=0.9,
                missing_information=[],
                recommendation="Ensure you agree to ongoing automatic renewals and understand the cancellation method.",
            )
        )

    # Finding 3: Cancellation Deadline requirement
    if cancellation and cancellation.deadline:
        ev = find_snippet_in_text(cancellation.raw_snippet, page_text)
        result.findings.append(
            Finding(
                id="finding-cancellation-deadline",
                category=FindingCategory.CANCELLATION_REFUND_CLARITY,
                severity=FindingSeverity.LOW,
                evidence_level=EvidenceLevel.EXPLICIT,
                evidence_text=ev,
                explanation=f"Cancellation must be completed within a specific deadline: '{cancellation.deadline}'.",
                confidence=0.9,
                missing_information=[],
                recommendation="Ensure you cancel before the specified cutoff window to prevent an unwanted subsequent charge.",
            )
        )

    # 7. Record remaining unknowns
    if result.is_recurring or trial:
        if not result.cancellation_terms:
            result.unknowns.append("Cancellation deadline and instructions are not stated on this page")
        if not result.future_charge_trigger and result.future_charge:
            result.unknowns.append("Exact billing trigger date is not explicitly specified")
        if not result.billing_interval and result.future_charge:
            result.unknowns.append("Billing interval frequency is not explicitly defined")

    # Clean duplicates in unknowns while preserving order
    dedup_unknowns: List[str] = []
    seen: Set[str] = set()
    for u in result.unknowns:
        if u not in seen:
            seen.add(u)
            dedup_unknowns.append(u)
    result.unknowns = dedup_unknowns

    return result
