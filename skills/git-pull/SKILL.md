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

From a project, the default updates `.agents` from `dev` and aligns every pack to
its reviewed Git pin. `--repo base drf` aligns just those packs to the currently
pinned revisions; include `agents` or omit `--repo` to fetch the newest reviewed
agents commit and sync the complete pack set. From the shared workflow workspace,
the command fast-forwards the named independent sibling clones from their declared
branches. `react` is accepted as an alias for `reactjs`.

The CLI checks remotes, branch state, divergence, unfinished Git operations, and
uncommitted work before updating. A dirty or divergent repository is a blocker to
resolve explicitly; do not reset, stash, or switch branches on the user's behalf.
