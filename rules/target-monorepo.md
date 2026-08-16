# Target monorepo contract

Create application source only in the user's target repository. Preserve compatible
brownfield conventions; for a new target, establish the paths declared in
`config/target-monorepo.json` before frontend implementation.

Root `README.md` documents local development and verification. Root `.gitignore`
excludes secrets, dependencies, caches, builds, test artifacts that are not evidence,
and editor/OS debris. `.env.example` contains names and safe examples only. When AWS deployment is
selected, it includes `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, and optional
`AWS_SESSION_TOKEN` placeholders; the ignored, untracked `.env` may supply those values to explicit
local deployment commands.
`compose.yaml` coordinates the selected frontend, backend, database, and required local
dependencies without production secrets. `Makefile` provides thin, noninteractive
entry points to install, run, test, lint, build, and validate the complete system.

Framework application files remain under `apps/frontend` and `apps/backend`. Generated
API clients belong in `packages/api-client`; integration and browser suites belong in
the root `tests` areas. Do not copy application boilerplate from behavior repositories.
