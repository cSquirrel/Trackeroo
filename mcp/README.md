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
variable. It defaults to `http://localhost:8000`.

```bash
export TRACKEROO_API_URL="http://localhost:8000"
```

## Run standalone

The server speaks MCP over stdio, so running it directly just waits for a client
on stdin/stdout (there is no interactive output — this is expected):

```bash
.venv/bin/python server.py
```

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
      "command": "/Users/ciukes/dev/Trackeroo/main/mcp/.venv/bin/python",
      "args": ["/Users/ciukes/dev/Trackeroo/main/mcp/server.py"],
      "env": {
        "TRACKEROO_API_URL": "http://localhost:8000"
      }
    }
  }
}
```

Or via the CLI:

```bash
claude mcp add trackeroo \
  --env TRACKEROO_API_URL=http://localhost:8000 \
  -- /Users/ciukes/dev/Trackeroo/main/mcp/.venv/bin/python \
     /Users/ciukes/dev/Trackeroo/main/mcp/server.py
```

## Register with Claude Desktop

Edit `claude_desktop_config.json` (macOS:
`~/Library/Application Support/Claude/claude_desktop_config.json`) and add the
same server entry:

```json
{
  "mcpServers": {
    "trackeroo": {
      "command": "/Users/ciukes/dev/Trackeroo/main/mcp/.venv/bin/python",
      "args": ["/Users/ciukes/dev/Trackeroo/main/mcp/server.py"],
      "env": {
        "TRACKEROO_API_URL": "http://localhost:8000"
      }
    }
  }
}
```

Restart Claude Desktop after editing the config.
