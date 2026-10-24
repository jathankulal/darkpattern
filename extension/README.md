# Dark Pattern Guardian — Browser Extension

Chrome extension client for Dark Pattern Guardian (Manifest V3), built with [WXT](https://wxt.dev/), React, TypeScript, and Tailwind CSS.

Analyzes visible page text on user request to explain pre-purchase financial commitments, subscription traps, recurring billing terms, and unclear fee structures.

---

## Prerequisites

- **Node.js**: v20+ (tested with v24)
- **npm**: v10+ (tested with v11)
- **Backend**: Python 3.12 FastAPI server running at `http://127.0.0.1:8000` (see `docs/05_DATA_CONTRACTS_API.md`)

---

## Getting Started

### 1. Install dependencies
```bash
cd extension
npm install
```

### 2. Configure environment (optional)
By default, the extension connects to `http://127.0.0.1:8000`. To customize the backend URL:
```bash
cp .env.example .env
# Edit VITE_BACKEND_URL in .env if needed
```

### 3. Run development mode
```bash
npm run dev
```
WXT will build the development bundle to `.output/chrome-mv3-dev/` and watch for changes.

### 4. Load unpacked extension in Chrome
1. Open Chrome and navigate to `chrome://extensions/`.
2. Enable **Developer mode** (toggle in upper right).
3. Click **Load unpacked**.
4. Select `d:\darkpattern\extension\.output\chrome-mv3-dev` (or `.output/chrome-mv3` after build).

---

## Available Scripts

| Command | Description |
|---|---|
| `npm run dev` | Start development server with HMR |
| `npm run build` | Build production extension to `.output/chrome-mv3/` |
| `npm test` | Run Vitest unit tests |
| `npm run compile` | Typecheck TypeScript files (`tsc --noEmit`) |
| `npm run zip` | Package production zip for distribution |

---

## Permissions Architecture (D-011)

In alignment with data minimization principles (`docs/07_PRIVACY_SECURITY.md`):
- `activeTab`: Access only the currently active tab when user triggers the action.
- `scripting`: Programmatically inject the extraction logic on user action.
- `http://127.0.0.1:8000/*` host permission: Allow network requests to the local backend.
- **No** `<all_urls>`, **no** background surveillance, **no** access to cookies, local storage, history, or form inputs (passwords, credit cards).

---

## Project Structure

```
extension/
├── entrypoints/
│   ├── popup/            # Extension popup UI (React + Tailwind)
│   ├── content.ts        # Content script listening for extraction requests
│   └── background.ts     # Minimal message-relay background service worker
├── src/
│   ├── types/
│   │   └── api.ts        # TypeScript contracts mirroring backend/app/schemas.py
│   ├── lib/
│   │   ├── api/          # Typed backend HTTP client (15s timeout, structured errors)
│   │   ├── extraction/   # Bounded visible text extractor (40k char cap, keyword scoring)
│   │   └── labels.ts     # Human-readable labels & error messages
│   ├── components/       # Popup UI components (CommitmentMap, FindingCard, Checklist, etc.)
│   └── tests/            # Vitest unit test suites
├── wxt.config.ts         # WXT & Manifest V3 configuration
└── tailwind.config.cjs   # Tailwind styling tokens
```

---

## Wave 2 Status & Known Limitations

- **Mock backend**: Responses in Wave 2 come from the deterministic mock endpoint (`/api/v1/analyze`). LLM integration is scheduled for Phase 4.
- **Evidence-substring validation**: Scheduled for Phase 2.
- **Financial arithmetic**: Scheduled for Phase 3.
