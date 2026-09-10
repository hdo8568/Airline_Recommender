#!/bin/zsh
cd -- "${0:A:h}"
echo "READ-ONLY TEST: replies appear in this window. Nothing will be sent."
if [[ ! -x .local/decode-message ]]; then
  python3 -m essos_travel build-decoder || exit 1
fi
python3 -m essos_travel messages
echo "Press Enter to close."
read
