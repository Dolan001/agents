# Frontend scope

Before feature slices, require the verified backend and its generated OpenAPI, then prepare an
executable client foundation: selected-framework package/configuration, routing, style entrypoints,
lint/test/build commands, and a generated typed API client.
Dispatch only frontend/shared-contract portions of the task DAG, excluding independent
verifier records. Whole-product backend verification dependencies remain integration
obligations. Blocked evidence never completes a task or permits dependent dispatch.

Load only the selected React or Next.js behavior pack. Implement dependency-safe
vertical slices under `apps/frontend/`. Implement each slice against the running backend and
disposable PostgreSQL test data. Fixtures may support isolated unit tests but cannot satisfy the
phase gate. Include accessible loading, empty, error, and validation states. Independently verify
authenticated success, negative, authorization, persistence round-trip, and error-mapping journeys,
then write `.ai/evidence/client-integration/frontend.json` against the current backend evidence and
OpenAPI hashes.
After implementation, run the design-fidelity resolver against approved HTML for deterministic
mobile, tablet, and desktop cases. Repair meaningful drift before the selected frontend verifier
independently approves `.ai/evidence/design-fidelity/frontend/verification.json`.
For requirement-backed realtime, use the selected framework realtime skill and produce
`.ai/evidence/realtime/frontend.json`. Require typed events, secure ticket/cookie authentication,
bounded reconnect with jitter, cursor resync, gap/deduplication handling, degraded/offline states,
lifecycle cleanup, browser tests, and accessible announcements.
