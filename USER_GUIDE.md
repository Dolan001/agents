# AI Workflow User Guide

This guide presents the workflow in the order a user normally follows it and includes the complete
command and flag reference for every skill shipped by `agents`.
The workflow must be mounted in the target project as `.agents`. Only PRD-selected nested
submodules are initialized.

## Start with an idea

The normal path for a new project is:

```text
Project idea -> $create-requirements -> approve REQUIREMENTS.md
    -> $generate-prd (PRD.md)
    -> $prepare-project-docs (TRD.md, UI_UX_SPEC.md, BACKEND_SPEC.md, DELIVERY_SPEC.md)
    -> $start-build
```

Tell Codex the idea, intended users, important features, and any framework preferences in an
ordinary message. The requirements skill asks about missing product decisions and revises the
file until you approve it. Run `$generate-prd` for the PRD, then `$prepare-project-docs` for the related specifications;
the PRD is required for the build, but you do not have to write it yourself. If you already have
approved requirements or a PRD, start from that file and skip earlier creation steps.

For first installation, the user can give Codex only this plain-text instruction—no Git knowledge
or preinstalled workflow skill is needed:

```text
setup-workflow "https://github.com/Dolan001/agents.git"
```

This is not a `$skill` or terminal command. Codex reads it as an installation request and adds the
repository as `.agents`. With only an idea, it initializes the provider bridge and `base`, asks the
user to reopen Codex, and points to `$create-requirements`. With requirements or a PRD, it also
runs the deterministic pack selector. After requirements approval, document preparation validates
the five specifications and selects the required packs.

The selector reads the PRD before downloading nested repositories. React selects `reactjs`; Next.js
selects `nextjs`; Flutter selects `flutter`; Python Desktop and a standalone Python package both
select the `desktop` pack; and the backend selects exactly one of `drf` or
`fastapi`. `rag` and `webscraping` are selected only by explicit PRD requirements. `aws` is loaded
only by an explicit AWS deployment workflow. Selection evidence is stored in
`.ai/selected-packs.json`. Successful project-document preparation reconciles immediately, and
build, token, and design-sync commands reconcile again before using project guidance.

## Select an execution adapter

Codex is the default when no adapter has been selected. To use another installed coding harness,
run one command from the project root:

```bash
./.agents/use-adapter claude
./.agents/use-adapter opencode
./.agents/use-adapter gemini
./.agents/use-adapter cursor
./.agents/use-adapter codex
```

Running `./.agents/use-adapter` with no name also selects Codex. Selection generates the native
provider files and applies to subsequent workflow commands. Agent launches refresh those files when
the selected behavior packs change. The small `.agents/use-adapter` wrapper delegates to the
separately maintained `.agents/agent-bridge` submodule. `--adapter` remains available as a
one-command override.

The bridge makes provider-native agents, skills, commands, and rules discoverable. Lifecycle hooks,
evidence gates, checkpoints, and Git safety still run through `./.agents/bin/ai`; opening a direct
provider chat does not run those controls automatically. Invoke the generated command or skill for
a controlled build. Gemini and Cursor require their respective CLI executables before selection.

## Invocation model

Type a skill in the Codex conversation, not in the terminal:

```text
$start-build --prd PRD.md --github-user dolan --frontend nextjs --backend django-drf
```

Codex validates the request, reads the skill, and invokes the equivalent workflow CLI under
`./.agents/bin/ai`. The examples below show both forms. Paths must be inside the target project.
Boolean flags such as `--push` do not take `true` or `false`; include the flag to enable it.
Repeatable flags must be written once per value.

The workflow supports `codex`, `claude`, `opencode`, `gemini`, and `cursor`, plus the explicit
`codex-reviewed` execution mode. Direct CLI commands support `-h` or `--help`. The examples below
that include `--adapter codex` deliberately pin Codex; normally the flag can be omitted.

## Measure adapter consistency and review lessons

Every agent attempt writes metadata to `.ai/telemetry/attempts.jsonl`: selected adapter, agent,
skill paths, prompt character count, elapsed time, exit code, and provider-reported usage when
available. It does not copy prompt text or adapter output. Character count is a size proxy, not
an exact token or cost measurement.

To compare the same small PRD built separately with different adapters, create a local manifest
outside the run folders:

```json
{
  "cases": [{
    "id": "sample-prd",
    "required_nodes": ["backend/verify-backend/phase"],
    "runs": [
      {"adapter": "codex", "project": "runs/codex"},
      {"adapter": "claude", "project": "runs/claude"}
    ]
  }]
}
```

