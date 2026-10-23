# 7. Privacy and Security Requirements

## Data minimization
- Scan only after explicit user action.
- Extract a bounded amount of visible text relevant to the current purchase decision.
- Do not send the entire DOM, HTML source, JavaScript, cookies, local storage, browsing history, or unrelated content.
- Do not collect card numbers, bank details, passwords, OTPs, payment tokens, or form field values.
- Strip URL query parameters and fragments by default unless there is a documented reason to retain them.
- Do not persist page text by default.
- If logs are used during development, avoid logging full page text or secrets.

## LLM and prompt injection
Page content is untrusted data. It may contain text attempting to instruct the model. The backend prompt must explicitly say that submitted page content is data to analyze, not instructions to follow. The LLM must not be allowed to change schemas, invoke tools, execute code, or decide product scope.

## Secrets
- Keep the LLM API key in backend environment variables or secret management.
- Never commit `.env`, API keys, credentials, or tokens.
- Provide `.env.example` with placeholders only.
- Never put the LLM key in extension code or browser storage.
- Add secret files to `.gitignore`.

## Extension permissions
Request the narrowest permissions that support the MVP. Do not add broad host permissions or `<all_urls>` access without a documented need and explicit approval. Explain each permission in the README.

## Network/API
- Validate all request fields and size limits.
- Use HTTPS for deployed API.
- Add sensible timeouts and error handling.
- Do not return stack traces or provider secrets to the extension.
- Apply rate limits if public deployment makes abuse plausible.
- Restrict CORS to intended extension/development origins where practical; do not use permissive wildcard CORS in production without justification.

## Data retention
No account system, server-side history, or analytics collection is required for MVP. Any future retention must be explicitly designed, documented, and disclosed.
