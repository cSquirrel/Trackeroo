# Trackeroo MCP Server

An [MCP](https://modelcontextprotocol.io) server that exposes the Trackeroo
task board's REST API as tools, so AI agents can read and manage tasks, epics,
comments, dependencies, and links directly.

It is a thin HTTP client of the REST API described in
[`../docs/api-contract.md`](../docs/api-contract.md); the Trackeroo backend must
be running and reachable for the tools to work.

## Install

```bash
cd mcp
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Configuration

v2's backend binds to a fresh, unpredictable port every time a project is
opened (that's what lets multiple projects run at once) — a hardcoded URL
goes stale the moment the app restarts. Point the server at the **project
folder** instead, and it discovers the live port automatically:

```bash
export TRACKEROO_PROJECT_PATH="/path/to/your/project"
```

It reads `<project>/.trackeroo-port` (written by the app every time it spawns
a backend) fresh before each request, so it keeps working across app
restarts with no config changes — as long as that project is currently open
in Trackeroo. If it isn't, you'll get a clear error telling you to open it
first, instead of a silent connection failure.

For a fixed URL instead (e.g. v1's Docker deployment, which doesn't have this
problem), `TRACKEROO_API_URL` still works and takes priority if both are set.

## Run standalone

The server speaks MCP over stdio, so running it directly just waits for a client
on stdin/stdout (there is no interactive output — this is expected):

```bash
.venv/bin/python server.py
```

## Tests

`tests/` holds an integration suite that exercises every tool end-to-end against
a real backend. A session-scoped pytest fixture boots the actual Docker Compose
stack on an isolated port (`8100`) and its own named volume — so it never
collides with a local dev stack or its data — waits for `/api/health`, runs the
tools through the MCP SDK's in-memory client session (the same path a real MCP
client uses), and tears the stack down (`docker compose down -v`) afterwards,
even on failure.

Requires Docker to be running. From the `mcp/` directory:

```bash
pip install -r requirements.txt -r tests/requirements.txt
pytest -q
```

The first run builds the image (a few minutes); later runs reuse the cache.

## Tools

- `get_project` — project config + swimlanes (call first to discover swimlane ids)
- `list_epics`, `create_epic`, `update_epic`
- `list_tasks`, `get_task`, `create_task`, `update_task`
- `move_task` — reorder/move into a swimlane; surfaces any soft `warnings`
- `block_task`, `unblock_task`
- `add_comment`
- `add_dependency`, `remove_dependency`
- `add_link`

## Register with Claude Code

Add an entry to `.mcp.json` at your project root (or run the `claude mcp add`
command below). Use the absolute path to the venv Python so dependencies resolve:

```json
{
  "mcpServers": {
    "trackeroo": {
      "command": "/Users/ciukes/dev/Trackeroo/main/v2/mcp/.venv/bin/python",
      "args": ["/Users/ciukes/dev/Trackeroo/main/v2/mcp/server.py"],
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
  -- /Users/ciukes/dev/Trackeroo/main/v2/mcp/.venv/bin/python \
     /Users/ciukes/dev/Trackeroo/main/v2/mcp/server.py
```

## Register with Claude Desktop

Edit `claude_desktop_config.json` (macOS:
`~/Library/Application Support/Claude/claude_desktop_config.json`) and add the
same server entry:

```json
{
  "mcpServers": {
    "trackeroo": {
      "command": "/Users/ciukes/dev/Trackeroo/main/v2/mcp/.venv/bin/python",
      "args": ["/Users/ciukes/dev/Trackeroo/main/v2/mcp/server.py"],
      "env": {
        "TRACKEROO_PROJECT_PATH": "/path/to/your/project"
      }
    }
  }
}
```

Restart Claude Desktop after editing the config.