Run `./.agents/bin/ai evaluate-adapters --manifest comparison.json`. The command is read-only and
returns 0 only when PRD content, framework/capability selections, adapter routing, required verified
nodes, and complete verified-node sets agree. Use additional cases for other PRDs or adapters.
Compare failure counts, prompt characters, and elapsed time to identify regressions. Matching
checkpoints do not prove identical behavior; inspect the evidence and resulting app as well.
Missing telemetry or an empty verified-node set fails the comparison.

After a failure, run `./.agents/bin/ai propose-lessons --project .`. This groups local failure
records by phase and failure class into `.ai/learning/proposals.json`; it does not alter agent
instructions. Review the evidence, then explicitly approve a concise corrective instruction:

```bash
./.agents/bin/ai approve-lesson --project . \
  --proposal LESSON-<id> \
  --guidance "Check the backend verification contract before retrying."
```

Only approved guidance appears in later prompts for the matching phase (up to three lessons).
It is advisory and cannot override the PRD or verification gate. Do not approve secrets, log
fragments, or untested fixes. The workflow never edits shared skills or rules automatically; a
proven reusable fix should be reviewed and committed to the appropriate repository separately.

## Recommended command order

With an idea but no requirements file, use:

```text
setup-workflow "<workflow-git-url>"
    -> reopen Codex
    -> $create-requirements
    -> review REQUIREMENTS.md and request changes until approved
    -> $generate-prd --requirements REQUIREMENTS.md
    -> $prepare-project-docs --requirements REQUIREMENTS.md
    -> $start-build
```

With an existing PRD or other project-document drafts, use:

```text
setup-workflow "<workflow-git-url>"
    -> reopen Codex
    -> $prepare-project-docs
    -> $start-build
```

With an existing approved requirements file, use:

```text
setup-workflow "<workflow-git-url>"
    -> reopen Codex
    -> $generate-prd --requirements REQUIREMENTS.md
    -> $prepare-project-docs --requirements REQUIREMENTS.md
    -> $start-build
```

For deliberate web/mobile stage-by-stage execution, use:

```text
$prepare-project-docs         # generates missing and completes user-written documents
    -> $start-backend         # when web/mobile needs an API
    -> $start-design
    -> $start-generatehtml
    -> $start-frontend and/or $start-mobile
       (design synchronization runs automatically)
    -> $start-integration
    -> $start-testing
    -> $start-deployment      # only when AWS preparation is required
    -> $start-delivery
```

For a local Python deliverable, declare `Desktop framework: Python Desktop` for a GUI and/or
`Python package: library|CLI|both` for a standalone distribution. Then use
`$prepare-project-docs -> $start-build`; the one-shot command runs the selected desktop phase and
skips unneeded backend or UI-design phases. `$start-desktop` stops after that phase if you want a
smaller checkpoint.

Afterward, use `$workflow-status` or `$resume-build` for recovery, `$sync-design` for an explicit
design recheck, `$resolve-token` for a scoped change, and the deployment operation skills only for
explicitly authorized live AWS work.

## All available skills

| Skill | Purpose | Normal stopping point or effect |
|---|---|---|
| `$create-requirements` | Turn an idea into a requirements source and revise it with the user | Reviewed `REQUIREMENTS.md` |
| `$prepare-project-docs` | Generate/audit all project specifications | Five consistent READY documents |
| `$generate-prd` | Convert requirements into a validated PRD | Ready `PRD.md` |
| `$start-design` | Create the design specification | Design specification |
| `$start-generatehtml` | Generate and approve static HTML | Approved HTML |
| `$start-frontend` | Build React or Next.js | Frontend gate |
| `$start-mobile` | Build Flutter for Android and iOS | Mobile gate |
| `$start-desktop` | Build a PySide6 desktop app, a standalone Python package, or both | Desktop gate |
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

## Requirements intake

### `$create-requirements`

Describe the project idea in ordinary language. Add preferred frameworks, platforms, users, or
constraints if known. The skill asks only material missing product questions, writes
`REQUIREMENTS.md`, and returns it for review. Request changes until it matches the intended
product. The draft includes functional (`FR`), business-rule (`BR`), nonfunctional (`NFR`),
structural (`SR`), and acceptance (`AC`) registers, with each in-scope `FR` linked to an `AC`.
It proposes a few relevant improvements and lets you accept, change, defer, or reject them without
silently adding features to the first release.
It stops after requirements approval. Run `$generate-prd --requirements REQUIREMENTS.md` to
create only the PRD, then `$prepare-project-docs --requirements REQUIREMENTS.md` to complete and
validate all five documents. If you want all five in one document step, invoke
`$prepare-project-docs` directly. Successful document preparation selects the required packs.

