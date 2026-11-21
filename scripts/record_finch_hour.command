#!/bin/zsh
cd -- "${0:A:h}/.." || exit 1
export SSL_CERT_FILE="$PWD/.venv/lib/python3.11/site-packages/certifi/cacert.pem"
./.venv/bin/python -m deepctm.capture --toronto --seconds 3600 --record-only --figures
read -r "reply?Press Return to close this window."
