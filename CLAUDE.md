# Trackeroo

This repo contains versioned implementations of Trackeroo, each self-contained under its own top-level folder:

- [`v1/`](v1/) — the Docker/web implementation (FastAPI + Svelte + MCP server, self-hosted via `docker compose`). Complete, tested, fully working.
- [`v2/`](v2/) — a Tauri desktop app wrapping the same backend as a native sidecar. The active development target: the confirmed use case is single-user, single-machine, no remote access ever, which fits a native app better than a self-hosted server (see `/Users/ciukes/dev/Trackeroo/ELECTRON_APP.md` for the full rationale).

Each version has its own `CLAUDE.md` with detailed conventions (`v1/CLAUDE.md`, `v2/CLAUDE.md` if present) — Claude Code auto-loads the nearest one, so working from inside `v1/` or `v2/` picks up the right instructions on top of this file.

## Worktrees are mandatory for any work

**Never edit files directly in this checkout's working tree (`main/`).** Always create a git worktree first and do the work there:

```bash
git worktree add worktrees/<short-task-name> -b <branch-name>
cd worktrees/<short-task-name>
```

- `worktrees/` lives inside `main/` (this checkout) and is git-ignored — it's local-only, never pushed.
- Pick a `branch-name` that describes the task (e.g. `fix-dependency-cycle`, `v2-notarize-build`). Base new branches off `main` unless told otherwise.
- When the work is done: commit in the worktree, merge/PR the branch into `main`, then remove the worktree (`git worktree remove worktrees/<name>`) — don't leave stale worktrees lying around after their branch has landed.
- This applies to every change, however small — doc tweaks, config edits, everything. It keeps `main`'s working tree always clean and matching `HEAD`, and keeps concurrent work (e.g. multiple agents/sessions) from colliding in the same files.
- If you're a Claude Code session and a worktree isn't already set up for your task, create one before your first edit — don't ask, just do it, per this file.

## Repo layout notes

- `.github/workflows/` stays at the repo root because GitHub only discovers workflows there; job paths inside are prefixed per-version (e.g. `v1/backend`).
- `AGENT_VISIBILITY.md` and `ELECTRON_APP.md` (in the parent `Trackeroo/` folder, one level above this repo) are untracked planning docs — not part of this repo.
