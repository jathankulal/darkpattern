/**
 * Visible page text extractor for Dark Pattern Guardian.
 *
 * Privacy rules (docs/07_PRIVACY_SECURITY.md, docs/02_PRD_REQUIREMENTS.md FR-2):
 * - Extract ONLY visible text relevant to purchase/payment/subscription decisions.
 * - Do NOT read: input field values, <script>, <style>, hidden elements, cookies,
 *   localStorage, credit card fields, or password fields.
 * - Hard character cap: MAX_PAGE_TEXT_CHARS (40 000) — well within the backend's 50 000 limit.
 * - User-triggered only — never call this function automatically.
 *
 * This module is pure and testable with a mocked document.
 */

/** Hard cap on extracted text length. Must stay below backend max_length=50000. */
export const MAX_PAGE_TEXT_CHARS = 40_000;

/**
 * Keywords that indicate a text block is relevant to purchase/commitment decisions.
 * Used to score and prioritize blocks. Case-insensitive.
 */
const RELEVANCE_KEYWORDS = [
  'price',
  'total',
  'subtotal',
  'checkout',
  'pay',
  'payment',
  'charge',
  'bill',
  'billing',
  'subscription',
  'subscribe',
  'plan',
  'trial',
  'free trial',
  'renew',
  'renewal',
  'recurring',
  'per month',
  'per year',
  'annually',
  'monthly',
  'auto-renew',
  'auto renew',
  'cancel',
  'cancellation',
  'refund',
  'fee',
  'tax',
  'shipping',
  'due',
  'today',
  'after trial',
  'then',
  '$',
  '€',
  '£',
  '¥',
];

/**
 * CSS selectors for elements that should NEVER contribute to extraction.
 * This guards against accidental collection of sensitive form values.
 */
const EXCLUDED_SELECTORS = [
  'script',
  'style',
  'noscript',
  'head',
  '[type="password"]',
  '[type="credit-card"]',
  '[autocomplete="cc-number"]',
  '[autocomplete="cc-csc"]',
  '[autocomplete="cc-exp"]',
  '[name="cardnumber"]',
  '[name="cvv"]',
  '[name="cvc"]',
  '[aria-hidden="true"]',
  '[hidden]',
];

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

function isExcluded(el: Element): boolean {
  return EXCLUDED_SELECTORS.some((sel) => {
    try {
      return el.matches(sel);
    } catch {
      return false;
    }
  });
}

function isVisible(el: Element): boolean {
  // Basic visibility check without getComputedStyle (not available in content scripts
  // without DOM access; this is a best-effort filter).
  if (isExcluded(el)) return false;
  const htmlEl = el as HTMLElement;
  if (htmlEl.hidden) return false;
  if (htmlEl.style?.display === 'none' || htmlEl.style?.visibility === 'hidden') return false;
  return true;
}

function blockRelevanceScore(text: string): number {
  const lower = text.toLowerCase();
  return RELEVANCE_KEYWORDS.reduce((score, kw) => (lower.includes(kw) ? score + 1 : score), 0);
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

export interface ExtractionResult {
  pageTitle: string;
  pageUrl: string;
  pageText: string;
  locale: string;
}

/**
 * Extract bounded, relevant visible text from the current document.
 *
 * Algorithm:
 * 1. Split body text into block-level segments.
 * 2. Score each segment by relevance keyword count.
 * 3. Sort by score descending, then truncate to MAX_PAGE_TEXT_CHARS.
 * 4. Strip URL query params and fragments (server also does this; defense-in-depth).
 *
 * @param doc - The document to extract from (defaults to window.document).
 */
export function extractRelevantText(doc: Document = document): ExtractionResult {
  // --- Page metadata ---
  const pageTitle = doc.title ?? '';
  const rawUrl = doc.location?.href ?? '';
  // Strip query and fragment client-side (server strips too — defense in depth).
  const urlObj = (() => {
    try {
      return new URL(rawUrl);
    } catch {
      return null;
    }
  })();
  const pageUrl = urlObj ? `${urlObj.protocol}//${urlObj.host}${urlObj.pathname}` : rawUrl;
  const locale = doc.documentElement.lang ?? navigator.language ?? '';

  // --- Text extraction ---
  // Walk block-level elements to extract text blocks.
  const blockTags = ['P', 'LI', 'TD', 'TH', 'H1', 'H2', 'H3', 'H4', 'H5', 'H6', 'SPAN', 'DIV', 'LABEL', 'SECTION', 'ARTICLE', 'ASIDE'];
  const seenText = new Set<string>();
  const blocks: { text: string; score: number }[] = [];

  // Collect all block-level visible elements.
  const allElements = doc.querySelectorAll(blockTags.join(','));

  for (const el of allElements) {
    if (!isVisible(el)) continue;
    // Only process leaf-ish nodes (no deeply nested block children) to avoid duplication.
    const hasBlockChild = blockTags.some((tag) => el.querySelector(tag.toLowerCase()));
    if (hasBlockChild) continue;

    const text = el.textContent?.trim() ?? '';
    if (text.length < 5) continue; // Skip trivially short fragments.
    if (seenText.has(text)) continue;
    seenText.add(text);

    blocks.push({ text, score: blockRelevanceScore(text) });
  }

  // Sort by relevance score descending (highest relevance first).
  blocks.sort((a, b) => b.score - a.score);

  // Concatenate up to MAX_PAGE_TEXT_CHARS.
  let pageText = '';
  for (const { text } of blocks) {
    if (pageText.length + text.length + 1 > MAX_PAGE_TEXT_CHARS) {
      // Append a truncated remainder to stay within the cap.
      const remaining = MAX_PAGE_TEXT_CHARS - pageText.length - 1;
      if (remaining > 0) {
        pageText += (pageText ? '\n' : '') + text.slice(0, remaining);
      }
      break;
    }
    pageText += (pageText ? '\n' : '') + text;
  }

  return { pageTitle, pageUrl, pageText, locale };
}
