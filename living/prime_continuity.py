#!/usr/bin/env python3
"""
prime_continuity.py — Aetheria Prime Release 1 local core.

Grok Bot spec: docs/AETHERIA_PRIME_SPEC.md
Live mapping: docs/AETHERIA_PRIME_PLAN_MAP.md

Implements, plant-safe:
  Draft Manager     — temp analysis; no execution, no ledger write
  Commit/Policy Gate — exact text + content hash; propose ≠ authorize
  Event Ledger      — append-only hash chain + idempotency
  Artifact store    — content-addressed blobs
  Local FTS search  — rebuildable SQLite index of docs (not living memory)
  Checkpoints       — durable head snapshot
  Handoff export    — inspectable package
  Network mode      — recorded; default offline_only

Does NOT parent long-horizon plant, call web/Tor/remote models,
replace living jsonl, or start FastAPI/React.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

SCHEMA_EVENT = "aetheria_prime_event_v1"
SCHEMA_DRAFT = "aetheria_prime_draft_v1"
SCHEMA_WORKSPACE = "aetheria_prime_workspace_v1"
SCHEMA_CHECKPOINT = "aetheria_prime_checkpoint_v1"
SCHEMA_ARTIFACT = "aetheria_prime_artifact_v1"
GENESIS_PREV = "0" * 64

NETWORK_MODES = ("offline_only", "direct_https", "tor_preferred", "tor_only")
NETWORK_ACTIONS = frozenset(
    {
        "web_search",
        "remote_model",
        "send_external",
        "peer_node",
        "tor_route",
    }
)
MUTATING_ACTIONS = frozenset(
    {
        "modify_file",
        "apply_edit",
        "run_command",
        "send_external",
    }
)

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DEFAULT_STORE = ROOT / "measurements" / "prime"


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canon_bytes(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode(
        "utf-8"
    )


def content_hash(obj: Any) -> str:
    return hashlib.sha256(_canon_bytes(obj)).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


class PrimeError(Exception):
    """Base error for Prime continuity."""


class HashMismatchError(PrimeError):
    """Ledger chain integrity failure — fail closed."""


class PolicyDenied(PrimeError):
    """Action blocked by commit/policy/network gate."""


class DuplicateIdempotency(PrimeError):
    """Ledger rejected a duplicate idempotency key."""


class DraftError(PrimeError):
    """Draft missing or invalid."""


@dataclass
class Event:
    event_id: str
    event_type: str
    workspace_id: str
    actor: str
    payload: Dict[str, Any]
    provenance: Dict[str, Any]
    status: str
    created_at: str
    prev_hash: str
    event_hash: str = ""
    idempotency_key: str = ""
    schema: str = SCHEMA_EVENT

    def payload_for_hash(self) -> Dict[str, Any]:
        return {
            "actor": self.actor,
            "created_at": self.created_at,
            "event_id": self.event_id,
            "event_type": self.event_type,
            "idempotency_key": self.idempotency_key,
            "payload": self.payload,
            "prev_hash": self.prev_hash,
            "provenance": self.provenance,
            "schema": self.schema,
            "status": self.status,
            "workspace_id": self.workspace_id,
        }

    def seal(self) -> "Event":
        self.event_hash = content_hash(self.payload_for_hash())
        return self

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Event":
        return cls(
            event_id=str(d["event_id"]),
            event_type=str(d["event_type"]),
            workspace_id=str(d["workspace_id"]),
            actor=str(d.get("actor") or "system"),
            payload=dict(d.get("payload") or {}),
            provenance=dict(d.get("provenance") or {}),
            status=str(d.get("status") or "committed"),
            created_at=str(d.get("created_at") or _utc()),
            prev_hash=str(d.get("prev_hash") or GENESIS_PREV),
            event_hash=str(d.get("event_hash") or ""),
            idempotency_key=str(d.get("idempotency_key") or ""),
            schema=str(d.get("schema") or SCHEMA_EVENT),
        )


@dataclass
class Draft:
    draft_id: str
    text: str
    content_hash: str
    created_at: str
    updated_at: str
    analysis: Dict[str, Any] = field(default_factory=dict)
    schema: str = SCHEMA_DRAFT

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Draft":
        return cls(
            draft_id=str(d["draft_id"]),
            text=str(d.get("text") or ""),
            content_hash=str(d.get("content_hash") or ""),
            created_at=str(d.get("created_at") or _utc()),
            updated_at=str(d.get("updated_at") or _utc()),
            analysis=dict(d.get("analysis") or {}),
            schema=str(d.get("schema") or SCHEMA_DRAFT),
        )


def classify_intents(text: str) -> List[str]:
    t = (text or "").lower()
    intents: List[str] = []
    if re.search(r"\b(compare|research|evidence|source|cite|paper)\b", t):
        intents.append("research")
    if re.search(r"\b(implement|fix|build|apply|edit|patch)\b", t):
        intents.append("build")
    if re.search(r"\b(status|health|plant|resume|hold)\b", t):
        intents.append("observe")
    if re.search(r"\b(search the web|look up online|browse)\b", t):
        intents.append("web_search")
    if not intents:
        intents.append("note")
    return intents


def propose_actions(text: str, intents: List[str]) -> List[Dict[str, Any]]:
    actions: List[Dict[str, Any]] = []
    if "research" in intents or "note" in intents:
        actions.append(
            {
                "action_id": "act_" + uuid.uuid4().hex[:12],
                "kind": "local_search",
                "status": "proposed",
                "summary": "Search local docs/measurements for matching files",
            }
        )
    if "web_search" in intents:
        actions.append(
            {
                "action_id": "act_" + uuid.uuid4().hex[:12],
                "kind": "web_search",
                "status": "proposed",
                "summary": "Web retrieval (requires network mode + authorize)",
            }
        )
    if "build" in intents:
        actions.append(
            {
                "action_id": "act_" + uuid.uuid4().hex[:12],
                "kind": "apply_edit",
                "status": "proposed",
                "summary": "File mutation (requires explicit authorize; not auto)",
            }
        )
    return actions


def analyze_draft_text(text: str, *, file_hints: Optional[List[str]] = None) -> Dict[str, Any]:
    """Local-only draft analysis. Must not execute, network, or commit."""
    intents = classify_intents(text)
    ambiguous = bool(re.search(r"\?|\b(maybe|might|unsure|or not)\b", text or "", re.I))
    sensitive = bool(
        re.search(r"(?i)(api[_-]?key|password|secret|authorization:\s*bearer)", text or "")
    )
    return {
        "intents": intents,
        "task_type": intents[0] if intents else "note",
        "ambiguous": ambiguous,
        "sensitive": sensitive,
        "suggested_files": list(file_hints or []),
        "executed": False,
        "network": False,
        "durable": False,
        "label": "draft_analysis_not_a_fact",
    }


def _local_file_hints(text: str, search_roots: List[Path], *, limit: int = 8) -> List[str]:
    words = [w for w in re.findall(r"[A-Za-z]{4,}", text or "") if w.lower() not in {"this", "that", "with", "from", "have"}]
    if not words:
        return []
    lowered = [w.lower() for w in words[:12]]
    hits: List[str] = []
    for root in search_roots:
        if not root.is_dir():
            continue
        try:
            for p in root.rglob("*"):
                if not p.is_file():
                    continue
                if p.suffix.lower() not in {".md", ".txt", ".json", ".py"}:
                    continue
                name = p.name.lower()
                if any(w in name for w in lowered):
                    hits.append(str(p))
                    if len(hits) >= limit:
                        return hits
        except OSError:
            continue
    return hits


class PrimeWorkspace:
    """One local workspace. Default store: measurements/prime. Inject root in tests."""

    def __init__(
        self,
        *,
        store: Optional[Path] = None,
        workspace_id: str = "default",
        search_roots: Optional[List[Path]] = None,
    ) -> None:
        self.store = Path(store) if store else DEFAULT_STORE
        self.workspace_id = workspace_id
        # Default: docs only. measurements/ holds operator notes; do not index them unless asked.
        self.search_roots = search_roots or [ROOT / "docs"]
        self._lock = threading.Lock()
        self._events: List[Event] = []
        self._idempotency: Dict[str, str] = {}
        self._actions: Dict[str, Dict[str, Any]] = {}
        self.store.mkdir(parents=True, exist_ok=True)
        (self.store / "drafts").mkdir(exist_ok=True)
        (self.store / "artifacts").mkdir(exist_ok=True)
        (self.store / "checkpoints").mkdir(exist_ok=True)
        (self.store / "handoffs").mkdir(exist_ok=True)
        self._ensure_workspace_file()
        self._load_ledger()

    # --- paths ---

    @property
    def ledger_path(self) -> Path:
        return self.store / "ledger.jsonl"

    @property
    def workspace_path(self) -> Path:
        return self.store / "workspace.json"

    @property
    def artifact_index_path(self) -> Path:
        return self.store / "artifacts" / "index.json"

    def _ensure_workspace_file(self) -> None:
        if self.workspace_path.is_file():
            return
        _atomic_write(
            self.workspace_path,
            json.dumps(
                {
                    "schema": SCHEMA_WORKSPACE,
                    "workspace_id": self.workspace_id,
                    "network_mode": "offline_only",
                    "created_at": _utc(),
                    "parents_lh": False,
                    "policy": {
                        "draft_cannot_execute": True,
                        "submit_is_not_authorize": True,
                        "mutations_need_authorize": True,
                    },
                },
                indent=2,
            )
            + "\n",
        )

    def workspace_meta(self) -> Dict[str, Any]:
        try:
            return json.loads(self.workspace_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"workspace_id": self.workspace_id, "network_mode": "offline_only"}

    def network_mode(self) -> str:
        mode = str(self.workspace_meta().get("network_mode") or "offline_only")
        return mode if mode in NETWORK_MODES else "offline_only"

    def set_network_mode(self, mode: str, *, actor: str = "user") -> Event:
        if mode not in NETWORK_MODES:
            raise PolicyDenied(f"unknown network mode: {mode}")
        meta = self.workspace_meta()
        prev = meta.get("network_mode")
        meta["network_mode"] = mode
        meta["updated_at"] = _utc()
        _atomic_write(self.workspace_path, json.dumps(meta, indent=2) + "\n")
        return self.append_event(
            "workspace.network_mode",
            {"from": prev, "to": mode},
            actor=actor,
            idempotency_key=f"netmode:{mode}:{meta['updated_at']}",
        )

    # --- ledger ---

    def _load_ledger(self) -> None:
        self._events = []
        self._idempotency = {}
        self._actions = {}
        if not self.ledger_path.is_file():
            return
        prev = GENESIS_PREV
        with self.ledger_path.open("r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                ev = Event.from_dict(json.loads(line))
                expected = content_hash(ev.payload_for_hash())
                if ev.event_hash != expected:
                    raise HashMismatchError(
                        f"ledger line {line_no}: stored hash mismatch event_id={ev.event_id}"
                    )
                if ev.prev_hash != prev:
                    raise HashMismatchError(
                        f"ledger line {line_no}: prev_hash mismatch event_id={ev.event_id}"
                    )
                prev = ev.event_hash
                self._events.append(ev)
                if ev.idempotency_key:
                    self._idempotency[ev.idempotency_key] = ev.event_id
                for act in ev.payload.get("actions") or []:
                    if isinstance(act, dict) and act.get("action_id"):
                        self._actions[str(act["action_id"])] = dict(act)
                single = ev.payload.get("action")
                if isinstance(single, dict) and single.get("action_id"):
                    self._actions[str(single["action_id"])] = dict(single)

    def verify_ledger(self) -> bool:
        with self._lock:
            prev = GENESIS_PREV
            for ev in self._events:
                if ev.prev_hash != prev:
                    return False
                if ev.event_hash != content_hash(ev.payload_for_hash()):
                    return False
                prev = ev.event_hash
            return True

    def events(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [e.to_dict() for e in self._events]

    def head_hash(self) -> str:
        with self._lock:
            return self._events[-1].event_hash if self._events else GENESIS_PREV

    def append_event(
        self,
        event_type: str,
        payload: Optional[Dict[str, Any]] = None,
        *,
        actor: str = "system",
        status: str = "committed",
        provenance: Optional[Dict[str, Any]] = None,
        idempotency_key: Optional[str] = None,
    ) -> Event:
        with self._lock:
            key = idempotency_key or f"{event_type}:{uuid.uuid4().hex}"
            if key in self._idempotency:
                raise DuplicateIdempotency(f"duplicate idempotency_key={key}")
            prev = self._events[-1].event_hash if self._events else GENESIS_PREV
            ev = Event(
                event_id="evt_" + uuid.uuid4().hex,
                event_type=event_type,
                workspace_id=self.workspace_id,
                actor=actor,
                payload=dict(payload or {}),
                provenance=dict(provenance or {"source": "prime_continuity"}),
                status=status,
                created_at=_utc(),
                prev_hash=prev,
                idempotency_key=key,
            ).seal()
            with self.ledger_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(ev.to_dict(), sort_keys=True, ensure_ascii=False) + "\n")
                f.flush()
            self._events.append(ev)
            self._idempotency[key] = ev.event_id
            return ev

    # --- drafts (temp; not ledger) ---

    def _draft_path(self, draft_id: str) -> Path:
        return self.store / "drafts" / f"{draft_id}.json"

    def draft_create(self, text: str) -> Draft:
        now = _utc()
        body = text if text is not None else ""
        d = Draft(
            draft_id="dft_" + uuid.uuid4().hex[:16],
            text=body,
            content_hash=sha256_bytes(body.encode("utf-8")),
            created_at=now,
            updated_at=now,
        )
        _atomic_write(self._draft_path(d.draft_id), json.dumps(d.to_dict(), indent=2) + "\n")
        return d

    def draft_load(self, draft_id: str) -> Draft:
        p = self._draft_path(draft_id)
        if not p.is_file():
            raise DraftError(f"no draft {draft_id}")
        return Draft.from_dict(json.loads(p.read_text(encoding="utf-8")))

    def draft_update(self, draft_id: str, text: str) -> Draft:
        d = self.draft_load(draft_id)
        d.text = text if text is not None else ""
        d.content_hash = sha256_bytes(d.text.encode("utf-8"))
        d.updated_at = _utc()
        d.analysis = {}
        _atomic_write(self._draft_path(draft_id), json.dumps(d.to_dict(), indent=2) + "\n")
        return d

    def draft_analyze(self, draft_id: str) -> Draft:
        """Local analysis only. Does not append ledger, network, or execute."""
        d = self.draft_load(draft_id)
        hints = _local_file_hints(d.text, self.search_roots)
        d.analysis = analyze_draft_text(d.text, file_hints=hints)
        d.updated_at = _utc()
        _atomic_write(self._draft_path(draft_id), json.dumps(d.to_dict(), indent=2) + "\n")
        return d

    def draft_discard(self, draft_id: str) -> None:
        p = self._draft_path(draft_id)
        if p.is_file():
            p.unlink()

    def active_draft_id(self) -> Optional[str]:
        drafts = sorted((self.store / "drafts").glob("dft_*.json"), key=lambda p: p.stat().st_mtime)
        return drafts[-1].stem if drafts else None

    # --- local search (rebuildable index; not living truth) ---

    @property
    def search_db_path(self) -> Path:
        return self.store / "search.sqlite"

    def _skip_path(self, p: Path) -> bool:
        try:
            p.resolve().relative_to(self.store.resolve())
            return True
        except ValueError:
            pass
        skip = {
            ".venv",
            "backups",
            "__pycache__",
            "g4_adapters",
            "node_modules",
            ".git",
            "handoffs",
            "artifacts",
            "drafts",
            "checkpoints",
        }
        return any(part.lower() in skip for part in p.parts)

    def _iter_indexable(self) -> List[Path]:
        out: List[Path] = []
        for root in self.search_roots:
            if not root.is_dir():
                continue
            try:
                for p in root.rglob("*"):
                    if not p.is_file():
                        continue
                    if self._skip_path(p):
                        continue
                    if p.suffix.lower() not in {".md", ".txt"}:
                        continue
                    try:
                        if p.stat().st_size > 1_000_000:
                            continue
                    except OSError:
                        continue
                    out.append(p)
            except OSError:
                continue
        return out

    def index_local_sources(self, *, record_event: bool = True) -> Dict[str, Any]:
        """Rebuild FTS/LIKE index from search_roots. Does not read living jsonl."""
        conn = sqlite3.connect(str(self.search_db_path))
        try:
            conn.execute("DROP TABLE IF EXISTS docs")
            fts = True
            try:
                # path/hash stored but not searchable — otherwise every "Aetheria_*.md" matches "Aetheria"
                conn.execute(
                    "CREATE VIRTUAL TABLE docs USING fts5(path UNINDEXED, title, body, hash UNINDEXED)"
                )
            except sqlite3.OperationalError:
                fts = False
                conn.execute(
                    "CREATE TABLE docs (path TEXT PRIMARY KEY, title TEXT, body TEXT, hash TEXT)"
                )
            n = 0
            for p in self._iter_indexable():
                try:
                    raw = p.read_bytes()
                except OSError:
                    continue
                try:
                    body = raw.decode("utf-8", errors="replace")
                except Exception:
                    continue
                rec_hash = sha256_bytes(raw)
                title = p.stem
                if fts:
                    conn.execute(
                        "INSERT INTO docs(path, title, body, hash) VALUES (?, ?, ?, ?)",
                        (str(p), title, body, rec_hash),
                    )
                else:
                    conn.execute(
                        "INSERT OR REPLACE INTO docs(path, title, body, hash) VALUES (?, ?, ?, ?)",
                        (str(p), title, body, rec_hash),
                    )
                n += 1
            conn.commit()
        finally:
            conn.close()
        info = {
            "indexed": n,
            "db": str(self.search_db_path),
            "fts5": True,
            "living_indexed": False,
        }
        # Detect fts from a probe
        conn = sqlite3.connect(str(self.search_db_path))
        try:
            row = conn.execute(
                "SELECT sql FROM sqlite_master WHERE name='docs'"
            ).fetchone()
            info["fts5"] = bool(row and row[0] and "fts5" in row[0].lower())
        finally:
            conn.close()
        if record_event:
            try:
                self.append_event(
                    "source.retrieved",
                    {"kind": "local_index", "indexed": n, "fts5": info["fts5"]},
                    actor="system",
                    idempotency_key=f"index:{_utc()}",
                )
            except DuplicateIdempotency:
                pass
        return info

    def search_local(self, query: str, *, limit: int = 10) -> List[Dict[str, Any]]:
        if not self.search_db_path.is_file():
            self.index_local_sources(record_event=False)
        terms = re.findall(r"[A-Za-z0-9_]{2,}", query or "")
        if not terms:
            return []
        strong = [t for t in terms if len(t) >= 4][:6] or terms[:6]
        conn = sqlite3.connect(str(self.search_db_path))
        hits: List[Dict[str, Any]] = []
        try:
            row = conn.execute("SELECT sql FROM sqlite_master WHERE name='docs'").fetchone()
            use_fts = bool(row and row[0] and "fts5" in (row[0] or "").lower())
            fetched: List[Any] = []
            if use_fts:
                try:
                    fetched = conn.execute(
                        "SELECT path, title, hash, snippet(docs, 2, '', '', '…', 16) "
                        "FROM docs WHERE docs MATCH ? LIMIT ?",
                        (" AND ".join(strong), int(limit)),
                    ).fetchall()
                    if not fetched:
                        fetched = conn.execute(
                            "SELECT path, title, hash, snippet(docs, 2, '', '', '…', 16) "
                            "FROM docs WHERE docs MATCH ? LIMIT ?",
                            (" OR ".join(strong), int(limit)),
                        ).fetchall()
                except sqlite3.OperationalError:
                    use_fts = False
            if not use_fts:
                like = "%" + "%".join(strong) + "%"
                fetched = conn.execute(
                    "SELECT path, title, hash, substr(body, 1, 160) "
                    "FROM docs WHERE body LIKE ? OR title LIKE ? LIMIT ?",
                    (like, like, int(limit)),
                ).fetchall()
            for path, title, rec_hash, snip in fetched:
                hits.append(
                    {
                        "path": path,
                        "title": title,
                        "content_hash": f"sha256:{rec_hash}",
                        "snippet": snip or "",
                    }
                )
        finally:
            conn.close()
        return hits

    # --- commit gate ---

    def submit(
        self,
        draft_id: str,
        *,
        actor: str = "user",
        authorize_actions: bool = False,
    ) -> Dict[str, Any]:
        d = self.draft_load(draft_id)
        if not d.analysis:
            d = self.draft_analyze(draft_id)
        exact = d.text
        text_hash = sha256_bytes(exact.encode("utf-8"))
        intents = list(d.analysis.get("intents") or classify_intents(exact))
        actions = propose_actions(exact, intents)
        for act in actions:
            self._actions[act["action_id"]] = dict(act)
        ev = self.append_event(
            "message.submitted",
            {
                "text": exact,
                "content_hash": text_hash,
                "draft_id": draft_id,
                "intents": intents,
                "actions": actions,
                "authorize_actions": False,
                "labels": {
                    "user_statement": True,
                    "model_assertion": False,
                    "executed": False,
                },
            },
            actor=actor,
            provenance={"source": "submit", "draft_id": draft_id},
            idempotency_key=f"submit:{draft_id}:{text_hash}",
        )
        authorized: List[Dict[str, Any]] = []
        if authorize_actions:
            for act in actions:
                try:
                    authorized.append(self.authorize(act["action_id"], actor=actor))
                except PolicyDenied as e:
                    authorized.append({"action_id": act["action_id"], "denied": str(e)})
        self.draft_discard(draft_id)
        return {
            "event": ev.to_dict(),
            "actions": actions,
            "authorized": authorized,
            "executed": False if not authorize_actions else any(
                isinstance(a, dict) and a.get("status") == "completed" for a in authorized
            ),
        }

    def _policy_check(self, action: Dict[str, Any]) -> None:
        kind = str(action.get("kind") or "")
        if kind in NETWORK_ACTIONS and self.network_mode() == "offline_only":
            raise PolicyDenied(f"network action {kind} blocked in offline_only")
        if kind in NETWORK_ACTIONS and self.network_mode() == "tor_only":
            # Route not implemented — refuse rather than pretend.
            raise PolicyDenied(f"network action {kind} requires a Tor route that is not implemented")
        if kind in MUTATING_ACTIONS:
            # Mutations are never implied by submit; authorize is explicit but still
            # refused here until companion_safe_build is the executor (not this module).
            raise PolicyDenied(
                f"mutating action {kind} is not executed by prime_continuity; "
                "use companion /propose /apply --yes"
            )

    def authorize(self, action_id: str, *, actor: str = "user") -> Dict[str, Any]:
        action = self._actions.get(action_id)
        if not action:
            raise PolicyDenied(f"unknown action {action_id}")
        self._policy_check(action)
        kind = str(action.get("kind") or "")
        result: Dict[str, Any] = {"ok": True, "kind": kind}
        if kind == "local_search":
            query = ""
            for ev in reversed(self._events):
                if ev.event_type == "message.submitted":
                    query = str(ev.payload.get("text") or "")
                    break
            hits = self.search_local(query)
            sources = [
                {
                    "path": h["path"],
                    "title": h["title"],
                    "content_hash": h["content_hash"],
                    "retrieval_method": "local_fts",
                    "source_type": "local_file",
                }
                for h in hits
            ]
            art = self.put_artifact(
                "tool_result",
                json.dumps({"query": query, "hits": hits, "sources": sources}, indent=2).encode(
                    "utf-8"
                ),
                media_type="application/json",
            )
            if sources:
                self.append_event(
                    "source.discovered",
                    {"query": query, "sources": sources},
                    actor=actor,
                    idempotency_key=f"src:{action_id}",
                )
            result["hits"] = hits
            result["sources"] = sources
            result["artifact_id"] = art["artifact_id"]
        else:
            raise PolicyDenied(f"no executor for {kind}")
        action = dict(action)
        action["status"] = "completed"
        action["result"] = {k: v for k, v in result.items() if k != "hits"}
        self._actions[action_id] = action
        ev = self.append_event(
            "action.authorized",
            {"action": action, "result": result},
            actor=actor,
            provenance={"source": "authorize", "action_id": action_id},
            idempotency_key=f"auth:{action_id}",
        )
        result["event_id"] = ev.event_id
        result["status"] = "completed"
        result["action_id"] = action_id
        return result

    def reject(self, action_id: str, *, actor: str = "user") -> Event:
        action = self._actions.get(action_id)
        if not action:
            raise PolicyDenied(f"unknown action {action_id}")
        action = dict(action)
        action["status"] = "rejected"
        self._actions[action_id] = action
        return self.append_event(
            "action.rejected",
            {"action": action},
            actor=actor,
            idempotency_key=f"rej:{action_id}",
        )

    # --- artifacts ---

    def put_artifact(
        self,
        kind: str,
        data: bytes,
        *,
        media_type: str = "application/octet-stream",
    ) -> Dict[str, Any]:
        digest = sha256_bytes(data)
        blob = self.store / "artifacts" / f"sha256_{digest}"
        if not blob.is_file():
            tmp = blob.with_suffix(".tmp")
            tmp.write_bytes(data)
            tmp.replace(blob)
        rec = {
            "schema": SCHEMA_ARTIFACT,
            "artifact_id": f"art_{digest[:16]}",
            "kind": kind,
            "media_type": media_type,
            "content_hash": f"sha256:{digest}",
            "path": str(blob),
            "bytes": len(data),
            "created_at": _utc(),
        }
        index = {}
        if self.artifact_index_path.is_file():
            try:
                index = json.loads(self.artifact_index_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                index = {}
        items = dict(index.get("items") or {})
        existed = rec["artifact_id"] in items
        items[rec["artifact_id"]] = rec
        _atomic_write(
            self.artifact_index_path,
            json.dumps({"schema": SCHEMA_ARTIFACT, "items": items}, indent=2) + "\n",
        )
        if not existed:
            try:
                self.append_event(
                    "artifact.created",
                    {
                        k: rec[k]
                        for k in ("artifact_id", "kind", "content_hash", "bytes", "media_type")
                    },
                    actor="system",
                    idempotency_key=f"art:{digest}",
                )
            except DuplicateIdempotency:
                pass
        return rec

    def get_artifact(self, artifact_id: str) -> Tuple[Dict[str, Any], bytes]:
        index = json.loads(self.artifact_index_path.read_text(encoding="utf-8"))
        rec = (index.get("items") or {}).get(artifact_id)
        if not rec:
            raise PrimeError(f"no artifact {artifact_id}")
        data = Path(rec["path"]).read_bytes()
        expect = str(rec.get("content_hash") or "").split(":", 1)[-1]
        if sha256_bytes(data) != expect:
            raise HashMismatchError(f"artifact {artifact_id} content hash mismatch")
        return rec, data

    # --- checkpoint / handoff / replay ---

    def checkpoint(self) -> Dict[str, Any]:
        snap = {
            "schema": SCHEMA_CHECKPOINT,
            "workspace_id": self.workspace_id,
            "created_at": _utc(),
            "head_hash": self.head_hash(),
            "event_count": len(self._events),
            "network_mode": self.network_mode(),
            "parents_lh": False,
            "last_event_id": self._events[-1].event_id if self._events else None,
        }
        latest = self.store / "checkpoints" / "latest.json"
        stamped = self.store / "checkpoints" / f"ckpt_{snap['created_at'].replace(':', '').replace('+', '_')}.json"
        text = json.dumps(snap, indent=2) + "\n"
        _atomic_write(latest, text)
        _atomic_write(stamped, text)
        self.append_event(
            "checkpoint.created",
            {"head_hash": snap["head_hash"], "event_count": snap["event_count"]},
            actor="system",
            idempotency_key=f"ckpt:{snap['created_at']}",
        )
        return snap

    def export_handoff(self, out_dir: Optional[Path] = None) -> Path:
        snap = self.checkpoint()
        dest = Path(out_dir) if out_dir else (self.store / "handoffs" / f"handoff_{snap['created_at'][:19].replace(':', '')}")
        dest.mkdir(parents=True, exist_ok=True)
        ledger_copy = (dest / "audit-log.jsonl")
        if self.ledger_path.is_file():
            ledger_copy.write_bytes(self.ledger_path.read_bytes())
        else:
            ledger_copy.write_text("", encoding="utf-8")
        _atomic_write(dest / "checkpoint.json", json.dumps(snap, indent=2) + "\n")
        events = self.events()
        manifest_items = []
        for name in ("HANDOFF.md", "checkpoint.json", "audit-log.jsonl", "manifest.json"):
            p = dest / name
            if name == "HANDOFF.md":
                continue
            if p.is_file():
                raw = p.read_bytes()
                manifest_items.append(
                    {
                        "path": name,
                        "content_hash": f"sha256:{sha256_bytes(raw)}",
                        "bytes": len(raw),
                    }
                )
        _atomic_write(
            dest / "manifest.json",
            json.dumps(
                {
                    "schema": "aetheria_prime_handoff_manifest_v1",
                    "workspace_id": self.workspace_id,
                    "head_hash": snap["head_hash"],
                    "event_count": snap["event_count"],
                    "created_at": snap["created_at"],
                    "items": manifest_items,
                },
                indent=2,
            )
            + "\n",
        )
        last_types = [e["event_type"] for e in events[-8:]]
        pending = [a for a in self._actions.values() if a.get("status") == "proposed"]
        md = "\n".join(
            [
                "# Aetheria Prime handoff",
                "",
                f"- workspace: `{self.workspace_id}`",
                f"- created_at: `{snap['created_at']}`",
                f"- head_hash: `{snap['head_hash']}`",
                f"- events: {snap['event_count']}",
                f"- network_mode: `{self.network_mode()}`",
                f"- parents_lh: false",
                f"- last event types: {', '.join(last_types) or '(none)'}",
                f"- proposed actions still open: {len(pending)}",
                "",
                "Restart: `python -u scripts/prime_continuity.py replay`",
                "Plant is not started by this package.",
                "",
            ]
        )
        _atomic_write(dest / "HANDOFF.md", md)
        self.append_event(
            "handoff.exported",
            {"path": str(dest), "head_hash": snap["head_hash"]},
            actor="system",
            idempotency_key=f"handoff:{snap['created_at']}",
        )
        return dest

    def replay(self) -> Dict[str, Any]:
        """Reload ledger from disk and re-verify. Does not re-execute actions."""
        with self._lock:
            self._load_ledger()
            ok = True
            prev = GENESIS_PREV
            for ev in self._events:
                if ev.prev_hash != prev or ev.event_hash != content_hash(ev.payload_for_hash()):
                    ok = False
                    break
                prev = ev.event_hash
        return {
            "ok": ok,
            "event_count": len(self._events),
            "head_hash": self.head_hash(),
            "network_mode": self.network_mode(),
            "reexecuted": False,
            "parents_lh": False,
        }

    def status(self) -> Dict[str, Any]:
        drafts = list((self.store / "drafts").glob("dft_*.json"))
        return {
            "ok": True,
            "workspace_id": self.workspace_id,
            "store": str(self.store),
            "network_mode": self.network_mode(),
            "event_count": len(self._events),
            "head_hash": self.head_hash(),
            "open_drafts": len(drafts),
            "proposed_actions": sum(1 for a in self._actions.values() if a.get("status") == "proposed"),
            "chain_ok": self.verify_ledger(),
            "parents_lh": False,
        }


def default_workspace() -> PrimeWorkspace:
    return PrimeWorkspace()
