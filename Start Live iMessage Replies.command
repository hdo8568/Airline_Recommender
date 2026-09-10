#!/bin/zsh
cd -- "${0:A:h}"
echo "Real Duffel flight search; limited phrase parser. Nothing is booked."
echo "Only the tester you enter receives replies. Stop any other reply window first with Control+C."
python3 -c 'from essos_travel.config import settings; import sys; sys.exit(0 if settings().get("DUFFEL_ACCESS_TOKEN", "").startswith("duffel_live_") else "A live Duffel token must be configured first.")' || exit 1
if [[ ! -x .local/decode-message ]]; then
  python3 -m essos_travel build-decoder || exit 1
fi
python3 -m essos_travel messages --send --provider duffel
echo "Press Enter to close."
read
