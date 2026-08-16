# Schemas

Canonical workflow schemas live in the private `base_ai/schemas` repository and are
mounted through the `base_ai` submodule in production. The orchestrator validates
task contracts, workflow state, requirements, evidence, capabilities, skills, path
leases, and failure records against those pinned schemas.

Provider-neutral orchestration schemas in this directory additionally validate PostgreSQL,
backend, realtime, AWS deployment readiness, immutable release identity, and live deployment
operation evidence without storing credentials.
