#!/usr/bin/env python3
"""
status_report.py — One-screen sparse-operator status (+ resource / orphan hygiene).

Default is read-only. Optional:
  --reap-orphans   kill stuck grok_supervised_12_probe.py when LH is idle
                   (never kills LH/WD; never reaps during running_tick)

Usage:
  python -u scripts/status_report.py
  python -u scripts/status_report.py --json
  python -u scripts/status_report.py --reap-orphans
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "measurements" / "status_report_latest.json"

# Defaults (overridable via env / CLI)
_DEFAULT_ORPHAN_MIN = float(os.environ.get("AETHERIA_ORPHAN_PROBE_MIN", "15"))
WARN_WS_MB = float(os.environ.get("AETHERIA_WARN_WS_MB", "150"))


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def _cim_processes() -> list[dict]:
    """Windows: list python/powershell with command lines."""
    if os.name != "nt":
        return []
    try:
        r = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                (
                    "Get-CimInstance Win32_Process -Filter \"Name='python.exe' OR Name='pythonw.exe' "
                    "OR Name='powershell.exe'\" | "
                    "Select-Object ProcessId,Name,CommandLine,WorkingSetSize,CreationDate | "
                    "ConvertTo-Json -Compress"
                ),
            ],
            capture_output=True,
            text=True,
            timeout=45,
            cwd=str(ROOT),
        )
        raw = (r.stdout or "").strip()
        if not raw:
            return []
        data = json.loads(raw)
        if isinstance(data, dict):
            return [data]
        return list(data or [])
    except Exception:
        return []


def _proc_age_min(creation_date) -> float | None:
    """Parse WMI CreationDate loosely → age minutes."""
    if not creation_date:
        return None
    s = str(creation_date)
    # e.g. 20260711121007.123456-240
    try:
        core = s.split(".")[0]
        if len(core) >= 14 and core[:14].isdigit():
            dt = datetime.strptime(core[:14], "%Y%m%d%H%M%S")
            # treat as local; age approx
            return max(0.0, (datetime.now() - dt).total_seconds() / 60.0)
    except Exception:
        pass
    return None


def collect_related_and_orphans(
    lh_status: str, lh_pid, wd_pid, orphan_min: float
) -> tuple[list, list]:
    """Return (related_procs, orphan_probes)."""
    related = []
    orphans = []
    keys = (
        "long_horizon_supervisor",
        "lh_watchdog",
        "grok_supervised_12_probe",
        "residual_autopilot",
        "aetheria_hope_path",
        "hope_path",
        "status_report",
    )
    for row in _cim_processes():
        cmd = row.get("CommandLine") or ""
        if not any(k in cmd for k in keys):
            continue
        pid = row.get("ProcessId")
        ws = row.get("WorkingSetSize") or 0
        try:
            ws_mb = round(int(ws) / (1024 * 1024), 1)
        except Exception:
            ws_mb = None
        age = _proc_age_min(row.get("CreationDate"))
        entry = {
            "pid": pid,
            "name": row.get("Name"),
            "ws_mb": ws_mb,
            "age_min": round(age, 1) if age is not None else None,
            "cmd": cmd[:160],
        }
        # CPU from Get-Process if possible
        try:
            pr = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    f"(Get-Process -Id {int(pid)} -EA SilentlyContinue).CPU",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            cpus = (pr.stdout or "").strip()
            if cpus:
                entry["cpu_s"] = round(float(cpus), 1)
        except Exception:
            pass
        related.append(entry)

        is_probe = "grok_supervised_12_probe" in cmd
        if not is_probe:
            continue
        # Orphan: probe running while plant not in a tick, and old enough
        idle_like = lh_status in (
            "idle_between_ticks",
            "stopped_by_file",
            "completed_max_ticks",
            "completed_once",
            "degraded",
            None,
            "",
        )
        # During running_tick a probe is expected — not an orphan
        if lh_status == "running_tick":
            continue
        age_ok = age is not None and age >= orphan_min
        # Flag probe when LH not in a tick and age exceeds threshold (or age unknown)
        if idle_like and (age_ok or age is None):
            if age is None:
                entry["orphan_reason"] = "probe_while_lh_idle_age_unknown"
            else:
                entry["orphan_reason"] = f"probe_while_lh_idle_age_{age:.0f}m"
            orphans.append(entry)
    return related, orphans


def system_memory() -> dict:
    if os.name != "nt":
        return {}
    try:
        r = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                (
                    "$o=Get-CimInstance Win32_OperatingSystem; "
                    "[PSCustomObject]@{total_gb=[math]::Round($o.TotalVisibleMemorySize/1MB,1); "
                    "free_gb=[math]::Round($o.FreePhysicalMemory/1MB,1)} | ConvertTo-Json -Compress"
                ),
            ],
            capture_output=True,
            text=True,
            timeout=20,
        )
        o = json.loads((r.stdout or "").strip() or "{}")
        tot = float(o.get("total_gb") or 0)
        free = float(o.get("free_gb") or 0)
        used = round(tot - free, 1) if tot else None
        pct = round(100 * (tot - free) / tot, 1) if tot else None
        return {"total_gb": tot, "free_gb": free, "used_gb": used, "pct_used": pct}
    except Exception as e:
        return {"error": str(e)[:120]}


def cpu_load() -> int | None:
    if os.name != "nt":
        return None
    try:
        r = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "(Get-CimInstance Win32_Processor).LoadPercentage",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        # may be multi-line for multi-cpu
        vals = [int(x.strip()) for x in (r.stdout or "").splitlines() if x.strip().isdigit()]
        if not vals:
            return None
        return int(sum(vals) / len(vals))
    except Exception:
        return None


def reap_orphans(orphans: list, lh_status: str) -> list:
    """Kill orphan probe PIDs. Returns list of reap results."""
    results = []
    if lh_status == "running_tick":
        return [{"ok": False, "error": "refuse_reap_during_running_tick"}]
    for o in orphans:
        pid = o.get("pid")
        if not pid:
            continue
        try:
            subprocess.run(
                ["taskkill", "/PID", str(int(pid)), "/F"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            dead = not pid_alive(pid)
            results.append(
                {
                    "pid": pid,
                    "ok": dead,
                    "reason": o.get("orphan_reason"),
                    "ws_mb": o.get("ws_mb"),
                    "age_min": o.get("age_min"),
                }
            )
        except Exception as e:
            results.append({"pid": pid, "ok": False, "error": str(e)[:160]})
    return results


def main() -> int:
    ap = argparse.ArgumentParser(description="Aetheria status + resource/orphan hygiene")
    ap.add_argument("--json", action="store_true", help="machine-readable object")
    ap.add_argument(
        "--reap-orphans",
        action="store_true",
        help="kill orphan probes when LH is not running_tick",
    )
    ap.add_argument(
        "--orphan-min",
        type=float,
        default=_DEFAULT_ORPHAN_MIN,
        help=f"minutes before idle probe is orphan (default {_DEFAULT_ORPHAN_MIN})",
    )
    args = ap.parse_args()
    orphan_min = float(args.orphan_min)

    lh = load(ROOT / "measurements" / "long_horizon_state.json", {}) or {}
    hope = load(ROOT / "measurements" / "hope_status.json", {}) or {}
    gate = load(ROOT / "measurements" / "gate_v2_eval_latest.json", {}) or {}
    wd_st = load(ROOT / "measurements" / "watchdog_status.json", {}) or {}
    gm = load(ROOT / "measurements" / "guidance_momentum.json", {}) or {}
    ga = load(ROOT / "measurements" / "gate_a_progress.json", {}) or {}
    summary = load(ROOT / "measurements" / "lh_probe_summary_latest.json", {}) or {}

    lh_pid = read_pid(ROOT / "measurements" / "long_horizon.pid") or lh.get("pid")
    wd_pid = read_pid(ROOT / "measurements" / "watchdog.pid")
    lh_status = lh.get("status")

    related, orphans = collect_related_and_orphans(lh_status, lh_pid, wd_pid, orphan_min)
    mem = system_memory()
    cpu = cpu_load()

    heavy = [r for r in related if (r.get("ws_mb") or 0) >= WARN_WS_MB]
    reaped = []
    if args.reap_orphans and orphans:
        reaped = reap_orphans(orphans, lh_status)
        # refresh after reap
        related, orphans = collect_related_and_orphans(lh_status, lh_pid, wd_pid, orphan_min)

    hist = lh.get("history") or []
    seg_green = sum(
        1 for h in hist if h.get("ok") is True or str(h.get("ok")) == "True"
    )
    mom = lh.get("persisted_mom") or lh.get("last_final_mom") or gm.get("guidance_momentum")
    gate_post = gate.get("post_residual_green_ticks") or ga.get("post_residual_green_ticks")

    report = {
        "schema": "aetheria_status_report_v3",
        "ts": utc(),
        "long_horizon": {
            "pid": lh_pid,
            "alive": pid_alive(lh_pid),
            "tick": lh.get("tick"),
            "max_ticks": lh.get("max_ticks"),
            "status": lh_status,
            "last_ok": lh.get("last_ok"),
            "mom": mom,
            "interval_min": lh.get("interval_min"),
            "heartbeat_at": lh.get("heartbeat_at"),
            "last_tick_finished": lh.get("last_tick_finished"),
            "started_at": lh.get("started_at"),
        },
        # Split segment vs campaign so tick reset is not misread as wiped progress
        "progress": {
            "segment": {
                "pid": lh_pid,
                "tick": lh.get("tick"),
                "max_ticks": lh.get("max_ticks"),
                "green_in_this_process": seg_green,
                "started_at": lh.get("started_at"),
                "note": "Tick counter is per process. New PID => tick restarts at 1; not a campaign wipe.",
            },
            "campaign": {
                "mom": mom,
                "guidance_momentum": gm.get("guidance_momentum"),
                "durable_gate_post_green": gate_post,
                "gate_A": gate.get("A"),
                "last_ok": lh.get("last_ok"),
                "note": "Mom + durable gate-A are continuity across PIDs. Prefer these over segment tick alone.",
            },
            "how_to_read": (
                "If tick looks 'low' after a reset: check progress.campaign.mom and "
                "durable_gate_post_green, and progress.segment.started_at/pid. "
                "A reset means a new segment process, not that you failed to understand progress."
            ),
        },
        "watchdog": {
            "pid": wd_pid,
            "alive": pid_alive(wd_pid) if wd_pid else False,
            "last_action": (wd_st.get("diag") or {}).get("action")
            or (wd_st.get("last_applied") or {}).get("action"),
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
            "post": gate_post,
            "source": gate.get("gate_a_source") or ga.get("sources"),
        },
        "probe_contract": {
            "ok": summary.get("ok") if summary else None,
            "completion_path": summary.get("completion_path"),
            "runner": summary.get("runner"),
            "cycles_complete": summary.get("cycles_complete"),
            "final_mom": summary.get("final_mom"),
            "error_class": summary.get("error_class"),
        },
        "stop_files": {
            "lh_stop": (ROOT / "measurements" / "long_horizon_STOP").exists(),
            "wd_stop": (ROOT / "measurements" / "watchdog_STOP").exists(),
        },
        "resources": {
            "memory": mem,
            "cpu_load_pct": cpu,
            "related_procs": related,
            "heavy_procs": heavy,
            "orphan_probes": orphans,
            "orphan_min_threshold": orphan_min,
            "warn_ws_mb": WARN_WS_MB,
            "reaped": reaped,
        },
        "lessons": {
            "orphan_probe": "Cycle finalize can hang after contract ok; kill orphans when LH idle",
            "find_lag": "status_report shows orphan_probes + heavy_procs + cpu/mem",
            "tick_reset": "Segment tick is per PID; mom + durable gate-A are campaign continuity",
        },
    }

    lh_ok = report["long_horizon"]["alive"] and report["long_horizon"]["last_ok"] is not False
    wd_ok = report["watchdog"]["alive"]
    if not report["long_horizon"]["alive"]:
        report["health"] = "down"
    elif orphans or heavy or (cpu is not None and cpu >= 85):
        report["health"] = "warn" if lh_ok else "degraded"
    elif lh_ok and wd_ok:
        report["health"] = "green"
    elif report["long_horizon"]["alive"]:
        report["health"] = "degraded"
    else:
        report["health"] = "down"

    # Persist for learning / pulses
    try:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    except Exception:
        pass

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        lh = report["long_horizon"]
        wd = report["watchdog"]
        g = report["gate"]
        pc = report["probe_contract"]
        seg = report["progress"]["segment"]
        camp = report["progress"]["campaign"]
        print("Aetheria status")
        print(f"  health:     {report['health']}")
        print(
            f"  segment:    pid={seg['pid']} tick={seg['tick']}/{seg['max_ticks']} "
            f"green_this_process={seg['green_in_this_process']} started={seg['started_at']}"
        )
        print(
            f"  campaign:   mom={camp['mom']} durable_gate_post={camp['durable_gate_post_green']} "
            f"gate_A={camp['gate_A']} last_ok={camp['last_ok']}"
        )
        print(
            f"  LH:         alive={lh['alive']} status={lh['status']} "
            f"interval_min={lh['interval_min']}"
        )
        print(
            f"  WD:         pid={wd['pid']} alive={wd['alive']} "
            f"action={wd['last_action']} reason={wd['last_reason']}"
        )
        print(f"  hope:       status={report['hope']['status']} mom={report['hope']['mom']}")
        print(
            f"  gate:       OPEN={g['OPEN']} A={g['A']} B={g['B']} C={g['C']} "
            f"post={g['post']} src={g['source']}"
        )
        print(
            f"  probe:      ok={pc.get('ok')} path={pc.get('completion_path')} "
            f"runner={pc.get('runner')} err={pc.get('error_class')}"
        )
        print(
            f"  stop_files: lh={report['stop_files']['lh_stop']} wd={report['stop_files']['wd_stop']}"
        )
        print(
            "  note:       tick is per-process; mom + durable_gate_post = continuity across PID resets"
        )
        mem = report["resources"]["memory"]
        if mem:
            print(
                f"  memory:     used={mem.get('used_gb')}GB free={mem.get('free_gb')}GB "
                f"({mem.get('pct_used')}% used)"
            )
        if cpu is not None:
            print(f"  cpu_load:   {cpu}%")
        if related:
            print("  related:")
            for r in related:
                age_s = f"{r.get('age_min')}m" if r.get("age_min") is not None else "?"
                print(
                    f"    pid={r.get('pid')} ws={r.get('ws_mb')}MB cpu={r.get('cpu_s')}s "
                    f"age={age_s}  {r.get('cmd', '')[:90]}"
                )
        if orphans:
            print(f"  ORPHAN_PROBES: {len(orphans)}  (use --reap-orphans if LH not running_tick)")
            for o in orphans:
                print(
                    f"    ! pid={o.get('pid')} ws={o.get('ws_mb')}MB age={o.get('age_min')}m "
                    f"{o.get('orphan_reason')}"
                )
        if reaped:
            print(f"  reaped:     {reaped}")
        if heavy and not orphans:
            print(f"  heavy:      {[h.get('pid') for h in heavy]} (>{WARN_WS_MB}MB)")
        if report["health"] == "warn":
            print("  hint:       lag often = orphan probe; --reap-orphans when idle")

    # exit codes: 0 green, 1 warn/degraded, 2 down
    if report["health"] == "green":
        return 0
    if report["health"] == "down":
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
