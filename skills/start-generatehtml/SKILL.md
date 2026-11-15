---
name: start-generatehtml
description: Generate, validate, and approve static HTML from a PRD, screenshots, design assets, or supplied HTML after the backend is verified, stopping before client code. Use when the user invokes start-generatehtml or requests only the HTML baseline.
---

# Generate approved HTML

Read `.agents/commands/references/start-command-contract.md`, then invoke
`./.agents/bin/ai start-generatehtml` with the resolved backend. Require the
backend gate first, then complete the design
gate and stop before frontend implementation.

Generate, independently verify, and approve HTML in the same invocation. The independent
verifier owns approval; do not pause for user HTML review. The orchestrator promotes the
verified draft using passing source-check hashes. Repair actionable failures within the
retry budget. Never describe source checks as browser or visual evidence.

Before approval, require each comparison page to show one deterministic route state.
Record that state with `data-design-state` on `html` or `body`, and keep mutually
exclusive state examples in separate pages or non-baseline design documentation.
The verifier must inspect rendered state visibility so an all-states gallery cannot
pass as a pixel reference for the later frontend or mobile implementation.
