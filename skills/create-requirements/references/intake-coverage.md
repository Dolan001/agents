# Requirements intake coverage

This is a decision checklist, not a demand that the user answer every line. The downstream
document architect writes technical detail and safely reversible defaults. Ask the user only for
material product-owned decisions; use additional short rounds when needed. A source with
unresolved material decisions stays pending.

## Source outline

1. **Purpose and users:** problem, target users, owner, desired outcome, and how success is observed.
2. **Scope and priorities:** first release, later work, exclusions, dependencies, and known deadlines.
3. **Deliverables and preferences:** web, Android/iOS, desktop GUI, Python library/CLI, or a
   combination; explicit framework choices and hard constraints, or "No preference."
4. **Journeys and behavior:** main user tasks in order, inputs and outputs, validation, failure,
   empty-state and permission behavior, and observable acceptance examples.
5. **Users and access:** roles, ownership/sharing boundaries, sign-in needs, and who can read,
   change, export, or delete information.
6. **Data and integrations:** business objects and relationships, important fields, user uploads,
   external systems, source of real test data, and data ownership.
7. **Experience:** important screens or navigation, content and language, brand references if any,
   accessibility or offline needs that affect users, and device/platform expectations.
8. **Quality and policy:** privacy, retention/deletion, security or compliance commitments,
   performance or scale expectations the user actually owns, audit/reporting needs.
9. **Operations and release:** hosting/deployment request, environments, domain or store ownership,
   rollout/approval responsibilities, budget or location constraints, and support expectations.
10. **Assumptions and open decisions:** visible proposals, their source, unresolved questions,
    and review status. Use credential variable names only; never values.

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
are expected, and which user-owned constraints apply? Are explicit choices preserved, assumptions
separate, unsupported choices surfaced, and any material open decision answered? If not, ask the
next short round before treating the source as ready for approval.
