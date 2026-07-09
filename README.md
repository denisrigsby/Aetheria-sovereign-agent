# Aetheria

Local multi-cycle agent runtime utilities.

Aetheria runs bounded work units on a schedule, outside an interactive session. A small supervisor process executes cycles, writes status to disk, and can be restarted by a watchdog if it exits or stalls. The design goal is continuity across restarts without keeping a chat window open as the parent process.

This repository contains the control-plane scripts and documentation for that loop. A working deployment also needs the private runtime modules and state that live on the operator machine (orchestrator, asset registry, living memory). Those are not distributed here.

## Components

- `scripts/long_horizon_supervisor.py` — scheduled multi-cycle runner  
- `scripts/lh_watchdog.py` — process monitor and relaunch  
- `scripts/aetheria_hope_path.py` — health check and short measured run  
- `scripts/m6_thin_safeedit.py` — guarded edit exercise on a sandbox file  
- `scripts/registry_hygiene.py`, `scripts/backup_sovereign_core.ps1` — maintenance  
- `living/aetheria_canon.py` — path helpers and status writer  

## Configuration

Stable defaults (keep these unless you are deliberately testing failure modes):

```
AETHERIA_LIGHT_MANAGE=1
AETHERIA_SKIP_FINAL_RECON=1
AETHERIA_HEAVY_HEALTH_CYCLES=6,12
AETHERIA_META_RECON=0
```

Light manage and skipped thrash-recon paths avoid multi-hour stalls observed under unbounded full-manage settings.

## Usage

Requires a full local install root (this clone alone is not enough to import the orchestrator).

```powershell
cd <AETHERIA_ROOT>

$env:AETHERIA_LIGHT_MANAGE = "1"
$env:AETHERIA_SKIP_FINAL_RECON = "1"
$env:AETHERIA_HEAVY_HEALTH_CYCLES = "6,12"
$env:AETHERIA_META_RECON = "0"

python -u scripts/aetheria_hope_path.py --cycles 2
powershell -File scripts/launch_long_horizon.ps1 -Cycles 2 -IntervalMin 15 -MaxTicks 96
powershell -File scripts/launch_lh_watchdog.ps1
```

Stop:

```powershell
Set-Content measurements/long_horizon_STOP "stop"
Set-Content measurements/watchdog_STOP "stop"
```

Status files (created at runtime): `measurements/hope_status.json`, `measurements/long_horizon_state.json`.

## Documentation

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)  
- [docs/OPERATIONS.md](docs/OPERATIONS.md)  
- [docs/INTERNALS.md](docs/INTERNALS.md)  
- [docs/MEMORY_AND_STATE.md](docs/MEMORY_AND_STATE.md)  
- [SETUP.md](SETUP.md)  

## Status

The light multi-cycle path and process supervision are in active use. Guarded edits are demonstrated on a disposable sandbox module. Broad automatic editing of production code is incomplete. Private memory streams and live registries are not published.

## License

MIT. See [LICENSE](LICENSE).
