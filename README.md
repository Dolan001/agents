# ai_workflow

Specification-driven control plane for new and brownfield full-stack delivery. Its
shape follows the proven `claude-fullstack` separation: commands enter a deterministic
pipeline; phase manifests select rules, skills, and agents; blueprints define
executable nodes; and evidence gates control progression.

The framework repositories are code-free behavior packs. During a one-shot run,
specialized agents read the selected pack and create application code directly in the
separate target monorepo. No demonstration project or prebuilt framework application
is bundled with this workspace.

The frontend phase creates and validates the target monorepo root contract:
`README.md`, `.gitignore`, `.env.example`, `compose.yaml`, `Makefile`, and the standard
`apps`, `packages`, `HTML`, `docs`, `tests`, `artifacts`, and `.ai` directories. The
frontend and backend phases then populate their selected framework structures.

## Install and use

```bash
git submodule add -b dev https://github.com/Dolan001/ai_workflow.git .agents
git submodule update --init --recursive

# Reopen Codex, then run the complete PRD-to-delivery skill
$start-build

# Or invoke the engine directly
./.agents/bin/ai one-shot --project . --prd docs/PRD.md \
  --frontend nextjs --backend django-drf --github-user your-github-user \
  --branch-feature initial-build \
  --html HTML/input/home.html \
  --screenshot HTML/input/home-mobile.png
# After reviewing the dry-run plan:
./.agents/bin/ai one-shot --project . --prd docs/PRD.md \
  --frontend nextjs --backend django-drf --github-user your-github-user \
  --branch-feature initial-build --adapter codex --execute \
  --commit-verified --push

# Individual control-plane commands remain available:
./.agents/bin/ai init --project . --prd docs/PRD.md --frontend nextjs --backend django-drf
./.agents/bin/ai inspect --project . --deep
./.agents/bin/ai reconcile --project .
./.agents/bin/ai plan --project . --remaining
./.agents/bin/ai status --project .
./.agents/bin/ai resume --project .
./.agents/bin/ai pipeline
```

Framework selection is defined in `config/framework-packs.json`. Pack contents are
instructions, not files to copy. A new target starts from its PRD and generated
requirements; a brownfield target starts from discovery and reconciliation.

`start-build` accepts only React or Next.js for frontend and Django REST Framework or
FastAPI for backend. Explicit PRD declarations are selected automatically. Codex asks
only for a missing side; unsupported, conflicting, or multiple declarations fail
before runtime state or application code is created.

When this repository is mounted at `.agents`, Codex discovers `skills/` directly and
the repository-local `bin/ai` launcher works without installation. `one-shot` is a dry
run unless `--execute` is present. Agent adapters receive prompts on standard input and
are invoked without a shell. Project-owned tests are argv arrays in
`.ai/test-commands.json`; command strings are not evaluated.

`--html` and `--screenshot` are optional and repeatable. Paths must be inside the
target repository and are preserved under `HTML/source/`. With HTML, the design phase
validates and approves it. With screenshots but no HTML, it generates HTML from the
screenshots plus PRD. With neither, it generates HTML from the PRD. The selected route
is recorded in `.ai/design-inputs.json`.

Stage commands execute immediately and stop only after their requested evidence gate:
`start-design`, `start-generatehtml`, `start-frontend`, `start-backend`,
`start-integration`, `start-testing`, `start-delivery`, and `start-build`. The design
and HTML commands intentionally do not create the application monorepo. See
[`docs/start-commands.md`](docs/start-commands.md) for the command matrix and setup.

`ai adopt` captures a Git and repository baseline before any application edit. `ai push`
is a dry run unless `--execute` is supplied, rejects dirty worktrees, and rejects every
protected or malformed branch.

## Resolve a scoped work token

After a build, place a token at `frontend/TKN001/TOKEN.md` or
`backend/TKN001/TOKEN.md` and invoke `$resolve-token <token-path>`. A token requires a
level-one title and `## Description`. Optional sibling visual evidence is discovered
as consecutive `current1.png`, `current2.png`, ... and `expected1.png`,
`expected2.png`, ... files; PNG, JPEG, and WebP are accepted. The route selects the
application area, and verified state is preserved under `.ai/token-runs/<TOKEN_ID>/`.

The first invocation diagnoses and returns a plan without editing application files.
After explicit approval, rerun with `--approve`. The resolver records the exact current
branch as the PR base, creates `ai/<github-user>/<token-id>` from its unchanged remote
commit, implements and verifies the plan, commits and pushes only the token paths, and
opens a PR back to the recorded branch. The base may have any valid branch name,
including `main` or `dev`; it is never pushed or merged by the resolver. GitHub CLI
authentication and an existing remote base branch are required.

## Linked repositories

`base_ai` and every framework behavior repository are root-level, pinned Git
submodules:

```text
.agents/                     # ai_workflow mounted as the Codex project submodule
├── agents/                  # orchestration-only agents
├── blueprints/              # deterministic + agentic node graphs
├── commands/                # workflow entry contracts
├── gates/                   # evidence contracts
├── hooks/                   # lifecycle dispatch
├── pipeline/                # manifests, evaluation, and recovery policy
├── rules/                   # common and phase scope rules
├── skills/                  # orchestration skills
├── base_ai/                 # shared AI behavior repository
├── drf_ai/                  # Django DRF behavior repository
├── fastapi_ai/              # FastAPI behavior repository
├── nextjs_ai/               # Next.js behavior repository
└── react_ai/                # React behavior repository
```

Clone with `git clone --recurse-submodules <ai_workflow-url>`, or initialize an
existing clone with `git submodule update --init --recursive`. Submodules track their
`dev` branches for explicit update operations while the parent repository always pins
an exact reviewed commit.

The linked repositories are `Dolan001/base_ai`, `Dolan001/drf_ai`,
`Dolan001/fastapi_ai`, `Dolan001/nextjs_ai`, and `Dolan001/react_ai`.

## Pipeline

```text
bootstrap → requirements/contracts → design/approved HTML → frontend
          → backend → integration → testing → feature delivery
```

`config/pipeline.json` is the phase registry. Every phase points to one manifest, one
blueprint, and one gate contract. Run `ai pipeline` to validate that the control plane
is fully connected. Framework packs are loaded only for their selected implementation
phase; no behavior repository contains application boilerplate.

### Accuracy, time, and token controls

- Accuracy: stable cross-layer contracts, artifact contracts on every agentic node,
  independent verification, and fail-closed evidence gates.
- Build time: focused fast checks, bounded retries, resumable checkpoints, and
  verified-node caching. Frontend precedes backend so approved user experience and
  observed data needs inform the backend contract without concurrent drift.
- Token use: Markdown progressive disclosure, exactly one frontend/backend pack,
  cached project summaries, 12-file/60k-character task bundles, and concise failure
  excerpts.

After independent feature and security verification, `--commit-verified` stages only
paths declared in that feature's evidence. `--push` also pushes each commit to the
current `ai/<github-user>/<feature>` branch. Protected branches are always rejected.

JSON remains only where the engine needs deterministic structure. Agent behavior,
skills, commands, hooks, and rules are Markdown.

## Exit codes

- `0`: command completed and its requested gate passed
- `1`: invalid input, unsafe state, or execution error
- `2`: command completed but verification/readiness did not pass
