# Operations

Day-2 runbook for the published control plane. Paths are relative to your Aetheria root (`<AETHERIA_ROOT>`).

## Environment

```powershell
$env:AETHERIA_LIGHT_MANAGE = "1"
$env:AETHERIA_SKIP_FINAL_RECON = "1"
$env:AETHERIA_HEAVY_HEALTH_CYCLES = "6,12"
$env:AETHERIA_META_RECON = "0"
```

Optional overrides: `AETHERIA_BIN_ROOT`, `AETHERIA_LIVING_PATH`.

## Short measured run

```powershell
cd <AETHERIA_ROOT>
python -u scripts/aetheria_hope_path.py --health-only
python -u scripts/aetheria_hope_path.py --cycles 2
# Inspect status when present:
#   measurements/hope_status.json
```

## Detached schedule

Example schedule (tune interval and max ticks to your load):

```powershell
powershell -File scripts/launch_long_horizon.ps1 -Cycles 2 -IntervalMin 30 -MaxTicks 200
powershell -File scripts/launch_lh_watchdog.ps1
```

### Stop

```powershell
Set-Content measurements/long_horizon_STOP "stop"
Set-Content measurements/watchdog_STOP "stop"
```

Supervisor honors the stop file between ticks; watchdog honors its own stop file on the next poll.

## After host restart

1. Check whether supervisor and watchdog PIDs are still alive (`measurements/long_horizon.pid`, `measurements/watchdog.pid`).
2. Relaunch only processes that are not running (same conservation env as above).
3. If `sovereign_asset_registry.json` is missing, restore the newest copy under `backups/` before heavy work.
4. Prefer **restore-and-continue** over configuration experiments while recovering.

## Maintenance

```powershell
powershell -File scripts/backup_sovereign_core.ps1 -Label ops
python -u scripts/registry_hygiene.py
```

Always retain a backup before registry hygiene.

## Sandbox edit check

```powershell
python -u scripts/m6_thin_safeedit.py
```

Requires the orchestrator (full install). Prefer running while the long-horizon supervisor is idle between ticks.

## Status files (runtime)

| File | Role |
|------|------|
| `measurements/hope_status.json` | Merged operational window |
| `measurements/long_horizon_state.json` | Tick, last_ok, momentum, heartbeat |
| `measurements/watchdog_status.json` | Last watchdog diagnosis |

These are **created at runtime** and are not published as live host state.

## Failure modes (quick)

| Symptom | First response |
|---------|----------------|
| Supervisor PID dead | Relaunch `launch_long_horizon.ps1` with conservation env |
| Stuck `running_tick` | Watchdog should relaunch; if not, stop + diagnose logs |
| Registry missing | Restore from `backups/`, then continue |
| Multi-hour stall on manage | Confirm conservation env; do not enable unbounded heavy manage |
