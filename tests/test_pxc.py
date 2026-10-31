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
