"""FastAPI application entry point for Dark Pattern Guardian."""

from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware

from app.ai import NullAIInterpreter, SimpleLLMInterpreter
from app.analyzer import analyze_page_content
from app.config import get_settings
from app.schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    HealthResponse,
)

settings = get_settings()

app = FastAPI(
    title="Dark Pattern Guardian API",
    description="Pre-purchase financial commitment explainer backend",
    version="0.1.0",
)

# Enable CORS for browser extension and configured frontends.
# allow_headers is intentionally narrow: this API only requires Content-Type
# for JSON POST requests. Wildcard headers are rejected per docs/07_PRIVACY_SECURITY.md
# which states CORS should be restricted to intended origins/headers in practice.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    # Browser extensions send requests from chrome-extension:// or moz-extension:// origins.
    # These will never appear in allow_origins (which is localhost-only for dev).
    # The regex below permits any extension origin without opening a wildcard.
    allow_origin_regex=r"^(chrome-extension|moz-extension)://[a-zA-Z0-9_-]+$",
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)


@app.get("/health", response_model=HealthResponse, status_code=status.HTTP_200_OK)
def health_check() -> HealthResponse:
    """System health check and configuration status."""
    return HealthResponse(
        status="ok",
        llm_configured=settings.llm_configured,
        environment=settings.environment,
        version="0.1.0",
    )


@app.post(
    "/api/v1/analyze",
    response_model=AnalyzeResponse,
    status_code=status.HTTP_200_OK,
)
def analyze_page(request: AnalyzeRequest) -> AnalyzeResponse:
    """Analyze page text for financial commitments and dark patterns.

    Uses deterministic extraction as the authoritative base, with optional
    AI contextual interpretation when credentials are configured.
    """
    ai_interpreter = (
        SimpleLLMInterpreter(
            api_key=settings.effective_api_key,
            api_url=settings.openai_api_url,
            model=settings.openai_model,
            timeout_seconds=settings.openai_timeout_s,
            max_retries=settings.openai_max_retries,
            max_text_chars=settings.llm_max_text_chars,
        )
        if settings.llm_configured
        else NullAIInterpreter()
    )
    return analyze_page_content(
        request=request,
        settings=settings,
        ai_interpreter=ai_interpreter,
    )
