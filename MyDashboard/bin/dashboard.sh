#!/bin/sh

STATE=$1
[ "$STATE" = /tmp/mydashboard.run ] && [ -d "$STATE" ] || exit 1
BIN=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd) || exit 1
ROOT=${BIN%/bin}
LC_ALL=C
TZ='EST5EDT,M3.2.0,M11.1.0'
city='Washington, DC'
URL='https://api.open-meteo.com/v1/forecast?latitude=38.9072&longitude=-77.0369&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m&hourly=temperature_2m&forecast_hours=12&temperature_unit=fahrenheit&wind_speed_unit=mph&timezone=America%2FNew_York&timeformat=unixtime'
if [ -f "$STATE/location" ]; then
    {
        read -r city &&
            read -r URL
    } < "$STATE/location" && [ -r "$STATE/timezone" ] ||
        { echo "MyDashboard: invalid prepared city settings." >&2; exit 1; }
    TZ=":$STATE/timezone"
elif [ -f "$ROOT/location.json" ]; then
    echo "MyDashboard: saved city was not prepared; launch through start.sh." >&2
    exit 1
fi
export LC_ALL TZ

layout=${2:-1448x1072}
case "$layout" in
    800x600|600x800)
        text_size=2
        ;;
    1448x1072)
        text_size=3 clock_size=11
        left=48 right=792
        clock_y=70 date_y=200 summary_y=350 quote_y=744
        calendar_y=84 forecast_y=450
        date_width=29 text_width=27 calendar_width=24
        date_format='%A, %B %d %Y'
        ;;
    *)
        echo "MyDashboard: unsupported layout: $2" >&2
        exit 1
        ;;
esac

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
    fbink -q -V -F IBM -S "$text_size" -X "$x" -Y "$y" -- "$padded"
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

panel_text() {
    fbink -q -V -b -F IBM -S "$3" -X "$1" -Y "$2" -- "$4"
}

panel_rect() {
    fbink -q -V -b -B BLACK -k "left=$1,top=$2,width=$3,height=$4"
}

panel_calendar() {
    cal_left=$1 cal_width=$2 cal_top=$3 cal_step=$4 cal_row=$5
    cal_grid=$((cal_left + (cal_width - (6 * cal_step + 32)) / 2))
    stamp=$(date '+%m %Y %d %w %B') || return 1
    set -- $stamp
    heading="$5 $2"
    panel_text "$((cal_left + (cal_width - ${#heading} * 16) / 2))" "$cal_top" 2 "$heading" || return 1
    awk -v m="$1" -v y="$2" -v today="$3" -v weekday="$4" \
        -v x="$cal_grid" -v top="$cal_top" -v step="$cal_step" -v row="$cal_row" '
        BEGIN {
            days = 31
            if (m == 4 || m == 6 || m == 9 || m == 11) days = 30
            if (m == 2) days = 28 + (y % 4 == 0 && (y % 100 != 0 || y % 400 == 0))
            first = (weekday - today + 36) % 7
            split("Su Mo Tu We Th Fr Sa", labels, " ")
            for (i = 0; i < 7; i++) print x + i * step, top + 40, 0, labels[i + 1]
            for (d = 1; d <= days; d++) {
                slot = first + d - 1
                printf "%d %d %d %02d\n", x + (slot % 7) * step,
                    top + 74 + int(slot / 7) * row, d == today, d
            }
        }
    ' | while read -r cx cy selected label; do
        if [ "$selected" -eq 1 ]; then
            fbink -q -V -b -h -F IBM -S 2 -X "$cx" -Y "$cy" -- "$label" || exit 1
        else
            panel_text "$cx" "$cy" 2 "$label" || exit 1
        fi
    done
}

panel_forecast() {
    forecast_column=$(($1 / 4)) forecast_top=$2 forecast_size=$3
    zone=$(date '+%Z') || return 1
    panel_text 16 "$((forecast_top + 16))" 1 "HOURLY TEMPERATURES ($zone)" || return 1
    if [ ! -s "$STATE/weather" ]; then
        panel_text 24 "$((forecast_top + 60))" 2 "No forecast available"
        return
    fi
    {
        read -r header
        index=0
        shown=0
        while read -r epoch temperature; do
            # Four samples span the next 12 hours: offsets 0, 3, 6, and 9.
            if [ "$((index % 3))" -eq 0 ] && [ "$shown" -lt 4 ]; then
                hour=$(date -d "@$epoch" '+%H:%M') || return 1
                fx=$((24 + shown * forecast_column))
                panel_text "$fx" "$((forecast_top + 50))" 2 "$hour" || return 1
                if [ "$temperature" != -- ]; then
                    temperature="$temperature F"
                fi
                panel_text "$fx" "$((forecast_top + 82))" "$forecast_size" "$temperature" || return 1
                shown=$((shown + 1))
            fi
            index=$((index + 1))
        done
    } < "$STATE/weather"
}

panel_icon() {
    case "$1" in
        0|1)
            rows='...#... .#...#. ..###.. #.###.# ..###.. .#...#. ...#...'
            ;;
        2|3|45|48)
            rows='....... ..###.. .#####. ####### ####### ....... .......'
            ;;
        51|53|55|56|57|61|63|65|66|67|80|81|82)
            rows='..###.. .#####. ####### ....... .#.#.#. #.#.#.. .......'
            ;;
        71|73|75|77|85|86)
            rows='..###.. .#####. ####### ....... .#...#. ###.### .#...#.'
            ;;
        95|96|99)
            rows='..###.. .#####. ####### ...#... ..##... ...##.. ...#...'
            ;;
        *) return 0 ;;
    esac
    printf '%s\n' "$rows" | awk -v x="$2" -v y="$3" '{
        for (r = 1; r <= NF; r++)
            for (c = 1; c <= length($r); c++)
                if (substr($r, c, 1) == "#") print x + (c - 1) * 7, y + (r - 1) * 7
    }' | while read -r ix iy; do
        panel_rect "$ix" "$iy" 7 7 || exit 1
    done
}

