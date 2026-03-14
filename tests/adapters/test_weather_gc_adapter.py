"""Tests for src/adapters/weather_gc_adapter.py

Uses unittest.mock to mock HTTP responses — does NOT call live API in tests.
Validates: adapter parsing, retry logic, logging, no API key usage.
"""
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from http.client import HTTPResponse
from io import BytesIO

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "src"))

from adapters.weather_gc_adapter import (
    WeatherGCAdapter,
    WeatherObservation,
    WeatherAPIError,
    BASE_URL,
    COLLECTION,
)


MOCK_GEOJSON = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [-106.5, 52.1]},
            "properties": {
                "datetime": "2026-03-13T12:00:00Z",
                "station_name": "Saskatoon",
                "aqhi": 3.0,
                "value": 7.5,
            },
        },
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [-104.6, 50.4]},
            "properties": {
                "datetime": "2026-03-13T12:00:00Z",
                "station_name": "Regina",
                "aqhi": 2.0,
                "value": 2.0,
            },
        },
    ],
}


def _mock_urlopen(data_dict, status=200):
    """Create a mock for urllib.request.urlopen that returns JSON data."""
    body = json.dumps(data_dict).encode("utf-8")
    mock_resp = MagicMock()
    mock_resp.read.return_value = body
    mock_resp.getcode.return_value = status
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


class TestAdapterParsing:
    """Test that adapter correctly parses GeoJSON responses."""

    @patch("adapters.weather_gc_adapter.urllib.request.urlopen")
    def test_parse_features(self, mock_url):
        mock_url.return_value = _mock_urlopen(MOCK_GEOJSON)
        with tempfile.TemporaryDirectory() as log_dir:
            adapter = WeatherGCAdapter(log_dir=Path(log_dir))
            obs = adapter.get_weather(bbox=(-110, 49, -101, 55))
        assert len(obs) == 2
        assert isinstance(obs[0], WeatherObservation)

    @patch("adapters.weather_gc_adapter.urllib.request.urlopen")
    def test_coordinates_parsed(self, mock_url):
        mock_url.return_value = _mock_urlopen(MOCK_GEOJSON)
        with tempfile.TemporaryDirectory() as log_dir:
            adapter = WeatherGCAdapter(log_dir=Path(log_dir))
            obs = adapter.get_weather(bbox=(-110, 49, -101, 55))
        assert obs[0].lon == -106.5
        assert obs[0].lat == 52.1

    @patch("adapters.weather_gc_adapter.urllib.request.urlopen")
    def test_station_name_parsed(self, mock_url):
        mock_url.return_value = _mock_urlopen(MOCK_GEOJSON)
        with tempfile.TemporaryDirectory() as log_dir:
            adapter = WeatherGCAdapter(log_dir=Path(log_dir))
            obs = adapter.get_weather(bbox=(-110, 49, -101, 55))
        assert obs[0].station_name == "Saskatoon"

    @patch("adapters.weather_gc_adapter.urllib.request.urlopen")
    def test_datetime_parsed(self, mock_url):
        mock_url.return_value = _mock_urlopen(MOCK_GEOJSON)
        with tempfile.TemporaryDirectory() as log_dir:
            adapter = WeatherGCAdapter(log_dir=Path(log_dir))
            obs = adapter.get_weather(bbox=(-110, 49, -101, 55))
        assert obs[0].observed_at == "2026-03-13T12:00:00Z"

    @patch("adapters.weather_gc_adapter.urllib.request.urlopen")
    def test_empty_features(self, mock_url):
        mock_url.return_value = _mock_urlopen({"type": "FeatureCollection", "features": []})
        with tempfile.TemporaryDirectory() as log_dir:
            adapter = WeatherGCAdapter(log_dir=Path(log_dir))
            obs = adapter.get_weather(bbox=(-110, 49, -101, 55))
        assert obs == []


