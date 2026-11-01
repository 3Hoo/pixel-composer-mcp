from PIL import Image

from pixel_composer_mcp.sheetcheck import check_sheet

FW, FH, GROUND, COLS = 128, 160, 144, 10


def heights(style):
    """Synthetic eruption: small telegraph, rise to 120 px at the hit frame, hold, shrink."""
    n, peak = (30, 9) if style == "pixel" else (60, 18)
    out = []
    for i in range(n):
        if i < peak - 3:
            out.append(4)
        elif i <= peak:
            out.append(120 - (peak - i) * 30)
        elif i < n * 0.6:
            out.append(120)
        else:
            out.append(max(4, int(120 * (n - i) / (n * 0.4))))
    return out


def make_sheet(tmp_path, style, colors=4, stray_alpha_frame=None, touch_top_frame=None):
    hs = heights(style)
    rows = -(-len(hs) // COLS)
    img = Image.new("RGBA", (FW * COLS, FH * rows), (0, 0, 0, 0))
    px = img.load()
    for i, h in enumerate(hs):
        ox, oy = (i % COLS) * FW, (i // COLS) * FH
        for y in range(GROUND - h, 150):
            c = ((y * 37) % colors) * 20
            for x in range(44, 84):
                px[ox + x, oy + y] = (200, c, 40, 255)
        if style == "illust":  # soft edge
            for y in range(GROUND - h, 150):
                px[ox + 43, oy + y] = (255, 230, 180, 120)
        if i == stray_alpha_frame:
            px[ox + 60, oy + 148] = (200, 0, 40, 128)
        if i == touch_top_frame:
            px[ox + 60, oy] = (200, 0, 40, 255)
    path = tmp_path / f"{style}.png"
    img.save(path)
    return str(path)


def make_blank(tmp_path, w, h):
    path = tmp_path / "blank.png"
    Image.new("RGBA", (w, h), (0, 0, 0, 0)).save(path)
    return str(path)


def test_pixel_sheet_passes(tmp_path):
    r = check_sheet(make_sheet(tmp_path, "pixel"), "pixel")
    assert r["ok"], r["failures"]
    assert r["frames"] == 30 and r["peak_frame"] == 9 and r["peak_height"] == 120


def test_illust_sheet_passes(tmp_path):
    r = check_sheet(make_sheet(tmp_path, "illust"), "illust")
    assert r["ok"], r["failures"]
    assert r["frames"] == 60 and r["peak_frame"] == 18


def test_pixel_sheet_semi_alpha_fails(tmp_path):
    r = check_sheet(make_sheet(tmp_path, "pixel", stray_alpha_frame=7), "pixel")
    assert not r["ok"] and any("frame 7" in f and "alpha" in f for f in r["failures"])


def test_pixel_sheet_too_many_colors_fails(tmp_path):
    r = check_sheet(make_sheet(tmp_path, "pixel", colors=12), "pixel")
    assert not r["ok"] and any("colors" in f for f in r["failures"])


def test_touching_edge_fails(tmp_path):
    r = check_sheet(make_sheet(tmp_path, "illust", touch_top_frame=20), "illust")
    assert any("frame 20" in f and "edge" in f for f in r["failures"])


def test_wrong_sheet_size_fails(tmp_path):
    assert not check_sheet(make_blank(tmp_path, 1280, 500), "pixel")["ok"]


def test_contact_preview_written(tmp_path):
    r = check_sheet(make_sheet(tmp_path, "pixel"), "pixel")
    with Image.open(r["contact"]) as im:
        assert im.size == (1280 * 2, 480 * 2)


def test_pixel_sheet_stray_color_named_by_frame(tmp_path):
    # A colour used by a handful of pixels is a palette leak even when the total count is under the cap.
    path = make_sheet(tmp_path, "pixel")
    img = Image.open(path)
    ox, oy = (14 % COLS) * FW, (14 // COLS) * FH
    img.putpixel((ox + 60, oy + 140), (12, 250, 90, 255))
    img.save(path)
    r = check_sheet(path, "pixel")
    assert not r["ok"] and any("frame 14" in f and "#0cfa5a" in f for f in r["failures"])
