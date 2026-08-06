# ADR-001: Separate reusable repositories

Status: accepted

## Decision

Keep `base_ai`, each code-free framework behavior pack, and `ai_workflow` as
independently versioned repository directories.
When remote repositories exist, `ai_workflow/base_ai` and `ai_workflow/templates/*`
are Git submodules pinned to reviewed revisions. The local workspace uses
sibling-relative URLs; those entries are replaced with private remote URLs when the
repositories are published.

No sample application lives in this workspace. One-shot agents create or adopt a
separate target monorepo with `apps`, `packages`, `HTML`, `docs`, `tests`, `artifacts`,
`infra`, `scripts`, and durable `.ai` state.

## Responsibilities

- `base_ai`: reusable behavior, contracts, policies, agent profiles, skills, hooks,
  state rules, leases, context, recovery, Git safety, and verification rules.
- `template_django_drf`: Django/DRF agents, skills, commands, hooks, and rules.
- `template_fastapi`: FastAPI agents, skills, commands, hooks, and rules.
- `template_react`: React agents, skills, commands, hooks, and rules.
- `template_nextjs`: Next.js agents, skills, commands, hooks, and rules.
- `ai_workflow`: user CLI, orchestration, discovery, reconciliation, state, adapters,
  framework-pack selection, reporting, and recovery.

## Consequences

Application boilerplate cannot live in `base_ai` or a framework pack. Framework
behavior upgrades are reviewed and versioned independently. Agents generate only
requirement-backed code in the target monorepo. Local development works without
GitHub; pushes and submodule conversion wait for configured remotes.
