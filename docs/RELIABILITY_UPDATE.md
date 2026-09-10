# Reliability update — September 10, 2026

## What changed

- Flight-search requests retry once for a temporary connection error or selected temporary HTTP errors. Each attempt has a 12-second socket timeout; short retry delays are bounded. Longer provider retry instructions return a useful error instead of blocking the conversation. This is a socket timeout, not a strict total wall-clock deadline.
- Authentication errors, invalid search requests, certificate errors, and unreadable responses produce separate explanations. Raw provider error bodies and credentials are not displayed.
- Only the Duffel offer-search endpoint is eligible for retries. Booking endpoints and uncertain iMessage sends are not automatically retried. A repeated search can incur another provider search charge.
- macOS trusted certificates are loaded while keeping certificate verification enabled.
- New conversation searches are recorded in a SQLite searches table with elapsed time, source, preferences, counts, and first-failure rejection categories. This is an additive schema change; existing sessions/events/cursors remain available.
- Incoming whitespace, invisible formatting characters, and Apple attachment placeholders are cleaned. If plain text is unusable, the reader can try the attributed-text decoder. This addresses plausible causes of the earlier blank-looking inputs; the exact original message encoding was not inspected.
- Terminal displays when processing begins and when a reply is prepared/submitted. No extra progress messages are sent to the tester.
- Check Project Status.command shows local configuration, whether a reply bridge is running, and recent processing/search status. It does not read the personal Messages inbox or make network requests.

## Verification

39 automated tests passed, including bounded retries, no retry of non-search requests, rate-limit delays, authentication errors, certificate checking, invalid JSON, invisible text, and persisted search diagnostics.

One fresh real Duffel evaluation returned 823 normalized offers in 6.39 seconds. 527 first failed the clinic arrival deadline; 296 eligible fares represented 103 distinct itineraries. No booking or iMessage was sent during this verification.

## Remaining limits

Real-data iMessage delivery still needs the final recipient test. Earlier sample-data delivery was confirmed. The phrase parser is still in use; no LLM is configured. The bridge processes one tester sequentially, so a slow search delays processing subsequent messages, including STOP. Socket timeouts do not constitute a strict end-to-end deadline. No production hosting, automatic daemon restart, complete fare interpretation, or independent delivery receipts were added.

## Use

When ready, stop the older reply window with Control+C and launch Start Live iMessage Replies.command. Enter the tester's exact iMessage sender address, including +1 for a US phone number. Wait for the listening message before the tester sends a new text.

Suggested live demo: Chicago under 1200; why option 1?; nonstop only; under 800. Prices and matches can change. Check Project Status.command can be run separately for troubleshooting.

No new Duffel setup or token entry is needed. Local credentials and result files remain excluded from Git. This update is a local checkpoint; no GitHub push was attempted.
