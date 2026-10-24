import React from 'react';
import type { CommitmentMap, MoneyValue } from '../types/api';

interface SafeAlternativeFinderProps {
  commitmentMap: CommitmentMap;
  isMultiPlan?: boolean;
}

function formatCharge(
  charge?: MoneyValue | null,
  billingInterval?: string | null,
): string {
  if (!charge?.amount) {
    return 'Not found in the text checked';
  }

  const interval = charge.interval || billingInterval;
  const intervalLabels: Record<string, string> = {
    annually: 'year',
    biannually: 'six months',
    biweekly: 'two weeks',
    daily: 'day',
    monthly: 'month',
    quarterly: 'quarter',
    weekly: 'week',
  };
  const amount = `${charge.currency ? `${charge.currency} ` : ''}${charge.amount}`;
  return interval
    ? `${amount} per ${intervalLabels[interval] || interval}`
    : amount;
}

export function SafeAlternativeFinder({
  commitmentMap,
  isMultiPlan = false,
}: SafeAlternativeFinderProps) {
  const { future_charge, billing_interval, trial_duration, cancellation_terms } =
    commitmentMap;

  return (
    <section
      aria-labelledby="safe-alternative-heading"
      className="bg-white rounded-lg border border-slate-200 p-4 shadow-sm space-y-3"
    >
      <div className="border-b border-slate-100 pb-2">
        <h3
          id="safe-alternative-heading"
          className="text-sm font-semibold text-slate-800"
        >
          Compare a clearer option
        </h3>
        <p className="mt-1 text-xs text-slate-600">
          No verified alternative listings are available, so we won’t name a
          provider or invent its terms. Use these details to compare another
          option.
        </p>
      </div>

      <div className="rounded-md bg-slate-50 border border-slate-200 p-3">
        <h4 className="text-xs font-semibold text-slate-700">
          {isMultiPlan ? 'This page lists multiple plans' : 'From this page scan'}
        </h4>
        {isMultiPlan ? (
          <p className="mt-1 text-xs text-slate-600">
            No plan is selected. Choose the tier you are considering in the
            breakdown above before comparing its terms.
          </p>
        ) : (
          <dl className="mt-2 grid grid-cols-2 gap-x-3 gap-y-2 text-xs">
            <dt className="text-slate-500">Recurring charge</dt>
            <dd className="text-right font-medium text-slate-800">
              {formatCharge(future_charge, billing_interval)}
            </dd>
            <dt className="text-slate-500">Trial duration</dt>
            <dd className="text-right font-medium text-slate-800">
              {trial_duration || 'Not found in the text checked'}
            </dd>
            <dt className="text-slate-500">Cancellation terms</dt>
            <dd className="text-right font-medium text-slate-800">
              {cancellation_terms || 'Not found in the text checked'}
            </dd>
          </dl>
        )}
      </div>

      <div>
        <h4 className="text-xs font-semibold text-slate-700">
          Check another option for
        </h4>
        <ul className="mt-1 list-disc pl-4 space-y-1 text-xs text-slate-600">
          <li>A clearly stated recurring price and billing frequency.</li>
          <li>
            If there is a trial, its length, renewal price, and when billing
            begins.
          </li>
          <li>How to cancel and any stated cancellation cutoff.</li>
        </ul>
      </div>

      <p className="text-[11px] text-slate-500">
        These are comparison criteria, not a verified recommendation. Check the
        other option’s own terms before deciding.
      </p>
    </section>
  );
}
