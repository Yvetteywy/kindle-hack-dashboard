#!/bin/sh

BIN=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd) || exit 1
ROOT=${BIN%/bin}
PATH="$BIN:$PATH:/usr/bin:/usr/sbin:/bin:/sbin"
export PATH
STATE=/tmp/mydashboard.run
LOG=/tmp/mydashboard.log

if [ "${1:-}" != --run ]; then
    command -v nohup >/dev/null 2>&1 || { echo "MyDashboard: missing nohup" >&2; exit 1; }
    set -- /bin/sh "$BIN/start.sh" --run
    if command -v setsid >/dev/null 2>&1; then
        set -- setsid "$@"
    fi
    nohup "$@" </dev/null >>"$LOG" 2>&1 &
    exit 0
fi

fail() {
    echo "MyDashboard: $*" >&2
    exit 1
}

for tool in fbink fbdepth initctl lipc-set-prop curl awk date sed; do
    command -v "$tool" >/dev/null 2>&1 || fail "missing $tool; see README."
done
date -u -d '@0' '+%H:%M' >/dev/null || fail "date must support Unix timestamps via -d @SECONDS."

umask 077
mkdir "$STATE" || fail "already running, or stale state; see README."
rotation=
ui_job=
restore_ui=0
restore_power=0
worker=

cleanup() {
    result=$?
    trap '' HUP INT TERM
    if [ -n "$worker" ]; then
        kill -TERM "$worker" 2>/dev/null || :
        wait "$worker"
    fi
    if [ "$restore_ui" -eq 1 ]; then
        fbdepth -q -r "$rotation" || { echo "MyDashboard: could not restore rotation" >&2; result=1; }
        if ! initctl status "$ui_job" | grep -q ' start/running'; then
            initctl start "$ui_job" || { echo "MyDashboard: could not restart $ui_job" >&2; result=1; }
        fi
    fi
    if [ "$restore_power" -eq 1 ]; then
        lipc-set-prop -i com.lab126.powerd preventScreenSaver 0 ||
            { echo "MyDashboard: could not re-enable screensaver" >&2; result=1; }
    fi
    if [ -f "$ROOT/STOP" ]; then
        rm -f "$ROOT/STOP"
    fi
    printf '%s\n' "$result" > "$LOG.status"
    rm -f "$STATE/stop" "$STATE/weather" "$STATE/response" "$STATE/weather.new"
    rmdir "$STATE" || result=1
    exit "$result"
}

trap cleanup 0
trap 'exit 1' INT TERM
stop_requested() { [ -f "$STATE/stop" ] || [ -f "$ROOT/STOP" ]; }

rm -f "$LOG.status"
sleep 2
stop_requested && exit 0

rotation=$(fbdepth -q -o) || fail "cannot read framebuffer rotation."
case "$rotation" in [0-3]) ;; *) fail "invalid framebuffer rotation: $rotation" ;; esac

for job in lab126_gui framework; do
    if initctl status "$job" 2>/dev/null | grep -q ' start/running'; then
        ui_job=$job
        break
    fi
done
[ -n "$ui_job" ] || fail "neither lab126_gui nor framework is running."

restore_power=1
lipc-set-prop -i com.lab126.powerd preventScreenSaver 1 || fail "could not disable screensaver."
restore_ui=1
initctl stop "$ui_job" || fail "could not stop $ui_job."

landscape() {
    fbdepth -q -r "$1" &&
        fbink -q -V -e | grep -q 'screenWidth=1448;screenHeight=1072;'
}
landscape CW || landscape CCW || fail "FBInk did not report a 1448x1072 framebuffer."
stop_requested && exit 0

/bin/sh "$BIN/dashboard.sh" "$STATE" </dev/null &
worker=$!
wait "$worker"
result=$?
worker=
exit "$result"