class TestNoAPIKey:
    """Verify adapter never uses API keys — MSC GeoMet is anonymous."""

    def test_no_api_key_in_source(self):
        source = (ROOT / "src" / "adapters" / "weather_gc_adapter.py").read_text()
        for forbidden in ["API_KEY", "api_key", "Bearer", "Token"]:
            assert forbidden not in source, f"Found '{forbidden}' — MSC GeoMet needs no key"

    def test_no_auth_header_set(self):
        """Adapter must never set an Authorization header in code (comments OK)."""
        source = (ROOT / "src" / "adapters" / "weather_gc_adapter.py").read_text()
        # Check that no code line sets an Authorization header
        for line in source.splitlines():
            stripped = line.lstrip()
            if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'"):
                continue  # skip comments and docstrings
            assert "add_header" not in stripped or "Authorization" not in stripped, \
                f"Found Authorization header being set: {stripped}"

    @patch("adapters.weather_gc_adapter.urllib.request.urlopen")
    def test_request_has_no_auth(self, mock_url):
        mock_url.return_value = _mock_urlopen(MOCK_GEOJSON)
        with tempfile.TemporaryDirectory() as log_dir:
            adapter = WeatherGCAdapter(log_dir=Path(log_dir))
            adapter.get_weather(bbox=(-110, 49, -101, 55))
        # Check the Request object passed to urlopen
        req = mock_url.call_args[0][0]
        assert req.get_header("Authorization") is None


class TestCorrectURL:
    """Verify adapter hits the right endpoint."""

    @patch("adapters.weather_gc_adapter.urllib.request.urlopen")
    def test_url_format(self, mock_url):
        mock_url.return_value = _mock_urlopen(MOCK_GEOJSON)
        with tempfile.TemporaryDirectory() as log_dir:
            adapter = WeatherGCAdapter(log_dir=Path(log_dir))
            adapter.get_weather(bbox=(-110, 49, -101, 55))
        req = mock_url.call_args[0][0]
        url = req.full_url
        assert "api.weather.gc.ca" in url
        assert "aqhi-observations-realtime" in url
        assert "bbox=-110,49,-101,55" in url


class TestRetryLogic:
    """Verify 3-second exponential backoff on 429/5xx."""

    @patch("adapters.weather_gc_adapter.time.sleep")
    @patch("adapters.weather_gc_adapter.urllib.request.urlopen")
    def test_retries_on_503(self, mock_url, mock_sleep):
        import urllib.error
        error_resp = MagicMock()
        error_resp.read.return_value = b""
        mock_url.side_effect = [
            urllib.error.HTTPError(url="", code=503, msg="", hdrs=None, fp=BytesIO(b"")),
            urllib.error.HTTPError(url="", code=503, msg="", hdrs=None, fp=BytesIO(b"")),
            _mock_urlopen(MOCK_GEOJSON),
        ]
        with tempfile.TemporaryDirectory() as log_dir:
            adapter = WeatherGCAdapter(log_dir=Path(log_dir))
            obs = adapter.get_weather(bbox=(-110, 49, -101, 55))
        assert len(obs) == 2
        assert mock_sleep.call_count == 2  # 2 retries with backoff

    @patch("adapters.weather_gc_adapter.time.sleep")
    @patch("adapters.weather_gc_adapter.urllib.request.urlopen")
    def test_raises_after_max_retries(self, mock_url, mock_sleep):
        import urllib.error
        mock_url.side_effect = urllib.error.HTTPError(
            url="", code=503, msg="", hdrs=None, fp=BytesIO(b"")
        )
        with tempfile.TemporaryDirectory() as log_dir:
            adapter = WeatherGCAdapter(log_dir=Path(log_dir))
            with pytest.raises(WeatherAPIError):
                adapter.get_weather(bbox=(-110, 49, -101, 55))


class TestAPICallLogging:
    """Verify every call is logged to data/api_logs/ (Rule R-3)."""

    @patch("adapters.weather_gc_adapter.urllib.request.urlopen")
    def test_log_file_created(self, mock_url):
        mock_url.return_value = _mock_urlopen(MOCK_GEOJSON)
        with tempfile.TemporaryDirectory() as log_dir:
            log_path = Path(log_dir)
            adapter = WeatherGCAdapter(log_dir=log_path)
            adapter.get_weather(bbox=(-110, 49, -101, 55))
            logs = list(log_path.glob("weather_gc_*.json"))
            assert len(logs) == 1

    @patch("adapters.weather_gc_adapter.urllib.request.urlopen")
    def test_log_content(self, mock_url):
        mock_url.return_value = _mock_urlopen(MOCK_GEOJSON)
        with tempfile.TemporaryDirectory() as log_dir:
            log_path = Path(log_dir)
            adapter = WeatherGCAdapter(log_dir=log_path)
            adapter.get_weather(bbox=(-110, 49, -101, 55))
            log_file = list(log_path.glob("weather_gc_*.json"))[0]
            log_data = json.loads(log_file.read_text())
            assert log_data["auth"] == "none"
            assert log_data["service"] == "MSC-GeoMet-OGC-anonymous"
            assert log_data["n_features"] == 2
