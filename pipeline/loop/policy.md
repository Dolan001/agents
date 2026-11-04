# Bounded recovery policy

This workflow does not use an infinite improvement loop. A failed node has a bounded
normal retry budget. After that, an actionable project failure may receive one
separately leased recovery pass. The original node must rerun its checks; recovery
evidence is not a gate pass. An unchanged external blocker receives no extra attempt.
Repeated identical failures remain blocked evidence. Verified nodes are cached until
a declared input changes.

A pure reusable-workflow defect may receive one separately scoped repository repair.
Its branch must pass repository tests before publication as a PR. The original command
may restart once against that tested local branch; the same defect cannot trigger an
unbounded restart chain. External access or verification failure preserves the
project checkpoint.
