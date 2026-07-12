# Market pain this control plane targets

User and open-source issue language (Ollama, Open WebUI, CrewAI, LangGraph, Reddit/HN) clusters around:

| Pain | Control plane answer |
|------|----------------------|
| Hang / stuck / timeout | Hard timeouts, STOP files, status/orphan tools |
| Session death / no resume | Detached supervisor + watchdog + on-disk state |
| Overnight / multi-hour babysitting | Rolling ticks/segments, green-tick logs |
| Runaway loops | max_ticks, bounded runners |
| Fake-local surprises | This repo is local control plane; cloud not required |

**Job #1:** prove smoke + (optional) launch/stop on your machine. See README.

This is **not** a multi-agent chat framework and not a hosted multi-tenant SaaS.
