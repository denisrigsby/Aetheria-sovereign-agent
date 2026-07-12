#!/usr/bin/env python3
"""
lh_watchdog.py — External guardian for long_horizon_supervisor.

Runs detached. Does NOT attach to Grok chat.
- Detects dead PID, stale heartbeat, stuck running_tick, completed_max_ticks
- Relaunches launch_long_horizon.ps1 (or python supervisor) when needed
- Writes measurements/watchdog_status.json always
- Writes measurements/NOTIFY_USER.md only on events that need human attention
- Never wipes registry; never merges living; never kills a healthy supervisor

Stop:
  echo stop > measurements/watchdog_STOP

Usage:
  python -u scripts/lh_watchdog.py --interval-sec 60
  # detached:
  powershell -File scripts/launch_lh_watchdog.ps1
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

MEAS = ROOT / "measurements"
STATE_PATH = MEAS / "long_horizon_state.json"
PID_PATH = MEAS / "long_horizon.pid"
LH_STOP = MEAS / "long_horizon_STOP"
WD_STOP = MEAS / "watchdog_STOP"
WD_PID = MEAS / "watchdog.pid"
WD_STATUS = MEAS / "watchdog_status.json"
NOTIFY = MEAS / "NOTIFY_USER.md"
WD_LOG = ROOT / "logs" / f"lh_watchdog_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

# Thresholds (minutes)
HEARTBEAT_STALE_MIN = 5.0          # idle should heartbeat ~30s
RUNNING_STUCK_MIN = 25.0           # 2-cycle probe soft wall ~10–15m; 25m = stuck
POST_EXIT_RELAUNCH_DELAY_S = 15


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def log(msg: str) -> None:
    line = f"[{utc_now()}] {msg}"
    print(line, flush=True)
    try:
        WD_LOG.parent.mkdir(parents=True, exist_ok=True)
        with WD_LOG.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, indent=2, default=str), encoding="utf-8")
    tmp.replace(path)


def read_state() -> Dict[str, Any]:
    if not STATE_PATH.exists():
        return {}
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"_error": "unreadable_state"}


def pid_alive(pid: Any) -> bool:
    try:
        p = int(pid)
    except Exception:
        return False
    if p <= 0:
        return False
    try:
        # Windows-friendly
        out = subprocess.run(
            ["tasklist", "/FI", f"PID eq {p}", "/NH"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        return str(p) in (out.stdout or "")
    except Exception:
        try:
            os.kill(p, 0)
            return True
        except Exception:
            return False


def read_pid_file() -> Optional[int]:
    if not PID_PATH.exists():
        return None
    try:
        t = PID_PATH.read_text(encoding="utf-8").strip().splitlines()[0].strip()
        return int(t)
    except Exception:
        return None


def parse_ts(s: Any) -> Optional[datetime]:
    if not s:
        return None
    try:
        t = str(s).replace("Z", "+00:00")
        dt = datetime.fromisoformat(t)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def age_min(ts: Any) -> Optional[float]:
    dt = parse_ts(ts)
    if not dt:
        return None
    return (datetime.now(timezone.utc) - dt.astimezone(timezone.utc)).total_seconds() / 60.0


def notify(title: str, body: str, level: str = "info") -> None:
    """User-facing notify — only when something matters."""
    MEAS.mkdir(exist_ok=True)
    stamp = utc_now()
    block = f"""# Aetheria notify — {title}

- **When:** {stamp}
- **Level:** {level}

{body}

