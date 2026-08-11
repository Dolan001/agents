# `ai one-shot`

Run the complete workflow against a separate target repository:

```text
bootstrap → requirements/contracts → design → (frontend ∥ backend) → integration → testing → delivery
```

The target may be empty or brownfield. The workflow repository remains the control
plane; selected framework repositories are read as behavior packs. Agents create or
complete the monorepo only inside the target.

Execution must stop at a failed gate and resume from the last verified node. A run
never pushes remotely unless the user separately invokes `ai push --execute`.

Reuse verified nodes when declared inputs are unchanged. Load bounded context and only
the selected framework packs. Use fast checks during implementation and affected full
gates before independent verification.
