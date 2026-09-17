# Aetheria Prime: Cohesive Product and Engineering Specification

**Status in this repository:** this is a **design specification**, not a claim that the full product is shipped.

- The published product of this repo is the **process control plane** ([STANDALONE_PRODUCT.md](STANDALONE_PRODUCT.md)).
- A thin Release 1 core (draft/commit, hash-chained ledger, local search, checkpoint/handoff) is optional: [PRIME_CONTINUITY.md](PRIME_CONTINUITY.md) and `living/prime_continuity.py`.
- FastAPI, React, trusted worker nodes, and Tor routing are **not implemented** here and are not required to use the control plane.
- Draft analysis must not execute actions. Submit is not authorize.

## 1. Product definition

Aetheria Prime is a **local-first, provider-independent AI continuity and research system**.

It coordinates humans, AI models, tools, files, web sources, and trusted worker nodes while preserving the user’s durable project state. Models are replaceable workers. The user’s evidence, decisions, artifacts, permissions, and project history are the primary assets.

Aetheria should allow a user to:

- work with local, remote, offline, and peer-hosted models;
- continue after provider limits, crashes, outages, or model changes;
- search local files and the web;
- preserve sources, timestamps, versions, hashes, citations, and provenance;
- extract and evaluate claims;
- identify contradictions, uncertainty, bias, stale information, and missing evidence;
- curate research datasets;
- compare outputs from multiple models;
- safely analyze text while it is being drafted;
- prevent drafts or untrusted content from executing actions;
- authorize tools and external communication explicitly;
- move work between devices and trusted worker nodes;
- use Direct HTTPS, Tor-preferred, or Tor-only networking;
- stop and restart work without losing project state;
- export a complete, inspectable handoff package.

The product is not primarily a chatbot. Its core capability is **durable, auditable, recoverable AI-assisted work**.

## 2. Product promise

> Aetheria lets users research, reason, preserve, and continue AI work without making any single model, provider, chat window, cloud service, or network connection the owner of their project.

Aetheria must preserve five things above all else:

1. **Evidence** — what information was used.
2. **Decisions** — what the user accepted, rejected, or authorized.
3. **Artifacts** — what was produced.
4. **State** — what remains unfinished.
5. **Lineage** — how every important result was created.

## 3. Design principles

### Local-first

The application must remain useful without network access. Local mode should support:

- local files;
- local source records;
- local search;
- local models;
- local embeddings;
- local datasets;
- local checkpoints;
- local audit logs;
- offline replay.

Network-dependent features must degrade gracefully rather than disable the application.

### Human-controlled

AI systems may analyze, recommend, classify, retrieve, and propose. They may not assume that an inferred intention is an authorization.

The system must distinguish:

```text
What the user typed
What the model inferred
What the system proposed
What the user authorized
What was executed
What actually completed
```

### Evidence-first

A model-generated statement is not a verified fact. Claims must be traceable to source evidence or explicitly labeled as:

- user statement;
- model assertion;
- interpretation;
- prediction;
- unsupported;
- contradicted;
- pending review.

### Provider independence

Models and providers are replaceable. The application must not make project state dependent on:

- one chat interface;
- one model family;
- one API;
- one cloud provider;
- one worker node;
- one network route.

### Append-only history

Durable history must be append-only and tamper-evident. Corrections create new events and versions rather than silently changing the past.

### Safe degradation

When search, a model, a node, or a network route fails, Aetheria should:

- preserve all completed work;
- identify the failure;
- mark affected tasks;
- offer a safe retry or fallback;
- avoid pretending that the task completed.

## 4. System architecture

