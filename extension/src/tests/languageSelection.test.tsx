import React from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import {
  normalizeLocale,
  getInitialLanguage,
  saveSelectedLanguage,
  STORAGE_KEY_LANGUAGE,
  SUPPORTED_LANGUAGES,
} from '../lib/language';
import { LanguageSelector } from '../components/LanguageSelector';
import { analyzePageRequest } from '../lib/api/backendClient';
import type { AnalyzeResponse } from '../types/api';

describe('Language Selection and Locale Normalization', () => {
  const originalLocalStorage = global.localStorage;
  const originalNavigator = global.navigator;

  beforeEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
  });

  describe('normalizeLocale', () => {
    it('normalizes Kannada regional tags', () => {
      expect(normalizeLocale('kn-IN')).toBe('kn');
      expect(normalizeLocale('kn_IN')).toBe('kn');
      expect(normalizeLocale('kn')).toBe('kn');
      expect(normalizeLocale('KN-in')).toBe('kn');
    });

    it('normalizes Hindi regional tags', () => {
      expect(normalizeLocale('hi-IN')).toBe('hi');
      expect(normalizeLocale('hi_IN')).toBe('hi');
      expect(normalizeLocale('hi')).toBe('hi');
      expect(normalizeLocale('HI-in')).toBe('hi');
    });

    it('normalizes English regional tags', () => {
      expect(normalizeLocale('en-US')).toBe('en');
      expect(normalizeLocale('en-GB')).toBe('en');
      expect(normalizeLocale('en')).toBe('en');
    });

    it('falls back to en for unsupported or empty tags', () => {
      expect(normalizeLocale(null)).toBe('en');
      expect(normalizeLocale(undefined)).toBe('en');
      expect(normalizeLocale('')).toBe('en');
      expect(normalizeLocale('   ')).toBe('en');
      expect(normalizeLocale('fr-FR')).toBe('en');
      expect(normalizeLocale('es-ES')).toBe('en');
      expect(normalizeLocale('de')).toBe('en');
    });
  });

  describe('getInitialLanguage & saveSelectedLanguage', () => {
    it('returns stored language from localStorage if valid', () => {
      localStorage.setItem(STORAGE_KEY_LANGUAGE, 'kn');
      expect(getInitialLanguage()).toBe('kn');

      localStorage.setItem(STORAGE_KEY_LANGUAGE, 'hi');
      expect(getInitialLanguage()).toBe('hi');

      localStorage.setItem(STORAGE_KEY_LANGUAGE, 'en');
      expect(getInitialLanguage()).toBe('en');
    });

    it('ignores invalid values in localStorage and falls back', () => {
      localStorage.setItem(STORAGE_KEY_LANGUAGE, 'invalid-lang');
      // Should fall back to browser or 'en'
      expect(['en', 'kn', 'hi']).toContain(getInitialLanguage());
    });

    it('saves language to localStorage', () => {
      saveSelectedLanguage('kn');
      expect(localStorage.getItem(STORAGE_KEY_LANGUAGE)).toBe('kn');

      saveSelectedLanguage('hi');
      expect(localStorage.getItem(STORAGE_KEY_LANGUAGE)).toBe('hi');
    });

    it('detects Kannada or Hindi from navigator.language when storage is empty', () => {
      localStorage.removeItem(STORAGE_KEY_LANGUAGE);

      const navSpy = vi.spyOn(navigator, 'language', 'get').mockReturnValue('kn-IN');
      expect(getInitialLanguage()).toBe('kn');

      navSpy.mockReturnValue('hi-IN');
      expect(getInitialLanguage()).toBe('hi');

      navSpy.mockReturnValue('fr-FR');
      expect(getInitialLanguage()).toBe('en');
    });
  });

  describe('LanguageSelector component', () => {
    it('renders all supported language options', () => {
      render(
        <LanguageSelector
          selectedLanguage="en"
          onLanguageChange={() => {}}
        />,
      );

      const select = screen.getByRole('combobox', { name: /language/i });
      expect(select).toBeDefined();

      for (const lang of SUPPORTED_LANGUAGES) {
        expect(screen.getByRole('option', { name: new RegExp(lang.nativeLabel, 'i') })).toBeDefined();
      }
    });

    it('displays the currently selected language', () => {
      render(
        <LanguageSelector
          selectedLanguage="kn"
          onLanguageChange={() => {}}
        />,
      );

      const select = screen.getByRole('combobox', { name: /language/i }) as HTMLSelectElement;
      expect(select.value).toBe('kn');
    });

    it('calls onLanguageChange when a different language is selected', () => {
      const handleChange = vi.fn();
      render(
        <LanguageSelector
          selectedLanguage="en"
          onLanguageChange={handleChange}
        />,
      );

      const select = screen.getByRole('combobox', { name: /language/i });
      fireEvent.change(select, { target: { value: 'hi' } });

      expect(handleChange).toHaveBeenCalledWith('hi');
    });

    it('is disabled when disabled prop is true', () => {
      render(
        <LanguageSelector
          selectedLanguage="en"
          onLanguageChange={() => {}}
          disabled={true}
        />,
      );

      const select = screen.getByRole('combobox', { name: /language/i }) as HTMLSelectElement;
      expect(select.disabled).toBe(true);
    });
  });

  describe('Request propagation with locale', () => {
    const originalFetch = global.fetch;

    afterEach(() => {
      global.fetch = originalFetch;
    });

    it('propagates selected locale to backend analyzePageRequest payload', async () => {
      const mockData: AnalyzeResponse = {
        status: 'ok',
        summary: 'ವಿವರಣೆ',
        findings: [],
        commitment_map: { unknowns: [] },
        price_integrity: { observations: [], reason: 'known' },
        checklist: [],
        limitations: [],
      };

      let sentBody: any = null;
      global.fetch = vi.fn().mockImplementation((_url, options) => {
        sentBody = JSON.parse(options.body as string);
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve(mockData),
        });
      });

      const res = await analyzePageRequest({
        page_title: 'Checkout',
        page_url: 'https://example.com/checkout',
        page_text: 'Subscription $9.99/mo',
        locale: 'kn',
      });

      expect(res).toEqual(mockData);
      expect(sentBody).not.toBeNull();
      expect(sentBody.locale).toBe('kn');
      expect(sentBody.page_title).toBe('Checkout');
    });

    it('propagates Hindi locale to backend analyzePageRequest payload', async () => {
      const mockData: AnalyzeResponse = {
        status: 'ok',
        summary: 'सारांश',
        findings: [],
        commitment_map: { unknowns: [] },
        price_integrity: { observations: [], reason: 'known' },
        checklist: [],
        limitations: [],
      };

      let sentBody: any = null;
      global.fetch = vi.fn().mockImplementation((_url, options) => {
        sentBody = JSON.parse(options.body as string);
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve(mockData),
        });
      });

      await analyzePageRequest({
        page_title: 'Checkout',
        page_url: 'https://example.com/checkout',
        page_text: 'Subscription $9.99/mo',
        locale: 'hi',
      });

      expect(sentBody.locale).toBe('hi');
    });
  });
});
