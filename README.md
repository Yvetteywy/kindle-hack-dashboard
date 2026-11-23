
# MyDashboard for Kindle

MyDashboard replaces the stock UI with a borderless 1448×1072 FBInk dashboard
on a jailbroken Kindle Paperwhite 4 (armv7l, firmware 5.16.2.1.1). It shows
Issaquah weather from [Open-Meteo](https://open-meteo.com/), a Pacific-time
clock and calendar, and a rotating daily quote. The screen updates once per
minute, with a flashing full-screen refresh and weather fetch at startup and
every hour. If a request fails, the dashboard labels the last successful
forecast from that session as stale.

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
3. Connect to Wi-Fi and choose **MyDashboard → Start dashboard** in KUAL.

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

Startup and runtime errors go to `/tmp/mydashboard.log`. If the worker was
forcibly killed, the stop request times out, or the UI does not come back,
restart the Kindle with the power button. A reboot clears the transient lock
and does not auto-start the dashboard.