```text
┌─────────────────────────────────────────────┐
│                 User Interface              │
│ Workspace · Research · Evidence · Datasets  │
│ Models · Continuity · Nodes · Audit         │
└───────────────────┬─────────────────────────┘
                    │
┌───────────────────▼─────────────────────────┐
│                Draft Manager                 │
│ Temporary analysis; no execution authority  │
└───────────────────┬─────────────────────────┘
                    │ explicit submit
┌───────────────────▼─────────────────────────┐
│            Commit and Policy Gate            │
│ Validate · classify · authorize · record    │
└───────────────────┬─────────────────────────┘
                    │
┌───────────────────▼─────────────────────────┐
│               Event Ledger                  │
│ Append-only events · hash chain · replay    │
└──────────────┬───────────────┬──────────────┘
               │               │
┌──────────────▼─────────┐ ┌───▼───────────────┐
│ Continuity Plane       │ │ Evidence Plane    │
│ Checkpoints            │ │ Sources           │
│ Handoffs               │ │ Versions          │
│ Leases                 │ │ Claims            │
│ Recovery               │ │ Datasets          │
│ Replay                 │ │ Provenance        │
└──────────────┬─────────┘ └───┬───────────────┘
               │               │
               └───────┬───────┘
                       ▼
┌─────────────────────────────────────────────┐
│                 Task Orchestrator            │
│ Stages · retries · dependencies · policies  │
└──────────────┬──────────────┬───────────────┘
               │              │
┌──────────────▼───────┐ ┌────▼────────────────┐
│ Model Broker         │ │ Tool and Retrieval  │
│ Local · remote       │ │ Files · web · OCR   │
│ peer · fallback      │ │ search · parsers    │
└──────────────┬───────┘ └────┬────────────────┘
               │              │
               └──────┬───────┘
                      ▼
             ┌────────────────────┐
             │ Review and Export  │
             │ Answers · reports  │
             │ handoffs · audits  │
             └────────────────────┘
```

## 5. Core components

### 5.1 Workspace

The workspace is the user’s project environment. It contains:

- conversations;
- research requests;
- source collections;
- evidence bundles;
- datasets;
- decisions;
- active tasks;
- checkpoints;
- model comparisons;
- exports;
- audit history.

A workspace must have its own policy, encryption configuration, artifact namespace, and access permissions.

### 5.2 Draft Manager

The Draft Manager handles text before submission.

Draft analysis may:

- identify probable topic;
- suggest local files;
- suggest search queries;
- highlight ambiguity;
- identify possible sensitive information;
- recommend a task type;
- estimate required tools;
- suggest clarifying questions.

Draft analysis must not:

- call external services;
- modify files;
- create a durable task;
- send data to a provider;
- authorize an action;
- create a committed event;
- write durable memory.

Draft state is temporary and may be discarded.

### 5.3 Commit and Policy Gate

When the user submits text, the system:

1. preserves the exact text;
2. calculates its content hash;
3. creates a committed event;
4. classifies possible intents;
5. creates proposed actions;
6. evaluates policy;
7. requests confirmation where necessary;
8. starts only permitted work.

A submitted message records what the user said. It does not authorize every action described in that message.

### 5.4 Event Ledger

The ledger records all durable state transitions.

Important event types include:

```text
workspace.created
draft.created
draft.updated
message.submitted
intent.detected
action.proposed
action.authorized
action.rejected
research.started
source.discovered
source.retrieved
source.versioned
claim.extracted
evidence.reviewed
dataset.created
dataset.item_included
dataset.item_excluded
model.started
model.completed
model.failed
worker.leased
worker.completed
checkpoint.created
handoff.exported
task.failed
task.recovered
artifact.created
artifact.superseded
```

Each event contains:

- event ID;
- event type;
- workspace ID;
- actor;
- payload;
- provenance;
- status;
- creation time;
- previous event hash;
- event hash;
- idempotency key.

The ledger must reject duplicate idempotency keys and invalid hash-chain entries.

### 5.5 Artifact store

All significant data must be stored as immutable, content-addressed artifacts.

Artifact types include:

```text
prompt
response
source_raw
source_text
source_metadata
evidence_bundle
claim_set
dataset
checkpoint
handoff
model_config
tool_result
audit_export
embedding
scrutiny_report
```

A changed source produces a new artifact and source version. It must not overwrite the old source.

### 5.6 Task orchestrator

Long-running work must be divided into explicit stages:

```text
created
planned
local_search
web_search
retrieval
parsing
deduplication
claim_extraction
evidence_analysis
dataset_curation
model_analysis
comparison
scrutiny
checkpoint
export
completed
failed
cancelled
```

