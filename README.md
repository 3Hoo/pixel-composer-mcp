# pixel-composer-mcp

MCP server that lets an agent drive [Pixel Composer](https://github.com/Ttanasart-pt/Pixel-Composer)
(Steam build, Windows): open a `.pxc`, read its node graph, change input values, render every Export node.

## How it works

- Talks to the app's built-in **Remote Terminal** addon (WebSocket, `127.0.0.1:22400`). Each command
  goes through the in-app console, which can call any GML function by name (`load_file_path`, `exportAll`, …).
- On every server start, `Addons/__init.json` is checked and `"Remote Terminal"` is appended if missing
  (other enabled addons are kept). The first start enables it; later starts only check.
- If the port is already open (you started Pixel Composer yourself), the server **attaches** to it.
  Otherwise it **launches** the app with `SteamAppId=2299510` (Steam builds abort without it) and reads its stdout.
  If the app is running without the port (started before the addon was enabled), restart it.
- A Pixel Composer window appears while working. `--headless` is not used: in 1.22.x it loads a stub theme
  missing keys that every Surface input needs, so almost no real project loads.

## Tools

| tool | what it does |
|---|---|
| `open_project(path)` | load a `.pxc` (launches the app if needed) |
| `inspect_project(path?)` | nodes, types, stored input values by index, connections (reads the file) |
| `set_input(node, index, value, path?, reload=True)` | edit a static input value in the file and reload it |
| `export(timeout=180)` | run every Export node, wait until outputs stop changing, return file paths |
| `run_command(command)` | raw console command, e.g. `set <global> <value>` or `<gml_function> arg1 arg2` |
| `status()` / `close()` | mode, project, log tail / quit the app (only if this server launched it) |

Limits: input names are not stored in `.pxc`, so inputs are addressed by index. The output file
extension comes from the Export node's format setting (asking for `x.png` can produce `x.gif`).
Image sequences (Export input 3 = 1) need `%f` in the name template (input 2, e.g. `%d%n_%f`),
otherwise every frame overwrites the same file.
Paths with spaces are loaded from a copy in `%LOCALAPPDATA%\PixelComposer\mcp_work\` because the
console splits arguments on spaces. In attach mode there is no app log, so `export` detects
completion by watching the Export folders.

## Setup

```json
{
  "mcpServers": {
    "pixel-composer": {
      "command": "uv",
      "args": ["run", "--directory", "D:/MCPS/pixel-composer-mcp", "pixel-composer-mcp"]
    }
  }
}
```

Environment overrides: `PXC_DIR` (install folder), `PXC_DATA_DIR` (default `%LOCALAPPDATA%\PixelComposer`),
`PXC_TERMINAL_PORT` (default `22400`).

## Security

Remote Terminal has no authentication and executes arbitrary app functions. It listens on all interfaces
(`::`), so keep port 22400 blocked from the network by the firewall. It stays enabled for normal app launches
too; turn it off in Pixel Composer's addon panel if you stop using this server.

## Tests

```
uv run pytest
```
