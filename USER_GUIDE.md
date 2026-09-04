# AI Workflow User Guide

This guide presents the workflow in the order a user normally follows it and includes the complete
command and flag reference for every skill shipped by `agents`.
The workflow must be mounted in the target project as `.agents`. Only PRD-selected nested
submodules are initialized.

For first installation, the user can give Codex only this plain-text instruction—no Git knowledge
or preinstalled workflow skill is needed:

```text
setup-workflow "https://github.com/Dolan001/agents.git"
```

This is not a `$skill` or terminal command. Codex reads it as an installation request, adds the
repository as `.agents`, runs the deterministic pack selector, asks only for missing framework
choices, initializes `base` plus the selected packs, verifies them, and asks the user to reopen
Codex. `$start-build` becomes available after that refresh.

The selector reads the PRD before downloading nested repositories. React selects `reactjs`; Next.js
selects `nextjs`; Flutter selects `flutter`; and the backend selects exactly one of `drf` or
`fastapi`. `rag` and `webscraping` are selected only by explicit PRD requirements. `aws` is loaded
only by an explicit AWS deployment workflow. Selection evidence is stored in
`.ai/selected-packs.json`, and later commands lazily reconcile it when the PRD changes.

## Invocation model

Type a skill in the Codex conversation, not in the terminal:

```text
$start-build --prd PRD.md --github-user dolan --frontend nextjs --backend django-drf
```

Codex validates the request, reads the skill, and invokes the equivalent workflow CLI under
`./.agents/bin/ai`. The examples below show both forms. Paths must be inside the target project.
Boolean flags such as `--push` do not take `true` or `false`; include the flag to enable it.
Repeatable flags must be written once per value.

The workflow supports Codex only. Therefore, `--adapter` accepts only `codex` and normally does not
need to be written. Direct CLI commands support `-h` or `--help`.

## Recommended command order

Most users need only the one-shot path:

```text
setup-workflow "<workflow-git-url>"
    -> reopen Codex
    -> $start-build
```

For deliberate stage-by-stage execution, use:

```text
$generate-prd                 # only when PRD.md does not already exist
    -> $start-design
    -> $start-generatehtml
    -> $start-frontend and/or $start-mobile
       (design synchronization runs automatically)
    -> $start-backend
    -> $start-integration
    -> $start-testing
    -> $start-deployment      # only when AWS preparation is required
    -> $start-delivery
```

Afterward, use `$workflow-status` or `$resume-build` for recovery, `$sync-design` for an explicit
design recheck, `$resolve-token` for a scoped change, and the deployment operation skills only for
explicitly authorized live AWS work.

## All available skills

| Skill | Purpose | Normal stopping point or effect |
|---|---|---|
| `$generate-prd` | Convert requirements into a validated PRD | Ready `PRD.md` |
| `$start-design` | Create the design specification | Design specification |
| `$start-generatehtml` | Generate and approve static HTML | Approved HTML |
| `$start-frontend` | Build React or Next.js | Frontend gate |
| `$start-mobile` | Build Flutter for Android and iOS | Mobile gate |
| `$sync-design` | Explicitly recheck or repair client design fidelity | Verified web/mobile design evidence |
| `$start-backend` | Build Django DRF or FastAPI | Backend gate |
| `$start-integration` | Connect selected clients and backend | Integration gate |
| `$start-testing` | Run complete independent verification | Testing/security gate |
| `$start-deployment` | Generate and verify AWS deployment assets | Deployment-readiness gate; no cloud mutation |
| `$start-delivery` | Finish verified feature delivery | Delivery gate |
| `$start-build` | One-shot shortcut for the entire lifecycle | Delivery gate |
| `$workflow-status` | Inspect checkpoints and blockers | Read-only report |
| `$resume-build` | Resume from durable verified checkpoints | Requested remaining lifecycle |
| `$resolve-token` | Diagnose and resolve one scoped work token | Commit, push, and unmerged PR after approval |
| `$deployment-status` | Read deployment evidence | Read-only report |
| `$deploy-staging` | Deploy the verified immutable release to AWS staging | Verified staging evidence |
| `$deploy-production` | Promote the staging digest to AWS production | Verified production evidence |
| `$rollback-deployment` | Restore a named AWS environment | Verified rollback evidence |

## PRD generation

### `$generate-prd`

```text
$generate-prd --requirements <path> [--output <path>] [--answer <QNNN=answer>]...
./.agents/bin/ai generate-prd --project . --requirements <path> \
  --output PRD.md --adapter codex [--answer <QNNN=answer>]...
```

