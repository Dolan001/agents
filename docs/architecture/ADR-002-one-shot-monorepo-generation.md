# ADR-002: One-shot agents generate the target monorepo

Status: accepted

## Decision

Do not bundle a demonstration project and do not store runnable application code in
framework repositories. A one-shot development run selects framework behavior packs
from the requested stack, inspects the PRD and optional brownfield code, reconciles
requirements, and then lets specialized agents generate vertical slices directly in
the separate target monorepo.

## Sequence

1. Validate the PRD and target location.
2. Discover supplied code and design evidence without mutation.
3. Select web and/or Flutter mobile behavior packs plus one backend behavior pack.
4. Reconcile requirements and current implementation state.
5. Create architecture decisions, a feature plan, and task contracts.
6. Acquire target path leases.
7. Generate or modify requirement-backed vertical slices under `apps/`.
8. Generate contracts and shared packages only when requirements need them.
9. Run project-owned checks and independent verification.
10. Record durable evidence and create safe feature commits.

Each step is represented by a phase manifest, blueprint node graph, and deterministic
gate contract. The control plane is validated with `ai pipeline` before a run.

## Consequences

Framework packs stay small, code-free, and reusable across new and existing projects.
Generated code reflects the actual PRD instead of a copied example. The orchestrator
must never treat a framework pack as a source tree to copy.
