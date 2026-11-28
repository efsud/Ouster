#!/bin/zsh
cd -- "${0:A:h}/.." || exit 1
umask 077
export SSL_CERT_FILE="$PWD/.venv/lib/python3.11/site-packages/certifi/cacert.pem"
if [[ -z "$1" ]]; then
  read -r "capture_date?Recording date (YYYY-MM-DD): "
else
  capture_date="$1"
fi
./.venv/bin/python -m deepctm.florida_peak --date "$capture_date"
read -r "reply?Press Return to close this window."
