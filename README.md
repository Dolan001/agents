# ai_workflow

`ai_workflow` is a Codex-first control plane that turns a required PRD and optional
design evidence into a verified full-stack monorepo. It coordinates specialized agents,
skills, phase rules, framework behavior packs, deterministic checks, evidence gates,
durable checkpoints, and safe Git delivery.

The workflow repository contains no demonstration application or framework source to
copy. Its linked framework repositories are code-free behavior packs. During execution,
agents use the selected guidance to create original application code in the user's
separate target repository.

## What the workflow builds

The supported application combinations are:

| Layer | Supported frameworks | Target |
|---|---|---|
| Web frontend | React or Next.js | `apps/frontend` |
| Mobile | Flutter for Android and iOS | `apps/mobile` |
| Backend | Django REST Framework or FastAPI | `apps/backend` |
| AI capability | RAG (optional, requirement-triggered) | Selected backend and clients |
| Deployment | AWS (optional) | `infra`, `.github/workflows`, `ops` |

Both backend choices use PostgreSQL. Generated tables and schema changes are owned by
reviewed Django migrations or Alembic revisions; neither backend may fall back to SQLite
or create production tables directly during application startup.

Projects may be web only, mobile only, or web plus mobile; every mode includes one
supported backend. The first selected client phase creates the monorepo root contract:

```text
target-project/
├── .agents/                 # this repository, installed as a Git submodule
├── .ai/                     # generated workflow state and evidence
├── apps/
│   ├── frontend/
│   ├── mobile/
│   └── backend/
├── packages/
│   └── api-client/
├── HTML/
│   ├── source/
│   └── approved/
├── docs/
│   ├── generated/
│   └── api/
├── tests/
├── artifacts/
├── README.md
├── .gitignore
├── .env.example
├── compose.yaml
└── Makefile
```

Design-only commands stop before this monorepo is created. `start-frontend` or
`start-mobile` is the first command allowed to scaffold the application structure.

## Setup for a user who knows only Codex

The user does not need to remember or run Git submodule commands. After adding the PRD to the
current project, open Codex in that project and send this single plain-text request:

```text
setup-workflow "https://github.com/Dolan001/ai_workflow.git"
```

`setup-workflow` is a readable instruction to Codex, not a terminal command, `$skill`, or installed
plugin. The quoted value is the workflow Git URL.

That plain request authorizes Codex to inspect the linked repository onboarding contract, verify the
project boundary, and perform the installation. Codex
must:

1. Confirm the current directory is the intended project and initialize local Git only if needed.
2. Refuse to overwrite an existing `.agents` path unless it is already this registered submodule.
3. Execute:

   ```bash
   git submodule add -b dev https://github.com/Dolan001/ai_workflow.git .agents
   git submodule update --init --recursive
   ```

4. Verify `.agents/skills/catalog.json`, the executable `.agents/bin/ai`, and all eight nested
   behavior repositories.
5. Make no application changes, commits, pushes, or remote branches during setup.
6. Tell the user to reopen Codex so skill discovery refreshes.

After reopening Codex, the only command needed is:

```text
$start-build
```

The workflow auto-discovers exactly one PRD, uses framework declarations already in it, and asks
only for genuinely missing choices such as a framework or GitHub user. A setup skill cannot provide
this first installation because skills inside `.agents` do not exist until after the repository is
installed; the plain `setup-workflow "<git-url>"` request above is the portable bootstrap.

## Quick start

The following is the manual fallback for an experienced user. Run it inside the target project, not
inside `ai_workflow` itself:

```bash
git submodule add -b dev https://github.com/Dolan001/ai_workflow.git .agents
git submodule update --init --recursive
```

Add the required PRD at one of the auto-discovered locations:

```text
docs/PRD.md
PRD.md
docs/prd.md
prd.md
```

If only informal requirements are available, create `REQUIREMENTS.md` and invoke:

```text
$generate-prd REQUIREMENTS.md
```

The generator sanitizes credential material, asks only for blocking decisions, validates the exact
build contract, and writes `PRD.md`. Then invoke `$start-build` normally.

Keep exactly one of those files, or pass an explicit `--prd` path. Then reopen Codex
so it discovers `.agents/skills`, and type this in Codex chat:

