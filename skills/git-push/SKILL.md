---
name: git-push
description: Review, commit pending changes when needed, and push the checked-out Git branch. Use when the user requests commit-and-push or invokes git-push.
---

# Git push

Read `.agents/base/agents/git-workflow-agent.md`. Inspect the branch, working-tree diff,
remote, and relevant checks. Write a meaningful commit subject when pending changes exist.
Then run:

```text
./.agents/bin/ai git-push --project . --message "<reviewed subject>"
```

Pass the branch as a positional argument or `--branch <name>` if supplied; the command
rejects a mismatch instead of switching.
If the work is already committed, it pushes without an extra commit. It checks remote
divergence before committing and never force-pushes. A network or permission denial must
be reported with the retained local commit, not bypassed.
