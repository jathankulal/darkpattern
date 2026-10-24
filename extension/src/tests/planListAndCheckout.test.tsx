import React from 'react';
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { PlanList } from '../components/PlanList';
import { PriceIntegrityTrail } from '../components/PriceIntegrityTrail';
import { CommitmentMap } from '../components/CommitmentMap';
import type { PlanSummary, PriceIntegrity, CommitmentMap as CommitmentMapType } from '../types/api';

describe('PlanList Component', () => {
  it('renders confident and ambiguous plans clearly', () => {
    const plans: PlanSummary[] = [
      {
        plan_name: 'Basic',
        amount_due_now: { amount: '499', currency: 'INR', kind: 'recurring', interval: 'monthly' },
        future_charge: { amount: '499', currency: 'INR', kind: 'recurring', interval: 'monthly' },
        billing_interval: 'monthly',
        trial_duration: null,
        future_charge_trigger: null,
        cancellation_terms: null,
        unknowns: [],
        is_ambiguous: false,
        evidence_text: 'Basic: ₹499/month',
      },
      {
        plan_name: 'Starter',
        amount_due_now: { amount: '49', currency: 'USD', kind: 'recurring', interval: 'monthly' },
        future_charge: { amount: '49', currency: 'USD', kind: 'recurring', interval: 'monthly' },
        billing_interval: 'monthly',
        trial_duration: null,
        future_charge_trigger: null,
        cancellation_terms: null,
        unknowns: ['Price is not unambiguously attributed to this specific plan'],
        is_ambiguous: true,
        ambiguity_reason: 'Price not unambiguously tied to Starter plan',
        evidence_text: 'Starter, Pro, Enterprise for $49/mo',
      },
    ];

    render(<PlanList plans={plans} />);

    // Plan names should be present
    expect(screen.getByText('Basic')).toBeDefined();
    expect(screen.getByText('Starter')).toBeDefined();

    // Badges should be present
    expect(screen.getByText('✓ Confident')).toBeDefined();
    expect(screen.getByText('⚠️ Ambiguous')).toBeDefined();

    // Ambiguity note should be clearly shown
    expect(screen.getByText(/Price not unambiguously tied to Starter plan/)).toBeDefined();
  });
});

