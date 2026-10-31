from typing import Any

from mcp.server.mcpserver import MCPServer

from . import app
from .pxc import Project

mcp = MCPServer(
    "pixel-composer",
    instructions=(
        "Controls Pixel Composer (node-based pixel-art/VFX tool) through its Remote Terminal addon. "
        "Typical loop: open_project -> inspect_project -> set_input (auto-reloads) -> export. "
        "Input values are positional (index); names are not stored in .pxc files. "
        "export renders every Export node in the project and returns the written files."
    ),
)
inst = app.Instance()


def _project(path: str | None) -> Project:
    if path:
        return Project(path)
    if inst.project is None:
        raise app.PxcError("no project open; pass path or call open_project")
    return Project(inst.project)


@mcp.tool()
def open_project(path: str) -> dict:
    """Open a .pxc in Pixel Composer, launching the app if needed (a window will appear)."""
    return inst.open(path)


@mcp.tool()
def inspect_project(path: str | None = None) -> dict:
    """List nodes with their type, stored input values (by index) and connections. Reads the file, not the app."""
    return _project(path).summary()


@mcp.tool()
def set_input(node: str, index: int, value: Any, path: str | None = None, reload: bool = True) -> dict:
    """Set a node input's static value in the .pxc file (node = id, iname or name).

    Reloads it in the app when it is the open project, so a following export uses the new value.
    """
    proj = _project(path)
    change = proj.set_input(node, index, value)
    proj.save()
    if reload and inst.project is not None and proj.path.resolve() == inst.project.resolve():
        change["reload"] = inst.open(proj.path)
    return change


@mcp.tool()
def export(timeout: float = 180) -> dict:
    """Run every Export node of the open project and wait until the output files stop changing."""
    return inst.export(timeout=timeout)


@mcp.tool()
def run_command(command: str, wait: float = 1.0) -> list[str]:
    """Send a raw console command (e.g. 'set <global> <value>', or any GML function name with
    space-separated args). Returns app log lines printed meanwhile (empty when attached)."""
    return inst.command(command, wait)


@mcp.tool()
def status() -> dict:
    """Connection mode (launched/attached/stopped), open project and recent app log."""
    return inst.status()


@mcp.tool()
def close() -> str:
    """Quit Pixel Composer if this server launched it."""
    return inst.close()


def main() -> None:
    # First run turns the addon on; later runs only find it already enabled.
    app.ensure_addon()
    mcp.run()