```text
$start-build --github-user <github-user>
```

`$start-build` is a Codex skill invocation, not a terminal command. It runs every missing
application phase through delivery and defers deployment. It does not push by default.

## Complete process: A to Z

For the ordered beginner workflow plus every user-facing `$skill`, accepted flag, default, and
equivalent CLI invocation, see [`USER_GUIDE.md`](USER_GUIDE.md).

### 1. Install and pin the workflow

The real project stores `ai_workflow` directly at `.agents`. The nested `base_ai`,
`drf_ai`, `fastapi_ai`, `flutter_ai`, `react_ai`, `nextjs_ai`, `rag_ai`, and `aws_ai` repositories are initialized
recursively. Commit `.gitmodules` and the `.agents` gitlink so every collaborator gets
the same reviewed workflow version:

```bash
git add .gitmodules .agents
git commit -m "chore: add AI workflow"
```

Another developer can then clone the project with:

```bash
git clone --recurse-submodules <project-url>
```

or initialize an existing clone with:

```bash
git submodule update --init --recursive
```

### 2. Supply the project inputs

The PRD is required and must be non-empty. It should describe product scope, users,
features, acceptance criteria, business rules, data, integrations, security needs, and
non-functional requirements.

If the user does not yet have a PRD, `$generate-prd <requirements-path>` provides an optional
pre-workflow intake. It stores only sanitized input and answers under `.ai/prd-intake/`, batches at
most five material questions, and writes the final PRD only after deterministic build-readiness
validation. Actual passwords, tokens, private keys, connection credentials, or access-key values
block generation; replace them with variable names or obvious placeholders and rotate exposed values.
Clarification answers must use `QNNN=answer`, cover the complete active question batch exactly once,
and cannot be attached to a stale or changed requirements source.

The generator does not use one generic architecture paragraph. It loads the monorepo profile plus
only the selected DRF or FastAPI backend profile, React or Next.js web profile, Flutter mobile
profile, and AWS profile when deployment is requested. The resulting `Architecture and Capability
Decisions` section is a machine-checked decision matrix covering PostgreSQL, `/api/v1`, API
contracts, authentication and authorization, migrations and backend boundaries, query budgets,
client states and accessibility,
background work, schedules, realtime, uploads/storage, audit and retention. AWS PRDs additionally
require environment isolation, region/domain ownership, availability, RPO/RTO, traffic, cost,
residency, backup retention, approval ownership, runtime topology, identity, rollback, alarms, and
restore requirements. Every architecture decision records whether it came from supplied
requirements, a clarification answer, a workflow invariant, or an explicit assumption; product- and
operations-owned choices cannot pass as assumptions.

Framework declarations are optional. To make automatic selection unambiguous, use
explicit declarations such as:

```markdown
Frontend framework: Next.js
Mobile framework: Flutter
Backend framework: Django REST Framework
Deployment provider: AWS
```

Optional design inputs must already be inside the target repository and can be passed
repeatedly:

```text
$start-build --github-user dolan --html HTML/input/home.html
$start-build --github-user dolan \
  --screenshot HTML/input/home-desktop.png \
  --screenshot HTML/input/home-mobile.png
```

HTML accepts `.html` or `.htm`. Screenshots accept valid PNG, JPEG, or WebP bytes.
Inputs are preserved under `HTML/source/`, hashed, and treated as untrusted design data.

### 3. Resolve frameworks before building

The workflow accepts only React or Next.js for web, Flutter for Android/iOS mobile,
and Django REST Framework or FastAPI for backend. AWS is the only deployment provider currently
accepted. At least one client is required.

- If the PRD explicitly declares a supported framework, Codex uses it without asking.
- If a framework required by the requested stopping point is absent, Codex asks only
  for the missing choice.
- Unsupported, conflicting, ambiguous, or multiple declarations fail before
  application code or runtime state is created.
- A saved framework choice cannot be silently changed during resume.
- AWS is activated only by `$start-deployment --deployment aws`. `start-build`, `resume-build`, and
  legacy `one-shot` always defer it, even when the PRD declares AWS; incidental AWS references also
  remain inactive.

