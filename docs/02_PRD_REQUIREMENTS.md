# 2. Product Requirements Document (PRD)

## Goal
Help a user make a more informed decision before paying by explaining visible financial commitments and unclear terms in the current page.

## User stories
1. As a user, I can click “Scan this page” so that the extension analyzes the page I am reviewing.
2. As a user, I can see the amount due now separately from future/recurring amounts.
3. As a user, I can see the exact text that supports each finding.
4. As a user, I can tell whether a claim is explicit, inferred, or unknown.
5. As a user, I can see what information is missing or unclear.
6. As a user, I can see a short “Ask Before You Pay” checklist.
7. As a user, I can see a price difference between stages only when the relevant stage values were actually observed.
8. As a user, I can review a transparent subscription without receiving an unsupported warning.
9. As a user, I can understand a result without needing to understand AI or machine learning.

## Functional requirements
### FR-1: User-triggered scan
The scan starts only after the user presses the scan action. No background surveillance or continuous page scanning in the MVP.

### FR-2: Page extraction
Extract visible text relevant to price, payment, subscription, trial, renewal, fees, cancellation, refund, and purchase terms. Keep a bounded excerpt. Avoid transmitting the full DOM, scripts, cookies, local storage, or unrelated page content.

### FR-3: Structured analysis
The backend returns schema-validated findings. Each finding includes category, severity, explanation, evidence text, confidence, and uncertainty or missing information where applicable.

### FR-4: Evidence validation
Every finding that claims page text as evidence must include a verbatim excerpt from the extracted text. Backend validation must reject or downgrade evidence that cannot be matched to the submitted text. The model must not invent quotes.

### FR-5: Financial Commitment Map
Show:
- Amount due now, if extracted.
- Future/recurring amount, if extracted.
- Billing interval and trial duration, if extracted.
- Trigger/date of future charge, if extracted.
- Cancellation/refund details, if extracted.
- Unknown or unclear terms.
Unknown values must be displayed as “Not found on this page” or equivalent, not guessed.

### FR-6: Deterministic calculations
Calculate totals only from structured, supported values. Use Python `Decimal` for money. Display assumptions and time horizon. If inputs are incomplete, show “Cannot calculate from available information.”

### FR-7: Price Integrity Trail
For MVP, compare only values actually observed from the scanned page or user-provided demo fixture. A single page scan cannot prove an earlier advertised price unless that value is also available. Distinguish disclosed taxes/shipping from unexplained price changes when the page gives enough evidence; otherwise say “difference observed; reason unclear.”

### FR-8: Ask Before You Pay
Generate a checklist from missing or ambiguous terms, for example:
- When does the trial end?
- What amount will be charged after the trial?
- How often will billing recur?
- How do I cancel?
- Are taxes or shipping added later?
Only include questions relevant to missing or uncertain information.

### FR-9: No unsupported accusation
Use calibrated wording such as “Potential concern,” “The page states…,” “Not found in the extracted text,” and “Verify before paying.” Do not call a merchant fraudulent based only on a page scan.

### FR-10: Errors and fallback
Show clear states for unsupported page, no relevant text, backend unavailable, analysis timeout, and invalid response. Do not silently substitute fabricated analysis.

## Non-functional requirements
- Explainability: every flagged finding has evidence or is clearly marked as a missing-information observation.
- Reliability: invalid model output must not crash the extension.
- Performance: target a useful result within 10 seconds under normal demo conditions; show progress while waiting.
- Privacy: user-triggered, minimal extraction, no default storage of page content or browsing history.
- Accessibility: readable contrast, clear headings, keyboard-accessible controls, no color-only status indicators.
- Maintainability: typed contracts, modular detection/calculation logic, automated tests.
- Safety: do not handle payment credentials or perform transactions.

## MVP success measures
Track on a curated evaluation set:
- Precision of flagged concerns.
- Recall for known demo concerns.
- Evidence-span match rate.
- Price extraction accuracy.
- Financial arithmetic correctness.
- False-positive rate on transparent subscriptions.
- User-rated usefulness from 5–10 test users.
- End-to-end latency and failure rate.

Do not claim production-grade accuracy from a tiny demo set.
