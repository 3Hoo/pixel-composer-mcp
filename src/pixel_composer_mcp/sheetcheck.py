"""Pass/fail checks for an effect sprite sheet against the elemental-rise spec.

Grid sheet, frames left-to-right then top-to-bottom, transparent background, ground line at
`ground_y` inside each frame. Numbers come from the design doc: 30 frames (pixel) / 60 (illust),
peak 100-140 px above the ground, pixel style hard-edged with at most 8 colors.
"""

from collections import Counter, defaultdict
from pathlib import Path
from typing import Literal

from PIL import Image

EXPECTED_FRAMES = {"pixel": 30, "illust": 60}
PEAK_WINDOW = {"pixel": (6, 12), "illust": (12, 24)}
PEAK_HEIGHT = (100, 140)
MAX_PIXEL_COLORS = 8
# A colour this rare (share of all opaque pixels, or at most this many pixels) is a stray: a
# palette leak or a leftover anti-aliased pixel, not part of the art.
STRAY_SHARE, STRAY_MIN_PX = 0.0005, 4


def _bbox_rows(alpha: Image.Image) -> tuple[int, int] | None:
    box = alpha.getbbox()
    return (box[1], box[3] - 1) if box else None


def check_sheet(path: str, style: Literal["pixel", "illust"], frame_w: int = 128, frame_h: int = 160,
                ground_y: int = 144) -> dict:
    img = Image.open(path).convert("RGBA")
    failures: list[str] = []
    W, H = img.size
    if W % frame_w or H % frame_h:
        return {"ok": False, "failures": [f"sheet {W}x{H} is not a grid of {frame_w}x{frame_h} frames"],
                "frames": 0, "peak_frame": -1, "peak_height": 0, "colors": 0, "contact": ""}

    cols = W // frame_w
    cells = [img.crop((c * frame_w, r * frame_h, (c + 1) * frame_w, (r + 1) * frame_h))
             for r in range(H // frame_h) for c in range(cols)]
    alphas = [f.getchannel("A") for f in cells]
    used = [i for i, a in enumerate(alphas) if a.getbbox()]
    n = used[-1] + 1 if used else 0
    if n != EXPECTED_FRAMES[style]:
        failures.append(f"{n} frames, expected {EXPECTED_FRAMES[style]}")

    tops: list[int | None] = []
    colors: Counter = Counter()
    color_frames: defaultdict = defaultdict(set)
    soft = False
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
        if box[0] == 0 or box[2] == frame_w or box[1] == 0:
            failures.append(f"frame {i} touches the left, right or top edge")
        hist = a.histogram()
        if any(hist[1:255]):
            soft = True
            if style == "pixel":
                failures.append(f"frame {i} has semi-transparent alpha ({sum(hist[1:255])} px)")
        here = Counter(p[:3] for p in frame.get_flattened_data() if p[3] == 255)
        colors.update(here)
        for rgb in here:
            color_frames[rgb].add(i)

    heights = [ground_y - t if t is not None else 0 for t in tops]
    peak = max(range(n), key=lambda i: heights[i]) if n else -1  # first frame at max height
    peak_h = heights[peak] if n else 0
    lo, hi = PEAK_HEIGHT
    if not lo <= peak_h <= hi:
        failures.append(f"peak height {peak_h}px (frame {peak}), expected {lo}-{hi}")
    w0, w1 = PEAK_WINDOW[style]
    if n and not w0 <= peak <= w1:
        failures.append(f"peak at frame {peak}, expected within {w0}-{w1}")
    if n:
        bottom = _bbox_rows(alphas[peak])
        if bottom and not ground_y - 8 <= bottom[1] < frame_h:
            failures.append(f"frame {peak} bottom row {bottom[1]} is off the ground line {ground_y}")
    if style == "pixel" and len(colors) > MAX_PIXEL_COLORS:
        failures.append(f"{len(colors)} opaque colors, expected <= {MAX_PIXEL_COLORS}")
    if style == "pixel":
        rare = max(STRAY_MIN_PX, sum(colors.values()) * STRAY_SHARE)
        for rgb, count in sorted(colors.items(), key=lambda kv: kv[1]):
            if count <= rare:
                frames = ", ".join(str(f) for f in sorted(color_frames[rgb]))
                failures.append(f"stray colour #{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}: {count} px in frame {frames}")
    if style == "illust" and n and not soft:
        failures.append("no soft (semi-transparent) edges in an illustration sheet")

    contact = Path(path).with_name(Path(path).stem + "_contact.png")
    img.resize((W * 2, H * 2), Image.Resampling.NEAREST).save(contact)
    return {"ok": not failures, "failures": failures, "frames": n, "peak_frame": peak,
            "peak_height": peak_h, "colors": len(colors), "contact": str(contact)}
