---
description: Create the design specification from PRD and optional visual inputs only
argument-hint: "[--prd PATH] [--html PATH] [--screenshot PATH] [--github-user USER]"
---
<!-- managed-by: ai_workflow -->
# Start design specification

Read `{{WORKFLOW_PATH}}/commands/references/start-command-contract.md`. Validate
`$ARGUMENTS`, then run:

```text
./{{WORKFLOW_PATH}}/bin/ai start-design --project . --adapter {{ADAPTER}} $ARGUMENTS
```

Stop after `HTML/design-specification.md`. Do not generate approved HTML or app code.
