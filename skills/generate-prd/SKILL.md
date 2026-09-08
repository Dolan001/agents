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
remove and rotate exposed values, keep only names/placeholders, and stop. If it is `NEEDS_INPUT`,
present the returned questions as a short, numbered conversation for a nontechnical user. Show the
plain-language choices and mark the recommended answer. Do not expose CLI answer syntax or repeat
technical jargon. Tell the user they may answer naturally, choose an option, provide their own answer,
or say “use the recommended defaults.” Map their response to one `--answer
<QUESTION_ID=answer>` argument per active question. When they accept defaults, submit every question's
`recommended_answer`; never invent a missing user-owned decision.

Do not ask the user for model names, embedding dimensions, similarity algorithms, pagination,
retries, worker configuration, database tuning, browser/OS versions, or infrastructure topology.
Those are architect-owned assumptions unless the user supplied a constraint that affects product
behavior, privacy, legal obligations, or cost.

On `READY`, confirm the command also reconciled `.ai/selected-packs.json` and initialized every
framework/capability pack selected by the PRD. Report `PRD.md`, its explicit framework selections,
recorded assumptions, selected packs, and the exact next command `$prepare-project-docs
--requirements <path>` so the technical, UI/UX, backend/data, and delivery specifications are
completed before design. Do not start later work unless the user separately requests it. Durable sanitized intake state lives under
`.ai/prd-intake/`; do not copy the original raw requirements or credential values there.
