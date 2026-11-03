---
name: start-deployment
description: Generate and independently verify AWS infrastructure, CI/CD, observability, and runbooks without cloud mutation. Use when the user invokes start-deployment or asks to prepare AWS deployment after testing.
---

# Start deployment preparation

Read `.agents/commands/references/start-command-contract.md`. Require the application testing and
security gates or run missing prerequisites. Select only AWS; reject another cloud provider. Invoke
`./.agents/bin/ai start-deployment --project . --deployment aws` with resolved
application frameworks. This command generates and validates assets only. Never add live credentials,
`--execute`, infrastructure apply, DNS change, or application deployment.
It selects both the `cicd` behavior pack for pipeline work and `aws` for infrastructure.

Before generation, read the approved PRD's region, domain/DNS owner and provider, monthly budget,
environment separation, CI/CD provider, and release approval owner. If a user-owned choice is
missing, ask for it; never invent production values. Use GitHub Actions by default only when the
PRD does not choose GitLab CI, and include Cloudflare only when selected. A different CI/CD
provider requires a pack extension before generation. Keep
credential values out of requirements, PRD, prompts, generated files, and evidence.
