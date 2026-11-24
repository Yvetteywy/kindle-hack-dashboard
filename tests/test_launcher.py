import json
import os
from itertools import product
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from urllib.parse import parse_qs, urlsplit


ROOT = Path(__file__).resolve().parents[1]


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        shutil.copy(ROOT / "MyDashboard/bin/font.sh", self.bin)
        (self.root / "fonts").symlink_to(ROOT / "MyDashboard/fonts", target_is_directory=True)
        self.usb = self.root / "usb"
        self.usb.mkdir()
        self.state = self.root / "state"
        self.events = self.root / "events"
        self.log = self.root / "mydashboard.log"
        self.status = self.root / "mydashboard.log.status"
        self.setup_log = self.root / "mydashboard-setup.log"
        for name in ("start.sh", "stop.sh"):
            source = (ROOT / "MyDashboard/bin" / name).read_text()
            source = source.replace("/tmp/mydashboard.run", str(self.state))
            source = source.replace("/mnt/us/", str(self.usb) + "/")
            (self.bin / name).write_text(source)
        self.env = dict(os.environ, EVENTS=str(self.events))
        self.command("sleep", "exit 0")
        self.command("nohup", 'exec "$@"')
        self.command("setsid", 'exec "$@"')
        self.command("fbink", 'echo "screenWidth=1072;screenHeight=1448;"')
        self.command("fbdepth", 'echo "fbdepth $*" >> "$EVENTS"\necho 0')
        self.command(
            "initctl",
            'echo "initctl $*" >> "$EVENTS"\necho "$2 start/running"',
        )
        self.command("lipc-set-prop", 'echo "power $*" >> "$EVENTS"')
        self.command("curl", "exit 0")
        self.command("dashboard.sh", 'echo "worker $2" >> "$EVENTS"')

    def command(self, name, body):
        path = self.bin / name
        path.write_text("#!/bin/sh\n" + body + "\n")
        path.chmod(0o755)

    def launch(self, *args):
        subprocess.run(
            ["/bin/sh", str(self.bin / "start.sh"), *args],
            env=self.env, check=True, timeout=5,
        )
        deadline = time.monotonic() + 5
        while not self.status.exists() or self.state.exists():
            if time.monotonic() >= deadline:
                self.fail("launcher did not finish")
            time.sleep(0.01)
        return self.status.read_text().strip(), self.log.read_text()

    def test_unsupported_display_leaves_ui_power_and_rotation_untouched(self):
        self.command("fbink", 'echo "screenWidth=758;screenHeight=1024;"')
        self.log.write_text("previous run\n")
        (self.root / "last-orientation").write_text("portrait\n")
        status, log = self.launch()
        self.assertEqual(status, "1")
        self.assertTrue(log.startswith("previous run\n"))
        self.assertIn("unsupported framebuffer: 758x1024", log)
        self.assertFalse(self.events.exists())
        self.assertEqual((self.root / "last-orientation").read_text(), "portrait\n")

    def test_unreadable_display_leaves_device_untouched(self):
        self.command("fbink", "exit 1")
        status, log = self.launch()
        self.assertEqual(status, "1")
        self.assertIn("cannot read framebuffer dimensions", log)
        self.assertFalse(self.events.exists())

    def test_malformed_dimensions_leave_device_untouched(self):
        self.command("fbink", 'echo "unexpected output"')
        status, log = self.launch()
        self.assertEqual(status, "1")
        self.assertIn("cannot parse framebuffer dimensions", log)
        self.assertFalse(self.events.exists())

    def test_supported_display_runs_worker_and_restores_ui(self):
        self.command(
            "fbink",
            'if [ -f "$EVENTS" ]; then\n'
            '    echo "screenWidth=1448;screenHeight=1072;"\n'
            'else\n'
            '    echo "screenWidth=1072;screenHeight=1448;"\n'
            "fi",
        )
        self.command(
            "initctl",
            'echo "initctl $*" >> "$EVENTS"\n'
            'if [ "$1" = status ]; then\n'
            '    if [ -f "$EVENTS.stopped" ]; then\n'
            '        echo "$2 stop/waiting"\n'
            '    else\n'
            '        echo "$2 start/running"\n'
            '    fi\n'
            'elif [ "$1" = stop ]; then\n'
            '    touch "$EVENTS.stopped"\n'
            "fi",
        )
        status, _ = self.launch()
        self.assertEqual(status, "0")
        events = self.events.read_text()
        self.assertIn("initctl stop lab126_gui", events)
        self.assertIn("worker", events)
        self.assertIn("fbdepth -q -r 0", events)
        self.assertIn("initctl start lab126_gui", events)
        self.assertIn("power -i com.lab126.powerd preventScreenSaver 0", events)
        self.assertEqual((self.root / "last-orientation").read_text(), "landscape\n")
        self.assertEqual(list(self.usb.iterdir()), [])

    def test_stop_reads_usb_visible_status(self):
        self.state.mkdir()
        self.command(
            "sleep",
            f'rm -f "{self.state}/stop"\n'
            f'rmdir "{self.state}"\n'
            f'echo 0 > "{self.status}"',
        )
        env = dict(self.env, PATH=str(self.bin) + ":" + os.environ["PATH"])
        subprocess.run(
            ["/bin/sh", str(self.bin / "stop.sh")],
            env=env, check=True, timeout=5,
        )

    def test_supported_display_already_in_landscape_runs_worker(self):
        self.command("fbink", 'echo "screenWidth=1448;screenHeight=1072;"')
        status, _ = self.launch()
        self.assertEqual(status, "0")
        self.assertIn("worker", self.events.read_text())

    def test_compact_display_selects_matching_worker_layout(self):
        for width, height in ((600, 800), (800, 600)):
            with self.subTest(width=width, height=height):
                self.status.unlink(missing_ok=True)
                self.events.unlink(missing_ok=True)
                self.command(
                    "fbink",
                    'if [ -f "$EVENTS" ]; then\n'
                    '    echo "screenWidth=800;screenHeight=600;"\n'
                    "else\n"
                    f'    echo "screenWidth={width};screenHeight={height};"\n'
                    "fi",
                )
                status, _ = self.launch()
                self.assertEqual(status, "0")
                self.assertIn("worker 800x600", self.events.read_text())

    def test_compact_rotation_failure_restores_without_running_worker(self):
        self.command("fbink", 'echo "screenWidth=600;screenHeight=800;"')
        status, log = self.launch()
        self.assertEqual(status, "1")
        self.assertIn("did not report a 800x600 framebuffer", log)
        events = self.events.read_text()
        self.assertNotIn("worker", events)
        self.assertIn("fbdepth -q -r CW", events)
        self.assertIn("fbdepth -q -r CCW", events)
        self.assertIn("fbdepth -q -r 0", events)
        self.assertIn("power -i com.lab126.powerd preventScreenSaver 0", events)

    def test_portrait_keeps_matching_orientation_and_passes_layout_to_worker(self):
        self.command("fbink", 'echo "screenWidth=600;screenHeight=800;"')
        status, _ = self.launch("portrait")
        self.assertEqual(status, "0")
        events = self.events.read_text()
        self.assertIn("worker 600x800", events)
        self.assertNotIn("fbdepth -q -r UR", events)
        self.assertNotIn("fbdepth -q -r CW", events)
        self.assertIn("fbdepth -q -r 0", events)
        self.assertEqual((self.root / "last-orientation").read_text(), "portrait\n")

    def test_portrait_rotates_from_landscape_and_restores_original_rotation(self):
        self.command(
            "fbdepth",
            'echo "fbdepth $*" >> "$EVENTS"\n'
            'if [ "$2" = -o ]; then echo 1; else touch "$EVENTS.rotated"; fi',
        )
        self.command(
            "fbink",
            'if [ -f "$EVENTS.rotated" ]; then\n'
            '    echo "screenWidth=600;screenHeight=800;"\n'
            "else\n"
            '    echo "screenWidth=800;screenHeight=600;"\n'
            "fi",
        )
        status, _ = self.launch("portrait")
        self.assertEqual(status, "0")
        events = self.events.read_text()
        self.assertIn("fbdepth -q -r UR", events)
        self.assertIn("worker 600x800", events)
        self.assertIn("fbdepth -q -r 1", events)
        self.assertLess(events.index("initctl stop"), events.index("fbdepth -q -r UR"))

    def test_portrait_rotation_failure_restores_without_running_worker(self):
        self.command("fbink", 'echo "screenWidth=800;screenHeight=600;"')
        status, log = self.launch("portrait")
        self.assertEqual(status, "1")
        self.assertIn("did not report a 600x800 framebuffer", log)
        events = self.events.read_text()
        self.assertNotIn("worker", events)
        self.assertIn("fbdepth -q -r UR", events)
        self.assertIn("fbdepth -q -r UD", events)
        self.assertIn("fbdepth -q -r 0", events)
        self.assertIn("power -i com.lab126.powerd preventScreenSaver 0", events)

    def test_portrait_rejects_high_resolution_screen_without_changing_ui(self):
        status, log = self.launch("portrait")
        self.assertEqual(status, "1")
        self.assertIn("portrait layout requires a 600x800 display", log)
        self.assertFalse(self.events.exists())

    def test_rendered_layouts_fit_and_retain_forecast_samples(self):
        source = (ROOT / "MyDashboard/bin/dashboard.sh").read_text()
        source = source.replace("/tmp/mydashboard.run", str(self.state))
        (self.bin / "dashboard.sh").write_text(source)
        weather = {
            "current": {
                "temperature_2m": 45,
                "relative_humidity_2m": 80,
                "weather_code": 99,
                "wind_speed_10m": 12,
            },
            "hourly": {
                "time": [1795478400 + i * 3600 for i in range(12)],
                "temperature_2m": [None] + [40 + i for i in range(11)],
            },
        }
        fixture = self.root / "forecast.json"
        fixture.write_text(json.dumps(weather))
        request = self.root / "weather-request"
        self.command("curl", f'printf "%s\\n" "$@" > "{request}"\ncat "{fixture}"')
        self.command("fbink", 'printf "%s\\0" "$@" >> "$EVENTS"\nprintf "\\0" >> "$EVENTS"')
        self.command("sleep", f'touch "{self.state}/stop"')
        self.command(
            "date",
            'if [ "$1" = -d ]; then exec /bin/date "$@"; fi\n'
            'exec /bin/date -d "2026-08-31 15:25:00" "$@"',
        )
        env = dict(self.env, PATH=str(self.bin) + ":" + os.environ["PATH"])
        smooth_sizes = {"sans": {}, "serif": {}}
        for font, (width, height) in product(
            ("bitmap", "sans", "serif"), ((800, 600), (600, 800), (1448, 1072)),
        ):
            with self.subTest(font=font, width=width, height=height):
                self.state.mkdir()
                (self.state / "font").write_text(font + "\n")
                self.events.unlink(missing_ok=True)
                subprocess.run(
                    ["/bin/sh", str(self.bin / "dashboard.sh"),
                     str(self.state), f"{width}x{height}"],
                    env=env, check=True, timeout=5,
                )
                calls = [
                    record.decode().split("\0")
                    for record in self.events.read_bytes().split(b"\0\0")
                    if record
                ]
                query = parse_qs(urlsplit(request.read_text().splitlines()[-1]).query)
                self.assertEqual(query["latitude"], ["38.9072"])
                self.assertEqual(query["longitude"], ["-77.0369"])
                self.assertEqual(query["timezone"], ["America/New_York"])
                rectangles = []
                texts = []
                for args in calls:
                    if "--" not in args:
                        continue
                    text = args[args.index("--") + 1]
                    texts.append(text)
                    lines = text.split("\n")
                    if font == "bitmap":
                        self.assertEqual(args[args.index("-F") + 1], "IBM")
                        size = int(args[args.index("-S") + 1])
                        x = int(args[args.index("-X") + 1])
                        y = int(args[args.index("-Y") + 1])
                        right = x + max(map(len, lines)) * 8 * size
                        bottom = y + len(lines) * 8 * size
                    else:
                        options = dict(
                            part.split("=", 1) if "=" in part else (part, "")
                            for part in args[args.index("-t") + 1].split(",")
                        )
                        family = "DejaVuSans" if font == "sans" else "DejaVuSerif"
                        self.assertTrue(options["regular"].endswith("/" + family + ".ttf"))
                        self.assertTrue(options["bold"].endswith("/" + family + "-Bold.ttf"))
                        self.assertIn("notrunc", options)
                        x, y = int(options["left"]), int(options["top"])
                        right = width - int(options["right"])
                        bottom = height - int(options["bottom"])
                        self.assertLessEqual(len(lines) * (int(options["px"]) + 2), bottom - y)
                        smooth_sizes[font][width, height, x, y, text] = int(options["px"])
                    self.assertGreaterEqual(x, 0)
                    self.assertGreaterEqual(y, 0)
                    self.assertLessEqual(right, width)
                    self.assertLessEqual(bottom, height)
                    for ax, ay, bx, by in rectangles:
                        self.assertFalse(x < bx and right > ax and y < by and bottom > ay)
                    rectangles.append((x, y, right, bottom))
                if width in (600, 800):
                    self.assertIn("Washington,\nDC" if width == 600 else "Washington, DC", texts)
                    description = next(text for text in texts if text.startswith("Thunderstorms"))
                    self.assertEqual(description.replace("\n", " "), "Thunderstorms with hail")
                    forecast_y = 706 if width == 600 else 506
                    self.assertEqual(len([r for r in rectangles if r[1] == forecast_y]), 4)
                    self.assertIn("--", texts)
                    self.assertIn("31", texts)
                    highlighted = [args[-1] for args in calls if "-h" in args]
                    self.assertEqual(highlighted, ["31"])
                    for index in (0, 3, 6, 9):
                        hour = subprocess.check_output(
                            ["/bin/date", "-d", f"@{weather['hourly']['time'][index]}", "+%H:%M"],
                            env=dict(env, TZ="EST5EDT,M3.2.0,M11.1.0"), text=True,
                        ).strip()
                        self.assertIn(hour, texts)
                    for args in calls:
                        if "-k" in args and args[-1].startswith("left="):
                            region = dict(part.split("=") for part in args[-1].split(","))
                            self.assertLessEqual(int(region["left"]) + int(region["width"]), width)
                            self.assertLessEqual(int(region["top"]) + int(region["height"]), height)
                    self.assertIn("-s", calls[-1])
                    self.assertTrue(all("-b" in args for args in calls[:-1] if "-c" not in args))
                else:
                    if font == "bitmap":
                        self.assertEqual(len(rectangles), 6)
                    else:
                        self.assertEqual([args[-1] for args in calls if "-h" in args], ["31"])
                        self.assertIn("-s", calls[-1])
                    forecast = next(text for text in texts if text.startswith("HOURLY"))
                    self.assertEqual(len(forecast.splitlines()[2:]), 12)
                    self.assertIn("--", forecast)
                    self.assertIn("Thunderstorms with hail", "\n".join(texts))
                self.assertTrue(any("DAILY QUOTE" in text for text in texts))
                for file in self.state.iterdir():
                    file.unlink()
                self.state.rmdir()
        self.assertEqual(smooth_sizes["sans"].keys(), smooth_sizes["serif"].keys())
        for label, size in smooth_sizes["sans"].items():
            with self.subTest(label=label):
                self.assertGreater(size, smooth_sizes["serif"][label])

    def test_compact_weather_failure_still_displays_clock_and_calendar(self):
        source = (ROOT / "MyDashboard/bin/dashboard.sh").read_text()
        source = source.replace("/tmp/mydashboard.run", str(self.state))
        (self.bin / "dashboard.sh").write_text(source)
        self.state.mkdir()
        self.command("curl", "exit 1")
        self.command("fbink", 'printf "%s\\0" "$@" >> "$EVENTS"\nprintf "\\0" >> "$EVENTS"')
        self.command("sleep", f'touch "{self.state}/stop"')
        self.command("date", 'if [ "$1" = +%Z ]; then exit 0; fi\nexec /bin/date "$@"')
        env = dict(self.env, PATH=str(self.bin) + ":" + os.environ["PATH"])
        result = subprocess.run(
            ["/bin/sh", str(self.bin / "dashboard.sh"), str(self.state), "800x600"],
            env=env, capture_output=True, text=True, timeout=5,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("weather request failed", result.stderr)
        calls = [
            record.decode().split("\0")
            for record in self.events.read_bytes().split(b"\0\0")
            if record
        ]
        texts = [args[-1] for args in calls if "--" in args]
        self.assertIn("Weather unavailable", texts)
        self.assertIn("Weather update failed", texts)
        self.assertIn("No forecast available", texts)
        self.assertIn("HOURLY TEMPERATURES", texts)
        self.assertFalse(any("()" in text for text in texts))
        self.assertEqual(len([args for args in calls if "-h" in args]), 1)
        self.assertIn("-s", calls[-1])

    def test_smooth_font_failure_leaves_ui_power_and_rotation_untouched(self):
        self.command(
            "fbink",
            'if [ "$3" = -e ]; then echo "screenWidth=800;screenHeight=600;"; else exit 1; fi',
        )
        status, log = self.launch()
        self.assertEqual(status, "1")
        self.assertIn("OpenType-enabled FBInk", log)
        self.assertFalse(self.events.exists())

    def test_missing_bundled_font_fails_before_ui_shutdown(self):
        (self.root / "fonts").unlink()
        status, log = self.launch()
        self.assertEqual(status, "1")
        self.assertIn("missing bundled font files", log)
        self.assertFalse(self.events.exists())

    def test_bitmap_needs_neither_bundled_fonts_nor_opentype_support(self):
        (self.root / "fonts").unlink()
        self.install_saved_city({
            "name": "Tokyo", "latitude": 35.68, "longitude": 139.69,
            "timezone": "Asia/Tokyo", "font": "bitmap",
        })
        self.command(
            "fbink",
            'if [ "$3" = -e ]; then echo "screenWidth=1448;screenHeight=1072;"; else exit 1; fi',
        )
        self.command("dashboard.sh", 'cat "$1/font" >> "$EVENTS"')
        status, _ = self.launch()
        self.assertEqual(status, "0")
        self.assertIn("bitmap", self.events.read_text())

    def install_saved_city(self, data):
        source = (ROOT / "MyDashboard/bin/setup_server.py").read_text()
        (self.bin / "setup_server.py").write_text(source)
        self.command("python.sh", f'exec {shlex.quote(sys.executable)} "$@"')
        (self.root / "location.json").write_text(json.dumps(data))

    def test_invalid_saved_city_fails_before_ui_shutdown(self):
        self.install_saved_city({"name": "Bad settings"})
        status, log = self.launch()
        self.assertEqual(status, "1")
        self.assertIn("could not load saved city", log)
        self.assertFalse(self.events.exists())
        self.assertFalse(self.state.exists())

    def test_saved_city_is_prepared_and_cleaned_up(self):
        self.install_saved_city({
            "name": "Tokyo", "latitude": 35.68,
            "longitude": 139.69, "timezone": "Asia/Tokyo",
        })
        self.command(
            "dashboard.sh",
            'cat "$1/location" >> "$EVENTS"\n'
            'read -r TZ < "$1/timezone"\nexport TZ\ndate -d @0 +%H:%M >> "$EVENTS"',
        )
        self.command("fbink", 'echo "screenWidth=1448;screenHeight=1072;"')
        status, _ = self.launch()
        self.assertEqual(status, "0")
        events = self.events.read_text()
        self.assertIn("Tokyo", events)
        self.assertIn("latitude=35.68", events)
        self.assertIn("timezone=Asia%2FTokyo", events)
        self.assertIn("09:00", events)
        self.assertFalse(self.state.exists())

    def install_setup_launcher(self):
        source = (ROOT / "MyDashboard/bin/setup.sh").read_text()
        source = source.replace("/tmp/mydashboard.run", str(self.state))
        source = source.replace("/mnt/us/", str(self.usb) + "/")
        (self.bin / "setup.sh").write_text(source)
        self.command("start.sh", 'echo "start $*" >> "$EVENTS"')

    def test_kual_font_actions_preserve_city_and_stop_dashboard_without_browser(self):
        self.install_setup_launcher()
        city = {"name": "Tokyo", "latitude": 35.68, "longitude": 139.69, "timezone": "Asia/Tokyo"}
        self.install_saved_city(city)
        self.command("stop.sh", f'rmdir "{self.state}"\necho stopped >> "$EVENTS"')
        self.command("curl", 'echo unexpected-network >> "$EVENTS"\nexit 1')
        menu = json.loads((ROOT / "MyDashboard/menu.json").read_text())
        actions = [item["action"] for item in menu["items"][0]["items"] if item["name"].startswith("Font:")]
        self.assertEqual(len(actions), 3)
        for action in actions:
            with self.subTest(action=action):
                self.state.mkdir()
                self.events.unlink(missing_ok=True)
                script, *args = shlex.split(action)
                previous = {"sans": None, "serif": "landscape", "bitmap": "portrait"}[args[-1]]
                if previous is None:
                    (self.root / "last-orientation").unlink(missing_ok=True)
                else:
                    (self.root / "last-orientation").write_text(previous + "\n")
                subprocess.run(
                    ["/bin/sh", str(self.bin / Path(script).name), *args],
                    env=self.env, check=True, timeout=5,
                )
                saved = json.loads((self.root / "location.json").read_text())
                self.assertEqual(saved, dict(city, font=args[-1]))
                self.assertEqual(self.events.read_text(), "stopped\nstart " + (previous or "portrait") + "\n")
                self.assertFalse(self.state.exists())
                self.assertIn(str(self.log), self.setup_log.read_text())
                self.assertEqual(list(self.usb.iterdir()), [])

    def test_setup_missing_runtime_leaves_dashboard_untouched(self):
        self.install_setup_launcher()
        self.state.mkdir()
        self.command("python.sh", 'echo "missing runtime" >&2\nexit 1')
        result = subprocess.run(
            ["/bin/sh", str(self.bin / "setup.sh"), "--font", "serif"],
            env=self.env, capture_output=True, text=True, timeout=5,
        )
        self.assertEqual(result.returncode, 1)
        self.assertTrue(self.state.exists())
        self.assertFalse(self.events.exists())
        self.assertIn("prerequisites are unavailable", result.stderr)
        self.assertIn("missing runtime", self.setup_log.read_text())

    def test_ip_detection_stops_dashboard_and_does_not_open_browser(self):
        self.install_setup_launcher()
        self.state.mkdir()
        self.command("stop.sh", f'rmdir "{self.state}"\necho stopped >> "$EVENTS"')
        self.command("python.sh", 'echo "$*" >> "$EVENTS"')
        subprocess.run(
            ["/bin/sh", str(self.bin / "setup.sh"), "--detect-location"],
            env=self.env, check=True, timeout=5,
        )
        events = self.events.read_text()
        self.assertLess(events.index("--check"), events.index("stopped"))
        self.assertLess(events.index("stopped"), events.index("--detect-location"))
        self.assertLess(events.index("--detect-location"), events.index("start portrait"))
        self.assertNotIn("power", events)
        self.assertFalse(self.state.exists())

    def test_ip_detection_failure_is_logged_and_returns_failure(self):
        self.install_setup_launcher()
        self.command("python.sh", '[ "$2" = --check ] && exit 0\necho "lookup offline" >&2\nexit 1')
        result = subprocess.run(
            ["/bin/sh", str(self.bin / "setup.sh"), "--detect-location"],
            env=self.env, capture_output=True, text=True, timeout=5,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("could not detect city", result.stderr)
        self.assertIn("lookup offline", self.setup_log.read_text())
        self.assertFalse(self.events.exists())

    def test_settings_report_an_immediate_restart_failure(self):
        self.install_setup_launcher()
        self.command("python.sh", "exit 0")
        self.command("start.sh", 'echo "missing nohup" >&2\nexit 1')
        result = subprocess.run(
            ["/bin/sh", str(self.bin / "setup.sh"), "--font", "sans"],
            env=self.env, capture_output=True, text=True, timeout=5,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("settings saved, but could not start dashboard", result.stderr)
        self.assertIn("missing nohup", self.setup_log.read_text())

    def test_invalid_remembered_orientation_leaves_running_dashboard_untouched(self):
        self.install_setup_launcher()
        self.state.mkdir()
        (self.root / "last-orientation").write_text("invalid\n")
        self.command("python.sh", 'echo unexpected-update >> "$EVENTS"')
        result = subprocess.run(
            ["/bin/sh", str(self.bin / "setup.sh"), "--font", "sans"],
            env=self.env, capture_output=True, text=True, timeout=5,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("invalid last dashboard orientation", result.stderr)
        self.assertTrue(self.state.exists())
        self.assertFalse(self.events.exists())


if __name__ == "__main__":
    unittest.main()
