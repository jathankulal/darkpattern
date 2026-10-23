import React, { useState } from 'react';
import type { FinancialTimeline as FinancialTimelineType, TimelineEvent, MoneyValue } from '../types/api';

interface FinancialTimelineProps {
  timeline?: FinancialTimelineType | null;
  title?: string;
  isCompact?: boolean;
}

function formatMoney(money?: MoneyValue | null): string {
  if (!money || !money.amount) return '';
  const prefix = money.currency ? `${money.currency} ` : '';
  const intervalStr = money.interval ? ` / ${money.interval}` : '';
  return `${prefix}${money.amount}${intervalStr}`;
}

export function FinancialTimeline({
  timeline,
  title = 'Financial Commitment Timeline',
  isCompact = false,
}: FinancialTimelineProps) {
  const [expandedEvidence, setExpandedEvidence] = useState<Record<number, boolean>>({});

  if (!timeline || (!timeline.events.length && !timeline.note && !timeline.annualized_cost)) {
    return null;
  }

  const toggleEvidence = (idx: number) => {
    setExpandedEvidence((prev) => ({ ...prev, [idx]: !prev[idx] }));
  };

  return (
    <section
      aria-labelledby="timeline-heading"
      className="bg-white rounded-lg border border-slate-200 p-4 shadow-xs space-y-3"
    >
      {/* Section Header */}
      <div className="flex items-center justify-between border-b border-slate-100 pb-2">
        <h3 id="timeline-heading" className="text-xs font-bold text-slate-800 uppercase tracking-wider flex items-center gap-1.5">
          <span className="text-blue-600" aria-hidden="true">⏱️</span>
          {title}
        </h3>
        {timeline.events.length > 0 && (
          <span className="text-[10px] text-slate-500 font-medium bg-slate-100 px-2 py-0.5 rounded-full">
            {timeline.events.length} milestone{timeline.events.length !== 1 ? 's' : ''}
          </span>
        )}
      </div>

      {/* Note / Disclaimers */}
      {timeline.note && (
        <div className="p-2.5 rounded-md bg-slate-50 border border-slate-200 text-xs text-slate-600 flex items-start gap-2">
          <span className="text-slate-500 text-sm" aria-hidden="true">ℹ️</span>
          <p className="leading-relaxed">{timeline.note}</p>
        </div>
      )}

      {/* Annualized Cost Projection Callout */}
      {timeline.annualized_cost && (
        <div className="bg-emerald-50/70 border border-emerald-200 rounded-lg p-3 text-xs space-y-1.5 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="font-semibold text-emerald-900 flex items-center gap-1">
              <span aria-hidden="true">📊</span> 12-Month Projected Commitment
            </span>
            <span className="text-sm font-bold text-emerald-800">
              {formatMoney(timeline.annualized_cost)}
            </span>
          </div>
          {timeline.annualized_cost_assumptions && (
            <p className="text-[11px] text-emerald-700 leading-normal pl-5">
              {timeline.annualized_cost_assumptions}
            </p>
          )}
        </div>
      )}

      {/* Chronological Event Rail */}
      {timeline.events.length > 0 && (
        <div className="relative pl-6 space-y-4 pt-1">
          {/* Vertical connecting rail line */}
          <div
            className="absolute left-2.5 top-2.5 bottom-2.5 w-0.5 bg-slate-200"
            aria-hidden="true"
          />

          {timeline.events.map((event: TimelineEvent, idx: number) => {
            const isCritical = Boolean(event.is_critical_action);
            const isCalculated = event.value_type === 'calculated';
            const isUnresolved = event.value_type === 'unresolved';

            return (
              <div key={idx} className="relative group">
                {/* Node icon / indicator */}
                <div
                  className={`absolute -left-6 top-1 w-3.5 h-3.5 rounded-full border-2 bg-white flex items-center justify-center ${
                    isCritical
                      ? 'border-rose-500 bg-rose-50 ring-2 ring-rose-200'
                      : isCalculated
                      ? 'border-emerald-500 bg-emerald-50'
                      : isUnresolved
                      ? 'border-amber-500 bg-amber-50 ring-2 ring-amber-100'
                      : 'border-blue-500 bg-blue-50'
                  }`}
                  aria-hidden="true"
                />

                {/* Event Card */}
                <div
                  className={`p-2.5 rounded-lg border text-xs transition-colors ${
                    isCritical
                      ? 'bg-rose-50/50 border-rose-200'
                      : isUnresolved
                      ? 'bg-amber-50/40 border-amber-200'
                      : isCalculated
                      ? 'bg-emerald-50/30 border-emerald-200'
                      : 'bg-slate-50 border-slate-200'
                  }`}
                >
                  {/* Timepoint and Badges */}
                  <div className="flex items-center justify-between gap-1 mb-1 flex-wrap">
                    <span className="font-bold text-slate-800 text-[11px]">
                      {event.timepoint}
                    </span>
                    <div className="flex items-center gap-1">
                      {isCritical && (
                        <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-rose-100 text-rose-700 border border-rose-300 flex items-center gap-0.5">
                          ⚠️ Action Required
                        </span>
                      )}
                      <span
                        className={`px-1.5 py-0.5 rounded text-[10px] font-medium border ${
                          isCalculated
                            ? 'bg-emerald-100 text-emerald-800 border-emerald-300'
                            : isUnresolved
                            ? 'bg-amber-100 text-amber-800 border-amber-300'
                            : 'bg-slate-200/80 text-slate-700 border-slate-300'
                        }`}
                      >
                        {isCalculated
                          ? 'Calculated'
                          : isUnresolved
                          ? 'Unresolved'
                          : 'Stated'}
                      </span>
                    </div>
                  </div>

                  {/* Title & Amount */}
                  <div className="flex items-baseline justify-between gap-2">
                    <h4 className="font-semibold text-slate-900 text-xs">
                      {event.title}
                    </h4>
                    {event.amount && (
                      <span className="font-bold text-slate-900 shrink-0">
                        {formatMoney(event.amount)}
                      </span>
                    )}
                  </div>

                  {/* Description */}
                  <p className="text-slate-600 text-[11px] mt-1 leading-relaxed">
                    {event.description}
                  </p>

                  {/* Verbatim Evidence Snippet */}
                  {event.evidence_text && !isCompact && (
                    <div className="mt-2 pt-1.5 border-t border-slate-200/60">
                      <button
                        type="button"
                        onClick={() => toggleEvidence(idx)}
                        className="text-[10px] text-blue-600 hover:text-blue-800 font-medium flex items-center gap-1 focus:outline-hidden"
                      >
                        <span>{expandedEvidence[idx] ? '▾ Hide' : '▸ View'} verified quote</span>
                      </button>
                      {expandedEvidence[idx] && (
                        <blockquote className="mt-1 p-1.5 bg-white border-l-2 border-blue-400 text-[10px] text-slate-600 italic font-mono rounded-r break-words">
                          "{event.evidence_text}"
                        </blockquote>
                      )}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
