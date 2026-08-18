---
name: sync-design
description: Compare approved HTML with selected React, Next.js, and Flutter implementations, repair meaningful visual, responsive, state, and accessibility drift, and require independent verification. Use when the user invokes sync-design, asks to compare application design with HTML, or asks to fix implementation design differences.
---

# Synchronize application design

1. Require initialized workflow state, non-empty `HTML/approved/`, and at least one selected,
   implemented web or mobile target.
2. Invoke the deterministic workflow entry point:

   ```text
   ./.agents/bin/ai sync-design --project . --adapter codex
   ```

   Use `--target frontend`, `--target mobile`, or the default `all`. Use `--check-only` to prohibit
   application edits. Add `--allow-baseline-update` only when the user explicitly authorizes changing
   approved HTML.
3. Read `references/fidelity-protocol.md` completely. Load only the selected React, Next.js, or
   Flutter implementation and verification guidance routed by the workflow.
4. Render approved HTML and the application with identical deterministic settings for every case.
   Run `./.agents/bin/ai compare-images` to generate each diff PNG and metrics JSON. Default to zero
   tolerance and zero changed pixels; never hand-author either generated artifact.
5. Compare deterministic cases, classify meaningful drift, and write the manifest, comparison, and
   repair plan under `.ai/evidence/design-fidelity/<target>/` before editing.
6. In repair mode, change only allowed target, test, and deliberately shared UI paths. Fix shared
   tokens and primitives before route-local symptoms. Re-render only affected cases after each pass.
7. Require a different selected framework verifier to recompute every pixel case and write final
   verification evidence. Pixel equality is mandatory but does not replace semantic, responsive,
   state, native-platform, or accessibility verification. Never
   approve missing captures, failed commands, unresolved blocker/major/minor drift, or an unavailable
   required Android/iOS comparison.

The PRD outranks visual evidence for behavior. Approved HTML outranks screenshots for presentation.
Do not copy unsafe HTML behavior, erase native Flutter conventions, or replace a baseline merely to
make a visual test pass. Stop after the bounded retry budget and report remaining localized evidence.
