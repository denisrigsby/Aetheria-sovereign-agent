# Aetheria

Local multi-cycle agent runtime. Scheduled work runs as a supervised process with on-disk status, not as a long-lived chat session.

This repository publishes the control-plane scripts (supervisor, watchdog, measured entry path, maintenance helpers) and the documentation needed to operate them. Deployment-specific state—living memory, asset registry, host configuration—remains on the operator machine.
