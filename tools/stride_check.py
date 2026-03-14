#!/usr/bin/env python3
"""Monitor tool: check defence-scope files have STRIDE models (Rule R-7).

Lists any file in src/defence/ that does not have a matching
docs/security/stride_{module}_{date}.md file.

Standalone: python tools/stride_check.py
Exit 0 = PASS, Exit 1 = FAIL
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFENCE_DIR = ROOT / "src" / "defence"
SECURITY_DIR = ROOT / "docs" / "security"

SKIP_FILES = {"__init__.py", "README.md", ".gitkeep", "__pycache__"}


def main():
    if not DEFENCE_DIR.exists():
        print("PASS: src/defence/ does not exist yet — nothing to check")
        sys.exit(0)

    defence_files = [
        f for f in DEFENCE_DIR.rglob("*.py")
        if f.name not in SKIP_FILES
    ]

    if not defence_files:
        print("PASS: no defence-scope Python files found — nothing to check")
        sys.exit(0)

    # Collect all STRIDE model filenames
    stride_models = set()
    if SECURITY_DIR.exists():
        for s in SECURITY_DIR.glob("stride_*.md"):
            stride_models.add(s.stem)  # e.g. "stride_auth_module_2026-03-13"

    uncovered = []
    for f in defence_files:
        module_name = f.stem  # e.g. "auth_module"
        # Check if any stride model contains this module name
        has_model = any(module_name in model_name for model_name in stride_models)
        if not has_model:
            uncovered.append(str(f.relative_to(ROOT)))

    if uncovered:
        print(f"FAIL: {len(uncovered)} defence file(s) without STRIDE model:")
        for u in uncovered:
            print(f"  → {u} — needs docs/security/stride_{{module}}_{{date}}.md")
        sys.exit(1)

    print(f"PASS: all {len(defence_files)} defence file(s) have STRIDE models")
    sys.exit(0)


if __name__ == "__main__":
    main()
