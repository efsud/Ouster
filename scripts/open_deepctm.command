#!/bin/zsh
cd -- "${0:A:h}/.." || exit 1
print 'DeepCTM capture and experiment: http://127.0.0.1:8768/'
./.venv/bin/python -m deepctm.preview
read -r "reply?Press Return to close this window."
