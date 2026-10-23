# ROADMAP.md — Dark Pattern Guardian

> **Authority:** Phase definitions, exit criteria, scope, and deferred items are governed by
> [`docs/09_IMPLEMENTATION_ROADMAP.md`](../docs/09_IMPLEMENTATION_ROADMAP.md).
> This file is the GSD progress tracker only. Do not invent milestones or change criteria here.
>
> **Acceptance criteria** for each phase are in
> [`docs/08_TEST_AND_ACCEPTANCE_PLAN.md`](../docs/08_TEST_AND_ACCEPTANCE_PLAN.md).

---

## Current Position

**Active phase:** Phase 1 — Skeleton and Contracts  
**Status:** Not started (no implementation code exists)

---

## Milestone 1 — Foundation (Phases 0–1)

### Phase 0: Freeze Requirements
**Status:** ✅ COMPLETE

Exit criteria (from `docs/09`):
- [x] Documentation pack read and understood.
- [x] Stack confirmed: WXT + TypeScript + React + Tailwind / Python + FastAPI + Pydantic.
- [x] No unresolved architectural conflicts found.
- [x] GSD bridge files created (`SPEC.md`, `ROADMAP.md`, `STATE.md`).

> Phase 0 is complete. Implementation has not started.

---

### Phase 1: Skeleton and Contracts
**Status:** ⬜ Not Started

Tasks (from `docs/09`):
- [ ] Scaffold WXT + TypeScript + React + Tailwind extension.
- [ ] Scaffold FastAPI backend.
- [ ] Define Pydantic request/response models (see `docs/05_DATA_CONTRACTS_API.md`).
- [ ] Define matching TypeScript types on the extension side.
- [ ] Add health endpoint and configuration checks.
- [ ] Add `.env.example`, `.gitignore`, `README.md`, and basic tests.

**Exit criterion:**
> Extension can call backend and render a typed mock response; no LLM required yet.

**Open decisions that may affect Phase 1:**
- O-005: Max page-text length and API request size (deferrable to Phase 2).
- O-006: Which extension permissions are strictly required after the first scaffold?
- Dev environment: Node/npm version, Python version, venv approach — confirm before running scaffold.

---

## Milestone 2 — Core Detection (Phases 2–3)

### Phase 2: Extraction and Deterministic Baseline
**Status:** ⬜ Not Started

Tasks (from `docs/09`):
- [ ] Implement user-triggered visible-text extraction with limits.
- [ ] Add deterministic candidate signals for price/trial/renewal/fees/cancellation.
- [ ] Implement evidence validator (verbatim substring matching).
- [ ] Build transparent deterministic-only result path.
- [ ] Add tests for all demo fixtures (see `docs/12_DEMO_SCENARIOS.md`).

**Exit criterion:**
> Every result is traceable to extracted text or explicitly marked unknown.

---

### Phase 3: Financial Commitment Map
**Status:** ⬜ Not Started

Tasks (from `docs/09`):
- [ ] Extract structured money and billing terms.
- [ ] Implement `Decimal` calculator (no binary floating-point for currency).
- [ ] Show pay-now, pay-later, interval, trigger, cancellation terms, and unknowns.
- [ ] Never calculate when required inputs are missing.

**Exit criterion:**
> Money tests pass and the UI shows assumptions/unknowns.

---

## Milestone 3 — Intelligence and Polish (Phases 4–6)

### Phase 4: LLM Contextual Interpretation
**Status:** ⬜ Not Started

Tasks (from `docs/09`):
- [ ] Add hosted LLM call behind backend interface.
- [ ] Enforce strict JSON/schema output.
- [ ] Validate evidence spans after model responds.
- [ ] Add timeout, retry policy (only if justified), and deterministic fallback.
- [ ] Keep arithmetic outside the model.
- [ ] Test prompt-injection-like text and invalid model output.

**Blocked on:** O-001 (LLM provider/model selection).

**Exit criterion:**
> Model adds useful context without inventing evidence or changing contracts.

---

### Phase 5: Price Integrity Trail and Checklist
**Status:** ⬜ Not Started

Tasks (from `docs/09`):
- [ ] Compare prices only when two comparable observed values exist.
- [ ] Explain disclosed vs. unclear fees where evidence supports it.
- [ ] Generate "Ask Before You Pay" questions from unknowns.
- [ ] Test the transparent subscription fixture (Scenario C).

**Exit criterion:**
> No fabricated previous price or unsupported accusation.

---

### Phase 6: Polish and Demo
**Status:** ✅ COMPLETE

Tasks (from `docs/09`):
- [x] Improve loading/error/partial states and accessibility.
- [x] Run pytest, Vitest, and end-to-end tests on a clean clone.
- [x] Prepare 2–3 minute demo using fixed fixtures.
- [x] Document known limitations and measured results.

**Exit criterion:**
> All acceptance criteria in `docs/08_TEST_AND_ACCEPTANCE_PLAN.md` are met and evidenced.

---

### Phase 7: Financial Commitment Timeline & Annualized Projections
**Status:** ✅ COMPLETE

Tasks:
- [x] Define typed timeline contracts (`TimelineEvent`, `TimelineValueType`, `FinancialTimeline`).
- [x] Implement deterministic annualized commitment calculations using Decimal arithmetic.
- [x] Construct chronological timeline tracking payments, trial expiration, cutoff deadlines, renewal charges, and 12-month projections.
- [x] Ground all milestones in verbatim extracted evidence snippets.
- [x] Build React `FinancialTimeline` component with vertical timeline rail, critical action badges, and calculation callouts.
- [x] Integrate timeline into popup view and multi-plan breakdowns.
- [x] Validate with 12 backend pytest tests (152 total) and 4 Vitest tests (21 total).

**Exit criterion:**
> Consumers are presented with a clear chronological sequence of financial milestones and annualized commitments before paying.

---

## Deferred (No Approval Received)

From `docs/09_IMPLEMENTATION_ROADMAP.md` — explicitly deferred:
- Cancellation journey automation.
- User accounts or server-side history.
- Browser-wide background monitoring.
- Multi-agent architecture.
- Custom model training.
- Composite Clarity Score.
- Automated blocking or purchase actions.

Do not implement any of the above without explicit approval and a new decision ID in `docs/11_DECISION_LOG.md`.
