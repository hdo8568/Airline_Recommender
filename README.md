# Essos Airline Recommender

Flights-only AI travel agent for a patient whose clinic and procedure dates are already known. It works through iMessage, keeps travel preferences across turns, searches live flights through Duffel, and can compare or recommend current options. It never purchases tickets.

## Current status

The flights MVP has been exercised end to end on a Mac with a real iMessage conversation, Claude, and live Duffel search. The automated suite passed 47 tests before the backend-context adapter was added. The iMessage bridge, Claude interpretation, live flight retrieval, preference persistence, comparison, and recommendation paths have therefore all been demonstrated.

The remaining product integration is the source of patient context. The standalone demo still supports a fictional local patient record, while `--context-url` lets the same agent read the normalized trip context from a backend endpoint without changing the agent logic.

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

- Flights only.
- Economy, 1–6 adults.
- One departure airport and one clinic airport.
- Exact outbound and return dates.
- Budget is a hard total round-trip USD cap for the whole party.
- No automatic currency conversion.
- No booking/payment/ticket issuance.
- Baggage, refund rules, loyalty points, and accessibility requirements are not verified in this MVP.
- Prices and availability can change after a Duffel response.
- Claude receives a minimized projection of trip context rather than the entire patient object.

## Main files

| File | Purpose |
|---|---|
| `essos_travel/advanced_agent.py` | Context questions, comparisons, recommendations |
| `essos_travel/conversation.py` | Preference state, deterministic validation, search response formatting |
| `essos_travel/llm_interpreter.py` | Claude intent extraction with minimized patient context |
| `essos_travel/context_source.py` | Local-file or backend-API patient context |
| `essos_travel/providers.py` | Mock and Duffel flight sources |
| `essos_travel/messages.py` | Local macOS Messages receive/send bridge |
| `essos_travel/storage.py` | Conversation and message-processing state |
| `essos_travel/ranking.py` | Deterministic recommendation ranking |
