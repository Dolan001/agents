# Deployment scope

Run only after testing and security gates pass. If AWS is selected, inspect the target, design the
architecture, generate target-owned OpenTofu-compatible infrastructure, GitHub Actions, monitoring,
and runbooks, then verify them independently. This phase must not call AWS APIs, assume credentials,
apply infrastructure, deploy applications, change DNS, or mutate any environment. Live deployment
uses separate explicit environment commands.
