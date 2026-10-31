import json

from pixel_composer_mcp import app


def test_ensure_addon_merges_and_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(app, "DATA_DIR", tmp_path)
    cfg = tmp_path / "Addons" / "__init.json"
    cfg.parent.mkdir()
    cfg.write_text(json.dumps(["Controller mapper"]))

    assert app.ensure_addon() is True
    assert json.loads(cfg.read_text()) == ["Controller mapper", "Remote Terminal"]
    assert app.ensure_addon() is False  # later starts only check


def test_ensure_addon_creates_config(tmp_path, monkeypatch):
    monkeypatch.setattr(app, "DATA_DIR", tmp_path)
    assert app.ensure_addon() is True
    assert json.loads((tmp_path / "Addons" / "__init.json").read_text()) == ["Remote Terminal"]
