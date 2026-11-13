#!/bin/zsh
# Dedicated Finch live session; credentials are prompted privately in Terminal.
cd -- "${0:A:h}/.." || exit 1
umask 077
export SSL_CERT_FILE="$(./.venv/bin/python -m certifi)"
export OUSTER_DB="$PWD/data/finch-live.sqlite3"
print 'Finch live map: http://127.0.0.1:8774/?region=Toronto&site=OBC-AG-SA-C257220#map'
print 'Live-only visualization; no new historical archive. Keep this Terminal open.'
./.venv/bin/python scripts/start_connected.py --port 8774 --toronto --record-duration 0
result=$?
if [ "$result" -ne 0 ]; then
  read -r "reply?Press Return to close this window."
fi
exit "$result"