Design specification and HTML generation do not require framework choices.
`start-frontend` requires a web selection; `start-mobile` requires Flutter. Backend and
later stages require one or both clients plus a backend. An absent optional client is
recorded as a skipped phase and loads no behavior-pack context.

### 4. Establish a safe Git boundary

For a fresh workflow, provide `--github-user` unless the project is already on a valid
workflow branch. Initialization creates or preserves a branch matching:

```text
ai/<github-user>/<feature-slug>
```

`main`, `master`, `dev`, `develop`, `stage`, `staging`, `production`, and `prod` are
protected from normal build delivery. The branch and baseline commit are recorded in
`.ai/state.json`. Resume fails if the checked-out branch no longer matches that saved
boundary.

### 5. Start the requested workflow

For a complete new build, invoke:

```text
$start-build --github-user <github-user>
```

The skill reads the shared start-command contract, validates arguments, resolves
frameworks, and invokes the Codex adapter. The engine first validates that all phase
manifests, blueprints, agents, hooks, and gates are connected.

Use a narrower command when only part of the lifecycle is required:

| Codex skill | Runs missing prerequisites through | Creates monorepo? |
|---|---|---:|
| `$generate-prd` | Validated `PRD.md`; stops before build initialization | No |
| `$start-design` | Design specification | No |
| `$start-generatehtml` | Approved static HTML | No |
| `$start-frontend` | Frontend gate | Yes |
| `$start-mobile` | Flutter Android/iOS gate | Yes |
| `$sync-design` | Approved HTML comparison, repair, and independent verification | No new monorepo |
| `$start-backend` | Backend gate | Yes |
| `$start-integration` | Typed integration gate | Yes |
| `$start-testing` | Independent testing and security gate | Yes |
| `$start-deployment` | AWS generation/readiness; no cloud mutation | Yes |
| `$start-delivery` | Release-readiness gate | Yes |
| `$start-build` | Complete non-deployment application lifecycle | Yes |
| `$resume-build` | Unchanged non-deployment checkpoints through delivery | As needed |
| `$workflow-status` | Read-only status report | No change |

Every start command runs missing prerequisites. For example, `$start-backend` does not
skip requirements, design, or any selected client when they are incomplete.

`$sync-design` is also available after implementation. By default it repairs selected web/mobile
targets; `--check-only` reports localized drift without application edits. Approved HTML remains
immutable unless the user explicitly passes `--allow-baseline-update`. Each case renders the
approved HTML and application at the same physical dimensions, compares every unmasked RGBA pixel,
and binds the captures, generated diff, thresholds, and numeric metrics by SHA-256. Strict zero
tolerance is the default. A pixel pass is mandatory but does not replace semantic, responsive,
state, accessibility, or native-platform verification.

### 6. Bootstrap the target

Bootstrap performs deterministic preflight work before application generation:

- validates the required PRD;
- inventories the repository and detects existing structure;
- classifies design inputs;
- records project mode, selected frameworks, Git baseline, assumptions, and branch;
- creates the durable `.ai` control directories; and
- passes the bootstrap evidence gate.

This phase does not write application source.

### 7. Reconcile requirements and contracts

The requirements phase converts the PRD into executable delivery contracts:

- normalized requirements in `docs/generated/requirements.json`;
- reconciliation evidence in `docs/generated/requirement-reconciliation.json`;
- API and data planning under `docs/api/`;
- vertical-slice tasks in `.ai/task-queue.json`; and
- dependencies, allowed paths, acceptance criteria, test requirements, and evidence
  requirements for each task.

Application implementation is still prohibited. The requirements gate must pass before
design work starts.

### 8. Produce and approve HTML

Design input precedence is deterministic:

```text
supplied HTML → screenshots/design evidence → PRD only
```

- With supplied HTML, agents validate, improve when required, and approve it.
- With screenshots but no HTML, agents generate HTML from visual evidence plus PRD.
- With neither, agents generate HTML from the PRD and design specification.

The route is recorded in `.ai/design-inputs.json`. The design phase produces
`HTML/design-specification.md`, approved static HTML under `HTML/approved/`, and design
evidence. Accessibility and HTML-quality checks must pass before frontend work.

