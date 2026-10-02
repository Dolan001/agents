---
name: start-mobile
description: Build the selected Flutter application for Android and iOS from approved design and integrate it with the verified live backend, then stop after the mobile gate. Use when the user invokes start-mobile or requests only mobile implementation.
---

# Start Flutter mobile

Read `.agents/commands/references/start-command-contract.md`, require Flutter and resolve the backend,
mobile framework, then invoke `./.agents/bin/ai start-mobile` with `--adapter codex-reviewed`
and `--mobile flutter`. Run missing design prerequisites and stop after the mobile
gate. Do not add Git delivery options unless explicitly requested.
Generate the typed client from current OpenAPI and require live authenticated, success, negative,
authorization, persistence, and error-mapping journeys. Fixtures cannot satisfy the mobile gate.
