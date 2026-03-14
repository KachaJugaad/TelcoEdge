#!/usr/bin/env python3
"""Monitor tool: check NTN satellite coverage data freshness (Rule R-6).

Reads .canedge/ntn_last_update.json for a timestamp.
If age > 30 minutes: FAIL — revert to terrestrial-only mode.
If file missing: PASS with note (NTN not yet integrated).

Standalone: python tools/ntn_coverage_freshness.py
Exit 0 = PASS, Exit 1 = FAIL
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

NTN_STATUS_FILE = Path(__file__).resolve().parent.parent / ".canedge" / "ntn_last_update.json"
MAX_AGE_MINUTES = 30


def main():
    if not NTN_STATUS_FILE.exists():
        print("PASS: .canedge/ntn_last_update.json not found — NTN not yet integrated (stub OK)")
        sys.exit(0)

    try:
        with open(NTN_STATUS_FILE) as f:
            data = json.load(f)
    except json.JSONDecodeError:
        print("FAIL: .canedge/ntn_last_update.json is not valid JSON")
        sys.exit(1)

    ts_str = data.get("last_update")
    if not ts_str:
        print("FAIL: ntn_last_update.json missing 'last_update' field")
        sys.exit(1)

    try:
        last_update = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    except ValueError:
        print(f"FAIL: cannot parse timestamp '{ts_str}' — expected ISO8601")
        sys.exit(1)

    now = datetime.now(timezone.utc)
    age_minutes = (now - last_update).total_seconds() / 60

    if age_minutes > MAX_AGE_MINUTES:
        print(f"FAIL: NTN coverage data is {age_minutes:.0f} min old (max {MAX_AGE_MINUTES} min)")
        print("Action: revert to terrestrial-only mode, alert human, log incident")
        sys.exit(1)

    print(f"PASS: NTN coverage data age={age_minutes:.0f} min (max {MAX_AGE_MINUTES} min)")
    sys.exit(0)


if __name__ == "__main__":
    main()
