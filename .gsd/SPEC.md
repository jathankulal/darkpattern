# SPEC.md — Dark Pattern Guardian

**Status: FINALIZED**

> This file is the GSD planning-lock gate only.
> All requirements, architecture, contracts, privacy rules, test strategy, and working rules
> live in `docs/`. Do not copy, restate, or modify those documents here.

---

## Source of Truth

The complete, approved specification is in the `docs/` directory.
Read [`docs/00_START_HERE.md`](../docs/00_START_HERE.md) for the read order and authority hierarchy.

| Document | Covers |
|---|---|
| [`docs/01_PROJECT_CHARTER.md`](../docs/01_PROJECT_CHARTER.md) | Product purpose, scope, non-goals, principles |
| [`docs/02_PRD_REQUIREMENTS.md`](../docs/02_PRD_REQUIREMENTS.md) | Functional and non-functional requirements, user stories |
| [`docs/03_ARCHITECTURE_AND_STACK.md`](../docs/03_ARCHITECTURE_AND_STACK.md) | Approved stack (WXT, TypeScript, React, Tailwind, FastAPI, Pydantic) and module boundaries |
| [`docs/04_DETECTION_AND_FINANCIAL_LOGIC.md`](../docs/04_DETECTION_AND_FINANCIAL_LOGIC.md) | Detection taxonomy, evidence levels, severity, LLM/calculator responsibilities |
| [`docs/05_DATA_CONTRACTS_API.md`](../docs/05_DATA_CONTRACTS_API.md) | Request/response schemas, money value shape, validation rules, error states |
| [`docs/06_UI_UX_SPEC.md`](../docs/06_UI_UX_SPEC.md) | Screen states, information hierarchy, accessibility, tone |
| [`docs/07_PRIVACY_SECURITY.md`](../docs/07_PRIVACY_SECURITY.md) | Data minimization, secrets handling, permissions, prompt injection, retention |
| [`docs/08_TEST_AND_ACCEPTANCE_PLAN.md`](../docs/08_TEST_AND_ACCEPTANCE_PLAN.md) | Test layers, demo fixtures, acceptance criteria, evaluation metrics |
| [`docs/09_IMPLEMENTATION_ROADMAP.md`](../docs/09_IMPLEMENTATION_ROADMAP.md) | Phased build order (Phases 0-6) and exit criteria |
| [`docs/10_ANTIGRAVITY_WORKING_RULES.md`](../docs/10_ANTIGRAVITY_WORKING_RULES.md) | Agent working rules — read before every task |
| [`docs/11_DECISION_LOG.md`](../docs/11_DECISION_LOG.md) | Approved decisions (D-001-D-010) and open decisions (O-001-O-007) |
| [`docs/12_DEMO_SCENARIOS.md`](../docs/12_DEMO_SCENARIOS.md) | Reproducible demo fixtures and expected behavior |

---

## Product in One Sentence

> Dark Pattern Guardian is a **user-triggered Chrome extension** that explains the real financial
> commitments on a shopping or subscription page before the user pays.
> It is a pre-purchase financial commitment explainer — not a scam detector, legal adjudicator,
> or automatic purchase blocker.

---

## What FINALIZED Means Here

The `docs/` specification was authored and reviewed before any implementation began.
No feature is considered implemented until code and tests confirm it.
If a request conflicts with `docs/`, stop and ask rather than proceeding.

To change any requirement: follow the change process in
[`docs/11_DECISION_LOG.md`](../docs/11_DECISION_LOG.md) — add a new decision ID,
explain the change, list impacted docs/code/tests, and obtain approval before editing.
