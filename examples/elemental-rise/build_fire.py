"""Build fire.pxc: an explosive flame burst erupting from the ground line, two styles.

Canvas 128x160, ground y=144, 60 frames @ 24 fps. Timeline: telegraph 0-11 (ground glow, slow
embers), burst 12-17 (peak ~frame 18), rolling flame to ~32, smoke and falling embers to 59.
Layers are chained through each particle node's Background input (back to front).
Illustration = the chain's output; pixel = alpha threshold + 6-colour hard gradient map + De-Stray,
sampled every 2nd frame (12 fps).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from pixel_composer_mcp.app import Instance  # noqa: E402
from pxgraph import Graph, color, curve, gradient, new_project, switch  # noqa: E402

HERE = Path(__file__).parent
W, H, FRAMES, FPS, GROUND, CX = 128, 160, 60, 24, 144, 64


def emitter(g: Graph, key: str, sprite: str, bg: str | None, *, spawn, amount, area, life, direction,
            speed, speed_curve, size, size_curve, colors, alpha_curve, gravity=None):
    g.link(sprite, key, 0)
    if bg:
        g.link(bg, key, 74)
    g.set(key, 16, 0).set(key, 21, False).set(key, 1, 1)          # stream, no loop, every frame
    g.anim(key, 27, spawn).set(key, 2, amount)
    g.set(key, 3, [*area, 0, 0], absolute=True)
    g.set(key, 5, life).set(key, 6, [0, *direction, 0, 0])
    g.set(key, 18, speed).set(key, 60, curve(speed_curve))
    g.set(key, 17, size).set(key, 11, curve(size_curve))
    g.set(key, 12, gradient(colors)).set(key, 14, curve(alpha_curve))
    if gravity:
        g.set(key, 19, gravity).set(key, 57, True)  # gravity only applies with "Use Physics" on


inst = Instance()
path = new_project(HERE / "fire.pxc", W, H, FRAMES, FPS)
g = Graph(inst, path)
g.add({
    "blob": ("Node_Shape", 0, 0), "soft": ("Node_Blur", 160, 0), "dot": ("Node_Shape", 0, 160),
    "tongue": ("Node_Shape", 0, 480), "tongsoft": ("Node_Blur", 160, 480), "bloom": ("Node_Bloom", 1120, 0), "haze": ("Node_Level", 1280, 0),
    "glow": ("Node_Shape", 0, 320), "glowsoft": ("Node_Blur", 160, 320),
    "smoke": ("Node_Particle", 320, 0), "hold": ("Node_Particle", 480, 0), "core": ("Node_Particle", 640, 0),
    "sparks": ("Node_Particle", 800, 0), "tele": ("Node_Particle", 960, 0),
    "thr": ("Node_Threshold", 1120, 160), "amask": ("Node_Alpha_Grey", 1120, 320), "pal": ("Node_Posterize", 1280, 160), "clean": ("Node_De_Stray", 1440, 160),
    "sheet_il": ("Node_Render_Sprite_Sheet", 1600, 0), "sheet_px": ("Node_Render_Sprite_Sheet", 1600, 160),
    "png_il": ("Node_Export", 1760, 0), "gif_il": ("Node_Export", 1760, 80),
    "png_px": ("Node_Export", 1760, 160), "gif_px": ("Node_Export", 1760, 240),
})

# sprites: soft round blob, tall flame tongue, small hard dot
g.dim("blob", 0, [32, 32]).set("blob", 17, [0.3, 0.3]).set("blob", 2, "Ellipse").set("blob", 1, 0).set("blob", 6, True)
g.link("blob", "soft", 0).set("soft", 1, 4)
g.dim("tongue", 0, [24, 40]).set("tongue", 17, [0.28, 0.4]).set("tongue", 2, "Ellipse").set("tongue", 1, 0).set("tongue", 6, True)
g.link("tongue", "tongsoft", 0).set("tongsoft", 1, 4)
g.dim("dot", 0, [6, 6]).set("dot", 17, [0.35, 0.35]).set("dot", 2, "Ellipse").set("dot", 1, 0).set("dot", 6, True)

# ground glow: grows during the telegraph, flashes wide on the burst, fades out
g.set("glow", 2, "Ellipse").set("glow", 1, 0).set("glow", 6, True).set("glow", 15, 1)
g.set("glow", 16, [CX, GROUND], absolute=True).set("glow", 10, color(255, 170, 80))
g.anim("glow", 17, [(0, [4, 1]), (11, [22, 3]), (12, [30, 4]), (16, [34, 5]), (26, [10, 2]), (30, [0, 0])], absolute=True)
g.link("glow", "glowsoft", 0).set("glowsoft", 1, 6)

FIRE = [(0, (255, 250, 220)), (0.2, (255, 220, 90)), (0.45, (255, 140, 40)), (0.7, (230, 70, 30)), (1, (150, 30, 30))]
emitter(g, "smoke", "soft", "glowsoft", spawn=switch(20, 50), amount=[1, 2], area=[CX, 122, 16, 14],
        life=[16, 22], direction=[80, 100], speed=[0.3, 0.8], speed_curve=[(0, 1), (1, 0.5)],
        size=[1.0, 1.4], size_curve=[(0, 0.6), (1, 1.3)],
        colors=[(0, (190, 140, 120)), (1, (140, 120, 125))], alpha_curve=[(0, 0), (0.25, 0.6), (1, 0)])
emitter(g, "hold", "tongsoft", "smoke", spawn=switch(16, 34), amount=[3, 4], area=[CX, 141, 16, 2],
        life=[10, 16], direction=[82, 98], speed=[4, 7], speed_curve=[(0, 1), (1, 0.3)],
        size=[0.6, 0.9], size_curve=[(0, 0.5), (0.3, 1), (1, 0.3)],
        colors=FIRE, alpha_curve=[(0, 1), (0.75, 0.9), (1, 0)])
emitter(g, "core", "tongsoft", "hold", spawn=switch(12, 18), amount=[9, 11], area=[CX, 143, 12, 2],
        life=[8, 12], direction=[80, 100], speed=[17, 21], speed_curve=[(0, 1), (0.5, 0.35), (1, 0.15)],
        size=[0.9, 1.3], size_curve=[(0, 0.5), (0.25, 1.15), (1, 0.35)],
        colors=FIRE, alpha_curve=[(0, 1), (0.6, 0.9), (1, 0)])
emitter(g, "sparks", "dot", "core", spawn=switch(12, 16), amount=[3, 5], area=[CX, 140, 10, 4],
        life=[30, 44], direction=[65, 115], speed=[3, 6], speed_curve=[(0, 1), (1, 0.4)],
        size=[0.6, 1.0], size_curve=[(0, 1), (1, 0.6)],
        colors=[(0, (255, 250, 200)), (0.5, (255, 180, 60)), (1, (220, 70, 30))],
        alpha_curve=[(0, 1), (0.8, 1), (1, 0)], gravity=[0.3, 0.4])
emitter(g, "tele", "dot", "sparks", spawn=switch(0, 12), amount=[1, 1], area=[CX, 144, 22, 1],
        life=[8, 14], direction=[85, 95], speed=[0.6, 1.2], speed_curve=[(0, 1), (1, 1)],
        size=[0.6, 0.9], size_curve=[(0, 1), (1, 0.5)],
        colors=[(0, (255, 220, 120)), (1, (230, 80, 30))], alpha_curve=[(0, 1), (1, 0)])

# pixel version: hard alpha, snap to a 7-colour palette (2 smoke greys + 5 fire), remove stray pixels
PIXEL_PALETTE = [(110, 90, 100), (165, 135, 130), (150, 35, 35), (225, 75, 35), (255, 145, 45),
                 (255, 215, 95), (255, 250, 215)]
# Palette Posterize writes opaque pixels everywhere, so it is masked by a hard 0/1 mask made from
# the thresholded alpha: inside -> palette colour, outside -> the (fully transparent) input.
g.link("tele", "thr", 0).set("thr", 7, True).set("thr", 8, 0.2)
g.link("thr", "amask", 0)
g.link("thr", "pal", 0).link("amask", "pal", 12).set("pal", 2, True).set("pal", 1, [color(*c) for c in PIXEL_PALETTE])
g.link("pal", "clean", 0)

# bloom spreads near-zero alpha over the whole frame; Level clips it (alpha < 4% -> 0)
g.link("tele", "bloom", 0).link("bloom", "haze", 0).set("haze", 5, [0.04, 1])

# outputs: illustration every frame, pixel every 2nd frame; 10-column grids
g.link("haze", "sheet_il", 0).set("sheet_il", 3, 2).set("sheet_il", 4, 10)
g.link("clean", "sheet_px", 0).set("sheet_px", 3, 2).set("sheet_px", 4, 10).set("sheet_px", 2, 2)
g.link("sheet_il", "png_il", 0).set("png_il", 1, str(HERE / "fire_illust.png"))
g.link("sheet_px", "png_px", 0).set("png_px", 1, str(HERE / "fire_pixel.png"))
g.link("haze", "gif_il", 0).set("gif_il", 1, str(HERE / "fire_illust.gif")).set("gif_il", 3, 2).set("gif_il", 8, FPS)
g.link("clean", "gif_px", 0).set("gif_px", 1, str(HERE / "fire_pixel.gif")).set("gif_px", 3, 2) \
    .set("gif_px", 8, FPS // 2).set("gif_px", 14, 2)
g.apply()
print(g.export(timeout=240))
