---
name: start-frontend
description: Build the selected React or Next.js frontend from existing verified HTML and integrate it with the verified live backend. Stop with recovery instructions if backend or HTML prerequisites are missing or stale. Use when the user invokes start-frontend.
---

# Start frontend

Read `.agents/commands/references/start-command-contract.md`, resolve the frontend and backend choices,
then invoke `./.agents/bin/ai start-frontend` with the explicitly selected adapter
(default `codex-reviewed`). After the backend and frontend gates pass, the CLI starts
the project locally on available loopback ports. Report the `local_preview.url` from
the CLI result so the user can open it in a browser. Stop after the frontend gate.

This command does not generate or repair HTML. If the prerequisite is missing or
stale, report the `start-generatehtml` recovery command and stop. The user may review
the generated HTML before starting frontend implementation, but personal review is
optional. Do not automatically invoke HTML generation on their behalf. Use
`start-build` when the user requests the combined lifecycle.

Generate the typed client from current OpenAPI and require live authenticated, success, negative,
authorization, persistence, and error-mapping journeys. Fixtures cannot satisfy the frontend gate.
If a frontend slice finds an implementable backend API gap, let the CLI perform its bounded
separately leased backend contract repair, full backend test matrix and independent verification,
then retry the same frontend slice in this invocation. Do not edit backend files under a frontend
lease or declare the frontend complete from repair evidence alone. Permission, quota, and
unavailable-service failures still require a truthful stop.
