# Essos Airline Recommender

Flights-only AI travel agent for a patient whose clinic and procedure dates are already known. It works through iMessage, keeps travel preferences across turns, searches live flights through Duffel, and can compare or recommend current options. It never purchases tickets.

## Current status

The combined code passes 76 automated tests and 8 scripted agent checks. Earlier user tests demonstrated iMessage transport and Claude with live Duffel searches. These separate checks do not establish phone delivery for this exact combined revision. See docs/INTEGRATION_CHECKPOINT.md for current evidence and remaining boundaries.

A real Essos patient backend is an optional future integration, not a missing flight-search database. The standalone demo still supports a fictional local patient record, while `--context-url` lets the same agent read the normalized trip context from a backend endpoint without changing the agent logic.

## Quick demo

Requires Python 3.11+.

```sh
python3 -m essos_travel demo
```

For an interactive local chat:

```sh
python3 -m essos_travel chat
```

## Configure Claude and Duffel

```sh
python3 -m essos_travel configure
python3 -m essos_travel doctor
```

Credentials are stored in ignored `.local/settings.json` unless supplied through environment variables.

Claude with mock flights:

```sh
python3 -m essos_travel chat --interpreter claude --provider mock
```

Claude with Duffel:

```sh
python3 -m essos_travel chat --interpreter claude --provider duffel
```

The code only uses Duffel offer search. It has no order, payment, or ticket-purchase path.

## Patient context

By default, the project uses `.local/patient.json`, creating a fictional example if needed.

You can still supply a JSON file:

```sh
python3 -m essos_travel chat --context /path/to/patient.json
```

Or point the agent at a backend endpoint that returns the same normalized context:

```sh
python3 -m essos_travel chat --context-url https://your-backend.example/patient-context
```

If the endpoint needs a bearer token, provide it without putting it in the repository:

```sh
export ESSOS_CONTEXT_TOKEN='...'
```

The backend response must contain:

```json
{
  "patient_id": "patient-123",
  "clinic": "Clinic name",
  "destination": "IST",
  "timezone": "Europe/Istanbul",
  "procedure_date": "2026-10-15",
  "arrival_deadline": "2026-10-14T18:00:00+03:00",
  "return_not_before": "2026-10-23",
  "outbound_date": "2026-10-13",
  "return_date": "2026-10-23"
}
```

Clinic and medical scheduling constraints are treated as fixed application context. The conversation can change flight-search preferences, not those constraints.

## iMessage

Build the Messages decoder:

```sh
python3 -m essos_travel build-decoder
```

Dry run, which reads a designated tester's new direct iMessages but sends nothing:

```sh
python3 -m essos_travel messages
```

Actual replies:

```sh
python3 -m essos_travel messages --send
```

Full live stack:

```sh
python3 -m essos_travel messages --send --interpreter claude --provider duffel
```

Add `--context-url ...` to that command when the backend patient-context endpoint is available.

The Mac terminal process needs Full Disk Access to read Messages and Automation permission to control Messages for sending. Only the explicitly entered direct-iMessage tester is processed. Group chats, SMS, reactions, outgoing messages, and stale messages are ignored.

## Conversation behavior

The agent already knows the clinic destination and required travel dates. It asks only for missing flight preferences and supports natural follow-ups such as:

- `Chicago under 1200`
- `nonstop only`
- `anything faster?`
- `compare the options`
- `which one would you recommend?`
- `what do you know about my trip?`
- `when do I need to arrive?`

Preferences persist across turns. Existing hard constraints are not silently relaxed when a search returns no matches.

## Architecture

```text
iMessage / terminal
        ↓
AdvancedAgent
        ↓
Claude intent interpreter or offline parser
        ↓
validated preference state + fixed patient context
        ↓
Duffel or mock flight provider
        ↓
deterministic eligibility checks
        ↓
comparison / recommendation
        ↓
iMessage / terminal reply
```

The LLM interprets supported user intent. Ordinary Python remains responsible for immutable clinic constraints, provider calls, validation, filtering, ranking, and displayed flight facts.

## Tests

```sh
python3 -m unittest discover -s tests -v
python3 scripts/run_agent_evals.py
```

Tests use synthetic data and stubbed providers. They do not send messages or make live provider calls.

## Important boundaries

- [Duffel offer requests](https://duffel.com/docs/api/v2/offer-requests)
- [Duffel test-mode limitations](https://duffel.com/docs/api/overview/test-mode)
- [Claude tool definitions](https://platform.claude.com/docs/en/agents-and-tools/tool-use/define-tools)
- [Existing local Messages technique](https://github.com/openclaw/imsg) — consulted as a reference, not installed or used as a dependency.
- [Apple phone-number setup](https://support.apple.com/en-nz/108758)

## Troubleshooting sending

Full Disk Access permits reading messages; Automation permits controlling Messages to send. Run `Check Sending Access.command` from Terminal and allow the permission prompt. This check sends nothing. Send mode now performs this check before listening. Failures display a sanitized error code, also saved in ignored `.local/last-send-error.json`; uncertain messages are never retried automatically.

## Live demo and diagnostics

Open `Start Live iMessage Replies.command` for real Duffel searches using the saved live key. The original `Start iMessage Replies.command` is still the mock demo. Stop the previous bridge with Control+C before changing launchers. Restarting is necessary to load edited code.

`Check Project Status.command` reports local readiness and recent search/error status without contacting external services or reading the personal Messages inbox. New searches are recorded in SQLite's `searches` table. See `docs/RELIABILITY_UPDATE.md` for retry behavior, validation, and limitations.

## Preferences and saved history

Text `show preferences` to see active restrictions or `reset` to clear them and restore the default clinic travel dates. Neither command makes a flight search. Reset does not delete historical records. New conversation searches save the exact response and displayed offer snapshots in SQLite, alongside search diagnostics. See `docs/API_DATABASE_CHECKPOINT.md` for the three-scenario live validation and limitations.
