from PIL import Image

from pixel_composer_mcp.sheetcheck import check_sheet

FW, FH, GROUND, COLS = 128, 160, 144, 10


def fx(style):
    """The elemental-rise effect rules (as the example README passes them)."""
    frames, window = (30, (6, 12)) if style == "pixel" else (60, (12, 24))
    return dict(frame_w=FW, frame_h=FH, frames=frames, ground_y=GROUND, peak_height=(100, 140),
                peak_window=window, edges=True)


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
    r = check_sheet(make_sheet(tmp_path, "pixel"), "pixel", **fx("pixel"))
    assert r["ok"], r["failures"]
    assert r["frames"] == 30 and r["peak_frame"] == 9 and r["peak_height"] == 120


def test_illust_sheet_passes(tmp_path):
    r = check_sheet(make_sheet(tmp_path, "illust"), "illust", **fx("illust"))
    assert r["ok"], r["failures"]
    assert r["frames"] == 60 and r["peak_frame"] == 18


def test_pixel_sheet_semi_alpha_fails(tmp_path):
    r = check_sheet(make_sheet(tmp_path, "pixel", stray_alpha_frame=7), "pixel", **fx("pixel"))
    assert not r["ok"] and any("frame 7" in f and "alpha" in f for f in r["failures"])


def test_pixel_sheet_too_many_colors_fails(tmp_path):
    r = check_sheet(make_sheet(tmp_path, "pixel", colors=12), "pixel", **fx("pixel"))
    assert not r["ok"] and any("colors" in f for f in r["failures"])


def test_touching_edge_fails(tmp_path):
    r = check_sheet(make_sheet(tmp_path, "illust", touch_top_frame=20), "illust", **fx("illust"))
    assert any("frame 20" in f and "edge" in f for f in r["failures"])


def test_wrong_sheet_size_fails(tmp_path):
    assert not check_sheet(make_blank(tmp_path, 1280, 500), "pixel", **fx("pixel"))["ok"]


def test_contact_preview_written(tmp_path):
    r = check_sheet(make_sheet(tmp_path, "pixel"), "pixel", **fx("pixel"))
    with Image.open(r["contact"]) as im:
        assert im.size == (1280 * 2, 480 * 2)


def test_pixel_sheet_stray_color_named_by_frame(tmp_path):
    # A colour used by a handful of pixels is a palette leak even when the total count is under the cap.
    path = make_sheet(tmp_path, "pixel")
    img = Image.open(path)
    ox, oy = (14 % COLS) * FW, (14 // COLS) * FH
    img.putpixel((ox + 60, oy + 140), (12, 250, 90, 255))
    img.save(path)
    r = check_sheet(path, "pixel", **fx("pixel"))
    assert not r["ok"] and any("frame 14" in f and "#0cfa5a" in f for f in r["failures"])


def test_effect_rules_only_when_asked(tmp_path):
    # Without effect numbers the sheet is just checked as pixel art; with them, frame count and peak.
    path = make_sheet(tmp_path, "pixel")
    assert check_sheet(path, "pixel", FW, FH)["ok"]
    r = check_sheet(path, "pixel", FW, FH, frames=31, ground_y=GROUND, peak_height=(130, 140), peak_window=(6, 12))
    assert any("30 frames, expected 31" in f for f in r["failures"])
    assert any("peak height 120px" in f for f in r["failures"])


def test_single_icon_defaults_to_whole_image(tmp_path):
    path = tmp_path / "icon.png"
    img = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    for x in range(32):  # an icon may fill its frame edge to edge
        for y in range(8, 24):
            img.putpixel((x, y), (200, 40, 40, 255))
    img.save(path)
    r = check_sheet(str(path), "pixel")
    assert r["ok"], r["failures"]
    assert r["frames"] == 1


def upscaled(tmp_path, stray_frame=None):
    """4 frames of 2x-upscaled art; optionally one lone 1x1 pixel (a mixed pixel size) in a frame."""
    path = tmp_path / "x2.png"
    img = Image.new("RGBA", (64 * 4, 64), (0, 0, 0, 0))
    for i in range(4):
        for x in range(10, 40, 2):
            for y in range(20, 50, 2):
                c = (200, 40, 40, 255) if (x + y) % 4 else (90, 20, 20, 255)
                for dx in (0, 1):
                    for dy in (0, 1):
                        img.putpixel((i * 64 + x + dx, y + dy), c)
    if stray_frame is not None:
        img.putpixel((stray_frame * 64 + 21, 31), (90, 20, 20, 255))
    img.save(path)
    return str(path)


def test_pixel_scale_consistent(tmp_path):
    r = check_sheet(upscaled(tmp_path), "pixel", 64, 64, pixel_scale=2)
    assert r["ok"], r["failures"]


def test_pixel_scale_mixed_named_by_frame(tmp_path):
    r = check_sheet(upscaled(tmp_path, stray_frame=2), "pixel", 64, 64, pixel_scale=2)
    assert not r["ok"] and any("frame 2" in f and "2x2" in f for f in r["failures"])
