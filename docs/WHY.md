# Why Aetheria’s control plane exists

## The problem

Long-running local AI work is often parented by an interactive session: a chat window, an IDE agent, or a notebook kernel. Those parents are unreliable for multi-hour jobs. They disconnect, rate-limit, crash, or simply stop when the human closes the laptop lid of attention.

When that happens, the usual failure modes are:

- The run **dies with the session**
- Progress is **only in chat memory**, not on disk
- Recovery means **starting over** or guessing what finished
- “Just leave it running” turns into **multi-hour hangs** under heavy manage/recon paths

## What we refuse

| Non-goal | Why |
|----------|-----|
| Chat as the parent of multi-hour work | Sessions are not process supervisors |
| Unbounded full-manage every cycle | Observed multi-hour stall ridge |
| Publishing private memory/registries | Control plane ≠ whole organism |
| Multi-tenant SaaS orchestration | This design optimizes for a **sovereign local owner** |

## What we build instead

A **control plane** in the spirit of process supervisors (supervisor, pm2):

1. **Detached supervisor** — ticks of bounded multi-cycle work  
2. **On-disk status** — hope / long-horizon / watchdog JSON  
3. **Watchdog** — relaunch on death, stall, or segment end  
4. **Conservation defaults** — light manage, selective heavy health  
5. **Rolling segments** — a process is a worker (e.g. 48 ticks), not the whole campaign  
6. **Restart-resilient green-tick accounting** — change gates do not forget progress when a PID dies  
7. **Private runtime stays private** — orchestrator, living streams, registries on the operator machine  

## Why this is not “just pm2”

Process supervision is the **bones**. The muscle is **agent continuity**:

- Momentum and status that survive restarts  
- Measured short runs (`aetheria_hope_path`) vs long detached campaigns  
- Optional change-control gate (enough green work since last change)  
- Explicit split: **public control plane** vs **private organism depth**  

If you only need to keep a static web server up, use pm2. If you need **local multi-cycle agent work that outlives chat**, you need something shaped like this.

## Success for the intended user

| Role | Success looks like |
|------|---------------------|
| Sparse operator | Plant runs while they do other things; pulses say “green” or “heal” |
| Recovering after reboot | Relaunch supervisor + watchdog; restore registry if needed; continue |
| Public reader | Understands *why*, can run or audit the control plane without private dumps |

Not success: a flashy single-turn chat demo that still dies when the tab closes.

## Related docs

- [ARCHITECTURE.md](ARCHITECTURE.md) — layers and components  
- [OPERATIONS.md](OPERATIONS.md) — start / stop / recover  
- [MEMORY_AND_STATE.md](MEMORY_AND_STATE.md) — public vs private  
- [../README.md](../README.md) — landing page  
