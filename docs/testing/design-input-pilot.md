# Design-input and monorepo pilot

Last run: 2026-08-12

The automated pilot executes the complete eight-phase state machine in isolated empty
Git repositories with a controlled adapter. The adapter satisfies the same artifact
contracts as a real Codex process, allowing orchestration,
sequencing, input routing, gates, and filesystem results to be tested deterministically
without consuming model tokens.

Covered scenarios:

| Input | Recorded mode | Frameworks | Expected route |
|---|---|---|---|
| PRD + HTML | `html_supplied` | Next.js + Django DRF | preserve, validate, approve HTML |
| PRD + screenshot | `screenshot_supplied` | React + FastAPI | generate HTML from visual evidence and PRD |
| PRD only | `prd_only` | Next.js + FastAPI | generate HTML from PRD |

Every scenario must finish all phases and produce:

- the required root monorepo control files and directory layout;
- `HTML/approved/index.html`;
- the selected framework structure under `apps/frontend/`;
- the selected framework structure under `apps/backend/`;
- `packages/api-client/`;
- deterministic test-command results;
- independent feature and security evidence;
- delivery artifacts and `status: complete`.

The structure gate reads the selected pack's `rules/project-structure.json` and rejects
missing paths or file/directory type mismatches. Tests also verify HTML precedence when
HTML and screenshots coexist, safe feature-branch creation, dry-run non-mutation of
application paths, and fail-closed behavior for incomplete structures.

At the latest run, 17 workflow tests and 6 shared-foundation tests passed. The control
plane contains 8 sequential phases and 26 nodes, including 16 agentic nodes with
required output contracts. Installed adapter command shapes were checked against
Codex CLI 0.146.0-alpha.9.2.

This proves the workflow engine and contracts. It does not substitute for a real-model
acceptance pilot, because generated application quality, package installation, runtime
behavior, browser fidelity, and provider permissions depend on the chosen adapter and
the supplied PRD/design. Run one reviewed project without `--push` before enabling
automated GitHub delivery.
