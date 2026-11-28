#!/bin/zsh
cd -- "${0:A:h}/.." || exit 1
url=http://127.0.0.1:8770/
if ! curl --silent --fail "$url/api/status" >/dev/null; then
  (sleep 1; open "$url") &
  ./.venv/bin/python -m deepctm.florida_preview
else
  open "$url"
fi
