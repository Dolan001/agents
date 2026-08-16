---
name: deployment-status
description: Report AWS deployment preparation, readiness, staging, production, and rollback evidence without mutation. Use when the user invokes deployment-status or asks what is deployed.
---

# Report deployment status

Invoke `./.agents/bin/ai deployment-status --project .`. Report the selected provider, whether the
generation phase passed, existing environment evidence, artifact digests, timestamps, and blockers.
Do not contact AWS, refresh credentials, deploy, rollback, or change durable state.
