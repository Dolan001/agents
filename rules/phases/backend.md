# Backend scope

Load only the selected Django DRF or FastAPI behavior pack. Generate the exact
structure declared by that pack under `apps/backend/`. Implement model-to-API
vertical slices, additive migrations, structured errors, security controls, tests,
and the stabilized OpenAPI contract. Require the selected pack's independent verifier
before the backend gate can pass. PostgreSQL is mandatory for both backend frameworks.
Require schema creation exclusively through migrations and validate connection,
empty-database upgrade, migration head/drift/idempotence, tables, constraints, indexes,
hot-query plans, and query budgets in `.ai/evidence/database-verification.json`.
Run these checks in one deterministic project-scoped Compose project shared by every backend slice
and the final verifier. Keep PostgreSQL private to the Compose
network and address it by service name; never depend on host port 5432 or create a sequence of
feature-named Compose projects or ad hoc containers with changing forwarded ports. Wait for the
declared database health check once, then reuse that runtime for slice tests, clean-database,
prior-schema, live HTTP, persistence, and cleanup checks.
Docker Compose is the sole runtime provider for PostgreSQL and, when activated by requirements,
Redis, Celery workers, and Celery Beat. Never discover, install, start, or use host PostgreSQL,
Redis, or globally installed Celery as a fallback. If an image is absent, pull its reviewed pinned
version or build the locked backend image through Compose. Derive one normalized Compose project
name from the checkout path, and use distinct normalized database names for each verification
purpose. Keep PostgreSQL identifiers within 63 bytes and credentials out of names.
Build dependencies only when the Dockerfile or dependency manifests/locks change. For source-only
changes, mount current source into the project-owned service or test container. Never run
`docker compose up --build` for every feature. Remove one-off containers and disposable databases
after each check without stopping shared services. Tag the dependency image with the deterministic
project name and label it `ai.workflow.project=<compose-project>`. After the final backend verifier
passes, run a project-scoped Compose down with volumes and orphans removed. Delete only dangling
images carrying that exact workflow-project label; retain one current tagged dependency image for
later frontend/mobile integration. Never use unfiltered/global Docker prune as workflow cleanup and
never remove unrelated running workloads, volumes, images, or caches.
Run the backend as a network service and make HTTP requests from a project-owned test container or
runtime client on the same network. Do not substitute in-process clients for live HTTP.
Validate dependency-lock alternatives, activated domain capability groups, and executable source
policies. Require `.ai/evidence/backend-verification.json` with exact successful import, startup,
readiness, API, authorization, transaction/concurrency, OpenAPI, and security commands.
When a domain task activates the background-task capability, require Celery with Redis, a
PostgreSQL transactional outbox/job, framework worker configuration and discovery, task tests, and
live broker/worker/enqueue/retry/idempotency/duplicate/outbox/failure evidence. Scheduled delivery is
verified only when requirements activate it. FastAPI in-process tasks do not satisfy durable work.
Run worker and Beat processes from the same locked backend image as separate Compose services;
Redis is a version-pinned Compose service, not a host daemon.
When realtime is activated, require the selected framework realtime skill and
`.ai/evidence/realtime/backend.json`. PostgreSQL is authoritative; Redis is transient fan-out.
Require secure authentication, per-command authorization, versioned events, cursor replay,
multi-instance delivery, outage recovery, limits, slow-consumer policy, and graceful shutdown.
