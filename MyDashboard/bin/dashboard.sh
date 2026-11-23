#!/bin/sh

STATE=$1
[ "$STATE" = /tmp/mydashboard.run ] && [ -d "$STATE" ] || exit 1
BIN=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd) || exit 1
ROOT=${BIN%/bin}
LC_ALL=C
TZ='PST8PDT,M3.2.0,M11.1.0'
export LC_ALL TZ

URL='https://api.open-meteo.com/v1/forecast?latitude=47.5301&longitude=-122.0326&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m&hourly=temperature_2m&forecast_hours=12&temperature_unit=fahrenheit&wind_speed_unit=mph&timezone=America%2FLos_Angeles&timeformat=unixtime'

stop_requested() { [ -f "$STATE/stop" ] || [ -f "$ROOT/STOP" ]; }
uptime_seconds() {
    read -r elapsed rest < /proc/uptime || return 1
    printf '%s\n' "${elapsed%%.*}"
}

fetch_weather() {
    curl -fsS --connect-timeout 5 --max-time 12 "$URL" > "$STATE/response" || return 1
    # Extract only the numeric objects and arrays requested from Open-Meteo.
    awk '
        function object(key, text) {
            if (!match(json, "\"" key "\"[[:space:]]*:[[:space:]]*[{][^}]*[}]")) return ""
            text = substr(json, RSTART, RLENGTH)
            sub(/^[^{]*[{]/, "", text)
            sub(/[}]$/, "", text)
            return text
        }
        function field(text, key, array) {
            if (!match(text, "\"" key "\"[[:space:]]*:[[:space:]]*")) return ""
            text = substr(text, RSTART + RLENGTH)
            if (array) {
                if (!match(text, /^\[[^]]*\]/)) return ""
                return substr(text, 2, RLENGTH - 2)
            }
            sub(/,.*/, "", text)
            return text
        }
        function clean(text) {
            gsub(/^[[:space:]]+|[[:space:]]+$/, "", text)
            return text
        }
        function number(text) { return text ~ /^-?[0-9]+([.][0-9]+)?$/ }
        { json = json $0 " " }
        END {
            c = object("current")
            h = object("hourly")
            t = clean(field(c, "temperature_2m", 0))
            rh = clean(field(c, "relative_humidity_2m", 0))
            code = clean(field(c, "weather_code", 0))
            wind = clean(field(c, "wind_speed_10m", 0))
            nt = split(field(h, "time", 1), times, ",")
            nv = split(field(h, "temperature_2m", 1), temps, ",")
            if (!number(t) || !number(rh) || code !~ /^[0-9]+$/ || !number(wind) ||
                nt != 12 || nv != nt) exit 1
            printf "%.0f %.0f %s %.0f\n", t, rh, code, wind
            for (i = 1; i <= nt; ++i) {
                epoch = clean(times[i])
                temp = clean(temps[i])
                if (epoch !~ /^[0-9]+$/ || (i > 1 && epoch - prev != 3600)) exit 1
                if (number(temp)) printf "%s %.0f\n", epoch, temp
                else if (temp == "null") print epoch, "--"
                else exit 1
                prev = epoch
            }
        }
    ' "$STATE/response" > "$STATE/weather.new" &&
        mv -f "$STATE/weather.new" "$STATE/weather"
}

condition() {
    case "$1" in
        0) echo "Clear" ;;
        1) echo "Mostly clear" ;;
        2) echo "Partly cloudy" ;;
        3) echo "Overcast" ;;
        45|48) echo "Fog" ;;
        51|53|55) echo "Drizzle" ;;
        56|57) echo "Freezing drizzle" ;;
        61|63|65) echo "Rain" ;;
        66|67) echo "Freezing rain" ;;
        71|73|75|77) echo "Snow" ;;
        80|81|82) echo "Rain showers" ;;
        85|86) echo "Snow showers" ;;
        95) echo "Thunderstorms" ;;
        96|99) echo "Thunderstorms with hail" ;;
        *) echo "Unknown conditions" ;;
    esac
}

daily_quote() {
    day=$(date +%j | sed 's/^0*//')
    case $((day % 5)) in
        0) printf 'Make room for a little\nunexpected joy.' ;;
        1) printf 'One small step is still\na change in direction.' ;;
        2) printf 'Leave a little space\nbetween plans.' ;;
        3) printf 'Notice what gets easier\nwhen you slow down.' ;;
        4) printf 'A quiet moment can be\nthe best part of a day.' ;;
    esac
}

