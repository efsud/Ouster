#!/bin/zsh
cd -- "${0:A:h}/.." || exit 1
umask 077
./.venv/bin/python -m dashboard.public_live &
viewer_pid=$!
trap 'kill "$viewer_pid" 2>/dev/null' EXIT INT TERM
print 'Public live viewer: keep this Terminal and both collector Terminals open.'
print 'Anyone with the generated URL can view live objects in both corridors.'
./data/public-live/cloudflared tunnel --no-autoupdate --url http://127.0.0.1:8776 2>&1 | tee data/public-live/tunnel.log
