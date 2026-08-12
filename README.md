# ai_workflow

Specification-driven control plane for new and brownfield full-stack delivery. Its
shape follows the proven `claude-fullstack` separation: commands enter a deterministic
pipeline; phase manifests select rules, skills, and agents; blueprints define
executable nodes; and evidence gates control progression.

The framework repositories are code-free behavior packs. During a one-shot run,
specialized agents read the selected pack and create application code directly in the
separate target monorepo. No demonstration project or prebuilt framework application
is bundled with this workspace.

The requirements phase also creates and validates the target monorepo root contract:
`README.md`, `.gitignore`, `.env.example`, `compose.yaml`, `Makefile`, and the standard
`apps`, `packages`, `HTML`, `docs`, `tests`, `artifacts`, and `.ai` directories. The
frontend and backend phases then populate their selected framework structures.

## Install and use

```bash
python -m pip install -e ../base_ai -e .
ai one-shot --project /path/to/project --prd docs/PRD.md \
  --frontend nextjs --backend django-drf --github-user your-github-user \
  --branch-feature initial-build \
  --html HTML/input/home.html \
  --screenshot HTML/input/home-mobile.png
# After reviewing the dry-run plan:
ai one-shot --project /path/to/project --prd docs/PRD.md \
  --frontend nextjs --backend django-drf --github-user your-github-user \
  --branch-feature initial-build --adapter claude --execute \
  --commit-verified --push

# Individual control-plane commands remain available:
ai init --project /path/to/project --prd docs/PRD.md --frontend nextjs --backend django-drf
ai inspect --project /path/to/project --deep
ai reconcile --project /path/to/project
ai plan --project /path/to/project --remaining
ai build --project /path/to/project --remaining --execute --adapter claude
ai status --project /path/to/project
ai resume --project /path/to/project
ai pipeline
```

Framework selection is defined in `config/framework-packs.json`. Pack contents are
instructions, not files to copy. A new target starts from its PRD and generated
requirements; a brownfield target starts from discovery and reconciliation.

The repository-local `bin/ai` launcher works without installation. `one-shot` is a dry
run unless `--execute` is present. Agent adapters receive prompts on standard input and
are invoked without a shell. Project-owned tests are argv arrays in
`.ai/test-commands.json`; command strings are not evaluated.

`--html` and `--screenshot` are optional and repeatable. Paths must be inside the
target repository and are preserved under `HTML/source/`. With HTML, the design phase
validates and approves it. With screenshots but no HTML, it generates HTML from the
screenshots plus PRD. With neither, it generates HTML from the PRD. The selected route
is recorded in `.ai/design-inputs.json`.

`ai adopt` captures a Git and repository baseline before any application edit. `ai push`
is a dry run unless `--execute` is supplied, rejects dirty worktrees, and rejects every
protected or malformed branch.

## Linked repositories

`base_ai` and every framework behavior repository are root-level, pinned Git
submodules:

```text
ai_workflow/
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
