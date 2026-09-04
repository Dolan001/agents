---
name: start-build
description: Start or continue the complete application workflow through design, approved HTML, selected web and/or Flutter mobile clients, backend, integration, independent testing, and delivery evidence. Use when the user asks to build the whole application from scratch or invokes start-build. AWS preparation is always a separate start-deployment run.
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

The CLI deterministically reconciles `.ai/selected-packs.json` before execution and initializes only
`base`, the selected application frameworks, and explicit RAG/web-scraping capabilities. Do not run
a recursive submodule update. Previously downloaded but now-unused packs are reported, not deleted.

The selected frontend and mobile phases automatically run `sync-design` after implementation and
before their independent verifier. Require design-fidelity evidence for every selected client; do not
skip it merely because component/widget tests pass.

Never pass `--deployment` to `start-build`, even when the PRD declares AWS. Record deployment as
deferred and finish the application through delivery evidence. When the user later requests AWS,
invoke `$start-deployment --deployment aws`; that separate run owns AWS architecture, IaC, CI/CD,
observability, and deployment-readiness evidence.
