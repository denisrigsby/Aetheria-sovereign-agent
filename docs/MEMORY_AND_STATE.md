# Memory and state

## Public vs private

| Published in this repo | Private (local only) |
|------------------------|----------------------|
| Control-plane scripts | Living memory streams |
| Path helpers + sandbox target | Live asset registry |
| Example / sanitized measurements and schemas | Host PID files, stop files, live hope/LH state |
| Docs, changelog, templates | Logs, backups, credentials, operator-private notes |

## Typical paths (full install)

| Path | Role |
|------|------|
| `living/` stream files | Long-term living content |
| `measurements/hope_status.json` | Runtime status window |
| `sovereign_asset_registry.json` | Assets and event log |

Helpers: `living/aetheria_canon.py`.  
Overrides: `AETHERIA_LIVING_PATH`, `AETHERIA_BIN_ROOT`.

## Practice

- Do **not** merge living streams as a casual cleanup step  
- Do **not** delete the registry without a backup on disk  
- Do **not** commit live `measurements/*` status, PID, or notify files  

## This repository

Live living files and registries are **not** included. Anything under `measurements/` here is example or sanitized only.
