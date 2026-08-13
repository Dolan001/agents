---
name: start-frontend
description: Run all missing prerequisites and build the selected React or Next.js frontend from approved HTML, then stop before backend work. Use when the user invokes start-frontend.
---

# Start frontend

Read `.agents/commands/references/start-command-contract.md`, resolve the frontend choice,
then invoke `./.agents/bin/ai start-frontend` with `--adapter codex`. Stop after the
frontend gate.
