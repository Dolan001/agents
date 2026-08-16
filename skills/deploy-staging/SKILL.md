---
name: deploy-staging
description: Deploy the verified immutable release to AWS staging through the project-owned deployment command. Use only when the user explicitly invokes deploy-staging after deployment readiness passes.
---

# Deploy AWS staging

First run `./.agents/bin/ai deploy-staging --project .` and report readiness. Do not mutate AWS from
that dry run. Only when the user explicitly authorizes the staging deployment, invoke it again with
`--execute`. The project-owned `deploy-staging` argv group must produce verified staging evidence;
stop on failure and never continue automatically to production.
