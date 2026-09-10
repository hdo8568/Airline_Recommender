# Iteration 1 report

September 10, 2026

## Outcome

Built a runnable **flights-only prototype**, with one engine shared by a terminal demonstration and a local iMessage connection. The offline conversation works. Real iMessage delivery and live Claude/Duffel requests remain unverified because this new project has no credentials configured and the Mac messaging permission/test flow has not been completed.

No actual messages were sent, no personal inbox was read, and no tickets were purchased during development.

## What was built

- Fictional clinic context with fixed arrival deadline and earliest return date.
- Persistent preferences: departure airport, exact travel dates, total party USD budget, maximum stops, number of adults and sorting preference.
- Up to three flight options; follow-up changes retain other preferences. “Why option 1?” explains the current result.
- Explicit DEMO, SANDBOX and LIVE modes. Failure does not fall back to invented offers.
- Optional Claude integration to translate natural language into validated preference changes.
- Duffel offer-search integration; no order, booking or payment capability.
- Read-only Mac Messages polling, one tester allowlist, direct iMessages only, AppleScript replies, message-ID deduplication, STOP/START, and a read-only dry-run mode.
- Swift helper for archived message text, simple double-click launchers, setup documentation, and automated tests.

## Design choices and reasons

| Choice | Why |
|---|---|
| Messages as the intended interface | Directly tests the assigned experience without building a website first. |
| Terminal simulator uses the same engine | The conversation can be tested immediately without Mac permissions or contacting another person. |
| Python standard library + small Swift helper | No Python package installation or framework setup; Swift reads the native archive format. |
| Sample data and offline parser by default | Provides a reproducible, no-credential checkpoint; explicitly not called an AI/live-flight demo. |
| Claude extracts changes; code filters and formats offers | Natural language does not control clinic restrictions or invent flight prices. |
| SQLite state and event checkpoints | Retains preferences and avoids repeat responses across restarts. |
| No automatic retry after uncertain sending | Prioritizes avoiding duplicate replies; a crash may require a fresh tester message. |
| Direct Messages integration | Matches the meeting’s local-Mac approach without a hosted messaging intermediary. |
| Flights only | Follows the user's clarified scope; hotels and clinic search were removed. |

## Checks completed

- 21 automated Python tests passed locally.
- Full scripted conversation passed: missing airport → Chicago/budget → nonstop → explanation → no matching result → removing budget.
- Synthetic Messages database checked sender isolation, group/SMS/reaction/outgoing exclusions, stale-message filtering, read-only access, first-start history skipping, duplicate suppression, dry-run behavior, uncertain-send handling and STOP/START.
- Arrival checked in the destination timezone, including an offset-aware late-arrival example; early returns rejected without overwriting previous dates.
- Non-USD prices, expired offers, wrong routes and disallowed return-leg stops excluded.
- Stubbed Claude/Duffel contract tests passed; these are **not** live provider tests.
- Swift helper compiled on this Mac and passed a synthetic archived-text round-trip including Unicode.
- Credentials, local patient context, conversation state and compiled assets are excluded from Git.

GitHub rejected creating an Actions workflow because the available credential lacks workflow permission. The optional configuration is saved as docs/examples/github-tests.yml instead; remote Actions are not enabled. All reported test results are local.

## Honest limitations

1. **iMessage remains an integration checkpoint:** macOS Full Disk Access and Automation permissions, sender identity, actual incoming message format and delivery must be tested on this Mac. AppleScript success is recorded as submitted, not confirmed delivered.
2. **AI/live search require access:** Claude credentials/model and Duffel token/account access must be supplied. The default is an offline parser, not a language model. Duffel test data is not real inventory.
3. **Narrow trip support:** economy, 1–6 adults, USD, one departure airport, one fixed clinic airport, exact dates. No fare-rule verification, baggage validation, points, accessible-travel requirements or booking links.
4. **Prototype operations:** keep the Mac awake and program running. No background service, multi-user deployment or delivery guarantee. Messages schema/archive behavior may vary with macOS.
5. **Simplified recommendation:** price or outbound duration ordering; not a personalized utility model or whole-market comparison.

## Next steps, in order

1. Try the offline conversation using **Try Demo.command**.
2. Confirm a new iMessage reaches this Mac; grant Terminal Full Disk Access.
3. Run **Check iMessage.command**, enter one tester, and verify read-only detection.
4. Run **Start iMessage Replies.command** for an intentional automatic-reply test; grant Automation permission when requested.
5. Configure Claude/Duffel using **Configure Access.command**, then verify each connection separately before combining them.
6. Get feedback from one short conversation and improve only the failure it exposes.

## Iteration evidence

The first offline run preserved the $900 budget when “nonstop only” was added. Tightening the budget to $500 produced no matching offers rather than silently reintroducing connecting flights. Switching providers clears old quotes so sample offers cannot be mislabeled live. Date and sender checks are ordinary code, independent of the model prompt.