---
_Auto-written by lh_watchdog. Safe to ignore if already handled. Delete this file to clear._
"""
    # Append if exists so we don't clobber history of issues
    prev = ""
    if NOTIFY.exists():
        try:
            prev = NOTIFY.read_text(encoding="utf-8")
        except Exception:
            prev = ""
    NOTIFY.write_text(block + "\n" + prev[:8000], encoding="utf-8")
    log(f"NOTIFY [{level}] {title}")
    try:
        from living.aetheria_canon import write_hope_status

        write_hope_status(
            {
                "notify": {
                    "title": title,
                    "level": level,
                    "ts": stamp,
                    "file": str(NOTIFY),
                }
            }
        )
    except Exception:
        pass


def relaunch_lh(cycles: int = 2, interval_min: float = 30.0, max_ticks: int = 0) -> Tuple[bool, str]:
    """Relaunch long horizon. Success = long_horizon.pid alive (P1), not just PS return.

    Default max_ticks=48 rolling segment (P2), not single-PID 200 heroics.
    """
    if LH_STOP.exists():
        return False, "lh_stop_file_present_not_relaunching"
    launch = ROOT / "scripts" / "launch_long_horizon.ps1"
    # P2: rolling segment default
    mt = max_ticks if max_ticks > 0 else 48
    args = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(launch),
        "-Cycles",
        str(cycles),
        "-IntervalMin",
        str(interval_min),
        "-MaxTicks",
        str(mt),
    ]
    out = ""
    timed_out = False
    try:
        # P1: allow slow launch; do not treat timeout alone as failure
        r = subprocess.run(args, cwd=str(ROOT), capture_output=True, text=True, timeout=180)
        out = (r.stdout or "") + (r.stderr or "")
        log(f"relaunch rc={r.returncode} out={out[:400]}")
    except subprocess.TimeoutExpired as e:
        timed_out = True
        out = f"timeout_180s partial={(e.stdout or b'')[:200]!r}"
        log(f"relaunch powershell timed out (will poll pid): {out[:200]}")
    except Exception as e:
        out = str(e)[:400]
        log(f"relaunch exception: {out}")

    # P1: poll pid file — success if supervisor is alive
    detail_parts = [out[:300] if out else ""]
    if timed_out:
        detail_parts.append("powershell_timeout_ignored_if_pid_alive")
    for i in range(40):  # up to ~120s
        pid = read_pid_file()
        if pid is not None and pid_alive(pid):
            msg = f"ok pid={pid} poll={i} max_ticks={mt} " + " ".join(detail_parts)
            log(f"relaunch success: {msg[:300]}")
            return True, msg[:500]
        time.sleep(3)
    pid = read_pid_file()
    return False, f"pid_not_alive after launch pid={pid} mt={mt} " + " ".join(detail_parts)[:300]


def diagnose() -> Dict[str, Any]:
    state = read_state()
    pid = state.get("pid") or read_pid_file()
    alive = pid_alive(pid) if pid else False
    status = state.get("status")
    hb_age = age_min(state.get("heartbeat_at") or state.get("updated_at"))
    tick_age = age_min(state.get("last_tick_finished"))
    last_ok = state.get("last_ok")
    action = "none"
    reason = "healthy"

    if LH_STOP.exists():
        action = "none"
        reason = "user_stop_file"
    elif not alive:
        if status in ("completed_max_ticks", "completed_once", "stopped_by_file"):
            if status == "stopped_by_file" or LH_STOP.exists():
                action = "none"
                reason = f"exited_{status}"
            else:
                action = "relaunch"
                reason = f"exited_{status}"
        elif status in ("degraded",) and last_ok is False:
            action = "relaunch"
            reason = "dead_after_degraded"
        else:
            action = "relaunch"
            reason = "pid_dead"
    elif status == "running_tick" and hb_age is not None and hb_age > RUNNING_STUCK_MIN:
        # updated_at set at tick start; if stuck >25m in running_tick → kill+relaunch
        action = "kill_relaunch"
        reason = f"running_tick_stuck_{hb_age:.1f}m"
    elif status == "idle_between_ticks" and hb_age is not None and hb_age > HEARTBEAT_STALE_MIN:
        action = "kill_relaunch"
        reason = f"heartbeat_stale_{hb_age:.1f}m"
    elif last_ok is False and status == "degraded":
        action = "notify_only"
        reason = "last_tick_failed_alive"
    else:
        action = "none"
        reason = "healthy"

    return {
        "ts": utc_now(),
        "pid": pid,
        "alive": alive,
        "status": status,
        "tick": state.get("tick"),
        "last_ok": last_ok,
        "last_final_mom": state.get("last_final_mom"),
        "hb_age_min": hb_age,
        "tick_age_min": tick_age,
        "action": action,
        "reason": reason,
        "interval_min": state.get("interval_min"),
        "max_ticks": state.get("max_ticks"),
        "lh_stop": LH_STOP.exists(),
    }


def kill_pid(pid: Any) -> None:
    try:
        p = int(pid)
        subprocess.run(["taskkill", "/PID", str(p), "/F"], capture_output=True, timeout=30)
        log(f"killed pid={p}")
    except Exception as e:
        log(f"kill note: {e}")


def apply_action(diag: Dict[str, Any]) -> Dict[str, Any]:
    action = diag.get("action")
    result = {"action": action, "ok": True, "detail": ""}
    if action == "none":
        return result
    if action == "notify_only":
        notify(
            "Long-horizon tick failed",
            f"Supervisor still alive (pid={diag.get('pid')}) but last_ok=false.\n\n"
            f"- tick: {diag.get('tick')}\n"
            f"- reason: {diag.get('reason')}\n"
            f"- Check: `measurements/long_horizon_state.json` and latest `logs/lh_probe_tick*`\n\n"
            "Watchdog will keep monitoring; Grok will repair on next session if it persists.",
            level="warn",
        )
        result["detail"] = "notified"
        return result
    if action in ("relaunch", "kill_relaunch"):
        if action == "kill_relaunch" and diag.get("alive") and diag.get("pid"):
            kill_pid(diag.get("pid"))
            time.sleep(2)
        ok, detail = relaunch_lh()
        result["ok"] = ok
        result["detail"] = detail
        if ok:
            notify(
                "Long-horizon relaunched",
                f"Watchdog action `{action}` reason `{diag.get('reason')}`.\n\n"
                f"New run started. State: `measurements/long_horizon_state.json`.\n"
                f"Detail: {detail[:300]}",
                level="info",
            )
        else:
            notify(
                "Long-horizon relaunch FAILED",
                f"Watchdog could not relaunch.\n\n- reason: {diag.get('reason')}\n"
                f"- detail: {detail}\n\n"
                "Need human or Grok session: `powershell -File scripts\\launch_long_horizon.ps1`",
                level="critical",
            )
        return result
    return result


def hope_patch(diag: Dict[str, Any], applied: Dict[str, Any]) -> None:
    try:
        from living.aetheria_canon import write_hope_status

        write_hope_status(
            {
                "watchdog": {
                    "ts": utc_now(),
                    "alive_lh": diag.get("alive"),
                    "lh_pid": diag.get("pid"),
                    "action": applied.get("action"),
                    "reason": diag.get("reason"),
                    "last_ok": diag.get("last_ok"),
                    "tick": diag.get("tick"),
                    "mom": diag.get("last_final_mom"),
                    "status_file": str(WD_STATUS),
                    "notify_file": str(NOTIFY),
                }
            }
        )
    except Exception as e:
        log(f"hope patch note: {e}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval-sec", type=float, default=60.0)
    ap.add_argument("--once", action="store_true")
    args = ap.parse_args()

    MEAS.mkdir(exist_ok=True)
    (ROOT / "logs").mkdir(exist_ok=True)
    if WD_STOP.exists():
        try:
            WD_STOP.unlink()
        except Exception:
            pass
    WD_PID.write_text(str(os.getpid()), encoding="utf-8")
    log(f"WATCHDOG START pid={os.getpid()} interval={args.interval_sec}s")

    last_action_key = ""
    while True:
        if WD_STOP.exists():
            log("watchdog STOP file — exit")
            break
        try:
            diag = diagnose()
            # Debounce identical relaunch loops
            key = f"{diag.get('action')}|{diag.get('reason')}|{diag.get('pid')}|{diag.get('tick')}"
            applied = {"action": "none", "ok": True, "detail": "skipped_debounce"}
            if diag.get("action") != "none":
                if key != last_action_key or diag.get("action") == "notify_only":
                    applied = apply_action(diag)
                    last_action_key = key
                    if diag.get("action") in ("relaunch", "kill_relaunch"):
                        time.sleep(POST_EXIT_RELAUNCH_DELAY_S)
                else:
                    applied = {"action": "none", "ok": True, "detail": "debounced"}
            else:
                last_action_key = ""

            status = {
                "schema": "lh_watchdog_v1",
                "watchdog_pid": os.getpid(),
                "log": str(WD_LOG),
                "diag": diag,
                "last_applied": applied,
                "updated_at": utc_now(),
                "mandate": "full_autonomy_velocity; notify only as needed",
            }
            write_json(WD_STATUS, status)
            hope_patch(diag, applied)
            log(
                f"tick={diag.get('tick')} alive={diag.get('alive')} status={diag.get('status')} "
                f"ok={diag.get('last_ok')} action={diag.get('action')}/{applied.get('action')} "
                f"reason={diag.get('reason')}"
            )
        except Exception as e:
            log(f"watchdog loop error: {e}\n{traceback.format_exc()[-400:]}")
            try:
                write_json(
                    WD_STATUS,
                    {"error": str(e)[:300], "updated_at": utc_now(), "watchdog_pid": os.getpid()},
                )
            except Exception:
                pass

        if args.once:
            break
        # responsive stop
        end = time.time() + max(15.0, float(args.interval_sec))
        while time.time() < end:
            if WD_STOP.exists():
                break
            time.sleep(min(5.0, end - time.time()))

    try:
        WD_PID.unlink()
    except Exception:
        pass
    log("WATCHDOG EXIT")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
