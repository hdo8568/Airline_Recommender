#!/bin/zsh
cd -- "${0:A:h}"
python3 -m essos_travel.evaluate
echo "Press Enter to close."
read