Each stage records:

- input artifact IDs;
- output artifact IDs;
- dependencies;
- worker;
- lease;
- attempt count;
- status;
- error;
- start time;
- completion time.

This makes recovery possible without rerunning the entire workflow.

## 6. Agent and bot operating protocol

Aetheria is designed for AI models and bots working with humans. Every AI worker must operate under a defined protocol.

### 6.1 Agent roles

A model or bot must declare one or more roles:

```text
researcher
retriever
document_parser
claim_extractor
critic
summarizer
dataset_curator
planner
executor
reviewer
handoff_writer
```

A role limits what the agent may do. A claim extractor should not have file-write or network-send capabilities by default.

### 6.2 Agent context

Every model job should receive a structured context:

```json
{
  "workspace_id": "ws_123",
  "task_id": "task_456",
  "role": "claim_extractor",
  "objective": "Extract factual claims from the supplied sources",
  "allowed_actions": ["read_artifact", "write_claims"],
  "forbidden_actions": ["send_external", "modify_file"],
  "input_artifacts": ["artifact_1", "artifact_2"],
  "output_schema": "ClaimSetV1",
  "evidence_policy": {
    "require_source_span": true,
    "allow_unsupported_claims": true,
    "mark_model_assertions": true
  },
  "human_authorization": {
    "level": "task_scoped",
    "expires_at": "..."
  }
}
```

### 6.3 Agent response requirements

An agent must return structured output containing:

- result;
- claims;
- evidence references;
- uncertainty;
- assumptions;
- failed subtasks;
- requested actions;
- missing information;
- confidence;
- model metadata.

Agents must not conceal uncertainty in prose.

### 6.4 Proposal before execution

Tool-using agents operate through this sequence:

```text
agent proposes action
→ schema validation
→ policy evaluation
→ data classification
→ authorization check
→ user confirmation if required
→ sandboxed execution
→ result validation
→ ledger recording
```

The model never directly invokes an unrestricted tool.

### 6.5 Human escalation

An agent must pause and request human review when:

- evidence conflicts materially;
- the requested action is irreversible;
- private or sensitive data would leave the device;
- a source appears poisoned or malicious;
- the task scope is ambiguous;
- a model output contradicts a user decision;
- an external side effect is proposed;
- the agent lacks evidence for a high-impact claim.

## 7. Research and evidence system

### 7.1 Research request

A research request should include:

```json
{
  "research_id": "res_123",
  "question": "Compare local-first AI architectures for Aetheria Prime",
  "scope": "both",
  "temporal_scope": {
    "published_after": "2023-01-01"
  },
  "required_source_types": ["technical_document", "repository", "paper"],
  "excluded_domains": [],
  "max_sources": 30,
  "require_citations": true,
  "require_counterevidence": true,
  "network_mode": "tor_preferred"
}
```

### 7.2 Source lifecycle

```text
discovered
→ retrieved
→ stored
→ parsed
→ deduplicated
→ assessed
→ cited
→ reviewed
→ superseded or archived
```

Each source record should include:

- canonical URL;
- title;
- publisher;
- source type;
- retrieval method;
- retrieval timestamp;
- publication timestamp, if known;
- raw content hash;
- extracted text hash;
- source version;
- license information;
- parser version;
- source-family identity;
- quality notes;
- prompt-injection warnings.

### 7.3 Evidence spans

An evidence span must point to a precise location:

```json
{
  "source_id": "src_123",
  "source_version": 2,
  "quote": "Exact preserved quotation",
  "location": "page 4, paragraph 2",
  "content_hash": "sha256:...",
  "extraction_method": "pdf_text"
}
```

If exact quotation is unavailable, the system must mark the citation as approximate.

### 7.4 Claim evaluation

Each claim should be evaluated for:

- evidence support;
- contradiction;
- source independence;
- freshness;
- scope match;
- primary versus secondary evidence;
- ambiguity;
- model dependence;
- confidence.

Claim statuses:

