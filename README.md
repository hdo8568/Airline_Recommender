# Essos Airline Recommender — first iteration

A flights-only assistant for a patient whose clinic and procedure dates are already known. It searches, filters and explains round-trip flights, then revises the shortlist as preferences change. It cannot purchase tickets, search clinics, or find hotels.

**Status:** runnable offline prototype; Claude and Duffel adapters implemented but require credentials and live verification. The direct Mac iMessage bridge is implemented and fixture-tested; real receive/send testing and macOS permissions remain necessary. No live capability is implied by a successful offline demo.

## Try it now

Requires Python 3.11+ (standard library only). macOS is required only for Messages.

Double-click **Try Demo.command**, or run from this repository:

```sh
python3 -m essos_travel chat
```

Try this conversation:

1. `Find flights for my appointment`
2. `Chicago under 900`
3. `nonstop only`
4. `why option 1?`
5. `under 500`
6. `no budget limit`

The default uses **invented flights and a limited offline parser**, clearly labeled. It makes no network requests and sends no messages. Type `/reset` to clear preferences, `/help` for supported phrases, `/quit` to exit. `python3 -m essos_travel demo` runs a complete scripted example with isolated temporary state.

The first run creates `.local/patient.json`, a **fictional** clinic record with future dates. Dates persist, so edit or regenerate that file if the demo becomes stale. It includes a required arrival deadline and earliest return date; these are test inputs, not general medical guidance. The demo uses IST as its one destination. No real patient data is supplied.

## Optional AI and actual search

Double-click **Configure Access.command**, or run:

```sh
python3 -m essos_travel configure
python3 -m essos_travel doctor
```

Enter your Claude API key, a model ID available to your account, and a Duffel token. Hidden input protects keys from terminal display. Configuration does not validate access or make a paid call. These values can alternatively be supplied as `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`, and `DUFFEL_ACCESS_TOKEN` environment variables.

```sh
# Natural-language preferences, still sample flights:
python3 -m essos_travel chat --interpreter claude

# Natural-language preferences and Duffel flight search:
python3 -m essos_travel chat --interpreter claude --provider duffel
```

`duffel_test_…` tokens produce **SANDBOX** results, not reliable real schedules. `duffel_live_…` tokens select **LIVE** search; account access must permit it. Claude and live search can incur provider charges. The code calls the offer-search endpoint only, never an order/payment endpoint. Credentials are not present in the repository.

The model extracts requested preference changes through a constrained tool call. Python validates those fields, calls the flight source, filters actual results, and formats the answer. The model does not invent the displayed flight facts. API failures never silently switch to sample flights.

## iMessage setup

1. Confirm a **new iMessage** to your number/email arrives in Messages on this Mac. An SMS conversation or old synced history is not sufficient.
2. In macOS System Settings → Privacy & Security → **Full Disk Access**, enable the terminal application that will run this program. Quit and reopen that terminal. This permission is broader than this program's query; the program itself reads only eligible messages from the designated tester.
3. Build the helper (Apple Command Line Tools / `swiftc` required):

   ```sh
   python3 -m essos_travel build-decoder
   ```

4. Start **dry-run** mode, enter the tester’s full international phone number or iMessage email, then have them send a **new** message:

   ```sh
   python3 -m essos_travel messages
   ```

   Replies appear in Terminal only. Confirm the right sender and text are detected.

5. Stop with Ctrl+C. When ready to actually reply, run:

   ```sh
   python3 -m essos_travel messages --send
   ```

   macOS may request permission for Terminal to control Messages; allow it under **Automation → Messages**. Actual permissions/delivery can only be validated on the running Mac. Start a **new** test conversation message after changing modes: dry-run and send modes have separate checkpoints and preference state.

6. Add `--interpreter claude --provider duffel` when those connections have been verified. Keep the Mac awake, online, and the terminal running. No public server or inbound port is required.

Only one designated **direct iMessage** conversation is supported per process. Group chats, SMS, reactions, outgoing messages, unreadable attachments, and messages older than ten minutes are ignored. First startup skips existing messages. `STOP` pauses that tester’s processing; `START` resumes it (control messages are not themselves answered). Ctrl+C shuts down the process.

Incoming text is read from SQLite in read-only mode. Some text is in a legacy attributed-string archive; the small Swift helper decodes this in an isolated process. Sending uses Messages' AppleScript interface with arguments, not shell interpolation. The active Messages account determines the outgoing identity; verify it in the test.

Each message GUID is claimed before processing. A crash or ambiguous send is **not automatically retried**, avoiding duplicate replies at the cost of possibly missing one response. `submitted_unverified` means AppleScript returned successfully, not that delivery was independently confirmed. See recent statuses with `python3 -m essos_travel events`.

## Small, explicit boundaries

- Economy; 1–6 adults; one departure airport and one clinic airport; exact outbound/return dates.
- Budget is a **hard USD cap for the entire party’s round trip**. Non-USD offers are excluded; no currency conversion.
- Clinic restrictions are immutable in chat. Update the context file for corrected clinic instructions.
- Shortlist contains up to three distinct itineraries, sorted by cheapest or shortest outbound duration. It is not a claim to have searched the entire market.
- Fare conditions, baggage, refunds, loyalty points, accessibility requirements and booking links are not verified/supported in this draft.
- This is a demonstration, not a deployed patient service. No automatic recovery from every Messages schema change, no delivery guarantee, no background launch service.
- A local program is not automatically fully private: enabling Claude sends recent conversation and trip preferences to Anthropic; enabling Duffel sends search criteria to Duffel. Only fictional patient context should be used for this trial.

## Files and validation

| File | Purpose |
|---|---|
| `essos_travel/conversation.py` | Preferences, optional Claude interpretation, clinic checks, shortlist explanations |
| `essos_travel/providers.py` | Sample offers, Duffel search, independent offer validation |
| `essos_travel/messages.py` | Local reading, allowlist, durable message deduplication, sending |
| `essos_travel/storage.py` | SQLite conversation state and processing checkpoints |
| `.local/` | Ignored credentials, fictional patient, conversation history and compiled helper |
| `docs/ITERATION_1_REPORT.md` | What was built, decisions, checks, remaining work |
| `docs/HANDOFF.md` | Concise context for a separate learning/review task |

```sh
python3 -m unittest discover -s tests -v
python3 -m essos_travel demo
```

Tests use synthetic data, stubbed provider responses, and a fake Messages database. They never read personal messages or call external services. An optional GitHub Actions template is in docs/examples/github-tests.yml. Enabling it later requires a GitHub credential with workflow permission; it is not active in this iteration. It would run Python tests, not macOS integration tests.

## Implementation references

- [Duffel offer requests](https://duffel.com/docs/api/v2/offer-requests)
- [Duffel test-mode limitations](https://duffel.com/docs/api/overview/test-mode)
- [Claude tool definitions](https://platform.claude.com/docs/en/agents-and-tools/tool-use/define-tools)
- [Existing local Messages technique](https://github.com/openclaw/imsg) — consulted as a reference, not installed or used as a dependency.
- [Apple phone-number setup](https://support.apple.com/en-nz/108758)

## Troubleshooting sending

Full Disk Access permits reading messages; Automation permits controlling Messages to send. Run `Check Sending Access.command` from Terminal and allow the permission prompt. This check sends nothing. Send mode now performs this check before listening. Failures display a sanitized error code, also saved in ignored `.local/last-send-error.json`; uncertain messages are never retried automatically.
