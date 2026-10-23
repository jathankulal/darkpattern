import { describe, it, expect, beforeEach } from 'vitest';
import {
  extractRelevantText,
  MAX_PAGE_TEXT_CHARS,
} from '../lib/extraction/textExtractor';

describe('textExtractor', () => {
  beforeEach(() => {
    document.body.innerHTML = '';
    document.title = 'Test Store';
  });

  it('extracts visible text and strips query and fragment from url', () => {
    window.history.pushState({}, 'Test Store', '/checkout?promo=discount#step2');

    document.body.innerHTML = `
      <h1>Checkout Page</h1>
      <p>Total price is $29.99 per month recurring subscription.</p>
    `;

    const result = extractRelevantText(document);

    expect(result.pageTitle).toBe('Test Store');
    expect(result.pageUrl).toBe('http://localhost:3000/checkout');
    expect(result.pageText).toContain('Total price is $29.99 per month recurring subscription.');
  });

  it('enforces MAX_PAGE_TEXT_CHARS cap on long pages', () => {
    const longChunk = 'This is a long recurring price plan description that repeats. '.repeat(1000);
    document.body.innerHTML = `
      <div>${longChunk}</div>
    `;

    const result = extractRelevantText(document);
    expect(result.pageText.length).toBeLessThanOrEqual(MAX_PAGE_TEXT_CHARS);
  });

  it('excludes hidden elements, scripts, styles, and password/credit card inputs', () => {
    document.body.innerHTML = `
      <script>var secret = "do_not_extract";</script>
      <style>.hidden { display: none; }</style>
      <p>Visible payment plan terms: $49.00 billed annually.</p>
      <input type="password" value="supersecretpassword" />
      <input type="credit-card" value="4111222233334444" />
      <div style="display: none">Hidden hidden text</div>
      <div hidden>Another hidden text</div>
      <div aria-hidden="true">Aria hidden promo</div>
    `;

    const result = extractRelevantText(document);

    expect(result.pageText).toContain('Visible payment plan terms: $49.00 billed annually.');
    expect(result.pageText).not.toContain('do_not_extract');
    expect(result.pageText).not.toContain('supersecretpassword');
    expect(result.pageText).not.toContain('4111222233334444');
    expect(result.pageText).not.toContain('Hidden hidden text');
    expect(result.pageText).not.toContain('Another hidden text');
    expect(result.pageText).not.toContain('Aria hidden promo');
  });

  it('prioritizes high-relevance blocks over unrelated blocks', () => {
    document.body.innerHTML = `
      <p>About our company founding in 1995 with great mission and history.</p>
      <p>Subscription auto-renews at $19.99 per month after free trial ends.</p>
    `;

    const result = extractRelevantText(document);
    // The relevant subscription text should appear at the beginning of the result
    const subscriptionPos = result.pageText.indexOf('Subscription auto-renews');
    const companyPos = result.pageText.indexOf('About our company');

    expect(subscriptionPos).toBeGreaterThanOrEqual(0);
    expect(companyPos).toBeGreaterThanOrEqual(0);
    expect(subscriptionPos).toBeLessThan(companyPos);
  });

  it('prioritizes urgency and scarcity phrases over unrelated background copy', () => {
    document.body.innerHTML = `
      <p>Browse our catalog of everyday supplies and accessories.</p>
      <p>Limited time offer! Sale ends in 15 minutes, only 2 left in stock!</p>
    `;

    const result = extractRelevantText(document);
    const urgencyPos = result.pageText.indexOf('Limited time offer');
    const catalogPos = result.pageText.indexOf('Browse our catalog');

    expect(urgencyPos).toBeGreaterThanOrEqual(0);
    expect(catalogPos).toBeGreaterThanOrEqual(0);
    expect(urgencyPos).toBeLessThan(catalogPos);
  });
});
