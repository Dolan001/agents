# Start commands

Add this repository directly at Codex's canonical project path:

```bash
git submodule add -b dev https://github.com/Dolan001/ai_workflow.git .agents
git submodule update --init --recursive
```

The `.agents` directory is the tracked `ai_workflow` submodule itself, not a generated
copy. Codex discovers `.agents/skills` directly. Commit `.gitmodules` and the `.agents`
gitlink to the real project so every developer receives the same pinned workflow with
`git clone --recurse-submodules`. No setup or skill-copy command is required. Runtime
`.ai` state remains separate and appears only when development starts.

| Entrypoint | Result | Monorepo created? |
|---|---|---:|
| `start-design` | Design specification only | No |
| `start-generatehtml` | Verified approved HTML | No |
| `start-frontend` | Prerequisites plus selected frontend | Yes |
| `start-backend` | Prerequisites plus selected backend | Yes |
| `start-integration` | Typed client and frontend/backend integration | Yes |
| `start-testing` | Full independent test and security gates | Yes |
| `start-delivery` | Release-ready evidence; optional explicit Git delivery | Yes |
| `start-build` | Every missing phase through delivery | Yes |
| `resume-build` | Continue from unchanged verified checkpoints | As needed |
| `workflow-status` | Read-only progress and recovery report | No change |

The PRD is required. Without `--prd`, the engine accepts exactly one of `docs/PRD.md`,
`PRD.md`, `docs/prd.md`, or `prd.md`. HTML and screenshots are optional repeatable
arguments. The engine prioritizes supplied HTML, otherwise screenshots, otherwise PRD
generation. The engine automatically uses explicit PRD declarations for React,
Next.js, Django REST Framework, or FastAPI. Codex asks only for a side that is still
missing. Unsupported, conflicting, or multiple declarations fail before build work.

Examples:

```text
$start-design --github-user dolan
$start-generatehtml
$start-frontend --frontend nextjs
$start-build
$workflow-status
$resume-build
```

No start command pushes by default. Add `--commit-verified` or `--push` only when that
Git mutation is explicitly intended; protected branches remain rejected.

For a scoped post-build bug or change, create `frontend/TKN001/TOKEN.md` or
`backend/TKN001/TOKEN.md`, optionally add consecutive sibling `currentN` and
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
