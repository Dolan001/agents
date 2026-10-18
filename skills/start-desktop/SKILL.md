---
name: start-desktop
description: Build and independently verify a selected PySide6 desktop application, a standalone no-GUI Python library or CLI package, or both, stopping after the desktop gate. Use when the user invokes start-desktop or requests either Python deliverable.
---

# Start Python deliverables

Read `.agents/commands/references/start-command-contract.md`. Require the PRD to declare at least
one of `Desktop framework: Python Desktop` and `Python package: library|CLI|both`. Invoke
`./.agents/bin/ai start-desktop` with only already-resolved framework flags; declarations in the
PRD need not be repeated. A local GUI app or standalone package does not require a backend.
Run missing requirements and selected design prerequisites, implement every projected slice, and
stop after independent verification.

For a GUI selection, build `apps/desktop/` with a `[project.gui-scripts]` launcher and truthful
native packaging readiness. For a package selection, build a separate `packages/python/` project
with an importable API for library mode, `[project.scripts]` for CLI mode, or both. Never add a GUI
dependency to the standalone package by default. Verify wheel and sdist builds and isolated
installation for every selected deliverable. Do not add `--push` unless explicitly requested.
