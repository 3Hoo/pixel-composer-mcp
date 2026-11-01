"""Build water.pxc: a water column bursting up from the ground line, two styles.

Canvas 128x160, ground y=144, 60 frames @ 24 fps, same casting rhythm as fire and ice:
telegraph 0-11 (bubbles converge on the centre while the ripple patch shrinks and sharpens),
bang at 12 (flash, the ~40 px column shoots up within 3 frames), hold to 35 with streaks running
up the column and a spray crown, then the column collapses (36-41) into droplets and a splash
at its base, with the ripple spreading out to 59.
The column is Quadrilateral/Ellipse shapes drawn in canvas pixels, chained through BG Surface.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from pixel_composer_mcp.app import Instance  # noqa: E402
from pixel_composer_mcp.graph import Graph, color, emitter, new_project, switch  # noqa: E402
from pxgraph import TAIL_NODES, output_tail  # noqa: E402

HERE = Path(__file__).parent
W, H, FRAMES, FPS, GROUND, CX = 128, 160, 60, 24, 144, 64
BASE, HEIGHT = GROUND + 2, 104  # the crown spray adds ~25 px on top
# (frame, k = column height fraction or None = hidden, dx = sway of the top in px).
# Hidden = moved off-canvas: a zero-area quad fills the frame.
COLUMN = [(0, None, 0), (11, None, 0), (12, 0.45, 0), (13, 0.85, 0), (14, 1, 0), (18, 0.98, 2),
          (22, 1, -1), (26, 0.97, 2), (30, 1, -2), (35, 1, 0),
          (37, 0.85, 0), (39, 0.55, 0), (41, 0.15, 0), (42, None, 0)]
OFF = [[0, 200], [0, 210], [6, 210], [6, 200]]


def top(k: float) -> int:
    return round(BASE - (BASE - GROUND + HEIGHT) * k)


inst = Instance()
path = new_project(HERE / "water.pxc", W, H, FRAMES, FPS)
g = Graph(inst, path)
g.add({
    "blob": ("Node_Shape", 0, 0), "soft": ("Node_Blur", 160, 0), "dot": ("Node_Shape", 0, 160),
    "streak": ("Node_Shape", 0, 480),
    "glow": ("Node_Shape", 0, 320), "glowsoft": ("Node_Blur", 160, 320),
    "body": ("Node_Shape", 320, 480), "inner": ("Node_Shape", 480, 480), "hilite": ("Node_Shape", 640, 480),
    "cap": ("Node_Shape", 800, 480),
    "streaks": ("Node_Particle", 320, 0), "spray": ("Node_Particle", 480, 0), "crown": ("Node_Particle", 480, 160),
    "foam": ("Node_Particle", 640, 160), "churn": ("Node_Particle", 800, 160), "drops": ("Node_Particle", 640, 0),
    "splash": ("Node_Particle", 800, 0), "inL": ("Node_Particle", 960, 0), "inR": ("Node_Particle", 960, 160),
    "flash": ("Node_Particle", 960, 320),
    **TAIL_NODES,
})

# sprites: soft round blob, small hard droplet, thin vertical streak
g.dim("blob", 0, [32, 32]).set("blob", 17, [0.3, 0.3]).set("blob", 2, "Ellipse").set("blob", 1, 0).set("blob", 6, True)
g.link("blob", "soft", 0).set("soft", 1, 4)
g.dim("dot", 0, [6, 6]).set("dot", 17, [0.35, 0.35]).set("dot", 2, "Ellipse").set("dot", 1, 0).set("dot", 6, True)
g.dim("streak", 0, [4, 16]).set("streak", 17, [0.4, 0.45]).set("streak", 2, "Ellipse").set("streak", 1, 0).set("streak", 6, True)

# ripple patch: wide and diffuse -> tight during the telegraph, then spreads out until the end
g.set("glow", 2, "Ellipse").set("glow", 1, 0).set("glow", 6, True).set("glow", 15, 1)
g.set("glow", 16, [CX, GROUND], absolute=True).set("glow", 10, color(150, 220, 250))
g.anim("glow", 17, [(0, [30, 4]), (11, [5, 2]), (12, [30, 5]), (36, [30, 5]), (48, [42, 4]), (59, [48, 3])], absolute=True)
g.link("glow", "glowsoft", 0).anim("glowsoft", 1, [(0, 6), (11, 2), (12, 3)])  # >6 wraps to the top row

# column: quads (bottom-left, top-left, top-right, bottom-right) narrowing slightly to the top
prev = "glowsoft"
for key, (bot, tip, col, drop) in {
        "body":   ((20, 16, (55, 145, 225), 0)),
        "inner":  ((10, 7, (130, 210, 250), 3)),
        "hilite": ((-13, -11, (235, 250, 255), 6)),   # negative: a thin strip on the left side
}.items():
    g.set(key, 2, "Quadrilateral").set(key, 15, 2).set(key, 6, True).set(key, 10, color(*col))
    g.set(key, 1, 2).link(prev, key, 46)  # Background = Surface: draw over the layers below
    if bot > 0:
        xs = [CX - bot, CX - tip, CX + tip, CX + bot]
    else:  # strip from x=CX+bot to CX+bot+3
        xs = [CX + bot, CX + tip, CX + tip + 3, CX + bot + 3]
    for idx, x, at_top in zip((32, 33, 35, 52), xs, (False, True, True, False)):
        keys = []
        for f, k, dx in COLUMN:
            if k is None:
                keys.append((f, OFF[[32, 33, 35, 52].index(idx)]))
            else:
                keys.append((f, [x + dx, min(BASE, top(k) + drop)] if at_top else [x, BASE]))
        g.anim(key, idx, keys, absolute=True)
    prev = key

# rounded foamy cap riding on the column top
g.set("cap", 2, "Ellipse").set("cap", 15, 1).set("cap", 6, True).set("cap", 10, color(225, 245, 255))
g.set("cap", 1, 2).link(prev, "cap", 46)
g.anim("cap", 16, [(f, [CX + dx, top(k) + 2] if k is not None else [CX, 220]) for f, k, dx in COLUMN], absolute=True)
g.anim("cap", 17, [(f, [17, 6] if k is not None else [1, 1]) for f, k, _ in COLUMN], absolute=True)

WATER = [(0, (255, 255, 255)), (0.4, (170, 230, 255)), (0.8, (80, 170, 235)), (1, (40, 110, 200))]
emitter(g, "streaks", "streak", "cap", spawn=switch(14, 34), amount=[1, 2], area=[CX, 128, 12, 10],
        life=[8, 12], direction=[90, 90], speed=[6, 8], speed_curve=[(0, 1), (1, 1)],
        size=[0.7, 1.0], size_curve=[(0, 1), (1, 0.8)],
        colors=[(0, (255, 255, 255)), (1, (190, 235, 255))], alpha_curve=[(0, 0), (0.2, 0.9), (0.8, 0.9), (1, 0)])
# crown: one burst when the column arrives (sets the peak height), then a steady low fountain
emitter(g, "crown", "dot", "streaks", spawn=switch(14, 16), amount=[7, 9], area=[CX, top(1) + 3, 12, 2],
        life=[12, 18], direction=[55, 125], speed=[2.5, 3.5], speed_curve=[(0, 1), (1, 0.8)],
        size=[0.8, 1.2], size_curve=[(0, 1), (1, 0.7)], colors=WATER, alpha_curve=[(0, 1), (0.8, 1), (1, 0)],
        gravity=[0.3, 0.35])
emitter(g, "spray", "dot", "crown", spawn=switch(16, 36), amount=[2, 3], area=[CX, top(1) + 3, 14, 2],
        life=[8, 12], direction=[50, 130], speed=[1, 2], speed_curve=[(0, 1), (1, 0.7)],
        size=[0.6, 1.0], size_curve=[(0, 1), (1, 0.7)], colors=WATER, alpha_curve=[(0, 1), (0.8, 1), (1, 0)],
        gravity=[0.25, 0.3])
emitter(g, "foam", "soft", "spray", spawn=switch(13, 36), amount=[2, 2], area=[CX, top(1) + 4, 14, 2],
        life=[6, 9], direction=[40, 140], speed=[0.6, 1.4], speed_curve=[(0, 1), (1, 0.5)],
        size=[0.4, 0.6], size_curve=[(0, 0.7), (1, 1.1)],
        colors=[(0, (255, 255, 255)), (1, (200, 240, 255))], alpha_curve=[(0, 0.9), (1, 0)])
emitter(g, "churn", "soft", "foam", spawn=switch(12, 36), amount=[1, 2], area=[CX, 141, 20, 2],
        life=[6, 10], direction=[60, 120], speed=[0.5, 1.5], speed_curve=[(0, 1), (1, 0.5)],
        size=[0.5, 0.8], size_curve=[(0, 0.7), (1, 1.1)],
        colors=[(0, (255, 255, 255)), (1, (190, 235, 255))], alpha_curve=[(0, 0.9), (1, 0)])
# the collapse: droplets shed from the falling column, then a splash where it lands
emitter(g, "drops", "dot", "churn", spawn=switch(36, 42), amount=[3, 4], area=[CX, 96, 18, 40],
        life=[12, 18], direction=[50, 130], speed=[1.5, 3.5], speed_curve=[(0, 1), (1, 0.7)],
        size=[0.7, 1.1], size_curve=[(0, 1), (1, 0.6)], colors=WATER, alpha_curve=[(0, 1), (0.8, 1), (1, 0)],
        gravity=[0.3, 0.4])
emitter(g, "splash", "dot", "drops", spawn=switch(39, 46), amount=[3, 4], area=[CX, 141, 20, 2],
        life=[10, 16], direction=[45, 135], speed=[3, 4.5], speed_curve=[(0, 1), (1, 0.6)],
        size=[0.7, 1.1], size_curve=[(0, 1), (1, 0.6)], colors=WATER, alpha_curve=[(0, 1), (0.8, 1), (1, 0)],
        gravity=[0.35, 0.45])
# telegraph: bubbles from both sides accelerate into the centre and die before the bang
CONVERGE = dict(spawn=switch(0, 9), amount=[1, 2], life=[9, 11], speed=[3.4, 3.8],
                speed_curve=[(0, 0.4), (1, 1)], size=[0.6, 0.9], size_curve=[(0, 0.6), (1, 1)],
                colors=[(0, (90, 180, 240)), (1, (230, 250, 255))], alpha_curve=[(0, 0), (0.2, 1), (0.85, 1), (1, 0)])
emitter(g, "inL", "dot", "splash", area=[CX - 30, 141, 6, 3], direction=[0, 0], **CONVERGE)
emitter(g, "inR", "dot", "inL", area=[CX + 30, 141, 6, 3], direction=[180, 180], **CONVERGE)
emitter(g, "flash", "soft", "inR", spawn=switch(12, 14), amount=[1, 1], area=[CX, 136, 0, 0],
        life=[4, 4], direction=[90, 90], speed=[0, 0], speed_curve=[(0, 1), (1, 1)],
        size=[2.0, 2.0], size_curve=[(0, 0.7), (0.4, 1), (1, 1)],
        colors=[(0, (255, 255, 255)), (1, (190, 235, 255))], alpha_curve=[(0, 1), (1, 0)])

PIXEL_PALETTE = [(255, 255, 255), (200, 240, 255), (130, 210, 250), (60, 150, 225), (35, 100, 190),
                 (20, 55, 130)]
# threshold 0.5 as for ice: anti-aliased column edges would otherwise outline in the darkest blue
output_tail(g, "flash", PIXEL_PALETTE, HERE / "water", FPS, threshold=0.5)
g.apply()
print(g.export(timeout=240))