`$start-design` intentionally stops after `HTML/design-specification.md`.
`$start-generatehtml` completes the design gate and stops before application code.

### 9. Build the optional web frontend

When selected, the frontend phase loads only React or Next.js guidance. Specialized
agents:

- create and validate the framework-neutral monorepo root;
- implement the approved HTML as production frontend code;
- preserve requirements, responsive behavior, accessibility, and design intent;
- define project-owned frontend test commands; and
- produce feature and structure evidence.

The generated `apps/frontend` structure must match the selected behavior pack's exact
project-structure contract before the frontend gate passes. If web is not selected,
the phase is checkpointed as skipped without invoking an agent.

Each framework node receives only its role-specific skill and the relevant selected
pack rules and hooks. React/Next.js implementation and verification are therefore
performed by the selected pack's implementer and independent verifier, not generic
framework-neutral substitutes.

Before frontend approval, the design-fidelity resolver captures deterministic mobile, tablet, and
desktop cases against hashed approved HTML, writes a repair plan, corrects meaningful drift, and
recaptures affected routes/states. The existing selected frontend verifier then independently checks
the raw captures, accessibility, responsiveness, focused tests, and production build.

### 10. Build the optional Flutter mobile application

When selected, the mobile phase loads only `flutter_ai`, establishes any missing
monorepo root structure, and generates one application under `apps/mobile/` for Android
and iOS. It creates feature-first boundaries, validated environments, navigation,
localization, adaptive design, typed networking, secure storage, lifecycle and offline
behavior, and unit/widget/golden/integration test foundations.

The gate validates the exact Flutter structure contract, Android and iOS platform
directories, accessibility and responsive evidence, Flutter analysis/tests, and
truthful platform release readiness. Unavailable iOS tooling must be reported as
unverified rather than silently passed. If mobile is not selected, no Flutter context
is loaded and the phase is checkpointed as skipped.

Before mobile approval, the same resolver compares stable Flutter goldens for Android and iOS with
approved HTML semantics while preserving valid Material/Cupertino differences. The Flutter verifier
independently checks all manifest cases, responsive/text-scale behavior, accessibility, analysis,
focused tests, and golden evidence.

### 11. Build the backend

After selected client approval, the backend phase loads only Django REST Framework or
FastAPI guidance. It uses reconciled requirements and observed web/mobile data needs to:

- implement API endpoints, domain logic, persistence, authentication, permissions,
  validation, exceptions, and error responses;
- create or finalize API contracts and backend test commands;
- run focused backend verification; and
- validate required paths, one dependency-lock strategy, activated domain capabilities, and
  executable source policies against the selected framework contract.

The backend gate blocks progression when required behavior, evidence, or structure is
missing. Its final phase decision belongs to the selected DRF or FastAPI independent
verifier; API contract verification is repeated at the integration boundary.

The gate also validates `.ai/evidence/database-verification.json`. A disposable
PostgreSQL database must accept a complete migration from empty state, remain at the
current migration head with no drift, produce a no-op second upgrade, expose expected
tables/constraints/indexes, and satisfy measured plans or query budgets for affected
hot paths.

The independent verifier must also produce `.ai/evidence/backend-verification.json` with exact
successful commands for application import, startup/readiness, positive and negative API behavior,
authorization, transaction/concurrency cases, OpenAPI, and security. The backend phase cannot pass
with a placeholder `verified` flag or structure-only fixture.

Durable background processing is requirement-triggered rather than generated for every backend.
When a domain adds a task, either backend uses Celery with Redis and a PostgreSQL transactional
outbox/job record. The structure gate then requires the framework worker entrypoint, explicit domain
task discovery, `celery[redis]`, broker environment configuration, Redis and worker compose services,
a worker health script, and domain task tests. Messages carry scalar IDs; tasks open fresh database
state and must tolerate duplicate delivery. The backend evidence gate additionally requires live
broker, worker startup, enqueue/consume, bounded retry, idempotency, outbox, terminal-failure, and—if
used—schedule checks. Celery Beat and a result backend are omitted unless requirements need them.
FastAPI in-process `BackgroundTasks` is allowed only for explicitly disposable work and does not
satisfy this durable-work gate.

