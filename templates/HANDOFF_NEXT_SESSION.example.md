# Session handoff (example)

Optional human-readable notes for the next operator session.  
The long-horizon supervisor does **not** require this file to run.

| Item | Example value |
|------|----------------|
| Long-horizon | running · 2 cycles / 30 min · segment max 48 ticks |
| Watchdog | running |
| Last tick | ok · momentum continued |
| Status files | `measurements/long_horizon_state.json`, `hope_status.json` |

**Operating principles:** conservation environment; backup before registry risk; one verified change at a time; interactive sessions are not the parent of the long run.

```powershell
cd <AETHERIA_ROOT>
$env:AETHERIA_LIGHT_MANAGE = "1"
$env:AETHERIA_SKIP_FINAL_RECON = "1"
$env:AETHERIA_HEAVY_HEALTH_CYCLES = "6,12"
$env:AETHERIA_META_RECON = "0"
powershell -File scripts/launch_long_horizon.ps1 -Cycles 2 -IntervalMin 30 -MaxTicks 48
powershell -File scripts/launch_lh_watchdog.ps1
```
