/**
 * Content script for Dark Pattern Guardian.
 *
 * Runs in the context of the page (MV3 content script).
 * Only activates on explicit user action — never automatically.
 *
 * Privacy: reads only visible text; does not touch form values,
 * cookies, localStorage, or payment fields.
 */

import { extractRelevantText } from '../src/lib/extraction/textExtractor';

export default defineContentScript({
  matches: ['<all_urls>'],
  main() {
    // Listen for extraction requests from the popup (relayed via background or direct).
    browser.runtime.onMessage.addListener((message, _sender, sendResponse) => {
      if (message?.type === 'EXTRACT_TEXT') {
        try {
          const result = extractRelevantText(document);
          sendResponse({ success: true, data: result });
        } catch (err) {
          sendResponse({
            success: false,
            error: err instanceof Error ? err.message : 'Extraction failed.',
          });
        }
        // Return true to indicate async response (Chrome requirement).
        return true;
      }
    });
  },
});
