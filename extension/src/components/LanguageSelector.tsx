import React from 'react';
import {
  SUPPORTED_LANGUAGES,
  type SupportedLanguage,
} from '../lib/language';

interface LanguageSelectorProps {
  selectedLanguage: SupportedLanguage;
  onLanguageChange: (lang: SupportedLanguage) => void;
  disabled?: boolean;
}

export function LanguageSelector({
  selectedLanguage,
  onLanguageChange,
  disabled = false,
}: LanguageSelectorProps) {
  return (
    <div className="flex items-center gap-1.5" title="Select explanation language">
      <label htmlFor="language-select" className="sr-only">
        Language
      </label>
      <div className="relative inline-flex items-center">
        <span className="text-[11px] text-slate-500 mr-1" aria-hidden="true">
          🌐
        </span>
        <select
          id="language-select"
          aria-label="Explanation language"
          value={selectedLanguage}
          disabled={disabled}
          onChange={(e) => onLanguageChange(e.target.value as SupportedLanguage)}
          className="text-[11px] font-medium bg-white text-slate-700 border border-slate-300 rounded-md px-2 py-0.5 pr-6 appearance-none focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500 transition-colors shadow-2xs cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {SUPPORTED_LANGUAGES.map((lang) => (
            <option key={lang.code} value={lang.code}>
              {lang.nativeLabel} ({lang.code.toUpperCase()})
            </option>
          ))}
        </select>
        <span
          className="pointer-events-none absolute right-1.5 text-[9px] text-slate-400"
          aria-hidden="true"
        >
          ▼
        </span>
      </div>
    </div>
  );
}
