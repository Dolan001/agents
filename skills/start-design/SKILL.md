---
name: start-design
description: After the backend is verified, create only the design specification from the required project documents and optional HTML or screenshots, stopping before HTML generation. Use when the user invokes start-design or asks to work only on design planning.
---

# Start design specification

Read `.agents/commands/references/start-command-contract.md`, then invoke
`./.agents/bin/ai start-design` with `--adapter codex-reviewed` and the resolved backend. The command runs
any missing requirements and backend prerequisites first. Stop after
`HTML/design-specification.md`; do not continue to HTML or application code.
