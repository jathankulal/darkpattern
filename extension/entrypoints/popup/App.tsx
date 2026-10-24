import React, { useState, useEffect } from 'react';
import type {
  AnalyzeResponse,
  ErrorCode,
  HealthResponse,
} from '../../src/types/api';
import {
  analyzePageRequest,
  healthCheck,
  BackendError,
} from '../../src/lib/api/backendClient';
import { extractRelevantText } from '../../src/lib/extraction/textExtractor';
import { ScanButton } from '../../src/components/ScanButton';
import { CommitmentMap } from '../../src/components/CommitmentMap';
import { PlanList } from '../../src/components/PlanList';
import { FindingCard } from '../../src/components/FindingCard';
import { PriceIntegrityTrail } from '../../src/components/PriceIntegrityTrail';
import { Checklist } from '../../src/components/Checklist';
import { FinancialTimeline } from '../../src/components/FinancialTimeline';
import { RiskOverview } from '../../src/components/RiskOverview';
import { SafeAlternativeFinder } from '../../src/components/SafeAlternativeFinder';
import { ErrorState } from '../../src/components/ErrorState';
import { LanguageSelector } from '../../src/components/LanguageSelector';
import {
  getInitialLanguage,
  saveSelectedLanguage,
  type SupportedLanguage,
} from '../../src/lib/language';

type UIState =
  | { type: 'idle' }
  | { type: 'extracting' }
  | { type: 'analyzing' }
  | { type: 'results'; data: AnalyzeResponse }
  | { type: 'error'; code: ErrorCode };