```text
supported
partially_supported
unsupported
contradicted
outdated
unreviewed
```

The final answer should distinguish:

```text
Evidence-backed conclusion
Reasonable interpretation
Model-generated hypothesis
Open question
```

## 8. Dataset curation

A temporary research workspace becomes a dataset only through an explicit curation operation.

Every dataset item must include:

- source ID;
- source version;
- decision;
- reason;
- labels;
- reviewer;
- date;
- selection rule;
- related claims.

Required decisions:

```text
candidate
included
excluded
needs_review
```

Dataset exports must include:

- manifest;
- item list;
- selection policy;
- source hashes;
- exclusion decisions;
- known gaps;
- license notes;
- quality notes;
- dataset version.

## 9. Model broker

The Model Broker provides one normalized interface for:

- text generation;
- structured output;
- streaming;
- embeddings;
- tool proposals;
- cancellation;
- retry;
- timeout;
- health checks;
- token and cost accounting.

Providers may include:

```text
local runtime
remote API
trusted peer node
offline mock adapter
```

Every model job must record:

- provider;
- model name;
- model version;
- runtime version;
- model file hash where available;
- system prompt hash;
- prompt template hash;
- sampling parameters;
- context artifact hashes;
- output artifact hash;
- network route;
- privacy class;
- start and completion times.

### Model comparison rule

All compared models must receive:

- the same evidence bundle;
- the same task instructions;
- the same output schema;
- the same source versions;
- the same citation requirements.

The interface must compare outputs by claim rather than only showing side-by-side paragraphs.

## 10. Privacy and network modes

Provide four explicit modes:

```text
Offline only
Direct HTTPS
Tor preferred
Tor only
```

### Offline only

Permits:

- local files;
- local indexes;
- local models;
- local nodes explicitly marked local;
- existing evidence.

Blocks:

- web search;
- remote providers;
- unapproved peer nodes;
- external telemetry.

### Direct HTTPS

Permits configured web and model providers after authorization. Every outbound request is recorded.

### Tor preferred

Attempts Tor first and falls back only if the user explicitly allows fallback.

### Tor only

Blocks all non-Tor network traffic for configured research and node operations.

Tor should be presented accurately as a network-routing option. It does not provide compute capacity, model access, or automatic trust in a remote node.

## 11. Trusted node protocol

A node must have:

- node ID;
- public/private key;
- enrollment record;
- capability declaration;
- data-sharing policy;
- software manifest;
- resource limits;
- lease support;
- signed results;
- revocation status.

A node job must include:

```text
job ID
lease ID
input artifact hashes
allowed data class
model requirements
maximum duration
maximum output size
result schema
expiration
```

The node may receive only artifacts permitted by its policy.

Node lifecycle:

```text
discovered
→ enrollment_pending
→ trusted
→ available
→ leased
→ running
→ completed
→ revoked
```

A completed result must be signed and verified before entering the project ledger.

## 12. Security controls

The first release must include:

- encrypted local secrets;
- no committed API keys;
- local-only mode;
- outbound-data preview;
- explicit remote-provider consent;
- obvious-secret redaction;
- URL validation;
- SSRF protection;
- redirect restrictions;
- file-size limits;
- decompression limits;
- sandboxed document parsing;
- path traversal protection;
- separate read and write permissions;
- confirmation for mutations;
- signed node results;
- lease expiration;
- replay protection;
- audit logs;
- prompt-injection labeling;
- untrusted-content isolation.

Retrieved content must always be treated as data. It must never become system instructions merely because a web page, PDF, repository, or model output contains imperative language.

## 13. User interface

### Workspace

Display:

- current project;
- committed conversation;
- draft input;
- active task;
- model and provider;
- local/remote status;
- pending approvals;
- latest checkpoint;
- next safe action.

### Research panel

Display:

- question;
- search queries;
- search scope;
- network route;
- discovered sources;
- retrieval state;
- timestamps;
- source versions;
- hashes;
- failed sources;
- blocked sources;
- prompt-injection warnings.

### Evidence panel

Display:

