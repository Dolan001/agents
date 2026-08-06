# One-shot delivery

Use when a required PRD should drive a new or brownfield full-stack delivery.

1. Establish the target boundary and initialize or adopt durable state.
2. Resolve exactly one frontend and one backend behavior pack.
3. Execute phases in `config/pipeline.json` order.
4. For each phase, load its manifest, rules, blueprint, and gate.
5. Give each agent a bounded task contract and path lease.
6. Persist node evidence before advancing.
7. Stop on gate failure; retry only within policy; resume from verified state.
8. Report gaps honestly and keep remote push opt-in.

Never create application source inside this repository or any behavior pack.
