#!/bin/zsh
# Double-click on macOS to enter credentials privately in Terminal.
cd -- "${0:A:h}/.." || exit 1
./.venv/bin/python scripts/start_connected.py --port 8766 --florida
result=$?
if [ "$result" -ne 0 ]; then
  read -r "reply?Press Return to close this window."
fi
exit "$result"
