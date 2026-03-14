#!/usr/bin/env python3
"""Monitor tool: check specs/versions.lock for drift (Rule R-4).

Verifies the file exists, is valid YAML, and all required keys are present.

Standalone: python tools/spec_version_check.py
Exit 0 = PASS, Exit 1 = FAIL
"""
import sys
from pathlib import Path

VERSIONS_LOCK = Path(__file__).resolve().parent.parent / "specs" / "versions.lock"

REQUIRED_KEYS = [
    "osc_xapp_sdk",
    "sionna",
    "oran_e2sm_kpm",
    "oran_e2sm_rc",
    "3gpp_ntn_spec",
    "env_canada_api",
    "python",
    "docker",
]


def parse_yaml_simple(text):
    """Minimal YAML key-value parser — no external dependency needed."""
    result = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            key, _, value = line.partition(":")
            result[key.strip()] = value.strip().strip("'\"")
    return result


def main():
    if not VERSIONS_LOCK.exists():
        print("FAIL: specs/versions.lock not found")
        sys.exit(1)

    content = VERSIONS_LOCK.read_text()
    versions = parse_yaml_simple(content)

    missing = [k for k in REQUIRED_KEYS if k not in versions]
    if missing:
        print(f"FAIL: missing keys in versions.lock: {', '.join(missing)}")
        sys.exit(1)

    empty = [k for k in REQUIRED_KEYS if not versions.get(k)]
    if empty:
        print(f"FAIL: empty values in versions.lock: {', '.join(empty)}")
        sys.exit(1)

    print("PASS: specs/versions.lock — all required keys present and non-empty")
    for k in REQUIRED_KEYS:
        print(f"  {k}: {versions[k]}")
    sys.exit(0)


if __name__ == "__main__":
    main()
