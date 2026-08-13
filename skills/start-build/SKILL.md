---
name: start-build
description: Start or continue the complete PRD-to-production workflow through design, approved HTML, frontend, backend, integration, testing, and delivery. Use when the user asks to build the whole system from scratch or invokes start-build.
---

# Start complete build

Read `.agents/commands/references/start-command-contract.md`. Before invoking the CLI,
inspect the PRD for explicit supported framework declarations. Use them without asking.
If either side is unspecified, ask one concise question containing only the missing
choice or choices:

- Frontend: React or Next.js
- Backend: Django REST Framework or FastAPI

Accept only these four frameworks. Wait for every missing selection; never choose a
framework based on product requirements when it is not explicitly declared. Then invoke
`./.agents/bin/ai start-build` with `--adapter codex`, `--frontend`, `--backend`, and
the other validated arguments. Run through delivery. Do not add `--push` unless
explicitly requested.