Realtime chat, notifications, presence, and live updates are conditional capabilities. The
requirements phase defines one versioned event/command/cursor contract. PostgreSQL stores messages,
membership, participant receipts, notifications, command deduplication, stream sequence, and outbox
events; Redis performs transient multi-instance fan-out and presence. Selected clients implement
bounded reconnect with jitter, cursor replay, sequence-gap detection, deduplication, offline/degraded
states, and lifecycle cleanup. Reusable access tokens are prohibited in WebSocket URLs; use secure
cookies or short-lived single-use tickets acquired over HTTPS. Activated realtime surfaces produce
`.ai/evidence/realtime/<phase>.json` proving authorization, protocol validation, limits, recovery,
and relevant backend or client runtime checks.

RAG is also conditional. The PRD generator records `RAG: Required` or `RAG: Not required`, and
existing PRDs are deterministically recognized from explicit retrieval-augmented generation,
semantic retrieval, document Q&A, grounded-answer, or knowledge-base requirements. When active,
`rag_ai` augments the selected framework packs rather than generating a separate service.

The default production design uses PostgreSQL full-text search plus pgvector hybrid retrieval,
durable Celery/Redis ingestion, immutable source and embedding versions, authorization inside every
candidate query, provider-neutral embedding/reranking/generation adapters, validated citations, and
explicit abstention. User uploads use approved object storage. SSE is preferred for one-way answer
streaming; WebSocket remains requirement-triggered for bidirectional behavior.

Independent RAG evidence is required for the backend, every selected client, and integration under
`.ai/evidence/rag/`. Verification uses a versioned evaluation set and checks retrieval separately
from generation: recall/ranking, zero ACL leakage, groundedness, citation precision/coverage,
unanswerable-query behavior, prompt injection and poisoned sources, deletion/reindexing, provider
degradation, latency, and per-query usage/cost thresholds. Approximate retrieval is compared with an
exact-search baseline so a visually convincing demo cannot pass with poor recall.

### 12. Integrate selected clients and backend

The integration phase generates or updates typed web and/or Dart API boundaries,
connects selected client flows to real backend APIs, and creates contract and
integration tests. Project-owned OpenAPI/client generation commands run without shell
evaluation. The gate requires every selected client, backend, and contract to agree.

### 13. Run independent testing and security review

The testing phase runs configured project-owned commands from
`.ai/test-commands.json`, including applicable backend, frontend, mobile, contract,
integration, and end-to-end lanes. Independent agents verify:

- PRD acceptance criteria and complete user journeys;
- API success responses, validation, exceptions, and error behavior;
- web/mobile/backend integration, browser behavior, and Android/iOS journeys;
- approved-HTML or screenshot design fidelity;
- responsiveness and accessibility;
- security controls and high-risk findings; and
- affected full tests, not only the narrow implementation check.

Results are stored under `artifacts/tests/`, `artifacts/security/`, and
`.ai/evidence/features/`. A task is marked verified only when its final evidence passes.

### 14. Generate and verify optional AWS deployment assets

When AWS is explicitly selected, this phase runs only after testing and security pass. It generates
target-owned OpenTofu-compatible environment roots under `infra/`, pinned GitHub Actions under
`.github/workflows/`, operations material under `ops/`, and architecture under `docs/deployment/`.

The default uses CloudFront, WAF, ALB, ECS Fargate, ECR, RDS PostgreSQL, ElastiCache Redis, S3,
Route 53, ACM, Secrets Manager, KMS, CloudWatch, and AWS Backup as required. React uses S3 plus
CloudFront; Next.js SSR runs on ECS. FastAPI uses Uvicorn. DRF uses Gunicorn only for WSGI-only
workloads and ASGI for WebSockets. Nginx is conditional when CloudFront, WAF, and ALB cannot meet a
documented proxy requirement.

`$start-deployment` is always separate from `$start-build` and never contacts AWS, assumes credentials,
applies infrastructure, deploys, or changes DNS. Its gate verifies structure, IaC, GitHub OIDC,
immutable digest promotion, protected production approval, migration safety, monitoring, rollback,
backup, and recovery. Without an explicit AWS selection, the phase is skipped without loading it.

Generated AWS projects include this complete local/manual credential contract:

