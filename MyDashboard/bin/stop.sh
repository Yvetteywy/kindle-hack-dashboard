#!/bin/sh

STATE=/tmp/mydashboard.run
LOG=/mnt/us/mydashboard.log
[ -d "$STATE" ] || exit 0

# The worker checks this after each render and during its sleep.
: > "$STATE/stop" || { [ ! -d "$STATE" ] && exit 0; exit 1; }
remaining=45
while [ -d "$STATE" ] && [ "$remaining" -gt 0 ]; do
    sleep 1
    remaining=$((remaining - 1))
done
if [ -d "$STATE" ]; then
    echo "MyDashboard: stop timed out; see $LOG." >&2
    exit 1
fi
if [ "$(cat "$LOG.status" 2>/dev/null)" != 0 ]; then
    echo "MyDashboard: dashboard or UI restoration failed; see $LOG." >&2
    exit 1
fi
