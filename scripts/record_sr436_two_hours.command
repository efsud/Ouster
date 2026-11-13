#!/bin/zsh
cd -- "${0:A:h}/.." || exit 1
umask 077
export SSL_CERT_FILE="$PWD/.venv/lib/python3.11/site-packages/certifi/cacert.pem"
./.venv/bin/python -m deepctm.florida_capture --seconds 7200
read -r "reply?Press Return to close this window."
