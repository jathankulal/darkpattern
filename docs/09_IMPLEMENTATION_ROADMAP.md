# 9. Implementation Roadmap

## Phase 0 — Freeze requirements
- Read this documentation pack.
- Create a short architecture decision record for any necessary deviation.
- Confirm development environment and backend provider.
- Do not start extra features while core requirements are unclear.

Exit criteria: repository structure and setup plan agreed.

## Phase 1 — Skeleton and contracts
- Scaffold WXT + TypeScript + React + Tailwind.
- Scaffold FastAPI backend.
- Define Pydantic request/response models and TypeScript equivalents.
- Add health endpoint and configuration checks.
- Add `.env.example`, `.gitignore`, README, and basic tests.

Exit criteria: extension can call backend and render a typed mock response; no LLM required yet.

## Phase 2 — Extraction and deterministic baseline
- Implement user-triggered visible-text extraction with limits.
- Add deterministic candidate signals for price/trial/renewal/fees/cancellation.
- Implement evidence validator.
- Build a transparent deterministic-only result path.
- Add tests for all demo fixtures.

Exit criteria: every result is traceable to extracted text or explicitly marked unknown.

## Phase 3 — Financial Commitment Map
- Extract structured money and billing terms.
- Implement Decimal calculator.
- Show pay-now, pay-later, interval, trigger, cancellation terms, and unknowns.
- Never calculate when required inputs are missing.

Exit criteria: money tests pass and the UI shows assumptions/unknowns.

## Phase 4 — LLM contextual interpretation
- Add hosted LLM call behind backend interface.
- Enforce strict JSON/schema output.
- Validate evidence spans after the model responds.
- Add timeout, retry policy only if justified, and deterministic fallback.
- Keep arithmetic outside the model.
- Test prompt-injection-like text and invalid model output.

Exit criteria: model adds useful context without inventing evidence or changing contracts.

## Phase 5 — Price Integrity Trail and checklist
- Compare prices only when two comparable observed values exist.
- Explain disclosed versus unclear fees where evidence supports it.
- Generate “Ask Before You Pay” questions from unknowns.
- Test the transparent subscription fixture.

Exit criteria: no fabricated previous price or unsupported accusation.

## Phase 6 — Polish and demo
- Improve loading/error/partial states and accessibility.
- Run pytest, Vitest, and end-to-end tests.
- Test on a clean clone and a second machine.
- Prepare a 2–3 minute demo using fixed fixtures.
- Document known limitations and measured results.

## Deferred until explicit approval
- Cancellation journey automation.
- User accounts or server-side history.
- Browser-wide background monitoring.
- Multi-agent architecture.
- Custom model training.
- Composite Clarity Score.
- Automated blocking or purchase actions.
