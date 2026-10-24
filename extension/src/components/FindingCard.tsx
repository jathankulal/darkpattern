import React, { useState } from 'react';
import type { Finding, FindingSeverity } from '../types/api';
import { SEVERITY_LABELS } from '../lib/labels';

interface FindingCardProps {
  finding: Finding;
  initiallyExpanded?: boolean;
  showExplanation?: boolean;
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

function getFindingPresentation(finding: Finding) {
  switch (finding.category) {
    case 'recurring_payment':
      if (finding.missing_information.length > 0) {
        return {
          title: 'The renewal price is not shown',
          explanation: "The page mentions recurring billing, but we couldn't find the price in the text we checked.",
          nextStep: 'Check the amount and billing schedule before paying.',
        };
      }
      return {
        title: 'You may be charged again',
        explanation: 'The page says this payment renews automatically.',
        nextStep: 'Check the renewal price and how to cancel before signing up.',
      };
    case 'free_trial_conversion':
      return {
        title: 'This free trial may become a paid subscription',
        explanation: 'The page says the trial is followed by a paid subscription.',
        nextStep: 'Check when the trial ends and what you will be charged.',
      };
    case 'future_charge_disclosure':
      return {
        title: "The trial's later price is not clear",
        explanation: "The page describes a trial, but we couldn't find its later price in the text we checked.",
        nextStep: 'Confirm the price before starting the trial.',
      };
    case 'additional_fee':
      return {
        title: 'The checkout total is higher than the listed charges',
        explanation: 'The final total is higher than the price and fees listed separately.',
        nextStep: 'Review the price breakdown or ask the seller about the difference before paying.',
      };
    case 'cancellation_refund_clarity':
      return {
        title: 'There is a cancellation deadline',
        explanation: 'The page gives a time limit for cancelling.',
        nextStep: 'Make a note of the deadline if you sign up.',
      };
    case 'urgency_pressure':
      return {
        title: 'The page is urging you to act quickly',
        explanation: 'A countdown or limited-availability message appears on the page. This alone does not show that the offer is deceptive.',
        nextStep: 'Take time to decide whether the offer suits you.',
      };
    case 'missing_commitment_info':
      return {
        title: 'Check how to cancel',
        explanation: "The text we checked doesn't show how to cancel.",
        nextStep: 'Before signing up, check the account settings or terms for how to cancel.',
      };
  }
}

export function FindingCard({
  finding,
  initiallyExpanded = true,
  showExplanation = true,
}: FindingCardProps) {
  const [expanded, setExpanded] = useState(initiallyExpanded);
  const style = SEVERITY_STYLES[finding.severity] ?? SEVERITY_STYLES.info;
  const severityLabel = SEVERITY_LABELS[finding.severity] ?? finding.severity;
  const presentation = getFindingPresentation(finding);

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
            <span role="heading" aria-level={4} className="text-xs font-semibold text-slate-800">
              {presentation.title}
            </span>
          </div>
          {showExplanation && (
            <p className="text-xs text-slate-600 mt-1 line-clamp-2 leading-relaxed">
              {presentation.explanation}
            </p>
          )}
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
                Why we're warning you
              </span>
              <blockquote className="bg-white/80 p-2 rounded border-l-3 border-blue-500 text-slate-700 italic font-mono text-[11px] break-words">
                {finding.evidence_text}
              </blockquote>
            </div>
          ) : (
            <div className="text-slate-500 text-[11px]">
              <span className="font-medium block mb-1">Why we're warning you</span>
              {finding.category === 'missing_commitment_info'
                ? "We couldn't find cancellation instructions in the text we checked."
                : "We couldn't find direct supporting words in the text we checked."}
            </div>
          )}

          <div className="bg-white p-2 rounded border border-slate-200">
            <span className="font-semibold text-blue-900 block mb-0.5">What to check:</span>
            <p className="text-slate-700 leading-relaxed">{presentation.nextStep}</p>
          </div>
        </div>
      )}
    </div>
  );
}
