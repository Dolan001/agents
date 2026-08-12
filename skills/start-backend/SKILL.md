---
name: start-backend
description: Run missing prerequisites and build the selected Django DRF or FastAPI backend after frontend completion, then stop before integration. Use when the user invokes start-backend.
---

# Start backend

Read `{{WORKFLOW_PATH}}/commands/references/start-command-contract.md`, resolve both framework
choices, then invoke `./{{WORKFLOW_PATH}}/bin/ai start-backend` with `--adapter codex`. Stop
after the backend gate.
