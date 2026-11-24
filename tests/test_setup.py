import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "MyDashboard/bin"))
import setup_server as setup


TOKYO = {"name": "Tokyo", "latitude": 35.68, "longitude": 139.69, "timezone": "Asia/Tokyo"}


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / "location.json"

    def mock_ip_response(self, body):
        def respond(command, *, stdout, **kwargs):
            stdout.write(body)
            return subprocess.CompletedProcess(command, 0, stderr=b"")
        return patch.object(setup.subprocess, "run", side_effect=respond)

    def test_save_reload_and_prepare_timezone_and_forecast_url(self):
        setup.save_location(self.path, TOKYO)
        self.assertEqual(setup.load_location(self.path).name, "Tokyo")
        setup.prepare_location(self.path, self.root)
        city, url = (self.root / "location").read_text().splitlines()
        self.assertEqual(city, "Tokyo")
        query = parse_qs(urlsplit(url).query)
        self.assertEqual(query["latitude"], ["35.68"])
        self.assertEqual(query["longitude"], ["139.69"])
        self.assertEqual(query["timezone"], ["Asia/Tokyo"])
        hour = subprocess.check_output(
            ["/bin/date", "-d", "@0", "+%H:%M"],
            env=dict(os.environ, TZ=(self.root / "timezone").read_text().strip()), text=True,
        ).strip()
        self.assertEqual(hour, "09:00")

    def test_invalid_settings_preserve_previously_saved_city(self):
        setup.save_location(self.path, TOKYO)
        original = self.path.read_bytes()
        for change in (
            {"latitude": float("nan")}, {"latitude": True}, {"longitude": 181},
            {"timezone": "../../etc/passwd"}, {"name": "Bad\ncity"},
            {"latitude": "35.68"}, {"name": ""}, {"latitude": 10 ** 400},
            {"font": "custom"}, {"font": "../../bad.ttf"}, {"font": None},
            {"font": ["sans"]},
        ):
            with self.subTest(change=change):
                with self.assertRaises(ValueError):
                    setup.save_location(self.path, dict(TOKYO, **change))
                self.assertEqual(self.path.read_bytes(), original)
        with patch.object(setup, "timezone_bytes", side_effect=ValueError("missing tzdata")):
            with self.assertRaisesRegex(ValueError, "missing tzdata"):
                setup.save_location(self.path, TOKYO)
        self.assertEqual(self.path.read_bytes(), original)

    def test_font_choices_round_trip_and_legacy_settings_use_sans(self):
        self.path.write_text(json.dumps(TOKYO))
        self.assertEqual(setup.load_location(self.path).font, "sans")
        for font in ("sans", "serif", "bitmap"):
            with self.subTest(font=font):
                setup.save_location(self.path, dict(TOKYO, font=font))
                self.assertEqual(setup.load_location(self.path).font, font)
                self.assertEqual(json.loads(self.path.read_text())["font"], font)
                setup.prepare_location(self.path, self.root)
                self.assertEqual((self.root / "font").read_text(), font + "\n")
                self.assertEqual((self.root / "location").read_text().splitlines()[0], "Tokyo")

    def test_font_cli_preserves_saved_city_and_applies_every_style(self):
        setup.save_location(self.path, TOKYO)
        for font in ("sans", "serif", "bitmap"):
            with self.subTest(font=font):
                with (
                    patch.object(sys, "argv", ["setup_server.py", "--font", font]),
                    patch.object(setup, "SETTINGS", self.path),
                    patch.object(setup, "STATE", self.root / "state"),
                    patch.object(setup.subprocess, "run") as network,
                    contextlib.redirect_stdout(io.StringIO()) as output,
                ):
                    setup.main()
                self.assertEqual(json.loads(self.path.read_text()), dict(TOKYO, font=font))
                self.assertIn("saved font: " + font, output.getvalue())
                network.assert_not_called()
                setup.prepare_location(self.path, self.root)
                self.assertEqual((self.root / "font").read_text(), font + "\n")

    def test_font_cli_without_saved_city_keeps_default_location(self):
        with (
            patch.object(sys, "argv", ["setup_server.py", "--font", "bitmap"]),
            patch.object(setup, "SETTINGS", self.path),
            patch.object(setup, "STATE", self.root / "state"),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            setup.main()
        self.assertEqual(setup.load_location(self.path), setup.Location(
            "Washington, DC", 38.9072, -77.0369, "America/New_York", "bitmap",
        ))

    def test_font_cli_rejects_invalid_input_and_preserves_settings_on_failure(self):
        setup.save_location(self.path, TOKYO)
        original = self.path.read_bytes()
        for font, running in (("invalid", False), ("serif", True), ("serif", False)):
            with self.subTest(font=font, running=running):
                state = self.root / "state"
                if running:
                    state.mkdir()
                with (
                    patch.object(sys, "argv", ["setup_server.py", "--font", font]),
                    patch.object(setup, "SETTINGS", self.path),
                    patch.object(setup, "STATE", state),
                    patch.object(setup, "timezone_bytes", side_effect=ValueError("missing tzdata")),
                    contextlib.redirect_stderr(io.StringIO()),
                ):
                    with self.assertRaises(SystemExit) as error:
                        setup.main()
                if font != "invalid":
                    self.assertIn("Stop the dashboard" if running else "missing tzdata", str(error.exception))
                self.assertEqual(self.path.read_bytes(), original)
                if running:
                    state.rmdir()

    def test_ip_detection_saves_city_timezone_and_preserves_font(self):
        response = {
            "success": True, "city": "Tokyo", "latitude": 35.68,
            "longitude": 139.69, "timezone": {"id": "Asia/Tokyo"},
        }
        for font in ("sans", "serif"):
            with self.subTest(font=font):
                if font == "serif":
                    setup.save_location(self.path, dict(vars(setup.DEFAULT), font=font))
                with self.mock_ip_response(json.dumps(response).encode()) as curl:
                    location = setup.detect_location(self.path)
                command = curl.call_args.args[0]
                self.assertEqual(command[0:3], ["curl", "-q", "-fsS"])
                self.assertEqual(command[-1], "https://ipwho.is/")
                self.assertNotIn("-k", command)
                self.assertNotIn("--insecure", command)
                self.assertEqual(curl.call_args.kwargs["timeout"], 15)
                self.assertEqual(location, setup.Location(**TOKYO, font=font))
                self.assertEqual(setup.load_location(self.path), location)
                setup.prepare_location(self.path, self.root)
                self.assertIn("timezone=Asia%2FTokyo", (self.root / "location").read_text())

    def test_failed_ip_detection_preserves_saved_settings(self):
        setup.save_location(self.path, TOKYO)
        original = self.path.read_bytes()
        valid = {
            "success": True, "city": "Washington, DC", "latitude": 38.9072,
            "longitude": -77.0369, "timezone": {"id": "America/New_York"},
        }
        for body in (
            b"not JSON", b"x" * 16385, b"[]",
            json.dumps({"success": False, "message": "rate limited"}).encode(),
            json.dumps(dict(valid, timezone=None)).encode(),
            json.dumps(dict(valid, city="")).encode(),
            json.dumps(dict(valid, latitude=91)).encode(),
            json.dumps(dict(valid, timezone={"id": "../invalid"})).encode(),
        ):
            with self.subTest(body=body[:80]):
                with self.mock_ip_response(body):
                    with self.assertRaises(ValueError):
                        setup.detect_location(self.path)
                self.assertEqual(self.path.read_bytes(), original)
        with self.mock_ip_response(json.dumps(valid).encode()):
            with patch.object(setup, "timezone_bytes", side_effect=ValueError("missing tzdata")):
                with self.assertRaisesRegex(ValueError, "missing tzdata"):
                    setup.detect_location(self.path)
        self.assertEqual(self.path.read_bytes(), original)

    def test_ip_detection_curl_errors_and_timeouts_preserve_settings(self):
        setup.save_location(self.path, TOKYO)
        original = self.path.read_bytes()
        with patch.object(
            setup.subprocess, "run",
            return_value=subprocess.CompletedProcess(
                ["curl"], 60, stderr=b"curl: (60) SSL certificate problem",
            ),
        ):
            with self.assertRaisesRegex(ValueError, "HTTPS request failed .*curl: .*SSL certificate"):
                setup.detect_location(self.path)
        self.assertEqual(self.path.read_bytes(), original)
        with patch.object(
            setup.subprocess, "run", side_effect=subprocess.TimeoutExpired(["curl"], 15),
        ):
            with self.assertRaisesRegex(ValueError, "HTTPS request timed out"):
                setup.detect_location(self.path)
        self.assertEqual(self.path.read_bytes(), original)

    def test_ip_detection_cli_logs_success(self):
        with (
            patch.object(sys, "argv", ["setup_server.py", "--detect-location"]),
            patch.object(setup, "SETTINGS", self.path),
            patch.object(setup, "STATE", self.root / "state"),
            self.mock_ip_response(json.dumps({
                "success": True, "city": "Tokyo", "latitude": 35.68,
                "longitude": 139.69, "timezone": {"id": "Asia/Tokyo"},
            }).encode()),
            contextlib.redirect_stdout(io.StringIO()) as output,
        ):
            setup.main()
        self.assertEqual(setup.load_location(self.path).name, "Tokyo")
        self.assertIn("saved IP-detected city: Tokyo (Asia/Tokyo)", output.getvalue())

    def test_ip_detection_cli_refuses_to_change_a_running_dashboard(self):
        state = self.root / "state"
        state.mkdir()
        with (
            patch.object(sys, "argv", ["setup_server.py", "--detect-location"]),
            patch.object(setup, "STATE", state),
            patch.object(setup, "detect_location") as detect,
        ):
            with self.assertRaisesRegex(SystemExit, "Stop the dashboard"):
                setup.main()
        detect.assert_not_called()

    def test_prepared_timezone_observes_dst(self):
        setup.save_location(self.path, vars(setup.DEFAULT))
        setup.prepare_location(self.path, self.root)
        env = dict(os.environ, TZ=(self.root / "timezone").read_text().strip())
        for stamp, expected in (("2026-01-15 12:00 UTC", "07:00"), ("2026-07-15 12:00 UTC", "08:00")):
            with self.subTest(stamp=stamp):
                result = subprocess.check_output(["/bin/date", "-d", stamp, "+%H:%M"], env=env, text=True)
                self.assertEqual(result.strip(), expected)

    def test_prepared_seattle_timezone_handles_date_and_dst_boundaries(self):
        setup.save_location(self.path, {
            "name": "Seattle", "latitude": 47.6062, "longitude": -122.3321,
            "timezone": "America/Los_Angeles",
        })
        setup.prepare_location(self.path, self.root)
        env = dict(os.environ, TZ=(self.root / "timezone").read_text().strip())
        for stamp, expected in (
            ("2026-11-24 03:10 UTC", "2026-11-23 19:10 PST"),
            ("2026-03-08 09:59 UTC", "2026-03-08 01:59 PST"),
            ("2026-03-08 10:00 UTC", "2026-03-08 03:00 PDT"),
            ("2026-11-01 08:59 UTC", "2026-11-01 01:59 PDT"),
            ("2026-11-01 09:00 UTC", "2026-11-01 01:00 PST"),
        ):
            with self.subTest(stamp=stamp):
                result = subprocess.check_output(
                    ["/bin/date", "-d", stamp, "+%Y-%m-%d %H:%M %Z"], env=env, text=True,
                )
                self.assertEqual(result.strip(), expected)

    def test_timezone_without_portable_rules_preserves_saved_settings(self):
        setup.save_location(self.path, TOKYO)
        original = self.path.read_bytes()
        data = setup.timezone_bytes("Asia/Tokyo").rsplit(b"\n", 2)[0] + b"\n\n"
        with patch.object(setup, "timezone_bytes", return_value=data):
            with self.assertRaisesRegex(ValueError, "POSIX timezone rule"):
                setup.save_location(self.path, vars(setup.DEFAULT))
        self.assertEqual(self.path.read_bytes(), original)

    def test_native_renderer_consumes_prepared_city_coordinates_and_timezone(self):
        setup.save_location(self.path, TOKYO)
        binary = self.root / "bin"
        binary.mkdir()
        shutil.copy(ROOT / "MyDashboard/bin/font.sh", binary)
        (self.root / "fonts").symlink_to(ROOT / "MyDashboard/fonts", target_is_directory=True)
        state = self.root / "state"
        source = (ROOT / "MyDashboard/bin/dashboard.sh").read_text()
        (binary / "dashboard.sh").write_text(source.replace("/tmp/mydashboard.run", str(state)))
        requests = self.root / "requests"
        drawing = self.root / "drawing"
        commands = {
            "curl": f'printf "%s\\n" "$@" > "{requests}"\nexit 1',
            "fbink": f'printf "%s\\0" "$@" >> "{drawing}"\nprintf "\\0" >> "{drawing}"',
            "sleep": f'touch "{state}/stop"',
            "date": 'case "$TZ" in :*|/*) TZ=UTC0; export TZ ;; esac\n'
                    'if [ "$1" = -d ]; then exec /bin/date "$@"; fi\nexec /bin/date -d @0 "$@"',
        }
        for name, body in commands.items():
            path = binary / name
            path.write_text("#!/bin/sh\n" + body + "\n")
            path.chmod(0o755)
        env = dict(os.environ, PATH=str(binary) + ":" + os.environ["PATH"])
        for layout in ("800x600", "600x800", "1448x1072"):
            with self.subTest(layout=layout):
                state.mkdir()
                setup.prepare_location(self.path, state)
                drawing.unlink(missing_ok=True)
                result = subprocess.run(
                    ["/bin/sh", str(binary / "dashboard.sh"), str(state), layout],
                    env=env, text=True, capture_output=True, timeout=5,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                calls = [
                    record.decode().split("\0")
                    for record in drawing.read_bytes().split(b"\0\0") if record
                ]
                text = "\n".join(args[-1] for args in calls if "--" in args)
                self.assertIn("Tokyo", text)
                self.assertIn("09:00", text)
                if layout != "1448x1072":
                    self.assertIn("HOURLY TEMPERATURES (JST)", text)
                url = requests.read_text().splitlines()[-1]
                query = parse_qs(urlsplit(url).query)
                self.assertEqual(query["latitude"], ["35.68"])
                self.assertEqual(query["timezone"], ["Asia/Tokyo"])
                for path in state.iterdir():
                    path.unlink()
                state.rmdir()


if __name__ == "__main__":
    unittest.main()
