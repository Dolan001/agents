# Start commands

Add this repository directly at Codex's canonical project path:

```bash
git submodule add -b dev https://github.com/Dolan001/agents.git .agents
./.agents/bin/ai select-packs --project .
```

The `.agents` directory is the tracked `agents` submodule itself, not a generated
copy. Codex discovers `.agents/skills` directly. The selector initializes `base` plus only the
framework and capability packs justified by the PRD and explicit deployment request. It reports
missing framework choices without guessing. Commit `.gitmodules` and the `.agents` gitlink to the
real project; runtime `.ai/selected-packs.json` records the PRD hash, selected pins, missing packs,
and unused existing checkouts.

| Entrypoint | Result | Monorepo created? |
|---|---|---:|
| `start-design` | Design specification only | No |
| `start-generatehtml` | Verified approved HTML | No |
| `start-frontend` | Prerequisites plus selected frontend | Yes |
| `start-mobile` | Prerequisites plus Flutter Android/iOS app | Yes |
| `start-backend` | Prerequisites plus selected backend | Yes |
| `start-integration` | Typed web/mobile and backend integration | Yes |
| `start-testing` | Full independent test and security gates | Yes |
| `start-deployment` | AWS assets and readiness; no cloud mutation | Yes |
| `start-delivery` | Release-ready evidence; optional explicit Git delivery | Yes |
| `start-build` | Every non-deployment phase through application delivery | Yes |
| `resume-build` | Continue from unchanged verified checkpoints | As needed |
| `workflow-status` | Read-only progress and recovery report | No change |

The PRD is required. Without `--prd`, the engine accepts exactly one of `docs/PRD.md`,
`PRD.md`, `docs/prd.md`, or `prd.md`. HTML and screenshots are optional repeatable
arguments. The engine prioritizes supplied HTML, otherwise screenshots, otherwise PRD
generation. The engine automatically uses explicit PRD declarations for React,
Next.js, Flutter, Django REST Framework, or FastAPI. Complete delivery requires at
least one web/mobile client and one backend. Unsupported, conflicting, or multiple
declarations fail before build work.

`start-build`, `resume-build`, and legacy `one-shot` always skip deployment. An explicit
`Deployment provider: AWS` declaration is retained for a later `$start-deployment --deployment aws`
run; it never activates AWS work inside one-shot application development. Live operations remain
separate: `deploy-staging`, `deploy-production`, `deployment-status`, and `rollback-deployment`.

Examples:

```text
$start-design --github-user dolan
$start-generatehtml
$start-frontend --frontend nextjs
$start-mobile --mobile flutter
$start-deployment
$start-build
$workflow-status
$resume-build
```

No start command pushes by default. Add `--commit-verified` or `--push` only when that
Git mutation is explicitly intended; protected branches remain rejected.

For a scoped post-build bug or change, create `frontend/TKN001/TOKEN.md`,
`mobile/TKN001/TOKEN.md`, or `backend/TKN001/TOKEN.md`, optionally add consecutive sibling `currentN` and
`expectedN` PNG/JPEG/WebP images, and invoke:

```text
$resolve-token frontend/TKN001/TOKEN.md
```

The resolver validates the route and images, loads only the selected area and
framework behavior, diagnoses, and returns a plan without code changes. After the user
approves, the same command with `--approve` creates a token branch, implements,
verifies, commits, pushes, and opens a PR. The branch checked out during diagnosis is
always the PR base, regardless of its name; the resolver never pushes or merges that
base branch.
