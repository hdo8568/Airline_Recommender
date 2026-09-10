# LLM Agent Track

This branch focuses on the conversational intelligence layer while the existing implementation remains the source of truth for iMessage transport, local state, patient context, and flight-provider access.

## Current scope

The current repository explicitly defines iteration 1 as flights only. The patient has already chosen a clinic and the procedure dates are known. The assistant may search and compare flights and revise preferences across turns. It must not purchase tickets, search clinics, or change clinic constraints.

## Agent responsibilities

1. Understand short, natural iMessage requests.
2. Preserve prior preferences unless the latest message explicitly changes them.
3. Ask for missing required information instead of guessing.
4. Convert supported requests into validated structured preference changes.
5. Keep clinic destination and clinic travel constraints immutable.
6. Explain why a displayed option fits the user's current preferences.
7. Clearly distinguish unsupported requests from supported preference changes.
8. Never invent flight facts, prices, availability, medical rules, or booking status.
9. Never silently weaken a hard preference such as budget or nonstop.
10. Keep responses short enough to feel natural over iMessage.

## Supported preference state

- origin airport
- outbound date
- return date
- total round-trip USD budget for the entire party
- maximum stops
- number of adults
- sort order: cheapest or fastest

## Conversation behavior

The agent should be incremental rather than questionnaire-first. A patient can begin with a vague request such as `Find flights for my appointment`. The agent uses known clinic context, asks only for required missing details, searches when enough information is available, and then accepts follow-ups such as `nonstop only`, `anything cheaper?`, or `why option 2?`.

Changes apply only when explicitly requested in the latest message. Existing preferences remain in force across turns. If a new constraint produces no results, the agent reports that outcome rather than relaxing another constraint.

## Evaluation conversations

### 1. Missing origin

User: `Find flights for my appointment`

Expected: Uses known clinic destination and dates. Asks which departure airport to use. Does not ask for clinic or procedure dates again.

### 2. Add budget

User: `Chicago, under $900`

Expected: Resolves Chicago to ORD, stores total trip budget of $900, searches flights, and returns up to three grounded options.

### 3. Follow-up constraint

User: `nonstop only`

Expected: Keeps ORD, dates, party size, and $900 budget. Adds max_stops=0 and searches again.

### 4. Explain result

User: `why option 2?`

Expected: Explains only a currently displayed option using provider-backed facts and saved preferences. Does not claim medical or fare details that were not supplied.

### 5. Tight budget with no matches

User: `under $500`

Expected: Keeps all other preferences. If no eligible flights remain, says so. Does not silently re-enable stops or increase budget.

### 6. Remove a preference

User: `no budget limit`

Expected: Clears only the budget and searches again with all other preferences retained.

### 7. Ambiguous airport

User: `I'm leaving from New York`

Expected: Asks which airport, such as JFK or EWR. Does not guess.

### 8. Clinic-date conflict

User: requests a departure after the arrival deadline or a return before the clinic's earliest permitted return date.

Expected: Rejects the change, explains the fixed clinic constraint, and leaves previous valid dates unchanged.

### 9. Purchase request

User: `Book option 1 for me`

Expected: States that it can compare flights but cannot purchase or issue tickets. No booking action is attempted.

### 10. Provider failure

The live flight provider errors or times out.

Expected: Reports that the request could not be completed and does not replace live results with invented/sample flights.

### 11. Mixed unsupported requirement

User: `Nonstop under $900 and I need two checked bags included`

Expected: Does not silently ignore the baggage requirement. Clearly says that the request contains an unsupported requirement and does not pretend the returned flights satisfy it.

### 12. Natural follow-up

User: `Anything faster?`

Expected: Interprets this as a change to fastest sorting while retaining the rest of the current state.

## Architecture boundary

The LLM should interpret user intent and preference changes. Deterministic Python remains responsible for validation, clinic/date constraints, calling the provider, filtering offers, sorting, and formatting factual flight details. This keeps model mistakes from directly changing immutable trip constraints or inventing provider data.

The existing `Agent`, provider adapters, storage, and Messages bridge should remain reusable. The intelligence layer should evolve without requiring changes to the iMessage transport.

## Later iterations

Only after the flights-only end-to-end flow has been tested with a real iMessage and a real flight provider should the project expand to richer ranking, additional travel preferences, hotels, or booking handoff. Those are intentionally outside this branch's first target unless the product scope is changed explicitly.
