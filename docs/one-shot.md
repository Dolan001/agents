# One-shot development contract

One-shot development operates on a user-supplied target, never inside a framework
pack and never inside this orchestration repository.

The orchestrator validates the PRD, detects new versus brownfield mode, selects the
configured frontend and backend behavior packs, performs discovery and reconciliation,
creates vertical-slice task contracts, and dispatches specialized agents. Agents write
only to leased target-monorepo paths. Framework-pack files are read-only behavioral
context and are never copied into the application.
