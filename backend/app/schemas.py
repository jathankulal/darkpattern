"""Pydantic schemas and data contracts for Dark Pattern Guardian API."""

from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import List, Literal, Optional
from urllib.parse import urlparse, urlunparse
from pydantic import BaseModel, Field, field_validator


class AnalyzeStatus(str, Enum):
    OK = "ok"
    PARTIAL = "partial"
    ERROR = "error"


class FindingSeverity(str, Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class EvidenceLevel(str, Enum):
    EXPLICIT = "explicit"
    INFERRED = "inferred"
    UNKNOWN = "unknown"


class FindingCategory(str, Enum):
    """Approved detection categories for MVP — from docs/04_DETECTION_AND_FINANCIAL_LOGIC.md.

    Do not add new categories without a decision-log entry and approval.
    """

    RECURRING_PAYMENT = "recurring_payment"
    """Recurring obligation is present or suggested."""

    FREE_TRIAL_CONVERSION = "free_trial_conversion"
    """A trial transitions to a paid plan, if supported by text."""

    FUTURE_CHARGE_DISCLOSURE = "future_charge_disclosure"
    """Future amount, timing, or trigger is missing, ambiguous, or identifiable."""

    ADDITIONAL_FEE = "additional_fee"
    """Extra charge or a price difference between observed checkout stages."""

    CANCELLATION_REFUND_CLARITY = "cancellation_refund_clarity"
    """Cancellation/refund terms are stated, unclear, or absent in the text."""

    URGENCY_PRESSURE = "urgency_pressure"
    """Language that may pressure the user — only when exact evidence is present."""

    MISSING_COMMITMENT_INFO = "missing_commitment_info"
    """Relevant amount, interval, renewal date, or cancellation terms are absent."""


class MoneyKind(str, Enum):
    ONE_TIME = "one_time"
    RECURRING = "recurring"
    TRIAL = "trial"
    FEE = "fee"


class PriceIntegrityReason(str, Enum):
    KNOWN = "known"
    DISCLOSED_TAX_OR_SHIPPING = "disclosed_tax_or_shipping"
    UNCLEAR = "unclear"
    NOT_COMPARABLE = "not_comparable"


class ErrorCode(str, Enum):
    UNSUPPORTED_PAGE = "unsupported_page"
    NO_RELEVANT_TEXT = "no_relevant_text"
    BACKEND_UNAVAILABLE = "backend_unavailable"
    ANALYSIS_TIMEOUT = "analysis_timeout"
    INVALID_MODEL_OUTPUT = "invalid_model_output"
    CONFIGURATION_MISSING = "configuration_missing"
    INTERNAL_ERROR = "internal_error"


class MoneyValue(BaseModel):
    """Structured representation of monetary values."""

    amount: str = Field(description="Decimal string representation of amount (may be negative for refunds)")
    # max_length=10 accepts ISO 4217 codes (3 chars) plus common variants/symbols up to 10 chars.
    # Reject arbitrary long strings while leaving room for currency codes like 'XBT' or 'USD'.
    currency: str = Field(
        max_length=10,
        description="Currency code or symbol, max 10 characters (e.g. USD, EUR, GBP)",
    )
    kind: MoneyKind = Field(description="Category of charge")
    interval: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Billing interval if recurring, e.g. monthly",
    )

    @field_validator("amount")
    @classmethod
    def validate_amount_decimal(cls, v: str) -> str:
        """Reject non-decimal strings and non-finite values (NaN, Infinity, -Infinity)."""
        try:
            val = Decimal(v)
            if not val.is_finite():
                raise ValueError("Amount must be a finite decimal (NaN and Infinity are not allowed)")
        except InvalidOperation:
            raise ValueError(f"Amount '{v}' is not a valid decimal string")
        return str(val)


# ---------------------------------------------------------------------------
# String and list length caps
# ---------------------------------------------------------------------------
# These limits are not numerically specified in docs/05_DATA_CONTRACTS_API.md
# (open decision O-005). The values below are the smallest reasonable choices
# that prevent memory/bandwidth abuse while accommodating realistic outputs:
#   - Finding text fields: 2 000 chars — sufficient for a paragraph of explanation.
#   - evidence_text: 1 000 chars — verbatim page snippet; very long evidence is
#     a signal the LLM invented rather than extracted.
#   - finding ID: 100 chars — opaque identifier.
#   - checklist / limitations items: 500 chars each.
#   - Array lengths: 20 findings, 10 unknowns, 20 checklist, 20 limitations.
# Propose changes in the decision log if these need adjustment.

_MAX_FINDING_TEXT = 2_000
_MAX_EVIDENCE_TEXT = 1_000
_MAX_ID_LEN = 100
_MAX_ITEM_TEXT = 500
_MAX_FINDINGS = 20
_MAX_UNKNOWNS = 10
_MAX_LIST_ITEMS = 20


