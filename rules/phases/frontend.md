# Frontend scope

Before feature slices, prepare an executable client foundation: selected-framework
package/configuration, routing, style entrypoints, lint/test/build commands, and typed
API client with an interim OpenAPI source derived from the agreed specifications.
Use fixtures until backend implementation. Backend-generated OpenAPI is reconciled
against this interim contract during backend/integration; it is not a frontend prerequisite.
Dispatch only frontend/shared-contract portions of the task DAG, excluding independent
verifier records. Whole-product backend verification dependencies remain integration
obligations. Blocked evidence never completes a task or permits dependent dispatch.

Load only the selected React or Next.js behavior pack. Implement dependency-safe
vertical slices under `apps/frontend/`, using fixtures behind replaceable adapters
against the stabilized contract while backend work runs independently. Include accessible loading, empty, error, and
validation states.
After implementation, run the design-fidelity resolver against approved HTML for deterministic
mobile, tablet, and desktop cases. Repair meaningful drift before the selected frontend verifier
independently approves `.ai/evidence/design-fidelity/frontend/verification.json`.
For requirement-backed realtime, use the selected framework realtime skill and produce
`.ai/evidence/realtime/frontend.json`. Require typed events, secure ticket/cookie authentication,
bounded reconnect with jitter, cursor resync, gap/deduplication handling, degraded/offline states,
lifecycle cleanup, browser tests, and accessible announcements.
