---
description: Resume a stopped complete build from verified durable checkpoints
argument-hint: "[--frontend react|nextjs] [--backend django-drf|fastapi] [--push]"
---
<!-- managed-by: ai_workflow -->
# Resume complete build

Read `{{WORKFLOW_PATH}}/commands/references/start-command-contract.md`. Inspect status,
validate `$ARGUMENTS`, then run:

```text
./{{WORKFLOW_PATH}}/bin/ai resume-build --project . --adapter {{ADAPTER}} $ARGUMENTS
```

Reuse unchanged verified nodes. Do not push unless explicitly requested.
