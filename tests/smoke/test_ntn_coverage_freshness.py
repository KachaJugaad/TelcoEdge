"""Tests for tools/ntn_coverage_freshness.py"""
import json
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
TOOL = ROOT / "tools" / "ntn_coverage_freshness.py"
NTN_FILE = ROOT / ".canedge" / "ntn_last_update.json"


def _run_tool():
    return subprocess.run(
        [sys.executable, str(TOOL)],
        capture_output=True, text=True, cwd=str(ROOT),
    )


class TestNtnCoverageFreshness:
    def setup_method(self):
        self._original = NTN_FILE.read_text() if NTN_FILE.exists() else None

    def teardown_method(self):
        if self._original is not None:
            NTN_FILE.write_text(self._original)
        elif NTN_FILE.exists():
            NTN_FILE.unlink()

    def test_missing_file_passes_stub(self):
        """No NTN integration yet — should pass as stub."""
        if NTN_FILE.exists():
            NTN_FILE.unlink()
        result = _run_tool()
        assert result.returncode == 0
        assert "PASS" in result.stdout

    def test_fresh_data_passes(self):
        now = datetime.now(timezone.utc).isoformat()
        NTN_FILE.write_text(json.dumps({"last_update": now}))
        result = _run_tool()
        assert result.returncode == 0
        assert "PASS" in result.stdout

    def test_stale_data_fails(self):
        old = (datetime.now(timezone.utc) - timedelta(minutes=45)).isoformat()
        NTN_FILE.write_text(json.dumps({"last_update": old}))
        result = _run_tool()
        assert result.returncode == 1
        assert "FAIL" in result.stdout

    def test_invalid_json_fails(self):
        NTN_FILE.write_text("{bad")
        result = _run_tool()
        assert result.returncode == 1
        assert "FAIL" in result.stdout

    def test_missing_field_fails(self):
        NTN_FILE.write_text(json.dumps({"source": "telesat"}))
        result = _run_tool()
        assert result.returncode == 1
        assert "FAIL" in result.stdout