- claims;
- exact supporting quotations;
- citations;
- contradictory evidence;
- unsupported assertions;
- source independence;
- freshness;
- confidence;
- review status.

### Dataset panel

Display:

- candidates;
- included items;
- excluded items;
- reasons;
- labels;
- dataset version;
- selection rules;
- provenance;
- export controls.

### Model comparison panel

Display:

- model identity;
- provider;
- local or remote status;
- input bundle hash;
- output;
- claim-level agreement;
- disagreement;
- unsupported claims;
- missing evidence;
- synthesis.

### Continuity panel

Display:

- current checkpoint;
- last committed event;
- active stages;
- completed stages;
- failed stages;
- unresolved questions;
- required approvals;
- stale artifacts;
- next safe action;
- export/import controls.

### Node panel

Display:

- node identity;
- trust state;
- capabilities;
- available resources;
- privacy policy;
- current lease;
- network route;
- signed result status;
- revocation controls.

### Audit panel

Display:

- messages;
- tool proposals;
- authorizations;
- outbound requests;
- model calls;
- retrieved sources;
- file operations;
- worker assignments;
- failures;
- recovery actions.

## 14. End-to-end demo

Use the question:

> Compare several local-first AI architectures and determine which approach best fits Aetheria Prime.

The demonstration should:

1. Start in local mode.
2. Type the question gradually.
3. Show draft analysis.
4. Prove that drafts do not execute.
5. Submit the exact message.
6. Show the committed event and hash.
7. Create a research request.
8. Search local files.
9. Search the web.
10. Retrieve and preserve sources.
11. Display timestamps, URLs, versions, routes, and hashes.
12. Extract claims and evidence spans.
13. Show a real source conflict.
14. Create a temporary dataset.
15. Include and exclude sources with reasons.
16. Freeze an evidence bundle.
17. Run the same bundle through two local models and optionally a remote model.
18. Compare outputs claim by claim.
19. Generate a scrutiny report.
20. Simulate provider exhaustion or worker failure.
21. Create a checkpoint and `HANDOFF.md`.
22. Shut down the application.
23. Restart it.
24. Replay or import the checkpoint.
25. Resume from the last safe stage.
26. Export the final research bundle and curated dataset.
27. Show the complete audit trail.
28. Demonstrate a limited trusted-node task.
29. Show the Tor route selection and signed result.

The restart and recovery sequence must use real persisted state, not a scripted animation.

## 15. Required outputs

```text
demo-output/
  HANDOFF.md
  checkpoint.json
  research-request.json
  research-bundle.json
  manifest.json
  sources/
  evidence/
  claims.json
  dataset-manifest.json
  model-comparisons/
  scrutiny-report.md
  audit-log.jsonl
  security-events.jsonl
  replay-result.json
```

`manifest.json` must list:

- artifact ID;
- path;
- media type;
- content hash;
- producing event;
- dependencies;
- creation time;
- version.

## 16. Recommended technical stack

```text
Backend:        Python, FastAPI, Pydantic
Frontend:       React, TypeScript, Vite
Database:       SQLite initially
Search:         SQLite FTS5, hybrid retrieval interface
Storage:        content-addressed local filesystem
Models:         local runtime adapter plus OpenAI-compatible adapter
Workers:        Python worker process with leases
Streaming:      Server-Sent Events initially
Documents:      HTML, Markdown, PDF, text extraction
Testing:        pytest, Playwright
Packaging:      Docker Compose plus native local runner
Networking:     HTTPS and optional Tor integration
```

Use interfaces so individual components can later be replaced with PostgreSQL, object storage, a dedicated queue, or a larger vector index.

## 17. API surface

