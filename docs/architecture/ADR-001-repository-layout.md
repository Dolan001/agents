# ADR-001: Separate reusable repositories

Status: accepted

## Decision

Keep `base`, each code-free framework behavior pack, and `agents` as
independently versioned repository directories.
`agents/base`, `agents/drf`, `agents/fastapi`,
`agents/flutter`, `agents/nextjs`, `agents/reactjs`, `agents/rag`,
`agents/webscraping`, and `agents/aws` are
root-level Git submodules pinned to reviewed revisions. Their `.gitmodules` entries use the GitHub
repositories and declare `branch = dev`. A target project initially checks out only the `agents`
superproject; deterministic PRD selection initializes `base` and the required subset. Unselected
packs remain uninitialized, and reconciliation never deletes an existing checkout automatically.

No sample application lives in this workspace. One-shot agents create or adopt a
separate target monorepo with `apps`, `packages`, `HTML`, `docs`, `tests`, `artifacts`,
`infra`, `scripts`, and durable `.ai` state.

## Responsibilities

- `base`: reusable behavior, contracts, policies, agent profiles, skills, hooks,
  state rules, leases, context, recovery, Git safety, and verification rules.
- `drf`: Django/DRF agents, skills, commands, hooks, and rules.
- `fastapi`: FastAPI agents, skills, commands, hooks, and rules.
- `flutter`: Flutter Android/iOS agents, skills, commands, hooks, structures, and rules.
- `reactjs`: React agents, skills, commands, hooks, and rules.
- `nextjs`: Next.js agents, skills, commands, hooks, and rules.
- `rag`: requirement-triggered retrieval-augmented generation behavior.
- `webscraping`: backend-only website discovery, selector, extraction, and verification behavior.
- `aws`: separately invoked AWS architecture and deployment behavior.
- `agents`: commands, manifests, blueprints, gates, rules, hooks, user CLI,
  discovery, reconciliation, state, framework-pack selection, reporting, and recovery.

## Consequences

Application boilerplate cannot live in `base` or a framework pack. Framework
behavior upgrades are reviewed and versioned independently. Agents generate only
requirement-backed code in the target monorepo.
