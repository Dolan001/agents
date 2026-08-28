---
name: start-delivery
description: Run missing application prerequisites through final verification and safe feature delivery without AWS preparation. Use when the user invokes start-delivery after implementation or asks to finish verified application delivery.
---

# Start delivery

Read `.agents/commands/references/start-command-contract.md`, then invoke
`./.agents/bin/ai start-delivery` with `--adapter codex`. Add `--commit-verified` or
`--push` only when the user explicitly requests those Git mutations. This command does
not generate AWS assets; use `$start-deployment` separately.
