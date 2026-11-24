#!/bin/sh

load_font() {
    FONT=sans
    if [ -f "$STATE/font" ]; then
        read -r FONT < "$STATE/font" || {
            echo "MyDashboard: cannot read saved font." >&2
            return 1
        }
    fi
    case "$FONT" in
        sans) FONT_FAMILY=DejaVuSans ;;
        serif) FONT_FAMILY=DejaVuSerif ;;
        bitmap) return 0 ;;
        *) echo "MyDashboard: unknown font: $FONT" >&2; return 1 ;;
    esac
    FONT_REGULAR="$ROOT/fonts/$FONT_FAMILY.ttf"
    FONT_BOLD="$ROOT/fonts/$FONT_FAMILY-Bold.ttf"
    [ -r "$FONT_REGULAR" ] && [ -r "$FONT_BOLD" ] || {
        echo "MyDashboard: missing bundled font files; copy the full MyDashboard/fonts folder." >&2
        return 1
    }
}

font_text() {
    ft_x=$1 ft_y=$2 ft_size=$3 ft_text=${4:- } ft_mode=${5:-normal}
    ft_metrics=$(printf '%s\n' "$ft_text" | awk '
        { if (length($0) > width) width = length($0) }
        END { print width, NR }
    ') || return 1
    set -- $ft_metrics
    ft_width=$(($1 * ft_size * 8))
    ft_height=$(($2 * ft_size * 8))
    ft_px=$((ft_size * 8))
    ft_style=REGULAR
    [ "$ft_size" -lt 3 ] || ft_style=BOLD
    if [ "$ft_mode" = display ] && [ "$FONT" != bitmap ]; then
        ft_px=$((ft_size * 11))
    fi
    if [ "$FONT" != bitmap ]; then
        [ "$ft_px" -ge 11 ] || ft_px=11
        [ "$FONT" != sans ] || ft_px=$((ft_px + 2))
        # FBInk expands line height when rasterized glyphs exceed rounded metrics.
        ft_height=$(($2 * (ft_px + 2)))
    fi
    [ "$((ft_x + ft_width))" -le "$SCREEN_WIDTH" ] || ft_width=$((SCREEN_WIDTH - ft_x))
    [ "$((ft_y + ft_height))" -le "$SCREEN_HEIGHT" ] || ft_height=$((SCREEN_HEIGHT - ft_y))
    set -- fbink -q -V
    [ "$FONT_BATCH" -eq 0 ] || set -- "$@" -b
    [ "$ft_mode" != invert ] || set -- "$@" -h
    if [ "$FONT" = bitmap ]; then
        "$@" -F IBM -S "$ft_size" -X "$ft_x" -Y "$ft_y" -- "$ft_text"
    else
        if [ "$ft_mode" = display ] || [ "$ft_mode" = heading ]; then
            set -- "$@" -m
            ft_style=BOLD
        fi
        "$@" -t "regular=$FONT_REGULAR,bold=$FONT_BOLD,px=$ft_px,style=$ft_style,left=$ft_x,top=$ft_y,right=$((SCREEN_WIDTH - ft_x - ft_width)),bottom=$((SCREEN_HEIGHT - ft_y - ft_height)),padding=BOTH,notrunc" -- "$ft_text"
    fi
}
