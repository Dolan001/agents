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
| Frontend | React or Next.js | `apps/frontend` |
| Backend | Django REST Framework or FastAPI | `apps/backend` |

The frontend phase creates the monorepo root contract before application code is
populated:

```text
target-project/
├── .agents/                 # this repository, installed as a Git submodule
├── .ai/                     # generated workflow state and evidence
├── apps/
│   ├── frontend/
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

Design-only commands stop before this monorepo is created. `start-frontend` is the
first command allowed to scaffold the application structure.

## Quick start

Run these commands inside the target project, not inside `ai_workflow` itself:

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

Keep exactly one of those files, or pass an explicit `--prd` path. Then reopen Codex
so it discovers `.agents/skills`, and type this in Codex chat:

```text
$start-build --github-user <github-user>
```

`$start-build` is a Codex skill invocation, not a terminal command. It runs every
missing phase through delivery. It does not push by default.

## Complete process: A to Z

### 1. Install and pin the workflow

The real project stores `ai_workflow` directly at `.agents`. The nested `base_ai`,
`drf_ai`, `fastapi_ai`, `react_ai`, and `nextjs_ai` repositories are initialized
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

Framework declarations are optional. To make automatic selection unambiguous, use
explicit declarations such as:

```markdown
Frontend framework: Next.js
Backend framework: Django REST Framework
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

The workflow accepts only React or Next.js for frontend and Django REST Framework or
FastAPI for backend.

- If the PRD explicitly declares a supported framework, Codex uses it without asking.
- If a framework required by the requested stopping point is absent, Codex asks only
  for the missing choice.
- Unsupported, conflicting, ambiguous, or multiple declarations fail before
  application code or runtime state is created.
- A saved framework choice cannot be silently changed during resume.

Design specification and HTML generation do not require framework choices.
`start-frontend` requires frontend selection. Backend and all later stages require both.

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
| `$start-design` | Design specification | No |
| `$start-generatehtml` | Approved static HTML | No |
| `$start-frontend` | Frontend gate | Yes |
| `$start-backend` | Backend gate | Yes |
| `$start-integration` | Typed integration gate | Yes |
| `$start-testing` | Independent testing and security gate | Yes |
| `$start-delivery` | Release-readiness gate | Yes |
| `$start-build` | Complete delivery lifecycle | Yes |
| `$resume-build` | Unchanged checkpoints through delivery | As needed |
| `$workflow-status` | Read-only status report | No change |

Every start command runs missing prerequisites. For example, `$start-backend` does not
skip requirements, design, or frontend when they are incomplete.

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

### 9. Build the frontend and create the monorepo

The frontend phase loads only the selected React or Next.js behavior pack. Specialized
agents:

- create and validate the framework-neutral monorepo root;
- implement the approved HTML as production frontend code;
- preserve requirements, responsive behavior, accessibility, and design intent;
- define project-owned frontend test commands; and
- produce feature and structure evidence.

The generated `apps/frontend` structure must match the selected behavior pack's exact
project-structure contract before the frontend gate passes.

### 10. Build the backend

After frontend approval, the backend phase loads only Django REST Framework or FastAPI
guidance. It uses the reconciled requirements and observed frontend data needs to:

- implement API endpoints, domain logic, persistence, authentication, permissions,
  validation, exceptions, and error responses;
- create or finalize API contracts and backend test commands;
- run focused backend verification; and
- validate the generated `apps/backend` structure against its framework contract.

The backend gate blocks progression when required behavior, evidence, or structure is
missing.

### 11. Integrate frontend and backend

The integration phase generates or updates the typed client in
`packages/api-client`, connects frontend flows to real backend APIs, and creates
contract and integration tests. Project-owned OpenAPI/client generation commands run
without shell evaluation. The gate requires frontend, backend, client, and contract
evidence to agree.

### 12. Run independent testing and security review

The testing phase runs configured project-owned commands from
`.ai/test-commands.json`, including the applicable backend, frontend, contract,
integration, and end-to-end lanes. Independent agents verify:

- PRD acceptance criteria and complete user journeys;
- API success responses, validation, exceptions, and error behavior;
- frontend/backend integration and browser behavior;
- approved-HTML or screenshot design fidelity;
- responsiveness and accessibility;
- security controls and high-risk findings; and
- affected full tests, not only the narrow implementation check.