calendar() {
    stamp=$(date '+%m %Y %d %w %B') || return 1
    set -- $stamp
    if command -v cal >/dev/null 2>&1 && TERM=dumb cal "$1" "$2"; then
        return
    fi
    # Some Kindle BusyBox builds omit cal. Derive the first weekday from today.
    awk -v m="$1" -v y="$2" -v day="$3" -v weekday="$4" -v month="$5" '
        BEGIN {
            days = 31
            if (m == 4 || m == 6 || m == 9 || m == 11) days = 30
            if (m == 2) days = 28 + (y % 4 == 0 && (y % 100 != 0 || y % 400 == 0))
            first = (weekday - day + 36) % 7
            print month, y
            print "Su Mo Tu We Th Fr Sa"
            for (i = 0; i < first; i++) printf "   "
            for (d = 1; d <= days; d++) {
                printf "%2d", d
                if ((first + d) % 7 == 0 || d == days) printf "\n"
                else printf " "
            }
        }
    '
}

# Pad old text away without clearing the whole panel on every minute tick.
block() {
    x=$1 y=$2 width=$3 height=$4 text=$5
    padded=$(printf '%s\n' "$text" | awk -v w="$width" -v h="$height" '
        BEGIN { pad = sprintf("%" w "s", "") }
        NR <= h { print substr($0 pad, 1, w) }
        END { for (i = NR; i < h; i++) print pad }
    ') || return 1
    fbink -q -V -S 3 -X "$x" -Y "$y" -- "$padded"
}

forecast() {
    if [ ! -s "$STATE/weather" ]; then
        echo "No forecast available"
        return
    fi
    {
        read -r header
        while read -r epoch temperature; do
            hour=$(date -d "@$epoch" '+%H:%M %Z') || return 1
            if [ "$temperature" = -- ]; then
                printf '%s   --\n' "$hour"
            else
                printf '%s   %3s F\n' "$hour" "$temperature"
            fi
        done
    } < "$STATE/weather"
}

render() {
    clock=$(date +%H:%M) || return 1
    today=$(date '+%A, %B %d %Y') || return 1
    month_grid=$(calendar) || return 1
    hourly=$(forecast) || return 1
    quote=$(daily_quote) || return 1

    if [ -s "$STATE/weather" ]; then
        read -r temp humidity code wind < "$STATE/weather" || return 1
        summary=$(printf 'Temperature: %s F\n%s\nHumidity: %s%%\nWind: %s mph' \
            "$temp" "$(condition "$code")" "$humidity" "$wind")
    else
        summary='Weather unavailable'
    fi

    fbink -q -V -S 11 -X 48 -Y 70 -- "$clock" &&
        block 48 200 29 2 "$today
Issaquah, WA" &&
        block 48 350 27 5 "$summary
$weather_status" &&
        block 48 744 27 4 "DAILY QUOTE

$quote" &&
        block 792 84 24 8 "$month_grid" &&
        block 792 450 24 14 "HOURLY TEMPERATURES

$hourly"
}

next_fetch=0
next_flash=0
next_draw=0
weather_status=
while ! stop_requested; do
    now=$(uptime_seconds) || exit 1
    if [ "$now" -ge "$next_fetch" ]; then
        next_fetch=$((now + 3600))
        if fetch_weather; then
            weather_status=
        else
            echo "MyDashboard: weather request failed or returned invalid data." >&2
            weather_status='Weather update failed'
            [ ! -s "$STATE/weather" ] || weather_status='Weather cached (stale)'
        fi
    fi
    stop_requested && break

    if [ "$now" -ge "$next_draw" ]; then
        if [ "$next_draw" -eq 0 ]; then
            next_draw=$((now + 60))
        else
            next_draw=$((next_draw + ((now - next_draw) / 60 + 1) * 60))
        fi
        if [ "$now" -ge "$next_flash" ]; then
            fbink -q -V -c -f -w || { echo "MyDashboard: full refresh failed." >&2; exit 1; }
            next_flash=$((now + 3600))
        fi
        render || { echo "MyDashboard: could not render dashboard." >&2; exit 1; }
    fi
    sleep 5
done
