# Operations

## Environment

```powershell
$env:AETHERIA_LIGHT_MANAGE = "1"
$env:AETHERIA_SKIP_FINAL_RECON = "1"
$env:AETHERIA_HEAVY_HEALTH_CYCLES = "6,12"
$env:AETHERIA_META_RECON = "0"
```

## Short measured run

```powershell
cd <AETHERIA_ROOT>
python -u scripts/aetheria_hope_path.py --cycles 2
Get-Content measurements/hope_status.json
```

## Detached schedule

```powershell
powershell -File scripts/launch_long_horizon.ps1 -Cycles 2 -IntervalMin 15 -MaxTicks 96
powershell -File scripts/launch_lh_watchdog.ps1
```

Stop:

```powershell
Set-Content measurements/long_horizon_STOP "stop"
Set-Content measurements/watchdog_STOP "stop"
```

## After restart

1. Check `measurements/long_horizon.pid` and `measurements/watchdog.pid`.  
2. Relaunch only processes that are not running.  
3. If `sovereign_asset_registry.json` is missing, restore the newest copy under `backups/`.  
4. Prefer restore-and-continue over configuration experiments while recovering.

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

Requires the orchestrator. Prefer running while the long-horizon supervisor is idle.
