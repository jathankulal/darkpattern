"""Phase 2: Locale propagation and language-aware AI explanation tests.

Tests cover:
- Prompt language instructions for English, Kannada, Hindi.
- Regional locale normalization (kn-IN → kn, hi-IN → hi, en-US → en).
- Evidence text remains verbatim regardless of locale.
- Missing/empty locale falls back to English (no language instruction).
- Invalid AI output and provider failure still degrade gracefully with locale.
- Full API endpoint accepts and propagates locale.
"""

import json
from typing import Optional
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.ai.base import (
    AIInterpretationResult,
    NullAIInterpreter,
    SimpleLLMInterpreter,
    _build_user_prompt,
    _normalise_locale,
    _SUPPORTED_LANGUAGES,
    _SYSTEM_PROMPT,
)
from app.analyzer import analyze_page_content
from app.config import Settings
from app.main import app
from app.schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    AnalyzeStatus,
    EvidenceLevel,
    FindingCategory,
    FindingSeverity,
)

client = TestClient(app)

_TEST_SETTINGS = Settings(environment="test", openai_api_key=None)

_SAMPLE_PAGE_TEXT = (
    "Start your free 7-day trial. Then $9.99 per month automatically. "
    "Cancel at least 24 hours before renewal. "
    "Limited time offer! Only 2 spots left!"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_openai_response(findings: list, summary: str = "Test summary", ambiguities: list | None = None) -> dict:
    """Construct a mock OpenAI chat-completions response dict."""
    content = {
        "findings": findings,
        "summary": summary,
    }
    if ambiguities is not None:
        content["ambiguities"] = ambiguities
    return {
        "choices": [
            {
                "message": {
                    "content": json.dumps(content),
                },
            }
        ],
    }


def _make_http_response(data: dict, status_code: int = 200) -> MagicMock:
    """Create a mock urllib response object."""
    body = json.dumps(data).encode("utf-8")
    resp = MagicMock()
    resp.read.return_value = body
    resp.status = status_code
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    return resp


# ===========================================================================
# 1. _normalise_locale — regional tag normalization
# ===========================================================================

class TestNormaliseLocale:
    """Verify BCP-47 primary subtag extraction."""

    def test_kannada_india(self):
        assert _normalise_locale("kn-IN") == "kn"

    def test_hindi_india(self):
        assert _normalise_locale("hi-IN") == "hi"

    def test_english_us(self):
        assert _normalise_locale("en-US") == "en"

    def test_english_gb(self):
        assert _normalise_locale("en-GB") == "en"

    def test_plain_kn(self):
        assert _normalise_locale("kn") == "kn"

    def test_plain_hi(self):
        assert _normalise_locale("hi") == "hi"

    def test_plain_en(self):
        assert _normalise_locale("en") == "en"

    def test_none_returns_none(self):
        assert _normalise_locale(None) is None

    def test_empty_string_returns_none(self):
        assert _normalise_locale("") is None

    def test_whitespace_only_returns_none(self):
        assert _normalise_locale("   ") is None

    def test_case_insensitive(self):
        assert _normalise_locale("KN-IN") == "kn"
        assert _normalise_locale("HI-in") == "hi"
        assert _normalise_locale("EN-us") == "en"


# ===========================================================================
# 2. _build_user_prompt — language instruction injection
# ===========================================================================

class TestBuildUserPromptLanguage:
    """Verify prompt includes correct language instruction for each locale."""

    def test_kannada_locale_injects_kannada_instruction(self):
        prompt = _build_user_prompt("Test Page", "some page text", locale="kn")
        assert "Respond in Kannada" in prompt
        assert "evidence_text" in prompt  # Must mention evidence preservation

    def test_kannada_regional_locale(self):
        prompt = _build_user_prompt("Test Page", "some page text", locale="kn-IN")
        assert "Respond in Kannada" in prompt

    def test_hindi_locale_injects_hindi_instruction(self):
        prompt = _build_user_prompt("Test Page", "some page text", locale="hi")
        assert "Respond in Hindi" in prompt
        assert "evidence_text" in prompt

    def test_hindi_regional_locale(self):
        prompt = _build_user_prompt("Test Page", "some page text", locale="hi-IN")
        assert "Respond in Hindi" in prompt

    def test_english_locale_no_language_instruction(self):
        """English is the default — no extra language instruction needed."""
        prompt = _build_user_prompt("Test Page", "some page text", locale="en")
        assert "LANGUAGE INSTRUCTION" not in prompt
        assert "Respond in" not in prompt

    def test_english_us_locale_no_language_instruction(self):
        prompt = _build_user_prompt("Test Page", "some page text", locale="en-US")
        assert "LANGUAGE INSTRUCTION" not in prompt

    def test_none_locale_no_language_instruction(self):
        prompt = _build_user_prompt("Test Page", "some page text", locale=None)
        assert "LANGUAGE INSTRUCTION" not in prompt

    def test_empty_locale_no_language_instruction(self):
        prompt = _build_user_prompt("Test Page", "some page text", locale="")
        assert "LANGUAGE INSTRUCTION" not in prompt

    def test_unsupported_locale_no_language_instruction(self):
        """Unsupported languages should not inject any instruction."""
        prompt = _build_user_prompt("Test Page", "some page text", locale="fr-FR")
        assert "LANGUAGE INSTRUCTION" not in prompt
        assert "Respond in" not in prompt

    def test_page_title_always_present(self):
        """Page title must appear regardless of locale."""
        for loc in [None, "en", "kn", "hi", "kn-IN"]:
            prompt = _build_user_prompt("My Checkout Page", "text here", locale=loc)
            assert "My Checkout Page" in prompt

    def test_page_text_always_in_delimiters(self):
        """Untrusted text delimiters must always be present."""
        for loc in [None, "en", "kn", "hi"]:
            prompt = _build_user_prompt("T", "secret page content", locale=loc)
            assert "=== UNTRUSTED WEBPAGE TEXT BEGIN ===" in prompt
            assert "=== UNTRUSTED WEBPAGE TEXT END ===" in prompt
            assert "secret page content" in prompt

    def test_evidence_text_preservation_instruction_in_language_prompt(self):
        """When a non-English language is requested, the prompt must explicitly
        instruct the AI to keep evidence_text as verbatim copies."""
        for loc in ["kn", "hi", "kn-IN", "hi-IN"]:
            prompt = _build_user_prompt("T", "text", locale=loc)
            assert "verbatim" in prompt.lower()


# ===========================================================================
# 3. _SUPPORTED_LANGUAGES map validation
# ===========================================================================

class TestSupportedLanguages:
    """Verify the supported language map has expected entries."""

    def test_kannada_in_supported(self):
        assert "kn" in _SUPPORTED_LANGUAGES
        assert _SUPPORTED_LANGUAGES["kn"] == "Kannada"

    def test_hindi_in_supported(self):
        assert "hi" in _SUPPORTED_LANGUAGES
        assert _SUPPORTED_LANGUAGES["hi"] == "Hindi"

    def test_english_not_in_map(self):
        """English is the default — it should NOT be in the map."""
        assert "en" not in _SUPPORTED_LANGUAGES


# ===========================================================================
# 4. NullAIInterpreter — locale parameter accepted without error
# ===========================================================================

class TestNullInterpreterLocale:
    def test_accepts_locale_parameter(self):
        result = NullAIInterpreter().interpret(
            "Title", "http://x", "text", {}, locale="kn"
        )
        assert result.ai_status == "unconfigured"
        assert result.additional_findings == []

    def test_accepts_none_locale(self):
        result = NullAIInterpreter().interpret(
            "Title", "http://x", "text", {}, locale=None
        )
        assert result.ai_status == "unconfigured"

    def test_accepts_regional_locale(self):
        result = NullAIInterpreter().interpret(
            "Title", "http://x", "text", {}, locale="hi-IN"
        )
        assert result.ai_status == "unconfigured"


# ===========================================================================
# 5. SimpleLLMInterpreter — locale propagated to prompt
# ===========================================================================

class TestSimpleLLMInterpreterLocale:
    """Verify locale is threaded through to the API call payload."""

    def test_kannada_locale_in_payload(self):
        interp = SimpleLLMInterpreter(api_key="test-key-123")
        mock_resp = _make_http_response(_make_openai_response([], summary="Test"))

        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
            result = interp.interpret(
                "Test Page", "https://example.com", _SAMPLE_PAGE_TEXT, {},
                locale="kn",
            )

            # Verify the request payload contains the Kannada instruction
            call_args = mock_urlopen.call_args
            req = call_args[0][0]  # urllib.request.Request object
            payload = json.loads(req.data.decode("utf-8"))
            user_msg = payload["messages"][1]["content"]
            assert "Respond in Kannada" in user_msg

        assert result.ai_status == "active"

    def test_hindi_locale_in_payload(self):
        interp = SimpleLLMInterpreter(api_key="test-key-123")
        mock_resp = _make_http_response(_make_openai_response([], summary="Test"))

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = interp.interpret(
                "Test Page", "https://example.com", _SAMPLE_PAGE_TEXT, {},
                locale="hi-IN",
            )
        assert result.ai_status == "active"

    def test_english_locale_no_instruction_in_payload(self):
        interp = SimpleLLMInterpreter(api_key="test-key-123")
        mock_resp = _make_http_response(_make_openai_response([], summary="Test"))

        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
            interp.interpret(
                "Test Page", "https://example.com", _SAMPLE_PAGE_TEXT, {},
                locale="en-US",
            )

            call_args = mock_urlopen.call_args
            req = call_args[0][0]
            payload = json.loads(req.data.decode("utf-8"))
            user_msg = payload["messages"][1]["content"]
            assert "LANGUAGE INSTRUCTION" not in user_msg

    def test_none_locale_no_instruction_in_payload(self):
        interp = SimpleLLMInterpreter(api_key="test-key-123")
        mock_resp = _make_http_response(_make_openai_response([], summary="Test"))

        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
            interp.interpret(
                "Test Page", "https://example.com", _SAMPLE_PAGE_TEXT, {},
                locale=None,
            )

            call_args = mock_urlopen.call_args
            req = call_args[0][0]
            payload = json.loads(req.data.decode("utf-8"))
            user_msg = payload["messages"][1]["content"]
            assert "LANGUAGE INSTRUCTION" not in user_msg


# ===========================================================================
# 6. Evidence text unchanged regardless of locale
# ===========================================================================

class TestEvidencePreservedWithLocale:
    """AI findings must have evidence_text exactly matching source,
    regardless of which locale was requested."""

    def test_evidence_grounded_with_kannada_locale(self):
        evidence = "Then $9.99 per month automatically"
        interp = SimpleLLMInterpreter(api_key="test-key-123")
        mock_resp = _make_http_response(_make_openai_response(
            findings=[{
                "category": "recurring_payment",
                "severity": "medium",
                "evidence_text": evidence,
                "explanation": "ಪ್ರತಿ ತಿಂಗಳು $9.99 ಶುಲ್ಕ ವಿಧಿಸಲಾಗುತ್ತದೆ",
                "recommendation": "ನವೀಕರಣ ದಿನಾಂಕವನ್ನು ಪರಿಶೀಲಿಸಿ",
            }],
            summary="ಟ್ರಯಲ್ ನಂತರ ಮಾಸಿಕ ಶುಲ್ಕ",
        ))

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = interp.interpret(
                "Test Page", "https://example.com", _SAMPLE_PAGE_TEXT, {},
                locale="kn",
            )

        assert result.ai_status == "active"
        assert len(result.additional_findings) == 1
        f = result.additional_findings[0]
        # Evidence must be the exact verbatim substring
        assert f.evidence_text == evidence
        assert f.evidence_text in _SAMPLE_PAGE_TEXT

    def test_evidence_grounded_with_hindi_locale(self):
        evidence = "Cancel at least 24 hours before renewal"
        interp = SimpleLLMInterpreter(api_key="test-key-123")
        mock_resp = _make_http_response(_make_openai_response(
            findings=[{
                "category": "cancellation_refund_clarity",
                "severity": "low",
                "evidence_text": evidence,
                "explanation": "रद्द करने की 24 घंटे की अवधि है",
                "recommendation": "नवीकरण तिथि से पहले रद्द करें",
            }],
            summary="रद्दीकरण शर्तें मौजूद हैं",
        ))

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = interp.interpret(
                "Test Page", "https://example.com", _SAMPLE_PAGE_TEXT, {},
                locale="hi",
            )

        assert result.ai_status == "active"
        assert len(result.additional_findings) == 1
        assert result.additional_findings[0].evidence_text == evidence
        assert result.additional_findings[0].evidence_text in _SAMPLE_PAGE_TEXT

    def test_fabricated_evidence_rejected_regardless_of_locale(self):
        """Evidence not in source must be rejected, even with non-English locale."""
        interp = SimpleLLMInterpreter(api_key="test-key-123")
        mock_resp = _make_http_response(_make_openai_response(
            findings=[{
                "category": "recurring_payment",
                "severity": "medium",
                "evidence_text": "ಈ ಪಠ್ಯವು ಪುಟದಲ್ಲಿ ಇಲ್ಲ",  # Kannada text not in source
                "explanation": "ಕೃತಕ ಸಾಕ್ಷಿ",
                "recommendation": "test",
            }],
            summary="Test",
        ))

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = interp.interpret(
                "Test Page", "https://example.com", _SAMPLE_PAGE_TEXT, {},
                locale="kn",
            )

        assert result.ai_status == "active"
        assert len(result.additional_findings) == 0  # Rejected


# ===========================================================================
# 7. Graceful fallback with locale
# ===========================================================================

class TestGracefulFallbackWithLocale:
    """Provider failures must still degrade gracefully when locale is set."""

    def test_provider_failure_with_kannada_locale(self):
        import urllib.error
        interp = SimpleLLMInterpreter(api_key="test-key-123", max_retries=0)

        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Connection refused")):
            result = interp.interpret(
                "Test Page", "https://example.com", _SAMPLE_PAGE_TEXT, {},
                locale="kn",
            )

        assert result.ai_status == "failed"
        assert result.additional_findings == []

    def test_malformed_json_with_hindi_locale(self):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"not json at all"
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        interp = SimpleLLMInterpreter(api_key="test-key-123")
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = interp.interpret(
                "Test Page", "https://example.com", _SAMPLE_PAGE_TEXT, {},
                locale="hi-IN",
            )

        assert result.ai_status == "failed"
        assert result.additional_findings == []

    def test_invalid_json_structure_with_locale(self):
        """Response is valid JSON but wrong structure."""
        mock_resp = _make_http_response({"choices": [{"message": {"content": "{\"bad\": true}"}}]})
        interp = SimpleLLMInterpreter(api_key="test-key-123")

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = interp.interpret(
                "Test Page", "https://example.com", _SAMPLE_PAGE_TEXT, {},
                locale="kn-IN",
            )

        # Should succeed with active status but no findings (bad structure)
        assert result.ai_status == "active"
        assert result.additional_findings == []


# ===========================================================================
# 8. analyze_page_content — locale propagation end-to-end
# ===========================================================================

class TestAnalyzePageContentLocale:
    """Verify locale flows from AnalyzeRequest through to the interpreter."""

    def test_locale_propagated_to_interpreter(self):
        """AnalyzeRequest.locale must reach the interpreter.interpret() call."""
        from unittest.mock import call

        mock_interp = MagicMock()
        mock_interp.interpret.return_value = AIInterpretationResult(
            ai_status="active",
            additional_findings=[],
            contextual_summary=None,
            identified_ambiguities=[],
        )

        request = AnalyzeRequest(
            page_title="Test",
            page_url="https://example.com",
            page_text=_SAMPLE_PAGE_TEXT,
            locale="kn-IN",
        )

        analyze_page_content(
            request=request,
            settings=_TEST_SETTINGS,
            ai_interpreter=mock_interp,
        )

        # Verify interpret was called with locale="kn-IN"
        mock_interp.interpret.assert_called_once()
        call_kwargs = mock_interp.interpret.call_args
        assert call_kwargs.kwargs.get("locale") == "kn-IN" or (
            len(call_kwargs.args) >= 5 and call_kwargs.args[4] == "kn-IN"
        ) or call_kwargs[1].get("locale") == "kn-IN"

    def test_missing_locale_propagated_as_none(self):
        """Request without locale should pass None to interpreter."""
        mock_interp = MagicMock()
        mock_interp.interpret.return_value = AIInterpretationResult(
            ai_status="unconfigured",
        )

        request = AnalyzeRequest(
            page_title="Test",
            page_url="https://example.com",
            page_text=_SAMPLE_PAGE_TEXT,
        )

        analyze_page_content(
            request=request,
            settings=_TEST_SETTINGS,
            ai_interpreter=mock_interp,
        )

        mock_interp.interpret.assert_called_once()
        call_kwargs = mock_interp.interpret.call_args
        # locale should be None
        assert call_kwargs.kwargs.get("locale") is None or (
            len(call_kwargs.args) >= 5 and call_kwargs.args[4] is None
        ) or call_kwargs[1].get("locale") is None


# ===========================================================================
# 9. API endpoint — locale accepted in request body
# ===========================================================================

class TestAPIEndpointLocale:
    def test_analyze_accepts_locale(self):
        payload = {
            "page_title": "Test Page",
            "page_url": "https://example.com/checkout",
            "page_text": _SAMPLE_PAGE_TEXT,
            "locale": "kn-IN",
        }
        response = client.post("/api/v1/analyze", json=payload)
        assert response.status_code == 200
        data = response.json()
        validated = AnalyzeResponse.model_validate(data)
        assert validated.status in (AnalyzeStatus.OK, AnalyzeStatus.PARTIAL)

    def test_analyze_accepts_hindi_locale(self):
        payload = {
            "page_title": "Test Page",
            "page_url": "https://example.com/checkout",
            "page_text": _SAMPLE_PAGE_TEXT,
            "locale": "hi",
        }
        response = client.post("/api/v1/analyze", json=payload)
        assert response.status_code == 200

    def test_analyze_works_without_locale(self):
        """Backward compatibility: requests without locale must still work."""
        payload = {
            "page_title": "Test Page",
            "page_url": "https://example.com/checkout",
            "page_text": _SAMPLE_PAGE_TEXT,
        }
        response = client.post("/api/v1/analyze", json=payload)
        assert response.status_code == 200

    def test_analyze_accepts_english_locale(self):
        payload = {
            "page_title": "Test Page",
            "page_url": "https://example.com/checkout",
            "page_text": _SAMPLE_PAGE_TEXT,
            "locale": "en-US",
        }
        response = client.post("/api/v1/analyze", json=payload)
        assert response.status_code == 200
