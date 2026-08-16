---
name: start-build
description: Start or continue the complete PRD-to-production workflow through design, approved HTML, selected web and/or Flutter mobile clients, backend, integration, testing, optional AWS asset readiness, and delivery. Use when the user asks to build the whole system from scratch or invokes start-build.
---

# Start complete build

Read `.agents/commands/references/start-command-contract.md`. Before invoking the CLI,
inspect the PRD for explicit supported framework declarations. Use them without asking.
Require at least one client and one backend. If still missing, ask one concise question
containing only the missing choice or choices:

- Client: React, Next.js, or Flutter; allow web plus Flutter when requested
- Backend: Django REST Framework or FastAPI

Accept only these five frameworks. Wait for every missing selection; never choose a
framework based on product requirements when it is not explicitly declared. Then invoke
`./.agents/bin/ai start-build` with `--adapter codex` and only the resolved
`--frontend`, `--mobile`, and `--backend` arguments. Run through delivery. Do not add
`--push` unless explicitly requested.

If the PRD explicitly declares `Deployment provider: AWS`, pass `--deployment aws`; incidental AWS
service mentions do not select deployment. The deployment phase may generate and validate target
assets, but `start-build` must never run cloud plan/apply, staging, production, rollback, or DNS changes.
