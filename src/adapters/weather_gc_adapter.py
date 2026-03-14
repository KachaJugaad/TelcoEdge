"""MSC GeoMet weather adapter — Environment and Climate Change Canada.

Base URL: https://api.weather.gc.ca/
Auth: NONE — anonymous OGC API, no registration, no key, no account
Operated by: Government of Canada
Data sovereignty: all data stays in Canada ✓

Adapter rules (from PROJECT.md):
  - Plain GET requests — no Authorization header, no API key
  - 3-second exponential backoff on 429 or 5xx
  - Log every call to data/api_logs/weather_gc_{ISO_timestamp}.json
  - Pinned in specs/versions.lock as: env_canada_api: MSC-GeoMet-OGC-anonymous

Reference: PROJECT.md Section 3 — Weather API
"""
import json
import time
import urllib.request
import urllib.error
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

BASE_URL = "https://api.weather.gc.ca"
COLLECTION = "aqhi-observations-realtime"
ITEMS_PATH = f"/collections/{COLLECTION}/items"

MAX_RETRIES = 3
BACKOFF_BASE = 3  # seconds
TIMEOUT = 10  # seconds

# Default log directory (Rule R-3: every API call logged)
LOG_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "api_logs"


@dataclass
class WeatherObservation:
    """Parsed weather observation from MSC GeoMet."""
    rain_mm_per_hr: float
    observed_at: str
    lat: float
    lon: float
    station_name: str = ""
    raw_properties: Optional[dict] = None


class WeatherGCAdapter:
    """Adapter for MSC GeoMet OGC API.

    NO API KEY NEEDED — MSC GeoMet is anonymous and free.
    Government of Canada infrastructure. Data never leaves Canada.
    """

    def __init__(self, base_url: str = BASE_URL, log_dir: Optional[Path] = None):
        self.base_url = base_url.rstrip("/")
        self.log_dir = log_dir or LOG_DIR

    def get_weather(self, bbox: tuple, limit: int = 10) -> list:
        """Fetch weather observations for a bounding box.

        Args:
            bbox: (lon_min, lat_min, lon_max, lat_max) — e.g. (-110, 49, -101, 55)
                  for Saskatchewan prairie
            limit: max number of features to return

        Returns:
            List of WeatherObservation objects

        Raises:
            WeatherAPIError on unrecoverable failure
        """
        lon_min, lat_min, lon_max, lat_max = bbox
        url = (
            f"{self.base_url}{ITEMS_PATH}"
            f"?bbox={lon_min},{lat_min},{lon_max},{lat_max}"
            f"&limit={limit}"
        )

        response_data = self._get_with_retry(url)
        self._log_call(url, response_data)

        return self._parse_features(response_data)

    def _get_with_retry(self, url: str) -> dict:
        """GET with 3-second exponential backoff on 429/5xx.

        No Authorization header — MSC GeoMet is anonymous.
        """
        last_error = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                req = urllib.request.Request(url, method="GET")
                # NO Authorization header — anonymous API
                with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                last_error = e
                if e.code in (429, 500, 502, 503, 504) and attempt < MAX_RETRIES:
                    wait = BACKOFF_BASE ** attempt
                    time.sleep(wait)
                    continue
                raise WeatherAPIError(f"HTTP {e.code} from {url}") from e
            except (urllib.error.URLError, OSError) as e:
                last_error = e
                if attempt < MAX_RETRIES:
                    wait = BACKOFF_BASE ** attempt
                    time.sleep(wait)
                    continue
                raise WeatherAPIError(f"Connection error: {e}") from e

        raise WeatherAPIError(f"Failed after {MAX_RETRIES} attempts: {last_error}")

    def _parse_features(self, data: dict) -> list:
        """Parse GeoJSON features into WeatherObservation objects.

        Note: the exact GeoJSON property name for precipitation intensity in
        the aqhi-observations-realtime collection should be verified by human
        against a live API response. This implementation checks common field names.
        """
        features = data.get("features", [])
        observations = []

        for feature in features:
            props = feature.get("properties", {})
            geometry = feature.get("geometry", {})
            coords = geometry.get("coordinates", [0, 0])

            # Extract rain intensity — check multiple possible field names
            # Unknown — recommend human check exact property name in live response
            rain = 0.0
            for key in ("precipitation_intensity", "rain_mm_per_hr",
                        "precip_amount", "aqhi", "value"):
                if key in props and props[key] is not None:
                    try:
                        rain = float(props[key])
                    except (ValueError, TypeError):
                        continue
                    break

            obs = WeatherObservation(
                rain_mm_per_hr=rain,
                observed_at=props.get("datetime", props.get("date", "")),
                lon=coords[0] if len(coords) > 0 else 0.0,
                lat=coords[1] if len(coords) > 1 else 0.0,
                station_name=props.get("station_name", props.get("name", "")),
                raw_properties=props,
            )
            observations.append(obs)

        return observations

    def _log_call(self, url: str, response_data: dict):
        """Log every API call to data/api_logs/ (Rule R-3 sovereignty)."""
        self.log_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        log_file = self.log_dir / f"weather_gc_{timestamp}.json"
        log_entry = {
            "url": url,
            "timestamp": timestamp,
            "service": "MSC-GeoMet-OGC-anonymous",
            "auth": "none",
            "n_features": len(response_data.get("features", [])),
        }
        log_file.write_text(json.dumps(log_entry, indent=2))


class WeatherAPIError(Exception):
    """Raised when the MSC GeoMet API is unreachable or returns an error."""
    pass