## Project document preparation

### `$prepare-project-docs`

```text
$prepare-project-docs [--requirements <path>] [--project-adapter <provider>] [--answer <QNNN=answer>]...
./.agents/bin/ai prepare-project-docs --project . [--requirements <path>] \
  --adapter codex [--answer <QNNN=answer>]...
```

| Flag | Value | Default | Meaning |
|---|---|---|---|
| `--project` | project directory | `.` | Target project root. |
| `--requirements` | in-project path | auto-discovered | Optional requirements source. |
| `--answer` | `QUESTION_ID=answer` | none | Answer every question in the active batch. Repeat once per answer. |
| `--adapter` | `codex` | `codex` | Execution adapter. |

The command discovers and audits `PRD.md`, `TRD.md`, `UI_UX_SPEC.md`,
`BACKEND_SPEC.md`, and `DELIVERY_SPEC.md` at the project root or under `docs/`.
Missing documents are generated. User-written documents are preserved until all
required answers are available, then every affected document is updated together.
Questions always use ordinary product language and arrive in batches of one to five;
large products may need multiple rounds. Technical implementation details are written
by the architect as visible assumptions. A hash-bound manifest under
`.ai/project-documents/` makes later build commands stop if any validated document is
changed or removed. Credential values block processing.

## PRD-only generation

### `$generate-prd`

```text
$generate-prd --requirements <path> [--output <path>] [--project-adapter <provider>] [--answer <QNNN=answer>]...
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

This compatibility command creates only `PRD.md`; continue with
`$prepare-project-docs --requirements <path>` before design. It stops with `NEEDS_INPUT` only when user-owned product, access, privacy, legal, budget, or
release decisions are missing. In Codex chat, questions are short and nontechnical, include simple
choices and a recommended answer, and can be answered naturally. Reply `use the recommended defaults`
to accept every displayed recommendation; Codex maps the response to the internal `--answer` flags.
Reversible implementation details are recorded as architect assumptions instead of being asked.
Actual credentials are blocked; use variable names and placeholders only. Skip this command when a
validated `PRD.md` already exists.

The generated capability matrix always records `RAG: Required` or `RAG: Not required`. When RAG is
required, intake also resolves source formats and retention, source ACLs, ingestion/versioning,
embedding and provider policy, hybrid retrieval, citations/abstention, and measurable quality,
latency, security, and cost gates. `$start-build` activates `rag` automatically; there is no RAG
framework flag and no separate RAG application command.

It also records `Web scraping: Required` or `Web scraping: Not required`. When required, intake asks
only for missing authorized websites/page areas, information to collect, login ownership, and desired
freshness. The architect supplies conservative navigation, limits, retry, storage, selector, and test
defaults. `$start-build` then loads `webscraping` only for requirements, relevant backend/integration
work, and independent testing. It never creates a separate scraper application or loads scraping
guidance for unrelated features.

Generated site adapters store approved selector routes as versioned YAML: URL/page state, window,
nested iframe chain, open shadow-root chain, reveal actions, primary ID/semantic/CSS/XPath selector,
fallbacks, transforms, validation and structural fingerprint. Fixture verification is the default;
live discovery or smoke testing requires an explicitly approved domain/account/page scope.

## Shared flags for start and resume skills

The following flags are accepted by `$start-design`, `$start-generatehtml`, `$start-frontend`,
`$start-mobile`, `$start-desktop`, `$start-backend`, `$start-integration`, `$start-testing`, `$start-deployment`,
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
| `--desktop` | `python` or `pyside6` | `unknown` | GUI desktop application selection. |
| `--python-package` | `library`, `cli`, or `both` | `unknown` | Standalone, no-GUI Python package selection. |
| `--backend` | `django-drf`, `fastapi`, or `unknown` | `unknown` | Backend selection. Do not explicitly pass `unknown` when the requested stage requires backend. |
| `--deployment` | `aws` or `unknown` | `unknown` | Deployment selection. Pass `aws` only to `$start-deployment`; complete-build commands reject it. |
| `--adapter` | `codex` | `codex` | Execution adapter. |
| `--commit-verified` | no value | off | Commit independently verified feature changes. Use only with explicit authorization. |
| `--push` | no value | off | Push verified commits from the current workflow branch. Use only with explicit authorization. |
| `--remaining` | no value | already enabled | Compatibility flag; commands already resume only remaining work. |
| `--approve-html` | no value | off | Deprecated compatibility flag; approval now follows independent verification automatically. |

Frameworks explicitly declared in the PRD take precedence and do not need to be repeated. Select
at least one deliverable: web, mobile, desktop GUI, or standalone Python package.
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
before approved HTML or application source. API contracts are first reconciled from the PRD, TRD,
and backend/data specification. Design then receives the PRD, TRD, UI/UX specification, normalized
requirements, and those API contracts. This standalone stage currently requires a selected backend;
for a local desktop-only product, use `$start-build` or `$start-desktop` instead.

### `$start-generatehtml`

```text
$start-generatehtml [shared start flags]
./.agents/bin/ai start-generatehtml --project . --adapter codex [shared start flags]
```

Runs missing design prerequisites, generates or validates approved static HTML, and stops before
frontend or mobile implementation. This standalone stage currently requires a selected backend;
package-only builds skip it.

Generation, independent verification, and approval complete in the same invocation.
No user HTML review or second approval command is required. After verification passes,
the orchestrator checks the source hashes and promotes the draft to `HTML/approved/`.
When browser automation is unavailable, the workflow records that limitation and defers rendered
accessibility and visual proof to frontend/mobile design synchronization. Supplied HTML,
screenshots, and design files still require rendered comparison.

### `$start-frontend`

```text
$start-frontend --frontend <react|nextjs> [shared start flags]
./.agents/bin/ai start-frontend --project . --adapter codex \
  --frontend <react|nextjs> [shared start flags]
