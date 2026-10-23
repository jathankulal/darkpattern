# 3. Architecture and Approved Stack

## Approved initial stack
### Browser extension
- WXT — extension tooling and build configuration.
- TypeScript — typed application and extension logic.
- React — popup/results UI.
- Tailwind CSS — styling.
- Chrome Extension Manifest V3 — browser platform.
- Content script — read limited visible page text after user action.
- Service worker/background entry — coordinate tab messaging and backend request where appropriate.

### Backend
- Python.
- FastAPI — HTTP API.
- Pydantic — request/response schema validation.
- Hosted LLM API — contextual interpretation only.
- Deterministic Python rules — keyword/regex checks and validation.
- Python `Decimal` — money arithmetic.
- Pytest — backend tests.

### Frontend and browser tests
- Vitest — unit tests for TypeScript utilities/components where appropriate.
- Playwright — browser/end-to-end checks where practical.

### Storage
- No database required for the first MVP.
- Optional SQLite later for explicitly opted-in local evaluation history; not part of initial scope.
- Do not persist scanned page text by default.

## High-level flow
1. User opens a page and clicks “Scan this page.”
2. Extension content script extracts a bounded set of relevant visible text.
3. Extension sends the minimal extracted payload to the backend.
4. Backend applies deterministic prechecks and calls the LLM for contextual interpretation when configured.
5. Backend validates the response against a Pydantic schema and validates evidence spans against submitted text.
6. Deterministic code calculates supported costs from extracted structured values.
7. Backend returns findings, commitment map, price observations, checklist, and limitations.
8. Extension displays results and links each finding to its evidence snippet.

## Architecture constraints
- LLM is not the source of truth for arithmetic.
- The backend is the only place that holds the LLM API secret.
- The extension must never include a provider API key.
- Treat page text as untrusted input, including any instructions embedded in it.
- Never execute page-provided scripts or instructions.
- Use narrow permissions and explain why each permission is required.
- Use a configurable backend URL for development and deployment.
- If no LLM key is configured, return a clear configuration state or use a clearly labeled deterministic-only mode. Never fabricate LLM output.

## Suggested module boundaries
Extension:
- `entrypoints/popup/` — popup UI.
- `entrypoints/background.ts` — background/service-worker orchestration as supported by WXT.
- `entrypoints/content.ts` — bounded text extraction and tab messaging.
- `src/lib/extraction/` — relevant-text filtering and limits.
- `src/lib/api/` — typed backend client.
- `src/components/` — findings, commitment map, checklist, errors/loading.

Backend:
- `app/main.py` — FastAPI application and route registration.
- `app/schemas.py` — Pydantic request/response models.
- `app/services/extraction_rules.py` — deterministic text signals/normalization.
- `app/services/llm_analysis.py` — LLM request and parsing.
- `app/services/evidence_validator.py` — verbatim evidence validation.
- `app/services/financial_calculator.py` — Decimal-only calculations.
- `app/services/analysis_service.py` — orchestration.
- `tests/` — schema, rule, evidence, calculator, API, and demo fixture tests.

These are proposed module boundaries, not a mandate to create all files at once. Keep structure consistent if WXT scaffolding differs; document any deviation before implementing it.
