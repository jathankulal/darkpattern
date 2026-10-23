# Dark Pattern Guardian

A user-triggered Chrome extension that explains financial commitments and unclear purchase terms before a user pays.

## Status
Planning baseline. Features are not considered implemented until verified in code and tests.

## Documentation
Read [`docs/00_START_HERE.md`](docs/00_START_HERE.md) first. The `/docs` folder defines the approved product scope, architecture, API contracts, privacy rules, tests, and Antigravity working rules.

## Approved initial stack
- WXT, TypeScript, React, Tailwind CSS, Chrome Manifest V3.
- Python, FastAPI, Pydantic.
- Hosted LLM API for contextual interpretation only.
- Deterministic rules and evidence validation.
- Python `Decimal` for money calculations.
- Pytest, Vitest, and Playwright where practical.

## Core product rule
The extension must explain what financial commitment the user is accepting and show the evidence. It must not invent terms, calculate money with an LLM, or label a merchant a scam based on weak evidence.

## Privacy
Scan only on user action. Send only bounded relevant text. Do not send credentials or persist page content by default. Keep provider API keys on the backend.

## Development
The setup commands will be added once the scaffold and exact dependency versions are created. Do not invent commands that have not been verified against the actual repository.
