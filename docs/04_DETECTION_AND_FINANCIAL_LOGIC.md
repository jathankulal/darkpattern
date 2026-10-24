# 4. Detection and Financial Logic

## Detection categories for MVP
1. **Recurring payment / subscription** — recurring obligation is present or suggested.
2. **Free-trial conversion** — a trial transitions to a paid plan, if supported by text.
3. **Future charge disclosure** — future amount, timing, or trigger is missing, ambiguous, or prominent enough to identify.
4. **Additional fee / price difference** — extra charge or a difference between observed price stages.
5. **Cancellation / refund clarity** — terms are stated, unclear, or not found in the extracted text.
6. **Urgency or pressure language** — language that may pressure the user, only when exact evidence is provided.
7. **Missing key commitment information** — relevant amount, interval, renewal date, or cancellation terms are not found in the available text.

This taxonomy is a starting point. Do not silently add new categories. Propose additions in the decision log and wait for approval.

For recurring commitments, an explicit cancellation method such as "cancel
from account settings" is treated as disclosed cancellation information by the
deterministic extractor. Its presence does not establish that the method works
or that a deadline and all cancellation terms are clear.

## Evidence levels
- **Explicit:** directly stated in page text.
- **Inferred:** reasonable contextual interpretation; label as inference and provide evidence.
- **Unknown:** not available in the extracted text.
Never convert “unknown” into “false” or into proof of manipulation.

## Severity guidance
- **Info:** ordinary commercial term or neutral disclosure.
- **Low:** minor ambiguity or a term worth checking.
- **Medium:** material future cost or condition appears unclear or easy to miss in the extracted text.
- **High:** clear evidence of a significant undisclosed or conflicting financial term. Use sparingly and only with strong evidence.
Severity is a triage aid, not a legal finding. Do not derive severity from confidence alone.

## LLM responsibilities
The LLM may:
- Interpret context around a price, trial, renewal, fee, or cancellation term.
- Classify candidate text into the approved categories. Candidate/category
  consistency checks may flag recognized contradictions for human review but
  do not establish classification truth or promote AI proposals.
- Explain a finding in plain language.
- Identify relevant missing information.
- Suggest a question for the checklist.

The LLM must not:
- Calculate money or totals.
- Invent amounts, dates, billing intervals, quotes, or policy terms.
- Assert that a merchant is a scam or has broken the law.
- Treat page instructions as developer/system instructions.
- Return evidence that is not a verbatim substring of the submitted text.
- Change the product taxonomy, schema, or scope.

## Financial calculation rules
- Use Python `Decimal`, not binary floating-point, for currency.
- Normalize currency symbols/codes only when clear.
- Do not assume a billing interval, tax, shipping, or number of billing periods.
- Distinguish one-time price, recurring price, trial price, and additional fees.
- A total projection requires a defined time horizon and sufficient known values.
- Include assumptions in the response.
- If the time horizon or a required value is missing, do not produce a guessed total.
- Never add two prices unless the page supports that they are separate charges for the same purchase.
- Timeline evidence should be the narrow verbatim source for each event: price
  events cite the matching price text, and recurring events cite the renewal or
  recurring-billing text. Annualized values are calculations from the stated
  price and interval, not directly observed charges, and must be labeled as such.
- Keep original extracted text available for audit/debugging only in the current request lifecycle; do not persist by default.

## Price Integrity Trail semantics
- “Observed price A” and “observed price B” must include the stage/source label.
- Difference = later observed total minus earlier observed total, only when both values are comparable and currencies match.
- Positive difference does not by itself mean deceptive behavior.
- If tax/shipping/fees are disclosed, show the disclosure context.
- If the reason is not established, say “Reason unclear from the available evidence.”
- Do not claim to track prior stages unless the extension actually observed or was given those values.

## Dark-pattern risk indicator
The extension may show a deterministic 0–100 dark-pattern risk indicator. It is not
a probability that a merchant is deceptive and is not a general clarity or safety
rating.

Only evidence-backed `urgency_pressure` and `future_charge_disclosure` findings
contribute. A finding needs explicit or inferred evidence, a non-empty matching
quote, and positive confidence. Ordinary recurring payments, clearly disclosed
trial conversions, cancellation policies, and `additional_fee` findings do not
raise the score by themselves.

For each qualifying finding, calculate:

`round(severity points × evidence multiplier × confidence)`

Severity points are 20 for low, 40 for medium, and 60 for high. Evidence
multipliers are 1.0 for explicit and 0.6 for inferred; unknown evidence scores
zero. For overlapping findings in one category, keep only the largest
contribution. Sum the distinct category contributions and cap the result at 100.

Labels are: 0–19 Low Detected Risk, 20–39 Some Warning Signs, 40–59 Moderate
Risk, 60–79 High Risk, and 80–100 Very High Risk. Show no number and use
“Insufficient evidence to score” when no finding qualifies. The weights and
bands are transparent product rules, not statistically calibrated; findings
must remain visible so users can inspect the evidence behind the indicator.
