# Schemas

Canonical workflow schemas live in the private `base_ai/schemas` repository and are
mounted through the `base_ai` submodule in production. The orchestrator validates
task contracts, workflow state, requirements, evidence, capabilities, skills, path
leases, and failure records against those pinned schemas.

Provider-neutral orchestration schemas in this directory additionally validate PostgreSQL,
backend, realtime, AWS deployment readiness, immutable release identity, and live deployment
operation evidence without storing credentials. `prd-intake.schema.json` validates the bounded
clarification-or-ready decision emitted by the PRD architect before any build state exists. A ready
assessment must also provide decision provenance for the generated architecture matrix; each source
is restricted to `requirements`, `answer`, `workflow-invariant`, or `assumption`.

The three `design-fidelity-*.schema.json` contracts bind selected web/mobile comparisons to exact
approved HTML hashes, deterministic route/screen cases, raw rendered/diff images, localized findings,
observed changed paths, successful visual/accessibility/framework checks, and a distinct independent
verifier. They prohibit a passing result with unresolved meaningful drift.