describe('PriceIntegrityTrail Component with Checkout Breakdown', () => {
  it('labels a free-trial renewal as the recurring price, not a price discrepancy', () => {
    const priceIntegrity: PriceIntegrity = {
      observations: [
        {
          stage: 'trial',
          amount: { amount: '0', currency: 'USD', kind: 'trial' },
          context: 'Free trial period',
        },
        {
          stage: 'renewal',
          amount: {
            amount: '29.00',
            currency: 'USD',
            kind: 'recurring',
            interval: 'monthly',
          },
          context: 'Subsequent recurring charge after trial',
        },
      ],
      difference: {
        amount: '29.00',
        currency: 'USD',
        kind: 'recurring',
        interval: 'monthly',
      },
      reason: 'known',
    };

    render(<PriceIntegrityTrail priceIntegrity={priceIntegrity} />);

    expect(screen.getByText('Recurring price after trial:')).toBeDefined();
    expect(screen.getByText(/This is the stated renewal price after the trial/i)).toBeDefined();
    expect(screen.getByText('Trial and renewal prices are stated')).toBeDefined();
    expect(screen.queryByText('Stage Price Difference:')).toBeNull();
    expect(screen.queryByText(/Unexplained Price Difference/)).toBeNull();
  });

  it('explains the unexplained checkout difference without claiming deception', () => {
    const priceIntegrity: PriceIntegrity = {
      observations: [
        { stage: 'subtotal', amount: { amount: '50.00', currency: 'USD', kind: 'one_time' } },
        { stage: 'processing fee', amount: { amount: '4.00', currency: 'USD', kind: 'fee' } },
        { stage: 'service fee', amount: { amount: '3.00', currency: 'USD', kind: 'fee' } },
        { stage: 'total', amount: { amount: '65.00', currency: 'USD', kind: 'one_time' } },
      ],
      difference: { amount: '15.00', currency: 'USD', kind: 'fee' },
      reason: 'unclear',
      checkout_subtotal: { amount: '50.00', currency: 'USD', kind: 'one_time' },
      explicit_fees: [
        {
          name: 'Processing Fee',
          amount: { amount: '4.00', currency: 'USD', kind: 'fee' },
        },
        {
          name: 'Service Fee',
          amount: { amount: '3.00', currency: 'USD', kind: 'fee' },
        },
      ],
      final_total: { amount: '65.00', currency: 'USD', kind: 'one_time' },
      unexplained_difference: { amount: '8.00', currency: 'USD', kind: 'fee' },
    };

    render(<PriceIntegrityTrail priceIntegrity={priceIntegrity} />);

    // Warning alert should be present
    expect(screen.getByText(/Not explained by charges found in the text:/)).toBeDefined();
    expect(screen.getByText(/This is a difference in the scanned price breakdown, not proof of deception/i)).toBeDefined();
    expect(screen.getAllByText(/\+USD 8\.00/).length).toBeGreaterThan(0);

    // Breakdown fields should be present
    expect(screen.getByText('Checkout Subtotal:')).toBeDefined();
    expect(screen.getByText('Processing Fee:')).toBeDefined();
    expect(screen.getByText('Service Fee:')).toBeDefined();
    expect(screen.getByText('Final Total:')).toBeDefined();
    expect(screen.getByText(/Final total above subtotal:/)).toBeDefined();
    expect(screen.getByText(/itemized charges detected in the scanned text/i)).toBeDefined();
  });

  it('unambiguously distinguishes difference from unexplained_difference for the $15 / $6 example', () => {
    const priceIntegrity: PriceIntegrity = {
      observations: [
        { stage: 'subtotal', amount: { amount: '50.00', currency: 'USD', kind: 'one_time' } },
        { stage: 'shipping', amount: { amount: '5.00', currency: 'USD', kind: 'fee' } },
        { stage: 'estimated tax', amount: { amount: '4.00', currency: 'USD', kind: 'fee' } },
        { stage: 'total', amount: { amount: '65.00', currency: 'USD', kind: 'one_time' } },
      ],
      checkout_subtotal: { amount: '50.00', currency: 'USD', kind: 'one_time' },
      explicit_fees: [
        { name: 'Shipping', amount: { amount: '5.00', currency: 'USD', kind: 'fee' } },
        { name: 'Estimated Tax', amount: { amount: '4.00', currency: 'USD', kind: 'fee' } },
      ],
      final_total: { amount: '65.00', currency: 'USD', kind: 'one_time' },
      difference: { amount: '15.00', currency: 'USD', kind: 'fee' },
      unexplained_difference: { amount: '6.00', currency: 'USD', kind: 'fee' },
      reason: 'unclear',
    };

    render(<PriceIntegrityTrail priceIntegrity={priceIntegrity} />);

    // Difference from subtotal ($15.00) is labeled in status footer
    expect(screen.getByText(/Final total above subtotal:/)).toBeDefined();
    expect(screen.getByText('USD 15.00')).toBeDefined();

    // Unexplained discrepancy ($6.00) is clearly labeled in alert banner and breakdown
    expect(screen.getByText(/Unexplained Discrepancy:/)).toBeDefined();
    expect(screen.getAllByText(/\+USD 6\.00/).length).toBe(2);
  });

  it('renders discounts with negative prefix and emerald styling', () => {
    const priceIntegrity: PriceIntegrity = {
      observations: [],
      checkout_subtotal: { amount: '100.00', currency: 'USD', kind: 'one_time' },
      explicit_fees: [
        { name: 'Discount', amount: { amount: '-15.00', currency: 'USD', kind: 'fee' } },
        { name: 'Shipping', amount: { amount: '10.00', currency: 'USD', kind: 'fee' } },
      ],
      final_total: { amount: '95.00', currency: 'USD', kind: 'one_time' },
      difference: { amount: '5.00', currency: 'USD', kind: 'fee' },
      reason: 'disclosed_tax_or_shipping',
    };

    render(<PriceIntegrityTrail priceIntegrity={priceIntegrity} />);
    expect(screen.getByText('-USD 15.00')).toBeDefined();
    expect(screen.getByText('USD 10.00')).toBeDefined();
    expect(screen.getByText('USD 95.00')).toBeDefined();
  });
});

describe('CommitmentMap Component Multi-Plan vs Single-Plan', () => {
  it('renders page-level distinction and does not imply selected plan when isMultiPlan is true', () => {
    const multiPlanMap: CommitmentMapType = {
      amount_due_now: null,
      future_charge: null,
      billing_interval: 'monthly',
      trial_duration: null,
      future_charge_trigger: null,
      cancellation_terms: 'Cancel anytime in account settings',
      unknowns: ['Plan selection is not established; see plan breakdown for individual tier pricing.'],
    };

    render(<CommitmentMap commitmentMap={multiPlanMap} isMultiPlan={true} />);

    // Page-level header and badge
    expect(screen.getByText('Page-Level Financial Summary')).toBeDefined();
    expect(screen.getByText('Multiple Plans')).toBeDefined();

    // General terms guidance
    expect(screen.getAllByText(/Plan selection is not established/).length).toBeGreaterThan(0);

    // Varies by plan placeholders
    const variesElements = screen.getAllByText('Varies by plan (see breakdown below)');
    expect(variesElements.length).toBeGreaterThan(0);
  });

  it('renders single-plan financial commitment summary normally when isMultiPlan is false', () => {
    const singlePlanMap: CommitmentMapType = {
      amount_due_now: { amount: '29.99', currency: 'USD', kind: 'recurring', interval: 'monthly' },
      future_charge: { amount: '29.99', currency: 'USD', kind: 'recurring', interval: 'monthly' },
      billing_interval: 'monthly',
      trial_duration: '7 days',
      future_charge_trigger: 'After 7 days trial ends',
      cancellation_terms: 'Cancel anytime',
      unknowns: [],
    };

    render(<CommitmentMap commitmentMap={singlePlanMap} isMultiPlan={false} />);

    expect(screen.getByText('Financial Commitment Summary')).toBeDefined();
    expect(screen.queryByText('Multiple Plans')).toBeNull();
    expect(screen.getAllByText('USD 29.99 / monthly').length).toBe(2);
    expect(screen.getByText('7 days')).toBeDefined();
  });
});
