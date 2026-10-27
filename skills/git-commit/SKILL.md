---
name: git-commit
description: Review and commit current repository changes on the checked-out branch without pushing. Use when the user requests a Git commit or invokes git-commit.
---

# Git commit

Read `.agents/base/agents/git-workflow-agent.md`. Inspect the current branch and diff,
resolve any clear delivery blocker within the requested scope, and write a commit subject
that describes the actual changes. Then run:

```text
./.agents/bin/ai git-commit --project . --message "<reviewed subject>"
```

Pass the branch as a positional argument or `--branch <name>` if the user supplied one.
This verifies the current branch;
it never switches branches. If there are no changes, report that the tree is clean.
Do not push for a commit-only request.
