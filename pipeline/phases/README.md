# Phase instructions

The executable phase graph lives in `config/pipeline.json`. Each phase is composed
from four connected artifacts:

1. `pipeline/manifests/<phase>.json` selects prerequisites, agents, skills, inputs,
   outputs, rules, and scope.
2. `blueprints/<phase>.json` defines deterministic and agentic nodes.
3. `rules/phases/<phase>.md` supplies phase-specific behavioral constraints.
4. `gates/contracts/<phase>.json` defines evidence required to advance.

The workflow loads those artifacts at runtime. Framework-specific structure and
implementation guidance comes only from the selected root-level behavior repository.

`phase_order` is the stable reporting order. `execution_groups` is the runtime DAG:
frontend and backend may run together after requirements/contracts and design pass,
but only with non-overlapping path leases. Integration waits for both.
