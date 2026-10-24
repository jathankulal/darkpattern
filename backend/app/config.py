"""Application configuration and settings."""

from functools import lru_cache
from typing import List, Literal, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment or .env file.

    OpenAI configuration (legacy interpreter):
      OPENAI_API_KEY   — Secret API key. Loaded from env only; never logged,
                         committed, or transmitted to the browser extension.
      OPENAI_MODEL     — Model identifier, e.g. "gpt-4o-mini" (default).
      OPENAI_API_URL   — Base chat-completions URL. Override for compatible
                         providers (Azure, local proxies, etc.).
      OPENAI_TIMEOUT_S — Per-request timeout in seconds.
      OPENAI_MAX_RETRIES — Maximum retry attempts on transient (5xx/timeout)
                           errors. Set to 0 to disable retries entirely.
      LLM_MAX_TEXT_CHARS — Maximum page-text characters sent to the LLM.
                           Caps the prompt to control cost and latency.
    Ollama proposal configuration:
      AI_PROPOSAL_PROVIDER — "none" (default) or opt-in "ollama".
      OLLAMA_BASE_URL — Local Ollama service URL.
      OLLAMA_MODEL — Local proposal model name.
      OLLAMA_TIMEOUT_S — Per-request timeout in seconds.

    Security notes:
      - The API key is read from the process environment / .env file only.
      - It is never included in API responses, logs, or the extension bundle.
      - The extension `.env` does NOT have this variable.
      - See docs/07_PRIVACY_SECURITY.md §Secrets for the full policy.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = "development"
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    # ------------------------------------------------------------------
    # OpenAI / LLM provider configuration
    # ------------------------------------------------------------------
    # Primary key name. The env-var alias keeps backward compatibility with
    # the older LLM_API_KEY variable used in Phases 1-3.
    openai_api_key: Optional[str] = None
    llm_api_key: Optional[str] = None  # backward-compat alias

    openai_model: str = "gpt-4o-mini"
    openai_api_url: str = "https://api.openai.com/v1/chat/completions"
    openai_timeout_s: float = 10.0
    openai_max_retries: int = 1
    llm_max_text_chars: int = 10_000

    ai_proposal_provider: Literal["none", "ollama"] = "none"
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen2.5:3b"
    ollama_timeout_s: float = Field(default=60.0, gt=0)

    @property
    def effective_api_key(self) -> Optional[str]:
        """Return the active API key, preferring OPENAI_API_KEY over LLM_API_KEY."""
        return self.openai_api_key or self.llm_api_key

    @property
    def cors_origin_list(self) -> List[str]:
        """Return parsed list of allowed CORS origins."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def llm_configured(self) -> bool:
        """Check if LLM API credentials are configured."""
        key = self.effective_api_key
        return bool(key and key.strip())


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
