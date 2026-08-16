---
name: generate-prd
description: Convert a software requirements file or user-provided software requirements into a validated build-ready PRD, asking only for material missing decisions. Use when the user invokes generate-prd, asks to create a PRD, or wants requirements prepared for start-build.
---

# Generate a build-ready PRD

Accept a requirements path inside the project. If the user supplied requirements only in the
conversation, create `REQUIREMENTS.md` containing the non-secret requirements and obvious credential
placeholders; never write a supplied credential value. Then invoke:

```text
./.agents/bin/ai generate-prd --project . --requirements <path> --output PRD.md --adapter codex
```

If the result is `CREDENTIALS_BLOCKED`, report the finding locations without values. Tell the user to
remove and rotate exposed values, keep only names/placeholders, and stop. If it is `NEEDS_INPUT`, ask
the returned questions together and stop. After the user answers, resume with one
`--answer <QUESTION_ID=answer>` argument per answer; never invent a missing business or architecture
decision.

On `READY`, report `PRD.md`, its explicit framework selections, recorded assumptions, and the exact
next command `$start-build --prd PRD.md`. Do not start the build unless the user separately requests
it. Durable sanitized intake state lives under `.ai/prd-intake/`; do not copy the original raw
requirements or credential values there.
