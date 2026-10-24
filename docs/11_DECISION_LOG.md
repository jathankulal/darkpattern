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
| D-008 | No composite Clarity Score in MVP. | Avoids arbitrary/unvalidated scoring. Superseded for the bounded evidence-based risk indicator by D-017; this does not authorize a calibrated probability or general safety/clarity rating. |
| D-009 | No automatic purchase blocking or transaction action. | Keeps the user in control. |
| D-010 | No database required for MVP. | Reduces complexity and privacy risk. |
| D-011 | Wave 2 extension permissions: `activeTab`, `scripting`, host permission `http://127.0.0.1:8000/*` for local dev. No `<all_urls>`, `tabs`, `cookies`, `storage`, or `history`. Backend URL driven by `VITE_BACKEND_URL` build-time env var so future deployment does not require manifest changes. | Narrowest permissions supporting MVP per docs/07_PRIVACY_SECURITY.md §Extension permissions. Approved 2026-10-23. |
| D-012 | OpenAI is the LLM provider for Phase 4. Used through the existing `SimpleLLMInterpreter` with stdlib `urllib` transport (no `openai` SDK dependency). Model is configurable via `OPENAI_MODEL` env var (default: `gpt-4o-mini`). API URL configurable via `OPENAI_API_URL` for Azure/local proxy/compatible providers. | Keeps the implementation zero-dependency, provider-switchable, and consistent with the existing interface. Resolves O-001. Approved 2026-10-23. |
| D-013 | Define backend-only AI proposals as a separate `AIProposal` schema, with AI provenance and fixed `pending_validation` status. Keep candidate labels free-form while any proposed approved category remains constrained to `FindingCategory`; do not add proposals to `AnalyzeResponse` or treat them as trusted `Finding` values in this stage. | Establishes an explicit trust boundary for later mock/comparison work without changing deterministic findings or the public API. Approved 2026-10-24. Its initial backend-only exposure constraint is refined by D-015. |
| D-014 | Compare AI proposals with deterministic findings only by exact category-and-evidence-quote match. Mark quote presence separately from proposal validity; never treat quote presence as validation of the explanation or recommendation. Keep comparison results separate from trusted findings and `AnalyzeResponse`. | Avoids unsupported semantic matching and preserves the trusted finding contract. Approved 2026-10-24. The opt-in wrapper exposure is specified by D-015. |
| D-015 | Expose proposal-comparison results only through the opt-in `POST /api/v1/analyze/compare` wrapper response. Keep the existing `POST /api/v1/analyze` contract and behavior unchanged; comparison uses deterministic findings and an unconfigured no-op provider by default. | Makes comparison results accessible without changing the existing endpoint or merging proposals into trusted findings. Approved 2026-10-24. |
| D-016 | For the candidate-review workflow only, persist proposals in a local SQLite knowledge base using the standard library. Keep it outside the repository by default, store no submitted page/title/URL, require an explicit manual validation decision before promotion, and keep promoted records advisory. Provide the mock source only through an explicitly invoked synthetic offline demo; do not implicitly persist `/api/v1/analyze/compare` requests or expose lifecycle mutations as unauthenticated routes. This does not change D-010's no-database MVP analysis path. | Avoids new infrastructure and hidden data retention while providing a durable, reviewable candidate lifecycle. Approved 2026-10-24. |
| D-017 | The extension may show an uncalibrated 0–100 dark-pattern risk indicator only for evidence-backed urgency-pressure and missing trial-renewal-price findings. Apply severity points × explicit/inferred evidence multiplier × confidence; count only the strongest finding per category, cap at 100, show the contributing findings, and use “Insufficient evidence to score” when none qualifies. Recurring billing, disclosed trials, cancellation policies, and unexplained checkout differences do not score by themselves. | Provides the requested primary result while avoiding ordinary financial terms and unexplained differences being treated as proof of deceptive intent. It is an indicator, not a probability or safety guarantee. Approved by the product request on 2026-10-24. |

## Open decisions — resolve before the relevant phase
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
