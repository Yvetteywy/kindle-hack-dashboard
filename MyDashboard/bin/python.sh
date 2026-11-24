#!/bin/sh

if command -v python3 >/dev/null 2>&1; then
    exec python3 "$@"
fi
if [ -x /mnt/us/python3/bin/python3 ]; then
    exec /mnt/us/python3/bin/python3 "$@"
fi
echo "MyDashboard: city setup needs Python 3.9+ on PATH or in /mnt/us/python3/bin; see README." >&2
exit 1
