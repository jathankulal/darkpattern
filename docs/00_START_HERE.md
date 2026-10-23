# Dark Pattern Guardian — Project Documentation Pack

## Purpose
This folder is the project's source of truth for development in Antigravity. Read these documents before changing code. If a request conflicts with these documents, stop and ask for clarification rather than silently changing the product.

## Read order
1. `01_PROJECT_CHARTER.md` — product purpose, scope, non-goals.
2. `02_PRD_REQUIREMENTS.md` — functional and non-functional requirements.
3. `03_ARCHITECTURE_AND_STACK.md` — approved architecture and technologies.
4. `04_DETECTION_AND_FINANCIAL_LOGIC.md` — detection taxonomy, evidence rules, calculations.
5. `05_DATA_CONTRACTS_API.md` — request/response contracts.
6. `06_UI_UX_SPEC.md` — screen and interaction behavior.
7. `07_PRIVACY_SECURITY.md` — data minimization and security constraints.
8. `08_TEST_AND_ACCEPTANCE_PLAN.md` — test strategy and definition of done.
9. `09_IMPLEMENTATION_ROADMAP.md` — phased build order.
10. `10_ANTIGRAVITY_WORKING_RULES.md` — strict instructions for the coding agent.
11. `11_DECISION_LOG.md` — decisions and unresolved questions.
12. `12_DEMO_SCENARIOS.md` — stable demo fixtures.

## Source-of-truth hierarchy
- Product behavior and scope: Project Charter + PRD.
- Technical choices: Architecture and Stack.
- Money calculations and detection semantics: Detection and Financial Logic.
- Data shape: API Contracts.
- Security/privacy: Privacy and Security.
- If a document is internally inconsistent, do not guess. Report the conflict and request a decision.

## Important project principle
Dark Pattern Guardian is a **pre-purchase financial commitment explainer**, not a universal scam detector, legal adjudicator, or automatic purchase blocker. It must show the user what it found, where it found it, what remains uncertain, and what to verify before paying.

## Current status
Planning/documentation baseline. Do not assume that any feature is implemented until code and tests confirm it.
