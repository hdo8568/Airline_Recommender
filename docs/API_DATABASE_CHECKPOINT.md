# API and database checkpoint — September 10, 2026

## Completed

- `show preferences` lists the active airport, party size, total budget, stop limit, sorting, travel dates, and fixed clinic rules. Every result now includes active preferences.
- `reset`, `/reset`, and `start over` clear this conversation’s preferences and latest offers, restoring default clinic travel dates. They do not erase historical search records or affect other users. These commands make no provider or LLM calls.
- Each new conversation search saves the exact generated response, displayed offer objects (including IDs, times, conditions, and segments where supplied), input message, preferences, clinic context, counts, and timing in the existing SQLite searches table. Historical records remain after later searches and resets.
- The status view summarizes searches without dumping the newly stored conversation text or full offer objects.

## Live validation

| Scenario | Returned offers | Eligible | Seconds |
|---|---:|---:|---:|
| Different origin (BOS–IST, 2026-10-13 to 2026-10-23, 1 adult(s)) | 399 | 228 | 11.68 |
| Different dates (ORD–IST, 2026-10-12 to 2026-10-24, 1 adult(s)) | 680 | 666 | 5.33 |
| Two adults (ORD–IST, 2026-10-13 to 2026-10-23, 2 adult(s)) | 793 | 264 | 5.47 |

44 automated tests passed. All three sets of returned live offers were also replayed through the conversation code to verify exact response/offer snapshots and history preservation after reset. These replay checks did not call the API or send messages.

## Remaining boundaries

These are sampled routes and dates, not proof of all-provider coverage or every possible itinerary. Historical prices are snapshots, not current quotes. Pre-update searches cannot be reconstructed retroactively because they did not store full replies/offers. Search history records generated replies; message events separately track submission, not independent phone delivery. Baggage/refund fields remain as supplied and are not fully interpreted or verified. Booking is outside scope. The limited phrase parser remains active.

## When you next use it

Restart Start Live iMessage Replies.command to load the update. No key entry or Duffel setup is needed. Text show preferences, reset, Chicago under 1200, then why option 1?. The user-provided earlier test log already demonstrates real Duffel searches and reply submission through Messages; final phone receipt is not established by logs alone.
