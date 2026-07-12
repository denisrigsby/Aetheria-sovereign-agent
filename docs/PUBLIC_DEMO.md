# Sanitized public demo

**Purpose:** Prove this control plane is real and runnable *as documentation + smoke tooling* without exposing private operator depth (living streams, companion chat, G4 train, host secrets).

**Parents long-horizon plant:** only if **you** launch it in a full local root — chat never does.

---

## What you get from a clone

| Included | Not included (private / full install) |
|----------|----------------------------------------|
| Supervisor / watchdog / status scripts | Private orchestrator & registry contents |
| Cycle runner contract examples | Companion chat / Ollama surface |
| Gate & continuity *shapes* | Live G4 adapters / train data |
| Disposable SafeEdit sandbox target | Operator host measurements |

That split is intentional: **public surface evolves; private core stays sovereign.**

---

## 5-minute local demo (Windows)

```powershell
git clone https://github.com/denisrigsby/Aetheria-sovereign-agent.git
cd Aetheria-sovereign-agent

# One-shot sanitized smoke (stdlib + this tree)
python -u scripts/demo_local_smoke.py

# Or double-click / run:
powershell -File scripts/demo_local.ps1
```

**Expected:** Python 3.10+ check, script compile, example JSON load, clear **scope banner**, optional status import probe.

**Not expected:** Multi-hour plant, chat UI, or private memory. If imports fail for cycle body, that is **by design** until you overlay a full Aetheria root (see [SETUP.md](../SETUP.md)).

**Local only:** this demo is for your machine. No cloud agent parent, no sauce, no private living streams.

---

## Optional: local model (not required for smoke)

The sanitized demo does **not** need a model. If you later run a **private** companion surface on a full operator install and Ollama has no model yet:

```powershell
ollama pull qwen2.5:14b
```

That is optional, private-depth tooling — not part of this control-plane smoke.

---

## Conservation defaults (if you later run a real plant)

```powershell
$env:AETHERIA_LIGHT_MANAGE = "1"
$env:AETHERIA_SKIP_FINAL_RECON = "1"
$env:AETHERIA_HEAVY_HEALTH_CYCLES = "6,12"
$env:AETHERIA_META_RECON = "0"
```

Never set live train flags or attach the plant to a chat session as parent.

---

## Success criteria (demo)

1. Clone runs smoke without private files  
2. README / this doc explain plant ≠ chat  
3. Operator can decide to go deeper via full install — or stop here  

---

## Hygiene

Public docs/demo changes follow [HYGIENE.md](HYGIENE.md): dry-run, allowlist, human merge.
