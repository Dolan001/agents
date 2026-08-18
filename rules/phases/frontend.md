# Frontend scope

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
