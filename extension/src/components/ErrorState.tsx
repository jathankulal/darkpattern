/**
 * ErrorState component — maps ErrorCode values to calm, user-actionable messages.
 *
 * Spec (docs/06_UI_UX_SPEC.md §Required states, docs/02_PRD FR-10):
 * - Show clear states for unsupported page, no relevant text, backend unavailable,
 *   analysis timeout, and invalid response.
 * - Do not silently substitute fabricated analysis.
 * - Tone: clear, calm, non-accusatory.
 */
import type { ErrorCode } from '../types/api';
import { ERROR_MESSAGES } from '../lib/labels';

interface ErrorStateProps {
  code: ErrorCode;
  /** Optional extra context, e.g. a retry callback. */
  onRetry?: () => void;
}

const ERROR_ICONS: Partial<Record<ErrorCode, string>> = {
  backend_unavailable: '🔌',
  analysis_timeout: '⏱',
  configuration_missing: '⚙️',
  no_relevant_text: '🔍',
  unsupported_page: '📄',
  invalid_model_output: '⚠️',
  internal_error: '⚠️',
};

export function ErrorState({ code, onRetry }: ErrorStateProps) {
  const icon = ERROR_ICONS[code] ?? '⚠️';
  const message = ERROR_MESSAGES[code] ?? 'An unexpected error occurred. Please try again.';

  return (
    <div
      role="alert"
      aria-live="assertive"
      className="flex flex-col items-center gap-3 px-4 py-6 text-center"
    >
      <span className="text-3xl" aria-hidden="true">
        {icon}
      </span>
      <p className="text-sm text-slate-700 leading-relaxed max-w-xs">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-2 px-4 py-2 text-sm font-medium rounded-md bg-blue-600 text-white hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition-colors"
          aria-label="Try the scan again"
        >
          Try again
        </button>
      )}
    </div>
  );
}