wrap_text() {
    awk -v width="$1" '{
        line = ""
        for (i = 1; i <= NF; i++) {
            word = $i
            if (line != "" && length(line) + length(word) + 1 > width) { print line; line = "" }
            while (length(word) > width) {
                print substr(word, 1, width)
                word = substr(word, width + 1)
            }
            line = line (line == "" ? "" : " ") word
        }
        print line
    }'
}

city_label() {
    printf '%s\n' "$city" | wrap_text "$1" | awk -v width="$1" '
        NR == 1 { first = $0 }
        NR == 2 { second = $0 }
        END {
            print first
            if (NR > 1) print (NR > 2 ? substr(second, 1, width - 3) "..." : second)
        }
    '
}

render_portrait() {
    label=$(city_label 13) || return 1
    panel_rect 240 12 1 296 &&
        panel_rect 0 320 600 1 &&
        panel_rect 240 340 1 280 &&
        panel_rect 0 656 600 1 &&
        panel_rect 150 702 1 62 &&
        panel_rect 300 702 1 62 &&
        panel_rect 450 702 1 62 &&
        panel_text 20 100 5 "$clock" &&
        panel_text 16 170 2 "$today" &&
        panel_text 84 212 3 "$weekday" &&
        panel_calendar 240 360 28 48 30 &&
        panel_text 16 364 2 "$label" || return 1

    if [ -s "$STATE/weather" ]; then
        read -r temp humidity code wind < "$STATE/weather" || return 1
        description=$(condition "$code" | wrap_text 13) || return 1
        panel_text 16 412 4 "$temp F" &&
            panel_icon "$code" 172 480 &&
            panel_text 16 550 2 "$description" &&
            panel_text 264 364 2 "Humidity" &&
            panel_text 264 398 3 "$humidity%" &&
            panel_text 440 364 2 "Wind" &&
            panel_text 440 398 2 "$wind mph" || return 1
    else
        panel_text 16 420 2 "Weather
unavailable" || return 1
    fi
    quote=$(printf '%s\n' "$quote" | wrap_text 20) || return 1
    panel_text 264 510 1 "DAILY QUOTE" &&
        panel_text 264 538 2 "$quote" &&
        panel_text 16 632 1 "${weather_status:- }" &&
        panel_forecast 600 656 2 &&
        panel_text 496 780 1 "Open-Meteo" &&
        fbink -q -V -w -s
}

render_compact() {
    clock=$(date '+%H:%M') || return 1
    today=$(date '+%Y / %m / %d') || return 1
    weekday=$(date '+%a') || return 1
    quote=$(daily_quote) || return 1

    # Compose the framebuffer without refreshing until the frame is complete.
    fbink -q -V -b -B WHITE -k || return 1
    if [ "$layout" = 600x800 ]; then
        render_portrait
        return
    fi
    label=$(city_label 20) || return 1
    panel_rect 350 12 1 236 &&
        panel_rect 0 260 800 1 &&
        panel_rect 350 276 1 160 &&
        panel_rect 0 456 800 1 &&
        panel_rect 200 502 1 62 &&
        panel_rect 400 502 1 62 &&
        panel_rect 600 502 1 62 &&
        panel_text 32 64 7 "$clock" &&
        panel_text 64 150 2 "$today" &&
        panel_text 140 194 3 "$weekday" &&
        panel_calendar 352 448 20 56 24 &&
        panel_text 24 280 2 "$label" || return 1

    if [ -s "$STATE/weather" ]; then
        read -r temp humidity code wind < "$STATE/weather" || return 1
        description=$(condition "$code" | wrap_text 20) || return 1
        panel_text 24 322 5 "$temp F" &&
            panel_icon "$code" 270 318 &&
            panel_text 24 382 2 "$description" &&
            panel_text 390 280 2 "Humidity" &&
            panel_text 390 312 3 "$humidity%" &&
            panel_text 590 280 2 "Wind" &&
            panel_text 590 312 3 "$wind mph" || return 1
    else
        panel_text 24 330 2 "Weather unavailable" || return 1
    fi
    panel_text 390 364 1 "DAILY QUOTE" &&
        panel_text 390 388 2 "$quote" &&
        panel_text 24 436 1 "${weather_status:- }" &&
        panel_forecast 800 456 3 &&
        panel_text 696 580 1 "Open-Meteo" &&
        fbink -q -V -w -s
}

render() {
    if [ "$text_size" -eq 2 ]; then
        render_compact
        return
    fi
    clock=$(date +%H:%M) || return 1
    today=$(date "+$date_format") || return 1
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

    fbink -q -V -F IBM -S "$clock_size" -X "$left" -Y "$clock_y" -- "$clock" &&
        block "$left" "$date_y" "$date_width" 2 "$today
$city" &&
        block "$left" "$summary_y" "$text_width" 5 "$summary
$weather_status" &&
        block "$left" "$quote_y" "$text_width" 4 "DAILY QUOTE

$quote" &&
        block "$right" "$calendar_y" "$calendar_width" 8 "$month_grid" &&
        block "$right" "$forecast_y" "$calendar_width" 14 "HOURLY TEMPERATURES

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
