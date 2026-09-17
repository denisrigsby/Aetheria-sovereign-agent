#!/usr/bin/env python3
"""Release 1 Prime continuity: draft never executes; ledger hashes; restart replay."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from living.prime_continuity import (  # noqa: E402
    GENESIS_PREV,
    DuplicateIdempotency,
    PolicyDenied,
    PrimeWorkspace,
)


def _ws(tmp_path: Path) -> PrimeWorkspace:
    return PrimeWorkspace(
        store=tmp_path / "prime",
        workspace_id="test",
        search_roots=[ROOT / "docs"],
    )


def test_draft_analyze_does_not_touch_ledger(tmp_path: Path):
    ws = _ws(tmp_path)
    d = ws.draft_create("Compare local-first AI architectures for Aetheria Prime")
    before = len(ws.events())
    analyzed = ws.draft_analyze(d.draft_id)
    assert analyzed.analysis["executed"] is False
    assert analyzed.analysis["network"] is False
    assert analyzed.analysis["durable"] is False
    assert "research" in analyzed.analysis["intents"]
    assert len(ws.events()) == before
    assert ws.ledger_path.exists() is False or ws.ledger_path.read_text(encoding="utf-8") == ""


def test_submit_commits_exact_text_and_hash_chain(tmp_path: Path):
    ws = _ws(tmp_path)
    text = "Preserve evidence, decisions, artifacts, state, and lineage."
    d = ws.draft_create(text)
    out = ws.submit(d.draft_id)
    ev = out["event"]
    assert ev["event_type"] == "message.submitted"
    assert ev["payload"]["text"] == text
    assert ev["payload"]["labels"]["executed"] is False
    assert ev["prev_hash"] == GENESIS_PREV
    assert ev["event_hash"]
    assert out["executed"] is False
    assert ws.verify_ledger() is True
    # draft discarded
    with pytest.raises(Exception):
        ws.draft_load(d.draft_id)


def test_duplicate_idempotency_rejected(tmp_path: Path):
    ws = _ws(tmp_path)
    ws.append_event("workspace.created", {"n": 1}, idempotency_key="once")
    with pytest.raises(DuplicateIdempotency):
        ws.append_event("workspace.created", {"n": 2}, idempotency_key="once")
    assert len(ws.events()) == 1


def test_offline_blocks_web_search_authorize(tmp_path: Path):
    ws = _ws(tmp_path)
    d = ws.draft_create("please search the web for local-first AI papers")
    out = ws.submit(d.draft_id)
    web = next(a for a in out["actions"] if a["kind"] == "web_search")
    assert ws.network_mode() == "offline_only"
    with pytest.raises(PolicyDenied):
        ws.authorize(web["action_id"])
    # reject is allowed
    ev = ws.reject(web["action_id"])
    assert ev.event_type == "action.rejected"


def test_authorize_local_search_writes_artifact(tmp_path: Path):
    ws = _ws(tmp_path)
    d = ws.draft_create("Compare architectures and cite evidence from STANDALONE_PRODUCT")
    out = ws.submit(d.draft_id)
    local = next(a for a in out["actions"] if a["kind"] == "local_search")
    result = ws.authorize(local["action_id"])
    assert result["status"] == "completed"
    assert result["kind"] == "local_search"
    rec, data = ws.get_artifact(result["artifact_id"])
    body = json.loads(data.decode("utf-8"))
    assert "hits" in body
    assert rec["content_hash"].startswith("sha256:")


def test_mutating_action_not_executed_here(tmp_path: Path):
    ws = _ws(tmp_path)
    d = ws.draft_create("please implement and apply a patch to the workbench")
    out = ws.submit(d.draft_id)
    build = next(a for a in out["actions"] if a["kind"] == "apply_edit")
    with pytest.raises(PolicyDenied):
        ws.authorize(build["action_id"])


def test_checkpoint_survives_new_instance_replay(tmp_path: Path):
    store = tmp_path / "prime"
    ws = PrimeWorkspace(store=store, workspace_id="test", search_roots=[ROOT / "docs"])
    d = ws.draft_create("Ask a question and continue later.")
    ws.submit(d.draft_id)
    snap = ws.checkpoint()
    head = snap["head_hash"]
    n = snap["event_count"]
    # new process / new object
    ws2 = PrimeWorkspace(store=store, workspace_id="test", search_roots=[ROOT / "docs"])
    replay = ws2.replay()
    assert replay["ok"] is True
    assert replay["reexecuted"] is False
    assert replay["event_count"] == n + 1  # checkpoint.created
    assert ws2.verify_ledger() is True
    assert ws2.head_hash() != GENESIS_PREV
    # original committed message still present
    types = [e["event_type"] for e in ws2.events()]
    assert "message.submitted" in types
    assert "checkpoint.created" in types
    # head from snap is an ancestor, not necessarily latest
    hashes = [e["event_hash"] for e in ws2.events()]
    assert head in hashes


def test_handoff_package_contains_required_files(tmp_path: Path):
    ws = _ws(tmp_path)
    d = ws.draft_create("Export a complete inspectable handoff package.")
    ws.submit(d.draft_id)
    dest = ws.export_handoff(tmp_path / "out")
    for name in ("HANDOFF.md", "checkpoint.json", "audit-log.jsonl", "manifest.json"):
        assert (dest / name).is_file(), name
    ck = json.loads((dest / "checkpoint.json").read_text(encoding="utf-8"))
    man = json.loads((dest / "manifest.json").read_text(encoding="utf-8"))
    assert ck["parents_lh"] is False
    assert man["head_hash"] == ck["head_hash"]
    md = (dest / "HANDOFF.md").read_text(encoding="utf-8")
    assert "parents_lh: false" in md


def test_replay_restores_authorized_action_status(tmp_path: Path):
    store = tmp_path / "prime"
    ws = PrimeWorkspace(store=store, workspace_id="test", search_roots=[ROOT / "docs"])
    d = ws.draft_create("Compare architectures in STANDALONE_PRODUCT")
    out = ws.submit(d.draft_id)
    local = next(a for a in out["actions"] if a["kind"] == "local_search")
    ws.authorize(local["action_id"])
    ws2 = PrimeWorkspace(store=store, workspace_id="test", search_roots=[ROOT / "docs"])
    restored = ws2._actions[local["action_id"]]
    assert restored["status"] == "completed"


def test_local_fts_indexes_body_not_living(tmp_path: Path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "alpha.md").write_text(
        "Aetheria Prime preserves evidence, decisions, artifacts, state, and lineage.\n",
        encoding="utf-8",
    )
    (docs / "noise.md").write_text("unrelated gardening notes\n", encoding="utf-8")
    living = tmp_path / "living"
    living.mkdir()
    (living / "personal_living.jsonl").write_text('{"secret":"should-not-index"}\n', encoding="utf-8")
    ws = PrimeWorkspace(store=tmp_path / "prime", workspace_id="test", search_roots=[docs, living])
    info = ws.index_local_sources(record_event=False)
    assert info["indexed"] == 2
    assert info["living_indexed"] is False
    hits = ws.search_local("lineage evidence")
    paths = [h["path"] for h in hits]
    assert any(p.endswith("alpha.md") for p in paths)
    assert not any("personal_living" in p for p in paths)
    assert hits[0]["content_hash"].startswith("sha256:")


def test_fts_does_not_match_path_only(tmp_path: Path):
    docs = tmp_path / "Aetheria_folder"
    docs.mkdir()
    (docs / "notes.md").write_text("pumpkin harvest calendar\n", encoding="utf-8")
    (docs / "other.md").write_text("lineage and evidence belong here\n", encoding="utf-8")
    ws = PrimeWorkspace(store=tmp_path / "prime", workspace_id="test", search_roots=[docs])
    ws.index_local_sources(record_event=False)
    pumpkin = ws.search_local("pumpkin")
    assert any(h["path"].endswith("notes.md") for h in pumpkin)
    aetheria_hits = ws.search_local("Aetheria")
    assert aetheria_hits == []


def test_tampered_ledger_fails_closed(tmp_path: Path):
    ws = _ws(tmp_path)
    ws.append_event("workspace.created", {"ok": True}, idempotency_key="w1")
    raw = ws.ledger_path.read_text(encoding="utf-8")
    tampered = raw.replace('"ok": true', '"ok": false', 1)
    ws.ledger_path.write_text(tampered, encoding="utf-8")
    from living.prime_continuity import HashMismatchError

    with pytest.raises(HashMismatchError):
        PrimeWorkspace(store=tmp_path / "prime", workspace_id="test")
