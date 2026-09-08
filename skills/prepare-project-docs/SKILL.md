---
name: prepare-project-docs
description: Generate or complete the full PRD, technical, UI/UX, backend/data, and delivery document set from requirements and user-written drafts. Use when the user invokes prepare-project-docs or wants project documents audited before design/build.
---

# Prepare all project documents

Use the optional requirements path when supplied; otherwise let the CLI discover
`REQUIREMENTS.md` and canonical drafts:

```text
./.agents/bin/ai prepare-project-docs --project . [--requirements <path>] --adapter codex
```

The command audits every existing `PRD.md`, `TRD.md`, `UI_UX_SPEC.md`,
`BACKEND_SPEC.md`, and `DELIVERY_SPEC.md` together and generates missing documents.

If it returns `CREDENTIALS_BLOCKED`, report locations without values, tell the user to
remove and rotate exposed credentials, and stop. If it returns `NEEDS_INPUT`, present
all returned questions as one short numbered conversation. Questions must remain in
plain everyday language even when the source documents are technical. Show choices,
mark the recommendation, and allow natural answers or “use the recommended defaults.”
Map the response to one `--answer <QNNN=answer>` per active question. There will be one
to five questions per round; large projects may require multiple rounds.

Do not ask the user to choose low-level implementation details. On `READY`, report the
five validated document paths, material changes, assumptions, selected packs, and the
next command `$start-design --prd <actual PRD path>`. Do not start design or build
unless separately requested.
