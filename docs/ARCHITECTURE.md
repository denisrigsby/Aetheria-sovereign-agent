# Architecture

## Overview

Interactive sessions are unreliable parents for multi-hour work. Aetheria splits:

1. **Operator** — goals and constraints  
2. **Session tooling** — implement and repair while a session is available  
3. **Runtime** — detached supervisor + watchdog + status files  

Long-running work is owned by the runtime processes.

## Runtime

**long_horizon_supervisor**  
On each tick: ensure registry presence (or restore from backup), run light health, execute N light cycles via the local probe, record momentum and completion, sleep until the next interval. Honors a stop file during sleep.

**lh_watchdog**  
Separate process. Monitors PID liveness and heartbeat freshness. Relaunches the supervisor when the process is dead, stuck in `running_tick` past a threshold, or has exited after max ticks. Writes `measurements/watchdog_status.json`. Optional operator notify file on failures that need attention.

**hope path**  
`aetheria_hope_path.py` performs health reporting, optional hygiene/backup, and a short measured run, then updates `measurements/hope_status.json`.

**State (full install)**  
Living memory streams and `sovereign_asset_registry.json` hold long-term content. Path resolution is centralized in `living/aetheria_canon.py`.

**Guarded edit**  
When the orchestrator is present, exact string edits can run with backup and uniqueness checks. The published exercise target is `living/m6_sandbox_target.py`.

## Defaults

Unbounded per-cycle manage and aggressive recon paths produced multi-hour stalls in testing. Defaults favor light manage, skipped thrash recon, and heavier health only on selected cycle indices (6 and 12).
