#!/usr/bin/env python3
"""Monitor tool: check data lineage (Rule R-8).

Scans a directory for data files missing a .lineage.json sidecar.
Unlabelled files should be moved to data/quarantine/.

Standalone: python tools/lineage_audit.py data/
Exit 0 = PASS, Exit 1 = FAIL
"""
import sys
from pathlib import Path

SKIP_DIRS = {"quarantine", "api_logs", "__pycache__"}
SKIP_EXTENSIONS = {".lineage.json"}
SKIP_FILES = {"README.md", ".gitkeep", ".gitignore"}


def audit(data_dir):
    data_path = Path(data_dir).resolve()
    if not data_path.exists():
        print(f"PASS: {data_dir} does not exist yet — nothing to audit")
        return True

    missing = []
    for f in data_path.rglob("*"):
        if not f.is_file():
            continue
        # Skip files in excluded directories
        if any(part in SKIP_DIRS for part in f.relative_to(data_path).parts):
            continue
        # Skip lineage files themselves
        if f.name.endswith(".lineage.json"):
            continue
        # Skip non-data files
        if f.name in SKIP_FILES:
            continue

        lineage = f.parent / f"{f.name}.lineage.json"
        if not lineage.exists():
            missing.append(str(f.relative_to(data_path)))

    if missing:
        print(f"FAIL: {len(missing)} file(s) missing .lineage.json sidecar:")
        for m in missing:
            print(f"  → {m}")
        print("Action: move unlabelled files to data/quarantine/")
        return False

    print("PASS: all data files have .lineage.json sidecars")
    return True


def main():
    data_dir = sys.argv[1] if len(sys.argv) > 1 else "data/"
    ok = audit(data_dir)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
