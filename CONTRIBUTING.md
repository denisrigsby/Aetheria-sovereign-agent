# Contributing

Thanks for helping improve the **public control plane**. This repository is intentionally small: process supervision scripts and documentation for local multi-cycle agents.

## What belongs here

- Bugfixes in published scripts (`scripts/`, `living/aetheria_canon.py`, sandbox target)
- Documentation clarity (README, docs, SETUP)
- CI improvements that stay dependency-light
- Example artifacts that are clearly fictional / sanitized

## What does **not** belong here

- Living memory dumps (`personal_living.jsonl`, etc.)
- Live asset registries or backups
- Logs, PID files, stop files, host paths
- Credentials, `.env`, API keys
- Operator-only co-pilot notes, session handoffs with private detail
- Large private module trees that are not part of the control plane

Pull requests that include the above will be closed without merge.

## Development workflow

1. Fork and branch from `main`
2. Keep changes focused (one concern per PR)
3. Run local checks:

```powershell
python -m compileall -q scripts living
```

4. If you have a full install, smoke:

```powershell
python -u scripts/aetheria_hope_path.py --health-only
```

5. Open a PR with a short description of **problem → change → how verified**

## Style

- Prefer boring, explicit names over clever abstractions  
- Document environment variables next to behavior  
- Do not expand scope into private runtime modules in this repo  
- Windows PowerShell launchers are first-class; keep them working  

## Security

If you discover a vulnerability in published scripts, open a private report to the maintainer rather than filing a public issue with exploit detail.

## License

Contributions are accepted under the MIT license covering this repository.
