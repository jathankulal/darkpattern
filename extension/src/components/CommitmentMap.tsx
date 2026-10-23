import React from 'react';
import type { CommitmentMap as CommitmentMapType, MoneyValue } from '../types/api';

interface CommitmentMapProps {
  commitmentMap: CommitmentMapType;
  isMultiPlan?: boolean;
}

function formatMoney(money?: MoneyValue | null, isMultiPlan?: boolean): string {
  if (!money || !money.amount) {
    return isMultiPlan ? 'Varies by plan (see breakdown below)' : 'Not found on this page';
  }
  const prefix = money.currency ? `${money.currency} ` : '';
  const intervalStr = money.interval ? ` / ${money.interval}` : '';
  return `${prefix}${money.amount}${intervalStr}`;
}

export function CommitmentMap({ commitmentMap, isMultiPlan = false }: CommitmentMapProps) {
  const {
    amount_due_now,
    future_charge,
    billing_interval,
    trial_duration,
    future_charge_trigger,
    cancellation_terms,
    unknowns = [],
  } = commitmentMap;

  return (
    <section
      aria-labelledby="commitment-map-heading"
      className="bg-white rounded-lg border border-slate-200 p-4 shadow-sm"
    >
      <div className="flex items-center justify-between mb-3 border-b border-slate-100 pb-2">
        <h3 id="commitment-map-heading" className="text-sm font-semibold text-slate-800 flex items-center gap-1.5">
          <svg className="w-4 h-4 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          {isMultiPlan ? 'Page-Level Financial Summary' : 'Financial Commitment Summary'}
        </h3>
        {isMultiPlan && (
          <span className="text-[11px] font-medium text-blue-700 bg-blue-50 border border-blue-200 px-2 py-0.5 rounded">
            Multiple Plans
          </span>
        )}
      </div>

      {isMultiPlan && (
        <div className="mb-3 p-2 bg-slate-50 border border-slate-200 rounded text-xs text-slate-600">
          <strong className="text-slate-700">General terms: </strong>
          Plan selection is not established. Specific prices, trials, and intervals are listed by tier in the <strong>Pricing Plans Breakdown</strong> below.
        </div>
      )}

      <dl className="grid grid-cols-2 gap-x-3 gap-y-3 text-xs">
        <div className="bg-slate-50 p-2.5 rounded border border-slate-100">
          <dt className="text-slate-500 font-medium">Due Now</dt>
          <dd className={`mt-0.5 text-sm font-semibold ${amount_due_now ? 'text-slate-900' : 'text-slate-400 font-normal italic'}`}>
            {formatMoney(amount_due_now, isMultiPlan)}
          </dd>
        </div>

        <div className="bg-slate-50 p-2.5 rounded border border-slate-100">
          <dt className="text-slate-500 font-medium">Future / Recurring</dt>
          <dd className={`mt-0.5 text-sm font-semibold ${future_charge ? 'text-slate-900' : 'text-slate-400 font-normal italic'}`}>
            {formatMoney(future_charge, isMultiPlan)}
          </dd>
        </div>

        <div className="bg-slate-50 p-2 rounded border border-slate-100">
          <dt className="text-slate-500 font-medium">Billing Interval</dt>
          <dd className={`mt-0.5 ${billing_interval ? 'text-slate-800 font-medium' : 'text-slate-400 italic'}`}>
            {billing_interval || (isMultiPlan ? 'Varies by plan' : 'Not found on this page')}
          </dd>
        </div>

        <div className="bg-slate-50 p-2 rounded border border-slate-100">
          <dt className="text-slate-500 font-medium">Trial Duration</dt>
          <dd className={`mt-0.5 ${trial_duration ? 'text-slate-800 font-medium' : 'text-slate-400 italic'}`}>
            {trial_duration || (isMultiPlan ? 'Plan-specific (see breakdown)' : 'Not found on this page')}
          </dd>
        </div>

        <div className="col-span-2 bg-slate-50 p-2 rounded border border-slate-100">
          <dt className="text-slate-500 font-medium">Future Charge Trigger</dt>
          <dd className={`mt-0.5 ${future_charge_trigger ? 'text-slate-800' : 'text-slate-400 italic'}`}>
            {future_charge_trigger || (isMultiPlan ? 'Plan-specific (see breakdown)' : 'Not found on this page')}
          </dd>
        </div>

        <div className="col-span-2 bg-slate-50 p-2 rounded border border-slate-100">
          <dt className="text-slate-500 font-medium">Cancellation & Refund Terms</dt>
          <dd className={`mt-0.5 ${cancellation_terms ? 'text-slate-800 leading-relaxed' : 'text-slate-400 italic'}`}>
            {cancellation_terms || 'Not found on this page'}
          </dd>
        </div>
      </dl>

      {unknowns.length > 0 && (
        <div className="mt-3 pt-2.5 border-t border-slate-100">
          <h4 className="text-xs font-medium text-amber-800 flex items-center gap-1 mb-1">
            <svg className="w-3.5 h-3.5 text-amber-600 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            Key Terms Not Stated on Page:
          </h4>
          <ul className="list-disc pl-5 text-xs text-slate-600 space-y-0.5">
            {unknowns.map((unknown, idx) => (
              <li key={idx}>{unknown}</li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
