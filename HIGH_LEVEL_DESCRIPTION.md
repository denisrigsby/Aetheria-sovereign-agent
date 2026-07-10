# Aetheria — high-level description

**Local multi-cycle agent runtime.** Scheduled work runs as a supervised process with on-disk status, not as a long-lived chat session.

This repository publishes the **control plane**: supervisor, watchdog, measured entry path, maintenance helpers, and the documentation needed to operate them.

Deployment-specific state — living memory, asset registry, host configuration — remains on the operator machine and is not distributed here.

## One sentence

Aetheria is process supervision for long-horizon local AI work: start a loop, persist progress, recover from crashes, without parenting multi-hour jobs on an interactive session.

## Keywords

local agent runtime · supervised LLM agent · persistent AI loop · watchdog process supervision · long-horizon agents
