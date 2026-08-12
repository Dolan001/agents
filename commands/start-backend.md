---
description: Build and verify the selected backend after required earlier phases
argument-hint: "--frontend react|nextjs --backend django-drf|fastapi [--prd PATH] [--github-user USER]"
---
<!-- managed-by: ai_workflow -->
# Start backend

Read `{{WORKFLOW_PATH}}/commands/references/start-command-contract.md`. Validate
`$ARGUMENTS`, require both framework choices when not recorded, then run:

```text
./{{WORKFLOW_PATH}}/bin/ai start-backend --project . --adapter {{ADAPTER}} $ARGUMENTS
```

Run missing prerequisites, pass the backend gate, and stop before integration.
