# Agent Advocate

Read [CLAUDE.md](CLAUDE.md) for project instructions and [plan.md](plan.md) for the current build status and acceptance contract.

This public repository owns its five product skills in `.agents/skills/`. They are created in Step 2 and discovered by Codex from this project. They are not entries in an external skill catalog. Keep runtime data outside all source repositories. Do not infer completion from the existence of a skill or a green unit test alone.

Use `assign-advocate` as the reusable coordinator entry point for explicitly named work. It routes to the other four skills as the run progresses; it does not replace the build's review gates.
