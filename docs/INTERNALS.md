# Internals

Operator-facing detail for a full local deployment. Complements the public scripts; does not include private state.

## Working definition of “healthy”

- Supervisor completes light multi-cycle ticks without multi-hour stalls  
- Watchdog can relaunch after death, stale heartbeat, or stuck `running_tick`  
- Status files under `measurements/` update with phase and last outcomes  
- Momentum can persist across process restarts  
- Durable green-tick log grows on successful ticks  
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

Optional continuity templates (examples in `templates/`):

- `HANDOFF_NEXT_SESSION.md` — human re-entry notes  
- `RESUME_STATE.json` — machine-oriented resume pointer  

## Process graph

1. `launch_long_horizon.ps1` starts `long_horizon_supervisor.py` and writes a pid file  
2. Each tick: health → N-cycle probe → record completion/momentum → durable green tick → sleep  
3. `lh_watchdog.py` polls pid and heartbeat; relaunches through the launch script when needed  
4. Interactive sessions **read** status files; they do **not** parent the long loop  

Recommended segment parameters: `--cycles 2 --interval-min 30 --max-ticks 48`.

## Continuity files

| File | Description |
|------|-------------|
| `measurements/long_horizon_state.json` | tick, last_ok, momentum series, heartbeat |
| `measurements/hope_status.json` | merged status window |
| `measurements/guidance_momentum.json` | momentum across restarts (when used) |
| `measurements/watchdog_status.json` | last watchdog diagnosis |
| `measurements/gate_a_green_ticks.jsonl` | durable successful ticks for change gates |
| `measurements/gate_a_progress.json` | latest gate-A snapshot from the evaluator |
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
7. After a process restart, gate-A progress is not wiped solely because history reset  

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

Promote new behavior into the live path only when checklist items hold and the change can be verified in isolation. Prefer rolling segments over single-process heroics for long campaigns.
