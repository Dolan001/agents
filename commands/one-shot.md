# `ai one-shot`

Run the complete workflow against a separate target repository:

```text
bootstrap → requirements/contracts → approved HTML → frontend → backend
          → integration → testing/security → delivery
```

The target may be empty or brownfield. The workflow repository remains the control
plane; selected framework repositories are read as behavior packs. Agents create or
complete the monorepo only inside the target.

Accept repeatable optional `--html` and `--screenshot` paths inside the target. Record
the deterministic input route in `.ai/design-inputs.json`: supplied HTML is validated;
otherwise screenshots generate HTML with PRD guidance; otherwise the PRD generates
HTML. Never start frontend work before approved HTML passes the design gate.

Dry-run is the default. With `--execute`, invoke the selected Claude, OpenCode, or
Codex adapter without a shell. Every node must create its declared artifact and every
phase must pass its evidence gate. Stop at failure and resume from the last verified
node.

After the complete testing/security gate, `--commit-verified` stages only paths listed
in independent feature evidence. `--push` pushes the resulting commits to the current
safe `ai/<github-user>/<feature>` branch. Protected branches are never writable.

Reuse verified nodes when declared inputs are unchanged. Load bounded context and only
the selected framework packs. Use fast checks during implementation and affected full
gates before independent verification.
