---
phase: 1
plan: 1
wave: 1
gap_closure: false
---

# Plan 1.1: FastAPI Backend Skeleton and Contract Scaffolding

## Objective
Establish the Python 3.12 FastAPI backend skeleton with strictly typed request/response schemas matching `docs/05_DATA_CONTRACTS_API.md`, configuration checks, health endpoint, deterministic mock analysis endpoint, and automated pytest suite.

## Context
Load these files for context:
- `docs/05_DATA_CONTRACTS_API.md`
- `docs/04_DETECTION_AND_FINANCIAL_LOGIC.md`
- `docs/03_ARCHITECTURE_AND_STACK.md`
- `PROJECT_RULES.md`

## Tasks

<task type="auto">
  <name>Task 1: Environment and Dependency Configuration</name>
  <files>
    backend/requirements.txt
    backend/.env.example
  </files>
  <action>
    Define backend dependencies in `requirements.txt` (fastapi, uvicorn, pydantic, pydantic-settings, pytest, httpx).
    Provide `.env.example` with configuration variables (`LLM_API_KEY`, `ENVIRONMENT`, `CORS_ORIGINS`).
    Initialize Python 3.12 virtual environment and install dependencies.

    AVOID: Including heavy ML/LLM libraries in Phase 1.
    USE: Standard lightweight FastAPI/Pydantic stack.
  </action>
  <verify>
    py -3.12 -m venv backend\.venv
    backend\.venv\Scripts\pip install -r backend\requirements.txt
  </verify>
  <done>
    Virtual environment activated and packages installed without errors.
  </done>
</task>

<task type="auto">
  <name>Task 2: Schemas, Configuration, and Endpoints</name>
  <files>
    backend/app/__init__.py
    backend/app/config.py
    backend/app/schemas.py
    backend/app/main.py
  </files>
  <action>
    Implement:
    1. `config.py`: Environment settings with Pydantic BaseSettings, configuration checks for LLM and CORS.
    2. `schemas.py`: Exact Pydantic v2 schemas from `docs/05_DATA_CONTRACTS_API.md` (MoneyValue, Finding, CommitmentMap, PriceObservation, PriceIntegrity, AnalyzeRequest, AnalyzeResponse, HealthResponse, ErrorResponse).
    3. `main.py`: FastAPI application with CORS middleware, `GET /health`, and `POST /api/v1/analyze` returning deterministic mock payload.

    AVOID: Adding LLM calls, DB queries, or financial math in Phase 1.
    USE: Deterministic typed responses adhering strictly to data contracts.
  </action>
  <verify>
    backend\.venv\Scripts\python -c "from app.main import app; print(app.title)"
  </verify>
  <done>
    App imports cleanly and exposes `/health` and `/api/v1/analyze`.
  </done>
</task>

<task type="auto">
  <name>Task 3: Unit and Contract Testing</name>
  <files>
    backend/tests/__init__.py
    backend/tests/test_health.py
  </files>
  <action>
    Implement pytest tests using FastAPI TestClient:
    - Test `GET /health` returns status 200 and schema validates.
    - Test `POST /api/v1/analyze` returns status 200 with valid AnalyzeRequest and response validates against AnalyzeResponse schema.
    - Test `POST /api/v1/analyze` rejects invalid request bodies with 422.
  </action>
  <verify>
    backend\.venv\Scripts\pytest backend\tests -v
  </verify>
  <done>
    All test cases pass cleanly under Python 3.12.
  </done>
</task>

## Must-Haves
After all tasks complete, verify:
- [ ] Backend runs on Python 3.12.
- [ ] `GET /health` returns 200 OK.
- [ ] `POST /api/v1/analyze` validates request and returns schema-compliant mock response.
- [ ] All tests pass via pytest.

## Success Criteria
- [ ] All 3 tasks verified passing.
- [ ] Zero database, LLM, or external service dependencies introduced.
