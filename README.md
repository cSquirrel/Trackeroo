# Trackeroo

This repository holds versioned implementations of **Trackeroo**, a lightweight, self-hosted single-project task tracker (epics → tasks, configurable kanban swim lanes, dependencies, blockers, comments/annotations, PR/Slack links, plus an MCP server for AI agents).

## Current implementation

The current implementation lives in [`v1/`](v1/README.md). Start there — its README has the Docker quickstart, local-dev instructions, and testing/CI details.

A future `v2/` (a different architecture) may be added as a sibling directory later; each version is self-contained under its own top-level folder.

> `.github/workflows/` stays at the repo root (GitHub only discovers workflows there); the CI job paths are prefixed to point into `v1/`.

## Versioning

This repo uses git. The `main` branch (this checkout) is the mainline; feature work happens in the sibling `../worktrees/` directory as git worktrees.
