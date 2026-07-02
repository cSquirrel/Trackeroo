# Trackeroo

A lightweight, self-hosted single-project task tracker — see `README.md` for the product overview and `v2/README.md`/`v2/CLAUDE.md` for the implementation (Tauri desktop app; `cd` into `v2/` before working on it, its `CLAUDE.md` has the real conventions). This file covers repo-wide conventions.

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

- No CI wiring exists yet. If one is added later, GitHub only discovers workflows at `.github/workflows/` relative to the repo root, so put it there even though the code lives under `v2/`.
