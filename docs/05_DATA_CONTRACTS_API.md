# 5. Data Contracts and API

## API versioning
Initial local API may use `/api/v1/analyze`. If the implementation scaffolding requires a different prefix, document the decision and keep it consistent across client, tests, and docs.

## Analyze request — conceptual contract
```json
{
  "page_title": "string",
  "page_url": "string",
  "page_text": "string",
  "scan_id": "optional opaque identifier",
  "locale": "optional language code"
}
```

Constraints:
- `page_text` is bounded by a documented maximum length.
- No cookies, local storage, form values, payment credentials, passwords, or full DOM.
- URL should be included only as needed; strip query parameters and fragments by default if not necessary.
- Treat every input field as untrusted.

## Analyze response — conceptual contract
```json
{
  "status": "ok | partial | error",
  "summary": "plain-language summary",
  "findings": [
    {
      "id": "stable request-local identifier",
      "category": "approved category",
      "severity": "info | low | medium | high",
      "evidence_level": "explicit | inferred | unknown",
      "evidence_text": "verbatim snippet or empty only for missing-information observations",
      "explanation": "plain-language explanation",
      "confidence": 0.0,
      "missing_information": ["string"],
      "recommendation": "string"
    }
  ],
  "commitment_map": {
    "amount_due_now": "optional structured money value",
    "future_charge": "optional structured money value",
    "billing_interval": "optional string",
    "trial_duration": "optional string",
    "future_charge_trigger": "optional string",
    "cancellation_terms": "optional string",
    "unknowns": ["string"]
  },
  "plans": [
    {
      "plan_name": "string",
      "amount_due_now": "optional structured money value",
      "future_charge": "optional structured money value",
      "billing_interval": "optional string",
      "trial_duration": "optional string",
      "future_charge_trigger": "optional string",
      "cancellation_terms": "optional string",
      "unknowns": ["string"],
      "is_ambiguous": false,
      "ambiguity_reason": null,
      "evidence_text": "string"
    }
  ],
  "price_integrity": {
    "observations": [],
    "difference": "optional structured money value (total baseline-to-total change: final_total - subtotal, or renewal - introductory)",
    "reason": "known | disclosed_tax_or_shipping | unclear | not_comparable",
    "advertised_price": "optional structured money value",
    "checkout_subtotal": "optional structured money value",
    "explicit_fees": [
      {
        "name": "Shipping | Estimated Tax | etc.",
        "amount": "structured money value (negative for discounts)",
        "context": "optional string"
      }
    ],
    "final_total": "optional structured money value",
    "unexplained_difference": "optional structured money value (unaccounted discrepancy when final_total > subtotal + disclosed fees)"
  },
  "checklist": ["string"],
  "limitations": ["string"]
}
```

The JSON above is a conceptual example, not final implementation code. Use Pydantic models with explicit enums and field constraints. Avoid arbitrary free-form schema expansion from the LLM.

## AI proposal contract

`AIProposal` is a separate, untrusted candidate model, not a trusted `Finding`
and not a field of `AnalyzeResponse`. It is returned only inside the opt-in
comparison endpoint response described below. It contains:

```json
{
  "candidate_pattern": "free-form proposed pattern label",
  "proposed_category": "one of the existing FindingCategory values, or null",
  "evidence_quote": "proposed quote from page text, or null when no quote is available",
  "explanation": "untrusted AI rationale",
  "recommendation": "optional untrusted recommendation",
  "provenance": "ai",
  "status": "pending_validation"
}
```

`candidate_pattern` permits recording an unfamiliar label without expanding the
approved `FindingCategory` taxonomy. `proposed_category`, when present, is
restricted to that existing enum. The schema requires non-blank pattern and
explanation text and an explicit `evidence_quote` field; the quote may be null
when no quote is available, but a supplied quote cannot be blank. An optional
recommendation is not validation evidence. Provenance and status are fixed literals, default safely
to `ai` and `pending_validation`, and unknown fields are rejected. In
particular, callers cannot set a proposal to a trusted or validated status.

This schema does **not** prove that a quote occurs in extracted page text or
that an explanation is supported by it. Those checks belong to a later
comparison and validation stage. Proposals must not be presented as verified
findings, alter deterministic results, or affect financial calculations.

## AI proposal comparison (opt-in API)

The backend comparison helper accepts proposal data, deterministic `Finding`
objects, and the submitted page text. It returns one ordered comparison result
per proposal, containing the validated proposal (or `null` for malformed data),
its input index, a comparison status, an evidence status, and a concise reason.
Malformed proposals are isolated and do not prevent later proposals from being
compared.

Comparison statuses:

- `matched_existing_finding`: the proposal and a deterministic finding have
  exactly the same approved category and evidence quote.
- `additional_candidate`: the quote is present in page text, but no exact
  category-and-quote match or category conflict was established.
- `conflicting_candidate`: the exact quote is associated with a deterministic
  finding of a different category, and no same-category exact match exists.
