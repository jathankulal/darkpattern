import React from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { AnalyzeResponse } from '../types/api';

const { analyzePageRequest, healthCheck } = vi.hoisted(() => ({
  analyzePageRequest: vi.fn(),
  healthCheck: vi.fn(),
}));

vi.mock('../lib/api/backendClient', () => ({
  analyzePageRequest,
  healthCheck,
  BackendError: class BackendError extends Error {},
}));

import App from '../../entrypoints/popup/App';

function makeResponse(): AnalyzeResponse {
  return {
    status: 'ok',
    summary: 'A scanned summary.',
    findings: [
      {
        id: 'finding-urgency',
        category: 'urgency_pressure',
        severity: 'low',
        evidence_level: 'explicit',
        evidence_text: 'Offer ends in 10 minutes.',
        explanation: 'Urgency language was found.',
        confidence: 0.85,
        missing_information: [],
        recommendation: 'Take time to decide.',
      },
    ],
    commitment_map: {
      amount_due_now: { amount: '0', currency: 'USD', kind: 'trial' },
      future_charge: { amount: '29', currency: 'USD', kind: 'recurring', interval: 'monthly' },
      billing_interval: 'monthly',
      trial_duration: '14 days',
      unknowns: [],
    },
    plans: [
      {
        plan_name: 'StreamCloud Pro',
        amount_due_now: { amount: '0', currency: 'USD', kind: 'trial' },
        future_charge: { amount: '29', currency: 'USD', kind: 'recurring', interval: 'monthly' },
        billing_interval: 'monthly',
        trial_duration: '14 days',
        unknowns: [],
        is_ambiguous: false,
        evidence_text: '14-day trial, then USD 29 monthly.',
      },
    ],
    price_integrity: {
      observations: [],
      reason: 'known',
    },
    checklist: ['Check the renewal date.'],
    limitations: ['Analysis uses visible text only.'],
    timeline: {
      events: [
        {
          timepoint: 'After 14 days',
          title: 'First recurring charge',
          amount: { amount: '29', currency: 'USD', kind: 'recurring', interval: 'monthly' },
          value_type: 'observed',
          description: 'The plan renews.',
          evidence_text: 'After the trial, USD 29 monthly.',
        },
      ],
    },
  };
}

describe('primary popup experience', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    healthCheck.mockResolvedValue({
      status: 'ok',
      llm_configured: false,
      environment: 'test',
      version: 'test',
    });
    analyzePageRequest.mockResolvedValue(makeResponse());
    Object.defineProperty(globalThis, 'browser', {
      configurable: true,
      value: {
        tabs: {
          query: vi.fn().mockResolvedValue([
            { id: 3, url: 'https://example.test/checkout', title: 'Example checkout' },
          ]),
          sendMessage: vi.fn().mockResolvedValue({
            success: true,
            data: {
              pageTitle: 'Example checkout',
              pageUrl: 'https://example.test/checkout',
              pageText: 'Offer ends in 10 minutes. 14-day trial, then USD 29 monthly.',
              locale: 'en',
            },
          }),
        },
      },
    });
  });

  it('puts risk and evidence first, while preserving supporting analysis behind the details control', async () => {
    render(<App />);
    fireEvent.click(screen.getByRole('button', { name: 'Scan this page' }));

    expect(await screen.findByText('Page analyzed')).toBeDefined();
    expect(screen.getByRole('heading', { name: 'Dark Pattern Risk' })).toBeDefined();
    expect(screen.getByRole('heading', { name: 'Main issues found' })).toBeDefined();
    const evidenceQuotes = screen.getAllByText('Offer ends in 10 minutes.', { selector: 'blockquote' });
    expect(evidenceQuotes.some((quote) => !quote.closest('details'))).toBe(true);
    expect(screen.getByRole('heading', { name: 'Financial impact' })).toBeDefined();
    const detailedMap = screen.getByRole('region', { name: 'Financial Commitment Summary' });
    expect(detailedMap.closest('details')?.open).toBe(false);

    fireEvent.click(screen.getByText('View detailed analysis'));

    await waitFor(() => {
      expect(screen.getByRole('region', { name: 'Financial Commitment Summary' })).toBeDefined();
      expect(screen.getByRole('region', { name: 'Financial Commitment Timeline' })).toBeDefined();
      expect(screen.getByRole('region', { name: 'Pricing Plans Breakdown (1)' })).toBeDefined();
      expect(screen.getByRole('region', { name: 'Compare a clearer option' })).toBeDefined();
      expect(screen.getByRole('region', { name: 'Price Integrity & Checkout Trail' })).toBeDefined();
      expect(screen.getByRole('region', { name: 'Ask Before You Pay' })).toBeDefined();
      expect(detailedMap.closest('details')?.open).toBe(true);
    });

    expect(screen.getByText('All findings (1)')).toBeDefined();
    expect(screen.getByText(/visible text only/i)).toBeDefined();
  });

  it('keeps extraction failures in the existing error state without showing a score', async () => {
    const browserApi = (globalThis as typeof globalThis & {
      browser: { tabs: { sendMessage: ReturnType<typeof vi.fn> } };
    }).browser;
    browserApi.tabs.sendMessage.mockResolvedValue({
      success: true,
      data: { pageTitle: 'Empty page', pageUrl: 'https://example.test', pageText: '' },
    });

    render(<App />);
    fireEvent.click(screen.getByRole('button', { name: 'Scan this page' }));

    expect(await screen.findByRole('alert')).toBeDefined();
    expect(screen.queryByRole('heading', { name: 'Dark Pattern Risk' })).toBeNull();
    expect(analyzePageRequest).not.toHaveBeenCalled();
  });
});
