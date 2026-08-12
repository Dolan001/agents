---
description: Generate and verify approved HTML from PRD, supplied HTML, or screenshots
argument-hint: "[--prd PATH] [--html PATH] [--screenshot PATH] [--github-user USER]"
---
<!-- managed-by: ai_workflow -->
# Generate approved HTML

Read `{{WORKFLOW_PATH}}/commands/references/start-command-contract.md`. Validate
`$ARGUMENTS`, then run:

```text
./{{WORKFLOW_PATH}}/bin/ai start-generatehtml --project . --adapter {{ADAPTER}} $ARGUMENTS
```

Complete the design gate and stop before frontend or monorepo creation.
