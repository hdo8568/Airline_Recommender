#!/bin/zsh
cd -- "${0:A:h}"
python3 -m essos_travel check-sending
echo "Press Enter to close."
read
