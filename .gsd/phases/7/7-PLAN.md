---
phase: 7
plan: 1
wave: 1
gap_closure: false
---

# Plan 7.1: Chronological Financial Commitment Timeline and Annualized Projections

## Objective
Implement an empirical, chronological financial timeline detailing pre-purchase milestones (initial payment due now, trial period expiration, cancellation cutoff deadlines, renewal charges, ongoing subscription intervals, and 12-month projections) grounded in verbatim extracted evidence.

## Context
Load these files for context:
- `docs/05_DATA_CONTRACTS_API.md`
- `docs/04_DETECTION_AND_FINANCIAL_LOGIC.md`
- `PROJECT_RULES.md`

## Tasks

<task type="auto">
  <name>Task 1: Schemas and Contract Extensions</name>
  <files>
    backend/app/schemas.py
    extension/src/types/api.ts
  </files>
  <action>
    1. Define `TimelineValueType` (`observed`, `calculated`, `unresolved`).
    2. Define `TimelineEvent` (`timepoint`, `title`, `amount`, `value_type`, `description`, `evidence_text`, `is_critical_action`).
    3. Define `FinancialTimeline` (`events`, `annualized_cost`, `annualized_cost_assumptions`, `note`).
    4. Attach `timeline` to `PlanSummary` and `AnalyzeResponse`.
  </action>
  <verify>
    FastAPI and TypeScript types compile cleanly.
  </verify>
  <done>
    Both backend schemas and frontend types expose timeline structures.
  </done>
</task>

<task type="auto">
  <name>Task 2: Backend Timeline Builder and Decimal Projection Calculation</name>
  <files>
    backend/app/analyzer.py
    backend/app/extraction.py
    backend/tests/test_financial_timeline.py
  </files>
  <action>
    1. Implement `calculate_annualized_cost` using Python `Decimal` arithmetic only (no floating point currency calculation).
    2. Implement `build_plan_timeline` for tier-specific subscription schedules.
    3. Implement `build_financial_timeline` handling:
       - Multi-plan tiers (deferring to plan-specific breakdown).
       - Conflicting prices (marking unresolved with critical warning).
       - Free trial conversion (start of trial, cancellation deadline, subsequent renewal charge, ongoing cadence, and 12-month projection).
       - Undisclosed renewal charge (unresolved with action-required badge).
       - One-time purchase (due now, no ongoing commitments).
    4. Ensure verbatim evidence grounding.
    5. Guard against negated recurring mentions (e.g. "no recurring fees").
    6. Write automated pytest suite covering calculations, all timeline cases, and all 4 demo fixtures.
  </action>
  <verify>
    backend\.venv\Scripts\pytest backend\tests\test_financial_timeline.py
  </verify>
  <done>
    All 12 timeline test cases and 152 backend tests pass with 100% success.
  </done>
</task>

<task type="auto">
  <name>Task 3: Extension UI Components and Visual Presentation</name>
  <files>
    extension/src/components/FinancialTimeline.tsx
    extension/src/components/PlanList.tsx
    extension/entrypoints/popup/App.tsx
    extension/src/tests/financialTimeline.test.tsx
  </files>
  <action>
    1. Build `FinancialTimeline` component rendering:
       - 12-Month Projected Commitment callout card with transparent calculation formula.
       - Vertical chronological timeline rail with node icons.
       - Clear value-type badges (`Stated`, `Calculated`, `Unresolved`).
       - High-visibility `⚠️ Action Required` badge for critical deadlines.
       - Verbatim verified quotation toggles.
       - Disclaimers/notes for one-time purchases and multi-plan summaries.
    2. Embed `FinancialTimeline` into `App.tsx` results view and `PlanList.tsx` for tier-specific schedules.
    3. Add comprehensive Vitest unit tests verifying milestone rendering, critical actions, annualized projections, quote toggling, and empty states.
  </action>
  <verify>
    npm test in extension/
    npm run build in extension/
  </verify>
  <done>
    All 21 Vitest tests pass; production bundle builds in under 1.5 seconds.
  </done>
</task>

## Must-Haves
- [x] Zero floating point currency math: strictly `Decimal` with transparent multiplier assumptions.
- [x] Every stated milestone has verbatim matching evidence text from page.
- [x] Unresolved milestones or deadlines prominently flag `is_critical_action: true`.
- [x] All 152 backend pytest tests and 21 extension Vitest tests pass.
