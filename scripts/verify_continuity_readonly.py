#!/usr/bin/env python3
"""
verify_continuity_readonly.py — Read-only continuity audit.

Checks backups, optional resume pointer, momentum carry files, and process
liveness without modifying the registry, starting probes, or restarting
processes. Writes a report under measurements/ only.

Usage:
  python -u scripts/verify_continuity_readonly.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
OUT = ROOT / "measurements" / "CONTINUITY_VERIFY_latest.json"
OUT_MD = ROOT / "measurements" / "CONTINUITY_VERIFY_latest.md"


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(p: Path):
    if not p.exists():
        return None
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


def check_backups() -> dict:
    bdir = ROOT / "backups"
    if not bdir.exists():
        return {"ok": False, "error": "backups_dir_missing", "count": 0}
    items = []
    for p in sorted(bdir.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        if p.name.startswith("."):
            continue
        try:
            st = p.stat()
            items.append(
                {
                    "name": p.name,
                    "is_dir": p.is_dir(),
                    "size": st.st_size if p.is_file() else None,
                    "mtime": datetime.fromtimestamp(st.st_mtime, timezone.utc).isoformat(),
                }
            )
        except Exception:
            continue
    zips = [i for i in items if i["name"].endswith(".zip")]
    return {
        "ok": len(items) > 0,
        "count": len(items),
        "zip_count": len(zips),
        "newest": items[0] if items else None,
        "sample": items[:8],
    }


def check_resume() -> dict:
    p = ROOT / "RESUME_STATE.json"
    raw = load_json(p)
    if raw is None:
        return {"ok": False, "error": "missing"}
    if isinstance(raw, dict) and raw.get("_error"):
        return {"ok": False, "error": raw["_error"]}
    required_top = ["schema", "updated_at", "phase", "mode"]
    missing = [k for k in required_top if k not in raw]
    nested = {
        "long_horizon": isinstance(raw.get("long_horizon"), dict),
        "pulse_heartbeat": isinstance(raw.get("pulse_heartbeat"), dict),
        "optional_blocks": True,
        "files": isinstance(raw.get("files"), dict) or raw.get("files") is None,
    }
    # PowerShell JSON footgun: nested objects dropped → flat empty
    lh = raw.get("long_horizon") if isinstance(raw.get("long_horizon"), dict) else {}
    ok = not missing and nested["long_horizon"]
    return {
        "ok": ok,
        "missing_top": missing,
        "nested_present": nested,
        "phase": raw.get("phase"),
        "mode": raw.get("mode"),
        "updated_at": raw.get("updated_at"),
        "lh_tick": lh.get("tick"),
        "lh_mom": lh.get("mom") or lh.get("last_final_mom"),
        "pulse_action": (raw.get("pulse_heartbeat") or {}).get("action")
        if isinstance(raw.get("pulse_heartbeat"), dict)
        else None,
    }


def check_momentum() -> dict:
    lh_p = ROOT / "measurements" / "long_horizon_state.json"
    gm_p = ROOT / "measurements" / "guidance_momentum.json"
    lh = load_json(lh_p) or {}
    gm = load_json(gm_p)
    if lh.get("_error"):
        return {"ok": False, "error": lh["_error"]}

    hist = lh.get("history") or []
    moms = [h.get("final_mom") for h in hist if isinstance(h, dict) and h.get("final_mom") is not None]
    persisted = lh.get("persisted_mom")
    last_final = lh.get("last_final_mom")

    steps = []
    mono = True
    for i in range(1, len(moms)):
        d = float(moms[i]) - float(moms[i - 1])
        steps.append(d)
        if d < 0:
            mono = False

    gm_val = None
    if isinstance(gm, dict) and not gm.get("_error"):
        gm_val = gm.get("guidance_momentum")

    # Carry-over consistency: last history mom should match last_final / persisted when present
    issues = []
    if moms and last_final is not None and float(moms[-1]) != float(last_final):
        issues.append("history_tail_ne_last_final_mom")
    if persisted is not None and last_final is not None and float(persisted) != float(last_final):
        issues.append("persisted_ne_last_final")
    if gm_val is not None and last_final is not None:
        # guidance may lag one tick; flag only large drift
        if abs(float(gm_val) - float(last_final)) > 50:
            issues.append("guidance_momentum_drift_gt_50")

    ok = len(issues) == 0 and (persisted is not None or last_final is not None or moms)
    return {
        "ok": ok,
        "issues": issues,
        "persisted_mom": persisted,
        "last_final_mom": last_final,
        "guidance_momentum": gm_val,
        "history_n": len(hist),
        "mom_first": moms[0] if moms else None,
        "mom_last": moms[-1] if moms else None,
        "mom_delta": (float(moms[-1]) - float(moms[0])) if len(moms) >= 2 else None,
        "non_negative_steps": all(s >= 0 for s in steps) if steps else None,
        "monotone_non_decreasing": mono if steps else None,
        "step_tail": steps[-5:] if steps else [],
        "guidance_file_present": gm_p.exists(),
    }


def check_plant_pids() -> dict:
    lh = load_json(ROOT / "measurements" / "long_horizon_state.json") or {}
    pid_file = ROOT / "measurements" / "long_horizon.pid"
    wd_file = ROOT / "measurements" / "watchdog.pid"
    lh_pid = None
    wd_pid = None
    if pid_file.exists():
        try:
            lh_pid = int(pid_file.read_text(encoding="utf-8").strip().splitlines()[0])
        except Exception:
            pass
    if wd_file.exists():
        try:
            wd_pid = int(wd_file.read_text(encoding="utf-8").strip().splitlines()[0])
        except Exception:
            pass
    if lh_pid is None:
        lh_pid = lh.get("pid")
    return {
        "ok": pid_alive(lh_pid),
        "lh_pid": lh_pid,
        "lh_alive": pid_alive(lh_pid),
        "wd_pid": wd_pid,
        "wd_alive": pid_alive(wd_pid) if wd_pid else None,
        "status": lh.get("status"),
        "last_ok": lh.get("last_ok"),
        "tick": lh.get("tick"),
        "note": "PID check is observational only; no relaunch",
    }


def main() -> int:
    report = {
        "schema": "aetheria_continuity_verify_readonly_v1",
        "ts": utc(),
        "safe_zone": True,
        "did_not": [
            "registry_hygiene",
            "hope_path_probe",
            "process_restart",
            "residual",
            "supervisor_or_watchdog_edit",
        ],
        "backups": check_backups(),
        "resume": check_resume(),
        "momentum": check_momentum(),
        "plant_observe": check_plant_pids(),
    }
    report["ok"] = all(
        [
            report["backups"].get("ok"),
            report["resume"].get("ok"),
            report["momentum"].get("ok"),
            report["plant_observe"].get("ok"),
        ]
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")

    lines = [
        "# Continuity verify (read-only safe zone)",
        "",
        f"**ts:** {report['ts']}",
        f"**overall_ok:** {report['ok']}",
        "",
        "## Backups",
        f"- ok: {report['backups'].get('ok')} count={report['backups'].get('count')} zips={report['backups'].get('zip_count')}",
        f"- newest: {(report['backups'].get('newest') or {}).get('name')}",
        "",
        "## RESUME_STATE",
        f"- ok: {report['resume'].get('ok')} phase={report['resume'].get('phase')} mode={report['resume'].get('mode')}",
        f"- nested long_horizon: {report['resume'].get('nested_present', {}).get('long_horizon')}",
        f"- lh_tick: {report['resume'].get('lh_tick')} mom: {report['resume'].get('lh_mom')}",
        "",
        "## Momentum carry",
        f"- ok: {report['momentum'].get('ok')} issues={report['momentum'].get('issues')}",
        f"- {report['momentum'].get('mom_first')} → {report['momentum'].get('mom_last')} (delta {report['momentum'].get('mom_delta')})",
        f"- persisted={report['momentum'].get('persisted_mom')} last_final={report['momentum'].get('last_final_mom')} guidance={report['momentum'].get('guidance_momentum')}",
        f"- monotone_non_decreasing: {report['momentum'].get('monotone_non_decreasing')}",
        "",
        "## Plant (observe only)",
        f"- LH pid={report['plant_observe'].get('lh_pid')} alive={report['plant_observe'].get('lh_alive')}",
        f"- WD pid={report['plant_observe'].get('wd_pid')} alive={report['plant_observe'].get('wd_alive')}",
        f"- tick={report['plant_observe'].get('tick')} status={report['plant_observe'].get('status')} last_ok={report['plant_observe'].get('last_ok')}",
        "",
        "No plant impact. Report only.",
        "",
    ]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"\nWrote {OUT}", file=sys.stderr)
    print(f"Wrote {OUT_MD}", file=sys.stderr)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
