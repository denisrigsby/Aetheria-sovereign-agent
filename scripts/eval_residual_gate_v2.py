#!/usr/bin/env python3
"""Evaluate change-control gate v2. Exit 0 if OPEN, 1 if closed, 2 if error.

Gate A counts successful supervisor ticks after the last recorded change from:
  - current long_horizon_state.history (this process segment)
  - durable measurements/gate_a_green_ticks.jsonl (survives process restart)

Optional: operators may record a last-change timestamp in RESUME_STATE or
measurement result files listed below. Without those, A uses all green ticks.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GATE_A_LOG = ROOT / "measurements" / "gate_a_green_ticks.jsonl"
GATE_A_SNAP = ROOT / "measurements" / "gate_a_progress.json"
LH_STATE = ROOT / "measurements" / "long_horizon_state.json"


def parse_dt(s):
    if not s:
        return None
    s = str(s).strip().replace("Z", "+00:00")
    # PowerShell often emits 7-digit fractional seconds — trim to microseconds
    if "." in s and ("+" in s[s.find(".") :] or s.endswith("+00:00")):
        head, rest = s.split(".", 1)
        for sign in ("+", "-"):
            if sign in rest[1:]:
                frac, tz = rest.split(sign, 1)
                tz = sign + tz
                break
        else:
            frac, tz = rest, ""
        frac = "".join(ch for ch in frac if ch.isdigit())[:6].ljust(6, "0")
        s = f"{head}.{frac}{tz}"
    try:
        return datetime.fromisoformat(s)
    except Exception:
        try:
            return datetime.strptime(str(s)[:19], "%Y-%m-%d %H:%M:%S")
        except Exception:
            return None


def record_green_tick(ts: str, tick, ok: bool, pid=None) -> None:
    """Append one green tick to durable log (no-op if not ok). Survives supervisor restart."""
    if not (ok is True or str(ok) == "True"):
        return
    GATE_A_LOG.parent.mkdir(parents=True, exist_ok=True)
    row = {"ts": ts, "tick": tick, "ok": True, "pid": pid}
    with GATE_A_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    # trim large logs
    try:
        lines = GATE_A_LOG.read_text(encoding="utf-8").splitlines()
        if len(lines) > 800:
            GATE_A_LOG.write_text("\n".join(lines[-500:]) + "\n", encoding="utf-8")
    except Exception:
        pass


def seed_durable_from_history(history) -> int:
    """If durable log empty, seed from current LH history greens (one-time bootstrap)."""
    if GATE_A_LOG.exists() and GATE_A_LOG.stat().st_size > 0:
        return 0
    n = 0
    for h in history or []:
        ok = h.get("ok") is True or str(h.get("ok")) == "True"
        if ok and h.get("ts"):
            record_green_tick(h.get("ts"), h.get("tick"), True, pid=None)
            n += 1
    return n


def collect_green_after(cut, history) -> tuple[int, list]:
    """Union of durable + in-memory history green ticks after cut. Dedup by ts."""
    events = {}
    for h in history or []:
        ok = h.get("ok") is True or str(h.get("ok")) == "True"
        ht = parse_dt(h.get("ts"))
        if not ok or not h.get("ts"):
            continue
        if cut is None or (ht and ht > cut):
            events[str(h.get("ts"))] = {"ts": h.get("ts"), "tick": h.get("tick"), "src": "history"}
    if GATE_A_LOG.exists():
        for line in GATE_A_LOG.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                o = json.loads(line)
            except Exception:
                continue
            ok = o.get("ok") is True or str(o.get("ok")) == "True"
            ht = parse_dt(o.get("ts"))
            if not ok or not o.get("ts"):
                continue
            if cut is None or (ht and ht > cut):
                key = str(o.get("ts"))
                if key not in events:
                    events[key] = {"ts": o.get("ts"), "tick": o.get("tick"), "src": "durable"}
    # sort by time
    items = sorted(events.values(), key=lambda x: parse_dt(x["ts"]) or datetime.min)
    return len(items), items


def resolve_last_residual_ts(resume: dict) -> str | None:
    candidates_ts = []
    lr = (resume.get("last_residual") or {}).get("ts")
    if lr:
        candidates_ts.append(lr)
    for rel in (
        "measurements/last_change_latest.json",
        "measurements/m6_thin_safeedit_latest.json",
        "measurements/m6_firmer_safeedit_latest.json",
        "measurements/m6_autopilot_safeedit_latest.json",
        "measurements/green_gated_hold_residual_latest.json",
    ):
        p = ROOT / rel
        if p.exists():
            try:
                o = json.loads(p.read_text(encoding="utf-8"))
                if not o.get("ts"):
                    continue
                # Prefer completed change records when present
                if o.get("ran") is False:
                    continue
                if o.get("ok") is False:
                    continue
                candidates_ts.append(o["ts"])
            except Exception:
                pass
    last_ts = None
    best = None
    for t in candidates_ts:
        dt = parse_dt(t)
        if dt and (best is None or dt > best):
            best = dt
            last_ts = t
    return last_ts


def main():
    lh = json.loads((ROOT / "measurements/long_horizon_state.json").read_text(encoding="utf-8"))
    resume = json.loads((ROOT / "RESUME_STATE.json").read_text(encoding="utf-8"))
    sb = json.loads((ROOT / "measurements/RARE_PATTERN_SCOREBOARD.json").read_text(encoding="utf-8"))

    # Bootstrap durable log once from current history
    seed_durable_from_history(lh.get("history") or [])

    last_ts = resolve_last_residual_ts(resume)
    cut = parse_dt(last_ts)
    since, items = collect_green_after(cut, lh.get("history") or [])

    # Snapshot for operators / restart debugging
    try:
        GATE_A_SNAP.write_text(
            json.dumps(
                {
                    "schema": "gate_a_progress_v1",
                    "last_residual_ts": last_ts,
                    "post_residual_green_ticks": since,
                    "needed": 4,
                    "durable_log": str(GATE_A_LOG.relative_to(ROOT)),
                    "sources": "history_union_durable_jsonl",
                    "tail": items[-8:],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    except Exception:
        pass

    cands = [p for p in sb.get("patterns") or [] if p.get("next_residual_candidate")]
    A = since >= 4
    B = len(cands) >= 1
    C = True
    out = {
        "A": A,
        "B": B,
        "C": C,
        "OPEN": A and B and C,
        "post_residual_green_ticks": since,
        "needed": 4,
        "candidates": [c.get("id") for c in cands],
        "last_residual_ts": last_ts,
        "lh_tick": lh.get("tick"),
        "lh_last_ok": lh.get("last_ok"),
        "gate_a_source": "history_union_durable_jsonl",
        "mode": "residual_allowed" if (A and B and C) else "hold",
    }
    print(json.dumps(out, indent=2))
    (ROOT / "measurements/gate_v2_eval_latest.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    return 0 if out["OPEN"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
