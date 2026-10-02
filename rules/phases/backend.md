# Backend scope

Load only the selected Django DRF or FastAPI behavior pack. Generate the exact
structure declared by that pack under `apps/backend/`. Implement model-to-API
vertical slices, additive migrations, structured errors, security controls, tests,
and the stabilized OpenAPI contract. Require the selected pack's independent verifier
before the backend gate can pass. PostgreSQL is mandatory for both backend frameworks.
Require schema creation exclusively through migrations and validate connection,
empty-database upgrade, migration head/drift/idempotence, tables, constraints, indexes,
hot-query plans, and query budgets in `.ai/evidence/database-verification.json`.
Run these checks in one uniquely named Compose project. Keep PostgreSQL private to the Compose
network and address it by service name; never depend on host port 5432 or create a sequence of
ad hoc containers with changing forwarded ports. Wait for the declared database health check once,
then reuse that runtime for clean-database, prior-schema, live HTTP, persistence, and cleanup checks.
Run the backend as a network service and make HTTP requests from a project-owned test container or
runtime client on the same network. Do not substitute in-process clients for live HTTP.
Validate dependency-lock alternatives, activated domain capability groups, and executable source
policies. Require `.ai/evidence/backend-verification.json` with exact successful import, startup,
readiness, API, authorization, transaction/concurrency, OpenAPI, and security commands.
When a domain task activates the background-task capability, require Celery with Redis, a
PostgreSQL transactional outbox/job, framework worker configuration and discovery, task tests, and
live broker/worker/enqueue/retry/idempotency/duplicate/outbox/failure evidence. Scheduled delivery is
verified only when requirements activate it. FastAPI in-process tasks do not satisfy durable work.
When realtime is activated, require the selected framework realtime skill and
`.ai/evidence/realtime/backend.json`. PostgreSQL is authoritative; Redis is transient fan-out.
Require secure authentication, per-command authorization, versioned events, cursor replay,
multi-instance delivery, outage recovery, limits, slow-consumer policy, and graceful shutdown.
