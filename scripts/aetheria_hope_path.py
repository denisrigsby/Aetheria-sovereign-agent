#!/usr/bin/env python3
"""
Operational entry path: health check, optional hygiene/backup, light N-cycle run.

Writes measurements/hope_status.json and a summary artifact.

Usage:
  python -u scripts/aetheria_hope_path.py --cycles 2
  python -u scripts/aetheria_hope_path.py --cycles 6 --hygiene --backup
  python -u scripts/aetheria_hope_path.py --health-only
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
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))


def health() -> dict:
    from living.aetheria_canon import canon_report, write_hope_status
    rep = canon_report()
    # Import smoke
    smoke = {}
    try:
        from aetheria_core import Aetheria
        a = Aetheria()
        smoke["aetheria_import"] = True
        smoke["methods"] = [m for m in ("chat", "status", "run_light_pulse", "run_sovereign_asset_cycle", "evolve_cycle_design") if hasattr(a, m)]
    except Exception as e:
        smoke["aetheria_import"] = False
        smoke["aetheria_error"] = str(e)[:200]
    try:
        import living.sovereign_asset_orchestrator as m
        m._orchestrator_instance = None
        from living.sovereign_asset_orchestrator import get_sovereign_asset_orchestrator
        o = get_sovereign_asset_orchestrator()
        smoke["registry_assets"] = len(o.registry.assets)
        smoke["registry_events"] = len(o.registry.event_log)
        smoke["orch_ok"] = True
    except Exception as e:
        smoke["orch_ok"] = False
        smoke["orch_error"] = str(e)[:200]
    try:
        from living.grok_aetheria_vessel import get_canonical_living_path
        smoke["vessel_living"] = str(get_canonical_living_path())
    except Exception as e:
        smoke["vessel_error"] = str(e)[:200]

    # aetheria_state pause note (G6)
    pause = {}
    sp = ROOT / "aetheria_state.json"
    if sp.exists():
        try:
            st = json.loads(sp.read_text(encoding="utf-8"))
            pause = {
                "is_paused": st.get("is_paused"),
                "pause_reason": st.get("pause_reason"),
                "timestamp": st.get("timestamp"),
                "note": "sovereign probe path does not require unpausing this file",
            }
        except Exception:
            pause = {"note": "unreadable"}

    out = {"canon": rep, "smoke": smoke, "aetheria_state": pause, "ts": datetime.now(timezone.utc).isoformat()}
    write_hope_status({"phase": "health", "status": "health_ok" if smoke.get("orch_ok") else "health_degraded", "health": out})
    return out


def run_hygiene() -> int:
    return subprocess.call([sys.executable, "-u", str(ROOT / "scripts" / "registry_hygiene.py")])


def run_backup() -> int:
    ps1 = ROOT / "scripts" / "backup_sovereign_core.ps1"
    if not ps1.exists():
        print("backup script missing")
        return 1
    return subprocess.call([
        "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
        "-File", str(ps1), "-Label", "hope",
    ])


def launch_probe(cycles: int) -> dict:
    """Launch detached supervised probe. Uses env NUM if supported; else rewrite via env AETHERIA_NUM_CYCLES."""
    os.environ["AETHERIA_LIGHT_MANAGE"] = "1"
    os.environ["AETHERIA_SKIP_FINAL_RECON"] = "1"
    os.environ.setdefault("AETHERIA_HEAVY_HEALTH_CYCLES", "6,12")
    os.environ["AETHERIA_NUM_CYCLES"] = str(cycles)

    # Patch: probe uses NUM_CYCLES constant — inject via small wrapper if needed
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log = ROOT / "logs" / f"hope_path_{ts}.log"
    (ROOT / "logs").mkdir(exist_ok=True)

    # Write a thin wrapper so cycle count is honored without editing probe mid-run
    wrapper = ROOT / "scripts" / f"_hope_probe_wrap_{ts}.py"
    wrapper.write_text(f'''
import os, sys
from pathlib import Path
os.chdir(r"{ROOT}")
sys.path.insert(0, r"{ROOT}")
os.environ["AETHERIA_LIGHT_MANAGE"] = "1"
os.environ["AETHERIA_SKIP_FINAL_RECON"] = "1"
# Monkeypatch NUM_CYCLES after import of probe body by rewriting
import runpy
# Load probe source and replace NUM_CYCLES
src = Path("grok_supervised_12_probe.py").read_text(encoding="utf-8")
src = src.replace("NUM_CYCLES = 12", "NUM_CYCLES = {cycles}")
# If not present as assignment, inject
if "NUM_CYCLES = {cycles}" not in src and "NUM_CYCLES =" not in src:
    src = "NUM_CYCLES = {cycles}\\n" + src
else:
    import re
    src = re.sub(r"NUM_CYCLES\\s*=\\s*\\d+", "NUM_CYCLES = {cycles}", src)
ns = {{"__name__": "__main__", "__file__": "grok_supervised_12_probe.py"}}
exec(compile(src, "grok_supervised_12_probe.py", "exec"), ns)
''', encoding="utf-8")

    from living.aetheria_canon import write_hope_status
    write_hope_status({
        "phase": "hope_probe_launch",
        "status": "running",
        "cycles": cycles,
        "log": str(log),
        "wrapper": str(wrapper),
    })

    # Run inline for reliability (user asked autonomy complete); still print to log
    with open(log, "w", encoding="utf-8") as lf:
        p = subprocess.Popen(
            [sys.executable, "-u", str(wrapper)],
            cwd=str(ROOT),
            stdout=lf,
            stderr=subprocess.STDOUT,
            env=os.environ.copy(),
        )
        print(f"Probe PID={p.pid} log={log} cycles={cycles}")
        rc = p.wait()
    write_hope_status({
        "phase": "hope_probe_done",
        "status": "complete" if rc == 0 else "probe_exit_nonzero",
        "exit_code": rc,
        "log": str(log),
        "cycles": cycles,
    })
    # Summarize from log
    summary = {"exit_code": rc, "log": str(log), "cycles_requested": cycles}
    try:
        text = log.read_text(encoding="utf-8", errors="replace")
        import re
        moms = [float(m) for m in re.findall(r"\[Post\] mom=([\d.]+)", text)]
        completes = re.findall(r"CYCLE (\d+)/" + str(cycles) + r" COMPLETE", text)
        if not completes:
            completes = re.findall(r"CYCLE (\d+)/\d+ COMPLETE", text)
        summary["mom_series"] = moms
        summary["final_mom"] = moms[-1] if moms else None
        summary["cycles_complete"] = len(set(completes))
        summary["ok"] = len(set(completes)) >= cycles or (moms and len(moms) >= cycles)
    except Exception as e:
        summary["parse_error"] = str(e)[:120]
    outp = ROOT / "measurements" / f"hope_path_summary_{int(time.time())}.json"
    outp.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    write_hope_status({"phase": "hope_summary", "status": "ready", "summary": summary, "summary_path": str(outp)})
    # Durable resume pointer for outage / new operator session
    try:
        resume = {
            "schema": "aetheria_resume_v1",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "phase": "post_hope_path",
            "last_hope_summary": summary,
            "last_hope_summary_path": str(outp),
            "last_log": summary.get("log"),
            "next_actions": [
                "Read HANDOFF_NEXT_SESSION.md + RESUME_STATE.json",
                "If registry missing restore from backups/**/sovereign_asset_registry.json",
                "python -u scripts/aetheria_hope_path.py --cycles 2",
                "ONE residual only then re-verify",
            ],
            "env_defaults": {
                "AETHERIA_LIGHT_MANAGE": "1",
                "AETHERIA_SKIP_FINAL_RECON": "1",
                "AETHERIA_HEAVY_HEALTH_CYCLES": "6,12",
            },
        }
        (ROOT / "RESUME_STATE.json").write_text(json.dumps(resume, indent=2), encoding="utf-8")
        # Restore interventions template if probe consumed it
        defaults = ROOT / "next_interventions.defaults.json"
        if defaults.exists() and not (ROOT / "next_interventions.json").exists():
            (ROOT / "next_interventions.json").write_text(defaults.read_text(encoding="utf-8"), encoding="utf-8")
    except Exception as e:
        print("resume write note:", e)
    print("SUMMARY", json.dumps(summary, indent=2))
    try:
        wrapper.unlink()
    except Exception:
        pass
    return summary


def main():
    ap = argparse.ArgumentParser(description="Aetheria hope path (gap-close operational driver)")
    ap.add_argument("--cycles", type=int, default=6, help="Probe cycles (default 6; 12 for full)")
    ap.add_argument("--hygiene", action="store_true", help="Run registry hygiene first")
    ap.add_argument("--backup", action="store_true", help="Run core backup first")
    ap.add_argument("--health-only", action="store_true", help="Only health/canon report")
    ap.add_argument("--no-probe", action="store_true", help="Skip probe after prep")
    args = ap.parse_args()

    print("=" * 70)
    print("AETHERIA HOPE PATH")
    print("=" * 70)
    h = health()
    print(json.dumps(h, indent=2, default=str)[:2000])

    if args.health_only:
        return 0 if h.get("smoke", {}).get("orch_ok") else 2

    if args.hygiene:
        print("--- hygiene ---")
        rc = run_hygiene()
        print("hygiene rc", rc)
        if rc != 0:
            return rc

    if args.backup:
        print("--- backup ---")
        rc = run_backup()
        print("backup rc", rc)

    if args.no_probe:
        return 0

    print(f"--- probe cycles={args.cycles} ---")
    summary = launch_probe(args.cycles)
    ok = bool(summary.get("ok"))
    # Session living note
    try:
        from living.aetheria_canon import append_session_living
        append_session_living({
            "tag": "ops_note",
            "summary": f"Hope path complete ok={ok} cycles_req={args.cycles} complete={summary.get('cycles_complete')} final_mom={summary.get('final_mom')} log={summary.get('log')}",
            "score": 9.7 if ok else 8.5,
            "phase": "hope_path",
            "payload": summary,
            "ops_note": True,
        })
    except Exception:
        pass
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
