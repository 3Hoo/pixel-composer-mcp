import functools
import os
from pathlib import Path
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from . import app
from .nodesrc import describe_node as describe_node_src
from .pxc import Project
from .sheetcheck import check_sheet as check_sheet_impl

mcp = MCPServer(
    "pixel-composer",
    instructions=(
        "Controls Pixel Composer (node-based pixel-art/VFX tool) through its Remote Terminal addon. "
        "Typical loop: open_project -> inspect_project -> set_input (auto-reloads) -> export. "
        "Build graphs with add_node / connect; look up what an input index means with describe_node. "
        "Input values are positional (index); names are not stored in .pxc files. "
        "export renders every Export node in the project and returns the written files. "
        "For the working procedure (interview, node map, known pitfalls, checks) use the pixel-composer "
        "agent skill from the repo's skills/pixel-composer folder."
    ),
)
inst = app.Instance()


def tool(fn):
    """Register fn as a tool; anticipated failures go to the client with their message.

    The SDK treats any other exception as a crash and replaces the message with a generic one,
    which hides things like an unknown node type or a missing file from the agent.
    """
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except (app.PxcError, KeyError, ValueError, OSError) as e:
            raise ToolError(str(e)) from e
    return mcp.tool()(wrapper)


def _project(path: str | None) -> Project:
    if path:
        return Project(path)
    if inst.project is None:
        raise app.PxcError("no project open; pass path or call open_project")
    return Project(inst.project)


@tool
def open_project(path: str) -> dict:
    """Open a .pxc in Pixel Composer, launching the app if needed (a window will appear)."""
    return inst.open(path)


@tool
def inspect_project(path: str | None = None) -> dict:
    """List nodes with their type, stored input values (by index) and connections. Reads the file, not the app."""
    return _project(path).summary()


def _edit(path: str | None, reload: bool, fn) -> dict:
    """Apply fn(Project) to the file. For the open project, save the app first (so unsaved
    in-app changes survive) and reload afterwards (so the app sees the edit)."""
    target = Path(path).resolve() if path else inst.project
    is_open = target is not None and inst.project is not None and target == inst.project.resolve()
    if is_open:
        inst.save()
    proj = _project(str(target) if target else None)
    change = fn(proj)
    proj.save()
    if is_open and reload:
        change["reload"] = inst.open(proj.path)
    return change


@tool
def set_input(node: str, index: int, value: Any, path: str | None = None, reload: bool = True,
              absolute: bool = False) -> dict:
    """Set a node input's static value in the .pxc file (node = id, iname or name); replaces keyframes.

    absolute=True stores positions/areas in pixels instead of 0..1 of the surface.
    Reloads it in the app when it is the open project, so a following export uses the new value;
    reload=False batches edits (the next save/export/edit loads them).
    """
    return _edit(path, reload, lambda p: p.set_input(node, index, value, absolute))


@tool
def set_keyframes(node: str, index: int, keys: list[tuple[int, Any]], path: str | None = None,
                  reload: bool = True, absolute: bool = False) -> dict:
    """Animate a node input with linear keyframes keys=[[frame, value], ...] (frames from 0).

    Booleans interpolate as well: to switch at frame f, key the old value at f-1 and the new at f.
    set_input on the same input turns the animation off again.
    """
    return _edit(path, reload, lambda p: p.set_keyframes(node, index, keys, absolute))


@tool
def connect(src: str, out_index: int, dst: str, in_index: int, path: str | None = None) -> dict:
    """Wire output `out_index` of node `src` into input `in_index` of node `dst`, then reload."""
    return _edit(path, True, lambda p: p.connect(src, out_index, dst, in_index))


@tool
def disconnect(dst: str, in_index: int, path: str | None = None) -> dict:
    """Remove the connection feeding input `in_index` of node `dst`, then reload."""
    return _edit(path, True, lambda p: p.disconnect(dst, in_index))


@tool
def add_node(node_type: str, x: int = 0, y: int = 0, file: str | None = None) -> dict:
    """Create a node (e.g. 'Node_Particle') in the open project via the app, save, return its id.

    File-reading nodes (Node_ASE_File_Read, Node_Image, ...) need file=<path without spaces>;
    built by type alone they open a dialog that freezes the app.
    """
    return inst.add_node(node_type, x, y, file)


@tool
def save() -> dict:
    """Save the open project from the app back to its .pxc file."""
    return inst.save()


@tool
def describe_node(node_type: str) -> dict:
    """Input/output names by index for a node type, from the Pixel Composer source clone in PXC_SOURCE."""
    src = os.environ.get("PXC_SOURCE")
    if not src:
        raise app.PxcError("set PXC_SOURCE to a clone of https://github.com/Ttanasart-pt/Pixel-Composer")
    return describe_node_src(node_type, Path(src))


@tool
def export(timeout: float = 180) -> dict:
    """Run every Export node of the open project and wait until the output files stop changing."""
    return inst.export(timeout=timeout)


@tool
def run_command(command: str, wait: float = 1.0) -> list[str]:
    """Send a raw console command (e.g. 'set <global> <value>', or any GML function name with
    space-separated args). Returns app log lines printed meanwhile (empty when attached)."""
    return inst.command(command, wait)


@tool
def status() -> dict:
    """Connection mode (launched/attached/stopped), open project and recent app log."""
    return inst.status()


@tool
def close() -> str:
    """Quit Pixel Composer if this server launched it."""
    return inst.close()


@tool
def check_sheet(path: str, style: str, frame_w: int | None = None, frame_h: int | None = None,
                frames: int | None = None, ground_y: int | None = None,
                peak_height: tuple[int, int] | None = None, peak_window: tuple[int, int] | None = None,
                edges: bool = False, max_colors: int = 8, pixel_scale: int = 1) -> dict:
    """Check a sprite sheet or single image (style 'pixel' or 'illust'); also writes
    <sheet>_contact.png, a 2x nearest-neighbour preview to look at.

    Always: grid fits, no empty frames in the middle. Pixel style: hard alpha, at most
    max_colors, stray colours named by frame, lone-pixel count ('orphans'), and with
    pixel_scale=k every frame on an aligned k x k grid. frame_w/frame_h default to the whole
    image. Effect rules run only when given: frames, ground_y (heights measured from it, peak
    must touch it), peak_height (min, max px), peak_window (first, last frame), edges (no
    clipping at left/right/top).
    """
    if style not in ("pixel", "illust"):
        raise ValueError("style must be 'pixel' or 'illust'")
    return check_sheet_impl(path, style, frame_w, frame_h, frames=frames, ground_y=ground_y,  # type: ignore[arg-type]
                            peak_height=peak_height, peak_window=peak_window, edges=edges,
                            max_colors=max_colors, pixel_scale=pixel_scale)


def main() -> None:
    # First run turns the addon on; later runs only find it already enabled.
    app.ensure_addon()
    mcp.run()
