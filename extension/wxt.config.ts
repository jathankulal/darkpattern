import { defineConfig } from 'wxt';

const backendUrl = process.env.VITE_BACKEND_URL ?? 'http://127.0.0.1:8000';

// See https://wxt.dev/api/reference/wxt/interfaces/inlineconfig.html
export default defineConfig({
  modules: ['@wxt-dev/module-react'],
  manifest: {
    name: 'Dark Pattern Guardian',
    description:
      'Pre-purchase financial commitment explainer. Analyzes visible page text on user request to surface recurring charges, trial conversions, and unclear terms.',
    version: '0.2.0',
    // D-011: narrowest permissions supporting MVP — activeTab + scripting only.
    // No <all_urls>, tabs, cookies, storage, or history.
    permissions: ['activeTab', 'scripting'],
    // Host permission restricted to local backend (D-011).
    // Set VITE_BACKEND_URL at build time to override for deployment.
    host_permissions: [`${backendUrl}/*`],
    action: {
      default_title: 'Dark Pattern Guardian — Scan this page',
    },
  },
  vite: () => ({
    // Expose VITE_BACKEND_URL to the extension bundle.
    define: {
      'import.meta.env.VITE_BACKEND_URL': JSON.stringify(backendUrl),
    },
  }),
});
