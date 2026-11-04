# Bounded recovery policy

This workflow does not use an infinite improvement loop. A failed node has a bounded
normal retry budget. After that, an actionable project failure may receive one
separately leased recovery pass. The original node must rerun its checks; recovery
evidence is not a gate pass. An unchanged external blocker receives no extra attempt.
Repeated identical failures remain blocked evidence. Verified nodes are cached until
a declared input changes.
