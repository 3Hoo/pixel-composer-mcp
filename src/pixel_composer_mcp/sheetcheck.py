"""Pass/fail checks for a sprite sheet: pixel-art hygiene always, effect timing/size when asked.

Grid sheet, frames left-to-right then top-to-bottom, transparent background. Without a frame
size the whole image is one frame (an icon). Effect rules (frame count, peak height and frame,
ground contact, clear edges) only run when their numbers are given.
"""

from collections import Counter, defaultdict
from pathlib import Path
from typing import Literal

from PIL import Image

# A colour this rare (share of all opaque pixels, or at most this many pixels) is a stray: a
# palette leak or a leftover anti-aliased pixel, not part of the art.
STRAY_SHARE, STRAY_MIN_PX = 0.0005, 4


def _bbox_rows(alpha: Image.Image) -> tuple[int, int] | None:
    box = alpha.getbbox()
    return (box[1], box[3] - 1) if box else None


def _off_grid(frame: Image.Image, k: int) -> int:
    """Pixels that differ from the top-left pixel of their aligned k x k block (0 = clean kx art)."""
    w, h = frame.size
    px = frame.load()
    return sum(1 for y in range(h) for x in range(w)
               if px[x, y] != px[x - x % k, y - y % k] and (px[x, y][3] or px[x - x % k, y - y % k][3]))


def _orphans(frame: Image.Image) -> int:
    """Opaque pixels whose 8 neighbours all have a different colour (lone dots)."""
    w, h = frame.size
    px = frame.load()
    n = 0
    for y in range(h):
        for x in range(w):
            p = px[x, y]
            if p[3] == 0:
                continue
            if all(px[x + dx, y + dy] != p for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                   if (dx or dy) and 0 <= x + dx < w and 0 <= y + dy < h):
                n += 1
    return n


def check_sheet(path: str, style: Literal["pixel", "illust"], frame_w: int | None = None,
                frame_h: int | None = None, *, frames: int | None = None, ground_y: int | None = None,
                peak_height: tuple[int, int] | None = None, peak_window: tuple[int, int] | None = None,
                edges: bool = False, max_colors: int = 8, pixel_scale: int = 1) -> dict:
    img = Image.open(path).convert("RGBA")
    failures: list[str] = []
    W, H = img.size
    frame_w, frame_h = frame_w or W, frame_h or H
    if W % frame_w or H % frame_h:
        return {"ok": False, "failures": [f"sheet {W}x{H} is not a grid of {frame_w}x{frame_h} frames"],
                "frames": 0, "peak_frame": -1, "peak_height": 0, "colors": 0, "orphans": 0, "contact": ""}

    cols = W // frame_w
    cells = [img.crop((c * frame_w, r * frame_h, (c + 1) * frame_w, (r + 1) * frame_h))
             for r in range(H // frame_h) for c in range(cols)]
    alphas = [f.getchannel("A") for f in cells]
    used = [i for i, a in enumerate(alphas) if a.getbbox()]
    n = used[-1] + 1 if used else 0
    if frames is not None and n != frames:
        failures.append(f"{n} frames, expected {frames}")

    base = ground_y if ground_y is not None else frame_h
    tops: list[int | None] = []
    colors: Counter = Counter()
    color_frames: defaultdict = defaultdict(set)
    soft = False
    orphans = 0
    for i in range(n):
        frame, a = cells[i], alphas[i]
        rows = _bbox_rows(a)
        tops.append(rows[0] if rows else None)
        if rows is None:
            if 0 < i < n - 1:
                failures.append(f"frame {i} is empty")
            continue
        box = a.getbbox()
        assert box is not None
        if edges and (box[0] == 0 or box[2] == frame_w or box[1] == 0):
            failures.append(f"frame {i} touches the left, right or top edge")
        hist = a.histogram()
        if any(hist[1:255]):
            soft = True
            if style == "pixel":
                failures.append(f"frame {i} has semi-transparent alpha ({sum(hist[1:255])} px)")
        if style == "pixel":
            here = Counter(p[:3] for p in frame.get_flattened_data() if p[3] == 255)
            colors.update(here)
            for rgb in here:
                color_frames[rgb].add(i)
            orphans += _orphans(frame)
            if pixel_scale > 1 and (off := _off_grid(frame, pixel_scale)):
                failures.append(f"frame {i}: {off} px break the {pixel_scale}x{pixel_scale} pixel grid "
                                "(mixed pixel sizes)")

    heights = [base - t if t is not None else 0 for t in tops]
    peak = max(range(n), key=lambda i: heights[i]) if n else -1  # first frame at max height
    peak_h = heights[peak] if n else 0
    if peak_height is not None:
        lo, hi = peak_height
        if not lo <= peak_h <= hi:
            failures.append(f"peak height {peak_h}px (frame {peak}), expected {lo}-{hi}")
    if peak_window is not None and n:
        w0, w1 = peak_window
        if not w0 <= peak <= w1:
            failures.append(f"peak at frame {peak}, expected within {w0}-{w1}")
    if ground_y is not None and n:
        bottom = _bbox_rows(alphas[peak])
        if bottom and not ground_y - 8 <= bottom[1] < frame_h:
            failures.append(f"frame {peak} bottom row {bottom[1]} is off the ground line {ground_y}")
    if style == "pixel":
        if len(colors) > max_colors:
            failures.append(f"{len(colors)} opaque colors, expected <= {max_colors}")
        rare = max(STRAY_MIN_PX, sum(colors.values()) * STRAY_SHARE)
        for rgb, count in sorted(colors.items(), key=lambda kv: kv[1]):
            if count <= rare:
                where = ", ".join(str(f) for f in sorted(color_frames[rgb]))
                failures.append(f"stray colour #{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}: {count} px in frame {where}")
    if style == "illust" and n and not soft:
        failures.append("no soft (semi-transparent) edges in an illustration sheet")

    contact = Path(path).with_name(Path(path).stem + "_contact.png")
    img.resize((W * 2, H * 2), Image.Resampling.NEAREST).save(contact)
    return {"ok": not failures, "failures": failures, "frames": n, "peak_frame": peak,
            "peak_height": peak_h, "colors": len(colors), "orphans": orphans, "contact": str(contact)}
