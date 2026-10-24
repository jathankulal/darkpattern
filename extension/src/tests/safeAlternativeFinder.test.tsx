import React from 'react';
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { SafeAlternativeFinder } from '../components/SafeAlternativeFinder';
import type { CommitmentMap } from '../types/api';

describe('SafeAlternativeFinder', () => {
  it('shows only scanned terms and clear criteria without inventing a merchant', () => {
    const commitmentMap: CommitmentMap = {
      amount_due_now: { amount: '0', currency: 'USD', kind: 'trial' },
      future_charge: {
        amount: '19.99',
        currency: 'USD',
        kind: 'recurring',
        interval: 'monthly',
      },
      billing_interval: 'monthly',
      trial_duration: '7 days',
      future_charge_trigger: 'After 7 days trial ends',
      cancellation_terms: 'Cancel anytime from account settings',
      unknowns: [],
    };

    render(<SafeAlternativeFinder commitmentMap={commitmentMap} />);

    expect(screen.getByText('USD 19.99 per month')).toBeDefined();
    expect(screen.getByText('7 days')).toBeDefined();
    expect(
      screen.getByText('Cancel anytime from account settings'),
    ).toBeDefined();
    expect(screen.getByText(/No verified alternative listings are available/)).toBeDefined();
    expect(screen.getByText(/A clearly stated recurring price and billing frequency/)).toBeDefined();
    expect(screen.getByText(/These are comparison criteria, not a verified recommendation/)).toBeDefined();
    expect(screen.queryByText(/Recommended provider:/)).toBeNull();
  });

  it('describes missing terms as not found in checked text', () => {
    const commitmentMap: CommitmentMap = { unknowns: [] };

    render(<SafeAlternativeFinder commitmentMap={commitmentMap} />);

    expect(screen.getAllByText('Not found in the text checked')).toHaveLength(3);
    expect(screen.getByText(/Check another option for/)).toBeDefined();
  });

  it('does not imply a specific tier is selected on a multi-plan page', () => {
    render(
      <SafeAlternativeFinder
        commitmentMap={{ unknowns: [] }}
        isMultiPlan
      />,
    );

    expect(screen.getByText('This page lists multiple plans')).toBeDefined();
    expect(screen.getByText(/No plan is selected/)).toBeDefined();
    expect(screen.queryByText('Recurring charge')).toBeNull();
  });
});
