#!/usr/bin/env python3
"""
aetheria_hope_path.py — The real "kickstart": close-gap operational path.

1) Canon + health report
2) Optional registry hygiene
3) Optional core backup
4) Detached light N-cycle probe (default 6; use --cycles 12 for full)
5) Write measurements/hope_status.json + summary

Usage:
  python -u scripts/aetheria_hope_path.py --cycles 6
  python -u scripts/aetheria_hope_path.py --cycles 12 --hygiene --backup
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
    """Paradigm-aligned probe: env cycle count + contract summary dual-read (no source rewrite)."""
    import re

    os.environ["AETHERIA_LIGHT_MANAGE"] = "1"
    os.environ["AETHERIA_SKIP_FINAL_RECON"] = "1"
    os.environ.setdefault("AETHERIA_HEAVY_HEALTH_CYCLES", "6,12")
    os.environ.setdefault("AETHERIA_META_RECON", "0")
    os.environ["AETHERIA_NUM_CYCLES"] = str(cycles)
    os.environ["NUM_CYCLES"] = str(cycles)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log = ROOT / "logs" / f"hope_path_{ts}.log"
    (ROOT / "logs").mkdir(exist_ok=True)
    probe = ROOT / "grok_supervised_12_probe.py"
    contract_path = ROOT / "measurements" / "lh_probe_summary_latest.json"
    try:
        if contract_path.exists():
            contract_path.unlink()
    except Exception:
        pass

    from living.aetheria_canon import write_hope_status

    write_hope_status(
        {
            "phase": "hope_probe_launch",
            "status": "running",
            "cycles": cycles,
            "log": str(log),
            "runner": "paradigm_probe_env",
        }
    )

    env = os.environ.copy()
    # timeout aligned with LH formula
    timeout = int(min(2400, max(600, 300 + 180 * int(cycles))))
    env_abs = os.environ.get("AETHERIA_PROBE_TIMEOUT_S", "").strip()
    if env_abs.isdigit() and int(env_abs) > 0:
        timeout = int(env_abs)

    with open(log, "w", encoding="utf-8") as lf:
        p = subprocess.Popen(
            [sys.executable, "-u", str(probe)],
            cwd=str(ROOT),
            stdout=lf,
            stderr=subprocess.STDOUT,
            env=env,
        )
        print(f"Probe PID={p.pid} log={log} cycles={cycles} timeout={timeout}s paradigm=env")
        deadline = time.time() + timeout
        rc = None
        while time.time() < deadline:
            if p.poll() is not None:
                rc = p.returncode
                break
            # Early complete if contract written
            try:
                if contract_path.exists():
                    c = json.loads(contract_path.read_text(encoding="utf-8"))
                    if c.get("ok") and int(c.get("cycles_complete") or 0) >= cycles:
                        fin_deadline = time.time() + 45
                        while time.time() < fin_deadline and p.poll() is None:
                            time.sleep(2)
                        if p.poll() is None:
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
            time.sleep(3)
        else:
            if p.poll() is None:
                p.kill()
                try:
                    p.wait(timeout=10)
                except Exception:
                    pass
                rc = -9

    write_hope_status(
        {
            "phase": "hope_probe_done",
            "status": "complete" if rc in (0, None) else "probe_exit_nonzero",
            "exit_code": rc,
            "log": str(log),
            "cycles": cycles,
        }
    )

    summary: dict = {
        "exit_code": rc,
        "log": str(log),
        "cycles_requested": cycles,
        "runner": "paradigm_probe_env",
        "timeout_s": timeout,
    }
    # Dual-read: contract primary, log regex fallback
    try:
        if contract_path.exists():
            c = json.loads(contract_path.read_text(encoding="utf-8"))
            if c.get("schema") == "lh_probe_summary_v1" and c.get("ok") and int(c.get("cycles_complete") or 0) >= cycles:
                summary["ok"] = True
                summary["cycles_complete"] = int(c.get("cycles_complete") or 0)
                summary["mom_series"] = c.get("mom_series") or []
                summary["final_mom"] = c.get("final_mom")
                summary["completion_path"] = "contract_summary"
            else:
                summary["contract_partial"] = {
                    "ok": c.get("ok"),
                    "cycles_complete": c.get("cycles_complete"),
                }
        if "ok" not in summary:
            text = log.read_text(encoding="utf-8", errors="replace")
            moms = [float(m) for m in re.findall(r"\[Post\] mom=([\d.]+)", text)]
            completes = re.findall(r"CYCLE (\d+)/\d+ COMPLETE", text)
            summary["mom_series"] = moms
            summary["final_mom"] = moms[-1] if moms else None
            summary["cycles_complete"] = len(set(completes))
            summary["ok"] = summary["cycles_complete"] >= cycles or (moms and len(moms) >= cycles)
            summary["completion_path"] = "log_regex_fallback"
        if rc == -9:
            summary["ok"] = False
            summary["error_class"] = "probe_timeout"
    except Exception as e:
        summary["parse_error"] = str(e)[:120]
        summary["ok"] = False

    outp = ROOT / "measurements" / f"hope_path_summary_{int(time.time())}.json"
    outp.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    write_hope_status(
        {"phase": "hope_summary", "status": "ready", "summary": summary, "summary_path": str(outp)}
    )
    # Merge hope result into RESUME (do not wipe plant resume block)
    try:
        rp = ROOT / "RESUME_STATE.json"
        if rp.exists():
            resume = json.loads(rp.read_text(encoding="utf-8-sig"))
        else:
            resume = {"schema": "aetheria_resume_v1"}
        resume["updated_at"] = datetime.now(timezone.utc).isoformat()
        resume["last_hope_summary"] = summary
        resume["last_hope_summary_path"] = str(outp)
        resume["last_hope_log"] = summary.get("log")
        rp.write_text(json.dumps(resume, indent=2), encoding="utf-8")
        defaults = ROOT / "next_interventions.defaults.json"
        if defaults.exists() and not (ROOT / "next_interventions.json").exists():
            (ROOT / "next_interventions.json").write_text(
                defaults.read_text(encoding="utf-8"), encoding="utf-8"
            )
    except Exception as e:
        print("resume write note:", e)
    print("SUMMARY", json.dumps(summary, indent=2))
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
            "tag": "RIGOR_ENFORCED",
            "summary": f"Hope path complete ok={ok} cycles_req={args.cycles} complete={summary.get('cycles_complete')} final_mom={summary.get('final_mom')} log={summary.get('log')}",
            "score": 9.7 if ok else 8.5,
            "phase": "hope_path",
            "payload": summary,
            "RIGOR_ENFORCED": True,
        })
    except Exception:
        pass
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