class Finding(BaseModel):
    """Specific observation of potential dark pattern or commitment term."""

    id: str = Field(max_length=_MAX_ID_LEN, description="Stable request-local identifier")
    # Enum-validated: only the 7 approved MVP categories are accepted.
    category: FindingCategory = Field(description="Approved taxonomy category")
    severity: FindingSeverity = Field(description="Severity triage level")
    evidence_level: EvidenceLevel = Field(description="Level of evidential grounding")
    evidence_text: str = Field(
        default="",
        max_length=_MAX_EVIDENCE_TEXT,
        description="Verbatim snippet or empty only for missing-information observations",
    )
    explanation: str = Field(
        max_length=_MAX_FINDING_TEXT,
        description="Plain-language explanation of finding",
    )
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score between 0.0 and 1.0")
    missing_information: List[str] = Field(
        default_factory=list,
        max_length=_MAX_UNKNOWNS,
        description="List of undisclosed relevant terms (max 10 items)",
    )
    recommendation: str = Field(
        max_length=_MAX_FINDING_TEXT,
        description="Actionable user recommendation",
    )

    @field_validator("missing_information", mode="before")
    @classmethod
    def cap_missing_information_items(cls, v: list) -> list:
        """Truncate individual missing_information strings to _MAX_ITEM_TEXT chars."""
        if isinstance(v, list):
            return [str(item)[:_MAX_ITEM_TEXT] for item in v]
        return v


class CommitmentMap(BaseModel):
    """Summary of financial obligations and recurring billing terms."""

    amount_due_now: Optional[MoneyValue] = Field(default=None, description="Amount payable immediately")
    future_charge: Optional[MoneyValue] = Field(default=None, description="Anticipated subsequent charge")
    billing_interval: Optional[str] = Field(
        default=None, max_length=_MAX_ITEM_TEXT, description="Frequency of recurring charge"
    )
    trial_duration: Optional[str] = Field(
        default=None, max_length=_MAX_ITEM_TEXT, description="Length of trial period"
    )
    future_charge_trigger: Optional[str] = Field(
        default=None, max_length=_MAX_ITEM_TEXT, description="Condition triggering future charge"
    )
    cancellation_terms: Optional[str] = Field(
        default=None, max_length=_MAX_ITEM_TEXT, description="Disclosed cancellation policy"
    )
    unknowns: List[str] = Field(
        default_factory=list,
        max_length=_MAX_UNKNOWNS,
        description="Missing or ambiguous terms (max 10 items)",
    )


class FeeItem(BaseModel):
    """Explicitly stated fee, tax, shipping, or discount."""

    name: str = Field(max_length=100, description="Fee name or label, e.g. 'Shipping', 'Tax', 'Service fee'")
    amount: MoneyValue = Field(description="Structured monetary value of the fee")
    context: Optional[str] = Field(default=None, max_length=_MAX_ITEM_TEXT, description="Contextual explanation or rate")


class PlanSummary(BaseModel):
    """Financial terms specific to an individual pricing plan or product option."""

    plan_name: str = Field(max_length=100, description="Name of the plan, tier, or product")
    amount_due_now: Optional[MoneyValue] = Field(default=None, description="Initial charge for this plan")
    future_charge: Optional[MoneyValue] = Field(default=None, description="Subsequent recurring charge for this plan")
    billing_interval: Optional[str] = Field(
        default=None, max_length=_MAX_ITEM_TEXT, description="Billing frequency (monthly, annually)"
    )
    trial_duration: Optional[str] = Field(
        default=None, max_length=_MAX_ITEM_TEXT, description="Trial duration specific to this plan"
    )
    future_charge_trigger: Optional[str] = Field(
        default=None, max_length=_MAX_ITEM_TEXT, description="Condition triggering future charge"
    )
    cancellation_terms: Optional[str] = Field(
        default=None, max_length=_MAX_ITEM_TEXT, description="Plan cancellation terms"
    )
    unknowns: List[str] = Field(
        default_factory=list,
        max_length=_MAX_UNKNOWNS,
        description="Missing or ambiguous terms for this plan",
    )
    is_ambiguous: bool = Field(
        default=False, description="True if plan terms or associations are ambiguous"
    )
    ambiguity_reason: Optional[str] = Field(
        default=None, max_length=_MAX_ITEM_TEXT, description="Reason for ambiguity if any"
    )
    evidence_text: str = Field(
        default="", max_length=_MAX_EVIDENCE_TEXT, description="Verbatim page text for this plan"
    )


