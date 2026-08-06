# Bootstrap scope

Bootstrap may create workflow state and discovery artifacts. It must not create
`apps/`, `packages/`, `tests/`, or infrastructure source. Brownfield inspection is
read-only with respect to existing application code.
