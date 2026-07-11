# Changelog

All notable changes to the **public control plane** are documented here.

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
