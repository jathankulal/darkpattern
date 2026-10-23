import React, { useState } from 'react';
import type { Finding, FindingSeverity } from '../types/api';
import { CATEGORY_LABELS, SEVERITY_LABELS, EVIDENCE_LEVEL_LABELS } from '../lib/labels';

interface FindingCardProps {
  finding: Finding;
  initiallyExpanded?: boolean;
}

const SEVERITY_STYLES: Record<
  FindingSeverity,
  { bg: string; text: string; border: string; badge: string; icon: string }
> = {
  info: {
    bg: 'bg-slate-50',
    text: 'text-slate-700',
    border: 'border-slate-200',
    badge: 'bg-slate-100 text-slate-700 border-slate-300',
    icon: 'ℹ️',
  },
  low: {
    bg: 'bg-blue-50/50',
    text: 'text-blue-900',
    border: 'border-blue-200',
    badge: 'bg-blue-100 text-blue-800 border-blue-300',
    icon: '🔍',
  },
  medium: {
    bg: 'bg-amber-50/50',
    text: 'text-amber-900',
    border: 'border-amber-200',
    badge: 'bg-amber-100 text-amber-800 border-amber-300',
    icon: '⚠️',
  },
  high: {
    bg: 'bg-red-50/50',
    text: 'text-red-900',
    border: 'border-red-200',
    badge: 'bg-red-100 text-red-800 border-red-300',
    icon: '🛑',
  },
};

function formatConfidence(confidence: number): string {
  const pct = Math.round(confidence * 100);
  if (confidence >= 0.85) return `High confidence (${pct}%)`;
  if (confidence >= 0.6) return `Moderate confidence (${pct}%)`;
  return `Low confidence (${pct}%)`;
}

export function FindingCard({ finding, initiallyExpanded = true }: FindingCardProps) {
  const [expanded, setExpanded] = useState(initiallyExpanded);
  const style = SEVERITY_STYLES[finding.severity] ?? SEVERITY_STYLES.info;
  const categoryLabel = CATEGORY_LABELS[finding.category] ?? finding.category;
  const severityLabel = SEVERITY_LABELS[finding.severity] ?? finding.severity;
  const evidenceLevelLabel =
    EVIDENCE_LEVEL_LABELS[finding.evidence_level] ?? finding.evidence_level;

  return (
    <div
      className={`rounded-lg border ${style.border} ${style.bg} transition-all overflow-hidden shadow-xs`}
    >
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="w-full p-3 text-left flex items-start justify-between gap-2 hover:opacity-90 focus:outline-none focus:ring-2 focus:ring-blue-500"
        aria-expanded={expanded}
      >
        <div className="flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span
              className={`inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded border ${style.badge}`}
            >
              <span aria-hidden="true">{style.icon}</span>
              <span>{severityLabel}</span>
            </span>
            <span className="text-xs font-semibold text-slate-800">{categoryLabel}</span>
          </div>
          <p className="text-xs text-slate-600 mt-1 line-clamp-2 leading-relaxed">
            {finding.explanation}
          </p>
        </div>

        <svg
          className={`w-4 h-4 text-slate-400 mt-1 transform transition-transform ${
            expanded ? 'rotate-180' : ''
          }`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
          aria-hidden="true"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {expanded && (
        <div className="px-3 pb-3 pt-1 border-t border-slate-100 space-y-2.5 text-xs">
          {finding.evidence_text ? (
            <div>
              <span className="text-[11px] font-medium text-slate-500 uppercase tracking-wider block mb-1">
                Evidence from page
              </span>
              <blockquote className="bg-white/80 p-2 rounded border-l-3 border-blue-500 text-slate-700 italic font-mono text-[11px] break-words">
                "{finding.evidence_text}"
              </blockquote>
            </div>
          ) : (
            <div className="text-slate-500 italic text-[11px]">
              (No direct text match — term is absent from page)
            </div>
          )}

          <div className="grid grid-cols-2 gap-2 text-[11px] pt-1">
            <div>
              <span className="text-slate-500 font-medium block">Detection type</span>
              <span className="text-slate-700">{evidenceLevelLabel}</span>
            </div>
            <div>
              <span className="text-slate-500 font-medium block">Confidence</span>
              <span className="text-slate-700">{formatConfidence(finding.confidence)}</span>
            </div>
          </div>

          {finding.recommendation && (
            <div className="bg-white p-2 rounded border border-slate-200">
              <span className="font-semibold text-blue-900 block mb-0.5">What to check:</span>
              <p className="text-slate-700 leading-relaxed">{finding.recommendation}</p>
            </div>
          )}

          {finding.missing_information && finding.missing_information.length > 0 && (
            <div className="pt-1">
              <span className="text-slate-500 font-medium block mb-1">Missing details:</span>
              <ul className="list-disc pl-4 text-slate-600 space-y-0.5">
                {finding.missing_information.map((item, idx) => (
                  <li key={idx}>{item}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
