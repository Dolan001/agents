# ADR-003: Authoritative delivery lifecycle

Status: accepted

The workflow repositories contain behavior and control logic, never a demonstration
application. A user supplies a separate target monorepo with a required PRD and
optional design evidence. `base` is shared behavior; `drf`, `fastapi`,
`flutter`, `desktop`, `reactjs`, `nextjs`, `rag`, `webscraping`, and `aws` describe exact generated structures and
production decisions; `agents` links them as pinned submodules and executes the lifecycle.

The default lifecycle is strictly sequential:

```text
bootstrap -> requirements/contracts -> optional backend -> optional approved static HTML
          -> optional web -> optional Flutter mobile -> optional Python GUI/package -> integration
          -> independent test/security -> feature Git delivery

explicit later command: start-deployment -> AWS asset readiness
```

Static HTML is the reviewable design contract for web/mobile and GUI flows that need it. Supplied
HTML is validated and preserved; when absent, it can be generated from screenshots/design evidence
or the PRD. Web or Flutter implementation cannot begin until this baseline is approved. A
package-only run skips UI design, and local Python deliverables do not invent a backend. Where a
backend is selected, it is verified before client integration.

Production knowledge uses progressive disclosure: concise agents and skills route to
framework references only when relevant. Accuracy comes from executable project-owned
checks, artifact contracts, independent verification, and fail-closed gates, not from
loading one enormous prompt. Time and tokens are reduced through bounded context,
focused checks, checkpoints, and verified artifact reuse.

`rag` is a cross-stack, requirement-triggered capability pack. It augments the selected backend
and clients, defaults to PostgreSQL full-text plus pgvector hybrid retrieval, and requires separate
retrieval/generation evaluation and zero-leak authorization evidence. It is not a new lifecycle
phase or a standalone generated application, which preserves the existing critical path and avoids
loading RAG context for ordinary products.

`webscraping` is a backend-only, requirement-triggered capability pack. It augments the selected DRF
or FastAPI backend with approved site adapters, versioned selector/context routes, a canonical UC
factory, durable execution and independent fixture-first verification. It is not loaded for ordinary
backend work and is not a separate generated application.

Application changes occur only on `ai/<github-user>/<feature>` branches. A feature can
be committed only after independent verification and the test/security gate; staging
is restricted to evidence-declared paths. Push is explicit. The workflow never merges
or deploys during the build lifecycle. AWS preparation is not an implicit build phase.
Separate deployment commands may generate assets, deploy, or roll back only after
explicit authorization, readiness, protected production approval, and runtime evidence.
