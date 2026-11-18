---
name: git-pull
description: Fast-forward workflow repositories safely, or sync a project's .agents and framework packs to reviewed submodule pins. Use when the user invokes git-pull or asks to update workflow repos.
---

# Pull workflow repositories

Read `.agents/agents/git-maintenance-agent.md`, then run:

```text
./.agents/bin/ai git-pull --project .
./.agents/bin/ai git-pull --project . --repo base drf
```

Every workflow repository uses `dev` as its default and update branch. From a
project, the default updates `.agents` from `dev`, fetches each pack's `dev`, and
aligns the packs to the reviewed Git pins in that agents commit. `--repo base drf`
fetches and aligns just those packs to the current pins; include `agents` or omit
`--repo` to get the newest reviewed pins. From the shared workflow workspace, the
command fast-forwards the independent sibling clones from `dev`. `react` is an
alias for `reactjs`.

The CLI checks remotes, branch state, divergence, unfinished Git operations, and
uncommitted work before updating. A dirty or divergent repository is a blocker to
resolve explicitly; do not reset, stash, or switch branches on the user's behalf.
