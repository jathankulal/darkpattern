/**
 * Language selection and locale normalization utilities for Dark Pattern Guardian.
 *
 * Supported languages:
 * - en: English (default)
 * - kn: Kannada (ಕನ್ನಡ)
 * - hi: Hindi (हिन्दी)
 *
 * Storage key: 'dpg_selected_language'
 */

export const SUPPORTED_LANGUAGES = [
  { code: 'en', label: 'English', nativeLabel: 'English' },
  { code: 'kn', label: 'Kannada', nativeLabel: 'ಕನ್ನಡ' },
  { code: 'hi', label: 'Hindi', nativeLabel: 'हिन्दी' },
] as const;

export type SupportedLanguage = (typeof SUPPORTED_LANGUAGES)[number]['code'];

export const STORAGE_KEY_LANGUAGE = 'dpg_selected_language';

/**
 * Normalizes BCP-47 locale tags (e.g., 'kn-IN', 'hi-IN', 'en-US') to one of
 * the supported language codes ('en', 'kn', 'hi').
 *
 * If the tag is missing or unsupported, defaults to 'en'.
 */
export function normalizeLocale(locale?: string | null): SupportedLanguage {
  if (!locale) {
    return 'en';
  }
  const parts = locale.split(/[-_]/);
  const primary = (parts[0] ?? '').toLowerCase().trim();
  if (primary === 'kn') {
    return 'kn';
  }
  if (primary === 'hi') {
    return 'hi';
  }
  return 'en';
}

/**
 * Detects the user's initial language.
 *
 * Priority:
 * 1. Previously stored user preference in localStorage (if valid).
 * 2. Browser language (navigator.language) mapped to supported languages.
 * 3. Fallback to English ('en').
 */
export function getInitialLanguage(): SupportedLanguage {
  try {
    if (typeof localStorage !== 'undefined') {
      const stored = localStorage.getItem(STORAGE_KEY_LANGUAGE);
      if (stored === 'en' || stored === 'kn' || stored === 'hi') {
        return stored;
      }
    }
  } catch {
    // Ignore localStorage access errors (e.g. sandboxed environments)
  }

  try {
    if (typeof navigator !== 'undefined') {
      const browserLang = navigator.language || (navigator.languages && navigator.languages[0]);
      if (browserLang) {
        const normalized = normalizeLocale(browserLang);
        // Only return non-default if explicitly matched
        const parts = browserLang.split(/[-_]/);
        const primary = (parts[0] ?? '').toLowerCase().trim();
        if (primary === 'kn' || primary === 'hi') {
          return normalized;
        }
      }
    }
  } catch {
    // Ignore navigator access errors
  }

  return 'en';
}

/**
 * Persists the user's selected language in localStorage.
 */
export function saveSelectedLanguage(language: SupportedLanguage): void {
  try {
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem(STORAGE_KEY_LANGUAGE, language);
    }
  } catch {
    // Ignore localStorage access errors
  }
}