Results are stored under `artifacts/tests/`, `artifacts/security/`, and
`.ai/evidence/features/`. A task is marked verified only when its final evidence passes.

### 13. Complete delivery

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

### 14. Inspect, resume, and recover

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

### 15. Resolve post-build bugs or changes with a token

Create exactly one scoped token at:

```text
frontend/TKN001/TOKEN.md
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

## Runtime state and evidence

`.agents` is the versioned workflow submodule. `.ai` is generated per-project runtime
state and remains separate:

```text
.ai/
├── state.json               # lifecycle, frameworks, branch, and completed phases
├── task-queue.json          # vertical-slice task contracts and status
├── node-state.json          # verified node checkpoints and input hashes
├── design-inputs.json       # HTML/screenshot/PRD routing decision
├── test-commands.json       # approved argv-based project test commands
├── path-leases.json         # controlled write ownership
├── decisions.jsonl          # durable workflow decisions
├── failures.jsonl           # failure and retry evidence
├── discovery/               # repository inventory
├── context-bundles/         # bounded task-specific context manifests
├── prompts/                 # exact dispatched node prompts
├── logs/                    # bounded adapter results
├── evidence/                # gates, structure, design, and feature verification
└── token-runs/              # token plans, state, and implementation evidence
```

Do not manually edit state to bypass a gate. Use `$workflow-status` to identify the
failed artifact and resume after correcting the actual cause.

## Accuracy, speed, and token controls

- Every agentic node has a required artifact contract and a phase evidence gate.
- The scheduler runs phases sequentially to prevent frontend/backend contract drift.
- Only one frontend and one backend behavior pack are selected.
- `build-context-bundle` creates an auditable manifest capped at 12 files and 60,000
  characters, prioritizing requirement anchors, contracts, affected code, and tests.
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
  --frontend nextjs --backend fastapi --github-user dolan
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
  --frontend nextjs --backend django-drf --github-user dolan
./.agents/bin/ai adopt --project . --prd docs/PRD.md \
  --frontend react --backend fastapi --github-user dolan

# Inspect, reconcile, and plan
./.agents/bin/ai inspect --project . --deep
./.agents/bin/ai reconcile --project .
./.agents/bin/ai plan --project . --remaining
./.agents/bin/ai status --project . --json

# Execute stage commands
./.agents/bin/ai start-design --project . --adapter codex
./.agents/bin/ai start-generatehtml --project . --adapter codex
./.agents/bin/ai start-frontend --project . --adapter codex --frontend nextjs
./.agents/bin/ai start-backend --project . --adapter codex \
  --frontend nextjs --backend django-drf
./.agents/bin/ai start-integration --project . --adapter codex
./.agents/bin/ai start-testing --project . --adapter codex
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

The lower-level `one-shot` command is a dry run unless `--execute` is supplied and
requires explicit frontend and backend values:

```bash
./.agents/bin/ai one-shot --project . --prd docs/PRD.md \
  --frontend nextjs --backend django-drf --github-user dolan \
  --branch-feature initial-build

./.agents/bin/ai one-shot --project . --prd docs/PRD.md \
  --frontend nextjs --backend django-drf --github-user dolan \
  --branch-feature initial-build --adapter codex --execute
```

`clean-state --yes` permanently removes `.ai` and is intentionally destructive. It is
not a normal recovery step.

## Linked repositories

The workflow pins exact reviewed commits for five behavior repositories while each
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
├── drf_ai/                  # Django DRF behavior pack
├── fastapi_ai/              # FastAPI behavior pack
├── nextjs_ai/               # Next.js behavior pack
└── react_ai/                # React behavior pack
```

The linked repositories are `Dolan001/base_ai`, `Dolan001/drf_ai`,
`Dolan001/fastapi_ai`, `Dolan001/nextjs_ai`, and `Dolan001/react_ai`.

To update the workflow in a target project, review the new `ai_workflow` commit and its
nested pins, then update the `.agents` gitlink explicitly. Do not copy skills into a
second `.agents` directory.

## Pipeline contract

```text
bootstrap → requirements/contracts → design/approved HTML → frontend
          → backend → integration → testing → delivery
```

`config/pipeline.json` is the phase registry. Each phase resolves one manifest, one
blueprint, and one gate. `config/framework-packs.json` maps selected frameworks to
read-only behavior packs and target application roots. JSON is reserved for
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
