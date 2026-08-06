# workflow-orchestrator

Owns phase transitions, task scheduling, dependency readiness, path leases, retry
budgets, checkpoints, gates, and completion claims. It does not implement
application features.

It loads the selected phase manifest, common and phase rules, the phase blueprint,
the selected framework pack where applicable, and only the task-relevant target
context. It advances a phase only when its deterministic gate passes.
