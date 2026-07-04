# Trackeroo

**Trackeroo** is a lightweight, self-hosted single-project task tracker: epics → tasks, configurable kanban swim lanes, dependencies, blockers, comments/annotations, PR/Slack links, plus an MCP server so AI agents can create and update tasks directly.

Packaged as a native macOS desktop app (Tauri) — the target use case is a single user on a single machine, with no remote access ever needed. See [`v2/README.md`](v2/README.md) for the product overview, quickstart, and how to build/run it.

> The app lives under `v2/` (historically the second implementation, now the only one) — left named as-is rather than flattened to the repo root.

## Worktrees

**Any work in this repo happens in a git worktree, never directly in the checkout's working tree.** `worktrees/` lives inside this checkout and is git-ignored:

```bash
git worktree add worktrees/<short-task-name> -b <branch-name> develop
cd worktrees/<short-task-name>
```

See `CLAUDE.md` for the full convention.

## Branch model & releases

- **`develop`** is the active development branch — feature branches fork from it and merge back into it.
- **`main`** holds stable releases. Cut a release by merging `develop` → `main` and pushing a semver tag `vX.Y.Z` on `main`; that tag runs `.github/workflows/release.yml`, which builds and drafts a signed GitHub Release. Publishing it is what ships an auto-update to installed apps. See [`v2/README.md`](v2/README.md) → "Releases & auto-updates" for the full pipeline and the one-time signing-key setup.
