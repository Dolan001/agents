---
name: start-delivery
description: Run missing prerequisites through final release-readiness and safe feature delivery. Use when the user invokes start-delivery after implementation or asks to finish verified delivery.
---

# Start delivery

Read `.agents/commands/references/start-command-contract.md`, then invoke
`./.agents/bin/ai start-delivery` with `--adapter codex`. Add `--commit-verified` or
`--push` only when the user explicitly requests those Git mutations.
