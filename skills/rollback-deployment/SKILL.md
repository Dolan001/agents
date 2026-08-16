---
name: rollback-deployment
description: Restore a named AWS environment to its prior verified immutable release. Use only when the user invokes rollback-deployment and explicitly authorizes the rollback.
---

# Roll back AWS deployment

Confirm `staging` or `production`, diagnose the incident, and present the tested rollback target and
database compatibility before mutation. After explicit authorization invoke
`./.agents/bin/ai rollback-deployment --project . --environment <environment> --execute
--approve-rollback`. Preserve evidence, never perform destructive database reversal automatically,
and require verified rollback evidence before declaring recovery.