| Flag | Value | Default | Meaning |
|---|---|---|---|
| `--project` | project directory | `.` | Target project root. |
| `--requirements` | in-project path | required | Requirements source. |
| `--output` | in-project path | `PRD.md` | Validated PRD destination. |
| `--answer` | `QUESTION_ID=answer` | none | Answer one active clarification. Repeat for every answer in the current batch. |
| `--adapter` | `codex` | `codex` | Execution adapter. |

The command stops with `NEEDS_INPUT` when material decisions are missing and resumes using repeated
`--answer` flags. Actual credentials are blocked; use variable names and placeholders only. Skip
this command when a validated `PRD.md` already exists.

The generated capability matrix always records `RAG: Required` or `RAG: Not required`. When RAG is
required, intake also resolves source formats and retention, source ACLs, ingestion/versioning,
embedding and provider policy, hybrid retrieval, citations/abstention, and measurable quality,
latency, security, and cost gates. `$start-build` activates `rag` automatically; there is no RAG
framework flag and no separate RAG application command.

It also records `Web scraping: Required` or `Web scraping: Not required`. When required, intake asks
only for missing website scope, target fields, access/authentication ownership, navigation complexity,
schedule and limits, PostgreSQL identity/update rules, and sanitized evidence policy. `$start-build`
then loads `webscraping` only for requirements, relevant backend/integration work, and independent
testing. It never creates a separate scraper application or loads scraping guidance for unrelated
features.

Generated site adapters store approved selector routes as versioned YAML: URL/page state, window,
nested iframe chain, open shadow-root chain, reveal actions, primary ID/semantic/CSS/XPath selector,
fallbacks, transforms, validation and structural fingerprint. Fixture verification is the default;
live discovery or smoke testing requires an explicitly approved domain/account/page scope.

## Shared flags for start and resume skills

The following flags are accepted by `$start-design`, `$start-generatehtml`, `$start-frontend`,
`$start-mobile`, `$start-backend`, `$start-integration`, `$start-testing`, `$start-deployment`,
`$start-delivery`, `$start-build`, and `$resume-build`.
In command patterns below, `[shared start flags]` means any applicable flag from this table that is
not already shown; do not repeat the same flag.

| Flag | Value | Default | Meaning |
|---|---|---|---|
| `--project` | project directory | `.` | Target project root. |
| `--prd` | in-project Markdown path | auto-discovered | PRD path. Without it, exactly one of `docs/PRD.md`, `PRD.md`, `docs/prd.md`, or `prd.md` must exist. |
| `--project-id` | identifier | derived from project directory | Durable workflow project identifier. |
| `--github-user` | GitHub user/owner string | none | Required for a fresh target when a safe workflow branch must be created. |
| `--branch-feature` | feature name | project directory name | Feature portion used when creating `ai/<github-user>/<feature>`. |
| `--html` | in-project HTML path | none | Optional HTML input. Repeat once per file. |
| `--screenshot` | in-project PNG/JPEG/WebP path | none | Optional screenshot input. Repeat once per file. |
| `--frontend` | `react`, `nextjs`, or `unknown` | `unknown` | Web selection. Do not explicitly pass `unknown` when the requested stage requires web. |
| `--mobile` | `flutter` or `unknown` | `unknown` | Mobile selection. Do not explicitly pass `unknown` when the requested stage requires mobile. |
| `--backend` | `django-drf`, `fastapi`, or `unknown` | `unknown` | Backend selection. Do not explicitly pass `unknown` when the requested stage requires backend. |
| `--deployment` | `aws` or `unknown` | `unknown` | Deployment selection. Pass `aws` only to `$start-deployment`; complete-build commands reject it. |
| `--adapter` | `codex` | `codex` | Execution adapter. |
| `--commit-verified` | no value | off | Commit independently verified feature changes. Use only with explicit authorization. |
| `--push` | no value | off | Push verified commits from the current workflow branch. Use only with explicit authorization. |
| `--remaining` | no value | already enabled | Compatibility flag; commands already resume only remaining work. |

Frameworks explicitly declared in the PRD take precedence and do not need to be repeated. At least
one client—React, Next.js, or Flutter—is required for backend and later complete-build stages.
`--html` and `--screenshot` can be combined and repeated:

```text
$start-build --html HTML/input/home.html \
  --screenshot HTML/input/home-mobile.png \
  --screenshot HTML/input/home-desktop.png
```

## Build lifecycle skills

### `$start-design`

```text
$start-design [shared start flags]
./.agents/bin/ai start-design --project . --adapter codex [shared start flags]
```

