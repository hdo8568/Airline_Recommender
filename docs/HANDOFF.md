# Context for another task

The active implementation task owns code changes. Use this file for learning, test-conversation design, or review; coordinate before editing shared files.

## Assignment

Independent demonstration for Essos, outside the company repository. The patient already chose a clinic, and procedure dates are known. Find appropriate flights through an interactive iMessage conversation, retaining preferences across turns. No purchases. **Flights only:** hotels and clinic discovery are excluded by the user's later clarification.

## User preferences

Extremely concise explanations. Math/research background; unfamiliar with practical software setup. Prefer a small working draft and iterative feedback over extensive architecture brainstorming. Hands-off implementation, except necessary macOS permissions, account setup, and real-person messaging tests.

## Current draft

Python standard-library program; terminal simulator and direct local iMessage bridge share one conversation engine. Fictional clinic context, sample offers by default. Optional Claude preference extraction and Duffel search. State, history, keys and message checkpoints remain in ignored `.local/`. No customer website: Messages is the intended interface. No hosted messaging intermediary.

## What has and has not been verified

See ITERATION_1_REPORT.md for current results. A working sample conversation is not proof of real iMessage delivery, model access or live flight inventory. Those require separate checks. No unrelated inbox contents belong in Git or the handoff.

## Useful independent work

Write 5–10 realistic patient conversations and expected behavior. Prioritize changing budget/nonstop preferences, impossible clinic dates, ambiguous airports, provider errors and requests outside scope. Avoid adding hotel search, a website, or purchasing to this iteration.
