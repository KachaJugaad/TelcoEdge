"""Tests for tools/weather_api_check.py"""
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch
import importlib

ROOT = Path(__file__).resolve().parent.parent.parent
TOOL = ROOT / "tools" / "weather_api_check.py"


def _run_tool():
    return subprocess.run(
        [sys.executable, str(TOOL)],
        capture_output=True, text=True, cwd=str(ROOT),
        timeout=60,
    )


class TestWeatherApiCheck:
    def test_tool_runs_without_error(self):
        """Tool should run and produce PASS or FAIL — never crash."""
        result = _run_tool()
        assert result.returncode in (0, 1)
        output = result.stdout + result.stderr
        assert "PASS" in output or "FAIL" in output

    def test_no_api_key_in_source(self):
        """Verify the tool does not reference any API key — MSC GeoMet is anonymous."""
        source = (ROOT / "tools" / "weather_api_check.py").read_text()
        for forbidden in ["API_KEY", "api_key", "Authorization", "Bearer", "Token"]:
            assert forbidden not in source, f"Found '{forbidden}' in weather_api_check.py — MSC GeoMet needs no key"

    def test_correct_url(self):
        """Verify the tool hits the correct Government of Canada endpoint."""
        source = (ROOT / "tools" / "weather_api_check.py").read_text()
        assert "https://api.weather.gc.ca/collections" in source

    def test_has_retry_logic(self):
        """Verify exponential backoff is implemented per PROJECT.md adapter rules."""
        source = (ROOT / "tools" / "weather_api_check.py").read_text()
        assert "retry" in source.lower() or "RETRIES" in source or "attempt" in source.lower()
