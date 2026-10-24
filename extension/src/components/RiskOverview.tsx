import React from 'react';
import type { AnalyzeResponse, Finding, MoneyValue } from '../types/api';
import { FindingCard } from './FindingCard';
import { assessDarkPatternRisk, getPrimaryFindings } from '../lib/riskScore';

function formatMoney(value: MoneyValue): string {
  const amount = `${value.currency ? `${value.currency} ` : ''}${value.amount}`;
  return value.interval ? `${amount} / ${value.interval}` : amount;
}

function getFinancialImpact(data: AnalyzeResponse): { title: string; detail: string } | null {
  const discrepancy = data.price_integrity.unexplained_difference;
  if (discrepancy) {
    return {
      title: 'Unexplained checkout difference',
      detail: `${formatMoney(discrepancy)} is not accounted for by charges detected in the scanned text. This is not proof of deception.`,
    };
  }

  if (data.timeline?.annualized_cost) {
    return {
      title: 'Estimated 12-month cost',
      detail: formatMoney(data.timeline.annualized_cost),
    };
  }

  const futureCharge = data.commitment_map.future_charge;
  if (futureCharge) {
    const trial = data.commitment_map.trial_duration;
    return {
      title: trial ? 'Recurring charge after the trial' : 'Recurring charge shown',
      detail: `${formatMoney(futureCharge)}${trial ? ` after ${trial}` : ''}`,
    };
  }

  const dueNow = data.commitment_map.amount_due_now;
  if (dueNow?.kind === 'one_time') {
    return { title: 'One-time amount shown', detail: formatMoney(dueNow) };
  }

  return null;
}

function contributorTitle(finding: Finding): string {
  if (finding.category === 'urgency_pressure') return 'Time-pressure language';
  return 'Unclear trial renewal price';
}

export function RiskOverview({ data }: { data: AnalyzeResponse }) {
  const assessment = assessDarkPatternRisk(data.findings);
  const primaryFindings = getPrimaryFindings(data.findings);
  const financialImpact = getFinancialImpact(data);
  const ringColor =
    assessment.score !== null && assessment.score >= 60
      ? '#dc2626'
      : assessment.score !== null && assessment.score >= 40
        ? '#d97706'
        : '#2563eb';

  return (
    <section aria-labelledby="risk-overview-heading" className="space-y-3">
      <div className="bg-white border border-slate-200 rounded-lg p-3 shadow-xs">
        <h2 id="risk-overview-heading" className="text-sm font-semibold text-slate-900">
          Dark Pattern Risk
        </h2>
        <div className="mt-3 flex items-center gap-3">
          <div
            role={assessment.score === null ? 'img' : 'meter'}
            aria-label={
              assessment.score === null
                ? 'Dark-pattern risk score unavailable: insufficient evidence'
                : `Dark-pattern risk score ${assessment.score} out of 100`
            }
            aria-valuemin={assessment.score === null ? undefined : 0}
            aria-valuemax={assessment.score === null ? undefined : 100}
            aria-valuenow={assessment.score ?? undefined}
            className="h-16 w-16 shrink-0 rounded-full flex items-center justify-center bg-slate-100 border-4 border-blue-200"
            style={
              assessment.score === null
                ? undefined
                : {
                    background: `conic-gradient(${ringColor} ${assessment.score * 3.6}deg, #e2e8f0 0deg)`,
                  }
            }
          >
            <span className="h-12 w-12 rounded-full bg-white flex items-center justify-center text-xl font-bold text-slate-900">
              {assessment.score === null ? '—' : assessment.score}
            </span>
          </div>
          <div>
            <h3 className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
              Final verdict
            </h3>
            <p className="text-sm font-semibold text-slate-900">{assessment.label}</p>
            <p className="text-xs text-slate-600 mt-0.5 leading-relaxed">{assessment.verdict}</p>
          </div>
        </div>
        <p className="mt-2 text-[10px] leading-relaxed text-slate-500">
          This score reflects detected evidence, not a calibrated probability. A subscription,
          ordinary fee, or cancellation policy does not raise it by itself.
        </p>
        {assessment.contributors.length > 0 && (
          <div className="mt-2 border-t border-slate-100 pt-2">
            <h3 className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
              Findings contributing to the score
            </h3>
            <ul className="mt-1 space-y-1">
              {assessment.contributors.map((finding) => (
                <li key={finding.id} className="text-xs text-slate-700">
                  {contributorTitle(finding)} — {finding.severity} severity,{' '}
                  {finding.evidence_level} evidence
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      <section aria-labelledby="main-issues-heading" className="space-y-2">
        <h2 id="main-issues-heading" className="text-xs font-bold uppercase tracking-wide text-slate-700">
          Main issues found
        </h2>
        {primaryFindings.length > 0 ? (
          primaryFindings.map((finding) => (
            <FindingCard key={finding.id} finding={finding} initiallyExpanded />
          ))
        ) : (
          <div className="bg-white border border-slate-200 rounded-lg p-3 text-xs text-slate-600">
            We didn’t find a supported warning sign in the text we checked. This scan may not
            include everything on the page.
          </div>
        )}
      </section>

      {financialImpact && (
        <section
          aria-labelledby="financial-impact-heading"
          className="bg-blue-50 border border-blue-200 rounded-lg p-3"
        >
          <h2 id="financial-impact-heading" className="text-xs font-semibold text-blue-900">
            Financial impact
          </h2>
          <p className="mt-1 text-xs font-medium text-blue-900">{financialImpact.title}</p>
          <p className="text-xs text-blue-800">{financialImpact.detail}</p>
        </section>
      )}
    </section>
  );
}
