/**
 * Typed backend API client for Dark Pattern Guardian.
 *
 * All network calls go through this module. No fetch calls elsewhere.
 *
 * Privacy constraints (docs/07_PRIVACY_SECURITY.md):
 * - Never log page text or secrets.
 * - Return structured error states; never expose stack traces or raw provider payloads.
 *
 * Error handling (docs/05_DATA_CONTRACTS_API.md §Error states):
 * - Network failure    → backend_unavailable
 * - Timeout           → analysis_timeout
 * - HTTP 4xx          → invalid_model_output  (shouldn't happen if types are correct)
 * - HTTP 5xx          → internal_error
 * - JSON parse fail   → invalid_model_output
 */

import type { AnalyzeRequest, AnalyzeResponse, ErrorCode, HealthResponse } from '../../types/api';

/** Timeout for all backend requests, in milliseconds. */
const REQUEST_TIMEOUT_MS = 15_000;

/** Base URL read from build-time env; defaults to local dev backend. */
const BACKEND_URL =
  (typeof import.meta !== 'undefined' &&
  (import.meta as unknown as { env?: { VITE_BACKEND_URL?: string } })?.env?.VITE_BACKEND_URL) ??
  'http://127.0.0.1:8000';

// ---------------------------------------------------------------------------
// Public error type
// ---------------------------------------------------------------------------

export class BackendError extends Error {
  constructor(
    public readonly code: ErrorCode,
    message: string,
    public readonly httpStatus?: number,
  ) {
    super(message);
    this.name = 'BackendError';
  }
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

async function fetchWithTimeout(
  url: string,
  options: RequestInit,
  timeoutMs: number,
): Promise<Response> {
  const controller = new AbortController();
  const timerId = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...options, signal: controller.signal });
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw new BackendError('analysis_timeout', 'Request timed out after waiting for the backend.');
    }
    throw new BackendError(
      'backend_unavailable',
      'Could not reach the analysis backend. Make sure it is running.',
    );
  } finally {
    clearTimeout(timerId);
  }
}

async function parseJsonResponse<T>(response: Response): Promise<T> {
  let body: unknown;
  try {
    body = await response.json();
  } catch {
    throw new BackendError(
      'invalid_model_output',
      'Backend returned an unreadable response.',
      response.status,
    );
  }

  if (response.status >= 500) {
    throw new BackendError(
      'internal_error',
      'The backend encountered an internal error. Please try again.',
      response.status,
    );
  }

  if (response.status === 422) {
    // Pydantic validation error — request shape mismatch; should not happen in normal use.
    throw new BackendError(
      'invalid_model_output',
      'The backend rejected the request. This is likely a bug.',
      response.status,
    );
  }

  if (!response.ok) {
    throw new BackendError(
      'internal_error',
      `Unexpected response from backend (HTTP ${response.status}).`,
      response.status,
    );
  }

  return body as T;
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * POST /api/v1/analyze
 * Sends the bounded page payload and returns a typed AnalyzeResponse.
 * Throws BackendError on any failure.
 */
export async function analyzePageRequest(request: AnalyzeRequest): Promise<AnalyzeResponse> {
  const response = await fetchWithTimeout(
    `${BACKEND_URL}/api/v1/analyze`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    },
    REQUEST_TIMEOUT_MS,
  );
  return parseJsonResponse<AnalyzeResponse>(response);
}

/**
 * GET /health
 * Returns backend health and configuration status.
 * Used by the popup to show whether the backend is fully configured.
 * Throws BackendError on failure.
 */
export async function healthCheck(): Promise<HealthResponse> {
  const response = await fetchWithTimeout(
    `${BACKEND_URL}/health`,
    { method: 'GET', headers: { Accept: 'application/json' } },
    REQUEST_TIMEOUT_MS,
  );
  return parseJsonResponse<HealthResponse>(response);
}
