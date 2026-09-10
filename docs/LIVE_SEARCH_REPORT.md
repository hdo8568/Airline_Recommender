# Live search update — September 10, 2026

The updated evaluator successfully searched Duffel in live mode for ORD–IST, October 13–23, one adult, economy. The request took 8.66 seconds and returned 823 offers. Of these, 527 failed the arrival deadline check; 296 eligible fares represented 103 distinct itineraries. Rejection counts record the first failed check, not every potential failure.

The lowest qualifying fare at search time was $916.60. The similar-looking Lufthansa offers are different return itineraries: the cheapest returns home October 24, while the next options return October 23 at different times. The shortlist now shows route, outbound departure, and arrival home; asking why an option fits includes each flight number and segment time. Prices are snapshots and must be refreshed.

## Changes

- Keep individual segments, carrier identities, flight numbers, time zones, and supplied baggage/fare fields and offer conditions. Missing facts remain unknown.
- Group ranked fare variants by flight itinerary for display without deleting the underlying evaluation offers.
- Record rejection counts and offer IDs locally for troubleshooting.
- Add Start Live iMessage Replies.command for real search using the existing limited phrase parser. The original launcher remains the sample-data demo.

## Validation and limits

30 automated tests passed. A recorded-live-data conversation verified budget filtering, route display, and flight details without sending messages. One fresh live API search passed. The new launcher has not yet been tested end to end with a recipient; earlier sample-data iMessage delivery was confirmed by the user. No booking or payment was performed. No LLM was enabled.

The local tool Python needed the macOS CA bundle for this test; TLS verification remained enabled. User Terminal had already completed a live search successfully.

## Run

Stop the previous bridge with Control+C. Open Start Live iMessage Replies.command, enter the tester, then send Chicago under 1200, followed by why option 1? and under 800. Live results can differ from the recorded evaluation. The Mac must remain online and awake.
