#!/usr/bin/env python3
"""City detection, font settings, and native-renderer configuration."""

import argparse
from dataclasses import asdict, dataclass
from importlib import resources
import io
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unicodedata
from urllib.parse import urlencode

if sys.version_info < (3, 9):
    sys.exit("MyDashboard: settings require Python 3.9 or newer.")

from zoneinfo import TZPATH, ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
SETTINGS = ROOT / "location.json"
STATE = Path("/tmp/mydashboard.run")


@dataclass(frozen=True)
class Location:
    name: str
    latitude: float
    longitude: float
    timezone: str
    font: str = "sans"


DEFAULT = Location("Washington, DC", 38.9072, -77.0369, "America/New_York")


def validate_location(data: object) -> Location:
    if not isinstance(data, dict):
        raise ValueError("City settings must be a JSON object.")
    name, timezone = data.get("name"), data.get("timezone")
    font = data.get("font", "sans")
    if font not in ("sans", "serif", "bitmap"):
        raise ValueError("Choose Sans-serif, Serif, or Classic bitmap.")
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
    return Location(name.strip(), coordinates[0], coordinates[1], timezone, font)


def display_name(name: str) -> str:
    label = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    if not label.strip():
        raise ValueError("This city needs an English display name for the dashboard.")
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


def checked_timezone(location: Location) -> str:
    data = timezone_bytes(location.timezone)
    # Kindle date implementations may ignore TZif paths; use the portable rules.
    footer = data.rsplit(b"\n", 2)
    if (
        data[:5] not in (b"TZif2", b"TZif3", b"TZif4")
        or len(footer) != 3 or footer[-1] or not footer[-2]
    ):
        raise ValueError(
            "Timezone " + location.timezone
            + " has no POSIX timezone rule. Install a current tzdata Python package."
        )
    ZoneInfo.from_file(io.BytesIO(data), key=location.timezone)
    return footer[-2].decode("ascii")


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


def detect_location(path: Path) -> Location:
    current = load_location(path)
    with tempfile.TemporaryFile() as response:
        try:
            result = subprocess.run(
                [
                    "curl", "-q", "-fsS", "--connect-timeout", "5", "--max-time", "12",
                    "--max-filesize", "16384", "https://ipwho.is/",
                ],
                stdout=response, stderr=subprocess.PIPE, timeout=15,
            )
        except subprocess.TimeoutExpired as error:
            raise ValueError("IP location HTTPS request timed out.") from error
        if result.returncode:
            detail = result.stderr.decode("utf-8", errors="replace").strip()
            raise ValueError(
                "IP location HTTPS request failed (curl exit " + str(result.returncode) + "): " + detail
            )
        response.seek(0)
        body = response.read(16385)
    if len(body) > 16384:
        raise ValueError("IP location service returned an oversized response.")
    data = json.loads(body)
    if not isinstance(data, dict) or data.get("success") is not True:
        raise ValueError("IP location lookup failed; check Wi-Fi or try again later.")
    timezone = data.get("timezone")
    if not isinstance(timezone, dict):
        raise ValueError("IP location service did not return a timezone.")
    return save_location(path, {
        "name": data.get("city"),
        "latitude": data.get("latitude"),
        "longitude": data.get("longitude"),
        "timezone": timezone.get("id"),
        "font": current.font,
    })


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
    (state / "timezone").write_text(zone + "\n", encoding="ascii")
    (state / "font").write_text(location.font + "\n", encoding="ascii")
    (state / "location").write_text(
        display_name(location.name) + "\n"
        + "https://api.open-meteo.com/v1/forecast?" + query + "\n",
        encoding="ascii",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--prepare", type=Path, metavar="STATE_DIRECTORY")
    mode.add_argument("--detect-location", action="store_true")
    mode.add_argument("--font", choices=("sans", "serif", "bitmap"))
    arguments = parser.parse_args()
    try:
        if (arguments.detect_location or arguments.font) and STATE.exists():
            raise ValueError("Stop the dashboard before changing settings.")
        if arguments.prepare:
            prepare_location(SETTINGS, arguments.prepare)
        elif arguments.check:
            checked_timezone(DEFAULT)
        elif arguments.detect_location:
            print("MyDashboard: detecting approximate city via ipwho.is (public IP shared).", flush=True)
            location = detect_location(SETTINGS)
            print(
                "MyDashboard: saved IP-detected city: " + display_name(location.name)
                + " (" + location.timezone + ").",
                flush=True,
            )
        elif arguments.font:
            current = load_location(SETTINGS)
            save_location(SETTINGS, dict(asdict(current), font=arguments.font))
            print(
                "MyDashboard: saved font: " + arguments.font + ".",
                flush=True,
            )
    except (OSError, ValueError, UnicodeError) as error:
        sys.exit("MyDashboard: " + str(error))


if __name__ == "__main__":
    main()
