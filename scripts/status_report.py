#!/usr/bin/env python3
"""
status_report.py — One-screen sparse-operator status (read-only).

Does not start/stop processes, hygiene, hope probes, or residuals.

Usage:
  python -u scripts/status_report.py
  python -u scripts/status_report.py --json
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(p: Path, default=None):
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception as e:
        return {"_error": str(e)}


def pid_alive(pid) -> bool:
    if pid is None:
        return False
    try:
        pid = int(pid)
    except Exception:
        return False
    try:
        r = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        return str(pid) in (r.stdout or "")
    except Exception:
        return False


def read_pid(path: Path):
    if not path.exists():
        return None
    try:
        return int(path.read_text(encoding="utf-8").strip().splitlines()[0].strip())
    except Exception:
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description="Read-only Aetheria plant status")
    ap.add_argument("--json", action="store_true", help="machine-readable object")
    args = ap.parse_args()

    lh = load(ROOT / "measurements" / "long_horizon_state.json", {}) or {}
    hope = load(ROOT / "measurements" / "hope_status.json", {}) or {}
    gate = load(ROOT / "measurements" / "gate_v2_eval_latest.json", {}) or {}
    wd_st = load(ROOT / "measurements" / "watchdog_status.json", {}) or {}
    gm = load(ROOT / "measurements" / "guidance_momentum.json", {}) or {}
    ga = load(ROOT / "measurements" / "gate_a_progress.json", {}) or {}

    lh_pid = read_pid(ROOT / "measurements" / "long_horizon.pid") or lh.get("pid")
    wd_pid = read_pid(ROOT / "measurements" / "watchdog.pid")

    report = {
        "schema": "aetheria_status_report_v1",
        "long_horizon": {
            "pid": lh_pid,
            "alive": pid_alive(lh_pid),
            "tick": lh.get("tick"),
            "max_ticks": lh.get("max_ticks"),
            "status": lh.get("status"),
            "last_ok": lh.get("last_ok"),
            "mom": lh.get("persisted_mom") or lh.get("last_final_mom") or gm.get("guidance_momentum"),
            "interval_min": lh.get("interval_min"),
            "heartbeat_at": lh.get("heartbeat_at"),
            "last_tick_finished": lh.get("last_tick_finished"),
            "started_at": lh.get("started_at"),
        },
        "watchdog": {
            "pid": wd_pid,
            "alive": pid_alive(wd_pid) if wd_pid else False,
            "last_action": (wd_st.get("diag") or {}).get("action") or (wd_st.get("last_applied") or {}).get("action"),
            "last_reason": (wd_st.get("diag") or {}).get("reason"),
        },
        "hope": {
            "status": hope.get("status"),
            "mom": hope.get("mom"),
            "phase": hope.get("phase"),
        },
        "gate": {
            "OPEN": gate.get("OPEN"),
            "A": gate.get("A"),
            "B": gate.get("B"),
            "C": gate.get("C"),
            "post": gate.get("post_residual_green_ticks") or ga.get("post_residual_green_ticks"),
            "source": gate.get("gate_a_source") or ga.get("sources"),
        },
        "stop_files": {
            "lh_stop": (ROOT / "measurements" / "long_horizon_STOP").exists(),
            "wd_stop": (ROOT / "measurements" / "watchdog_STOP").exists(),
        },
    }

    # Simple health rollup
    lh_ok = report["long_horizon"]["alive"] and report["long_horizon"]["last_ok"] is not False
    report["health"] = "green" if lh_ok and report["watchdog"]["alive"] else (
        "degraded" if report["long_horizon"]["alive"] else "down"
    )

    if args.json:
        print(json.dumps(report, indent=2))
        return 0

    lh = report["long_horizon"]
    wd = report["watchdog"]
    g = report["gate"]
    print("Aetheria status (read-only)")
    print(f"  health:     {report['health']}")
    print(f"  LH:         pid={lh['pid']} alive={lh['alive']} tick={lh['tick']}/{lh['max_ticks']} "
          f"status={lh['status']} last_ok={lh['last_ok']} mom={lh['mom']}")
    print(f"  WD:         pid={wd['pid']} alive={wd['alive']} action={wd['last_action']} reason={wd['last_reason']}")
    print(f"  hope:       status={report['hope']['status']} mom={report['hope']['mom']}")
    print(f"  gate:       OPEN={g['OPEN']} A={g['A']} B={g['B']} C={g['C']} post={g['post']} src={g['source']}")
    print(f"  stop_files: lh={report['stop_files']['lh_stop']} wd={report['stop_files']['wd_stop']}")
    return 0 if report["health"] == "green" else 1


if __name__ == "__main__":
    raise SystemExit(main())