```dotenv
AWS_ACCESS_KEY_ID=<your aws access key id>
AWS_SECRET_ACCESS_KEY=<your aws secret access key>
AWS_REGION=<your aws region>
AWS_SESSION_TOKEN=<optional temporary session token>
```

Copy `.env.example` to `.env` and replace the required placeholders. Explicit local deployment
commands automatically load only these AWS variables after verifying that `.env` is ignored and
untracked, and redact their values from captured output. `AWS_SESSION_TOKEN` is needed only for
temporary credentials. GitHub Actions uses OIDC instead of `.env`, and ECS workloads use IAM roles
plus Secrets Manager.

Live operations are separate and require explicit authorization:

```text
$deploy-staging
$deployment-status
$deploy-production
$rollback-deployment
```

Production must promote the staging-verified digest. Rollback names an environment and never
automatically reverses destructive database changes. Project-owned argv commands perform mutations
and must produce validated post-operation evidence.

### 15. Complete delivery

The delivery phase aggregates verified evidence into `artifacts/final/` and evaluates
release readiness. It does not deploy or merge.

No start command commits or pushes unless the user explicitly requests it:

```text
$start-build --github-user dolan --commit-verified
$start-build --github-user dolan --push
```

`--commit-verified` stages only files declared by independently verified feature
evidence and commits them on the current safe feature branch. `--push` implies verified
commits and pushes that same branch to `origin`. Unverified or out-of-scope paths fail
closed.

### 16. Inspect, resume, and recover

At any time, inspect state without changing the project:

```text
$workflow-status
```

If execution stops, fix any external blocker and continue with:

```text
$resume-build
```

Verified nodes are keyed by hashes of their declared inputs. Unchanged nodes are
reused; changed inputs invalidate only affected work. Each failed agentic node gets at
most two retries. The first attempt does not load recovery guidance. A retry receives
the concise prior failure and the `recover-failure` skill. Exhausted failures are
recorded in `.ai/failures.jsonl` and stop the phase.

The executable `on_failure` hook also tracks every recovered or terminal error under
`.ai/issues/`. `events.jsonl` preserves every occurrence, `issues.json` groups repeated
errors, `summary.json` exposes counts, and `REPORT.md` provides a later-resolution
backlog. Secret values and full logs/prompts are never stored. `$workflow-status`
reports unresolved and resolved totals, and delivery includes the issue report in its
final evidence review.

### 17. Resolve post-build bugs or changes with a token

Create exactly one scoped token at:

```text
frontend/TKN001/TOKEN.md
mobile/TKN001/TOKEN.md
backend/TKN001/TOKEN.md
```

The minimum token format is:

```markdown
# Short problem title

## Description
Describe the observed behavior, expected behavior, and relevant conditions.
```

Optional sibling evidence can use consecutive names:

```text
current1.png
current2.png
expected1.png
expected2.png
```

PNG, JPEG, and WebP are supported. Invoke diagnosis from the branch that must receive
the eventual PR:

```text
$resolve-token frontend/TKN001/TOKEN.md
```

The first invocation validates scope and images, records the exact current branch as
the PR base, diagnoses without modifying application files, writes a plan under
`.ai/token-runs/TKN001/`, presents it, and waits for explicit approval.

After reviewing and approving the plan, Codex runs:

```text
$resolve-token frontend/TKN001/TOKEN.md --approve
```

The resolver verifies that the recorded base still matches its remote commit, creates
`ai/<github-user>/<token-id>`, implements only the approved scope, runs focused and
affected tests, validates observed changed paths, commits, pushes the token branch, and
opens an unmerged PR targeting the exact recorded base branch. That base can have any
valid name, including `main` or `dev`; the token resolver never pushes or merges it.
GitHub CLI authentication and an existing remote base branch are required.
The route selects the matching React/Next.js, Flutter, or backend behavior pack and
enforces changes under `apps/frontend`, `apps/mobile`, or `apps/backend` respectively.

## Runtime state and evidence

`.agents` is the versioned workflow submodule. `.ai` is generated per-project runtime
state and remains separate:

