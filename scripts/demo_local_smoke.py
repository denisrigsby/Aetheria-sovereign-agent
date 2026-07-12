#!/usr/bin/env python3
"""
Sanitized public demo smoke — control plane only.

No private living streams, no companion chat, no G4 train, no host secrets.
Does not start long-horizon plant unless you separately launch it in a full root.

Exit 0: smoke checks passed (or soft-warned as expected for clone-only).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def banner() -> None:
    print("=" * 60)
    print(" Aetheria public control-plane DEMO (sanitized)")
    print(" Repo: control plane only — private core not included")
    print(" Chat never parents the plant. Plant is opt-in full install.")
    print("=" * 60)


def check_python() -> bool:
    ok = sys.version_info >= (3, 10)
    print(f"[1] Python {sys.version.split()[0]}  ({'OK' if ok else 'NEED 3.10+'})")
    return ok


def check_layout() -> bool:
    need = [
        "scripts/long_horizon_supervisor.py",
        "scripts/lh_watchdog.py",
        "scripts/status_report.py",
        "measurements/lh_probe_summary.example.json",
        "docs/PUBLIC_DEMO.md",
        "README.md",
    ]
    missing = [p for p in need if not (ROOT / p).exists()]
    print(f"[2] Layout  missing={len(missing)}  ({'OK' if not missing else missing})")
    return not missing


def check_compile() -> bool:
    import compileall

    ok = compileall.compile_dir(str(ROOT / "scripts"), quiet=1)
    print(f"[3] compileall scripts/  ({'OK' if ok else 'FAIL'})")
    return bool(ok)


def check_examples() -> bool:
    paths = list((ROOT / "measurements").glob("*.example.json"))
    paths += list((ROOT / "measurements").glob("*.json"))
    loaded = 0
    for p in paths:
        if p.name == "STATUS_SNAPSHOT.json" or "example" in p.name:
            try:
                json.loads(p.read_text(encoding="utf-8"))
                loaded += 1
            except Exception as e:
                print(f"[4] example load FAIL {p.name}: {e}")
                return False
    print(f"[4] example JSON load  n={loaded}  (OK)")
    return loaded > 0


def check_status_import() -> None:
    """Soft: may fail on clone-only without full private root."""
    sys.path.insert(0, str(ROOT))
    try:
        # status_report may import private modules — catch and explain
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "status_report", ROOT / "scripts" / "status_report.py"
        )
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            try:
                spec.loader.exec_module(mod)
                print("[5] status_report import  (OK — full root likely present)")
            except Exception as e:
                print(
                    f"[5] status_report import soft-fail (expected on clone-only): "
                    f"{type(e).__name__}: {str(e)[:100]}"
                )
                print("    Overlay onto a full Aetheria root to run live plant status.")
    except Exception as e:
        print(f"[5] status probe skip: {e}")


def main() -> int:
    banner()
    print(f"Root: {ROOT}\n")
    ok = True
    ok = check_python() and ok
    ok = check_layout() and ok
    ok = check_compile() and ok
    ok = check_examples() and ok
    check_status_import()
    print()
    if ok:
        print("DEMO SMOKE PASS (sanitized control plane).")
        print("Next: docs/PUBLIC_DEMO.md · SETUP.md · optional full-root plant launch.")
        print("Never: treat chat as plant parent; never commit private living/G4 paths.")
        return 0
    print("DEMO SMOKE FAIL — fix layout/Python and re-run.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
