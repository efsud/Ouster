#!/bin/zsh
cd -- "${0:A:h}/.." || exit 1
./.venv/bin/python scripts/collect_phase_definitions.py
read -r 'reply?Press Return to close this window.'
