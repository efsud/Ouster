#!/bin/zsh
cd "$(dirname "$0")/.."
print "Finch rolling figures: http://127.0.0.1:8768/finch"
print "Keep the Finch live collector running."
exec .venv/bin/python -m deepctm.finch_rolling
