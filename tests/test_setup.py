import contextlib
import http.client
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import URLError
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
            env=dict(os.environ, TZ=":" + str(self.root / "timezone")), text=True,
        ).strip()
        self.assertEqual(hour, "09:00")

    def test_invalid_settings_preserve_previously_saved_city(self):
        setup.save_location(self.path, TOKYO)
        original = self.path.read_bytes()
        for change in (
            {"latitude": float("nan")}, {"latitude": True}, {"longitude": 181},
            {"timezone": "../../etc/passwd"}, {"name": "Bad\ncity"},
            {"latitude": "35.68"}, {"name": ""}, {"latitude": 10 ** 400},
        ):
            with self.subTest(change=change):
                with self.assertRaises(ValueError):
                    setup.save_location(self.path, dict(TOKYO, **change))
                self.assertEqual(self.path.read_bytes(), original)
        with patch.object(setup, "timezone_bytes", side_effect=ValueError("missing tzdata")):
            with self.assertRaisesRegex(ValueError, "missing tzdata"):
                setup.save_location(self.path, TOKYO)
        self.assertEqual(self.path.read_bytes(), original)

    def test_prepared_timezone_observes_dst(self):
        setup.save_location(self.path, vars(setup.DEFAULT))
        setup.prepare_location(self.path, self.root)
        env = dict(os.environ, TZ=":" + str(self.root / "timezone"))
        for stamp, expected in (("2026-01-15 12:00 UTC", "07:00"), ("2026-07-15 12:00 UTC", "08:00")):
            with self.subTest(stamp=stamp):
                result = subprocess.check_output(["/bin/date", "-d", stamp, "+%H:%M"], env=env, text=True)
                self.assertEqual(result.strip(), expected)

    def test_search_encodes_city_and_country_and_keeps_disambiguating_region(self):
        result = dict(TOKYO, admin1="Tokyo", country="Japan")
        with patch.object(setup, "urlopen") as opener:
            opener.return_value.__enter__.return_value.read.return_value = json.dumps({"results": [result]}).encode()
            cities = setup.search_cities("Tokyo & nearby", "jp")
        query = parse_qs(urlsplit(opener.call_args.args[0]).query)
        self.assertEqual(query["name"], ["Tokyo & nearby"])
        self.assertEqual(query["countryCode"], ["JP"])
        self.assertEqual(cities[0]["region"], "Tokyo")
        self.assertEqual(cities[0]["country"], "Japan")
        self.assertEqual(cities[0]["timezone"], "Asia/Tokyo")

    def test_native_renderer_consumes_prepared_city_coordinates_and_timezone(self):
        setup.save_location(self.path, TOKYO)
        binary = self.root / "bin"
        binary.mkdir()
        state = self.root / "state"
        source = (ROOT / "MyDashboard/bin/dashboard.sh").read_text()
        (binary / "dashboard.sh").write_text(source.replace("/tmp/mydashboard.run", str(state)))
        requests = self.root / "requests"
        drawing = self.root / "drawing"
        commands = {
            "curl": f'printf "%s\\n" "$@" > "{requests}"\nexit 1',
            "fbink": f'printf "%s\\0" "$@" >> "{drawing}"\nprintf "\\0" >> "{drawing}"',
            "sleep": f'touch "{state}/stop"',
            "date": 'if [ "$1" = -d ]; then exec /bin/date "$@"; fi\nexec /bin/date -d @0 "$@"',
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
                url = requests.read_text().splitlines()[-1]
                query = parse_qs(urlsplit(url).query)
                self.assertEqual(query["latitude"], ["35.68"])
                self.assertEqual(query["timezone"], ["Asia/Tokyo"])
                for path in state.iterdir():
                    path.unlink()
                state.rmdir()

    def test_service_lifetime_is_fifteen_minutes(self):
        with (
            patch.object(sys, "argv", ["setup_server.py"]),
            patch.object(setup, "SetupServer") as server,
            patch.object(setup.time, "monotonic", side_effect=[0, 899, 900]),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            setup.main()
        server.assert_called_once_with(("127.0.0.1", 8765), setup.SETTINGS, setup.STATE, setup.PAGE)
        server.return_value.__enter__.return_value.handle_request.assert_called_once()


class SetupHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / "location.json"
        self.state = self.root / "state"
        self.server = setup.SetupServer(
            ("127.0.0.1", 0), self.path, self.state, ROOT / "MyDashboard/setup.html",
        )
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.01})
        self.thread.start()
        self.addCleanup(self.close_server)

    def close_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)

    def request(self, method, path, body=None, headers=None):
        connection = http.client.HTTPConnection(*self.server.server_address, timeout=3)
        self.addCleanup(connection.close)
        request_headers = {"X-MyDashboard-Token": self.server.token}
        if body is not None:
            request_headers["Content-Type"] = "application/json"
        request_headers.update(headers or {})
        connection.request(method, path, body=None if body is None else json.dumps(body), headers=request_headers)
        response = connection.getresponse()
        data = response.read()
        return response.status, data

    def test_default_search_select_save_and_reload(self):
        status, body = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertNotIn(b"__TOKEN__", body)
        self.assertIn(self.server.token.encode(), body)
        status, body = self.request("GET", "/api/location")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["name"], "Washington, DC")
        self.assertFalse(json.loads(body)["saved"])
        with patch.object(setup, "search_cities", return_value=[dict(TOKYO, country="Japan", region="Tokyo")]):
            status, body = self.request("GET", "/api/search?q=Tokyo")
        self.assertEqual(status, 200)
        choice = json.loads(body)["results"][0]
        status, body = self.request("POST", "/api/location", choice)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["name"], "Tokyo")
        self.assertEqual(setup.load_location(self.path).timezone, "Asia/Tokyo")
        status, body = self.request("GET", "/api/location")
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(body)["saved"])
        self.assertEqual(json.loads(body)["name"], "Tokyo")

    def test_empty_results_and_network_failure_are_distinct(self):
        with patch.object(setup, "search_cities", return_value=[]):
            status, body = self.request("GET", "/api/search?q=Nowhere")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["results"], [])
        with patch.object(setup, "search_cities", side_effect=URLError("offline")):
            status, body = self.request("GET", "/api/search?q=Tokyo")
        self.assertEqual(status, 502)
        self.assertIn("Wi-Fi", json.loads(body)["error"])
        self.assertFalse(self.path.exists())

    def test_save_rejects_foreign_requests_invalid_settings_and_running_dashboard(self):
        for headers in (
            {"Host": "example.com"}, {"Origin": "https://example.com"},
            {"X-MyDashboard-Token": "invalid"},
        ):
            with self.subTest(headers=headers):
                status, _ = self.request("POST", "/api/location", TOKYO, headers)
                self.assertEqual(status, 403)
        status, _ = self.request("POST", "/api/location", dict(TOKYO, longitude=190))
        self.assertEqual(status, 400)
        self.state.mkdir()
        status, body = self.request("POST", "/api/location", TOKYO)
        self.assertEqual(status, 409)
        self.assertIn("Stop", json.loads(body)["error"])
        self.assertFalse(self.path.exists())

    def test_persistence_failure_returns_an_error(self):
        with patch.object(setup, "save_location", side_effect=OSError("read-only storage")):
            status, body = self.request("POST", "/api/location", TOKYO)
        self.assertEqual(status, 500)
        self.assertIn("Could not save", json.loads(body)["error"])

    def test_malformed_settings_can_be_replaced_through_setup(self):
        self.path.write_text("invalid json")
        status, body = self.request("GET", "/api/location")
        self.assertEqual(status, 400)
        self.assertIn("error", json.loads(body))
        status, _ = self.request("POST", "/api/location", TOKYO)
        self.assertEqual(status, 200)
        self.assertEqual(setup.load_location(self.path).name, "Tokyo")


if __name__ == "__main__":
    unittest.main()
