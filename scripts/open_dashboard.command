#!/bin/zsh
# Run the local dashboard independently of agent-tool terminal sessions.
cd -- "${0:A:h}/.." || exit 1
mkdir -p data/logs
print 'Dashboard: http://127.0.0.1:8766/?site=OBC-AG-SA-C618861'
print 'Keep this Terminal window open. Live data also requires the Toronto recorder.'
print 'Server diagnostics: data/logs/dashboard-8766.log'
./.venv/bin/python -m dashboard.server --port 8766 >> data/logs/dashboard-8766.log 2>&1
result=$?
print "Dashboard stopped (exit $result)."
read -r 'reply?Press Return to close this window.'
exit "$result"
