# Backend scope

Load only the selected Django DRF or FastAPI behavior pack. Generate the exact
structure declared by that pack under `apps/backend/`. Implement model-to-API
vertical slices, additive migrations, structured errors, security controls, tests,
and the stabilized OpenAPI contract. Require the selected pack's independent verifier
before the backend gate can pass. PostgreSQL is mandatory for both backend frameworks.
Require schema creation exclusively through migrations and validate connection,
empty-database upgrade, migration head/drift/idempotence, tables, constraints, indexes,
hot-query plans, and query budgets in `.ai/evidence/database-verification.json`.
