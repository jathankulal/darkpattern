import React from 'react';
import type { PriceIntegrity, MoneyValue, PriceIntegrityReason } from '../types/api';

interface PriceIntegrityTrailProps {
  priceIntegrity: PriceIntegrity;
}

const REASON_LABELS: Record<PriceIntegrityReason, string> = {
  known: 'Price consistent across observed stages',
  disclosed_tax_or_shipping: 'Price changed due to disclosed taxes, fees, or shipping',
  unclear: 'Price change reason is unclear or unexplained',
  not_comparable: 'Comparison not possible across stages',
};

function formatMoney(m: MoneyValue): string {
  const isNegative = m.amount.startsWith('-');
  const cleanAmount = isNegative ? m.amount.substring(1) : m.amount;
  const prefix = m.currency ? `${m.currency} ` : '';
  const interval = m.interval ? ` / ${m.interval}` : '';
  return isNegative ? `-${prefix}${cleanAmount}${interval}` : `${prefix}${cleanAmount}${interval}`;
}

export function PriceIntegrityTrail({ priceIntegrity }: PriceIntegrityTrailProps) {
  const {
    observations = [],
    difference,
    reason,
    advertised_price,
    checkout_subtotal,
    explicit_fees = [],
    final_total,
    unexplained_difference,
    note,
  } = priceIntegrity;

  const hasCheckoutComparison = Boolean(checkout_subtotal || advertised_price || final_total || (explicit_fees && explicit_fees.length > 0));

  return (
    <section
      aria-labelledby="price-integrity-heading"
      className="bg-white rounded-lg border border-slate-200 p-4 shadow-sm space-y-3"
    >
      <div className="flex items-center justify-between border-b border-slate-100 pb-2">
        <h3
          id="price-integrity-heading"
          className="text-sm font-semibold text-slate-800 flex items-center gap-1.5"
        >
          <svg
            className="w-4 h-4 text-blue-600"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth="2"
              d="M7 12l3-3 3 3 4-4M8 21l4-4 4 4M3 4h18M4 4h16v12a1 1 0 01-1 1H5a1 1 0 01-1-1V4z"
            />
          </svg>
          Price Integrity & Checkout Trail
        </h3>
      </div>

      {/* Unexplained Difference Warning Banner */}
      {unexplained_difference && (
        <div
          role="alert"
          className="bg-rose-50 border border-rose-200 rounded-lg p-2.5 text-xs text-rose-900 flex items-start gap-2"
        >
          <span className="text-rose-600 font-bold" aria-hidden="true">⚠️</span>
          <div>
            <strong className="font-semibold">Unexplained Price Difference: </strong>
            Final total is{' '}
            <strong className="font-bold underline">
              +{formatMoney(unexplained_difference)}
            </strong>{' '}
            higher than the base price plus disclosed fees.
          </div>
        </div>
      )}

      {/* Informational note for NOT_COMPARABLE or incomplete evidence */}
      {note && (
        <div
          role="note"
          className="bg-blue-50 border border-blue-200 rounded-lg p-2.5 text-xs text-blue-900 flex items-start gap-2"
        >
          <span className="text-blue-600 font-bold" aria-hidden="true">ℹ️</span>
          <span>{note}</span>
        </div>
      )}

      {/* Checkout Itemized Breakdown */}
      {hasCheckoutComparison && (
        <div className="bg-slate-50 p-2.5 rounded-lg border border-slate-200 text-xs space-y-1.5">
          <div className="text-[11px] font-semibold text-slate-700 uppercase tracking-wider mb-1">
            Checkout Calculation Breakdown
          </div>

          {advertised_price && (
            <div className="flex items-center justify-between text-slate-600">
              <span>Advertised Price:</span>
              <span className="font-medium text-slate-800">{formatMoney(advertised_price)}</span>
            </div>
          )}

          {checkout_subtotal && (
            <div className="flex items-center justify-between text-slate-600">
              <span>Checkout Subtotal:</span>
              <span className="font-medium text-slate-800">{formatMoney(checkout_subtotal)}</span>
            </div>
          )}

          {explicit_fees.length > 0 && (
            <div className="pt-1 border-t border-slate-200/70 space-y-1">
              <span className="text-[11px] font-medium text-slate-500 block">Disclosed Fees, Taxes & Discounts:</span>
              {explicit_fees.map((fee, idx) => {
                const isDiscount = fee.amount.amount.startsWith('-');
                return (
                  <div key={idx} className="flex items-center justify-between pl-2 text-slate-600">
                    <span>{fee.name}:</span>
                    <span className={`font-medium ${isDiscount ? 'text-emerald-700 font-semibold' : 'text-slate-800'}`}>
                      {formatMoney(fee.amount)}
                    </span>
                  </div>
                );
              })}
            </div>
          )}

          {unexplained_difference && (
            <div className="pt-1 border-t border-rose-200/70 flex items-center justify-between text-xs font-semibold text-rose-700 bg-rose-50/70 p-1.5 rounded">
              <span>Unexplained Discrepancy:</span>
              <span>+{formatMoney(unexplained_difference)}</span>
            </div>
          )}

          {final_total && (
            <div className="pt-1.5 border-t border-slate-300 flex items-center justify-between text-xs font-semibold text-slate-900">
              <span>Final Total:</span>
              <span className="text-sm">{formatMoney(final_total)}</span>
            </div>
          )}
        </div>
      )}

      {/* Observation Timeline (if available) */}
      {observations.length > 1 && (
        <div className="space-y-2 text-xs pt-1">
          <span className="text-[11px] font-semibold text-slate-600 uppercase tracking-wider">
            Observed Stages
          </span>
          <ol className="relative border-l border-slate-200 ml-2 space-y-2 py-1">
            {observations.map((obs, idx) => (
              <li key={idx} className="ml-3">
                <span className="absolute -left-1.5 mt-1.5 h-3 w-3 rounded-full border-2 border-white bg-blue-500" />
                <div className="flex items-baseline justify-between gap-2">
                  <span className="font-medium text-slate-700 capitalize">{obs.stage}</span>
                  <span className="font-semibold text-slate-900">{formatMoney(obs.amount)}</span>
                </div>
                {obs.context && (
                  <p className="text-[11px] text-slate-500 mt-0.5">{obs.context}</p>
                )}
              </li>
            ))}
          </ol>
        </div>
      )}

      {/* Status Footer */}
      <div className="pt-1 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-500">
        <div>
          <span className="font-medium text-slate-700">Status: </span>
          <span>{REASON_LABELS[reason] ?? reason}</span>
        </div>
        {difference && (
          <div>
            <span className="font-medium text-slate-700">
              {hasCheckoutComparison ? 'Total Added to Subtotal: ' : 'Stage Price Difference: '}
            </span>
            <span className="font-semibold text-slate-900">{formatMoney(difference)}</span>
          </div>
        )}
      </div>
    </section>
  );
}
