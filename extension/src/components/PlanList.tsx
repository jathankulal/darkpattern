import React from 'react';
import type { PlanSummary, MoneyValue } from '../types/api';

interface PlanListProps {
  plans: PlanSummary[];
}

function formatMoney(money?: MoneyValue | null): string {
  if (!money || !money.amount) {
    return 'Not found on page';
  }
  const prefix = money.currency ? `${money.currency} ` : '';
  const intervalStr = money.interval ? ` / ${money.interval}` : '';
  return `${prefix}${money.amount}${intervalStr}`;
}

export function PlanList({ plans }: PlanListProps) {
  if (!plans || plans.length === 0) {
    return null;
  }

  return (
    <section
      aria-labelledby="plan-list-heading"
      className="bg-white rounded-lg border border-slate-200 p-4 shadow-sm space-y-3"
    >
      <div className="flex items-center justify-between border-b border-slate-100 pb-2">
        <h3 id="plan-list-heading" className="text-sm font-semibold text-slate-800 flex items-center gap-1.5">
          <svg className="w-4 h-4 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
          </svg>
          Pricing Plans Breakdown ({plans.length})
        </h3>
      </div>

      <div className="space-y-3">
        {plans.map((plan, idx) => (
          <div
            key={idx}
            className={`p-3 rounded-lg border text-xs transition-colors ${
              plan.is_ambiguous
                ? 'bg-amber-50/50 border-amber-200'
                : 'bg-slate-50 border-slate-200'
            }`}
          >
            {/* Plan Header */}
            <div className="flex items-center justify-between mb-2">
              <h4 className="font-semibold text-slate-900 text-sm">{plan.plan_name}</h4>
              {plan.is_ambiguous ? (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-amber-100 text-amber-800 border border-amber-300">
                  ⚠️ Ambiguous
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-emerald-100 text-emerald-800 border border-emerald-200">
                  ✓ Confident
                </span>
              )}
            </div>

            {/* Ambiguity Alert */}
            {plan.is_ambiguous && plan.ambiguity_reason && (
              <div className="mb-2 p-2 rounded bg-amber-100/70 border border-amber-200 text-amber-900 text-[11px]">
                <strong className="font-medium">Uncertainty Note: </strong>
                {plan.ambiguity_reason}
              </div>
            )}

            {/* Plan Details Grid */}
            <dl className="grid grid-cols-2 gap-2 text-xs">
              <div className="bg-white p-2 rounded border border-slate-100">
                <dt className="text-slate-500 font-medium">Due Now</dt>
                <dd className={`mt-0.5 font-semibold ${plan.amount_due_now ? 'text-slate-900' : 'text-slate-400 font-normal italic'}`}>
                  {formatMoney(plan.amount_due_now)}
                </dd>
              </div>

              <div className="bg-white p-2 rounded border border-slate-100">
                <dt className="text-slate-500 font-medium">Recurring Charge</dt>
                <dd className={`mt-0.5 font-semibold ${plan.future_charge ? 'text-slate-900' : 'text-slate-400 font-normal italic'}`}>
                  {formatMoney(plan.future_charge)}
                </dd>
              </div>

              <div className="bg-white p-2 rounded border border-slate-100">
                <dt className="text-slate-500 font-medium">Billing Interval</dt>
                <dd className="mt-0.5 text-slate-700">
                  {plan.billing_interval || 'Not specified'}
                </dd>
              </div>

              <div className="bg-white p-2 rounded border border-slate-100">
                <dt className="text-slate-500 font-medium">Trial Duration</dt>
                <dd className="mt-0.5 text-slate-700">
                  {plan.trial_duration || 'No trial'}
                </dd>
              </div>

              {plan.cancellation_terms && (
                <div className="col-span-2 bg-white p-2 rounded border border-slate-100">
                  <dt className="text-slate-500 font-medium">Cancellation Terms</dt>
                  <dd className="mt-0.5 text-slate-700">{plan.cancellation_terms}</dd>
                </div>
              )}
            </dl>

            {/* Plan-specific Unknowns */}
            {plan.unknowns && plan.unknowns.length > 0 && (
              <div className="mt-2 pt-2 border-t border-slate-200/60">
                <span className="text-[11px] font-medium text-slate-600 block mb-0.5">Missing / Unclear Terms:</span>
                <ul className="list-disc pl-4 text-[11px] text-slate-500 space-y-0.5">
                  {plan.unknowns.map((u, i) => (
                    <li key={i}>{u}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}
