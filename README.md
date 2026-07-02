# Trackeroo

**Trackeroo** is a lightweight, self-hosted single-project task tracker: epics → tasks, configurable kanban swim lanes, dependencies, blockers, comments/annotations, PR/Slack links, plus an MCP server so AI agents can create and update tasks directly.

Packaged as a native macOS desktop app (Tauri) — the target use case is a single user on a single machine, with no remote access ever needed. See [`v2/README.md`](v2/README.md) for the product overview, quickstart, and how to build/run it.

> This repo previously held a Docker/web-app implementation (`v1/`) alongside this one; it's been retired since the target use case is single-machine, not self-hosted-server. `v2/` — historically the second implementation, now the only one — is left named as-is rather than flattened to the repo root.

## Worktrees

**Any work in this repo happens in a git worktree, never directly in `main`'s working tree.** `worktrees/` lives inside this checkout and is git-ignored:

```bash
git worktree add worktrees/<short-task-name> -b <branch-name>
cd worktrees/<short-task-name>
```

See `CLAUDE.md` for the full convention.

## Versioning

This repo uses git. The `main` branch (this checkout) is the mainline; all feature work happens in `worktrees/` as git worktrees, never directly against `main`.
