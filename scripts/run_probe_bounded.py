#!/usr/bin/env python3
"""
run_probe_bounded.py — Manual / smoke probe with hard timeout (no orphans).

Use this instead of bare `python -u grok_supervised_12_probe.py` for offline tests.
Kills the process after timeout or after contract summary + finalize grace.

Usage:
  python -u scripts/run_probe_bounded.py --cycles 2
  python -u scripts/run_probe_bounded.py --cycles 2 --timeout-s 660
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def main() -> int:
    ap = argparse.ArgumentParser(description="Bounded cycle-runner smoke test (reaps process)")
    ap.add_argument("--cycles", type=int, default=2)
    ap.add_argument("--timeout-s", type=int, default=0, help="0 = formula 300+180*cycles capped")
    args = ap.parse_args()
    os.chdir(ROOT)

    cycles = max(1, int(args.cycles))
    timeout = args.timeout_s or int(min(2400, max(600, 300 + 180 * cycles)))
    env = os.environ.copy()
    env["AETHERIA_NUM_CYCLES"] = str(cycles)
    env["NUM_CYCLES"] = str(cycles)
    env.setdefault("AETHERIA_LIGHT_MANAGE", "1")
    env.setdefault("AETHERIA_SKIP_FINAL_RECON", "1")
    env.setdefault("AETHERIA_META_RECON", "0")

    contract = ROOT / "measurements" / "lh_probe_summary_latest.json"
    try:
        if contract.exists():
            contract.unlink()
    except Exception:
        pass

    log = ROOT / "logs" / f"bounded_probe_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    log.parent.mkdir(exist_ok=True)
    probe = ROOT / "grok_supervised_12_probe.py"
    print(f"[bounded] cycles={cycles} timeout={timeout}s log={log}", flush=True)

    with log.open("w", encoding="utf-8") as lf:
        p = subprocess.Popen(
            [sys.executable, "-u", str(probe)],
            cwd=str(ROOT),
            stdout=lf,
            stderr=subprocess.STDOUT,
            env=env,
        )
        deadline = time.time() + timeout
        rc = None
        while time.time() < deadline:
            if p.poll() is not None:
                rc = p.returncode
                break
            if contract.exists():
                try:
                    c = json.loads(contract.read_text(encoding="utf-8"))
                    if c.get("ok") and int(c.get("cycles_complete") or 0) >= cycles:
                        # grace then kill finalize hang
                        fin = time.time() + 45
                        while time.time() < fin and p.poll() is None:
                            time.sleep(2)
                        if p.poll() is None:
                            print(f"[bounded] contract ok — terminating finalize pid={p.pid}", flush=True)
                            p.terminate()
                            try:
                                p.wait(timeout=15)
                            except Exception:
                                p.kill()
                            rc = 0
                        else:
                            rc = p.returncode
                        break
                except Exception:
                    pass
            time.sleep(2)
        else:
            if p.poll() is None:
                print(f"[bounded] TIMEOUT — kill pid={p.pid}", flush=True)
                p.kill()
                try:
                    p.wait(timeout=10)
                except Exception:
                    pass
                rc = -9

    # Ensure process gone
    if p.poll() is None:
        p.kill()

    summary = {
        "schema": "bounded_probe_run_v1",
        "ts": utc(),
        "cycles": cycles,
        "timeout_s": timeout,
        "exit_code": rc,
        "log": str(log),
        "contract": None,
    }
    if contract.exists():
        try:
            summary["contract"] = json.loads(contract.read_text(encoding="utf-8"))
        except Exception:
            pass
    out = ROOT / "measurements" / "bounded_probe_latest.json"
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)
    ok = rc in (0, None) and (summary.get("contract") or {}).get("ok") is True
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
