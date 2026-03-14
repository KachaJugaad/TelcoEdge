#!/usr/bin/env python3
"""Monitor tool: check compute budget caps from Rule R-5.

Reads .canedge/cost_log.json and checks:
  - tokens_used < 35,000 (warn) / 50,000 (fail)
  - GPU_hours_this_week < 15 (warn) / 20 (fail)

Standalone: python tools/budget_check.py
Exit 0 = PASS, Exit 1 = FAIL
"""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

COST_LOG = Path(__file__).resolve().parent.parent / ".canedge" / "cost_log.json"

TOKEN_WARN = 35_000
TOKEN_CAP = 50_000
GPU_WARN = 15
GPU_CAP = 20


def load_cost_log():
    if not COST_LOG.exists():
        print("FAIL: .canedge/cost_log.json not found")
        sys.exit(1)
    try:
        with open(COST_LOG) as f:
            return json.load(f)
    except json.JSONDecodeError:
        print("FAIL: .canedge/cost_log.json is not valid JSON")
        sys.exit(1)


def check_budget(entries):
    total_tokens = 0
    gpu_hours_week = 0.0
    week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

    warnings = []
    for entry in entries:
        total_tokens += entry.get("tokens", 0)
        ts = entry.get("timestamp", "")
        if ts >= week_ago:
            gpu_hours_week += entry.get("gpu_hours", 0.0)

    if total_tokens >= TOKEN_CAP:
        print(f"FAIL: tokens_used={total_tokens} exceeds cap {TOKEN_CAP}")
        return False
    if gpu_hours_week >= GPU_CAP:
        print(f"FAIL: GPU_hours_this_week={gpu_hours_week:.1f} exceeds cap {GPU_CAP}")
        return False
    if total_tokens >= TOKEN_WARN:
        warnings.append(f"WARN: tokens_used={total_tokens} approaching cap {TOKEN_CAP}")
    if gpu_hours_week >= GPU_WARN:
        warnings.append(f"WARN: GPU_hours_this_week={gpu_hours_week:.1f} approaching cap {GPU_CAP}")

    for w in warnings:
        print(w)

    print(f"PASS: tokens={total_tokens}/{TOKEN_CAP}, GPU_hrs_week={gpu_hours_week:.1f}/{GPU_CAP}")
    return True


def main():
    entries = load_cost_log()
    if not isinstance(entries, list):
        print("FAIL: cost_log.json must be a JSON array")
        sys.exit(1)
    ok = check_budget(entries)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
