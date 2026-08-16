---
name: deploy-production
description: Promote the staging-verified immutable digest to protected AWS production. Use only when the user explicitly invokes deploy-production and authorizes production execution.
---

# Deploy AWS production

Require successful staging evidence for the exact artifact digest, current readiness, a protected
production environment approval, reviewed plan, rollback target, and explicit user authorization.
Run `./.agents/bin/ai deploy-production --project . --execute --approve-production`. Never rebuild,
change branches, merge, substitute a tag for the digest, or bypass the production approval. Stop or
roll back on declared abort signals and require verified production evidence.
