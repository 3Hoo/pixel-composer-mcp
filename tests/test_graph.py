from pixel_composer_mcp.graph import color, new_project, switch
from pixel_composer_mcp.pxc import Project


def test_new_project_needs_no_installed_sample(tmp_path, monkeypatch):
    # The skeleton ships with the package; agents outside the author's machine have no sample folder.
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "nothing"))
    p = Project(new_project(tmp_path / "a.pxc", 64, 48, 12, 8))
    assert p.data["nodes"] == [] and p.data["attributes"]["surface_dimension"] == [64, 48]
    assert p.data["animator"]["frames_total"] == 12 and p.data["animator"]["framerate"] == 8
    assert p.header[:4] == b"PXCX" and b"THMB" not in p.header


def test_switch_holds_value_without_ramp():
    assert switch(3, 6) == [(0, False), (2, False), (3, True), (5, True), (6, False)]


def test_color_is_abgr():
    assert color(1, 2, 3) == 0xFF030201
