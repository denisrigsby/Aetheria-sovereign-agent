# Internals

Operator notes for a full local deployment. Complements the public scripts; does not replace private state.

## Working definition of “healthy”

- Supervisor completes light 2-cycle ticks without multi-hour stalls  
- Watchdog can relaunch after death, stale heartbeat, or stuck `running_tick`  
- `hope_status.json` updates with phase and last outcomes  
- Momentum can persist across process restarts via `measurements/guidance_momentum.json`  
- Sandbox guarded edit has produced a real disk change at least once  

Not claimed complete: broad autonomous editing of production modules under load.

## Expected tree (full install)

```
<AETHERIA_ROOT>/
  scripts/                         # as published, plus local tools
  living/                          # canon helpers + private modules + living jsonl
  measurements/
  backups/
  logs/
  sovereign_asset_registry.json    # private; restore from backups if missing
  grok_supervised_12_probe.py      # cycle probe body used by supervisor
  HANDOFF_NEXT_SESSION.md
  RESUME_STATE.json
  next_interventions.defaults.json
```

## Process graph

1. `launch_long_horizon.ps1` starts `long_horizon_supervisor.py`, writes pid  
2. Tick: health → N-cycle probe → parse completion/momentum → write state → sleep  
3. `lh_watchdog.py` polls pid and heartbeat; relaunches through the launch script  
4. Sessions read status files; they do not parent the long loop  

Current schedule: `--cycles 2 --interval-min 15 --max-ticks 96`.

## Continuity files

| File | Role |
|---|---|
| `measurements/long_horizon_state.json` | tick, last_ok, momentum series, heartbeat |
| `measurements/hope_status.json` | merged status for operators and tools |
| `measurements/guidance_momentum.json` | momentum across restarts |
| `measurements/watchdog_status.json` | last watchdog diagnosis |
| `RESUME_STATE.json` | machine-oriented resume pointer |
| `HANDOFF_NEXT_SESSION.md` | human-oriented re-entry notes |

## Reliability checks

Internal checklist used when changing the system:

1. Multi-cycle run finishes  
2. Momentum compounds across ticks  
3. Process exits cleanly  
4. Status file stays current  
5. Backup exists before risky registry work  
6. Guarded edit path can show a verified disk change (sandbox first)  

## Guarded edit

- Driver: `scripts/m6_thin_safeedit.py`  
- Target: `living/m6_sandbox_target.py`  
- Full install uses orchestrator backup + unique-match replace  

Do not aim experimental edits at critical launch entrypoints.

## Resume after outage

1. Read handoff, resume state, long-horizon state, watchdog status  
2. Relaunch dead supervisor / watchdog with conservation env  
3. Restore registry from backup if missing  
4. One change at a time once healthy  

## Change policy

Promote new behavior into the live path only when checks 1–5 hold and the change can be verified in isolation.
