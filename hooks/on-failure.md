# On failure

For every error occurrence, invoke the deterministic build-issue tracker before retry,
return, or escalation. Persist secret-safe evidence inside the target project:

- `.ai/issues/events.jsonl` is the append-only history of every observed error.
- `.ai/issues/issues.json` groups repeated errors by fingerprint and preserves counts.
- `.ai/issues/summary.json` provides open, blocked, resolved, and occurrence totals.
- `.ai/issues/REPORT.md` is the human-readable backlog for later resolution.

Record the command, phase/node/feature when known, attempt, classification,
retryability, concise message, and evidence paths. Never store credentials, full logs,
PRD contents, prompts, or command arguments containing secrets. Mark a tracked issue
resolved only after a later attempt or resumed execution passes its original command
or verification contract; never delete error history. Invalidate affected context and
dependents only. Retry only with
a changed hypothesis or input, at most twice. Failure tracking must not hide the
original error when storage itself is unavailable.
