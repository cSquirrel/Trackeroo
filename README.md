# Trackeroo

A lightweight, self-hosted task tracker for a single project: epics → tasks, configurable kanban swim lanes, dependencies, blockers, comments/annotations, and links to PRs or Slack threads — plus an MCP server so AI agents can create and update tasks directly.

## Quickstart (Docker)

```bash
docker compose up --build
```

Then open `http://localhost:8000`. The SQLite database is persisted to `./data` on the host via a mounted volume, so your board survives container restarts.

## What you get

- **Web board** — a kanban view with configurable swim lanes (default: Backlog / To Do / In Progress / Review / Done), draggable task cards, epic filtering and color-tagging.
- **Task detail** — description, comments and annotations, block/unblock with a reason, dependency links to other tasks, and links out to PRs or Slack threads.
- **Epics** — group related tasks; manage epics from their own view.
- **Swim lane config** — add, rename, reorder, or remove columns; mark one as the "done" column (used for dependency warnings).
- **MCP server** — `mcp/` exposes the same task/epic operations as MCP tools so an AI assistant (Claude Code, Claude Desktop, etc.) can manage the board on your behalf. See `mcp/README.md` for the exact config snippet to register it.

## Data model

One project → many epics → many tasks. Tasks can depend on other tasks (advisory — moving a task into the done column with open dependencies warns but doesn't block), can be marked blocked with a reason, and can carry links to PRs/Slack threads plus a comment/annotation thread. Full field-level detail lives in [`docs/api-contract.md`](docs/api-contract.md).

## Repo layout

```
backend/    FastAPI + SQLite REST API
frontend/   Svelte + Vite web UI
mcp/        MCP server (stdio) — thin HTTP client of the backend API
docs/       API contract (source of truth for backend/frontend/MCP)
data/       SQLite database file (Docker volume mount, gitignored)
```

## Local development (without Docker)

Backend:
```bash
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload
```

Frontend:
```bash
cd frontend
npm install
VITE_API_BASE_URL=http://localhost:8000 npm run dev
```

MCP server:
```bash
cd mcp
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
TRACKEROO_API_URL=http://localhost:8000 .venv/bin/python server.py
```

## Testing

```bash
cd backend && pytest --cov=app --cov-report=term-missing
cd frontend && npm run test
```

End-to-end (Playwright) and MCP integration suites run against the full Docker stack — see the CI workflow once added.

## Versioning

This repo uses git. The `main` branch (this checkout) is the mainline; feature work happens in the sibling `../worktrees/` directory as git worktrees.
