# Essos flight assistant — first demonstration

September 10, 2026

## What this demonstrates

A tester sent iMessages to Henry’s Mac. The local program read them, generated sample flight recommendations, and sent replies through Messages. Henry confirmed that the tester received the replies on their phone.

The transcript below is condensed from the supplied Terminal logs. Repeated messages and blank inputs are omitted. It is a text record of the demonstration, not a screenshot or independent delivery audit.

## Conversation

**Tester:** Chicago under 900

**Assistant:** DEMO — invented flights and prices. ORD ↔ IST, departing October 13, 2026, returning October 23, 2026. Economy, one adult. Total round-trip prices in USD, cheapest first:

1. Example Budget — $490; up to two stops each way.
2. Example Connect — $640; up to one stop each way.
3. Example Direct — $890; nonstop each way.

All three sample itineraries arrive October 14 at 12:00 and depart on the return October 23 at 14:00. Times are local to each airport. Nothing booked.

**Tester:** nonstop only

**Assistant:** DEMO — invented flights and prices. Same route, dates, and passenger count. Example Direct — $890, nonstop each way.

**Tester:** Under 800

**Assistant:** DEMO — invented flights and prices. No USD offers from this search fit all your constraints. Try a higher budget, more stops, or different permitted dates. I haven’t relaxed anything.

## Result

The assistant remembered the departure airport and retained the nonstop requirement when the budget changed. It returned no matches rather than silently relaxing the user’s preferences. Actual iMessage reply receipt was confirmed by Henry.

## Scope and remaining work

This prototype uses fictional clinic context, invented flight offers, and a limited phrase parser. It does not book travel. Natural-language AI interpretation and real flight search integrations still need configuration and live verification. Hotels and clinic discovery are outside this first iteration.

The Mac and the Terminal program must remain running for replies. The bridge is restricted to the selected tester. A later local fix skips whitespace-only inputs; restarting the program loads updated code. Twenty-four automated tests pass, using simulated data rather than proving external service availability.
