---
name: start-backend
description: Run requirements, build the selected Django DRF or FastAPI backend, and verify it with live HTTP and disposable PostgreSQL before any design or client implementation. Use when the user invokes start-backend.
---

# Start backend

Read `.agents/commands/references/start-command-contract.md`, resolve only the backend choice, then
invoke `./.agents/bin/ai start-backend` with `--adapter codex-reviewed`. Stop after the backend gate. Require
real PostgreSQL migrations, deterministic synthetic seed data, live HTTP success/negative/auth tests,
a persistence round-trip, OpenAPI verification, and cleanup evidence.
Use one project-scoped Compose network for the complete verification run. PostgreSQL stays on the
internal network and is reached by service name; do not publish or probe changing host database ports.
