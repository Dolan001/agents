# ADR-001: Separate reusable repositories

Status: accepted

## Decision

Keep `base_ai`, each code-free framework behavior pack, and `ai_workflow` as
independently versioned repository directories.
`ai_workflow/base_ai`, `ai_workflow/django`, `ai_workflow/fastapi`,
`ai_workflow/nextjs`, and `ai_workflow/react` are root-level Git submodules pinned to
reviewed revisions. Their `.gitmodules` entries use the private GitHub repositories
and declare `branch = dev`, matching the `claude-fullstack` repository convention.

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
- `ai_workflow`: commands, manifests, blueprints, gates, rules, hooks, user CLI,
  discovery, reconciliation, state, framework-pack selection, reporting, and recovery.

## Consequences

Application boilerplate cannot live in `base_ai` or a framework pack. Framework
behavior upgrades are reviewed and versioned independently. Agents generate only
requirement-backed code in the target monorepo.
