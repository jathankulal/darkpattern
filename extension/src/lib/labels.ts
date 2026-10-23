/**
 * Human-readable labels for FindingCategory values.
 * Kept in a separate file so it can be imported by both components and tests.
 */
import type { FindingCategory, FindingSeverity, EvidenceLevel, ErrorCode } from '../types/api';

export const CATEGORY_LABELS: Record<FindingCategory, string> = {
  recurring_payment: 'Recurring Payment',
  free_trial_conversion: 'Free Trial Conversion',
  future_charge_disclosure: 'Future Charge',
  additional_fee: 'Additional Fee',
  cancellation_refund_clarity: 'Cancellation / Refund Terms',
  urgency_pressure: 'Urgency or Pressure Language',
  missing_commitment_info: 'Missing Commitment Information',
};

export const SEVERITY_LABELS: Record<FindingSeverity, string> = {
  info: 'Info',
  low: 'Low',
  medium: 'Medium',
  high: 'High',
};

export const EVIDENCE_LEVEL_LABELS: Record<EvidenceLevel, string> = {
  explicit: 'Explicitly stated on page',
  inferred: 'Inferred from context',
  unknown: 'Not found in extracted text',
};

/** User-facing messages for each error code (docs/02_PRD FR-10, docs/06_UI_UX_SPEC §Required states). */
export const ERROR_MESSAGES: Record<ErrorCode, string> = {
  unsupported_page:
    'This page type is not supported for analysis. Try navigating to a checkout or subscription page.',
  no_relevant_text:
    'No financial commitment terms were found on this page. This may not be a purchase or subscription page.',
  backend_unavailable:
    'Cannot connect to the analysis backend. Make sure the backend is running on the configured address.',
  analysis_timeout:
    'The analysis took too long to complete. Please try again.',
  invalid_model_output:
    'The backend returned an unexpected response. Please try again or report this issue.',
  configuration_missing:
    'The backend is not fully configured. An API key may be missing.',
  internal_error:
    'The backend encountered an internal error. Please try again.',
};
