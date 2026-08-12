---
description: Build the complete production system from PRD through verified delivery
argument-hint: "[--prd PATH] --frontend react|nextjs --backend django-drf|fastapi [--html PATH] [--screenshot PATH] [--github-user USER]"
---
<!-- managed-by: ai_workflow -->
# Start complete build

Read `{{WORKFLOW_PATH}}/commands/references/start-command-contract.md`. Validate
`$ARGUMENTS`, resolve missing required framework choices, then run:

```text
./{{WORKFLOW_PATH}}/bin/ai start-build --project . --adapter {{ADAPTER}} $ARGUMENTS
```

Run every missing phase through delivery. Do not push unless explicitly requested.
