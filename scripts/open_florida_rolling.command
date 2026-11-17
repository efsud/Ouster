#!/bin/zsh
cd -- "${0:A:h}/.." || exit 1
print 'Florida rolling figures: http://127.0.0.1:8768/florida'
print 'Keep the Florida live collector and figures viewer running.'
./.venv/bin/python -m deepctm.florida_rolling
