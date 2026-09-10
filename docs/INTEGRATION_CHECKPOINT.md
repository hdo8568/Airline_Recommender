# Combined flights prototype checkpoint

September 10, 2026. Integration branch: integration/llm-api.

Combined the latest GitHub main (LLM agent and optional context URL adapter) with the local Duffel/database implementation. Preserved detailed flight segments, itinerary grouping, rejection reasons, bounded search retry, preferences/reset, SQLite search snapshots, and messaging diagnostics. Added validation of backend context types, dates, timezone, airport format, and default travel constraints.

Validation: 76 automated tests and 8 scripted agent checks passed. A real Claude/Duffel conversation searched Chicago under $1,200, restricted to nonstop, recommended a returned option, showed preferences, and reset. Both searches saved exact response/offer snapshots in temporary SQLite. No message was sent and nothing booked during this validation.

The SQLite application database already exists; it stores sessions, message events/cursors, and searches. Flight data comes from Duffel, not an Essos patient endpoint. Mock clinic context is intentional for this standalone prototype. The optional context URL adapter is available but is not connected to a real Essos backend; no such endpoint or credentials were supplied.

Remaining acceptance check: phone receipt using this exact combined revision with Claude and Duffel. Earlier checks of individual components are not evidence of delivery for this revision. Baggage/refund completeness, booking, multi-user routing, and real Essos patient integration remain outside this checkpoint.

Coordination: use this branch to review the combined code. Do not replace it with the older LLM branch, which lacks the local provider/history improvements. Secrets and runtime databases are excluded from Git. No further token setup is required in the user's existing configured LLM checkout; a new checkout needs local credentials separately.
