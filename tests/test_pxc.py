import json
import os
from pathlib import Path

import pytest

from pixel_composer_mcp.pxc import Project

SAMPLES = Path(os.environ.get("LOCALAPPDATA", "")) / "PixelComposer" / "Welcome files" / "Sample Projects"
needs_samples = pytest.mark.skipif(not SAMPLES.exists(), reason="Pixel Composer sample projects not installed")


@needs_samples
@pytest.mark.parametrize("name", ["Cogwheels.pxc", "Tree.pxc"])
def test_roundtrip_keeps_data_and_header(tmp_path, name):
    src = Project(SAMPLES / name)
    out = src.save(tmp_path / name)
    back = Project(out)
    assert back.data == src.data
    assert back.header == src.header and back.compressed == src.compressed


def test_plain_json_project(tmp_path):
    p = tmp_path / "plain.pxc"
    p.write_text(json.dumps({"nodes": [{"id": "a", "iname": "Blur1", "name": "Blur", "type": "Node_Blur",
                                        "inputs": [{"r": {"d": -4}, "from_node": "b"}, {"r": {"d": 2}}]}]}))
    proj = Project(p)
    assert not proj.compressed and proj.header == b""
    assert proj.set_input("Blur1", 1, 5)["old"] == 2
    with pytest.raises(ValueError):
        proj.set_input("a", 0, 1)  # linked input
    proj.save()
    assert Project(p).find("Blur")["inputs"][1]["r"]["d"] == 5


@needs_samples
def test_summary_lists_tree_export():
    s = Project(SAMPLES / "Tree.pxc").summary()
    assert any(n["type"] == "Node_Export" for n in s["nodes"])


def make_plain(tmp_path):
    p = tmp_path / "graph.pxc"
    p.write_text(json.dumps({"nodes": [
        {"id": "a", "iname": "Blur1", "name": "Blur", "type": "Node_Blur", "inputs": [{"r": {"d": -4}}, {"r": {"d": 2}}]},
        {"id": "b", "iname": "Shape1", "name": "Shape", "type": "Node_Shape", "inputs": [], "outputs": [{}]},
    ]}))
    return Project(p)


def test_connect_and_disconnect(tmp_path):
    proj = make_plain(tmp_path)
    r = proj.connect("Shape1", 0, "Blur1", 1)
    assert r == {"from": "b", "from_index": 0, "to": "a", "in_index": 1}
    inp = proj.find("a")["inputs"][1]
    assert inp["from_node"] == "b" and inp["from_index"] == 0
    proj.disconnect("a", 1)
    assert "from_node" not in proj.find("a")["inputs"][1]
    proj.set_input("a", 1, 3)  # allowed again once unlinked


def test_connect_pads_inputs(tmp_path):
    proj = make_plain(tmp_path)
    proj.connect("b", 0, "a", 5)
    assert len(proj.find("a")["inputs"]) == 6


def test_add_export_node_from_template(tmp_path):
    proj = make_plain(tmp_path)
    nid = proj.add_export_node(320, 64, "C:/out/fx.png")
    node = proj.find(nid)
    assert node["type"] == "Node_Export" and (node["x"], node["y"]) == (320, 64)
    assert node["inputs"][1]["r"]["d"] == "C:/out/fx.png"
    assert "from_node" not in node["inputs"][0]
    assert proj.add_export_node(0, 0, "") != nid  # ids stay unique


def test_export_template_uses_node_defaults(tmp_path):
    # The template came from a sample whose Export had scale 8 and GIF settings; a new node must not.
    proj = make_plain(tmp_path)
    node = proj.find(proj.add_export_node(0, 0, ""))
    for i, inp in enumerate(node["inputs"][2:], start=2):
        if "def_val" in inp and "r" in inp:
            assert inp["r"]["d"] == inp["def_val"], f"input {i}"


def plain_blur(tmp_path):
    p = tmp_path / "plain.pxc"
    p.write_text(json.dumps({"nodes": [{"id": "a", "iname": "Blur1", "name": "Blur", "type": "Node_Blur",
                                        "inputs": [{"r": {"d": -4}, "from_node": "b"}, {"r": {"d": 2}}]}]}))
    return Project(p)


def test_set_keyframes_then_back_to_static(tmp_path):
    proj = plain_blur(tmp_path)
    proj.set_keyframes("Blur1", 1, [(0, 2), (10, 6)])
    inp = proj.find("Blur1")["inputs"][1]
    assert inp["anim"] is True
    assert [(k[0][1], k[1]) for k in inp["r"]] == [(0, 2), (10, 6)]
    proj.set_input("Blur1", 1, 3)  # a static value replaces the keyframes
    assert "anim" not in inp and inp["r"] == {"d": 3}


def test_absolute_values_use_pixel_unit(tmp_path):
    proj = plain_blur(tmp_path)
    proj.set_input("Blur1", 1, [10, 20], absolute=True)
    assert proj.find("Blur1")["inputs"][1]["unit"] == 0


def test_set_keyframes_refuses_linked_input(tmp_path):
    with pytest.raises(ValueError, match="connection"):
        plain_blur(tmp_path).set_keyframes("Blur1", 0, [(0, 1)])
