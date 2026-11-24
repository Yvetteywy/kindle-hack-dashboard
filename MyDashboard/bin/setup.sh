#!/bin/sh

BIN=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd) || exit 1
PATH="$BIN:$PATH:/usr/bin:/usr/sbin:/bin:/sbin"
export PATH
LOG=/mnt/us/mydashboard-setup.log
URL=http://127.0.0.1:8765

fail() {
    echo "MyDashboard: $*; see $LOG." >&2
    echo "MyDashboard: $*" >> "$LOG"
    exit 1
}

for tool in curl nohup lipc-set-prop; do
    command -v "$tool" >/dev/null 2>&1 || fail "missing $tool"
done
/bin/sh "$BIN/python.sh" "$BIN/setup_server.py" --check >> "$LOG" 2>&1 ||
    fail "city setup prerequisites are unavailable"

if [ -d /tmp/mydashboard.run ]; then
    /bin/sh "$BIN/stop.sh" >> "$LOG" 2>&1 || fail "could not stop dashboard"
fi

ready() {
    [ "$(curl --noproxy '*' -fsS --max-time 1 "$URL/health" 2>/dev/null)" = mydashboard-setup-v1 ]
}
if ! ready; then
    set -- /bin/sh "$BIN/python.sh" "$BIN/setup_server.py"
    if command -v setsid >/dev/null 2>&1; then
        set -- setsid "$@"
    fi
    nohup "$@" </dev/null >> "$LOG" 2>&1 &
    setup_pid=$!
    remaining=10
    while ! ready; do
        remaining=$((remaining - 1))
        if [ "$remaining" -eq 0 ]; then
            kill "$setup_pid" 2>/dev/null || :
            fail "setup service did not become ready"
        fi
        sleep 1
    done
fi

lipc-set-prop com.lab126.appmgrd start \
    "app://com.lab126.browser#going?url=$URL/" >> "$LOG" 2>&1 ||
    fail "could not open Kindle browser"
