# Prime continuity (Release 1)

Optional local evidence/continuity core. It does **not** start the long-horizon plant, parent chat, or replace living jsonl.

Design source: [AETHERIA_PRIME_SPEC.md](AETHERIA_PRIME_SPEC.md) (full spec; most of it is not built).

## What is implemented

| Piece | Behavior |
|-------|----------|
| Draft | Temp text. Analyze locally. No ledger write, no execute, no network. |
| Submit | Commits **exact** text + content hash. Propose ≠ authorize. |
| Ledger | Append-only JSONL, `prev_hash` chain, idempotency keys. Tamper fails closed. |
| Artifacts | Content-addressed blobs (`sha256_…`). |
| Local search | Rebuildable SQLite FTS over `docs/` (not living dumps). Path is stored, not searched. |
| Checkpoint / replay | Reload from disk without re-executing actions. |
| Handoff | `HANDOFF.md` + `checkpoint.json` + `audit-log.jsonl` + `manifest.json`. |
| Network mode | Default `offline_only`. Web search is proposed, then **blocked** until mode + authorize. |

## What is not implemented

FastAPI/React UI, web retrieval, claim spans, model broker, trusted nodes, Tor as a route, companion chat routed through this ledger.

## Run

```text
python -u scripts/prime_continuity.py status
python -u scripts/prime_continuity.py draft "your question"
python -u scripts/prime_continuity.py analyze
python -u scripts/prime_continuity.py submit
python -u scripts/prime_continuity.py index
python -u scripts/prime_continuity.py search "local-first"
python -u scripts/prime_continuity.py events
python -u scripts/prime_continuity.py checkpoint
python -u scripts/prime_continuity.py verify
```

Runtime files stay under `measurements/prime/` and are gitignored (ledger, search index, drafts, artifacts). Do not commit them.

Tests: `python -m pytest tests/test_prime_continuity.py -q`
