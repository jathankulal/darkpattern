/**
 * API types for Dark Pattern Guardian extension.
 *
 * These types mirror the Pydantic models in backend/app/schemas.py exactly.
 * Do not add extra fields here without updating the backend contract first.
 * Do not add logic — types only.
 */

// ---------------------------------------------------------------------------
// Enums (mirroring Python str enums as TypeScript literal union types)
// ---------------------------------------------------------------------------

export type AnalyzeStatus = 'ok' | 'partial' | 'error';

export type FindingSeverity = 'info' | 'low' | 'medium' | 'high';

export type EvidenceLevel = 'explicit' | 'inferred' | 'unknown';

/**
 * Approved MVP detection categories — from docs/04_DETECTION_AND_FINANCIAL_LOGIC.md.
 * Must stay in sync with backend FindingCategory enum.
 * Do not add new values without a decision-log entry and approval.
 */
export type FindingCategory =
  | 'recurring_payment'
  | 'free_trial_conversion'
  | 'future_charge_disclosure'
  | 'additional_fee'
  | 'cancellation_refund_clarity'
  | 'urgency_pressure'
  | 'missing_commitment_info';

export type MoneyKind = 'one_time' | 'recurring' | 'trial' | 'fee';

export type PriceIntegrityReason =
  | 'known'
  | 'disclosed_tax_or_shipping'
  | 'unclear'
  | 'not_comparable';

export type ErrorCode =
  | 'unsupported_page'
  | 'no_relevant_text'
  | 'backend_unavailable'
  | 'analysis_timeout'
  | 'invalid_model_output'
  | 'configuration_missing'
  | 'internal_error';

// ---------------------------------------------------------------------------
// Interfaces (mirroring Pydantic BaseModel classes)
// ---------------------------------------------------------------------------

export interface MoneyValue {
  /** Decimal string, e.g. "19.99". May be negative for refunds. */
  amount: string;
  /** Currency code, max 10 chars, e.g. "USD". */
  currency: string;
  kind: MoneyKind;
  /** Billing interval if recurring, e.g. "monthly". */
  interval?: string;
}

export interface Finding {
  /** Stable request-local identifier. */
  id: string;
  category: FindingCategory;
  severity: FindingSeverity;
  evidence_level: EvidenceLevel;
  /** Verbatim snippet from page text, or empty string for missing-info findings. */
  evidence_text: string;
  explanation: string;
  /** Confidence between 0.0 and 1.0. */
  confidence: number;
  missing_information: string[];
  recommendation: string;
}

export interface CommitmentMap {
  /** null/undefined means "not found on this page" — never render as zero. */
  amount_due_now?: MoneyValue | null;
  future_charge?: MoneyValue | null;
  billing_interval?: string | null;
  trial_duration?: string | null;
  future_charge_trigger?: string | null;
  cancellation_terms?: string | null;
  unknowns: string[];
}

export interface PlanSummary {
  plan_name: string;
  amount_due_now?: MoneyValue | null;
  future_charge?: MoneyValue | null;
  billing_interval?: string | null;
  trial_duration?: string | null;
  future_charge_trigger?: string | null;
  cancellation_terms?: string | null;
  unknowns: string[];
  is_ambiguous: boolean;
  ambiguity_reason?: string | null;
  evidence_text: string;
}

export interface FeeItem {
  name: string;
  amount: MoneyValue;
  context?: string | null;
}

export interface PriceObservation {
  stage: string;
  amount: MoneyValue;
  context?: string;
}

export interface PriceIntegrity {
  observations: PriceObservation[];
  /** Total computed difference between baseline stage/subtotal and final stage/total (e.g. final_total - checkout_subtotal). */
  difference?: MoneyValue | null;
  reason: PriceIntegrityReason;
  advertised_price?: MoneyValue | null;
  checkout_subtotal?: MoneyValue | null;
  explicit_fees?: FeeItem[];
  final_total?: MoneyValue | null;
  /** Unexplained discrepancy when final total exceeds base/subtotal plus disclosed adjustments. */
  unexplained_difference?: MoneyValue | null;
  /** Human-readable note explaining why a comparison result is NOT_COMPARABLE or incomplete. */
  note?: string | null;
}

export interface AnalyzeRequest {
  page_title: string;
  /** Page URL — query params and fragments are stripped server-side. */
  page_url: string;
  page_text: string;
  scan_id?: string;
  locale?: string;
}

export interface AnalyzeResponse {
  status: AnalyzeStatus;
  summary: string;
  findings: Finding[];
  commitment_map: CommitmentMap;
  plans?: PlanSummary[];
  price_integrity: PriceIntegrity;
  checklist: string[];
  limitations: string[];
}

export interface HealthResponse {
  status: 'ok';
  llm_configured: boolean;
  environment: string;
  version: string;
}

export interface ErrorDetail {
  code: ErrorCode;
  message: string;
  details?: Record<string, unknown>;
}

export interface ErrorResponse {
  status: 'error';
  error: ErrorDetail;
}
