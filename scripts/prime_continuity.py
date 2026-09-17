#!/usr/bin/env python3
"""
CLI for Aetheria Prime Release 1 continuity core.

  python -u scripts/prime_continuity.py status
  python -u scripts/prime_continuity.py draft "question text"
  python -u scripts/prime_continuity.py analyze
  python -u scripts/prime_continuity.py submit
  python -u scripts/prime_continuity.py authorize <action_id>
  python -u scripts/prime_continuity.py reject <action_id>
  python -u scripts/prime_continuity.py checkpoint
  python -u scripts/prime_continuity.py handoff
  python -u scripts/prime_continuity.py verify
  python -u scripts/prime_continuity.py replay
  python -u scripts/prime_continuity.py network [offline_only|direct_https|tor_preferred|tor_only]
  python -u scripts/prime_continuity.py index
  python -u scripts/prime_continuity.py search "local-first"
  python -u scripts/prime_continuity.py events

Never parents the long-horizon plant.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _ws():
    from living.prime_continuity import PrimeWorkspace

    return PrimeWorkspace()


def _print(obj) -> int:
    print(json.dumps(obj, indent=2, default=str))
    return 0


def cmd_status(_: argparse.Namespace) -> int:
    return _print(_ws().status())


def cmd_draft(ns: argparse.Namespace) -> int:
    text = ns.text if ns.text is not None else sys.stdin.read()
    d = _ws().draft_create(text)
    return _print(d.to_dict())


def cmd_analyze(ns: argparse.Namespace) -> int:
    ws = _ws()
    draft_id = ns.draft_id or ws.active_draft_id()
    if not draft_id:
        print("no draft", file=sys.stderr)
        return 1
    d = ws.draft_analyze(draft_id)
    assert d.analysis.get("executed") is False
    return _print(d.to_dict())


def cmd_submit(ns: argparse.Namespace) -> int:
    ws = _ws()
    draft_id = ns.draft_id or ws.active_draft_id()
    if not draft_id:
        print("no draft", file=sys.stderr)
        return 1
    return _print(ws.submit(draft_id, authorize_actions=bool(ns.authorize)))


def cmd_authorize(ns: argparse.Namespace) -> int:
    return _print(_ws().authorize(ns.action_id))


def cmd_reject(ns: argparse.Namespace) -> int:
    ev = _ws().reject(ns.action_id)
    return _print(ev.to_dict())


def cmd_checkpoint(_: argparse.Namespace) -> int:
    return _print(_ws().checkpoint())


def cmd_handoff(ns: argparse.Namespace) -> int:
    dest = _ws().export_handoff(Path(ns.out) if ns.out else None)
    return _print({"ok": True, "path": str(dest)})


def cmd_verify(_: argparse.Namespace) -> int:
    ws = _ws()
    ok = ws.verify_ledger()
    _print({"ok": ok, "head_hash": ws.head_hash(), "event_count": len(ws.events())})
    return 0 if ok else 2


def cmd_replay(_: argparse.Namespace) -> int:
    r = _ws().replay()
    _print(r)
    return 0 if r.get("ok") else 2


def cmd_network(ns: argparse.Namespace) -> int:
    ws = _ws()
    if ns.mode:
        ev = ws.set_network_mode(ns.mode)
        return _print(ev.to_dict())
    return _print({"network_mode": ws.network_mode()})


def cmd_index(_: argparse.Namespace) -> int:
    return _print(_ws().index_local_sources())


def cmd_search(ns: argparse.Namespace) -> int:
    hits = _ws().search_local(ns.query, limit=int(ns.limit))
    return _print({"ok": True, "n": len(hits), "hits": hits})


def cmd_events(ns: argparse.Namespace) -> int:
    evs = _ws().events()
    n = int(ns.limit)
    slim = [
        {
            "event_id": e["event_id"],
            "event_type": e["event_type"],
            "created_at": e["created_at"],
            "event_hash": e["event_hash"],
            "status": e["status"],
        }
        for e in evs[-n:]
    ]
    return _print({"ok": True, "n": len(evs), "shown": len(slim), "events": slim})


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Aetheria Prime continuity (Release 1). Does not start plant.")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status")
    d = sub.add_parser("draft")
    d.add_argument("text", nargs="?", default=None)
    a = sub.add_parser("analyze")
    a.add_argument("--draft-id", dest="draft_id", default=None)
    s = sub.add_parser("submit")
    s.add_argument("--draft-id", dest="draft_id", default=None)
    s.add_argument("--authorize", action="store_true", help="also authorize proposed actions (local_search only)")
    au = sub.add_parser("authorize")
    au.add_argument("action_id")
    rj = sub.add_parser("reject")
    rj.add_argument("action_id")
    sub.add_parser("checkpoint")
    h = sub.add_parser("handoff")
    h.add_argument("--out", default=None)
    sub.add_parser("verify")
    sub.add_parser("replay")
    n = sub.add_parser("network")
    n.add_argument("mode", nargs="?", default=None)
    sub.add_parser("index")
    se = sub.add_parser("search")
    se.add_argument("query")
    se.add_argument("--limit", default=10)
    evp = sub.add_parser("events")
    evp.add_argument("--limit", default=20)

    ns = p.parse_args(argv)
    fn = {
        "status": cmd_status,
        "draft": cmd_draft,
        "analyze": cmd_analyze,
        "submit": cmd_submit,
        "authorize": cmd_authorize,
        "reject": cmd_reject,
        "checkpoint": cmd_checkpoint,
        "handoff": cmd_handoff,
        "verify": cmd_verify,
        "replay": cmd_replay,
        "network": cmd_network,
        "index": cmd_index,
        "search": cmd_search,
        "events": cmd_events,
    }[ns.cmd]
    try:
        return fn(ns)
    except Exception as e:
        print(f"{type(e).__name__}: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
