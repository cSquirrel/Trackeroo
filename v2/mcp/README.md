# Trackeroo MCP Server

An [MCP](https://modelcontextprotocol.io) server that exposes the Trackeroo
task board's REST API as tools, so AI agents can read and manage tasks, epics,
comments, dependencies, and links directly.

It is a thin HTTP client of the REST API described in
[`../docs/api-contract.md`](../docs/api-contract.md). The Trackeroo app does
**not** need to be open: if no live backend is found for the project, the MCP
server spawns one itself on demand (see `backend_spawn.py`).

It's bundled into the app as a real executable (`Contents/MacOS/trackeroo-mcp`)
— installing `Trackeroo.app` is enough, no Python/pip/venv needed to use MCP.

## Configuration

v2's backend binds to a fresh, unpredictable port every time a project is
opened (that's what lets multiple projects run at once) — a hardcoded URL
goes stale the moment the app restarts. Point the server at the **project
folder** instead, and it discovers the live port automatically:

```bash
export TRACKEROO_PROJECT_PATH="/path/to/your/project"
```

It reads `<project>/.trackeroo/.env` (a KEY=VALUE file written every time a
backend spawns, containing `TRACKEROO_API_URL=<full-origin>`) fresh before
each request, so it keeps working across app restarts with no config changes.
If no live backend is found there — the app is closed, or its backend died —
the MCP server health-checks, then spawns the backend itself (the same entry
point the app uses) and writes `.env` the same way, so the app and other MCP
clients can discover it too.

MCP-spawned backends shut themselves down after 30 minutes without any HTTP
requests (set `TRACKEROO_IDLE_TIMEOUT_MINUTES` to change this). App-spawned
backends are untouched by all of this: the app still starts and stops its own
backend exactly as before. If you open the app on a project while an
MCP-spawned backend is still idling out, the two overlap harmlessly for a
while (WAL + busy-timeout keep writes safe); the idle one exits on its own.

For a known, fixed backend URL instead (e.g. manual testing against a
backend you started yourself, or a remote backend), `TRACKEROO_API_URL` as
an **environment variable** still works and takes priority if both are set.
The URL should be the origin only (e.g. `http://host:8787`) — the MCP server
appends `/api/…` paths itself.

## Register with Claude Code

Add an entry to `.mcp.json` at your project root, pointing at the bundled
binary inside the installed app:

```json
{
  "mcpServers": {
    "trackeroo": {
      "command": "/Applications/Trackeroo.app/Contents/MacOS/trackeroo-mcp",
      "args": [],
      "env": {
        "TRACKEROO_PROJECT_PATH": "/path/to/your/project"
      }
    }
  }
}
```

Or via the CLI:

```bash
claude mcp add trackeroo \
  --env TRACKEROO_PROJECT_PATH=/path/to/your/project \
  -- /Applications/Trackeroo.app/Contents/MacOS/trackeroo-mcp
```

## Register with Claude Desktop

Edit `claude_desktop_config.json` (macOS:
`~/Library/Application Support/Claude/claude_desktop_config.json`) and add the
same server entry:

```json
{
  "mcpServers": {
    "trackeroo": {
      "command": "/Applications/Trackeroo.app/Contents/MacOS/trackeroo-mcp",
      "args": [],
      "env": {
        "TRACKEROO_PROJECT_PATH": "/path/to/your/project"
      }
    }
  }
}
```

Restart Claude Desktop after editing the config.

## Tools

- `get_project` — project config + swimlanes (call first to discover swimlane ids)
- `create_swimlane`, `update_swimlane`, `delete_swimlane`, `reorder_swimlanes`
  (no `list_swimlanes` tool — `get_project` already returns them, ordered)
- `list_epics`, `create_epic`, `update_epic`, `epic_status` — rollup of an
  epic's progress: task counts by swimlane, done %, blocked count
- `list_tasks` — filter by `epic_id`/`swimlane_id`/`priority`, or set
  `sort_by_priority=True` for highest-priority-first (e.g. "highest priority
  tickets in review"). Returns a markdown table, not JSON — one header row
  instead of repeating field names per task. `fields` picks the columns
  (default: `id, title, description, type, priority, epic_id, swimlane_id,
  is_blocked` — `description` truncated to 120 chars, call `get_task` for the
  full text). Valid columns: `id, title, description, type, priority,
  epic_id, swimlane_id, position, is_blocked, blocked_reason, created_at,
  updated_at`.
- `search_tasks` — case-insensitive substring match over title/description
  (e.g. "do we have a ticket covering authentication?"). Same markdown-table
  output and `fields` param as `list_tasks`.
- `get_task`, `create_task`, `update_task`
- `move_task` — reorder/move into a swimlane; surfaces any soft `warnings`
- `block_task`, `unblock_task`
- `add_comment`
- `add_dependency`, `remove_dependency`
- `add_link`

Every tool returns compact markdown, not JSON — chosen for token economy on
the LLM side. Single objects render as `key: value` lines; nested lists
(comments, links, dependencies, swimlanes) render as tables under a
`name (count):` heading; multi-line text (e.g. a task description) comes last
as its own block. Null fields and empty lists are omitted entirely — absence
means "not set"/"none".

## Developing

Run from source instead of the bundled binary (e.g. while changing `server.py`):

```bash
cd mcp
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
TRACKEROO_PROJECT_PATH=/path/to/your/project .venv/bin/python server.py
```

The server speaks MCP over stdio, so running it directly just waits for a client
on stdin/stdout (there is no interactive output — this is expected).

To rebuild the bundled binary after a change, see `../README.md`'s "Building a
release bundle" section.

## Tests

`tests/` holds an integration suite that exercises every tool end-to-end against
a real backend. A session-scoped pytest fixture spawns the actual backend (the
same `run_sidecar.py` entry point the app uses) from `../backend/.venv` on an
isolated free port, pointed at a throwaway SQLite database in a temp dir — so it
never collides with a local dev stack or its data — waits for `/api/health`,
runs the tools through the MCP SDK's in-memory client session (the same path a
real MCP client uses), and kills the backend afterwards, even on failure.

No Docker required — it just needs the backend's virtualenv. From the `mcp/`
directory:

```bash
# one-time: create the backend venv the tests spawn
python3 -m venv ../backend/.venv
../backend/.venv/bin/pip install -r ../backend/requirements.txt

pip install -r requirements.txt -r tests/requirements.txt
pytest -q
```

`tests_spawn/` separately covers `backend_spawn.py`'s discover-or-spawn logic
(it manages its own per-test backends); run it with `pytest tests_spawn/ -q`.
