#!/bin/zsh
cd -- "${0:A:h}/.." || exit 1
print 'Watching Finch phase agreement. Requires the Finch collector and signal estimator.'
./.venv/bin/python -m dashboard.finch_groups
