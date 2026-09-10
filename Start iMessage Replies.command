#!/bin/zsh
cd -- "${0:A:h}"
echo "This sends automatic replies to the ONE tester you enter. Uses SAMPLE flights and the offline parser."
echo "Use Ctrl+C to stop. The tester can text STOP to pause and START to resume."
if [[ ! -x .local/decode-message ]]; then
  python3 -m essos_travel build-decoder || exit 1
fi
python3 -m essos_travel messages --send
echo "Press Enter to close."
read
