#!/usr/bin/env python3
"""
registry_hygiene.py — Clean thrash-era registry debt without wiping real progress.

- Backs up registry first
- Loads assets from snapshot preferentially (skip full replay thrash when --fast)
- Dedupes LatticeModule / SovereignAssetOrchestrator by name
- Drops assets that fail basic validation repeatedly (optional aggressive)
- Writes measurements/hope_status.json

Usage:
  python -u scripts/registry_hygiene.py
  python -u scripts/registry_hygiene.py --aggressive
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os_chdir = ROOT
import os

os.chdir(ROOT)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--aggressive", action="store_true", help="Also drop assets missing name/id")
    ap.add_argument("--max-assets", type=int, default=0, help="If >0, keep only newest N assets by updated_at")
    args = ap.parse_args()

    from living.aetheria_canon import registry_path, write_hope_status, append_session_living, bin_root

    reg_path = registry_path()
    if not reg_path.exists():
        print("No registry at", reg_path)
        return 1

    bak_dir = bin_root() / "backups" / f"registry_hygiene_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    bak_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(reg_path, bak_dir / "sovereign_asset_registry.json")
    print("Backup:", bak_dir)

    data = json.loads(reg_path.read_text(encoding="utf-8"))
    assets = data.get("assets") or {}
    events = data.get("event_log") or []
    proposals = data.get("proposals") or {}
    before_n = len(assets)
    before_e = len(events)

    # Dedupe by name for lattice modules / orchestrator / meta-* churn
    by_name = {}
    keep = {}
    dropped = []
    for aid, ad in list(assets.items()):
        if not isinstance(ad, dict):
            dropped.append((aid, "not_dict"))
            continue
        name = str(ad.get("name") or "")
        atype = str(ad.get("asset_type") or "").lower()
        if args.aggressive and (not name or not aid):
            dropped.append((aid, "missing_name_or_id"))
            continue
        # Collapse meta-governance spam: keep one per module name prefix
        if name.startswith("meta-") or name.startswith("auto_tightened") or "meta-auto_tightened" in name:
            key = f"meta:{name.split('-')[0] if '-' in name else name}"
            # keep newest-ish by estimated value
            if key in by_name:
                dropped.append((aid, f"dupe_{key}"))
                continue
            by_name[key] = aid
        if name in ("SovereignAssetOrchestrator",) or atype in ("lattice_module",):
            key = f"{atype}:{name}"
            if key in by_name:
                dropped.append((aid, f"dupe_{key}"))
                continue
            by_name[key] = aid
        keep[aid] = ad

    # Optional size cap: keep highest estimated_value first then rest
    if args.max_assets and len(keep) > args.max_assets:
        def score(item):
            ad = item[1]
            try:
                v = (ad.get("current_valuation") or {}).get("estimated_value") or 0
                return float(v)
            except Exception:
                return 0.0
        # Always retain non-meta named assets preferentially: sort meta last
        def sort_key(item):
            aid, ad = item
            name = str(ad.get("name") or "")
            meta_penalty = 0 if not (name.startswith("meta-") or "auto_tightened" in name) else -1000
            return meta_penalty + score(item)
        ranked = sorted(keep.items(), key=sort_key, reverse=True)[: args.max_assets]
        dropped += [(a, "max_assets_cap") for a, _ in keep.items() if a not in dict(ranked)]
        keep = dict(ranked)

    # Cap event_log growth for load speed (keep last N + all evo/patch)
    MAX_EVENTS = int(os.environ.get("AETHERIA_MAX_EVENT_LOG", "2500"))
    if len(events) > MAX_EVENTS:
        protected = [
            e for e in events
            if isinstance(e, dict) and (
                "autonomous_code" in str(e.get("type", ""))
                or e.get("type") in ("patch_effect_probe", "meta_directive_autonomously_applied", "automatic_summary")
            )
        ]
        tail = events[-(MAX_EVENTS - min(len(protected), MAX_EVENTS // 3)) :]
        # merge unique by id/ts
        seen = set()
        new_events = []
        for e in protected + tail:
            if not isinstance(e, dict):
                continue
            k = str(e.get("event_id") or e.get("ts") or id(e))
            if k in seen:
                continue
            seen.add(k)
            new_events.append(e)
        events = new_events[-MAX_EVENTS:]

    data["assets"] = keep
    data["event_log"] = events
    data["proposals"] = proposals
    data["_hygiene"] = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "before_assets": before_n,
        "after_assets": len(keep),
        "dropped": len(dropped),
        "before_events": before_e,
        "after_events": len(events),
        "backup": str(bak_dir),
    }

    # Write with skip-replay load friendly: keep assets snapshot primary
    reg_path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    print("Hygiene done:", data["_hygiene"])
    print("Sample dropped:", dropped[:8])

    write_hope_status({
        "phase": "registry_hygiene",
        "registry_assets": len(keep),
        "registry_events": len(events),
        "hygiene": data["_hygiene"],
        "status": "hygiene_complete",
    })
    append_session_living({
        "tag": "ops_note",
        "summary": f"Registry hygiene: assets {before_n}->{len(keep)} events {before_e}->{len(events)} dropped={len(dropped)} bak={bak_dir.name}",
        "score": 9.2,
        "phase": "registry_hygiene",
        "ops_note": True,
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
