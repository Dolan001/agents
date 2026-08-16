# Deployment scope

Run only after testing and security gates pass. If AWS is selected, inspect the target, design the
architecture, generate target-owned OpenTofu-compatible infrastructure, GitHub Actions, monitoring,
and runbooks, then verify them independently. This phase must not call AWS APIs, assume credentials,
apply infrastructure, deploy applications, change DNS, or mutate any environment. Live deployment
uses separate explicit environment commands.

Generate a complete root `.env.example` for optional local AWS authentication. Explicit live
deployment commands may load only the documented AWS variables from `.env` after verifying that it
is ignored and untracked. Redact all credential values. GitHub Actions must use OIDC and deployed
workloads must use IAM roles and Secrets Manager.
