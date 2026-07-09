# Handoff

| Item | Value |
|---|---|
| long-horizon | running / stopped · cadence |
| watchdog | running / stopped |
| last tick | ok / fail · momentum |
| next change | one line |

Rules: conservation environment; backup before registry risk; one verified change; session is not the parent of the long run.

```powershell
cd <AETHERIA_ROOT>
$env:AETHERIA_LIGHT_MANAGE = "1"
$env:AETHERIA_SKIP_FINAL_RECON = "1"
powershell -File scripts/launch_long_horizon.ps1 -Cycles 2 -IntervalMin 15 -MaxTicks 96
powershell -File scripts/launch_lh_watchdog.ps1
Get-Content measurements/hope_status.json
```
