---
description: Connect frontend and backend and verify API contracts
argument-hint: "--frontend react|nextjs --backend django-drf|fastapi [--prd PATH] [--github-user USER]"
---
<!-- managed-by: ai_workflow -->
# Start integration

Read `{{WORKFLOW_PATH}}/commands/references/start-command-contract.md`. Validate
`$ARGUMENTS`, then run:

```text
./{{WORKFLOW_PATH}}/bin/ai start-integration --project . --adapter {{ADAPTER}} $ARGUMENTS
```

Run missing prerequisites, pass contract and integration gates, then stop.
