# Setup

## Requirements

| Item | Notes |
|------|--------|
| OS | Windows is the reference platform (PowerShell launchers) |
| Python | 3.10+ |
| PowerShell | 5.1+; PowerShell 7+ recommended |
| Full install | Orchestrator, registry, and cycle probe modules (not in this repo) |

## Full install vs this repository

This repository publishes the **control plane**:

- Supervisor / watchdog / hope-path scripts
- Path helpers and a disposable sandbox edit target
- Documentation and example status shapes

Scripts import runtime modules that belong to a **complete local Aetheria tree**. You typically either:

1. Clone this repo into (or overlay onto) that tree, or  
2. Copy `scripts/` and `living/` helpers into an existing root.

Without those modules, some imports fail **by design**. The control plane still documents process supervision clearly for review and partial reuse.

## Environment

```powershell
$env:AETHERIA_LIGHT_MANAGE = "1"
$env:AETHERIA_SKIP_FINAL_RECON = "1"
$env:AETHERIA_HEAVY_HEALTH_CYCLES = "6,12"
$env:AETHERIA_META_RECON = "0"
```

Optional: `AETHERIA_BIN_ROOT`, `AETHERIA_LIVING_PATH`.

## Smoke test

```powershell
cd <AETHERIA_ROOT>

# Syntax / structure (works on this repo alone)
python -m compileall -q scripts living

# Runtime health (needs full install)
python -u scripts/aetheria_hope_path.py --health-only
python -u scripts/aetheria_hope_path.py --cycles 2
```

## Next steps

- [docs/OPERATIONS.md](docs/OPERATIONS.md) — start detached schedule + watchdog  
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — process model  
- [docs/INTERNALS.md](docs/INTERNALS.md) — continuity files and change policy  
