import React from 'react';
import { describe, expect, it } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { FindingCard } from '../components/FindingCard';
import type { Finding } from '../types/api';

function makeFinding(overrides: Partial<Finding> = {}): Finding {
  return {
    id: 'finding-recurring-payment',
    category: 'recurring_payment',
    severity: 'info',
    evidence_level: 'explicit',
    evidence_text: 'Renews automatically at $19.99 per month.',
    explanation: 'Commitment includes automatic renewal at USD 19.99 per monthly.',
    confidence: 0.9,
    missing_information: [],
    recommendation: 'Ensure you agree to ongoing automatic renewals.',
    ...overrides,
  };
}

describe('FindingCard', () => {
  it('shows plain-language copy, severity, an unchanged quote, and a practical next step', () => {
    const exactEvidence = 'Renews automatically at $19.99 per month.';
    render(
      <FindingCard
        finding={makeFinding({
          evidence_text: exactEvidence,
          explanation: 'Internal wording that should not appear in the popup.',
          recommendation: 'Technical recommendation that should not appear.',
        })}
      />,
    );

    expect(screen.getByRole('heading', { name: 'You may be charged again' })).toBeDefined();
    expect(screen.getByText('Info')).toBeDefined();
    expect(screen.getByText('The page says this payment renews automatically.')).toBeDefined();
    expect(screen.getByText(exactEvidence, { selector: 'blockquote' })).toBeDefined();
    expect(screen.getByText('Check the renewal price and how to cancel before signing up.')).toBeDefined();
    expect(screen.queryByText(/Internal wording|Technical recommendation/)).toBeNull();
  });

  it('states cancellation uncertainty without implying cancellation is impossible or inventing a quote', () => {
    render(
      <FindingCard
        finding={makeFinding({
          id: 'finding-missing-cancellation-terms',
          category: 'missing_commitment_info',
          severity: 'low',
          evidence_level: 'unknown',
          evidence_text: '',
          missing_information: ['Cancellation terms, method, or cutoff deadline'],
        })}
      />,
    );

    expect(screen.getByRole('heading', { name: 'Check how to cancel' })).toBeDefined();
    expect(screen.getByText("We couldn't find cancellation instructions in the text we checked.")).toBeDefined();
    expect(screen.getByText(/check the account settings or terms for how to cancel/i)).toBeDefined();
    expect(screen.queryByRole('blockquote')).toBeNull();
    expect(screen.queryByText(/impossible|can't cancel/i)).toBeNull();
  });

  it('keeps urgency wording calm and can avoid repeating an explanation for similar findings', () => {
    render(
      <FindingCard
        finding={makeFinding({
          category: 'urgency_pressure',
          evidence_text: 'Sale ends in 15 minutes.',
        })}
        showExplanation={false}
      />,
    );

    expect(screen.getByRole('heading', { name: 'The page is urging you to act quickly' })).toBeDefined();
    expect(screen.getByText('Sale ends in 15 minutes.', { selector: 'blockquote' })).toBeDefined();
    expect(screen.getByText('Take time to decide whether the offer suits you.')).toBeDefined();
    expect(screen.queryByText(/deceptive/i)).toBeNull();
    expect(screen.queryByText(/countdown or limited-availability/)).toBeNull();
  });

  it('keeps the evidence disclosure accessible through the existing expand control', () => {
    render(<FindingCard finding={makeFinding()} initiallyExpanded={false} />);

    const toggle = screen.getByRole('button', { name: /you may be charged again/i });
    expect(toggle.getAttribute('aria-expanded')).toBe('false');
    fireEvent.click(toggle);
    expect(toggle.getAttribute('aria-expanded')).toBe('true');
    expect(screen.getByText("Why we're warning you")).toBeDefined();
  });
});
