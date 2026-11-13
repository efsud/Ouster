#!/bin/zsh
# View both running collector sessions through one local dashboard.
cd -- "${0:A:h}/.." || exit 1
print 'Combined Finch + Florida map: http://127.0.0.1:8775/?region=Toronto&site=OBC-AG-SA-C257220#map'
print 'Keep the Finch and Florida collector Terminals open. This viewer needs no login.'
./.venv/bin/python -m dashboard.server --port 8775 --combined-live
