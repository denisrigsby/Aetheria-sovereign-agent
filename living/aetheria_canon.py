#!/usr/bin/env python3
"""
Path helpers and status-file writer for Aetheria.

Relative to install root:
  living/personal_living.jsonl   — long-term living stream
  personal_living.jsonl          — session overlay
  measurements/hope_status.json  — operator status window

Env:
  AETHERIA_LIVING_PATH
  AETHERIA_BIN_ROOT
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


def bin_root() -> Path:
    env = os.environ.get("AETHERIA_BIN_ROOT", "").strip()
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[1]


def living_stream_path() -> Path:
    """Primary living stream for this install."""
    env = os.environ.get("AETHERIA_LIVING_PATH", "").strip()
    if env:
        p = Path(env)
        p.parent.mkdir(parents=True, exist_ok=True)
        return p
    p = bin_root() / "living" / "personal_living.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


# Back-compat alias used by older callers
def organism_living_path() -> Path:
    return living_stream_path()


def session_living_path() -> Path:
    p = bin_root() / "personal_living.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def hope_status_path() -> Path:
    p = bin_root() / "measurements" / "hope_status.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def registry_path() -> Path:
    return bin_root() / "sovereign_asset_registry.json"


def write_hope_status(update: Dict[str, Any], merge: bool = True) -> Path:
    """Write operator status JSON (merge by default)."""
    path = hope_status_path()
    cur: Dict[str, Any] = {}
    if merge and path.exists():
        try:
            cur = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            cur = {}
    cur.update(update or {})
    cur["updated_at"] = datetime.now(timezone.utc).isoformat()
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(cur, indent=2, default=str), encoding="utf-8")
    tmp.replace(path)
    return path


def append_session_living(entry: Dict[str, Any]) -> None:
    entry = dict(entry)
    entry.setdefault("ts", datetime.now(timezone.utc).isoformat())
    with session_living_path().open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def append_living_stream(entry: Dict[str, Any]) -> None:
    entry = dict(entry)
    entry.setdefault("ts", datetime.now(timezone.utc).isoformat())
    p = living_stream_path()
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# Back-compat
def append_organism_living(entry: Dict[str, Any]) -> None:
    append_living_stream(entry)


def canon_report() -> Dict[str, Any]:
    ol = living_stream_path()
    sl = session_living_path()
    rp = registry_path()
    return {
        "bin_root": str(bin_root()),
        "living_stream": str(ol),
        "living_stream_exists": ol.exists(),
        "living_stream_mb": round(ol.stat().st_size / 1e6, 2) if ol.exists() else 0,
        "session_living": str(sl),
        "session_living_exists": sl.exists(),
        "registry": str(rp),
        "registry_exists": rp.exists(),
        "hope_status": str(hope_status_path()),
        # legacy keys
        "organism_living": str(ol),
        "organism_living_exists": ol.exists(),
        "organism_living_mb": round(ol.stat().st_size / 1e6, 2) if ol.exists() else 0,
    }
