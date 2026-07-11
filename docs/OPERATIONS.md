# Operations

Runbook for the published control plane. Paths are relative to your Aetheria root (`<AETHERIA_ROOT>`).

## Environment

```powershell
$env:AETHERIA_LIGHT_MANAGE = "1"
$env:AETHERIA_SKIP_FINAL_RECON = "1"
$env:AETHERIA_HEAVY_HEALTH_CYCLES = "6,12"
$env:AETHERIA_META_RECON = "0"
```

Optional path overrides: `AETHERIA_BIN_ROOT`, `AETHERIA_LIVING_PATH`.

## Short measured run

```powershell
cd <AETHERIA_ROOT>
python -u scripts/aetheria_hope_path.py --health-only
python -u scripts/aetheria_hope_path.py --cycles 2
```

When present, inspect `measurements/hope_status.json`.

## Detached schedule (rolling segment)

Default recommendation: **2 cycles per tick**, **30 minutes** between ticks, **48 ticks per process segment**.

```powershell
powershell -File scripts/launch_long_horizon.ps1 -Cycles 2 -IntervalMin 30 -MaxTicks 48
powershell -File scripts/launch_lh_watchdog.ps1
```

A segment ending (`completed_max_ticks`) is normal. The watchdog can relaunch a new segment. Process identity is a **worker**, not the whole campaign.

### Stop

```powershell
Set-Content measurements/long_horizon_STOP "stop"
Set-Content measurements/watchdog_STOP "stop"
```

The supervisor honors the stop file between ticks; the watchdog honors its stop file on the next poll.

## After host restart

1. Check `measurements/long_horizon.pid` and `measurements/watchdog.pid` for live processes.  
2. Relaunch only what is not running (same conservation environment).  
3. If `sovereign_asset_registry.json` is missing, restore the newest copy under `backups/` before heavy work.  
4. Prefer **restore-and-continue** over configuration experiments while recovering.  
5. Expect the **tick counter** to restart on a new process; momentum and durable green-tick logs can continue.

## Status, lag, and orphans

```powershell
python -u scripts/status_report.py
# alias:
python -u scripts/resource_check.py
```

Shows plant health, last cycle-runner contract fields, related processes, memory/CPU, and **orphan** cycle workers (children still running while the plant is idle — a common host-lag cause after finalize hangs).

```powershell
# Only when long-horizon is NOT mid-tick:
python -u scripts/status_report.py --reap-orphans
```

## Continuity audit (read-only)

```powershell
python -u scripts/verify_continuity_readonly.py
```

Writes `measurements/CONTINUITY_VERIFY_latest.json` (and a short markdown twin). Does not start cycle workers or kill processes.

## Cycle runner (contract)

See [CYCLE_RUNNER.md](CYCLE_RUNNER.md). Short form:

- Env: `AETHERIA_NUM_CYCLES` (and conservation vars)
- Summary: `measurements/lh_probe_summary_latest.json` (`lh_probe_summary_v1`)
- Manual smoke: `python -u scripts/run_probe_bounded.py --cycles 2`

## Change-control gate (optional)

```powershell
python -u scripts/eval_residual_gate_v2.py
```

Evaluates whether enough **green ticks after the last recorded change** have completed (Gate A), whether a candidate change is declared (Gate B, if used), and whether the budget is free (Gate C). Green ticks are counted from the current process history **and** `measurements/gate_a_green_ticks.jsonl` so restarts do not silently zero progress.

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

| File | Description |
|------|-------------|
| `measurements/hope_status.json` | Merged operational window |
| `measurements/long_horizon_state.json` | Tick, last_ok, momentum, heartbeat |
| `measurements/watchdog_status.json` | Last watchdog diagnosis |
| `measurements/guidance_momentum.json` | Momentum across restarts (when used) |
| `measurements/gate_a_green_ticks.jsonl` | Durable successful-tick log for change gates |
| `measurements/NOTIFY_USER.md` | Optional operator alert file written by the watchdog on notable events |

These are **created at runtime** and are not published as live host state.

## Failure modes

| Symptom | First response |
|---------|----------------|
| Supervisor PID dead | Relaunch `launch_long_horizon.ps1` with conservation env |
| Stuck `running_tick` | Watchdog should relaunch; if not, stop and inspect logs |
| Registry missing | Restore from `backups/`, then continue |
| Multi-hour stall on manage | Confirm conservation env; avoid unbounded heavy manage |
| Watchdog reported relaunch failure | Confirm whether `long_horizon.pid` is actually alive (slow launches can outlive a short timeout; current watchdog polls for a live PID) |
