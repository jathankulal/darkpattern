# 11. Decision Log

## Approved decisions
| ID | Decision | Reason |
|---|---|---|
| D-001 | Product is a pre-purchase financial commitment explainer. | Keeps scope specific and user value clear. |
| D-002 | Scan is user-triggered. | Privacy and user control. |
| D-003 | Financial Commitment Map is the flagship feature. | Directly answers the core product question. |
| D-004 | Price Integrity Trail is limited to observed comparable prices. | Prevents invented historical prices. |
| D-005 | Ask Before You Pay checklist is derived from missing/unclear terms. | Converts analysis into action. |
| D-006 | LLM does not calculate money. | Reproducibility and correctness. |
| D-007 | Evidence must match extracted text. | Prevents hallucinated quotations. |
| D-008 | No composite Clarity Score in MVP. | Avoids arbitrary/unvalidated scoring. |
| D-009 | No automatic purchase blocking or transaction action. | Keeps the user in control. |
| D-010 | No database required for MVP. | Reduces complexity and privacy risk. |

## Open decisions — resolve before the relevant phase
- O-001: Which hosted LLM provider/model will be used?
- O-002: Which deployment target will host FastAPI, if remote deployment is needed?
- O-003: Which currencies are required for the demo? Do not assume currency automatically.
- O-004: Is the demo limited to English initially?
- O-005: What exact maximum page-text length and API request size will be used?
- O-006: Which extension permissions are strictly required after the first scaffold?
- O-007: Will the hackathon demo use synthetic pages, public pages, or both?

## Change process
When a decision changes:
1. Add a new decision ID; do not silently rewrite history.
2. Explain why the change is necessary.
3. List impacted docs, code, tests, and risks.
4. Get user approval before changing an approved decision.
5. Update this log and affected documents together.
