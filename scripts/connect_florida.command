#!/bin/zsh
# Double-click on macOS to enter credentials privately in Terminal.
cd -- "${0:A:h}/.." || exit 1
umask 077
export SSL_CERT_FILE="$PWD/.venv/lib/python3.11/site-packages/certifi/cacert.pem"
export OUSTER_DB="$PWD/data/florida-live.sqlite3"
print 'Florida live map: http://127.0.0.1:8773/?region=Florida'
print 'Live-only visualization; no new historical archive. Keep this Terminal open.'
./.venv/bin/python scripts/start_connected.py --port 8773 --florida --record-duration 0
result=$?
if [ "$result" -ne 0 ]; then
  read -r "reply?Press Return to close this window."
fi
exit "$result"
