"""Tests for tools/spec_version_check.py"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
TOOL = ROOT / "tools" / "spec_version_check.py"
VERSIONS_LOCK = ROOT / "specs" / "versions.lock"

VALID_CONTENT = """\
osc_xapp_sdk: j-release-2025
sionna: 0.18.0
oran_e2sm_kpm: v3.0
oran_e2sm_rc: v1.03
3gpp_ntn_spec: TR38.821-Rel18
env_canada_api: MSC-GeoMet-OGC-anonymous
python: '3.11'
docker: '24.0'
"""


def _run_tool():
    return subprocess.run(
        [sys.executable, str(TOOL)],
        capture_output=True, text=True, cwd=str(ROOT),
    )


class TestSpecVersionCheck:
    def setup_method(self):
        self._original = VERSIONS_LOCK.read_text() if VERSIONS_LOCK.exists() else None

    def teardown_method(self):
        if self._original is not None:
            VERSIONS_LOCK.write_text(self._original)
        elif VERSIONS_LOCK.exists():
            VERSIONS_LOCK.unlink()

    def test_valid_versions_lock_passes(self):
        VERSIONS_LOCK.parent.mkdir(parents=True, exist_ok=True)
        VERSIONS_LOCK.write_text(VALID_CONTENT)
        result = _run_tool()
        assert result.returncode == 0
        assert "PASS" in result.stdout

    def test_missing_file_fails(self):
        if VERSIONS_LOCK.exists():
            VERSIONS_LOCK.unlink()
        result = _run_tool()
        assert result.returncode == 1
        assert "FAIL" in result.stdout

    def test_missing_key_fails(self):
        VERSIONS_LOCK.parent.mkdir(parents=True, exist_ok=True)
        VERSIONS_LOCK.write_text("osc_xapp_sdk: j-release-2025\nsionna: 0.18.0\n")
        result = _run_tool()
        assert result.returncode == 1
        assert "FAIL" in result.stdout
        assert "missing" in result.stdout
