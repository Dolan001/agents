# ai_workflow

Specification-driven control plane for new and brownfield full-stack delivery. Its
shape follows the proven `claude-fullstack` separation: commands enter a deterministic
pipeline; phase manifests select rules, skills, and agents; blueprints define
executable nodes; and evidence gates control progression.

The framework repositories are code-free behavior packs. During a one-shot run,
specialized agents read the selected pack and create application code directly in the
separate target monorepo. No demonstration project or prebuilt framework application
is bundled with this workspace.

## Install and use

```bash
python -m pip install -e ../base_ai -e .
ai init --project /path/to/project --prd docs/PRD.md --frontend nextjs --backend django-drf
ai inspect --project /path/to/project --deep
ai reconcile --project /path/to/project
ai plan --project /path/to/project --remaining
ai build --project /path/to/project --remaining
ai status --project /path/to/project
ai resume --project /path/to/project
ai pipeline
```

Framework selection is defined in `config/framework-packs.json`. Pack contents are
instructions, not files to copy. A new target starts from its PRD and generated
requirements; a brownfield target starts from discovery and reconciliation.

The repository-local `bin/ai` launcher works without installation.

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
├── django/                  # Django DRF behavior repository
├── fastapi/                 # FastAPI behavior repository
├── nextjs/                  # Next.js behavior repository
└── react/                   # React behavior repository
```

Clone with `git clone --recurse-submodules <ai_workflow-url>`, or initialize an
existing clone with `git submodule update --init --recursive`. Submodules track their
`dev` branches for explicit update operations while the parent repository always pins
an exact reviewed commit.

The expected private repositories are under the `potentialInc` organization:
`claude-base-ai`, `claude-django`, `claude-fastapi`, `claude-nextjs`, and
`claude-react`.

## Pipeline

```text
bootstrap → requirements/contracts → design ─┬→ frontend ─┐
                                             └→ backend  ─┴→ integration
                                                → testing → delivery
```

`config/pipeline.json` is the phase registry. Every phase points to one manifest, one
blueprint, and one gate contract. Run `ai pipeline` to validate that the control plane
is fully connected. Framework packs are loaded only for their selected implementation
phase; no behavior repository contains application boilerplate.

### Accuracy, time, and token controls

- Accuracy: stable cross-layer contracts, artifact contracts on every agentic node,
  independent verification, and fail-closed evidence gates.
- Build time: dependency-DAG scheduling, frontend/backend safe concurrency, focused
  fast checks, critical-path priority, and verified-node caching.
- Token use: Markdown progressive disclosure, exactly one frontend/backend pack,
  cached project summaries, 12-file/60k-character task bundles, and concise failure
  excerpts.

JSON remains only where the engine needs deterministic structure. Agent behavior,
skills, commands, hooks, and rules are Markdown.

## Exit codes

- `0`: command completed and its requested gate passed
- `1`: invalid input, unsafe state, or execution error
- `2`: command completed but verification/readiness did not pass
