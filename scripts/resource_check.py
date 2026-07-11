#!/usr/bin/env python3
"""
resource_check.py — Effortless lag / orphan / resource snapshot.

Same as status_report.py (resources + orphans included). Prefer either name.

Usage:
  python -u scripts/resource_check.py
  python -u scripts/resource_check.py --reap-orphans
  python -u scripts/resource_check.py --json
"""
from __future__ import annotations

import runpy
import sys
from pathlib import Path

if __name__ == "__main__":
    target = Path(__file__).resolve().parent / "status_report.py"
    sys.argv[0] = str(target)
    runpy.run_path(str(target), run_name="__main__")
