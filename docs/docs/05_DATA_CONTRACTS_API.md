# 5. Data Contracts and API

## API versioning
Initial local API may use `/api/v1/analyze`. If the implementation scaffolding requires a different prefix, document the decision and keep it consistent across client, tests, and docs.

## Analyze request — conceptual contract
```json
{
  "page_title": "string",
  "page_url": "string",
  "page_text": "string",
  "scan_id": "optional opaque identifier",
  "locale": "optional language code"
}
```

Constraints:
- `page_text` is bounded by a documented maximum length.
- No cookies, local storage, form values, payment credentials, passwords, or full DOM.
- URL should be included only as needed; strip query parameters and fragments by default if not necessary.
- Treat every input field as untrusted.

## Analyze response — conceptual contract
```json
{
  "status": "ok | partial | error",
  "summary": "plain-language summary",
  "findings": [
    {
      "id": "stable request-local identifier",
      "category": "approved category",
      "severity": "info | low | medium | high",
      "evidence_level": "explicit | inferred | unknown",
      "evidence_text": "verbatim snippet or empty only for missing-information observations",
      "explanation": "plain-language explanation",
      "confidence": 0.0,
      "missing_information": ["string"],
      "recommendation": "string"
    }
  ],
  "commitment_map": {
    "amount_due_now": "optional structured money value",
    "future_charge": "optional structured money value",
    "billing_interval": "optional string",
    "trial_duration": "optional string",
    "future_charge_trigger": "optional string",
    "cancellation_terms": "optional string",
    "unknowns": ["string"]
  },
  "price_integrity": {
    "observations": [],
    "difference": "optional structured money value",
    "reason": "known | disclosed_tax_or_shipping | unclear | not_comparable"
  },
  "checklist": ["string"],
  "limitations": ["string"]
}
```

The JSON above is a conceptual example, not final implementation code. Use Pydantic models with explicit enums and field constraints. Avoid arbitrary free-form schema expansion from the LLM.

## Money value
Represent monetary values as structured data, for example:
```json
{
  "amount": "9.99",
  "currency": "USD",
  "kind": "one_time | recurring | trial | fee",
  "interval": "monthly"
}
```
`amount` should be a decimal string. Use a supported currency code when identifiable. Do not silently assume a currency based only on user location.

## Validation rules
- Reject unknown category/severity/evidence-level values or map them through an explicit safe fallback.
- Confidence must be between 0 and 1.
- Evidence must be found verbatim in the request text; otherwise remove the quote and mark the finding as unsupported/unknown or discard the finding.
- Limit array lengths and string sizes.
- Validate all money values before calculation.
- Use structured error responses without exposing secrets, stack traces, or raw provider payloads.

## Error states
- `unsupported_page`
- `no_relevant_text`
- `backend_unavailable`
- `analysis_timeout`
- `invalid_model_output`
- `configuration_missing`
- `internal_error`

Exact enum names may be adapted during implementation, but the UI must distinguish user-actionable errors from internal failures.
