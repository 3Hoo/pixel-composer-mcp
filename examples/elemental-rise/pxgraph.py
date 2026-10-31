"""Small scripting layer over pixel_composer_mcp for building effect graphs.

Nodes are created by the app (nodeBuild) so their JSON is valid; values, keyframes and links are
then edited in the saved .pxc and the project is reloaded. Value formats mirror Pixel Composer's
own serialisation (scripts/node_keyframe, curveBox, gradients_function in its source).
"""

import json
import os
import time
from pathlib import Path

from pixel_composer_mcp.app import Instance, ws_send
from pixel_composer_mcp.pxc import Project

SKELETON = Path(os.environ["LOCALAPPDATA"]) / "PixelComposer/Welcome files/Sample Projects/Cogwheels.pxc"


def new_project(path: Path, w: int, h: int, frames: int, fps: int) -> Path:
    """An empty project: a sample's top-level structure with its nodes removed."""
    p = Project(SKELETON)
    p.data["nodes"] = []
    p.data["previewNode"] = p.data["inspectingNode"] = ""
    p.data["attributes"]["surface_dimension"] = [w, h]
    p.data["animator"].update(frames_total=frames, framerate=fps)
    path.parent.mkdir(parents=True, exist_ok=True)
    p.save(path)
    return path


def color(r: int, g: int, b: int, a: int = 255) -> int:
    """GameMaker colour with alpha: 0xAABBGGRR."""
    return (a << 24) | (b << 16) | (g << 8) | r


def gradient(stops: list[tuple[float, tuple]], hard: bool = False) -> str:
    keys = [{"time": float(t), "value": float(color(*c))} for t, c in stops]
    return json.dumps({"keys": keys, "type": 1.0 if hard else 0.0})


def curve(points: list[tuple[float, float]]) -> list[float]:
    """Piecewise-linear curve through (x, y) points, x in 0..1."""
    out: list[float] = [0, 1, 0, 0, 1, 0]  # CURVE_PADD header as in CURVE_DEF_*
    for i, (x, y) in enumerate(points):
        px, py = points[i - 1] if i > 0 else (x, y)
        nx, ny = points[i + 1] if i < len(points) - 1 else (x, y)
        out += [-(x - px) / 3, -(y - py) / 3, x, y, (nx - x) / 3, (ny - y) / 3]
    return out


def switch(on: int, off: int) -> list[tuple[int, bool]]:
    """Keyframes for a boolean that is True only for frames on..off-1 (no interpolated ramp)."""
    keys: list[tuple[int, bool]] = []
    if on > 0:
        keys += [(0, False), (on - 1, False)]
    keys += [(on, True), (off - 1, True), (off, False)]
    return keys


class Graph:
    def __init__(self, inst: Instance, path: Path):
        self.inst, self.path = inst, Path(path)
        self.ids: dict[str, str] = {}
        inst.open(self.path)
        self.proj = Project(self.path)

    def add(self, specs: dict[str, tuple[str, int, int]]) -> dict[str, str]:
        """Create nodes {key: (Node_Type, x, y)} in one save; positions must be unique."""
        self.inst.save()
        before = {n["id"] for n in Project(self.path).nodes()}
        built = {k: s for k, s in specs.items() if s[0] != "Node_Export"}
        # One frame, one command per line: the addon runs them in order. Separate connections
        # in quick succession time out while the app is busy building nodes.
        ws_send("\n".join(f"nodeBuild {t} {x} {y}" for t, x, y in built.values()))
        # The app works through the lines over several frames; save until every node is there.
        new: dict = {}
        for _ in range(20):
            time.sleep(1.0)
            self.inst.save()
            self.proj = Project(self.path)
            new = {(n["type"], round(n["x"]), round(n["y"])): n["id"]
                   for n in self.proj.nodes() if n["id"] not in before}
            if all((t, x, y) in new for t, x, y in built.values()):
                break
        # Export nodes come from a JSON template: creating one in the app opens a modal dialog.
        for node_type, x, y in specs.values():
            if node_type == "Node_Export":
                new[(node_type, x, y)] = self.proj.add_export_node(x, y, "")
        for key, (node_type, x, y) in specs.items():
            if (node_type, x, y) not in new:
                raise RuntimeError(f"{key}: {node_type} was not created")
            self.ids[key] = new[(node_type, x, y)]
        return self.ids

    def _inp(self, key: str, index: int) -> dict:
        return self.proj._input(self.ids.get(key, key), index)[1]

    def set(self, key: str, index: int, value, absolute: bool = False) -> "Graph":
        """absolute=True: area/position values in pixels instead of 0..1 of the surface (input 'unit')."""
        inp = self._inp(key, index)
        inp.pop("anim", None)
        inp["r"] = {"d": value}
        if absolute:
            inp["unit"] = 0
        return self

    def dim(self, key: str, index: int, size: list[int]) -> "Graph":
        """Fixed surface size; Dimension inputs otherwise follow the project size."""
        inp = self._inp(key, index)
        inp["r"] = {"d": size}
        inp.setdefault("attri", {})["use_project_dimension"] = 0
        return self

    def anim(self, key: str, index: int, frames: list[tuple[int, object]], absolute: bool = False) -> "Graph":
        """Linear keyframes [(frame, value), ...]. Booleans interpolate too, so hold a value
        with a duplicate key right before a change (see `switch`)."""
        inp = self._inp(key, index)
        inp["anim"] = True
        inp["r"] = [[[0, f], v, [0, 1], [0, 0], 0, 0, True, 0, 16777215] for f, v in frames]
        if absolute:
            inp["unit"] = 0
        return self

    def link(self, src: str, dst: str, in_index: int, out_index: int = 0) -> "Graph":
        self.proj.connect(self.ids[src], out_index, self.ids[dst], in_index)
        return self

    def apply(self) -> None:
        self.proj.save()
        self.inst.open(self.path)

    def export(self, timeout: float = 180) -> dict:
        """Render Spritesheet nodes only collect frames while the timeline renders, which an
        animation Export (GIF) triggers. Pass 1 renders (GIFs + sheet frames); pass 2 writes the
        now-complete sheets."""
        first = self.inst.export(timeout)
        if not first.get("ok"):
            return first
        return self.inst.export(timeout)
