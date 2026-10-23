import React from 'react';

interface ChecklistProps {
  items: string[];
}

export function Checklist({ items }: ChecklistProps) {
  if (!items || items.length === 0) {
    return null;
  }

  return (
    <section
      aria-labelledby="checklist-heading"
      className="bg-white rounded-lg border border-slate-200 p-4 shadow-sm"
    >
      <h3
        id="checklist-heading"
        className="text-sm font-semibold text-slate-800 flex items-center gap-1.5 mb-2"
      >
        <svg
          className="w-4 h-4 text-emerald-600"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth="2"
            d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"
          />
        </svg>
        Ask Before You Pay
      </h3>

      <ul className="space-y-1.5 text-xs text-slate-700">
        {items.map((item, idx) => (
          <li key={idx} className="flex items-start gap-2">
            <span
              className="mt-0.5 inline-block w-3.5 h-3.5 rounded border border-slate-300 bg-slate-50 flex-shrink-0"
              aria-hidden="true"
            />
            <span className="leading-relaxed">{item}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
