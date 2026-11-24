
# MyDashboard for Kindle

**A jailbroken Kindle with KUAL installed is required. This is not an app for
stock, unmodified Kindle firmware.**

**Start here: [Quick-start guide](./QUICKSTART.md)** — download links,
installation order, Python setup, and stop/recovery instructions for the basic
Kindle (8th generation, KT3).

Also see [USB city overrides](#manually-set-or-override-your-city-over-usb) and
[how the code works](#how-the-code-works).

MyDashboard replaces the stock UI with a borderless FBInk dashboard
on a jailbroken Kindle. It shows
weather from [Open-Meteo](https://open-meteo.com/), a city-local
clock and calendar, and a rotating daily quote. Washington, DC and Eastern time
are the default until you save a different city. The screen updates once per
minute, with a flashing full-screen refresh and weather fetch at startup and
every hour. If a request fails, the dashboard labels the last successful
forecast from that session as stale.
The clock uses 24-hour time: `03:10` is 3:10 AM and `19:10` is 7:10 PM.

The default layout selects 800×600 landscape for the basic Kindle
(8th generation), or the original 1448×1072 landscape layout for higher-resolution
devices such as the Paperwhite 4. A 600×800 portrait layout is also available
for the basic Kindle. The compact layouts are inspired by
[KindleReborn](https://github.com/Yvetteywy/KindleReborn): divided clock/calendar
and weather panels, today's calendar date highlighted, a large temperature,
pixel-art weather icon, and four forecast samples at offsets 0, 3, 6, and 9 hours
from the fetched forecast's first entry. The larger layout retains all 12 hourly
rows. Both run locally with FBInk, without a browser, address bar, or rendering
server. Bundled DejaVu Sans is the default font; DejaVu Serif and the original
IBM bitmap style are selectable. The dashboard itself is display-only.
KUAL provides direct font choices and an action to detect and save an
approximate city from the Kindle's public IP address. No browser is required.

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

## Visual previews

These are software-rendered previews of the dashboard's drawing commands with
sample data, not screenshots captured from a Kindle. Actual device rendering
of the new smooth font styles still needs verification. These previews use
Sans-serif; Serif alternatives are linked below.

### Portrait (600×800)

![Portrait dashboard preview](./Asset/mydashboard-portrait-preview.png)

### Landscape (800×600)

![Landscape dashboard preview](./Asset/mydashboard-landscape-preview.png)

Serif previews: [Portrait](./Asset/mydashboard-portrait-serif-preview.png) ·
[Landscape](./Asset/mydashboard-landscape-serif-preview.png).

## Prerequisites

- **Jailbreak your Kindle first**, using a method compatible with its exact
  model and firmware. Start with the
  [Kindle Modding jailbreak wizard](https://kindlemodding.org/jailbreak-wizard.html)
  and complete the guide's post-jailbreak steps.
  [WinterBreak](https://kindlemodding.org/jailbreaking/WinterBreak/) is one
  reference, not a universal method: its guide explicitly excludes firmware
  5.18.1 and later. Do not update firmware just to install this dashboard.
- **Install [KUAL][kual-download]**
  (Kindle Unified Application Launcher), following the instructions appropriate
  to your jailbreak. MyDashboard appears as a KUAL extension. Keep an existing
  working KUAL installation; Python does not require reinstalling it.
- **Install [MRPI][mrpi-download]**
  (MobileRead Package Installer) if you need to install the Python update
  package described below. MRPI is separate from KUAL and the jailbreak.
- **Python 3.9+ and timezone data are required for city/font configuration and
  starting with saved settings**, but not for the default-city dashboard.
  FBInk, FBDepth and the remaining native dependencies are described below.

[kual-download]: https://storage.gra.cloud.ovh.net/v1/AUTH_2ac4bfee353948ec8ea7fd1710574097/mr-public/KUAL/KUAL-c6ac782-20250419.tar.xz
[mrpi-download]: https://storage.gra.cloud.ovh.net/v1/AUTH_2ac4bfee353948ec8ea7fd1710574097/mr-public/KUAL/kual-mrinstaller-1.7.N-r19303.tar.xz
[python-download]: https://storage.gra.cloud.ovh.net/v1/AUTH_2ac4bfee353948ec8ea7fd1710574097/mr-public/Touch/kindle-python-0.15.N-r18981.tar.xz
[snapshot-index]: https://storage.gra.cloud.ovh.net/v1/AUTH_2ac4bfee353948ec8ea7fd1710574097/mr-public/index.html
[fbink-download]: https://www.mobileread.com/forums/attachment.php?attachmentid=198200

## Install and use

1. With the jailbreak and KUAL already installed, copy [MyDashboard](./MyDashboard/) to
   `/mnt/us/extensions/MyDashboard/`. Keep the scripts executable and use LF
   line endings. Include the bundled `fonts` folder and its license.
2. Download **[FBInk v1.25.0 Kindle binaries][fbink-download]** (about 2.5 MB).
   This is a direct archive download, not the source repository or a forum
   thread; anonymous access was verified without a MobileRead login.
   Extract `FBInk-v1.25.0-kindle.tar.gz` on your computer. For the basic Kindle
   (8th generation), copy **both** `PW2/bin/fbink` and `PW2/bin/fbdepth` into
   `/mnt/us/extensions/MyDashboard/bin/` and make both executable.
   The `PW2` directory denotes the compatible binary family; it is also correct
   for this basic Kindle. For other models, select a compatible build rather
   than assuming the same directory applies. These executables are copied
   directly, not installed through MRPI. The
   [FBInk source project](https://github.com/NiLuJe/FBInk) is available separately.
   Sans-serif and Serif require an **OpenType-enabled FBInk build**. Startup
   checks font loading without drawing before stopping the Kindle UI, and
   reports incompatible builds or missing fonts in `/mnt/us/extensions/MyDashboard/mydashboard.log`.
   Classic bitmap does not need OpenType support or the bundled font files.
   The Kindle also needs `curl` with working HTTPS certificate validation and the usual
   BusyBox tools. The dashboard uses `cal` if installed and draws an equivalent
   calendar itself otherwise. No separate weather server or API key is needed.
3. Connect to Wi-Fi and choose **MyDashboard → Start dashboard** in KUAL for
   landscape, or **Start portrait dashboard** for 600×800 portrait. Stop the
   running dashboard before changing orientation. From SSH, use
   `sh /mnt/us/extensions/MyDashboard/bin/start.sh portrait` for portrait;
   omitting `portrait` retains the default landscape behavior.
   The launcher keeps the current orientation if it already matches, otherwise
   it rotates only after stopping the Kindle UI, and restores rotation on exit.

## Configure the city and font on the Kindle

The default-city dashboard still works without Python. To enable
city detection, font selection and saved settings, install a compatible
**Python 3.9+ Kindle runtime**. Its `python3` must be on `PATH` or at
`/mnt/us/python3/bin/python3`. These are Kindle prerequisites, not packages
installed on your Mac or in a cloud workspace.

### Install Python on the basic Kindle (8th generation)

For this device, use NiLuJe's Kindle runtime rather than a Python installer for
macOS, Windows, or desktop Linux:

These direct downloads use **NiLuJe's public storage**, not forum attachments;
no MobileRead login is required. A [public file index][snapshot-index] is also
available, but its listing can lag behind individual packages. Use the direct
links below for the verified versions.

1. Download **[Python 2.7 & Python 3.9][python-download]** (about 105 MiB).
   This is the Touch/PW2-and-up package, not the legacy Kindle 2/3/4 package.
   The verified archive is
   `kindle-python-0.15.N-r18981.tar.xz`; it contains separate Python 2 and
   Python 3 installers.
2. If MRPI is not already installed, download
   **[MR Package Installer 1.7.N-r19303][mrpi-download]**.
   Extract it on your computer and merge its
   `extensions` and `mrpackages` folders into the Kindle's USB-visible root.
   Preserve existing extensions. Follow your jailbreak's instructions for any
   additional setup.
3. Extract the Python archive on your computer. For the basic Kindle
   (8th generation, KT3), copy **only**
   `Python/Update_python3_0.15.N_install_pw2_and_up.bin` into the Kindle's
   `mrpackages` folder. If mounted as `Kindle` on a Mac, that destination is
   `/Volumes/Kindle/mrpackages/`; on the Kindle it is `/mnt/us/mrpackages/`.
   Do not select the Python 2 installer, `touch_pw` variant, or uninstaller.
4. Safely eject the Kindle, open **KUAL → Helper → Install MR Packages**,
   and leave the device alone until installation finishes and the UI returns.
   Use MRPI, **not Settings → Update Your Kindle**. Installing this package
   does not require SSH.
5. Choose **MyDashboard → Detect city from Wi-Fi**. If prerequisites are
   missing, inspect `/mnt/us/extensions/MyDashboard/mydashboard-setup.log` over USB as
   `/Volumes/Kindle/extensions/MyDashboard/mydashboard-setup.log`.

Back up an existing `python3` folder before reinstalling: the runtime installer
replaces that folder. Other Kindle models or newer firmware may need different
packages; check the maintainer's compatibility instructions instead of assuming
this installer is universal. The listed Python 3.9 build is a legacy runtime,
not the latest upstream Python release.

If you have a terminal or SSH session **running on the Kindle**, you can verify
the installation and MyDashboard's timezone prerequisites with:

```sh
python3 --version
sh /mnt/us/extensions/MyDashboard/bin/python.sh \
  /mnt/us/extensions/MyDashboard/bin/setup_server.py --check
```

The version must be 3.9 or newer. Do not run these commands in a local Mac or
Codespaces shell and expect them to check the Kindle.

### Timezone data

**Keep the timezone data you installed.** Switching IP detection to `curl`
fixed HTTPS certificate verification; it did not remove the need for timezone
data. CA certificates establish trust in an HTTPS server. Timezone data
defines local clock offsets and daylight-saving transitions; they are separate
dependencies.

| How you use the dashboard | Python 3.9+ | IANA timezone data |
| --- | --- | --- |
| Default Washington, DC dashboard, without `location.json` | Not needed | Not needed; the shell has built-in Eastern-time rules |
| Detect city from Wi-Fi or choose a font in KUAL | Required | Required |
| Start with saved settings, including a USB-created `location.json` | Required | Required for the saved timezone |

The Python **`tzdata` package itself is optional only if the runtime already
has the required IANA files in its system zoneinfo paths**. The settings helper
checks those paths first, then tries `tzdata`. A timezone name such as
`America/Los_Angeles` in JSON does not contain the underlying timezone rules.
The helper requires modern TZif data with a POSIX timezone-rule footer, as
provided by current `tzdata` packages.

If system timezone files are missing and the runtime supports pip, install it
with `python3 -m pip install tzdata` **on the Kindle**, then repeat the check above.
Do not install it only on your computer.

If the runtime has no pip, a USB-only alternative for the Python 3.9 runtime
above is to download the pure-Python wheel (`.whl`) from
[tzdata's PyPI files](https://pypi.org/project/tzdata/#files), extract it as a ZIP
on your computer, and copy its complete `tzdata` directory into
`python3/lib/python3.9/site-packages/` on the Kindle's USB drive. Keep the nested
`zoneinfo` directory and its files intact. Retry the KUAL settings action afterward.

Missing dependencies are reported in `/mnt/us/extensions/MyDashboard/mydashboard-setup.log`; they are not installed
automatically. Python is also used to validate saved settings and prepare the
timezone when starting a configured dashboard.

### Save your city and font

#### Detect your city

1. Copy the updated `MyDashboard` folder to the Kindle, including `menu.json`,
   `bin/setup.sh`, and `bin/setup_server.py`. Python 3.9+, `curl` HTTPS support, and
   timezone data are still required.
2. Connect to Wi-Fi and choose **MyDashboard → Detect city from Wi-Fi** in KUAL.
   This explicitly contacts [ipwho.is](https://ipwhois.io/documentation) over
   HTTPS; the provider sees the Kindle connection's public IP. No browser,
   API key, or separate computer service is needed.
   The lookup uses the Kindle's `curl`, like weather fetching, rather than
   Python's separate certificate store. HTTPS certificate verification stays
   enabled; `curl` must have a working CA certificate bundle.
3. Allow the lookup to finish. On success, the dashboard opens automatically
   in its last-used orientation, or portrait if none has been recorded.
   No settings page opens. To verify the result,
   read `/mnt/us/extensions/MyDashboard/mydashboard-setup.log` over USB: success logs
   `saved IP-detected city` followed by the city and timezone.

Detection runs only when you choose that action, not at every startup. It
preserves your saved font, or uses Sans-serif if there are no saved settings.
Network, service, invalid-response, or missing-timezone-data errors are logged
without overwriting previous settings. Malformed existing settings must be
corrected or backed up and renamed before detection. A running dashboard is
stopped safely before detection. A failed lookup does not launch a dashboard.

IP location is approximate and can identify your ISP's city rather than your
own, especially with a VPN or mobile hotspot. Run detection again after moving
if desired. This is not GPS.

#### Choose a font directly in KUAL

1. Select one of these entries under **MyDashboard**:
   - **Font: Sans-serif** — bundled DejaVu Sans, the default, with a slightly larger pixel size for readability.
   - **Font: Serif** — bundled DejaVu Serif.
   - **Font: Classic bitmap** — FBInk's original IBM style.
2. The action saves the choice without changing your city, coordinates, or
   timezone. It needs Python and timezone data, but no browser or network.
   Without a saved city, it keeps Washington, DC and Eastern time.
3. The dashboard automatically reopens to apply the choice, using its last-used
   orientation or portrait if none has been recorded.

Font actions stop a running dashboard safely before saving. To regain access
to KUAL while the dashboard owns the screen, first use the USB `STOP` file or
SSH as described below. Success is logged as `saved font` in
`/mnt/us/extensions/MyDashboard/mydashboard-setup.log`; validation/save failures leave existing settings
unchanged.

Automatic reopening applies to successful KUAL font/detection actions only.
The explicit **Start dashboard** entry still selects landscape, and **Start
portrait dashboard** selects portrait. Once display, font, and rotation checks
pass, the launcher records its orientation in
`extensions/MyDashboard/last-orientation` for the next settings action. This
file is separate from the city JSON and excluded from Git.
If startup fails after settings were saved, those settings remain saved; see
`mydashboard.log` for the startup error. The device does not auto-start on reboot.

There is **no GPS or automatic startup location lookup**. KUAL actions save
settings in
`/mnt/us/extensions/MyDashboard/location.json`. That file survives reboot and is
excluded from Git; preserve it when updating the extension. City labels are
transliterated to ASCII consistently across font styles, and long labels wrap or shorten to
fit the screen.

The two smooth styles include regular and bold
[DejaVu fonts](https://dejavu-fonts.github.io/) under their
[redistribution license](./MyDashboard/fonts/LICENSE.txt). Rendering still runs
entirely on the Kindle through FBInk; no web font download or rendering server is
needed. Older saved city-only settings automatically use Sans-serif until you
choose another style. The bitmap option retains the original rendering.

### Manually set or override your city over USB

You can bypass IP detection by editing the same settings file it writes.
Python and timezone data are still needed when starting with this file.

1. Stop the dashboard, then connect the Kindle by USB.
2. Open `extensions/MyDashboard/location.json` on the Kindle drive. If absent,
   create it there as plain text; it is not included in the repository or ZIP.
   Back up an existing file before editing it. Do not edit a copy only on your
   computer and expect the Kindle to see it.
3. Use this example, replacing the city, coordinates, and timezone as needed:

   ```json
   {
     "name": "Seattle",
     "latitude": 47.6062,
     "longitude": -122.3321,
     "timezone": "America/Los_Angeles",
     "font": "sans"
   }
   ```

4. Save as exactly `location.json`, not `location.json.txt`. Safely eject and
   start either dashboard orientation again. Settings are loaded at startup,
   not watched for changes while running.

| Field | What it controls |
| --- | --- |
| `name` | Display label, not a city search. Changing it alone does not move the weather location. |
| `latitude`, `longitude` | Weather coordinates; JSON numbers in ranges -90 to 90 and -180 to 180, respectively. |
| `timezone` | IANA identifier for the clock, calendar, and forecast times; must have corresponding timezone data installed. |
| `font` | `sans`, `serif`, or `bitmap`. Optional; omitted values use `sans`. |

Use valid JSON: no comments or trailing commas. Invalid settings or missing
timezone data stop startup and are reported in `/mnt/us/extensions/MyDashboard/mydashboard.log`.

**Overwrite rules:** there is one settings file, not separate manual and
automatic layers. Your USB edits remain until you change them:

- Starting the dashboard reads settings; it does not detect or overwrite a city.
- **Detect city from Wi-Fi** replaces city name, coordinates, and timezone
  after a successful lookup and validation, while preserving the font.
- A **Font:** action changes only the font and preserves the city fields.
- Failed lookup, validation, or save operations leave the existing file
  unchanged. Successful updates write a temporary file and atomically replace
  `location.json`.
- Backing up and renaming the active file restores the built-in defaults.

The browser setup page, city-search UI, and local HTTP service have been
removed. No server or always-on computer is required. Weather continues to be
fetched directly from Open-Meteo with `curl`.

#### Upgrading from browser-based configuration

Merge the full updated `MyDashboard` folder onto the Kindle, preserving
`location.json`, your FBInk binaries, and the bundled fonts. Over USB, delete
the obsolete `extensions/MyDashboard/setup.html` file if present; merging a ZIP
does not remove old files. Replace `menu.json` and all updated scripts together.
Restart the Kindle once to stop any old setup service still in memory.

Invalid saved settings or missing timezone data stop startup before the Kindle
UI is stopped; see `/mnt/us/extensions/MyDashboard/mydashboard.log` for details. Install missing
timezone data as described above. To reset malformed settings over USB, back
up and rename `location.json`, then detect the city again. Removing the active
settings file restores the Washington, DC and Sans-serif defaults.

## How the code works

### Structure

| File | Responsibility |
| --- | --- |
| [menu.json](./MyDashboard/menu.json) | KUAL entries and the shell arguments each entry runs. |
| [bin/setup.sh](./MyDashboard/bin/setup.sh) | Validates settings-action arguments, checks prerequisites, stops a running dashboard safely, runs detection or font selection, and requests a restart in the remembered orientation. Logs to `/mnt/us/extensions/MyDashboard/mydashboard-setup.log`. |
| [bin/python.sh](./MyDashboard/bin/python.sh) | Finds `python3` on `PATH`, or uses `/mnt/us/python3/bin/python3`. |
| [bin/setup_server.py](./MyDashboard/bin/setup_server.py) | Command-line settings helper: validates/saves JSON, detects a city via `curl`, changes fonts, and prepares timezone/forecast settings. Despite the historical name, it no longer runs a server. |
| [bin/start.sh](./MyDashboard/bin/start.sh) | Background launcher: prepares saved settings, checks display/font support, manages rotation and Kindle UI ownership, launches the drawing worker, and restores the UI on exit. |
| [bin/dashboard.sh](./MyDashboard/bin/dashboard.sh) | Shell drawing worker: fetches weather with `curl`, parses it, computes calendar/quotes, and draws through FBInk. |
| [bin/font.sh](./MyDashboard/bin/font.sh) | Shared font loading and FBInk text options for Sans-serif, Serif, and bitmap styles. |
| [bin/stop.sh](./MyDashboard/bin/stop.sh) | Requests a cooperative stop and checks the recorded exit status; it does not forcibly kill the Kindle UI. |
| [fonts/](./MyDashboard/fonts/) | Bundled DejaVu font files and their redistribution license. |
| [tests/](./tests/) | Mocked launcher/renderer checks and settings/detection/font tests; no Kindle is required to run them. |

### Startup and data flow

```text
KUAL detection/font entry
  -> setup.sh -> python.sh -> setup_server.py
  -> validate and save location.json
  -> start.sh in last-used orientation (portrait if none recorded)

KUAL Start dashboard / Start portrait dashboard
  -> start.sh
  -> if location.json exists: Python --prepare writes temporary runtime files
  -> check display and font -> stop Kindle UI -> select rotation
  -> dashboard.sh -> curl weather -> FBInk drawing
  -> on stop: start.sh restores rotation, UI, and screensaver
```

`location.json` and `last-orientation` are persistent and excluded from Git.
The former stores city/font settings; the latter records portrait or landscape.
In contrast,
`/tmp/mydashboard.run/` is temporary: it is both the running-state lock and the
directory for prepared city/forecast URL, POSIX timezone rule, selected font, weather
cache, and stop requests. Do not put your permanent configuration there.

With saved settings, `checked_timezone()` validates the IANA timezone data and
extracts its POSIX rule (for example, `PST8PDT,M3.2.0,M11.1.0` for Seattle).
`prepare_location()` writes that rule as text into the runtime directory.
The shell reads the rule into `TZ`, rather than passing a binary timezone-file
path that some Kindle date implementations ignore. This supplies local time,
date, timezone abbreviation, and DST without changing the Kindle's system
timezone. Data without a usable footer is rejected instead of silently using
UTC. Without saved settings, the worker uses its built-in Washington, DC
coordinates and Eastern-time rules. Python does not stay running to draw
the screen.

### Where to change behavior

| You want to change... | Start here |
| --- | --- |
| Your city or font only | Edit `location.json` over USB or use KUAL; no source changes needed. Follow the overwrite rules above. |
| KUAL labels or commands | [menu.json](./MyDashboard/menu.json); keep arguments consistent with [setup.sh](./MyDashboard/bin/setup.sh) and the Python CLI. |
| Which settings get overwritten | `detect_location()` and the `--font` branch of `main()` in [setup_server.py](./MyDashboard/bin/setup_server.py). Both use `save_location()` for validation and atomic replacement. |
| IP-geolocation provider | `detect_location()` in [setup_server.py](./MyDashboard/bin/setup_server.py): update both the HTTPS request and response-field mapping, plus its mocked tests. |
| Portrait or landscape layout, text, icons, quotes | `render_portrait()`, `render_compact()`, `panel_icon()`, and `daily_quote()` in [dashboard.sh](./MyDashboard/bin/dashboard.sh). Coordinates and text sizes depend on screen dimensions. |
| Font files or text sizing | [font.sh](./MyDashboard/bin/font.sh) and [fonts/](./MyDashboard/fonts/); new font choices also need CLI validation and KUAL entries. |
| Draw/weather/full-refresh intervals | The final loop in [dashboard.sh](./MyDashboard/bin/dashboard.sh): drawing is scheduled every 60 seconds; weather and flashing refresh every 3600 seconds. These also run at startup. |
| Temperature or wind units | Both the default URL in [dashboard.sh](./MyDashboard/bin/dashboard.sh) and `prepare_location()` in [setup_server.py](./MyDashboard/bin/setup_server.py), plus the renderer's `F`/`mph` labels. Changing only a URL would leave incorrect labels. |
| Built-in fallback city | `DEFAULT` in [setup_server.py](./MyDashboard/bin/setup_server.py) and the initial city, URL, and `TZ` in [dashboard.sh](./MyDashboard/bin/dashboard.sh); keep them consistent. |

For code changes, preserve the startup safety checks and cooperative UI
restoration. Run the tests below before copying changed scripts to the Kindle.

## Development checks

Run `python3 -B -m unittest discover -s tests -v` for the mocked native-renderer,
launcher, city detection, and font-setting tests. Check shell syntax with
`for script in MyDashboard/bin/*.sh; do sh -n "$script" || exit; done`.
Tests use temporary settings and mocked network responses;
they do not stop the workstation UI or write to a connected Kindle.

## Stop and recover

While the dashboard owns the framebuffer, the Kindle UI is stopped, so its
KUAL stop entry is not reachable on-screen. There is no on-screen tap-to-exit
control. **A normal exit does not require rebooting.** Use either method:

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

Startup and runtime errors are appended to `/mnt/us/extensions/MyDashboard/mydashboard.log`, with the
last completed run's exit status in `/mnt/us/extensions/MyDashboard/mydashboard.log.status`. These files
survive a reboot. Over USB on a Mac with the Kindle mounted as `Kindle`, read
`/Volumes/Kindle/extensions/MyDashboard/mydashboard.log`; the Kindle's internal `/tmp` is not exposed
over USB. A forced reboot may leave no current exit status. Older logs at the USB
root are no longer used and can be deleted.

If the worker was
forcibly killed, the stop request times out, or the UI does not come back,
restart the Kindle with the power button. A reboot clears the transient lock
and does not auto-start the dashboard.
