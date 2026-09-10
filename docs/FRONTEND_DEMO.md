# Local welcome page and travel rules

Open `Open Travel Page.command` from the Airline_Integration folder. Stop the old reply Terminal first with Control+C: both deliberately share one Messages lock. The launcher opens http://127.0.0.1:8765 on this Mac. Leave Terminal and Messages running.

A tester enters their iMessage phone number including country code, confirms consent, and presses Send me an iMessage. The Mac submits a fixed welcome message, then the existing Claude/Duffel agent handles replies. This version has one active tester at a time. Messages uses the enabled account on the Mac; keep Start new conversations from set to henryding37@gmail.com. It is a local page, not a public website. A public enrollment service would need a separately authenticated connection back to the Mac.

The server binds only to loopback, checks request origin/host and a per-launch token, and rate-limits enrollment. Welcome attempts are recorded before sending and not repeated automatically after uncertain delivery. A number gets at most one welcome attempt per day; resubmitting activates that conversation without another welcome. STOP/START controls remain available in Messages. Submission is not proof of delivery.

## Scheduling

Arrive at least seven full days before the procedure; depart home at least 24 hours after it. With an offset-aware procedure_at timestamp, checks use exact elapsed time. With only a date, conservatively use the beginning of that day for the arrival limit and the end for the return limit. For October 15 in Istanbul, arrival must be no later than October 8 at 00:00 and return departure no earlier than October 17 at 00:00. Default outbound moves earlier if needed. Existing valid later returns remain valid. The policy is enforced against actual flight times, not just departure dates or model text. This is the user-specified demo rule, not medical advice.

Validation: 83 automated tests plus eight scripted agent checks passed. New tests cover consent, number validation, duplicate/uncertain sends, rate limits, exact boundary times, UTC offsets, conservative date handling and old-context migration. Tests use a fake sender; no welcome was sent during development. The first real welcome and phone receipt remain a manual acceptance check.
