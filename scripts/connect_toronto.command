#!/bin/zsh
# Double-click on macOS to connect the ten Finch West sensors using a private prompt.
cd -- "${0:A:h}/.." || exit 1
./.venv/bin/python scripts/start_connected.py --port 8767 --toronto --record-duration 3600
result=$?
if [ "$result" -ne 0 ]; then
  read -r "reply?Press Return to close this window."
fi
exit "$result"
