import React from 'react';

interface ScanButtonProps {
  isLoading: boolean;
  loadingLabel?: string;
  onClick: () => void;
  disabled?: boolean;
}

export function ScanButton({
  isLoading,
  loadingLabel = 'Analyzing visible text...',
  onClick,
  disabled = false,
}: ScanButtonProps) {
  return (
    <div className="flex flex-col items-center gap-2">
      <button
        type="button"
        onClick={onClick}
        disabled={isLoading || disabled}
        className={`w-full py-2.5 px-4 rounded-lg font-medium text-sm text-white shadow-sm transition-all flex items-center justify-center gap-2 ${
          isLoading || disabled
            ? 'bg-blue-400 cursor-not-allowed'
            : 'bg-blue-600 hover:bg-blue-700 active:bg-blue-800 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2'
        }`}
        aria-busy={isLoading}
      >
        {isLoading ? (
          <>
            <svg
              className="animate-spin -ml-1 mr-2 h-4 w-4 text-white"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
              />
            </svg>
            <span>{loadingLabel}</span>
          </>
        ) : (
          <>
            <svg
              className="w-4 h-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2"
                d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
              />
            </svg>
            <span>Scan this page</span>
          </>
        )}
      </button>
      <p className="text-xs text-slate-500 text-center">
        Checks visible terms on this page. No passwords or form inputs are read.
      </p>
    </div>
  );
}
