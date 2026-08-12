---
description: Build and verify the selected frontend from approved HTML
argument-hint: "--frontend react|nextjs [--prd PATH] [--html PATH] [--screenshot PATH] [--github-user USER]"
---
<!-- managed-by: ai_workflow -->
# Start frontend

Read `{{WORKFLOW_PATH}}/commands/references/start-command-contract.md`. Validate
`$ARGUMENTS`, require the frontend choice, then run:

```text
./{{WORKFLOW_PATH}}/bin/ai start-frontend --project . --adapter {{ADAPTER}} $ARGUMENTS
```

Run missing prerequisites, create the target monorepo, pass the frontend gate, and stop.
