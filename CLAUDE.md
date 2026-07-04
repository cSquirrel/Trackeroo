# Trackeroo

A lightweight, self-hosted single-project task tracker — see `README.md` for the product overview and `v2/README.md`/`v2/CLAUDE.md` for the implementation (Tauri desktop app; `cd` into `v2/` before working on it, its `CLAUDE.md` has the real conventions). This file covers repo-wide conventions.

## Branch model

- **`develop` is the active development branch.** All feature work branches off `develop` and merges back into `develop`.
- **`main` holds stable releases only.** It moves forward when a release is cut: merge `develop` → `main`, then push a semver tag `vX.Y.Z` on `main`. That tag triggers `.github/workflows/release.yml`, which builds the signed macOS bundle + updater artifacts and drafts a GitHub Release. Publishing that release is what makes the auto-updater's `/releases/latest/download/latest.json` endpoint point at the new version (see `v2/README.md` → Releases & auto-updates).
- Don't commit directly to `main`; it only receives merges from `develop` at release time.

## Worktrees are mandatory for any work

**Never edit files directly in this checkout's working tree.** Always create a git worktree first and do the work there:

```bash
git worktree add worktrees/<short-task-name> -b <branch-name> develop
cd worktrees/<short-task-name>
```

- `worktrees/` lives inside this checkout and is git-ignored — it's local-only, never pushed.
- Pick a `branch-name` that describes the task (e.g. `fix-dependency-cycle`, `v2-notarize-build`). Base new branches off `develop` unless told otherwise.
- When the work is done: commit in the worktree, merge/PR the branch into `develop`, then remove the worktree (`git worktree remove worktrees/<name>`) — don't leave stale worktrees lying around after their branch has landed.
- This applies to every change, however small — doc tweaks, config edits, everything. It keeps the checkout's working tree always clean and matching `HEAD`, and keeps concurrent work (e.g. multiple agents/sessions) from colliding in the same files.
- If you're a Claude Code session and a worktree isn't already set up for your task, create one before your first edit — don't ask, just do it, per this file.

## Merging work

Whenever you land a working branch into `develop` (or `develop` into `main` for a release):

- **Merge only when it's proven safe.** First run every applicable check — lint, the automated test suites, a build, and (where relevant) a manual run of the app — and confirm the change actually works and does not break the app. Never merge on a hunch or with known-failing or skipped-that-should-pass checks.
- **Confirm the target branch is healthy after the merge.** Re-verify on the branch itself (tests/build pass, the app still runs) so a bad merge is caught right away, not later.
- **Always remove the working branch after a successful merge** — locally and on the remote (`git branch -d <name>` and `git push origin --delete <name>`), and remove its worktree if it had one (`git worktree remove worktrees/<name>`). Leave no stale branches or worktrees behind.

## Repo layout notes

- CI/release wiring lives at `.github/workflows/` relative to the repo root (GitHub only discovers workflows there), even though the app code lives under `v2/`. See `release.yml` for the tag-triggered release pipeline.