```text
.ai/
├── prd-intake/              # sanitized requirements, questions, answers, candidate, and status
├── state.json               # lifecycle, frameworks, branch, and completed phases
├── task-queue.json          # vertical-slice task contracts and status
├── node-state.json          # verified node checkpoints and input hashes
├── design-inputs.json       # HTML/screenshot/PRD routing decision
├── test-commands.json       # approved argv-based project test commands
├── path-leases.json         # controlled write ownership
├── decisions.jsonl          # durable workflow decisions
├── failures.jsonl           # failure and retry evidence
├── issues/                  # error events, grouped issues, summary, and readable report
├── discovery/               # repository inventory
├── context-bundles/         # bounded task-specific context manifests
├── prompts/                 # exact dispatched node prompts
├── logs/                    # bounded adapter results
├── evidence/                # gates, structure, design, feature, and deployment verification
└── token-runs/              # token plans, state, and implementation evidence
```

Do not manually edit state to bypass a gate. Use `$workflow-status` to identify the
failed artifact and resume after correcting the actual cause.

## Accuracy, speed, and token controls

- Every agentic node has a required artifact contract and a phase evidence gate.
- The scheduler runs phases sequentially to prevent client/backend contract drift.
- Only selected web, mobile, backend, and optional AWS behavior packs are loaded.
- `build-context-bundle` creates an auditable manifest capped at 12 files and 60,000
  characters for phase work and 10 files/45,000 characters for feature work,
  prioritizing requirement anchors, contracts, affected code, and tests while excluding
  dependencies, caches, build output, and duplicated PRD payloads.
- Context manifests store paths, hashes, priorities, and sizes instead of duplicating
  project source in orchestration prompts.
- Agents use search and exact-range reads and must record necessary context expansion.
- `recover-failure` is loaded only after a real failure, never on the normal path.
- Verified-node caching and durable checkpoints prevent unchanged work from repeating.
- Inputs, PRD text, HTML, screenshots, and token contents are treated as untrusted data.
- Agent adapters and project commands receive fixed argument arrays; user content is
  never evaluated as shell text.

## Existing or brownfield projects

Use explicit adoption for an existing codebase. The engine inventories existing source,
detects known frameworks where possible, records a Git baseline, reconciles PRD
requirements against current files, and preserves verified existing work:

```bash
./.agents/bin/ai adopt --project . --prd docs/PRD.md \
  --frontend nextjs --mobile flutter --backend fastapi --github-user dolan
./.agents/bin/ai reconcile --project .
./.agents/bin/ai plan --project . --remaining
./.agents/bin/ai start-build --project . --adapter codex
```

Adoption is explicit; a normal fresh `$start-build` does not silently reinterpret an
existing application as brownfield state.

## Direct CLI reference

The Codex skills are the recommended interface. The deterministic engine remains
available at `./.agents/bin/ai`:

```bash
# Validate environment and control-plane wiring
./.agents/bin/ai doctor --project .
./.agents/bin/ai pipeline

# Initialize or adopt
./.agents/bin/ai init --project . --prd docs/PRD.md \
  --frontend nextjs --mobile flutter --backend django-drf --github-user dolan
./.agents/bin/ai adopt --project . --prd docs/PRD.md \
  --frontend react --backend fastapi --github-user dolan

# Inspect, reconcile, and plan
./.agents/bin/ai inspect --project . --deep
./.agents/bin/ai reconcile --project .
./.agents/bin/ai plan --project . --remaining
./.agents/bin/ai status --project . --json

# Execute stage commands
./.agents/bin/ai generate-prd --project . --requirements REQUIREMENTS.md --output PRD.md --adapter codex
./.agents/bin/ai start-design --project . --adapter codex
./.agents/bin/ai start-generatehtml --project . --adapter codex
./.agents/bin/ai start-frontend --project . --adapter codex --frontend nextjs
./.agents/bin/ai start-mobile --project . --adapter codex --mobile flutter
./.agents/bin/ai sync-design --project . --target all --adapter codex
./.agents/bin/ai sync-design --project . --target frontend --check-only --adapter codex
# Internal deterministic primitive used by the resolver and independent verifier
./.agents/bin/ai compare-images --project . --reference reference.png --actual actual.png \
  --diff diff.png --metrics metrics.json
./.agents/bin/ai start-backend --project . --adapter codex \
  --frontend nextjs --mobile flutter --backend django-drf
./.agents/bin/ai start-integration --project . --adapter codex
./.agents/bin/ai start-testing --project . --adapter codex
./.agents/bin/ai start-deployment --project . --adapter codex --deployment aws
./.agents/bin/ai deployment-status --project .
./.agents/bin/ai deploy-staging --project . --execute
./.agents/bin/ai deploy-production --project . --execute --approve-production
./.agents/bin/ai rollback-deployment --project . --environment production \
  --execute --approve-rollback
./.agents/bin/ai start-delivery --project . --adapter codex
./.agents/bin/ai start-build --project . --adapter codex

# Verify or run configured tests
./.agents/bin/ai verify --project .
./.agents/bin/ai test --project . --all
./.agents/bin/ai test --project . --all --execute

# Dry-run and explicitly execute a safe push
./.agents/bin/ai push --project .
./.agents/bin/ai push --project . --execute
```

