"""Tests for tools/stride_check.py"""
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
TOOL = ROOT / "tools" / "stride_check.py"


def _run_tool():
    return subprocess.run(
        [sys.executable, str(TOOL)],
        capture_output=True, text=True, cwd=str(ROOT),
    )


class TestStrideCheck:
    def test_no_defence_files_passes(self):
        """With no .py files in src/defence/ (just __init__.py), should pass."""
        result = _run_tool()
        assert result.returncode == 0
        assert "PASS" in result.stdout

    def test_defence_file_without_stride_fails(self):
        """A defence .py file without a STRIDE model should fail."""
        defence_dir = ROOT / "src" / "defence"
        test_file = defence_dir / "test_uncovered_module.py"
        try:
            defence_dir.mkdir(parents=True, exist_ok=True)
            test_file.write_text("# defence module without STRIDE model")
            result = _run_tool()
            assert result.returncode == 1
            assert "FAIL" in result.stdout
            assert "test_uncovered_module" in result.stdout
        finally:
            if test_file.exists():
                test_file.unlink()

    def test_defence_file_with_stride_passes(self):
        """A defence .py file with a matching STRIDE model should pass."""
        defence_dir = ROOT / "src" / "defence"
        security_dir = ROOT / "docs" / "security"
        test_file = defence_dir / "auth_gate.py"
        stride_file = security_dir / "stride_auth_gate_2026-03-13.md"
        try:
            defence_dir.mkdir(parents=True, exist_ok=True)
            security_dir.mkdir(parents=True, exist_ok=True)
            test_file.write_text("# auth gate module")
            stride_file.write_text("# STRIDE model for auth_gate")
            result = _run_tool()
            assert result.returncode == 0
            assert "PASS" in result.stdout
        finally:
            if test_file.exists():
                test_file.unlink()
            if stride_file.exists():
                stride_file.unlink()
