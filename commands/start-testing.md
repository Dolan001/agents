---
description: Run full independent design, API, integration, E2E, and security testing
argument-hint: "--frontend react|nextjs --backend django-drf|fastapi [--prd PATH] [--github-user USER]"
---
<!-- managed-by: ai_workflow -->
# Start testing

Read `{{WORKFLOW_PATH}}/commands/references/start-command-contract.md`. Validate
`$ARGUMENTS`, then run:

```text
./{{WORKFLOW_PATH}}/bin/ai start-testing --project . --adapter {{ADAPTER}} $ARGUMENTS
```

Run missing prerequisites and the complete testing/security gate. Do not push.