The lower-level `one-shot` command is a dry run unless `--execute` is supplied. It
requires at least one web/mobile client and one backend:

```bash
./.agents/bin/ai one-shot --project . --prd docs/PRD.md \
  --mobile flutter --backend django-drf --github-user dolan \
  --branch-feature initial-build

./.agents/bin/ai one-shot --project . --prd docs/PRD.md \
  --frontend nextjs --mobile flutter --backend django-drf --github-user dolan \
  --branch-feature initial-build --adapter codex --execute
```

`clean-state --yes` permanently removes `.ai`, including the build-issue history, and
is intentionally destructive. Archive `.ai/issues/` first when that history must be
retained. It is not a normal recovery step.

## Linked repositories

The workflow pins exact reviewed commits for eight behavior repositories while each
submodule records `branch = dev` for explicit update operations:

```text
.agents/
├── agents/                  # orchestration agents
├── blueprints/              # deterministic and agentic node graphs
├── commands/                # entry contracts
├── gates/                   # phase evidence contracts
├── hooks/                   # lifecycle instructions
├── pipeline/                # manifests, evaluation, and recovery policy
├── rules/                   # shared and phase scope rules
├── skills/                  # Codex-discoverable user entrypoints
├── base_ai/                 # shared agents and skills
├── aws_ai/                  # AWS infrastructure and deployment behavior pack
├── drf_ai/                  # Django DRF behavior pack
├── fastapi_ai/              # FastAPI behavior pack
├── flutter_ai/              # Flutter Android/iOS behavior pack
├── nextjs_ai/               # Next.js behavior pack
├── rag_ai/                  # Cross-stack RAG capability pack
└── react_ai/                # React behavior pack
```

The linked repositories are `Dolan001/base_ai`, `Dolan001/drf_ai`,
`Dolan001/fastapi_ai`, `Dolan001/flutter_ai`, `Dolan001/nextjs_ai`,
`Dolan001/react_ai`, `Dolan001/rag_ai`, and `Dolan001/aws_ai`.

To update the workflow in a target project, review the new `ai_workflow` commit and its
nested pins, then update the `.agents` gitlink explicitly. Do not copy skills into a
second `.agents` directory.

## Pipeline contract

```text
bootstrap → requirements/contracts → design/approved HTML → optional web
          → optional Flutter mobile → backend → integration → testing
          → application delivery

explicit later command: start-deployment → AWS asset readiness
```

`config/pipeline.json` is the phase registry. Each phase resolves one manifest, one
blueprint, and one gate. `config/framework-packs.json` maps selected frameworks and explicit
capabilities to read-only behavior packs and target application roots. JSON is reserved for
deterministic catalogs, schemas, graphs, configuration, state, and evidence. Agent
behavior, skills, commands, hooks, and rules are Markdown.

Additional references:

- [`docs/start-commands.md`](docs/start-commands.md)
- [`docs/one-shot.md`](docs/one-shot.md)
- [`docs/architecture/`](docs/architecture/)

## Exit codes

- `0`: command completed and its requested evidence gate passed
- `1`: invalid input, unsafe state, missing dependency, or execution failure
- `2`: command ran but verification or readiness did not pass
