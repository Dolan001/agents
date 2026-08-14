---
name: start-mobile
description: Run missing prerequisites and build the selected Flutter application for Android and iOS from approved design and contracts, then stop after the mobile gate. Use when the user invokes start-mobile or requests only mobile implementation.
---

# Start Flutter mobile

Read `.agents/commands/references/start-command-contract.md`, require Flutter as the
mobile framework, then invoke `./.agents/bin/ai start-mobile` with `--adapter codex`
and `--mobile flutter`. Run missing design prerequisites and stop after the mobile
gate. Do not add Git delivery options unless explicitly requested.
