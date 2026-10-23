/**
 * Background service worker for Dark Pattern Guardian.
 *
 * Minimal orchestration only — no persistent state, no auto-scanning.
 * Relays messages between popup and content script.
 *
 * Message flow:
 *   popup → background: {type: "SCAN", tabId: number}
 *   background → content: {type: "EXTRACT_TEXT"}
 *   content → background: {success: boolean, data?: ExtractionResult, error?: string}
 *   background → popup: {type: "SCAN_EXTRACTION", ...}
 */
export default defineBackground(() => {
  browser.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    if (message?.type === 'SCAN') {
      const tabId: number = message.tabId;

      browser.tabs
        .sendMessage(tabId, { type: 'EXTRACT_TEXT' })
        .then((response) => {
          sendResponse({ type: 'SCAN_EXTRACTION', ...response });
        })
        .catch((err) => {
          sendResponse({
            type: 'SCAN_EXTRACTION',
            success: false,
            error: err instanceof Error ? err.message : 'Content script unreachable.',
          });
        });

      // Return true for async response.
      return true;
    }
  });
});
