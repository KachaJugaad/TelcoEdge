"""Tests for tools/lineage_audit.py"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
TOOL = ROOT / "tools" / "lineage_audit.py"


def _run_tool(data_dir):
    return subprocess.run(
        [sys.executable, str(TOOL), str(data_dir)],
        capture_output=True, text=True, cwd=str(ROOT),
    )


class TestLineageAudit:
    def test_empty_dir_passes(self):
        with tempfile.TemporaryDirectory() as d:
            result = _run_tool(d)
            assert result.returncode == 0
            assert "PASS" in result.stdout

    def test_nonexistent_dir_passes(self):
        result = _run_tool("/tmp/canedge_nonexistent_test_dir")
        assert result.returncode == 0
        assert "PASS" in result.stdout

    def test_file_with_lineage_passes(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "sample.csv").write_text("data")
            Path(d, "sample.csv.lineage.json").write_text(json.dumps({
                "source": "measured", "date": "2026-03-13",
                "terrain_type": "prairie", "weather_condition": "clear",
                "operator": "test", "telco_partner_consent": "N/A",
            }))
            result = _run_tool(d)
            assert result.returncode == 0
            assert "PASS" in result.stdout

    def test_file_without_lineage_fails(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "sample.csv").write_text("data")
            result = _run_tool(d)
            assert result.returncode == 1
            assert "FAIL" in result.stdout
            assert "sample.csv" in result.stdout

    def test_quarantine_dir_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            q = Path(d, "quarantine")
            q.mkdir()
            Path(q, "unlabelled.csv").write_text("data")
            result = _run_tool(d)
            assert result.returncode == 0
            assert "PASS" in result.stdout
