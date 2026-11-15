# Design scope

Preserve received assets in `HTML/source/`. Generate reviewable static HTML in
`HTML/generated/`; promote only an accepted baseline to `HTML/approved/`. Do not
start React or Next.js implementation without an approved HTML baseline unless the
task contract records explicit user authorization.

Each approved HTML comparison page must show one deterministic route state, marked
with `data-design-state` on `html` or `body`. Mark explicit screen-state regions
with `data-design-screen-state`; only the selected state may be visible in a capture. Keep alternate
loading, empty, success, validation, authorization, and error states in separate
comparison pages or design documentation outside `HTML/approved/`. The independent
HTML verifier must check rendered state visibility before approval. A page that
displays an all-states gallery is not a valid frontend pixel baseline.
