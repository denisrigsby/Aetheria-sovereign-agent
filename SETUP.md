# Setup

## Requirements

- Windows (reference platform)
- Python 3.10+
- PowerShell 7+ recommended for launch scripts

## Full install vs this repository

Scripts here import runtime modules that are part of a complete local Aetheria tree (orchestrator, registry, cycle probe). Clone this repo into that tree, or copy the `scripts/` and `living/` helpers onto an existing root.

Without those modules, imports fail by design. That is expected.

## Environment

```powershell
$env:AETHERIA_LIGHT_MANAGE = "1"
$env:AETHERIA_SKIP_FINAL_RECON = "1"
$env:AETHERIA_HEAVY_HEALTH_CYCLES = "6,12"
$env:AETHERIA_META_RECON = "0"
```

Optional path overrides: `AETHERIA_BIN_ROOT`, `AETHERIA_LIVING_PATH`.

## Smoke test

```powershell
cd <AETHERIA_ROOT>
python -u scripts/aetheria_hope_path.py --health-only
python -u scripts/aetheria_hope_path.py --cycles 2
```

## Further reading

[docs/OPERATIONS.md](docs/OPERATIONS.md), [docs/INTERNALS.md](docs/INTERNALS.md).
