# ADR-003: Authoritative delivery lifecycle

Status: accepted

The workflow repositories contain behavior and control logic, never a demonstration
application. A user supplies a separate target monorepo with a required PRD and
optional design evidence. `base_ai` is private shared behavior; `drf_ai`, `fastapi_ai`,
`flutter_ai`, `react_ai`, `nextjs_ai`, and `aws_ai` describe exact generated structures and
production decisions; `ai_workflow` links them as pinned submodules and executes the lifecycle.

The default lifecycle is strictly sequential:

```text
bootstrap -> requirements/contracts -> approved static HTML -> optional web
          -> optional Flutter mobile -> backend -> typed integration
          -> independent test/security -> optional AWS asset readiness -> feature Git delivery
```

Static HTML is the reviewable design contract. Supplied HTML is validated and
preserved; when absent, static HTML is generated from screenshots/design evidence or,
last, the PRD. Web or Flutter implementation cannot begin until this baseline is
approved. Backend follows every selected client to eliminate contract and UX drift.

Production knowledge uses progressive disclosure: concise agents and skills route to
framework references only when relevant. Accuracy comes from executable project-owned
checks, artifact contracts, independent verification, and fail-closed gates, not from
loading one enormous prompt. Time and tokens are reduced through bounded context,
focused checks, checkpoints, and verified artifact reuse.

Application changes occur only on `ai/<github-user>/<feature>` branches. A feature can
be committed only after independent verification and the test/security gate; staging
is restricted to evidence-declared paths. Push is explicit. The workflow never merges
or deploys during the build lifecycle. Separate environment commands may deploy or roll back only
after explicit authorization, readiness, protected production approval, and runtime evidence.
