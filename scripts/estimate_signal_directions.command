#!/bin/zsh
cd -- "${0:A:h}/.." || exit 1
print 'Learning ESTIMATED phase directions from running Finch and Florida collectors.'
print 'Keep both collector Terminals running. No credentials needed here.'
print 'Evidence is provisional; ambiguous directions remain unknown.'
./.venv/bin/python -m dashboard.signal_estimation