class PriceObservation(BaseModel):
    """Individual price recorded at a specific checkout stage."""

    stage: str = Field(description="Checkout stage or source identifier")
    amount: MoneyValue = Field(description="Observed price")
    context: Optional[str] = Field(default=None, description="Contextual note or disclosure")


class PriceIntegrity(BaseModel):
    """Price Integrity Trail comparison across stages."""

    observations: List[PriceObservation] = Field(
        default_factory=list, description="Observed price stages"
    )
    difference: Optional[MoneyValue] = Field(
        default=None,
        description="Total computed difference between baseline stage/subtotal and final stage/total (e.g. final_total - checkout_subtotal, or renewal - introductory)",
    )
    reason: PriceIntegrityReason = Field(
        description="Explanation or classification for price difference"
    )
    advertised_price: Optional[MoneyValue] = Field(
        default=None, description="Advertised base price or item price"
    )
    checkout_subtotal: Optional[MoneyValue] = Field(
        default=None, description="Checkout subtotal before additional fees"
    )
    explicit_fees: List[FeeItem] = Field(
        default_factory=list, description="Explicitly disclosed fees, taxes, shipping, discounts, etc."
    )
    final_total: Optional[MoneyValue] = Field(
        default=None, description="Final displayed total amount"
    )
    unexplained_difference: Optional[MoneyValue] = Field(
        default=None,
        description="Unexplained discrepancy when final total exceeds base/subtotal plus disclosed adjustments (final_total - (subtotal + sum(fees)))",
    )
    note: Optional[str] = Field(
        default=None,
        description="Human-readable note explaining why a comparison result is NOT_COMPARABLE or incomplete",
    )


def strip_url_sensitive_parts(url: str) -> str:
    """Remove query parameters and fragments from a URL.

    Required by docs/05_DATA_CONTRACTS_API.md and docs/07_PRIVACY_SECURITY.md:
      'Strip URL query parameters and fragments by default unless there is a
       documented reason to retain them.'

    The stripped URL is used for analysis context only. The original URL is
    never logged or retained beyond this function call.
    """
    try:
        parsed = urlparse(url)
        # Rebuild with scheme, netloc, path only — drop query and fragment.
        stripped = urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))
        return stripped
    except Exception:
        # If parsing fails, return the original string unchanged rather than
        # raising here; the max_length validator will still apply.
        return url


class AnalyzeRequest(BaseModel):
    """Inbound request from Chrome extension."""

    page_title: str = Field(max_length=500, description="Page title")
    page_url: str = Field(
        max_length=2048,
        description="Page URL; query parameters and fragments are stripped server-side",
    )
    page_text: str = Field(max_length=50000, description="Bounded extracted text content")
    scan_id: Optional[str] = Field(
        default=None, max_length=128, description="Optional opaque request identifier"
    )
    locale: Optional[str] = Field(
        default=None, max_length=35, description="Optional BCP-47 language tag, e.g. en-US"
    )

    @field_validator("page_url", mode="before")
    @classmethod
    def strip_url(cls, v: str) -> str:
        """Strip query parameters and fragments from page_url before validation."""
        if isinstance(v, str):
            return strip_url_sensitive_parts(v)
        return v


class AnalyzeResponse(BaseModel):
    """Standardized analysis output contract."""

    status: AnalyzeStatus = Field(description="Execution status")
    summary: str = Field(
        max_length=_MAX_FINDING_TEXT,
        description="Plain-language overview of commitments and findings",
    )
    findings: List[Finding] = Field(
        default_factory=list,
        max_length=_MAX_FINDINGS,
        description="List of identified findings (max 20)",
    )
    commitment_map: CommitmentMap = Field(description="Structured financial commitment mapping")
    plans: List[PlanSummary] = Field(
        default_factory=list,
        max_length=10,
        description="Plan-specific commitment breakdown when multiple plans are present",
    )
    price_integrity: PriceIntegrity = Field(description="Price comparison and disclosure trail")
    checklist: List[str] = Field(
        default_factory=list,
        max_length=_MAX_LIST_ITEMS,
        description="Actionable checklist before paying (max 20 items)",
    )
    limitations: List[str] = Field(
        default_factory=list,
        max_length=_MAX_LIST_ITEMS,
        description="Disclosures regarding analysis boundaries (max 20 items)",
    )


class HealthResponse(BaseModel):
    """Health check response schema."""

    status: Literal["ok"] = "ok"
    llm_configured: bool = False
    environment: str = "development"
    version: str = "0.1.0"


class ErrorDetail(BaseModel):
    """Structured error payload."""

    code: ErrorCode
    message: str
    details: Optional[dict] = None


class ErrorResponse(BaseModel):
    """Standard error response format."""

    status: Literal["error"] = "error"
    error: ErrorDetail
