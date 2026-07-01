# Trackeroo

This repository holds versioned implementations of **Trackeroo**, a lightweight, self-hosted single-project task tracker (epics → tasks, configurable kanban swim lanes, dependencies, blockers, comments/annotations, PR/Slack links, plus an MCP server for AI agents).

## Implementations

- **[`v1/`](v1/README.md) — web app.** FastAPI + Svelte + SQLite, self-hosted via `docker compose up`, accessed through a browser. Complete, tested, fully working.
- **[`v2/`](v2/README.md) — Tauri desktop app.** A native macOS app wrapping the same backend as a bundled sidecar process, no Docker or browser involved. The active development target: the confirmed use case is a single user on a single machine with no remote access ever needed, which fits a native app better than a self-hosted server.

Each version is self-contained under its own top-level folder — its own backend/frontend/mcp copies, its own README and CLAUDE.md. Nothing is shared between them at the code level; a fix in one doesn't automatically apply to the other.

> `.github/workflows/` stays at the repo root (GitHub only discovers workflows there); the CI job paths are prefixed to point into `v1/` — v2 has no CI wiring yet.

## Worktrees

**Any work in this repo happens in a git worktree, never directly in `main`'s working tree.** `worktrees/` lives inside this checkout and is git-ignored:

```bash
git worktree add worktrees/<short-task-name> -b <branch-name>
cd worktrees/<short-task-name>
```

See `CLAUDE.md` for the full convention.

## Versioning

This repo uses git. The `main` branch (this checkout) is the mainline; all feature work happens in `worktrees/` as git worktrees, never directly against `main`.
