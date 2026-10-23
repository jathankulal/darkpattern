# 6. UI/UX Specification

## Main interaction
1. User clicks the extension icon.
2. Popup shows a clear action: “Scan this page.”
3. Loading state explains that only relevant visible text is being checked.
4. Results appear with a short summary and transparent evidence.
5. User can expand each finding to see the quote, explanation, confidence/uncertainty, and recommended check.

## Results information hierarchy
### A. Financial Commitment Map
Prominently show:
- Pay now
- Pay later / recurring amount
- Trial end or future charge trigger
- Billing interval
- Cancellation/refund terms
- Unknowns

Unknown values should never be represented as zero. Use “Not found on this page.”

### B. Findings
Each finding should show:
- Plain-language title/category
- Neutral severity label
- Evidence snippet, visually distinguished
- Why it matters financially
- Whether explicit or inferred
- What to verify next

Do not show a red warning solely because a subscription exists.

### C. Price Integrity Trail
When comparable observations exist, show stages and values in order. If there is no earlier-stage evidence, state that a comparison is unavailable. Do not fabricate an advertised price.

### D. Ask Before You Pay
Show a short, relevant checklist based on missing or ambiguous information. Avoid generic checklist items when not relevant.

## Tone and visual behavior
- Clear, calm, non-accusatory.
- Prefer “Potential concern” over “Scam detected.”
- Explain technical terms in everyday language.
- Never rely on color alone; pair color with text/icon/label.
- Distinguish fact, inference, and unknown.
- Avoid a single unvalidated overall score.

## Required states
- Idle / ready to scan.
- Extracting/analyzing.
- Successful results.
- Partial result.
- Unsupported page or no relevant text.
- Backend unavailable or configuration missing.
- Invalid response / recoverable failure.

## Accessibility
- Keyboard-operable controls.
- Visible focus.
- Readable text size and contrast.
- Semantic headings and labels.
- Screen-reader-friendly status messages.
