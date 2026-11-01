"""Scripting layer for building Pixel Composer graphs from Python build scripts.

Nodes are created by the app (nodeBuild) so their JSON is valid; values, keyframes and links are
then edited in the saved .pxc and the project is reloaded. Value formats mirror Pixel Composer's
own serialisation (scripts/node_keyframe, curveBox, gradients_function in its source).

Run a build script from anywhere with the package on the path, e.g.
    uv run --python 3.13 --with git+https://github.com/3Hoo/pixel-composer-mcp python build.py
"""

import json
import time
from pathlib import Path

from .app import Instance, ws_send
from .pxc import Project

SKELETON = Path(__file__).with_name("templates") / "empty_project.pxc"


def new_project(path: Path, w: int, h: int, frames: int, fps: int) -> Path:
    """An empty project of the given canvas size and timeline (bundled skeleton, no nodes)."""
    p = Project(SKELETON)
    p.data["attributes"]["surface_dimension"] = [w, h]
    p.data["animator"].update(frames_total=frames, framerate=fps)
    path = Path(path)
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
    """Create nodes in the app, then edit values/keyframes/links in the file and reload once."""

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

    def _ref(self, key: str) -> str:
        return self.ids.get(key, key)

    def set(self, key: str, index: int, value, absolute: bool = False) -> "Graph":
        """absolute=True: area/position values in pixels instead of 0..1 of the surface."""
        self.proj.set_input(self._ref(key), index, value, absolute)
        return self

    def dim(self, key: str, index: int, size: list[int]) -> "Graph":
        """Fixed surface size; Dimension inputs otherwise follow the project size."""
        inp = self.proj._input(self._ref(key), index)[1]
        inp["r"] = {"d": size}
        inp.setdefault("attri", {})["use_project_dimension"] = 0
        return self

    def anim(self, key: str, index: int, frames: list[tuple[int, object]], absolute: bool = False) -> "Graph":
        """Linear keyframes [(frame, value), ...] (see `switch` for booleans)."""
        self.proj.set_keyframes(self._ref(key), index, frames, absolute)
        return self

    def link(self, src: str, dst: str, in_index: int, out_index: int = 0) -> "Graph":
        self.proj.connect(self._ref(src), out_index, self._ref(dst), in_index)
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


def emitter(g: Graph, key: str, sprite: str, bg: str | None, *, spawn, amount, area, life, direction,
            speed, speed_curve, size, size_curve, colors, alpha_curve, gravity=None,
            rotation=None, spin=None):
    """Stream Node_Particle layer drawn over `bg` (Background input 74); spawn = switch() keys.

    Burst spawn renders nothing when driven this way, so short bursts are a stream switched on
    for a few frames.
    """
    g.link(sprite, key, 0)
    if bg:
        g.link(bg, key, 74)
    g.set(key, 16, 0).set(key, 21, False).set(key, 1, 1)          # stream, no loop, every frame
    g.anim(key, 27, spawn).set(key, 2, amount)
    g.set(key, 3, [*area, 0, 0], absolute=True)
    g.set(key, 5, life).set(key, 6, [0, *direction, 0, 0])
    g.set(key, 18, speed).set(key, 60, curve(speed_curve))
    g.set(key, 17, size).set(key, 11, curve(size_curve))
    g.set(key, 12, gradient(colors)).set(key, 14, curve(alpha_curve))
    if gravity:
        g.set(key, 19, gravity).set(key, 57, True)  # gravity only applies with "Use Physics" on
    if rotation:
        g.set(key, 8, [0, *rotation, 0, 0])
    if spin:
        g.set(key, 9, [0, *spin, 0, 0])