Runs missing bootstrap and requirements work, creates `HTML/design-specification.md`, and stops
before approved HTML or application source.

### `$start-generatehtml`

```text
$start-generatehtml [shared start flags]
./.agents/bin/ai start-generatehtml --project . --adapter codex [shared start flags]
```

Runs missing design prerequisites, generates or validates approved static HTML, and stops before
frontend or mobile implementation.

### `$start-frontend`

```text
$start-frontend --frontend <react|nextjs> [shared start flags]
./.agents/bin/ai start-frontend --project . --adapter codex \
  --frontend <react|nextjs> [shared start flags]
```

Builds the selected web frontend from approved HTML, runs pixel/semantic design synchronization and
independent frontend verification, then stops before backend work.

### `$start-mobile`

```text
$start-mobile --mobile flutter [shared start flags]
./.agents/bin/ai start-mobile --project . --adapter codex \
  --mobile flutter [shared start flags]
```

Builds Flutter for Android and iOS, runs design synchronization and independent mobile verification,
then stops after the mobile gate.

### `$start-backend`

```text
$start-backend --backend <django-drf|fastapi> [client selection] [shared start flags]
./.agents/bin/ai start-backend --project . --adapter codex \
  --backend <django-drf|fastapi> [client selection] [shared start flags]
```

Requires at least one selected client, runs missing client prerequisites, builds the PostgreSQL
backend, and stops before integration.

### `$start-integration`

```text
$start-integration [resolved framework flags] [shared start flags]
./.agents/bin/ai start-integration --project . --adapter codex \
  [resolved framework flags] [shared start flags]
```

Runs missing prerequisites, connects the typed client boundaries to the backend, executes contract
checks, and stops after integration.

### `$start-testing`

```text
$start-testing [resolved framework flags] [shared start flags]
./.agents/bin/ai start-testing --project . --adapter codex \
  [resolved framework flags] [shared start flags]
```

Runs missing prerequisites and the complete independent API, browser, mobile, integration, design,
accessibility, security, and release-readiness test gates. It does not push.

### `$start-deployment`

```text
$start-deployment --deployment aws [resolved framework flags] [shared start flags]
./.agents/bin/ai start-deployment --project . --adapter codex --deployment aws \
  [resolved framework flags] [shared start flags]
```

Runs missing testing/security prerequisites and generates AWS infrastructure, CI/CD, observability,
and runbooks. It never plans, applies, deploys, changes DNS, or uses live credentials.

### `$start-delivery`

```text
$start-delivery [resolved framework flags] [--commit-verified] [--push]
./.agents/bin/ai start-delivery --project . --adapter codex \
  [resolved framework flags] [--commit-verified] [--push]
```

Runs missing prerequisites through release readiness. `--commit-verified` and `--push` require
explicit user authorization.

### `$start-build`

```text
$start-build [resolved framework flags] [shared start flags]
./.agents/bin/ai start-build --project . --adapter codex \
  [resolved framework flags] [shared start flags]
```

Runs the complete application lifecycle through delivery while always deferring deployment. Do not
pass `--deployment`; run `$start-deployment --deployment aws` separately later. It does not push
unless `--push` is explicit.

If the PRD activates RAG, the same invocation additionally designs the RAG contract, builds client
surfaces and the selected DRF/FastAPI implementation, connects the typed/streaming contract, and
requires independent RAG evidence before the corresponding phase gates pass.

Example with every meaningful selection:

```text
$start-build --project . --prd docs/PRD.md --project-id trustix \
  --github-user dolan --branch-feature customer-accounts \
  --html HTML/input/home.html --screenshot HTML/input/home-mobile.png \
  --frontend nextjs --mobile flutter --backend django-drf \
  --adapter codex --commit-verified --push
```

## Status, recovery, and design fidelity

### `$workflow-status`

```text
$workflow-status [--project <directory>]
./.agents/bin/ai status --project . --json
```

The only user-selectable flag is `--project` (default `.`). JSON mode is always used internally.
This command is read-only. Its output includes build-issue totals and links to
`.ai/issues/REPORT.md` and the append-only `.ai/issues/events.jsonl` history.

### `$resume-build`

```text
$resume-build [shared start flags]
./.agents/bin/ai resume-build --project . --adapter codex [shared start flags]
```

Resumes only invalid or incomplete nodes from durable checkpoints. Preserve saved framework and Git
choices. `--push` remains opt-in.

### `$sync-design`

```text
$sync-design [--project <directory>] [--target <all|frontend|mobile>] \
  [--check-only] [--allow-baseline-update] [--adapter codex]
./.agents/bin/ai sync-design --project . --target all --adapter codex
```

