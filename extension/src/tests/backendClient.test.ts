import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  analyzePageRequest,
  healthCheck,
  BackendError,
} from '../lib/api/backendClient';
import type { AnalyzeResponse, HealthResponse } from '../types/api';

describe('backendClient', () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it('successful 200 returns typed AnalyzeResponse', async () => {
    const mockData: AnalyzeResponse = {
      status: 'ok',
      summary: 'Test summary',
      findings: [],
      commitment_map: { unknowns: [] },
      price_integrity: { observations: [], reason: 'known' },
      checklist: ['Check cancellation terms'],
      limitations: ['Visible text only'],
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: vi.fn().mockResolvedValue(mockData),
    });

    const res = await analyzePageRequest({
      page_title: 'Test',
      page_url: 'http://example.com',
      page_text: 'Price $10',
    });

    expect(res).toEqual(mockData);
  });

  it('network error maps to backend_unavailable', async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error('Failed to fetch'));

    await expect(
      analyzePageRequest({
        page_title: 'Test',
        page_url: 'http://example.com',
        page_text: 'Price $10',
      }),
    ).rejects.toThrow(
      expect.objectContaining({
        code: 'backend_unavailable',
      }),
    );
  });

  it('timeout maps to analysis_timeout', async () => {
    const abortErr = new DOMException('The user aborted a request.', 'AbortError');
    global.fetch = vi.fn().mockRejectedValue(abortErr);

    await expect(
      analyzePageRequest({
        page_title: 'Test',
        page_url: 'http://example.com',
        page_text: 'Price $10',
      }),
    ).rejects.toThrow(
      expect.objectContaining({
        code: 'analysis_timeout',
      }),
    );
  });

  it('422 maps to invalid_model_output', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 422,
      json: vi.fn().mockResolvedValue({ detail: 'Validation error' }),
    });

    await expect(
      analyzePageRequest({
        page_title: 'Test',
        page_url: 'http://example.com',
        page_text: 'Price $10',
      }),
    ).rejects.toThrow(
      expect.objectContaining({
        code: 'invalid_model_output',
        httpStatus: 422,
      }),
    );
  });

  it('500 maps to internal_error', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: vi.fn().mockResolvedValue({ error: 'Server exploded' }),
    });

    await expect(
      analyzePageRequest({
        page_title: 'Test',
        page_url: 'http://example.com',
        page_text: 'Price $10',
      }),
    ).rejects.toThrow(
      expect.objectContaining({
        code: 'internal_error',
        httpStatus: 500,
      }),
    );
  });

  it('malformed json maps to invalid_model_output', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: vi.fn().mockRejectedValue(new SyntaxError('Unexpected token')),
    });

    await expect(
      analyzePageRequest({
        page_title: 'Test',
        page_url: 'http://example.com',
        page_text: 'Price $10',
      }),
    ).rejects.toThrow(
      expect.objectContaining({
        code: 'invalid_model_output',
      }),
    );
  });

  it('healthCheck returns HealthResponse on success', async () => {
    const mockHealth: HealthResponse = {
      status: 'ok',
      llm_configured: false,
      environment: 'development',
      version: '0.2.0',
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: vi.fn().mockResolvedValue(mockHealth),
    });

    const res = await healthCheck();
    expect(res).toEqual(mockHealth);
  });
});
