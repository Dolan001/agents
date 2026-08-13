---
name: resume-build
description: Resume an interrupted complete build from durable verified checkpoints without repeating unchanged nodes. Use when the user invokes resume-build or asks to continue a stopped workflow.
---

# Resume complete build

Read `.agents/commands/references/start-command-contract.md`, inspect workflow status,
then invoke `./.agents/bin/ai resume-build` with `--adapter codex`. Preserve existing
framework choices and do not push unless explicitly requested.
