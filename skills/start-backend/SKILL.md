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
Use Docker Compose as the only provider for PostgreSQL and any requirement-backed Redis, Celery
worker, or Celery Beat process. Never require or install host services. Pull missing pinned service
images and build the worker/Beat services from the locked backend image. Use the deterministic
Compose project name supplied by the workflow for every backend slice, reuse its services and image,
and use purpose-specific database names. Rebuild only after Dockerfile or dependency-lock changes;
mount source for normal slice checks. Keep the shared runtime during resumable failures, then remove
its containers, network, and volumes after the final backend verifier passes. Retain one current
project-labelled dependency image for later client integration and delete only dangling revisions
with the exact project label. Cleanup must never use an unfiltered or global Docker prune.
