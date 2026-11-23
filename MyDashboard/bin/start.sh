#!/bin/sh

BIN=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd) || exit 1
ROOT=${BIN%/bin}
PATH="$BIN:$PATH:/usr/bin:/usr/sbin:/bin:/sbin"
export PATH
STATE=/tmp/mydashboard.run
LOG=/mnt/us/mydashboard.log

if [ "${1:-}" = --run ]; then
    orientation=${2:-landscape}
else
    orientation=${1:-landscape}
fi
case "$orientation" in
    landscape|portrait) ;;
    *) echo "MyDashboard: unknown orientation: $orientation" >&2; exit 1 ;;
esac

if [ "${1:-}" != --run ]; then
    command -v nohup >/dev/null 2>&1 || { echo "MyDashboard: missing nohup" >&2; exit 1; }
    set -- /bin/sh "$BIN/start.sh" --run "$orientation"
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

display=$(fbink -q -V -e) || fail "cannot read framebuffer dimensions."
dimensions=$(printf '%s\n' "$display" |
    sed -n 's/.*screenWidth=\([0-9][0-9]*\);screenHeight=\([0-9][0-9]*\);.*/\1x\2/p')
case "$dimensions" in
    600x800|800x600)
        if [ "$orientation" = portrait ]; then
            target_dimensions=600x800
        else
            target_dimensions=800x600
        fi
        ;;
    1072x1448|1448x1072)
        [ "$orientation" = landscape ] || fail "portrait layout requires a 600x800 display. Kindle UI left unchanged."
        target_dimensions=1448x1072
        ;;
    '') fail "cannot parse framebuffer dimensions." ;;
    *) fail "unsupported framebuffer: $dimensions; dashboard requires 800x600 or 1448x1072 landscape. Kindle UI left unchanged." ;;
esac

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

display_matches() {
    fbink -q -V -e | grep -q "screenWidth=${target_dimensions%x*};screenHeight=${target_dimensions#*x};"
}
rotate_display() {
    fbdepth -q -r "$1" && display_matches
}
if ! display_matches; then
    if [ "$orientation" = portrait ]; then
        rotate_display UR || rotate_display UD || fail "FBInk did not report a $target_dimensions framebuffer."
    else
        rotate_display CW || rotate_display CCW || fail "FBInk did not report a $target_dimensions framebuffer."
    fi
fi
stop_requested && exit 0

/bin/sh "$BIN/dashboard.sh" "$STATE" "$target_dimensions" </dev/null &
worker=$!
wait "$worker"
result=$?
worker=
exit "$result"
