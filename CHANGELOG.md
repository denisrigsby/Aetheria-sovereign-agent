# Changelog

All notable changes to the **public control plane** are documented here.


## [Unreleased]

### Added

- Operator hygiene PR propose path (dry-run default; human merge) — see private plant residual `hygiene_pr_propose` / docs when published

### Changed

- (none yet)

## [0.3.1] - 2026-07-12

### Added

- `status_report` **segment vs campaign** progress block (avoids misreading PID/tick reset as wiped progress)
- Architecture / WHY notes: **plant clock != chat**; optional private companion stays out of this repo
- OPERATIONS: preferred one-screen status pulse and orphan reap caution

### Changed

- Control-plane scripts refreshed from operator tree with host absolute paths scrubbed
- README: explicit private-depth boundary (companion / generate not published)

### Security / privacy

- Continues policy: no private living streams, chat ownership, generative train stacks, or host paths in the public surface

## [0.3.0] — 2026-07-11

### Added

- **Cycle runner contract** documentation ([docs/CYCLE_RUNNER.md](docs/CYCLE_RUNNER.md))
- `measurements/lh_probe_summary.example.json` — structured completion schema
- Supervisor + hope-path consumers: env cycle count, summary dual-read, bounded finalize
- `status_report` / `resource_check`: related processes, orphan cycle workers, host RAM/CPU
- `--reap-orphans` for safe cleanup when the plant is not mid-tick
- `run_probe_bounded.py` — manual smokes with hard timeout (prevents host lag from orphans)

### Changed

- README rewritten for technical clarity and engagement (problem → architecture → features)
- Public language prefers **cycle runner / contract** over informal codenames
- Operator-facing strings scrubbed of host absolute paths and session-vendor specifics
- OPERATIONS: lag/orphan playbook; ARCHITECTURE: cycle boundary diagram section

### Fixed

- Class of failures where cycle work finished but child finalize hung unbounded (parent path)
- Class of host lag from orphan cycle processes while supervisor already idle

## [0.2.1] — 2026-07-11

### Added

- `docs/WHY.md` — problem, non-goals, success criteria (public “why”)  
- `scripts/status_report.py` — one-screen read-only plant/control-plane status  

### Changed

- README links WHY + status report in quick path  

## [0.2.0] — 2026-07-11

### Added

- Durable green-tick log for change-control Gate A (`gate_a_green_ticks.jsonl`), unioned with in-process history so process restarts do not erase progress  
- `verify_continuity_readonly.py` — read-only continuity audit (backups, resume shape, momentum carry, process liveness)  
- Example `measurements/gate_a_progress.example.json`  
- Rolling **segment** model documented as the default campaign unit  

### Changed

- Default / recommended `MaxTicks` **48** (was commonly documented as 96–200 single-PID heroics)  
- Watchdog relaunch: longer launcher timeout, **success = supervisor PID alive** (poll), default relaunch segment length 48  
- Supervisor records durable green ticks on successful ticks  
- Public docs rewritten as product descriptions (less operator-checklist dump, no host absolute paths)  
- Example handoff / resume templates aligned with segment defaults  

### Fixed

- False “relaunch failed” class of outcomes when the supervisor starts after a slow launcher return  

## [0.1.0] — 2026-07-10

### Added

- Initial public control plane: supervisor, watchdog, hope path, launch scripts  
- Architecture / operations docs, CONTRIBUTING, SECURITY, CI  
