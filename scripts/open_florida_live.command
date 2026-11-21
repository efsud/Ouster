#!/bin/zsh
cd -- "${0:A:h}/.." || exit 1
export OUSTER_DB="$PWD/data/florida-live.sqlite3"
print 'Florida map: http://127.0.0.1:8773/?region=Florida'
print 'Saved map view only. Use connect_florida.command for current objects.'
./.venv/bin/python -m dashboard.server --port 8773
