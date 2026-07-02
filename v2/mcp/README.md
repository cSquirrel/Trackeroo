# Trackeroo MCP Server

An [MCP](https://modelcontextprotocol.io) server that exposes the Trackeroo
task board's REST API as tools, so AI agents can read and manage tasks, epics,
comments, dependencies, and links directly.

It is a thin HTTP client of the REST API described in
[`../docs/api-contract.md`](../docs/api-contract.md); the Trackeroo backend must
be running and reachable for the tools to work.

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

It reads `<project>/.trackeroo/port` (written by the app every time it spawns
a backend) fresh before each request, so it keeps working across app
restarts with no config changes — as long as that project is currently open
in Trackeroo. If it isn't, you'll get a clear error telling you to open it
first, instead of a silent connection failure.

For a known, fixed backend URL instead (e.g. manual testing against a
backend you started yourself), `TRACKEROO_API_URL` still works and takes
priority if both are set.

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
- `list_epics`, `create_epic`, `update_epic`
- `list_tasks`, `get_task`, `create_task`, `update_task`
- `move_task` — reorder/move into a swimlane; surfaces any soft `warnings`
- `block_task`, `unblock_task`
- `add_comment`
- `add_dependency`, `remove_dependency`
- `add_link`

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
