#!/usr/bin/env python3
"""Loopback-only city setup and native-renderer configuration preparation."""

import argparse
from dataclasses import asdict, dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from importlib import resources
import io
import json
import math
import os
from pathlib import Path
import re
import secrets
import sys
import tempfile
import time
import unicodedata
from urllib.error import URLError
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import urlopen

if sys.version_info < (3, 9):
    sys.exit("MyDashboard: city setup requires Python 3.9 or newer.")

from zoneinfo import TZPATH, ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
SETTINGS = ROOT / "location.json"
PAGE = ROOT / "setup.html"
STATE = Path("/tmp/mydashboard.run")
PORT = 8765
MAX_BODY = 4096


@dataclass(frozen=True)
class Location:
    name: str
    latitude: float
    longitude: float
    timezone: str


DEFAULT = Location("Washington, DC", 38.9072, -77.0369, "America/New_York")


def validate_location(data: object) -> Location:
    if not isinstance(data, dict):
        raise ValueError("Select a city from the search results.")
    name, timezone = data.get("name"), data.get("timezone")
    if (
        not isinstance(name, str) or not name.strip() or len(name) > 128
        or any(unicodedata.category(char).startswith("C") for char in name)
    ):
        raise ValueError("City name must be 1-128 characters without control characters.")
    if (
        not isinstance(timezone, str)
        or not re.fullmatch(r"[A-Za-z0-9_+-]+(?:/[A-Za-z0-9_+-]+)*", timezone)
    ):
        raise ValueError("The city must have a valid IANA timezone.")
    coordinates = []
    for key, bound in (("latitude", 90), ("longitude", 180)):
        value = data.get(key)
        if (
            isinstance(value, bool) or not isinstance(value, (int, float))
            or abs(value) > bound or not math.isfinite(value)
        ):
            raise ValueError("City coordinates are missing or out of range.")
        coordinates.append(float(value))
    display_name(name)
    return Location(name.strip(), coordinates[0], coordinates[1], timezone)


def display_name(name: str) -> str:
    label = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    if not label.strip():
        raise ValueError("This city needs an English display name for the built-in bitmap font.")
    return label.strip()


def timezone_bytes(key: str) -> bytes:
    for directory in TZPATH:
        path = Path(directory).joinpath(*key.split("/"))
        if path.is_file():
            return path.read_bytes()
    try:
        resource = resources.files("tzdata.zoneinfo")
        for component in key.split("/"):
            resource = resource.joinpath(component)
        return resource.read_bytes()
    except (ModuleNotFoundError, FileNotFoundError) as error:
        raise ValueError(
            "Timezone data unavailable for " + key
            + ". Install the tzdata Python package in the Kindle's Python environment."
        ) from error


def checked_timezone(location: Location) -> bytes:
    data = timezone_bytes(location.timezone)
    ZoneInfo.from_file(io.BytesIO(data), key=location.timezone)
    return data


def load_location(path: Path) -> Location:
    if not path.exists():
        return DEFAULT
    return validate_location(json.loads(path.read_text(encoding="utf-8")))


def save_location(path: Path, data: object) -> Location:
    location = validate_location(data)
    checked_timezone(location)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as file:
            temporary = Path(file.name)
            json.dump(asdict(location), file, ensure_ascii=False, allow_nan=False)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    return location


def prepare_location(path: Path, state: Path) -> None:
    location = load_location(path)
    zone = checked_timezone(location)
    query = urlencode({
        "latitude": location.latitude,
        "longitude": location.longitude,
        "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m",
        "hourly": "temperature_2m",
        "forecast_hours": 12,
        "temperature_unit": "fahrenheit",
        "wind_speed_unit": "mph",
        "timezone": location.timezone,
        "timeformat": "unixtime",
    })
    (state / "timezone").write_bytes(zone)
    (state / "location").write_text(
        display_name(location.name) + "\n"
        + "https://api.open-meteo.com/v1/forecast?" + query + "\n",
        encoding="ascii",
    )


def search_cities(query: str, country: str) -> list:
    if not 2 <= len(query) <= 100:
        raise ValueError("Enter 2-100 characters for the city or postal code.")
    if country and not re.fullmatch(r"[A-Za-z]{2}", country):
        raise ValueError("Country must be a two-letter code, such as US or GB, or blank.")
    parameters = {"name": query, "count": "10", "language": "en", "format": "json"}
    if country:
        parameters["countryCode"] = country.upper()
    url = "https://geocoding-api.open-meteo.com/v1/search?" + urlencode(parameters)
    with urlopen(url, timeout=12) as response:
        body = response.read(262145)
    if len(body) > 262144:
        raise ValueError("City search returned an oversized response.")
    data = json.loads(body)
    if not isinstance(data, dict) or data.get("error"):
        raise ValueError("City search returned an invalid response.")
    results = data.get("results", [])
    if not isinstance(results, list):
        raise ValueError("City search returned invalid results.")
    cities = []
    for result in results[:10]:
        location = validate_location(result)
        cities.append(dict(
            asdict(location), region=result.get("admin1", ""),
            country=result.get("country", ""),
        ))
    return cities