- `category_mismatch`: the quote is present, but a recognized pattern-label cue
  conflicts with the proposal's canonical category; human review is required.
- `insufficient_evidence`: the quote is absent, unusable, not present verbatim
  in page text, or the proposal is malformed.

Evidence statuses are `quote_verified`, `missing_quote`, `quote_not_found`, and
`invalid_proposal`. A `quote_verified` result means only that the exact quote
occurs in submitted page text. It does not verify the explanation,
recommendation, classification, or truth of any claim. Matching is deliberately
literal; no semantic-equivalence inference is made. Comparison results remain
separate from `Finding` and do not promote proposals or change the public
`AnalyzeResponse`.

The comparison helper also flags a narrow set of known contradictions: an
explanation that says cancellation instructions are missing or unclear when the
existing cancellation extractor finds explicit cancellation information, or
that says price information is missing when the price extractor finds an
explicit currency-qualified price. These results use the existing
`insufficient_evidence` status and retain `quote_verified` when the quote itself
matches; the reason identifies the contradiction and the proposal remains
`pending_validation`. This is a conservative phrase check, not general
natural-language fact verification. It can miss paraphrases or produce a
false positive, so it does not validate claims or automatically reject,
promote, or persist proposals.

The comparison also reports `category_consistency` as `consistent`,
`inconsistent`, or `unverified`. A small token-based cue map reuses the seven
canonical `FindingCategory` values; for example, "time pressure", "scarcity",
and "countdown" signal `urgency_pressure`, while "surcharge" and "extra fee"
signal `additional_fee`. A recognized label/category contradiction produces
the explicit `category_mismatch` comparison status even when its quote is
present. Labels with no recognized cue, or cues spanning multiple categories,
remain `unverified` and require human review; the checker does not attempt
general natural-language classification or broaden the taxonomy. This is a
consistency warning only and does not validate or promote the proposal.

The opt-in `POST /api/v1/analyze/compare` endpoint accepts the same request
body as `POST /api/v1/analyze` and returns `{ "analysis": <AnalyzeResponse>,
"ai_comparison": <AIProposalComparison> }`. The original endpoint and response
shape remain unchanged. The comparison endpoint uses deterministic findings
only and defaults to an unconfigured no-op proposal provider; no external
provider call occurs unless a provider is explicitly injected/configured. The
comparison endpoint is the only route that returns AI proposals, and it labels
them as pending-validation candidates rather than trusted findings.

The legacy `AIInterpreter` still emits internal `Finding`-shaped values, but
`analyze_page_content` does not include them in the authoritative
`AnalyzeResponse.findings`, even when their evidence quote occurs in the page
text. If the optional legacy interpreter runs, the response limitation
discloses that its findings were excluded. Deterministic findings and financial
calculations remain authoritative. The opt-in comparison path remains separate
and returns untrusted `AIProposal` values only under `ai_comparison`.

## Candidate knowledge base (local and advisory)

`CandidateKnowledgeBase` stores proposal candidates in a local SQLite database
using Python's standard library. The default path is
`~/.darkpattern-guardian/candidate_knowledge_base.sqlite3`; set
`DPG_KNOWLEDGE_BASE_PATH` to select another location. The store records bounded
proposal fields and review events only. It does not retain the submitted page
text, title, or URL. The evidence quote is part of the candidate record.

The knowledge-base service also provides five built-in, read-only starter
guides for free-trial conversion, recurring payments, additional fees,
cancellation friction, and urgency/scarcity. Each guide includes evidence
signals to examine and cautionary context (for example, automatic renewal or a
genuine limited offer is not automatically deceptive). On an explicitly
configured Ollama comparison request, the service retrieves a bounded set of
guides relevant to the submitted text and may include manually promoted prior
candidates. Retrieval is performed in memory; it does not save the current
page. Any prior quote is labeled as historical advisory context, never evidence
for the current page. The comparison provider must continue to ground proposal
quotes in the current submitted text, and all proposals remain untrusted.
Relevance is selected with bounded keyword matching; this is a practical
lookup aid, not a semantic correctness or accuracy guarantee.

Candidate lifecycle states are `candidate`, `validated`, `rejected`, and
`promoted`. Each review event records an actor, rationale, timestamp, and
`manual_review` provenance. Validation requires an explicit
`evidence_supports_pattern=True` decision; a quote match alone cannot pass this
gate. Promotion is accepted only from `validated`. A rejected item must first
be explicitly reviewed to reopen it, and it must be validated again before
promotion. Invalid proposals are rejected before persistence; duplicate
proposals receive a stable content-derived identifier and do not reset an
existing lifecycle state.

Promoted records remain advisory knowledge. They are not `Finding` objects and
are not loaded by the deterministic analyzer or used to alter detection,
severity, evidence, or financial calculations. Lifecycle operations are
currently a backend service interface, not unauthenticated HTTP endpoints. The
existing `/api/v1/analyze/compare` route remains stateless and its response
shape is unchanged; persisting every comparison implicitly would introduce
unannounced retention of page-derived evidence. A future authenticated,
explicit persistence API requires a separate design.

