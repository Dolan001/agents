# Bounded recovery policy

This workflow does not use an infinite improvement loop. A failed node may be retried
twice after failure classification and context invalidation. Repeated identical
failure becomes blocked evidence and is escalated. Verified nodes are cached until a
declared input changes.
