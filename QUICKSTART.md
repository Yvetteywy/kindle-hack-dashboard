# Kindle dashboard quick start

This guide targets the **basic Kindle, 8th generation (KT3)**. Other models and
firmware may need different jailbreaks, Python installers, and FBInk binaries.
Do not assume these package choices work on every Kindle.

You need a computer, USB cable, Wi-Fi, and a **jailbroken Kindle with working
KUAL**. No always-on computer, weather server, or API key is needed.
These instructions install software **on the Kindle**, not in Codespaces or
your computer's Python environment.

## 1. Download checklist

Download and extract archives on your computer. The versions below are the
ones documented by this project, not a promise that they are the latest.

| Download / reference | What it is for |
| --- | --- |
| [Jailbreak wizard](https://kindlemodding.org/jailbreak-wizard.html) | Choose a jailbreak for your exact model and firmware; complete its post-jailbreak instructions first. Do not update firmware just for this dashboard. |
| [KUAL archive][kual] | Kindle application launcher. Install using your jailbreak's instructions; keep an existing working installation. |
| [MR Package Installer (MRPI) archive][mrpi] | Installs the Kindle Python update package. Not needed if you skip Python. |
| [MyDashboard repository](https://github.com/yvetteyu12345/kindle-hack-dashboard) | Use **Code → Download ZIP**, extract, and locate the `MyDashboard` folder. |
| [FBInk v1.25.0 Kindle binaries][fbink] | Supplies both `fbink` and `fbdepth`. Download the binaries archive, not source code. |
| [Kindle Python 2.7 & 3.9 archive][python] | About 105 MiB; use only the Python 3 installer specified below. Needed for city/font configuration and starting with saved settings. |
| [tzdata wheel files](https://pypi.org/project/tzdata/#files) | Only needed if the Kindle Python runtime lacks IANA timezone data; see step 4. |

The KUAL, MRPI, and Python links point to NiLuJe's public storage and do not
require a MobileRead login. The [public package index][index] is an alternative
reference, but its listing may lag behind individual packages.

## 2. Copy the dashboard and display tools

Connect the Kindle by USB. In this guide, **USB root** means the drive you see
on your computer; internally, the Kindle calls it `/mnt/us/`.

1. Copy the complete `MyDashboard` folder into `extensions` at the USB root.
   The result must be `extensions/MyDashboard/menu.json`, not an extra nested
   `MyDashboard/MyDashboard` folder. Include `fonts` and its license.
2. Extract `FBInk-v1.25.0-kindle.tar.gz`. For the **KT3**, copy both
   `PW2/bin/fbink` and `PW2/bin/fbdepth` into `extensions/MyDashboard/bin/`.
   Despite its name, `PW2` is the correct binary family for this device.
   These files are copied directly, **not installed through MRPI**.
3. Keep shell scripts and the two binaries executable, and preserve LF line
   endings. The default Sans-serif font needs an **OpenType-enabled FBInk
   build**; startup logs an error if font loading is unsupported.

The Kindle also needs `curl` with working HTTPS certificate validation and the
usual BusyBox tools. These are not supplied by the Python installer. If startup
reports a missing tool, resolve that dependency before continuing; do not
disable certificate checks. A separate `cal` installation is not required.

**Fastest first run:** without Python or saved settings, safely eject, connect
to Wi-Fi, and choose **KUAL → MyDashboard → Start dashboard**. This uses
Washington, DC, Eastern time, and Sans-serif. Skip to step 5 for stop/recovery
instructions, or continue below to configure your city and font.

## 3. Install Python 3 on the Kindle

Skip this step if you only want the default-city dashboard.

1. If MRPI is not already installed, extract its archive and merge its
   `extensions` and `mrpackages` folders into the USB root. Preserve existing
   extensions and follow any additional setup required by your jailbreak.
2. Extract the Kindle Python archive. For the **KT3**, copy **only**
   `Python/Update_python3_0.15.N_install_pw2_and_up.bin` into `mrpackages` at
   the USB root. Do not use the Python 2 installer, `touch_pw` variant, or
   uninstaller. Back up an existing `python3` folder first: installation
   replaces it.
3. Safely eject. Open **KUAL → Helper → Install MR Packages** and leave the
   Kindle alone until installation finishes and the UI returns.
   **Do not use Settings → Update Your Kindle.** SSH is not required.

MyDashboard requires Python **3.9+** for saved settings. It looks for `python3`
on `PATH`, then at `/mnt/us/python3/bin/python3`. The linked Python 3.9 package
is a legacy Kindle runtime, not the latest upstream Python.

## 4. Detect your city without the browser

1. Connect the Kindle to Wi-Fi.
2. Choose **KUAL → MyDashboard → Detect city from Wi-Fi**.
3. Allow the lookup to finish. On success, the dashboard opens automatically
   in its last-used orientation (portrait if none has been recorded).
   It does not open a configuration page. Look for
   `saved IP-detected city` in `extensions/MyDashboard/mydashboard-setup.log` to confirm
   the detected city and timezone.

This opt-in action sends a request to [ipwho.is](https://ipwhois.io/documentation),
which sees your public IP and returns an approximate city and timezone. VPNs,
hotspots, and ISP routing can make the result inaccurate. Detection happens
only when selected, not at every startup, and saves the result for later use.
It preserves your existing font and leaves saved settings unchanged if the
lookup or validation fails. A running dashboard is stopped before detection.
Failed settings actions do not launch the dashboard.

Detection uses the Kindle's `curl` HTTPS client, not Python's certificate
store. If an older version logs Python `CERTIFICATE_VERIFY_FAILED` during
detection, update the dashboard scripts and retry. Certificate validation is
not disabled; `curl` must still have working CA certificates.

Python and timezone data are still required; see troubleshooting below for
missing timezone data. No extra download or API key is needed. If this menu
item is missing, copy the updated complete
`MyDashboard` folder, including `menu.json` and the scripts.

### Manually override the city using USB

Instead of detecting a city, create or edit
`extensions/MyDashboard/location.json` on the Kindle drive. It is not included
in the ZIP; successful KUAL settings actions create it. See the
[JSON example and overwrite rules](./README.md#manually-set-or-override-your-city-over-usb).
Stop before editing, preserve a backup, safely eject, and start again.
Manual settings still require Python and timezone data. Detection does not
run at startup; only choosing **Detect city from Wi-Fi** replaces the city.

### Choose a font in KUAL

Under **KUAL → MyDashboard**, choose **Font: Sans-serif**, **Font: Serif**, or
**Font: Classic bitmap**. The dashboard reopens automatically in its last-used
orientation, defaulting to portrait. Your saved city is
preserved. Choosing a font needs Python and timezone data but no internet or
browser; it uses Washington, DC if no city has been saved yet.

If the dashboard is running, use the USB `STOP` file or SSH to regain access
to KUAL first (see step 5). Font actions stop any running dashboard before
saving, then reopen it only after a successful update. The remembered orientation
is stored in `extensions/MyDashboard/last-orientation`; preserve it when updating.
The explicit **Start dashboard** entry still selects landscape.

### Missing timezone data

**Do not remove `tzdata` just because detection now uses `curl`.** HTTPS
certificates and timezone rules are different dependencies. Saved settings,
including USB-created JSON, need IANA timezone data. The Python `tzdata`
package is optional only when the runtime already has the required system
zoneinfo files. The no-settings Washington, DC dashboard is the exception:
it uses built-in Eastern-time rules and does not need Python.

If a settings action fails, reconnect by USB and read
`extensions/MyDashboard/mydashboard-setup.log`. If it reports missing timezone data:

- With a terminal **on the Kindle**, run `python3 -m pip install tzdata` if
  that runtime supports pip.
- Without a Kindle terminal, download the pure-Python `.whl` from the
  [tzdata files page](https://pypi.org/project/tzdata/#files), extract it as a
  ZIP on your computer, and copy its complete `tzdata` directory into
  `python3/lib/python3.9/site-packages/` on the USB drive. Preserve all nested
  `zoneinfo` files. This destination is for the linked Python 3.9 runtime.

Safely eject and retry the KUAL action. Installing timezone data only on your
computer does not fix the Kindle runtime.

### Clock shows UTC or the wrong date

The clock is 24-hour: `03:10` means 3:10 AM. At `03:10 UTC` on November 24,
2026, Seattle should show `19:10` on November 23, with timezone
`America/Los_Angeles`.

Older dashboard versions pass a binary timezone-file path to the Kindle's
`date` command, which some runtimes ignore. Update the complete dashboard,
including both `bin/setup_server.py` and `bin/dashboard.sh`, then stop and
restart it. The updated helper extracts a portable POSIX timezone rule with
DST transitions from the same IANA data. Keep your saved city and `tzdata`.
If the date/time still disagrees, compare the saved timezone and the Kindle's
system clock; timezone conversion cannot correct an incorrectly set clock.

### Updating an older installation

The browser-based Configure menu, page, and HTTP service have been removed.
Merge the updated full `MyDashboard` folder, preserving `location.json`,
FBInk binaries, and fonts. Delete the obsolete
`extensions/MyDashboard/setup.html` on the Kindle if present, then safely eject
and restart once to stop any older setup service.

## 5. Start, stop, and recover

- **Landscape:** KUAL → MyDashboard → **Start dashboard**.
- **Portrait (600×800):** KUAL → MyDashboard → **Start portrait dashboard**.
  Stop the dashboard before switching orientation.
- **Stop without SSH:** connect by USB, create an empty file named `STOP`
  (no `.txt` extension) inside `extensions/MyDashboard/`, then safely eject.
  The dashboard consumes the file and restores the Kindle UI.
- **Stop over existing Kindle SSH:** run
  `sh /mnt/us/extensions/MyDashboard/bin/stop.sh`.

KUAL is not reachable on-screen while the dashboard owns the display. A stop
normally takes a few seconds when idle, but waits for current weather requests
or drawing to finish. There is no on-screen exit control, but **the USB `STOP`
method does not require a reboot**. If the UI does not return, restart the Kindle using its
power button. Rebooting clears the transient lock and does not auto-start the
dashboard. Hardware rotation and UI recovery still need device verification.

Read `extensions/MyDashboard/mydashboard.log` for startup/runtime errors, or
`extensions/MyDashboard/mydashboard-setup.log` for configuration errors. Preserve
`extensions/MyDashboard/location.json` when updating: it stores your settings.
Keep the Kindle powered for extended use.

## More detail and references

- [Full installation and compatibility notes](./README.md#install-and-use)
- [Python installation and checks](./README.md#install-python-on-the-basic-kindle-8th-generation)
- [Timezone data](./README.md#timezone-data)
- [Code structure and customization](./README.md#how-the-code-works)
- [Stop and recovery details](./README.md#stop-and-recover)
- [FBInk upstream project](https://github.com/NiLuJe/FBInk)
- [Kindle Modding guides](https://kindlemodding.org/)
- [DejaVu fonts](https://dejavu-fonts.github.io/) and [bundled license](./MyDashboard/fonts/LICENSE.txt)

[kual]: https://storage.gra.cloud.ovh.net/v1/AUTH_2ac4bfee353948ec8ea7fd1710574097/mr-public/KUAL/KUAL-c6ac782-20250419.tar.xz
[mrpi]: https://storage.gra.cloud.ovh.net/v1/AUTH_2ac4bfee353948ec8ea7fd1710574097/mr-public/KUAL/kual-mrinstaller-1.7.N-r19303.tar.xz
[python]: https://storage.gra.cloud.ovh.net/v1/AUTH_2ac4bfee353948ec8ea7fd1710574097/mr-public/Touch/kindle-python-0.15.N-r18981.tar.xz
[fbink]: https://www.mobileread.com/forums/attachment.php?attachmentid=198200
[index]: https://storage.gra.cloud.ovh.net/v1/AUTH_2ac4bfee353948ec8ea7fd1710574097/mr-public/index.html
