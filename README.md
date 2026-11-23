
# MyDashboard for Kindle

MyDashboard replaces the stock UI with a borderless FBInk dashboard
on a jailbroken Kindle. It shows
Issaquah weather from [Open-Meteo](https://open-meteo.com/), a Pacific-time
clock and calendar, and a rotating daily quote. The screen updates once per
minute, with a flashing full-screen refresh and weather fetch at startup and
every hour. If a request fails, the dashboard labels the last successful
forecast from that session as stale.

The default layout selects 800×600 landscape for the basic Kindle
(8th generation), or the original 1448×1072 landscape layout for higher-resolution
devices such as the Paperwhite 4. A 600×800 portrait layout is also available
for the basic Kindle. The compact layouts are inspired by
[KindleReborn](https://github.com/Yvetteywy/KindleReborn): divided clock/calendar
and weather panels, today's calendar date highlighted, a large temperature,
pixel-art weather icon, and four forecast samples at offsets 0, 3, 6, and 9 hours
from the fetched forecast's first entry. The larger layout retains all 12 hourly
rows. Both run locally with FBInk, without a browser, address bar, or rendering
server. Fonts are FBInk's built-in bitmap fonts, not the reference's web fonts;
the interface is display-only, with no touch settings.

The compact weather panel shows current temperature, conditions, humidity and
wind, plus the daily quote. It does not currently fetch feels-like temperature,
daily highs/lows, UV, rain probability or AQI. Missing weather is shown as
unavailable, and failed updates label cached readings stale. The compact frame
is composed without intermediate display updates, then refreshed once per
minute; the hourly flashing refresh remains.

Startup
checks the display dimensions without changing rotation and rejects unsupported
screens before stopping the Kindle UI or changing screensaver settings.
Device rotation and UI recovery still need verification on actual hardware.

## Install and use

1. Install KUAL and copy [MyDashboard](./MyDashboard/) to
   `/mnt/us/extensions/MyDashboard/`. Keep the scripts executable and use LF
   line endings.
2. Put compatible ARM Kindle builds of **both** `fbink` and `fbdepth` from
   [FBInk](https://github.com/NiLuJe/FBInk) in
   `/mnt/us/extensions/MyDashboard/bin/` (or on the Kindle's `PATH`). The Kindle
   also needs `curl` with working HTTPS certificate validation and the usual
   BusyBox tools. The dashboard uses `cal` if installed and draws an equivalent
   calendar itself otherwise. No separate weather server or API key is needed.
3. Connect to Wi-Fi and choose **MyDashboard → Start dashboard** in KUAL for
   landscape, or **Start portrait dashboard** for 600×800 portrait. Stop the
   running dashboard before changing orientation. From SSH, use
   `sh /mnt/us/extensions/MyDashboard/bin/start.sh portrait` for portrait;
   omitting `portrait` retains the default landscape behavior.
   The launcher keeps the current orientation if it already matches, otherwise
   it rotates only after stopping the Kindle UI, and restores rotation on exit.

## Stop and recover

While the dashboard owns the framebuffer, the Kindle UI is stopped, so its
KUAL stop entry is not reachable on-screen. Use either of these methods:

- Over an existing SSH connection, run
  `sh /mnt/us/extensions/MyDashboard/bin/stop.sh`. The KUAL stop entry calls
  this same script.
- Over USB, create an empty file named `STOP` (no extension) in
  `/mnt/us/extensions/MyDashboard/`. Eject the drive so the Kindle can read the
  file. The dashboard consumes it on exit.

The worker exits at its next stop check, normally within five seconds when
idle, or after any current weather request or drawing finishes. The launcher
restores rotation, restarts the UI job it stopped, and re-enables the
screensaver. Keep the Kindle powered for extended use.

Startup and runtime errors are appended to `/mnt/us/mydashboard.log`, with the
last completed run's exit status in `/mnt/us/mydashboard.log.status`. These files
survive a reboot. Over USB on a Mac with the Kindle mounted as `Kindle`, read
`/Volumes/Kindle/mydashboard.log`; the Kindle's internal `/tmp` is not exposed
over USB. A forced reboot may leave no current exit status.

If the worker was
forcibly killed, the stop request times out, or the UI does not come back,
restart the Kindle with the power button. A reboot clears the transient lock
and does not auto-start the dashboard.
