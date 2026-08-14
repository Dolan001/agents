# Design-input and monorepo pilot

Last run: 2026-08-12

The automated pilot executes the complete nine-phase state machine in isolated empty
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
- the selected Flutter structure under `apps/mobile/` when mobile is enabled;
- the selected framework structure under `apps/backend/`;
- `packages/api-client/`;
- deterministic test-command results;
- independent feature and security evidence;
- delivery artifacts and `status: complete`.

The structure gate reads the selected pack's `rules/project-structure.json` and rejects
missing paths or file/directory type mismatches. Tests also verify HTML precedence when
HTML and screenshots coexist, safe feature-branch creation, dry-run non-mutation of
application paths, and fail-closed behavior for incomplete structures.

The current control plane contains 9 sequential phases and 31 nodes, including 20
agentic nodes with required output contracts. Flutter-only and web-plus-Flutter routes
are covered by deterministic workflow tests.

This proves the workflow engine and contracts. It does not substitute for a real-model
acceptance pilot, because generated application quality, package installation, runtime
behavior, browser fidelity, and provider permissions depend on the chosen adapter and
the supplied PRD/design. Run one reviewed project without `--push` before enabling
automated GitHub delivery.