| Flag | Value | Default | Meaning |
|---|---|---|---|
| `--project` | project directory | `.` | Initialized target project. |
| `--target` | `all`, `frontend`, or `mobile` | `all` | Implemented client target to compare. |
| `--adapter` | `codex` | `codex` | Execution adapter. |
| `--check-only` | no value | off | Report drift without editing application paths. |
| `--allow-baseline-update` | no value | off | Permit approved HTML changes. Requires explicit authorization and cannot be combined with `--check-only`. |

Normal mode repairs meaningful drift and independently verifies all deterministic pixel, semantic,
responsive, state, accessibility, and platform checks.

## Scoped token resolution

### `$resolve-token`

Diagnosis:

```text
$resolve-token --token <frontend|mobile|backend>/<TOKEN_ID>/TOKEN.md
./.agents/bin/ai resolve-token --project . --token <path> --adapter codex
```

Approved implementation:

```text
$resolve-token --token <path> --approve [--github-user <user>] [--remote <name>]
./.agents/bin/ai resolve-token --project . --token <path> --adapter codex \
  --approve [--github-user <user>] [--remote <name>]
```

| Flag | Value | Default | Meaning |
|---|---|---|---|
| `--project` | project directory | `.` | Target project. |
| `--token` | supported `TOKEN.md` path | required | Exactly one frontend, mobile, or backend token. |
| `--adapter` | `codex` | `codex` | Execution adapter. |
| `--approve` | no value | off | Approve the diagnosed plan and begin implementation. Never inferred. |
| `--github-user` | GitHub user/owner string | saved/current context | Used when constructing the token branch. |
| `--remote` | Git remote name | `origin` | Remote used for push and PR preparation. |

The first invocation diagnoses and returns a plan without edits. After approval, the resolver creates
a token branch, implements and verifies the plan, commits, pushes, and opens an unmerged PR targeting
the branch that was current during diagnosis.

## AWS deployment operations

`$start-deployment --deployment aws` is the only build-stage command that generates deployment
assets. The following skills form the separate live-operation boundary.

### `$deployment-status`

```text
$deployment-status [--project <directory>]
./.agents/bin/ai deployment-status --project .
```

`--project` defaults to `.`. The command reads local readiness and deployment evidence without
contacting AWS or mutating state.

### `$deploy-staging`

```text
$deploy-staging [--project <directory>] [--execute]
./.agents/bin/ai deploy-staging --project . [--execute]
```

| Flag | Value | Default | Meaning |
|---|---|---|---|
| `--project` | project directory | `.` | Target project. |
| `--execute` | no value | off | Perform the project-owned staging deployment. Without it, the command is a dry run. |

Run the dry invocation first. Add `--execute` only after explicit authorization. The underlying CLI
also accepts `--approve-production` for parser consistency, but it has no staging purpose and must
not be used.

### `$deploy-production`

```text
$deploy-production [--project <directory>] [--execute] [--approve-production]
./.agents/bin/ai deploy-production --project . --execute --approve-production
```

| Flag | Value | Default | Meaning |
|---|---|---|---|
| `--project` | project directory | `.` | Target project. |
| `--execute` | no value | off | Perform the production promotion rather than a dry run. |
| `--approve-production` | no value | off | Explicit protected-production approval required for execution. |

Production promotes the exact staging-verified immutable digest; it does not rebuild.

### `$rollback-deployment`

```text
$rollback-deployment --environment <staging|production> [--project <directory>] \
  [--execute] [--approve-rollback]
./.agents/bin/ai rollback-deployment --project . --environment <staging|production> \
  --execute --approve-rollback
```

| Flag | Value | Default | Meaning |
|---|---|---|---|
| `--project` | project directory | `.` | Target project. |
| `--environment` | `staging` or `production` | required | Environment to restore. |
| `--execute` | no value | off | Execute the project-owned rollback rather than a dry run. |
| `--approve-rollback` | no value | off | Explicit rollback authorization required for execution. |

The workflow verifies the prior immutable release and database compatibility. It never performs an
automatic destructive database reversal.

## Internal CLI utilities are not skills

Commands such as `select-packs`, `init`, `adopt`, `one-shot`, `inspect`, `reconcile`, `plan`, `build`, `verify`,
`test`, `review`, `status`, `resume`, `push`, `doctor`, `pipeline`, `clean-state`, and
`compare-images` are orchestration primitives used by skills or maintainers. They are intentionally
not separate `$skills`. Use the user-facing skill commands above for normal operation.