class SetupServer(HTTPServer):
    def __init__(self, address: tuple, settings: Path, state: Path, page: Path):
        self.settings_path = settings
        self.state_path = state
        self.page_path = page
        self.token = secrets.token_hex(24)
        super().__init__(address, SetupHandler)

    def get_request(self):
        connection, address = super().get_request()
        connection.settimeout(15)
        return connection, address


class SetupHandler(BaseHTTPRequestHandler):
    server: SetupServer

    def reply(self, status: int, data: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers()
        self.wfile.write(data)

    def reply_json(self, status: int, data: dict) -> None:
        self.reply(status, json.dumps(data, allow_nan=False).encode(), "application/json; charset=utf-8")

    def allowed(self, token: bool = False) -> bool:
        host = "127.0.0.1:" + str(self.server.server_address[1])
        if (
            self.headers.get("Host") != host
            or self.headers.get("Origin", "http://" + host) != "http://" + host
            or (token and not secrets.compare_digest(
                self.headers.get("X-MyDashboard-Token", ""), self.server.token
            ))
        ):
            self.reply_json(403, {"error": "Open setup from the Kindle's KUAL entry."})
            return False
        return True

    def do_GET(self) -> None:
        if not self.allowed():
            return
        request = urlsplit(self.path)
        try:
            if request.path == "/health":
                self.reply(200, b"mydashboard-setup-v1", "text/plain")
            elif request.path == "/":
                page = self.server.page_path.read_text(encoding="utf-8")
                self.reply(200, page.replace("__TOKEN__", self.server.token).encode(), "text/html; charset=utf-8")
            elif not self.allowed(token=True):
                return
            elif request.path == "/api/location":
                location = load_location(self.server.settings_path)
                self.reply_json(200, dict(
                    asdict(location), saved=self.server.settings_path.exists(),
                    display_name=display_name(location.name),
                ))
            elif request.path == "/api/search":
                parameters = parse_qs(request.query)
                cities = search_cities(
                    parameters.get("q", [""])[0].strip(),
                    parameters.get("country", [""])[0].strip(),
                )
                self.reply_json(200, {"results": cities})
            else:
                self.reply_json(404, {"error": "Not found."})
        except (URLError, TimeoutError) as error:
            self.log_error("City search failed: %s", error)
            self.reply_json(502, {"error": "City search failed. Check Wi-Fi, device clock and HTTPS certificates."})
        except (ValueError, UnicodeError) as error:
            self.log_error("Invalid setup data: %s", error)
            self.reply_json(400, {"error": str(error)})
        except OSError as error:
            self.log_error("Setup read failed: %s", error)
            self.reply_json(500, {"error": "Could not read setup files; see mydashboard-setup.log."})

    def do_POST(self) -> None:
        if not self.allowed(token=True):
            return
        if self.path != "/api/location":
            self.reply_json(404, {"error": "Not found."})
            return
        try:
            if self.server.state_path.exists():
                self.reply_json(409, {"error": "Stop the dashboard before saving a city."})
                return
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_BODY:
                raise ValueError("Invalid settings request size.")
            if self.headers.get_content_type() != "application/json":
                raise ValueError("Settings must be sent as JSON.")
            location = save_location(
                self.server.settings_path, json.loads(self.rfile.read(length))
            )
            self.reply_json(200, dict(asdict(location), display_name=display_name(location.name)))
        except (ValueError, UnicodeError) as error:
            self.log_error("Could not save city: %s", error)
            self.reply_json(400, {"error": str(error)})
        except OSError as error:
            self.log_error("Could not write settings: %s", error)
            self.reply_json(500, {"error": "Could not save settings; see mydashboard-setup.log."})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--prepare", type=Path, metavar="STATE_DIRECTORY")
    arguments = parser.parse_args()
    try:
        if arguments.prepare:
            prepare_location(SETTINGS, arguments.prepare)
        elif arguments.check:
            checked_timezone(DEFAULT)
        else:
            with SetupServer(("127.0.0.1", PORT), SETTINGS, STATE, PAGE) as server:
                server.timeout = 1
                deadline = time.monotonic() + 900
                print("MyDashboard: city setup listening on 127.0.0.1:8765 for 15 minutes.", flush=True)
                while time.monotonic() < deadline:
                    server.handle_request()
                print("MyDashboard: city setup session expired.", flush=True)
    except (OSError, ValueError, UnicodeError) as error:
        sys.exit("MyDashboard: " + str(error))


if __name__ == "__main__":
    main()
