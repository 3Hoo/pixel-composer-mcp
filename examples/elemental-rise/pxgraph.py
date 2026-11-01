"""Output tail shared by the elemental-rise build scripts: one front layer -> illustration and
pixel-art branches, 10-column sprite sheets and preview GIFs. The general graph helpers live in
pixel_composer_mcp.graph.
"""

from pathlib import Path

from pixel_composer_mcp.graph import Graph, color


# Nodes of the shared output tail; merge into Graph.add specs (x >= 1120 is reserved for them).
TAIL_NODES = {
    "bloom": ("Node_Bloom", 1120, 0), "haze": ("Node_Level", 1280, 0),
    "thr": ("Node_Threshold", 1120, 160), "amask": ("Node_Alpha_Grey", 1120, 320),
    "pal": ("Node_Posterize", 1280, 160), "clean": ("Node_De_Stray", 1440, 160),
    "sheet_il": ("Node_Render_Sprite_Sheet", 1600, 0), "sheet_px": ("Node_Render_Sprite_Sheet", 1600, 160),
    "png_il": ("Node_Export", 1760, 0), "gif_il": ("Node_Export", 1760, 80),
    "png_px": ("Node_Export", 1760, 160), "gif_px": ("Node_Export", 1760, 240),
}


def output_tail(g: Graph, front: str, palette: list[tuple], out: Path, fps: int, threshold: float = 0.2) -> None:
    """Both styles from the front layer: illustration (bloom, every frame) and pixel art
    (hard alpha, palette, every 2nd frame), as 10-column sheets plus preview GIFs
    <out>_illust.png/.gif and <out>_pixel.png/.gif."""
    # Palette Posterize writes opaque pixels everywhere, so it is masked by a hard 0/1 mask made
    # from the thresholded alpha: inside -> palette colour, outside -> the (transparent) input.
    g.link(front, "thr", 0).set("thr", 7, True).set("thr", 8, threshold)
    g.link("thr", "amask", 0)
    g.link("thr", "pal", 0).link("amask", "pal", 12).set("pal", 2, True).set("pal", 1, [color(*c) for c in palette])
    g.link("pal", "clean", 0)
    # bloom spreads near-zero alpha over the whole frame; Level clips it (alpha < 4% -> 0)
    g.link(front, "bloom", 0).link("bloom", "haze", 0).set("haze", 5, [0.04, 1])
    g.link("haze", "sheet_il", 0).set("sheet_il", 3, 2).set("sheet_il", 4, 10)
    g.link("clean", "sheet_px", 0).set("sheet_px", 3, 2).set("sheet_px", 4, 10).set("sheet_px", 2, 2)
    g.link("sheet_il", "png_il", 0).set("png_il", 1, f"{out}_illust.png")
    g.link("sheet_px", "png_px", 0).set("png_px", 1, f"{out}_pixel.png")
    g.link("haze", "gif_il", 0).set("gif_il", 1, f"{out}_illust.gif").set("gif_il", 3, 2).set("gif_il", 8, fps)
    g.link("clean", "gif_px", 0).set("gif_px", 1, f"{out}_pixel.gif").set("gif_px", 3, 2)         .set("gif_px", 8, fps // 2).set("gif_px", 14, 2)
