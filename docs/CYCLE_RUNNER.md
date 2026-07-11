# Cycle runner contract

Technical design for the **light multi-cycle worker** invoked on each long-horizon tick (and by the measured entry path).

## Problem

Interactive agents die when the session dies. Even a solid process supervisor still needs a **trustworthy cycle worker**: if completion is inferred by scraping log text, or if a child process hangs after the real work finishes, you get silent multi-hour stalls and host lag from orphan processes.

## Design goals

| Goal | Mechanism |
|------|-----------|
| Explicit success/failure | Structured summary JSON (`lh_probe_summary_v1`) |
| No source rewriting | `AETHERIA_NUM_CYCLES` / `NUM_CYCLES` environment variables |
| Bounded runtime | Timeout formula + optional `AETHERIA_PROBE_TIMEOUT_S` |
| Finalize hangs do not win | After contract `ok`, short grace then terminate child |
| Parent stays simple | Supervisor enforces time + records tick; does not “babysit” logs as primary truth |
| Dual-read safety | If summary missing, fall back to log markers (transitional) |

## Contract: `measurements/lh_probe_summary_latest.json`

See [../measurements/lh_probe_summary.example.json](../measurements/lh_probe_summary.example.json).

| Field | Meaning |
|-------|---------|
| `ok` | Contract satisfied |
| `cycles_requested` / `cycles_complete` | Progress |
| `mom_series` / `final_mom` | Momentum samples when available |
| `error_class` | Enumerable failure class (`probe_timeout`, `cycles_incomplete`, …) |
| `runner` | Which path wrote the summary |

The cycle body may write this **before** optional finalize/scribe work so the parent can treat the tick as complete without waiting on hang-prone tails.

## Callers

| Caller | Role |
|--------|------|
| `long_horizon_supervisor.run_probe_cycles` | Plant clock: launch → wait → dual-read → tick ok/fail |
| `aetheria_hope_path.launch_probe` | Short measured run: same env + dual-read |
| `run_probe_bounded.py` | Manual smoke tests with hard reaping (avoids orphans) |

## Private cycle body

A full install provides the cycle implementation (e.g. a local probe module). This repository publishes the **contract and parent consumers**. Without the private body, the supervisor reports `probe_script_missing` — expected for control-plane-only clones.

## Timeout policy

```
timeout_s = min(2400, max(600, 300 + 180 * cycles))
# override: AETHERIA_PROBE_TIMEOUT_S=<seconds>
```

## Escape hatch

`AETHERIA_PROBE_LEGACY=1` — temporary temp-file cycle rewrite (discouraged; for recovery only).

## Resource hygiene

Finalize can hang **after** a successful contract. That leaves an orphan process while the plant is already `idle_between_ticks`.

```powershell
python -u scripts/status_report.py              # shows orphan_probes + RAM/CPU
python -u scripts/status_report.py --reap-orphans  # only when not running_tick
python -u scripts/run_probe_bounded.py --cycles 2  # never leave unbounded smokes
```

## What this is not

- Not a chat UI  
- Not multi-tenant SaaS scheduling  
- Not a claim that the private cycle body is fully open-sourced  

It is a **professional boundary** between process supervision and cycle execution.