### Offline demonstration

From `backend`, run:

```powershell
.venv\Scripts\python.exe -m app.ai.demo
```

This explicitly invokes `MockAIProposalProvider` on a synthetic checkout
fixture, compares only fixed quotes present in that fixture, and stores the
resulting advisory candidates in the local SQLite database. The output labels
the source `offline_mock`; it is not a trained model or real AI analysis. The
mock provider is never selected by normal analysis or by the comparison
endpoint. Set `DPG_KNOWLEDGE_BASE_PATH` before running the command to choose the
database file.

## Optional local Ollama proposal provider

`OllamaAIProposalProvider` is an opt-in source for the existing
`POST /api/v1/analyze/compare` pathway. It uses Ollama's local `/api/chat`
endpoint and the structured JSON output format. Returned items are validated
against `AIProposal`; malformed responses fail the proposal comparison safely.
Its prompt requests readable pattern labels and short exact quotes copied from
the submitted text. The comparison layer still checks quote presence against
that original text; a matching quote alone does not validate a proposal's
classification or other claims.
Ollama-generated labels, explanations, and recommendations are limited to 160,
600, and 300 characters respectively. The prompt asks for 1-3 concise,
page-grounded explanation sentences, but those instructions cannot guarantee
that a model's rationale is accurate. Proposals remain pending-validation
candidates; quote verification does not validate their explanations.
The normal `POST /api/v1/analyze` route does not use this provider. The default
`AI_PROPOSAL_PROVIDER=none` keeps the existing no-op behavior.

### Windows setup

Install Ollama for Windows, then in a separate PowerShell terminal start its
local service if it is not already running:

```powershell
ollama serve
```

In another terminal, download the model once:

```powershell
ollama pull qwen2.5:3b
ollama list
```

Then enable the provider for the backend process only and start the API from
the backend directory:

```powershell
Set-Location D:\darkpattern\backend
$env:AI_PROPOSAL_PROVIDER = "ollama"
$env:OLLAMA_BASE_URL = "http://127.0.0.1:11434"
$env:OLLAMA_MODEL = "qwen2.5:3b"
$env:OLLAMA_TIMEOUT_S = "60"
.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Alternatively, put these values in the backend `.env` file and restart the
backend process. Supported environment variables are:

| Variable | Default | Purpose |
|---|---|---|
| `AI_PROPOSAL_PROVIDER` | `none` | Set to `ollama` to opt in on `/api/v1/analyze/compare`. |
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Local Ollama server base URL; `/api/chat` is appended. |
| `OLLAMA_MODEL` | `qwen2.5:3b` | Model tag already available to Ollama. |
| `OLLAMA_TIMEOUT_S` | `60` | Per-request timeout in seconds; must be positive. |
| `LLM_MAX_TEXT_CHARS` | `10000` | Maximum page text sent to the local model. |

Send a request to `/api/v1/analyze/compare` to exercise proposals. The regular
`/api/v1/analyze` route remains unchanged. The provider sends bounded page title
and page text to the local Ollama service; no request is made while the
provider setting is `none`. Proposal results are never automatically persisted,
validated, promoted, or merged into trusted findings.

### Limitations and troubleshooting

- `Ollama` must be running at `OLLAMA_BASE_URL`, and `OLLAMA_MODEL` must match
  an installed model. Check `ollama list` and the local service before testing.
- Model startup/inference can exceed a short timeout; increase
  `OLLAMA_TIMEOUT_S` if needed. The provider makes one bounded request and does
  not retry automatically.
- A missing service, timeout, model error, malformed JSON, or invalid proposal
  produces a generic failed comparison status; deterministic analysis remains
  available and raw provider errors are not returned.
- Ollama structured output constrains format but does not make claims factual.
  Exact quote presence is checked separately; explanations and classifications
  remain untrusted suggestions requiring human review.
- Local inference can be resource-intensive and results can vary between model
  versions. Do not use proposals as legal conclusions, financial calculations,
  or autonomous rule updates.

## Money value
Represent monetary values as structured data, for example:
```json
{
  "amount": "9.99",
  "currency": "USD",
  "kind": "one_time | recurring | trial | fee",
  "interval": "monthly"
}
```
`amount` should be a decimal string. Use a supported currency code when identifiable. Do not silently assume a currency based only on user location.

## Validation rules
- Reject unknown category/severity/evidence-level values or map them through an explicit safe fallback.
- Confidence must be between 0 and 1.
- Evidence must be found verbatim in the request text; otherwise remove the quote and mark the finding as unsupported/unknown or discard the finding.
- Limit array lengths and string sizes.
- Validate all money values before calculation.
- Use structured error responses without exposing secrets, stack traces, or raw provider payloads.

## Error states
- `unsupported_page`
- `no_relevant_text`
- `backend_unavailable`
- `analysis_timeout`
- `invalid_model_output`
- `configuration_missing`
- `internal_error`

Exact enum names may be adapted during implementation, but the UI must distinguish user-actionable errors from internal failures.