export default function App() {
  const [state, setState] = useState<UIState>({ type: 'idle' });
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [language, setLanguage] = useState<SupportedLanguage>(getInitialLanguage);

  const handleLanguageChange = (newLang: SupportedLanguage) => {
    setLanguage(newLang);
    saveSelectedLanguage(newLang);
  };

  // Check backend health on initial popup mount
  useEffect(() => {
    let mounted = true;
    healthCheck()
      .then((res) => {
        if (mounted) setHealth(res);
      })
      .catch(() => {
        // Non-blocking for idle view, but user will get error if they scan while backend is down
      });
    return () => {
      mounted = false;
    };
  }, []);

  const handleScan = async () => {
    setState({ type: 'extracting' });

    try {
      // 1. Query active tab
      const [activeTab] = await browser.tabs.query({ active: true, currentWindow: true });
      if (!activeTab || !activeTab.id || !activeTab.url) {
        setState({ type: 'error', code: 'unsupported_page' });
        return;
      }

      // Check for restricted URLs (chrome://, about:, etc.)
      if (
        activeTab.url.startsWith('chrome://') ||
        activeTab.url.startsWith('edge://') ||
        activeTab.url.startsWith('about:') ||
        activeTab.url.startsWith('chrome-extension://')
      ) {
        setState({ type: 'error', code: 'unsupported_page' });
        return;
      }

      // 2. Request extraction from content script
      let extraction: ReturnType<typeof extractRelevantText> | null = null;
      try {
        const response = await browser.tabs.sendMessage(activeTab.id, { type: 'EXTRACT_TEXT' });
        if (response && response.success && response.data) {
          extraction = response.data;
        }
      } catch {
        // Content script might not be injected yet into pre-existing tab.
        // Try programmatic injection via chrome.scripting if available.
        try {
          if (browser.scripting && browser.scripting.executeScript) {
            const results = await browser.scripting.executeScript({
              target: { tabId: activeTab.id },
              func: () => {
                // Inline fallback extraction
                const tags = ['P', 'LI', 'TD', 'TH', 'H1', 'H2', 'H3', 'SPAN', 'DIV', 'LABEL'];
                const seen = new Set<string>();
                const texts: string[] = [];
                for (const el of document.querySelectorAll(tags.join(','))) {
                  const t = el.textContent?.trim() ?? '';
                  if (t.length > 5 && !seen.has(t)) {
                    seen.add(t);
                    texts.push(t);
                  }
                }
                const urlObj = new URL(window.location.href);
                return {
                  pageTitle: document.title,
                  pageUrl: `${urlObj.protocol}//${urlObj.host}${urlObj.pathname}`,
                  pageText: texts.join('\n').slice(0, 40000),
                  locale: document.documentElement.lang || navigator.language,
                };
              },
            });
            if (results && results[0]?.result) {
              extraction = results[0].result;
            }
          }
        } catch {
          // Injection failed
        }
      }

      if (!extraction || !extraction.pageText || extraction.pageText.trim().length === 0) {
        setState({ type: 'error', code: 'no_relevant_text' });
        return;
      }

      // 3. Send to backend
      setState({ type: 'analyzing' });
      const result = await analyzePageRequest({
        page_title: extraction.pageTitle,
        page_url: extraction.pageUrl,
        page_text: extraction.pageText,
        locale: language,
      });

      setState({ type: 'results', data: result });
    } catch (err) {
      if (err instanceof BackendError) {
        setState({ type: 'error', code: err.code });
      } else {
        setState({ type: 'error', code: 'internal_error' });
      }
    }
  };

  return (
    <div className="min-h-[480px] flex flex-col bg-slate-50 text-slate-800">
      {/* Extension Header */}
      <header className="bg-white border-b border-slate-200 px-4 py-3 flex items-center justify-between sticky top-0 z-10 shadow-xs">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-md bg-blue-600 flex items-center justify-center text-white font-bold text-xs shadow-xs">
            🛡️
          </div>
          <div>
            <h1 className="text-xs font-bold text-slate-900 leading-tight">
              Dark Pattern Guardian
            </h1>
            <span className="text-[10px] text-slate-500 block">Financial Clarity Assistant</span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <LanguageSelector
            selectedLanguage={language}
            onLanguageChange={handleLanguageChange}
            disabled={state.type === 'extracting' || state.type === 'analyzing'}
          />
          {state.type === 'results' ? (
            <span className="text-[10px] bg-emerald-50 text-emerald-700 px-2 py-0.5 rounded-full border border-emerald-200">
              Page analyzed
            </span>
          ) : health ? (
            <span
              className="text-[10px] bg-slate-100 text-slate-600 px-2 py-0.5 rounded-full border border-slate-200"
              title={`Backend connected (${health.version})`}
            >
              Ready
            </span>
          ) : null}
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 p-3.5 space-y-3">
        {state.type === 'idle' && (
          <div className="flex flex-col items-center justify-center py-8 px-2 text-center space-y-4">
            <div className="w-12 h-12 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center text-2xl">
              🔍
            </div>
            <div>
              <h2 className="text-sm font-semibold text-slate-900">Scan for Financial Terms</h2>
              <p className="text-xs text-slate-500 mt-1 max-w-xs leading-relaxed">
                Click below to analyze visible terms, prices, subscription renewal conditions, and
                hidden fee disclosures on this page.
              </p>
            </div>
            <div className="w-full max-w-xs pt-2">
              <ScanButton isLoading={false} onClick={handleScan} />
            </div>
          </div>
        )}

        {(state.type === 'extracting' || state.type === 'analyzing') && (
          <div className="flex flex-col items-center justify-center py-16 px-4 text-center space-y-3">
            <ScanButton
              isLoading={true}
              loadingLabel={
                state.type === 'extracting'
                  ? 'Reading page terms…'
                  : 'Analyzing with backend…'
              }
              onClick={() => {}}
            />
          </div>
        )}

        {state.type === 'error' && (
          <div className="py-6">
            <ErrorState code={state.code} onRetry={handleScan} />
          </div>
        )}

        {state.type === 'results' && (
          <div className="space-y-3 pb-4">
            {/* Partial Banner */}
            {state.data.status === 'partial' && (
              <div
                role="status"
                className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-xs text-amber-900 flex items-start gap-2"
              >
                <span className="text-amber-600 font-bold" aria-hidden="true">
                  ⚠️
                </span>
                <p>
                  <strong>Partial analysis:</strong> Some commitment terms or sections could not be
                  fully verified.
                </p>
              </div>
            )}

            <RiskOverview data={state.data} />

            <details className="group bg-white border border-slate-200 rounded-lg shadow-xs">
              <summary className="cursor-pointer list-none px-3 py-2.5 text-xs font-semibold text-blue-700 hover:bg-blue-50 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500">
                View detailed analysis
              </summary>
              <div className="p-3 pt-0 space-y-3">
                <div className="bg-slate-50 border border-slate-200 rounded-lg p-3">
                  <h2 className="text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
                    Analyzer summary
                  </h2>
                  <p className="text-xs text-slate-800 leading-relaxed">{state.data.summary}</p>
                </div>

                <CommitmentMap
                  commitmentMap={state.data.commitment_map}
                  isMultiPlan={Boolean(state.data.plans && state.data.plans.length > 1)}
                />
                <FinancialTimeline timeline={state.data.timeline} />
                {state.data.plans && state.data.plans.length > 0 && (
                  <PlanList plans={state.data.plans} />
                )}
                <SafeAlternativeFinder
                  commitmentMap={state.data.commitment_map}
                  isMultiPlan={Boolean(state.data.plans && state.data.plans.length > 1)}
                />

                <section aria-labelledby="findings-heading" className="space-y-2">
                  <h3 id="findings-heading" className="text-xs font-bold text-slate-700 uppercase tracking-wider">
                    All findings ({state.data.findings.length})
                  </h3>
                  {state.data.findings.length === 0 ? (
                    <div className="bg-white border border-slate-200 rounded-lg p-3 text-center text-xs text-slate-600">
                      We didn't find any known warning signs in the text we checked. This scan may not
                      include everything on the page.
                    </div>
                  ) : (
                    <div className="space-y-2">
                      {state.data.findings.map((finding, index) => (
                        <FindingCard
                          key={finding.id}
                          finding={finding}
                          showExplanation={
                            state.data.findings.findIndex(
                              (candidate) => candidate.category === finding.category,
                            ) === index
                          }
                        />
                      ))}
                    </div>
                  )}
                </section>

                <PriceIntegrityTrail priceIntegrity={state.data.price_integrity} />
                <Checklist items={state.data.checklist} />

                {state.data.limitations.length > 0 && (
                  <div className="bg-slate-100 rounded-lg p-2.5 border border-slate-200 text-[11px] text-slate-500">
                    <span className="font-semibold text-slate-700 block mb-0.5">Limitations:</span>
                    <ul className="list-disc pl-4 space-y-0.5">
                      {state.data.limitations.map((limitation, index) => (
                        <li key={index}>{limitation}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </details>

            <button
              type="button"
              onClick={handleScan}
              className="w-full py-2 px-3 text-xs font-medium text-slate-700 bg-white hover:bg-slate-100 border border-slate-300 rounded-md transition-colors shadow-xs"
            >
              Scan page again
            </button>
          </div>
        )}
      </main>
    </div>
  );
}
