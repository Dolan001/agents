---
name: workflow-status
description: Inspect durable workflow checkpoints, completed phases, evidence, blockers, and the exact next safe action without changing project state. Use when the user asks for workflow status or invokes workflow-status.
---

# Inspect workflow status

Run `./.agents/bin/ai status --project . --json`. Report completed phases,
the current phase, failed evidence, and the exact next command. Do not mutate files,
Git state, or remote systems.

<!-- managed-by: ai_workflow -->
