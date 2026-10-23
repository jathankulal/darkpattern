# 1. Project Charter

## Product name
Dark Pattern Guardian

## One-line description
A user-triggered browser extension that helps people understand the real financial commitments, price changes, and unclear terms on a shopping or subscription page before they pay.

## Core question
**“What financial commitment am I actually agreeing to?”**

## Problem
Online offers may make the immediate price prominent while making recurring charges, trial conversion dates, cancellation terms, extra fees, or other conditions difficult to notice. Users can accept a commitment without understanding its future cost or the conditions that trigger it.

## Proposed solution
The user explicitly runs a scan on the current page. The extension extracts a limited amount of relevant page text and presents an evidence-backed Financial Commitment Map:
- Pay now
- Pay later / recurring obligations
- Trigger or date for future charges, if stated
- Cancellation/refund terms, if stated
- Price differences or additional fees observed
- Evidence snippets from the page
- Missing or unclear information
- Practical questions to check before paying

The extension may use deterministic rules and an LLM to interpret context. Money calculations must be performed by deterministic code, never by the LLM.

## Primary users
Consumers reviewing online purchases, free trials, subscriptions, and checkout pages.

## Product promise
Do not merely label a page “bad.” Explain the specific financial commitment and show the evidence that supports each finding.

## Differentiators
1. **Financial Commitment Map** — make present and future obligations visible.
2. **Price Integrity Trail** — compare advertised, cart, and checkout prices when the user scans those stages and the evidence is available.
3. **Ask Before You Pay** — a short checklist derived from missing or unclear terms.

## MVP scope
- Chrome extension using Manifest V3.
- User-triggered scan of the current tab.
- Extract relevant visible text and page URL/title only as needed.
- Detect likely subscription/trial terms, price/fee language, cancellation/refund information, and urgency/choice-pressure language when supported by evidence.
- Send a minimized page excerpt to a backend for contextual analysis.
- Return structured findings with evidence spans, confidence, severity, uncertainty, and questions to verify.
- Calculate explicit costs with deterministic financial logic.
- Show results in a concise extension UI.
- Include three demo cases: misleadingly presented recurring trial, checkout fee/price change, and a transparent legitimate subscription.

## Explicit non-goals for MVP
- Do not block purchases or click buttons for the user.
- Do not label a merchant a scam or make legal conclusions.
- Do not scan every page continuously or collect browsing history by default.
- Do not process payment credentials, card numbers, passwords, or authentication tokens.
- Do not train a custom ML model.
- Do not build a multi-agent framework.
- Do not promise detection of every dark pattern.
- Do not produce a single composite “Clarity Score 0–100” until its meaning and validation are defined.
- Do not implement cancellation friction detection as a complete multi-step workflow in the first MVP; it may be a later phase.

## Product principles
- Evidence before accusation.
- Uncertainty must be visible.
- Transparent recurring billing is not inherently a dark pattern.
- Missing information is not proof of wrongdoing.
- User remains in control.
- Data minimization by default.
- Financial arithmetic must be reproducible.
