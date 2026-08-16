---
name: start-deployment
description: Generate and independently verify AWS infrastructure, CI/CD, observability, and runbooks without cloud mutation. Use when the user invokes start-deployment or asks to prepare AWS deployment after testing.
---

# Start deployment preparation

Read `.agents/commands/references/start-command-contract.md`. Require the application testing and
security gates or run missing prerequisites. Select only AWS; reject another cloud provider. Invoke
`./.agents/bin/ai start-deployment --project . --adapter codex --deployment aws` with resolved
application frameworks. This command generates and validates assets only. Never add live credentials,
`--execute`, infrastructure apply, DNS change, or application deployment.
