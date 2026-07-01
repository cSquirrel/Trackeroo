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

The server reads the API base URL from the `TRACKEROO_API_URL` environment
variable. In v2 the Trackeroo backend runs as the Tauri app's sidecar on port
`8787`, so point the MCP server at it:

```bash
export TRACKEROO_API_URL="http://localhost:8787"
```

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
        "TRACKEROO_API_URL": "http://localhost:8787"
      }
    }
  }
}
```

Or via the CLI:

```bash
claude mcp add trackeroo \
  --env TRACKEROO_API_URL=http://localhost:8787 \
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
        "TRACKEROO_API_URL": "http://localhost:8787"
      }
    }
  }
}
```

Restart Claude Desktop after editing the config.
