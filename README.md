# ai_workflow

User-facing orchestration for new and brownfield projects. It validates a required
PRD, inventories existing code without rewriting it, reconciles requirements, creates
task contracts, maintains durable state and leases, and gates review and release.

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
```

Framework selection is defined in `config/framework-packs.json`. Pack contents are
instructions, not files to copy. A new target starts from its PRD and generated
requirements; a brownfield target starts from discovery and reconciliation.

The repository-local `bin/ai` launcher works without installation.

`ai adopt` captures a Git and repository baseline before any application edit. `ai push`
is a dry run unless `--execute` is supplied, rejects dirty worktrees, and rejects every
protected or malformed branch.

## Exit codes

- `0`: command completed and its requested gate passed
- `1`: invalid input, unsafe state, or execution error
- `2`: command completed but verification/readiness did not pass