```

Builds the selected web frontend from approved HTML, runs pixel/semantic design synchronization and
independent frontend verification, then stops before backend work.

Before feature work, the workflow creates an executable framework foundation and a typed API
client from an interim OpenAPI contract based on the specifications. Client tests use fixtures;
backend-generated OpenAPI and live integration are checked in their later phases. The phase plan
under `.ai/phase-plans/frontend.json` contains only relevant tasks in dependency order.
Blocked implementation evidence stops the phase immediately and cannot satisfy a prerequisite.

### `$start-mobile`

```text
$start-mobile --mobile flutter [shared start flags]
./.agents/bin/ai start-mobile --project . --adapter codex \
  --mobile flutter [shared start flags]
```

Builds Flutter for Android and iOS, runs design synchronization and independent mobile verification,
then stops after the mobile gate.

### `$start-desktop`

```text
$start-desktop [--desktop python] [--python-package <library|cli|both>] [shared start flags]
./.agents/bin/ai start-desktop --project . --adapter codex \
  --python-package cli [shared start flags]
```

Builds whichever deliverables are selected. `Desktop framework: Python Desktop` creates an
installable PySide6 GUI under `apps/desktop/`. `Python package: library`, `CLI`, or `both` creates a
separate importable/command-line distribution under `packages/python/`, with no Qt requirement.
Declare both to build both in one run. The workflow checks wheel and source distributions plus
isolated installation; native GUI bundles require evidence from each target operating system.

### `$start-backend`

```text
$start-backend --backend <django-drf|fastapi> [--verification-only | --full-revalidation] [shared start flags]
./.agents/bin/ai start-backend --project . --adapter codex \
  --backend <django-drf|fastapi> [--verification-only | --full-revalidation] [shared start flags]
```

Builds and verifies the PostgreSQL backend before client implementation, then stops at the backend
gate. `--verification-only` reruns the final backend matrix from existing verified slices;
`--full-revalidation` deliberately reopens every backend slice and the final matrix.

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
$start-build --project . --prd docs/PRD.md --project-id customer-platform \
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
It also includes `progress`: an overall percentage and per-phase breakdown based on
current verified node artifacts and accepted phase gates. Run it while a build is active
for the latest saved checkpoint. The percentage is unavailable until tasks are planned;
it can decrease if inputs invalidate an earlier checkpoint. It is not a time estimate.

### `$resume-build`

```text
$resume-build [shared start flags]
./.agents/bin/ai resume-build --project . --adapter codex [shared start flags]
```

Resumes only invalid or incomplete nodes from durable checkpoints. Preserve saved framework and Git
choices. Its result reports the overall non-deployment percentage, as does `$start-build`.
Individual stage commands report only their requested stage's percentage. `--push` remains opt-in.

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
| `--token` | supported `TOKEN.md` path | required | Exactly one frontend, mobile, desktop-GUI, or backend token. |
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