```text
POST   /api/workspaces
GET    /api/workspaces/{id}
POST   /api/drafts
PATCH  /api/drafts/{id}
POST   /api/messages/submit
GET    /api/conversations/{id}/events

POST   /api/research
GET    /api/research/{id}
POST   /api/research/{id}/run
GET    /api/research/{id}/sources

GET    /api/sources/{id}
GET    /api/sources/{id}/versions
GET    /api/sources/{id}/evidence

POST   /api/datasets
POST   /api/datasets/{id}/items
PATCH  /api/datasets/{id}/items/{item_id}
POST   /api/datasets/{id}/export

POST   /api/model-jobs
GET    /api/model-jobs/{id}
POST   /api/model-jobs/{id}/cancel

POST   /api/actions/{id}/authorize
POST   /api/actions/{id}/reject

POST   /api/checkpoints
GET    /api/checkpoints/latest
POST   /api/recovery/replay
POST   /api/handoffs/export
POST   /api/handoffs/import

GET    /api/nodes
POST   /api/nodes/register
POST   /api/nodes/{id}/revoke
POST   /api/nodes/{id}/jobs

GET    /api/audit
POST   /api/ledger/verify
```

The frontend must never modify durable state directly. It submits commands. The backend validates the command, applies policy, writes the event, updates projections, and returns the resulting state.

## 18. Acceptance criteria

The product is complete only when:

- draft text never triggers actions;
- Enter commits exact text;
- committed events are hash-linked;
- local search works offline;
- web retrieval works when enabled;
- sources are saved with timestamps and hashes;
- source changes create new versions;
- claims link to evidence spans;
- unsupported claims are visible;
- contradictions are visible;
- citation links survive model switching;
- dataset decisions are recorded;
- models receive identical evidence bundles;
- model disagreement is visible;
- remote transmission requires authorization;
- local-only mode blocks external calls;
- worker failure does not duplicate commits;
- checkpoints survive application restart;
- handoffs are importable;
- audit logs show external calls;
- Tor can be selected as a route;
- trusted nodes receive only permitted data;
- node results are authenticated;
- all required artifacts can be exported;
- the complete demo runs from documented instructions;
- a new user can understand the result without reading source code.

## 19. Development sequence

### Release 1: Durable local core

Build first:

- workspace;
- draft manager;
- commit gate;
- event ledger;
- artifact store;
- local files;
- SQLite search;
- checkpoints;
- audit viewer.

### Release 2: Evidence workflow

Add:

- web retrieval;
- source versions;
- claim extraction;
- evidence spans;
- contradiction handling;
- dataset curation;
- scrutiny reports.

### Release 3: Model independence

Add:

- model broker;
- two local adapters;
- remote adapter;
- structured outputs;
- model comparison;
- fallback routing;
- model fingerprints.

### Release 4: Recovery and distribution

Add:

- worker leases;
- crash recovery;
- trusted-node enrollment;
- signed results;
- encrypted bundle transfer;
- Tor-preferred and Tor-only modes.

### Release 5: Competitive hardening

Add:

- evaluation harness;
- red-team suite;
- performance benchmarks;
- migration tools;
- reproducible demo corpus;
- documentation;
- backup and restore;
- project export/import;
- permission templates;
- accessibility and usability refinement.

## 20. What not to build initially

Defer:

- unrestricted shell access;
- autonomous production changes;
- hidden background actions;
- custom blockchain infrastructure;
- anonymous compute marketplaces;
- fully autonomous multi-agent planning;
- automatic publication of datasets;
- large-scale peer discovery;
- complex cross-project memory;
- dependence on Tor for compute;
- a custom model-training platform.

The competitive advantage is not maximum autonomy. It is **controlled continuity with evidence, provenance, and recovery**.

## Final product definition

Aetheria Prime is complete when a user can:

> Ask a question, research it locally and on the web, preserve and curate the evidence, compare multiple AI workers, inspect uncertainty and disagreement, authorize or reject proposed actions, stop the system, restart it later, and continue from durable project state without depending on one model, provider, chat window, or network path.

That is the cohesive product. The essential order of priority is:

```text
1. Durable state
2. Draft/commit safety
3. Evidence and provenance
4. Human authorization
5. Reliable recovery
6. Model interoperability
7. Dataset curation
8. Local-first execution
9. Trusted worker nodes
10. Tor and network routing
11. Security hardening
12. Evaluation and polished demonstration
```

If those capabilities work together in one uninterrupted, inspectable workflow, Aetheria Prime becomes a serious product rather than a collection of AI features.