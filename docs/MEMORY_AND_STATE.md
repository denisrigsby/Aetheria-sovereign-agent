# Memory and state

## Paths (full install)

| Path | Role |
|---|---|
| `living/personal_living.jsonl` | Long-term living stream |
| `personal_living.jsonl` | Session / operations overlay |
| `measurements/hope_status.json` | Runtime status window |
| `sovereign_asset_registry.json` | Assets and event log |

Helpers: `living/aetheria_canon.py`.  
Overrides: `AETHERIA_LIVING_PATH`, `AETHERIA_BIN_ROOT`.

## Practice

- Do not merge living streams as a cleanup step.  
- Do not delete the registry without a backup on disk.  
- Auxiliary pause flags are secondary; the measured run path does not depend on them.

## This repository

Live living files and registries are not included. Examples under `measurements/` are sanitized.
