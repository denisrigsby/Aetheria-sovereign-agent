# Public control-plane hygiene

This repo is the **auditable control plane** (supervisor, watchdog, cycle contract, status tools). Private plant depth stays off GitHub.

## Hygiene PRs

- Prefer small allowlisted docs/CI fixes.
- **Dry-run first**; human reviews and merges.
- Never parent long-horizon ticks from chat or a PR bot.
- Do not open the residual gate from thrash or CI noise alone.

## Local operator tip

On the operator machine, supervised hygiene may run with explicit auth while the plant holds under conservation. Autopilot residuals still require gate + day-cap.
