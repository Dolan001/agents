# Requirements intake coverage

This is a decision checklist, not a demand that the user answer every line. The downstream
document architect writes technical detail and safely reversible defaults. Ask the user only for
material product-owned decisions; use additional short rounds when needed. A source with
unresolved material decisions stays pending.

## Requirements structure

Use these second-level headings in the generated source. Keep each requirement atomic, scoped to
the first release or clearly marked later, and give it a stable ID. Preserve IDs when revising;
never recycle an ID for different behavior. User-specified choices and assistant proposals must
remain distinguishable.

1. `## Product goals and release scope` — problem, audience, desired outcomes, MVP, later work,
   exclusions, success criteria, and dependencies.
2. `## Deliverables and framework choices` — selected web/mobile/desktop/package/backend outputs,
   required frameworks or explicit no preference, and deployment scope. Use canonical framework
   labels where chosen (`React`, `Next.js`, `Flutter`, `Python Desktop`, `Django REST Framework`,
   `FastAPI`). Do not silently substitute an unsupported requirement.
3. `## Users, roles, and permissions` — actor list, ownership and sharing boundaries, sign-in,
   who may read/write/delete/export, and administrator limits.
4. `## Functional requirements` — `FR-001` onward, each stating actor, trigger, and observable
   result. Cover primary journeys, validation, failures, authorization, and relevant empty/offline
   states. Split unrelated outcomes rather than hiding them in one long bullet.
5. `## Business rules and edge cases` — `BR-001` onward for rules such as membership, retention,
   limits, status meanings, lifecycle transitions, and conflicting or failed actions.
6. `## Data and privacy` — core business objects and relationships, ownership, visibility,
   sensitive fields, retention/deletion, uploads, external sources, and realistic test-data needs.
7. `## Experience and design requirements` — screens/routes, key layouts and journeys, visual
   direction or supplied references, responsive/device scope, accessibility, content, and loading,
   empty, error, permission, and offline states. Use `UX-` IDs when requirements are specific.
8. `## Non-functional requirements` — `NFR-001` onward for measurable or otherwise verifiable
   performance, reliability, security, accessibility, capacity, data integrity, and observability
   outcomes. Include at least one numeric service-quality target needed by the PRD validator.
   If the user supplied no numeric target, propose a conservative baseline, label it as proposed,
   and ask for approval; do not present it as a prior user decision. State how each target can be
   checked, including the load or environment when relevant.
9. `## Structural requirements` — `SR-001` onward for required system boundaries and constraints:
   clients and backend responsibilities, API/realtime boundaries, persistence and background work,
   named external integrations, environment/deployment boundary, and required data flows. Separate
   mandated stack from architect-owned design; do not turn implementation suggestions into
   immutable requirements. A system-context sketch may help but cannot replace the ID register.
10. `## Acceptance scenarios and traceability` — `AC-001` onward with Given/When/Then or another
    observable test condition, each naming its `FR` (and relevant `BR`/`NFR`/`UX`/`SR`). Cover
    success, validation, denied access, failure/recovery, and a representative end-to-end journey.
    Every in-scope `FR` needs at least one `AC`.
11. `## Delivery and verification` — real-data/API verification needs, target environments,
    release approval, migration/backup expectations when relevant, and what is deferred.
12. `## Assumptions and open decisions` — source/provenance of proposed choices, dependencies,
    risks, and remaining user-owned questions. Use `None` only when no material decision remains.

Put `Review status: Pending user approval` near the top; change it only on explicit approval.
The file is a product source, not a prewritten PRD: do not copy the PRD's 24 headings, database
schema, API pagination, worker topology, or cloud infrastructure unless the user requires them.

## Coverage prompts

Ask about missing user-owned facts behind those headings, not every technical detail. Record only
credential variable names or placeholders, never values. When the user delegated a product choice,
make a reviewable proposal and mark its provenance rather than silently claiming it came from the
user. When the user did not delegate a material choice, ask for it across as many short rounds as
needed. Do not mark the source approved while material questions remain.

The PRD turns journeys into `FR`, `AC`, `BR`, and `NFR` IDs and traceability. The TRD derives
architecture and APIs; UI/UX derives routes, screens, states, and design; backend derives data,
permissions, errors, and verification; delivery derives environments and release operations.
The requirements source should provide the user-owned facts behind those documents. It need not
pre-design database indexes, API pagination, worker topology, cloud architecture, or test tooling.

## Conditional checks

- **Framework compatibility:** the current workflow supports React or Next.js web, Flutter mobile,
  Python Desktop/PySide6 GUI or Python library/CLI, and Django REST Framework or FastAPI backend.
  Web/mobile builds require a backend. If the user's required stack is outside these options or
  they want a web/mobile client without a backend, surface the mismatch and ask how to proceed;
  never silently replace their choice. If they have no preference, say so explicitly.
- **RAG or document Q&A:** ask which content is allowed, who may access each source, whether answers
  must be grounded and cited, necessary languages, sensitive-data limits, retention/deletion,
  and any user-owned provider or budget constraint. Let the architect choose retrieval mechanics.
- **Web scraping:** ask for authorized websites/URL scope, desired records and fields, account or
  login ownership, allowed access boundaries, and freshness/schedule. Do not infer permission to
  scrape a site from its public visibility.
- **Uploads and external services:** ask what users provide, who owns it, who may see it, and what
  happens when a provider fails; record required provider names only if the user specified them.
- **Realtime and offline:** ask what users need to see when updates arrive, connectivity is lost,
  or work resumes; let the architect choose transport, queues, and reconciliation mechanics.
- **Mobile/desktop/package:** ask for target platforms and distribution expectations only when
  relevant; do not imply an unrequested app store release or native installer.
- **Deployment:** AWS is the supported explicit cloud-deployment workflow. If requested, gather
  only user-owned region/residency, domain, environments, availability/recovery, budget, approval,
  and backup/retention expectations. If deployment is not requested, say it is deferred. If another
  provider is mandatory, flag the workflow mismatch before document generation.

## Readiness check before requesting approval

Can a reviewer tell who uses the product, what the first release does, what it excludes, who may
access each important data type, what successful and failed journeys look like, which deliverables
are expected, and which user-owned constraints apply? Does every `FR` have an acceptance scenario,
do the `BR`, `NFR`, and `SR` registers agree with those journeys, and can the UI, backend, and
delivery documents trace back to a named source requirement? Are explicit choices preserved,
assumptions separate, unsupported choices surfaced, and any material open decision answered? If
not, ask the next short round before treating the source as ready for approval.
