---
name: git-merge
description: Merge user-authorized workflow repair PRs after checking exact heads, base branches, reviews, and CI. Use when the user invokes git-merge or asks to merge workflow PRs.
---

# Merge workflow PRs

Read `.agents/agents/git-maintenance-agent.md`. A user may name exact PRs:

```text
./.agents/bin/ai git-merge --project . base pr-2 agents pr-6
```

With no pairs, the command merges all PRs recorded as pending merge approval in
this project's `.ai/workflow-pr-proposals/`. It never sweeps unrelated GitHub PRs.
The CLI preflights every PR, merges framework/base PRs before agents, and matches
the reviewed head commit immediately before each merge. It does not pull code or
change local branches. Report any partial merge accurately.
