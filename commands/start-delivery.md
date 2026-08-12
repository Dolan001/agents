---
description: Finish release readiness and optionally commit or push verified features
argument-hint: "--frontend react|nextjs --backend django-drf|fastapi [--commit-verified] [--push]"
---
<!-- managed-by: ai_workflow -->
# Start delivery

Read `{{WORKFLOW_PATH}}/commands/references/start-command-contract.md`. Validate
`$ARGUMENTS`, then run:

```text
./{{WORKFLOW_PATH}}/bin/ai start-delivery --project . --adapter {{ADAPTER}} $ARGUMENTS
```

Only pass Git mutation flags that the user explicitly supplied.
