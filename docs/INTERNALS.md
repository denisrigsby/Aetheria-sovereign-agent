# Internals

Operator-facing detail for a full local deployment. Complements the public scripts; does not include private state.

## Working definition of “healthy”

- Supervisor completes light multi-cycle ticks without multi-hour stalls  
- Watchdog can relaunch after death, stale heartbeat, or stuck `running_tick`  
- Status files under `measurements/` update with phase and last outcomes  
- Momentum can persist across process restarts  
- Sandbox guarded edit has produced a real disk change at least once  

**Not claimed complete:** broad autonomous editing of production modules under load.

## Expected tree (full install)

```
<AETHERIA_ROOT>/
  scripts/                      # control plane (as published) + local tools
  living/                       # canon helpers + private modules + living streams
  measurements/                 # runtime status (local)
  backups/
  logs/
  sovereign_asset_registry.json # private; restore from backups if missing
  # cycle probe / orchestrator modules used by the supervisor (local)
```

Optional operator continuity templates (examples in `templates/`):

- `HANDOFF_NEXT_SESSION.md` — human re-entry notes  
- `RESUME_STATE.json` — machine-oriented resume pointer  

## Process graph

1. `launch_long_horizon.ps1` starts `long_horizon_supervisor.py` and writes a pid file  
2. Each tick: health → N-cycle probe → parse completion/momentum → write state → sleep  
3. `lh_watchdog.py` polls pid and heartbeat; relaunches through the launch script  
4. Interactive sessions **read** status files; they do **not** parent the long loop  

Example schedule parameters (not mandatory): `--cycles 2 --interval-min 30 --max-ticks 200`.

## Continuity files

| File | Role |
|------|------|
| `measurements/long_horizon_state.json` | tick, last_ok, momentum series, heartbeat |
| `measurements/hope_status.json` | merged status window |
| `measurements/guidance_momentum.json` | momentum across restarts (when used) |
| `measurements/watchdog_status.json` | last watchdog diagnosis |
| `RESUME_STATE.json` | optional machine resume pointer |
| `HANDOFF_NEXT_SESSION.md` | optional human re-entry notes |

## Reliability checklist

Use when changing the system:

1. Multi-cycle run finishes  
2. Momentum compounds across ticks  
3. Process exits cleanly when stopped  
4. Status files stay current  
5. Backup exists before risky registry work  
6. Guarded edit path can show a verified disk change (sandbox first)  

## Guarded edit

- Driver: `scripts/m6_thin_safeedit.py`  
- Target: `living/m6_sandbox_target.py`  
- Full install uses orchestrator backup + unique-match replace  

Do not aim experimental edits at critical launch entrypoints.

## Resume after outage

1. Read handoff/resume (if used), long-horizon state, watchdog status  
2. Relaunch dead supervisor / watchdog with conservation env  
3. Restore registry from backup if missing  
4. One change at a time once healthy  

## Change policy

Promote new behavior into the live path only when checklist items 1–5 hold and the change can be verified in isolation.
