#!/bin/sh

BIN=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd) || exit 1
ROOT=${BIN%/bin}
PATH="$BIN:$PATH:/usr/bin:/usr/sbin:/bin:/sbin"
export PATH
LOG="$ROOT/mydashboard-setup.log"

fail() {
    echo "MyDashboard: $*; see $LOG." >&2
    echo "MyDashboard: $*" >> "$LOG"
    exit 1
}

case "${1:-}" in
    --detect-location)
        [ "$#" -eq 1 ] || fail "usage: setup.sh --detect-location"
        command -v curl >/dev/null 2>&1 || fail "missing curl"
        failure="could not detect city"
        ;;
    --font)
        [ "$#" -eq 2 ] || fail "usage: setup.sh --font {sans|serif|bitmap}"
        case "$2" in
            sans|serif|bitmap) ;;
            *) fail "unknown font: $2" ;;
        esac
        failure="could not save font"
        ;;
    *) fail "choose Detect city from Wi-Fi or a Font entry in KUAL" ;;
esac

orientation=portrait
if [ -f "$ROOT/last-orientation" ]; then
    IFS= read -r orientation < "$ROOT/last-orientation" ||
        fail "cannot read last dashboard orientation"
    case "$orientation" in
        portrait|landscape) ;;
        *) fail "invalid last dashboard orientation; remove last-orientation or start a dashboard explicitly" ;;
    esac
fi

/bin/sh "$BIN/python.sh" "$BIN/setup_server.py" --check >> "$LOG" 2>&1 ||
    fail "settings prerequisites are unavailable"

if [ -d /tmp/mydashboard.run ]; then
    /bin/sh "$BIN/stop.sh" >> "$LOG" 2>&1 || fail "could not stop dashboard"
fi

/bin/sh "$BIN/python.sh" "$BIN/setup_server.py" "$@" >> "$LOG" 2>&1 ||
    fail "$failure"

/bin/sh "$BIN/start.sh" "$orientation" >> "$LOG" 2>&1 ||
    fail "settings saved, but could not start dashboard"
echo "MyDashboard: requested $orientation dashboard startup; see $ROOT/mydashboard.log." >> "$LOG"
