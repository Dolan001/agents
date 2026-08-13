---
name: start-build
description: Start or continue the complete PRD-to-production workflow through design, approved HTML, frontend, backend, integration, testing, and delivery. Use when the user asks to build the whole system from scratch or invokes start-build.
---

# Start complete build

Read `.agents/commands/references/start-command-contract.md`. Before invoking the CLI,
resolve missing inputs. If the frontend or backend is unspecified, ask one concise
combined question with these choices:

- Frontend: React or Next.js
- Backend: Django REST Framework or FastAPI

Wait for both selections; never infer them from the PRD. Then invoke
`./.agents/bin/ai start-build` with `--adapter codex`, `--frontend`, `--backend`, and
the other validated arguments. Run through delivery. Do not add `--push` unless
explicitly requested.
