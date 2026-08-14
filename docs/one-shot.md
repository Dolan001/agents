# One-shot development contract

One-shot development operates on a user-supplied target, never inside a framework
pack and never inside this orchestration repository.

The orchestrator validates the PRD, detects new versus brownfield mode, selects the
configured web, Flutter mobile, and backend behavior packs, performs discovery and reconciliation,
creates vertical-slice task contracts, and dispatches specialized agents. Agents write
only to leased target-monorepo paths. Framework-pack files are read-only behavioral
context and are never copied into the application.

The workflow uses:

```text
command
  → phase manifest
  → blueprint nodes
  → scoped stable agents and only selected web/mobile/backend skills
  → evidence gate
  → durable checkpoint
```

This mirrors the useful control-plane architecture of `claude-fullstack` without
copying framework source templates or placing a generated project in this repository.
