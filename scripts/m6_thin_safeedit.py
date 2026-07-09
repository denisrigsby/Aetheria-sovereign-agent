#!/usr/bin/env python3
"""
Measured self-edit demo on a disposable sandbox file.

Uses the orchestrator guarded-edit path (when available). Prefer running while
the long-horizon supervisor is idle to avoid registry contention.

Usage:
  python -u scripts/m6_thin_safeedit.py
  python -u scripts/m6_thin_safeedit.py --force
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

SANDBOX = ROOT / "living" / "m6_sandbox_target.py"
OLD = 'M6_SANDBOX_VERSION = "1"'
NEW = 'M6_SANDBOX_VERSION = "2"'
DESC = "M6 thin residual: sandbox version 1->2 via SafeEdit (disposable target)"


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def lh_busy() -> bool:
    p = ROOT / "measurements" / "long_horizon_state.json"
    if not p.exists():
        return False
    try:
        st = json.loads(p.read_text(encoding="utf-8"))
        return st.get("status") == "running_tick"
    except Exception:
        return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    if not args.force and lh_busy():
        print("LH running_tick — defer M6 (use --force to override)")
        return 2

    if not SANDBOX.exists():
        print("sandbox missing", SANDBOX)
        return 1

    text = SANDBOX.read_text(encoding="utf-8")
    if OLD not in text:
        # already promoted or drifted
        if 'M6_SANDBOX_VERSION = "2"' in text:
            print("already at version 2 — M6 sandbox previously applied")
            out = {
                "ok": True,
                "already": True,
                "disk_edited": False,
                "ts": utc(),
            }
        else:
            print("old_string not found; sandbox drifted")
            out = {"ok": False, "error": "old_string_missing", "ts": utc()}
            (ROOT / "measurements" / "m6_thin_safeedit_latest.json").write_text(
                json.dumps(out, indent=2), encoding="utf-8"
            )
            return 1
    else:
        os.environ.setdefault("AETHERIA_LIGHT_MANAGE", "1")
        os.environ.setdefault("AETHERIA_SKIP_FINAL_RECON", "1")
        os.environ.setdefault("AETHERIA_META_RECON", "0")

        import living.sovereign_asset_orchestrator as m

        m._orchestrator_instance = None
        from living.sovereign_asset_orchestrator import get_sovereign_asset_orchestrator

        o = get_sovereign_asset_orchestrator()
        # Prefer absolute path so SafeEdit resolves correctly
        target = str(SANDBOX.resolve())
        edited, pre_h, post_h = o._safe_autonomous_edit(target, OLD, NEW, DESC)
        # Count recent autonomous_code_patch events
        autop = sum(
            1
            for e in o.registry.event_log
            if "autonomous_code" in str(e.get("type", ""))
            or e.get("type") == "meta_directive_autonomously_applied"
        )
        try:
            o.registry.save()
        except Exception:
            try:
                # common alternate
                if hasattr(o.registry, "persist"):
                    o.registry.persist()
            except Exception:
                pass

        post_text = SANDBOX.read_text(encoding="utf-8")
        ver2 = 'M6_SANDBOX_VERSION = "2"' in post_text
        out = {
            "ok": bool(edited and ver2),
            "disk_edited": bool(edited),
            "version2_on_disk": ver2,
            "target": target,
            "description": DESC,
            "pre_hash": (pre_h or {}).get("source_hash") if isinstance(pre_h, dict) else None,
            "post_hash": (post_h or {}).get("source_hash") if isinstance(post_h, dict) else None,
            "autop_events_approx": autop,
            "ts": utc(),
        }
        print(json.dumps(out, indent=2))

    meas = ROOT / "measurements"
    meas.mkdir(exist_ok=True)
    (meas / "m6_thin_safeedit_latest.json").write_text(json.dumps(out, indent=2), encoding="utf-8")

    try:
        from living.aetheria_canon import write_hope_status, append_session_living

        write_hope_status(
            {
                "M6_thin": out,
                "scorecard_note": "M6 thin sandbox residual attempted",
            }
        )
        if out.get("ok"):
            append_session_living(
                {
                    "tag": "ops_note",
                    "summary": f"M6 thin SafeEdit SUCCESS disk_edited={out.get('disk_edited')} sandbox v1->v2.",
                    "score": 9.7,
                    "phase": "m6_thin_safeedit",
                    "ops_note": True,
                }
            )
    except Exception as e:
        print("hope note", e)

    return 0 if out.get("ok") or out.get("already") else 1


if __name__ == "__main__":
    raise SystemExit(main())
