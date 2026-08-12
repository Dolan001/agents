# Start commands

Install project-local entrypoints once after cloning or updating the workflow submodule:

```bash
./ai_workflow/bin/ai install-commands --project .
```

Restart or reopen the agent client so it refreshes project command discovery. Claude
and OpenCode use `/start-build`; Codex loads the same behavior as the project skill
`$start-build`. Direct CLI commands are always available.

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
generation. Frontend selection is required only when execution reaches frontend;
backend selection is required only when it reaches backend.

Examples:

```text
/start-design --github-user dolan
/start-generatehtml
/start-frontend --frontend nextjs
/start-build --frontend nextjs --backend django-drf --github-user dolan
/workflow-status
/resume-build
```

No start command pushes by default. Add `--commit-verified` or `--push` only when that
Git mutation is explicitly intended; protected branches remain rejected.
