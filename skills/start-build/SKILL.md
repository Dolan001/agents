---
name: start-build
description: Start or continue the complete PRD-to-production workflow through design, approved HTML, frontend, backend, integration, testing, and delivery. Use when the user asks to build the whole system from scratch or invokes start-build.
---

# Start complete build

Read `{{WORKFLOW_PATH}}/commands/references/start-command-contract.md`, resolve missing required
inputs, then invoke `./{{WORKFLOW_PATH}}/bin/ai start-build` with `--adapter codex` and the
validated arguments. Run through delivery. Do not add `--push` unless explicitly
requested.
