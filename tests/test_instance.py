"""Instance/server behaviour against a fake app that answers SAVE / load / nodeBuild like Pixel Composer."""

import copy
import json
import os
import types
import uuid
from pathlib import Path

import pytest

from pixel_composer_mcp import app, server
from pixel_composer_mcp.pxc import Project


class FakeApp:
    """Holds the project the 'app' loaded; SAVE writes that in-memory state back to disk.

    build_delay: how many SAVEs pass before a nodeBuild shows up (the real app builds over frames).
    """

    def __init__(self, build_delay: int = 0):
        self.loaded: Path | None = None
        self.state: dict | None = None
        self.build_delay = build_delay
        self.pending: list[list] = []

    def send(self, command: str) -> None:
        for line in command.split("\n"):
            if line.startswith("load_file_path "):
                self.loaded = Path(line.split(" ", 1)[1])
                self.state = copy.deepcopy(Project(self.loaded).data)
            elif line.startswith("nodeBuild "):
                _, t, x, y = line.split()
                node = {"id": uuid.uuid4().hex, "iname": t[5:] + "1", "type": t, "x": int(x), "y": int(y)}
                self.pending.append([self.build_delay, node])
            elif line.startswith("Node_create_") and line.split()[0].endswith("_path"):
                name, x, y, file = line.split(" ", 3)
                t = "Node_" + name[len("Node_create_"):-len("_path")]
                node = {"id": uuid.uuid4().hex, "iname": t[5:] + "1", "type": t, "x": int(x), "y": int(y),
                        "inputs": [{"r": {"d": file}}]}
                self.pending.append([self.build_delay, node])
            elif line == "SAVE":
                self._save()

    def _save(self) -> None:
        assert self.loaded is not None and self.state is not None
        for item in self.pending:
            if item[0] <= 0:
                self.state["nodes"].append(item[1])
            item[0] -= 1
        self.pending = [i for i in self.pending if i[0] >= 0]
        before = self.loaded.stat().st_mtime_ns
        p = Project(self.loaded)
        p.data = copy.deepcopy(self.state)
        p.save()
        # Guarantee a visible mtime change even on coarse clocks.
        os.utime(self.loaded, ns=(before, max(self.loaded.stat().st_mtime_ns, before + 1_000_000)))


@pytest.fixture
def fake(tmp_path, monkeypatch):
    path = tmp_path / "p.pxc"
    path.write_text(json.dumps({"nodes": [{"id": "a", "iname": "Blur1", "name": "Blur", "type": "Node_Blur",
                                            "inputs": [{}, {"r": {"d": 2}}]}]}))
    fake = FakeApp()
    monkeypatch.setattr(app, "ws_send", fake.send)
    monkeypatch.setattr(app, "time", types.SimpleNamespace(time=app.time.time, sleep=lambda s: None))
    inst = app.Instance()
    monkeypatch.setattr(inst, "connect", lambda *a, **k: "attached")
    monkeypatch.setattr(inst, "mode", lambda: "attached")
    monkeypatch.setattr(server, "inst", inst)
    inst.open(path)
    return types.SimpleNamespace(app=fake, inst=inst, path=path)


def blur_value(path: Path):
    return Project(path).find("Blur1")["inputs"][1]["r"]["d"]


def test_unreloaded_edit_survives_next_save(fake):
    # reload=False batches edits; the app still holds the old graph, and its SAVE must not undo them.
    server.set_input("Blur1", 1, 5, reload=False)
    server.save()
    assert blur_value(fake.path) == 5


def test_unreloaded_edit_survives_next_edit(fake):
    server.set_input("Blur1", 1, 5, reload=False)
    server.set_input("Blur1", 0, 1)  # reload=True: saves the app first
    assert blur_value(fake.path) == 5


def test_add_node_waits_for_slow_build(fake):
    fake.app.build_delay = 3
    r = server.add_node("Node_Shape", 10, 20)
    assert r["type"] == "Node_Shape"
    assert any(n["type"] == "Node_Shape" for n in Project(fake.path).nodes())


def test_add_node_unknown_type_still_fails(fake):
    fake.app.build_delay = 10_000
    with pytest.raises(Exception, match="did not create"):
        server.add_node("Node_Nope")


def test_open_warns_about_export_paths_that_cannot_be_written(fake, tmp_path):
    # Committed example projects carry the author's absolute export paths; say so instead of
    # letting a later export fail or write somewhere unexpected.
    proj = Project(fake.path)
    nid = proj.add_export_node(0, 0, "Q:/not/here/fire.png")
    ok = proj.add_export_node(0, 80, str(tmp_path / "ok.png"))
    proj.save()
    r = fake.inst.open(fake.path)
    assert len(r["warnings"]) == 1 and nid[-6:] in r["warnings"][0] and "Q:/not/here" in r["warnings"][0]
    assert ok[-6:] not in r["warnings"][0]


def test_add_file_node_without_dialog(fake, tmp_path):
    # File-reading nodes open a dialog when built by type; the app's *_path creators take the file.
    ase = tmp_path / "hero.aseprite"
    ase.write_bytes(b"x")
    r = server.add_node("Node_ASE_File_Read", 0, 0, file=str(ase))
    assert r["type"] == "Node_ASE_File_Read"
    node = Project(fake.path).find(r["id"])
    assert node["inputs"][0]["r"]["d"] == ase.as_posix()


def test_add_file_node_rejects_spaced_or_missing_path(fake, tmp_path):
    with pytest.raises(Exception, match="spaces"):
        server.add_node("Node_ASE_File_Read", 0, 0, file=str(tmp_path / "my hero.aseprite"))
    with pytest.raises(Exception, match="not found"):
        server.add_node("Node_ASE_File_Read", 0, 0, file=str(tmp_path / "missing.aseprite"))
