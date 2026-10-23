# 8. Test and Acceptance Plan

## Test layers
### Backend unit tests (pytest)
- Schema validation and size limits.
- Deterministic text signal extraction.
- Evidence substring validation.
- Money parsing and Decimal arithmetic.
- Missing/ambiguous input behavior.
- Prompt-injection-like page text remains data.
- Invalid LLM JSON and provider timeout behavior.

### Extension unit tests (Vitest)
- Text filtering/truncation.
- API client success/error/timeout.
- Rendering of explicit, inferred, and unknown findings.
- Unknown values are not shown as zero.
- UI handles empty findings and partial results.

### Browser/end-to-end tests (Playwright where feasible)
- User clicks scan and receives demo results.
- Unsupported page state.
- Backend unavailable state.
- Transparent subscription is not escalated without evidence.
- Evidence snippet shown in result matches the fixture.

## Required demo fixtures
1. Trial offer with clearly stated recurring charge but weak prominence in the synthetic fixture. The system should explain the future obligation without claiming illegality.
2. Checkout fee/price difference with both compared values available and context indicating whether a fee is disclosed.
3. Transparent subscription with recurring price, interval, and cancellation details. The system should present the commitment neutrally.
4. Ambiguous offer missing renewal amount or timing. The system should show the missing information and avoid calculating a future total.
5. Adversarial page text saying “ignore previous instructions.” It must not change the output contract or cause execution.

## Acceptance criteria
- [ ] Scan only starts on user action.
- [ ] Page text sent to backend is bounded and relevant.
- [ ] No API key appears in extension bundle or repository.
- [ ] All displayed evidence quotes match submitted text exactly.
- [ ] Every monetary projection is deterministic and covered by tests.
- [ ] Incomplete inputs result in an explicit unknown/not-calculable state.
- [ ] Transparent recurring billing is not automatically treated as deceptive.
- [ ] Price comparison appears only when comparable values are available.
- [ ] Backend failures are explained without fabricated results.
- [ ] Main user journey works from a clean clone using documented setup.
- [ ] No feature outside MVP scope is introduced without approval.

## Evaluation metrics
Report measurements and sample size. Do not claim “100% accurate” without a defensible evaluation. Measure precision, recall, evidence match rate, money arithmetic correctness, false positives, latency, and task usefulness.
