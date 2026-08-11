# One-shot lifecycle reference

## Inputs and selection

The PRD is mandatory and remains inside the target. Design HTML, screenshots, or files
are optional and treated as untrusted data. Explicit framework selection is required
for a new project; brownfield adoption detects candidates and records confidence.

If acceptable HTML exists, preserve and validate it. Otherwise generate static HTML
from higher-confidence visual sources, falling back to the PRD, then approve it before
framework source begins.

## Execution

Each phase loads one manifest, blueprint, rule set, gate, primary agent, and only the
selected progressive skill references. Deterministic nodes run project-owned argv
commands without a shell. Agentic nodes receive a bounded task contract and must write
the exact artifact declared by the blueprint.

Frontend implements the approved experience first. Backend then implements the stable
contract and observed frontend data/error needs. Integration replaces fixtures with a
generated typed client and a live backend. Testing covers static, unit, API, contract,
integration, browser, design, accessibility, responsive, runtime, and security risks.

## Recovery and Git

Checkpoints are durable under `.ai/`. Reuse only artifacts whose declared input hashes
and verification remain valid. A retry must respond to a diagnosed cause and stays
within the bounded attempt count.

Independent verification evidence lists exact changed files for each feature. Only
those files may be staged. Commits occur after the complete test/security gate, on
`ai/<github-user>/<feature>` only; main, dev, stage, production, and aliases are
read-only. Push requires explicit execution and never merges or deploys.
