---
name: start-build
description: Start or continue the complete workflow through requirements, selected web/mobile/desktop GUI and/or standalone Python library/CLI deliverables, system testing, and delivery evidence. Use when the user asks to build the whole product or invokes start-build. AWS preparation is separate.
---

# Start complete build

Read `.agents/commands/references/start-command-contract.md`. Before invoking the CLI,
inspect the PRD for explicit supported framework declarations. Use them without asking.
Require at least one deliverable. Require a backend only for web/mobile selections. If still missing, ask one concise question
containing only the missing choice or choices:

- Deliverable: React, Next.js, Flutter, Python Desktop GUI, Python library, or Python CLI; allow combinations
- Backend, when web/mobile is selected: Django REST Framework or FastAPI

Wait for every missing selection; never choose a framework based on product requirements when it
is not explicitly declared. Then invoke `./.agents/bin/ai start-build` with only the resolved
`--frontend`, `--mobile`, `--desktop`, `--python-package`, and `--backend` arguments. PRD declarations
need not be repeated. Run through delivery. Do not add
`--push` unless explicitly requested.

When selected, the backend gate runs before design and must prove a live HTTP service, deterministic synthetic
seed data, PostgreSQL persistence, negative and authorization behavior, and cleanup. Web/mobile phases
then implement and verify real API integration against that backend; fixtures cannot pass a client
gate. Package-only work skips UI design and does not require an API service.

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
