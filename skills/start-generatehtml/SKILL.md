---
name: start-generatehtml
description: Generate, validate, and approve static HTML from a PRD, screenshots, design assets, or supplied HTML, stopping before frontend code. Use when the user invokes start-generatehtml or requests only the HTML baseline.
---

# Generate approved HTML

Read `.agents/commands/references/start-command-contract.md`, then invoke
`./.agents/bin/ai start-generatehtml` with `--adapter codex`. Complete the design
gate and stop before frontend implementation.

Generate, independently verify, and approve HTML in the same invocation. The independent
verifier owns approval; do not pause for user HTML review. The orchestrator promotes the
verified draft using passing source-check hashes. Repair actionable failures within the
retry budget. Never describe source checks as browser or visual evidence.
