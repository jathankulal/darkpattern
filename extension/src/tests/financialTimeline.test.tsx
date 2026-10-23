import React from 'react';
import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { FinancialTimeline } from '../components/FinancialTimeline';
import type { FinancialTimeline as FinancialTimelineType } from '../types/api';

describe('FinancialTimeline Component', () => {
  it('renders null when timeline is null or empty without note', () => {
    const { container } = render(<FinancialTimeline timeline={null} />);
    expect(container.firstChild).toBeNull();

    const emptyTimeline: FinancialTimelineType = {
      events: [],
      annualized_cost: null,
      annualized_cost_assumptions: null,
      note: null,
    };
    const { container: emptyContainer } = render(<FinancialTimeline timeline={emptyTimeline} />);
    expect(emptyContainer.firstChild).toBeNull();
  });

  it('renders note when present even without events', () => {
    const noteTimeline: FinancialTimelineType = {
      events: [],
      annualized_cost: null,
      annualized_cost_assumptions: null,
      note: 'One-time transaction. Annualized cost is not applicable.',
    };

    render(<FinancialTimeline timeline={noteTimeline} />);
    expect(screen.getByText(/One-time transaction/i)).toBeDefined();
    expect(screen.getByText(/Financial Commitment Timeline/i)).toBeDefined();
  });

  it('renders trial to recurring subscription milestones and critical action cutoff', () => {
    const trialTimeline: FinancialTimelineType = {
      events: [
        {
          timepoint: 'Today',
          title: 'Free Trial Begins',
          amount: { amount: '0', currency: 'USD', kind: 'trial' },
          value_type: 'observed',
          description: 'Start of 14-day trial period.',
          evidence_text: '14-day free trial',
          is_critical_action: false,
        },
        {
          timepoint: 'Before Trial Ends',
          title: 'Cancellation Cutoff Deadline',
          amount: null,
          value_type: 'observed',
          description: 'Cancellation required (24 hours prior) to prevent auto-renewal charge.',
          evidence_text: 'Cancel at least 24 hours before trial ends',
          is_critical_action: true,
        },
        {
          timepoint: 'After 14-day free trial',
          title: 'First Recurring Charge',
          amount: { amount: '49.99', currency: 'USD', kind: 'recurring', interval: 'monthly' },
          value_type: 'observed',
          description: 'Trial transitions to recurring charge of USD 49.99 per month unless cancelled.',
          evidence_text: '$49.99/month thereafter',
          is_critical_action: false,
        },
        {
          timepoint: '12-Month Projection',
          title: 'Annualized Recurring Commitment',
          amount: { amount: '599.88', currency: 'USD', kind: 'recurring', interval: 'annually' },
          value_type: 'calculated',
          description: 'Projected 12-month recurring expenditure of USD 599.88 based on stated interval.',
          evidence_text: '$49.99/month',
          is_critical_action: false,
        },
      ],
      annualized_cost: { amount: '599.88', currency: 'USD', kind: 'recurring', interval: 'annually' },
      annualized_cost_assumptions: 'Calculated deterministically as 12 × USD 49.99 over a 12-month period.',
      note: null,
    };

    render(<FinancialTimeline timeline={trialTimeline} />);

    // Milestones header
    expect(screen.getByText('4 milestones')).toBeDefined();

    // Event titles
    expect(screen.getByText('Free Trial Begins')).toBeDefined();
    expect(screen.getByText('Cancellation Cutoff Deadline')).toBeDefined();
    expect(screen.getByText('First Recurring Charge')).toBeDefined();
    expect(screen.getByText('Annualized Recurring Commitment')).toBeDefined();

    // Critical action badge
    expect(screen.getByText('⚠️ Action Required')).toBeDefined();

    // Value type badges
    expect(screen.getAllByText('Stated').length).toBeGreaterThan(0);
    expect(screen.getByText('Calculated')).toBeDefined();

    // Annualized projection callout
    expect(screen.getByText(/12-Month Projected Commitment/i)).toBeDefined();
    expect(screen.getAllByText('USD 599.88 / annually').length).toBe(2);
    expect(screen.getByText(/Calculated deterministically as 12 × USD 49.99/i)).toBeDefined();

    // Verified quote toggling
    const viewQuoteBtns = screen.getAllByText(/View verified quote/i);
    expect(viewQuoteBtns.length).toBeGreaterThan(0);

    fireEvent.click(viewQuoteBtns[0]);
    expect(screen.getByText(/"14-day free trial"/i)).toBeDefined();
  });

  it('renders unresolved renewal charge with high-visibility indicator', () => {
    const unresolvedTimeline: FinancialTimelineType = {
      events: [
        {
          timepoint: 'Today',
          title: 'Free Trial Begins',
          amount: { amount: '0', currency: 'USD', kind: 'trial' },
          value_type: 'observed',
          description: 'Start of 7-day trial.',
          evidence_text: '7-day trial',
          is_critical_action: false,
        },
        {
          timepoint: 'After 7-day trial',
          title: 'Renewal Charge Amount (Undisclosed)',
          amount: null,
          value_type: 'unresolved',
          description: 'The renewal charge amount upon trial expiration is not disclosed in the visible text.',
          evidence_text: '',
          is_critical_action: true,
        },
      ],
      annualized_cost: null,
      annualized_cost_assumptions: null,
      note: 'Renewal price after trial is not stated on this page.',
    };

    render(<FinancialTimeline timeline={unresolvedTimeline} />);

    expect(screen.getByText('Renewal Charge Amount (Undisclosed)')).toBeDefined();
    expect(screen.getByText('Unresolved')).toBeDefined();
    expect(screen.getByText('⚠️ Action Required')).toBeDefined();
    expect(screen.getByText(/Renewal price after trial is not stated on this page/i)).toBeDefined();
  });
});
