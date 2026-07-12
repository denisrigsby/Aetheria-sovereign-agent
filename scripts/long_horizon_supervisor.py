#!/usr/bin/env python3
"""
long_horizon_supervisor.py — Detached long-horizon Aetheria loop (survives Grok chat death).

Architecture:
  [This process, detached]  runs forever (or until stop file / max ticks)
       |
       +-- health check
       +-- light N-cycle probe (hope_path / supervised probe)
       +-- update hope_status + RESUME_STATE + long_horizon_state.json
       +-- optional periodic core backup
       +-- sleep interval
  [Grok] supervises by reading status files when a session is alive;
         does NOT need to be parent of this process.

Stop gracefully:
  echo stop > measurements/long_horizon_STOP

Usage:
  python -u scripts/long_horizon_supervisor.py --cycles 2 --interval-min 30 --max-ticks 48
  # 48 * 30min ≈ 24h of ticks if continuous power

Env (defaults match conservation mode):
  AETHERIA_LIGHT_MANAGE=1
  AETHERIA_SKIP_FINAL_RECON=1
  AETHERIA_HEAVY_HEALTH_CYCLES=6,12
  AETHERIA_META_RECON=0
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

STATE_PATH = ROOT / "measurements" / "long_horizon_state.json"
STOP_PATH = ROOT / "measurements" / "long_horizon_STOP"
PID_PATH = ROOT / "measurements" / "long_horizon.pid"
LOG_JSONL = ROOT / "logs" / "long_horizon.jsonl"
LOG_TXT = ROOT / "logs" / f"long_horizon_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def log(msg: str) -> None:
    line = f"[{utc_now()}] {msg}"
    print(line, flush=True)
    try:
        LOG_TXT.parent.mkdir(parents=True, exist_ok=True)
        with LOG_TXT.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def append_jsonl(obj: dict) -> None:
    try:
        LOG_JSONL.parent.mkdir(parents=True, exist_ok=True)
        with LOG_JSONL.open("a", encoding="utf-8") as f:
            f.write(json.dumps(obj, ensure_ascii=False, default=str) + "\n")
    except Exception:
        pass


def write_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    state = dict(state)
    state["updated_at"] = utc_now()
    tmp = STATE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")
    tmp.replace(STATE_PATH)
    try:
        from living.aetheria_canon import write_hope_status

        write_hope_status(
            {
                "phase": "long_horizon",
                "status": state.get("status", "running"),
                "long_horizon": {
                    "tick": state.get("tick"),
                    "last_ok": state.get("last_ok"),
                    "last_mom_series": state.get("last_mom_series"),
                    "last_error": state.get("last_error"),
                    "pid": state.get("pid"),
                    "stop_file": str(STOP_PATH),
                    "log": str(LOG_TXT),
                },
            }
        )
    except Exception as e:
        log(f"hope_status note: {e}")


def write_resume(state: dict) -> None:
    resume = {
        "schema": "aetheria_resume_v1",
        "updated_at": utc_now(),
        "workspace": str(ROOT),
        "phase": "long_horizon_autonomous",
        "mode": "long_horizon_supervisor",
        "north_star": "Persistent sovereign Aetheria; multi-cycle; co-pilot; careful self-evo; no multi-hour hangs. Outages expected.",
        "long_horizon": state,
        "files": {
            "handoff": "HANDOFF_NEXT_SESSION.md",
            "resume": "RESUME_STATE.json",
            "lh_state": str(STATE_PATH.relative_to(ROOT)),
            "hope_status": "measurements/hope_status.json",
            "lh_log": str(LOG_TXT),
            "stop": str(STOP_PATH.relative_to(ROOT)),
        },
        "env_defaults": {
            "AETHERIA_LIGHT_MANAGE": "1",
            "AETHERIA_SKIP_FINAL_RECON": "1",
            "AETHERIA_HEAVY_HEALTH_CYCLES": "6,12",
            "AETHERIA_META_RECON": "0",
        },
        "next_actions": [
            "Read HANDOFF_NEXT_SESSION.md + RESUME_STATE.json + measurements/long_horizon_state.json",
            "If supervisor dead but wanted: python -u scripts/long_horizon_supervisor.py (or launch_long_horizon.ps1)",
            "If registry missing: restore from backups/**/sovereign_asset_registry.json",
            "Grok: read hope_status; only intervene on last_ok=false or stalled ticks",
        ],
        "do_not": [
            "kill supervisor without writing stop file unless emergency",
            "wipe registry",
            "heavy manage every cycle",
            "attach long runs to chat session",
        ],
        "user_constraints": "Power/Windows/internet outages expected; supervisor is process-local durable; Grok session is optional supervisor UI",
        "prompt_seed_for_next_grok": (
            "Read <AETHERIA_ROOT>/HANDOFF_NEXT_SESSION.md, RESUME_STATE.json, "
            "measurements/long_horizon_state.json, measurements/hope_status.json. "
            "Long-horizon mode may be running detached. Check PID alive; if dead and user wants continuity, relaunch launch_long_horizon.ps1. "
            "Do not redesign; maintain conservation; intervene only on failures."
        ),
    }
    (ROOT / "RESUME_STATE.json").write_text(json.dumps(resume, indent=2), encoding="utf-8")


def ensure_env() -> None:
    os.environ.setdefault("AETHERIA_LIGHT_MANAGE", "1")
    os.environ.setdefault("AETHERIA_SKIP_FINAL_RECON", "1")
    os.environ.setdefault("AETHERIA_HEAVY_HEALTH_CYCLES", "6,12")
    os.environ.setdefault("AETHERIA_META_RECON", "0")


def restore_registry_if_missing() -> bool:
    reg = ROOT / "sovereign_asset_registry.json"
    if reg.exists() and reg.stat().st_size > 100:
        return True
    backups = sorted(
        (ROOT / "backups").rglob("sovereign_asset_registry.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not backups:
        log("CRITICAL: no registry and no backup")
        return False
    import shutil

    shutil.copy2(backups[0], reg)
    log(f"Restored registry from {backups[0]}")
    return True


def run_health() -> dict:
    try:
        from scripts.aetheria_hope_path import health  # type: ignore

        return health()
    except Exception:
        # direct
        sys.path.insert(0, str(ROOT))
        try:
            # import by path
            import importlib.util

            spec = importlib.util.spec_from_file_location(
                "aetheria_hope_path", ROOT / "scripts" / "aetheria_hope_path.py"
            )
            mod = importlib.util.module_from_spec(spec)
            assert spec.loader
            spec.loader.exec_module(mod)
            return mod.health()
        except Exception as e:
            return {"ok": False, "error": str(e)[:300]}


def _probe_timeout_s(cycles: int) -> int:
    """Bounded wall time for probe (paradigm: loud fail, no multi-hour mystery)."""
    env_abs = os.environ.get("AETHERIA_PROBE_TIMEOUT_S", "").strip()
    if env_abs.isdigit() and int(env_abs) > 0:
        return int(env_abs)
    # base 300 + 180/cycle, floor 600, cap 2400
    return int(min(2400, max(600, 300 + 180 * int(cycles))))


def _load_probe_contract_summary() -> dict | None:
    p = ROOT / "measurements" / "lh_probe_summary_latest.json"
    if not p.exists():
        return None
    try:
        o = json.loads(p.read_text(encoding="utf-8"))
        if o.get("schema") != "lh_probe_summary_v1":
            return None
        return o
    except Exception:
        return None


def run_probe_cycles(cycles: int, tick: int) -> dict:
    """Run paradigm probe: env cycle count + contract summary; regex dual-read fallback.

    Primary: AETHERIA_NUM_CYCLES + grok_supervised_12_probe.py (no source rewrite).
    Parent trusts measurements/lh_probe_summary_latest.json when present.
    """
    ensure_env()
    probe_script = ROOT / "grok_supervised_12_probe.py"
    if not probe_script.exists():
        return {"ok": False, "error": "probe_script_missing", "error_class": "import_error", "tick": tick}

    log_path = ROOT / "logs" / f"lh_probe_tick{tick}_{int(time.time())}.log"
    summary: dict = {
        "tick": tick,
        "cycles": cycles,
        "log": str(log_path),
        "ok": False,
        "started": utc_now(),
        "runner": "paradigm_probe_v1",
    }
    # Clear stale contract so we do not read a previous tick's ok
    contract_path = ROOT / "measurements" / "lh_probe_summary_latest.json"
    try:
        if contract_path.exists():
            contract_path.unlink()
    except Exception:
        pass

    env = os.environ.copy()
    env["AETHERIA_NUM_CYCLES"] = str(cycles)
    env["NUM_CYCLES"] = str(cycles)
    env.setdefault("AETHERIA_LIGHT_MANAGE", "1")
    env.setdefault("AETHERIA_SKIP_FINAL_RECON", "1")
    env.setdefault("AETHERIA_META_RECON", "0")

    legacy = env.get("AETHERIA_PROBE_LEGACY", "").strip() in ("1", "true", "True")
    wrap = None
    run_target = probe_script
    if legacy:
        # Escape hatch: old temp-file NUM_CYCLES rewrite
        src = probe_script.read_text(encoding="utf-8")
        src = re.sub(r"NUM_CYCLES\s*=\s*\d+", f"NUM_CYCLES = {cycles}", src)
        wrap = ROOT / "scripts" / f"_lh_probe_{tick}_{int(time.time())}.py"
        wrap.write_text(src, encoding="utf-8")
        run_target = wrap
        summary["note"] = "legacy_source_rewrite"

    timeout = _probe_timeout_s(cycles)
    summary["timeout_s"] = timeout
    try:
        with log_path.open("w", encoding="utf-8") as lf:
            p = subprocess.Popen(
                [sys.executable, "-u", str(run_target)],
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
                # Early complete: contract summary OR log markers
                contract = _load_probe_contract_summary()
                cycles_done = False
                if contract and int(contract.get("cycles_complete") or 0) >= cycles:
                    cycles_done = True
                    summary["completion_path"] = "contract_summary"
                else:
                    try:
                        text_so_far = log_path.read_text(encoding="utf-8", errors="replace")
                    except Exception:
                        text_so_far = ""
                    completes_so_far = set(re.findall(r"CYCLE (\d+)/\d+ COMPLETE", text_so_far))
                    if len(completes_so_far) >= cycles:
                        cycles_done = True
                        summary["completion_path"] = "log_regex_early"
                if cycles_done:
                    # Finalize grace — scribe/channel can hang after contract is already ok
                    fin_deadline = time.time() + 45
                    while time.time() < fin_deadline and p.poll() is None:
                        time.sleep(2)
                    if p.poll() is None:
                        log(f"probe cycles complete — terminating slow finalize pid={p.pid}")
                        p.terminate()
                        try:
                            p.wait(timeout=15)
                        except Exception:
                            p.kill()
                        rc = 0
                        summary["note"] = (summary.get("note") or "") + "|finalize_truncated"
                        summary["error_class"] = summary.get("error_class") or "parent_finalize_truncate"
                    else:
                        rc = p.returncode
                    break
                time.sleep(3)
            else:
                if p.poll() is None:
                    p.kill()
                    try:
                        p.wait(timeout=10)
                    except Exception:
                        pass
                    summary["error"] = f"probe_timeout_{timeout}s"
                    summary["error_class"] = "probe_timeout"
                    rc = -9
                else:
                    rc = p.returncode

        summary["exit_code"] = rc
        text = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""

        # Dual-read: contract primary, regex fallback
        contract = _load_probe_contract_summary()
        if contract and contract.get("ok") is True and int(contract.get("cycles_complete") or 0) >= cycles:
            summary["ok"] = True
            summary["cycles_complete"] = int(contract.get("cycles_complete") or 0)
            summary["mom_series"] = contract.get("mom_series") or []
            summary["final_mom"] = contract.get("final_mom")
            summary["completion_path"] = summary.get("completion_path") or "contract_summary"
            summary["contract"] = {k: contract.get(k) for k in ("schema", "runner", "finished_at", "ok")}
        else:
            moms = [float(m) for m in re.findall(r"\[Post\] mom=([\d.]+)", text)]
            completes = re.findall(r"CYCLE (\d+)/\d+ COMPLETE", text)
            summary["mom_series"] = moms
            summary["final_mom"] = moms[-1] if moms else None
            summary["cycles_complete"] = len(set(completes))
            summary["ok"] = summary["cycles_complete"] >= cycles
            summary["completion_path"] = "log_regex_fallback"
            if contract:
                summary["contract_partial"] = {
                    "ok": contract.get("ok"),
                    "cycles_complete": contract.get("cycles_complete"),
                }
            if not summary["ok"] and summary.get("error_class") is None:
                summary["error_class"] = "cycles_incomplete"
            if summary["ok"]:
                summary["note"] = (summary.get("note") or "") + "|completion_via_fallback"

        if summary["ok"] and rc not in (0, None) and not summary.get("error"):
            summary["note"] = (summary.get("note") or "") + "|nonzero_exit_but_cycles_ok"
        if summary.get("error_class") == "probe_timeout":
            summary["ok"] = False
        summary["finished"] = utc_now()

        # Refresh contract file with parent view (optional audit)
        try:
            parent_view = {
                "schema": "lh_probe_summary_v1",
                "ok": summary.get("ok"),
                "cycles_requested": cycles,
                "cycles_complete": summary.get("cycles_complete"),
                "final_mom": summary.get("final_mom"),
                "mom_series": summary.get("mom_series"),
                "exit_code": rc,
                "started_at": summary.get("started"),
                "finished_at": summary.get("finished"),
                "error": summary.get("error"),
                "error_class": summary.get("error_class"),
                "log_path": str(log_path),
                "runner": "paradigm_probe_v1_parent",
                "completion_path": summary.get("completion_path"),
                "notes": [summary.get("note")] if summary.get("note") else [],
                "tick": tick,
            }
            contract_path.write_text(json.dumps(parent_view, indent=2), encoding="utf-8")
        except Exception:
            pass
    except Exception as e:
        summary["error"] = str(e)[:400]
        summary["error_class"] = "unknown"
        summary["traceback"] = traceback.format_exc()[-500:]
    finally:
        if wrap is not None:
            try:
                wrap.unlink()
            except Exception:
                pass
        defaults = ROOT / "next_interventions.defaults.json"
        if defaults.exists():
            (ROOT / "next_interventions.json").write_text(
                defaults.read_text(encoding="utf-8"), encoding="utf-8"
            )
    return summary


def maybe_backup(tick: int, every: int) -> None:
    if every <= 0 or tick % every != 0:
        return
    ps1 = ROOT / "scripts" / "backup_sovereign_core.ps1"
    if not ps1.exists():
        return
    log(f"Periodic backup tick={tick}")
    try:
        subprocess.call(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(ps1),
                "-Label",
                f"lh_tick{tick}",
            ],
            cwd=str(ROOT),
            timeout=300,
        )
    except Exception as e:
        log(f"backup note: {e}")


def should_stop() -> bool:
    return STOP_PATH.exists()


def main() -> int:
    ap = argparse.ArgumentParser(description="Long-horizon detached Aetheria supervisor")
    ap.add_argument("--cycles", type=int, default=2, help="Cycles per tick (default 2; use 6 for deeper)")
    ap.add_argument("--interval-min", type=float, default=30.0, help="Minutes between ticks after a run")
    ap.add_argument("--max-ticks", type=int, default=48, help="Stop after N ticks (0=unlimited)")
    ap.add_argument("--backup-every", type=int, default=4, help="Backup every N ticks (0=never)")
    ap.add_argument("--hygiene-every", type=int, default=8, help="Registry hygiene every N ticks (0=never)")
    ap.add_argument("--once", action="store_true", help="Single tick then exit (test)")
    args = ap.parse_args()

    ensure_env()
    (ROOT / "logs").mkdir(exist_ok=True)
    (ROOT / "measurements").mkdir(exist_ok=True)
    if STOP_PATH.exists():
        STOP_PATH.unlink()

    pid = os.getpid()
    PID_PATH.write_text(str(pid), encoding="utf-8")
    state = {
        "pid": pid,
        "status": "starting",
        "tick": 0,
        "cycles_per_tick": args.cycles,
        "interval_min": args.interval_min,
        "max_ticks": args.max_ticks,
        "log_txt": str(LOG_TXT),
        "started_at": utc_now(),
        "history": [],
    }
    write_state(state)
    write_resume(state)
    log(f"LONG HORIZON SUPERVISOR START pid={pid} cycles={args.cycles} interval={args.interval_min}m")

    try:
        from living.aetheria_canon import append_session_living

        append_session_living(
            {
                "tag": "RIGOR_ENFORCED",
                "summary": f"Long-horizon supervisor START pid={pid} cycles/tick={args.cycles} interval_min={args.interval_min} max_ticks={args.max_ticks}. Detached; Grok supervises via hope_status. RIGOR_ENFORCED.",
                "score": 9.8,
                "phase": "long_horizon_start",
                "RIGOR_ENFORCED": True,
            }
        )
    except Exception:
        pass

    tick = 0
    while True:
        if should_stop():
            log("STOP file detected — graceful exit")
            state["status"] = "stopped_by_file"
            break
        tick += 1
        state["tick"] = tick
        state["status"] = "running_tick"
        write_state(state)
        write_resume(state)
        log(f"=== TICK {tick} BEGIN ===")

        if not restore_registry_if_missing():
            state["last_ok"] = False
            state["last_error"] = "registry_missing_no_backup"
            write_state(state)
            time.sleep(60)
            if args.once:
                break
            continue

        # Health
        h = run_health()
        orch_ok = bool((h.get("smoke") or {}).get("orch_ok") if isinstance(h, dict) else False)
        log(f"health orch_ok={orch_ok}")

        if args.hygiene_every and tick % args.hygiene_every == 0:
            try:
                subprocess.call(
                    [sys.executable, "-u", str(ROOT / "scripts" / "registry_hygiene.py"), "--max-assets", "500"],
                    cwd=str(ROOT),
                    timeout=120,
                )
            except Exception as e:
                log(f"hygiene note: {e}")

        # Probe
        summary = run_probe_cycles(args.cycles, tick)
        log(
            f"tick={tick} probe ok={summary.get('ok')} moms={summary.get('mom_series')} "
            f"complete={summary.get('cycles_complete')}/{args.cycles}"
        )
        append_jsonl({"ts": utc_now(), "tick": tick, "summary": summary, "health_orch_ok": orch_ok})

        state["last_ok"] = bool(summary.get("ok"))
        state["last_mom_series"] = summary.get("mom_series")
        state["last_final_mom"] = summary.get("final_mom")
        state["last_error"] = summary.get("error")
        state["last_probe_log"] = summary.get("log")
        state["last_tick_finished"] = utc_now()
        hist = list(state.get("history") or [])
        tick_ts = utc_now()
        hist.append(
            {
                "tick": tick,
                "ok": summary.get("ok"),
                "final_mom": summary.get("final_mom"),
                "ts": tick_ts,
            }
        )
        state["history"] = hist[-50:]
        state["status"] = "idle_between_ticks" if summary.get("ok") else "degraded"
        # P0: durable gate-A green ticks survive PID restart
        try:
            from scripts.eval_residual_gate_v2 import record_green_tick

            record_green_tick(
                tick_ts,
                tick,
                bool(summary.get("ok")),
                pid=state.get("pid"),
            )
        except Exception:
            try:
                # fallback if scripts. package import fails
                import importlib.util

                _p = ROOT / "scripts" / "eval_residual_gate_v2.py"
                spec = importlib.util.spec_from_file_location("eval_residual_gate_v2", _p)
                mod = importlib.util.module_from_spec(spec)
                assert spec.loader is not None
                spec.loader.exec_module(mod)
                mod.record_green_tick(tick_ts, tick, bool(summary.get("ok")), pid=state.get("pid"))
            except Exception as e:
                log(f"gate_a durable record note: {e}")
        # Persist mom so next tick subprocess continues ladder (not reset to 0)
        try:
            mom = summary.get("final_mom")
            if mom is not None:
                mp = ROOT / "measurements" / "guidance_momentum.json"
                mp.write_text(
                    json.dumps(
                        {"guidance_momentum": float(mom), "updated_at": utc_now(), "from_tick": tick},
                        indent=2,
                    ),
                    encoding="utf-8",
                )
                state["persisted_mom"] = float(mom)
        except Exception as e:
            log(f"mom persist note: {e}")
        write_state(state)
        write_resume(state)

        maybe_backup(tick, args.backup_every)

        # Steering zoom (user weakness/opportunity hygiene) — non-fatal
        try:
            subprocess.call(
                [sys.executable, "-u", str(ROOT / "scripts" / "zoom_lens.py"), "--quiet"],
                cwd=str(ROOT),
                timeout=60,
            )
        except Exception as e:
            log(f"zoom_lens note: {e}")

        if args.once:
            log(" --once set; exiting after one tick")
            state["status"] = "completed_once"
            break
        if args.max_ticks and tick >= args.max_ticks:
            log(f"max_ticks={args.max_ticks} reached")
            state["status"] = "completed_max_ticks"
            break

        # Sleep in small slices so STOP file is responsive
        sleep_s = max(30.0, float(args.interval_min) * 60.0)
        log(f"sleeping {sleep_s/60:.1f} min until next tick")
        end = time.time() + sleep_s
        while time.time() < end:
            if should_stop():
                log("STOP during sleep")
                state["status"] = "stopped_by_file"
                write_state(state)
                write_resume(state)
                return 0
            # heartbeat
            state["heartbeat_at"] = utc_now()
            write_state(state)
            time.sleep(min(30.0, end - time.time()))

    write_state(state)
    write_resume(state)
    try:
        PID_PATH.unlink()
    except Exception:
        pass
    if STOP_PATH.exists():
        try:
            STOP_PATH.unlink()
        except Exception:
            pass
    log(f"LONG HORIZON SUPERVISOR EXIT status={state.get('status')}")
    return 0 if state.get("last_ok", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
