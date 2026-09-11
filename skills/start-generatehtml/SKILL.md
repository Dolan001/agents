---
name: start-generatehtml
description: Generate, validate, and approve static HTML from a PRD, screenshots, design assets, or supplied HTML, stopping before frontend code. Use when the user invokes start-generatehtml or requests only the HTML baseline.
---

# Generate approved HTML

Read `.agents/commands/references/start-command-contract.md`, then invoke
`./.agents/bin/ai start-generatehtml` with `--adapter codex`. Complete the design
gate and stop before frontend implementation.

If generation passes deterministic source checks but pauses for product-owner review,
show the user the generated preview and stop without retrying. After the user explicitly
approves that exact preview, invoke `./.agents/bin/ai start-generatehtml --project .
--adapter codex --approve-html`. Never add the approval flag before the user has reviewed
the draft, and never describe source checks as browser or visual evidence.
