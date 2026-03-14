"""Tests for tools/budget_check.py"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
TOOL = ROOT / "tools" / "budget_check.py"
COST_LOG = ROOT / ".canedge" / "cost_log.json"


def _run_tool():
    result = subprocess.run(
        [sys.executable, str(TOOL)],
        capture_output=True, text=True, cwd=str(ROOT),
    )
    return result


def _write_cost_log(entries):
    COST_LOG.parent.mkdir(parents=True, exist_ok=True)
    COST_LOG.write_text(json.dumps(entries))


def _backup_and_restore():
    """Return original content for teardown."""
    if COST_LOG.exists():
        return COST_LOG.read_text()
    return None


class TestBudgetCheck:
    def setup_method(self):
        self._original = _backup_and_restore()

    def teardown_method(self):
        if self._original is not None:
            COST_LOG.write_text(self._original)
        elif COST_LOG.exists():
            COST_LOG.write_text("[]")

    def test_empty_log_passes(self):
        _write_cost_log([])
        result = _run_tool()
        assert result.returncode == 0
        assert "PASS" in result.stdout

    def test_under_budget_passes(self):
        _write_cost_log([{"tokens": 10000, "gpu_hours": 2.0, "timestamp": "2026-03-13T00:00:00"}])
        result = _run_tool()
        assert result.returncode == 0
        assert "PASS" in result.stdout

    def test_over_token_cap_fails(self):
        _write_cost_log([{"tokens": 55000, "gpu_hours": 0, "timestamp": "2026-03-13T00:00:00"}])
        result = _run_tool()
        assert result.returncode == 1
        assert "FAIL" in result.stdout

    def test_warn_on_high_tokens(self):
        _write_cost_log([{"tokens": 36000, "gpu_hours": 0, "timestamp": "2026-03-13T00:00:00"}])
        result = _run_tool()
        assert result.returncode == 0
        assert "WARN" in result.stdout

    def test_invalid_json_fails(self):
        COST_LOG.write_text("{bad json")
        result = _run_tool()
        assert result.returncode == 1
        assert "FAIL" in result.stdout
