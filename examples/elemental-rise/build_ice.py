"""Build ice.pxc: a cluster of ice spikes jutting up from the ground line, two styles.

Canvas 128x160, ground y=144, 60 frames @ 24 fps, same casting rhythm as fire: telegraph 0-11
(frost glints converge on the centre while the frost patch shrinks and sharpens), bang at 12
(flash, all five spikes shoot up within 3 frames, chips fly), hold to 35 with glints, then the
spikes crumble (36-39) into falling shards and frost mist that fade by 59.
Each spike is two Triangle shapes (light left face, dark right face) drawn in canvas pixels
(Positioning Mode "Full Image") and chained through the Shape's BG Surface input.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from pixel_composer_mcp.app import Instance  # noqa: E402
from pixel_composer_mcp.graph import Graph, color, emitter, new_project, switch  # noqa: E402
from pxgraph import TAIL_NODES, output_tail  # noqa: E402

HERE = Path(__file__).parent
W, H, FRAMES, FPS, GROUND, CX = 128, 160, 60, 24, 144, 64
BASE = GROUND + 2  # spike bases sit just below the ground line so they read as coming out of it

# (base centre x, base half width, height above ground, tip lean in px, rise keys)
# The centre spike leads; the side spikes trail by a frame so the cluster opens like a burst.
# k = height fraction; None = hidden. A zero-area Triangle fills the whole frame in Pixel Composer,
# so a hidden spike is moved off the canvas instead of being flattened.
LEAD = [(0, None), (11, None), (12, 0.5), (13, 0.88), (14, 1)]
TRAIL = [(0, None), (11, None), (12, 0.25), (13, 0.7), (14, 0.95), (15, 1)]
SPIKES = [(64, 11, 118, 0, LEAD), (46, 8, 84, -10, TRAIL), (83, 8, 92, 12, TRAIL),
          (32, 6, 52, -14, TRAIL), (98, 6, 58, 14, TRAIL)]
CRUMBLE = [(35, 1), (37, 0.55), (38, 0.25), (39, None)]  # spikes sink fast while the shards burst out
OFF = ([0, 200], [4, 210], [-4, 210])  # foot, tip, ridge foot of a hidden face, below the canvas
LIGHT, DARK = (215, 245, 255), (95, 170, 230)

inst = Instance()
path = new_project(HERE / "ice.pxc", W, H, FRAMES, FPS)
g = Graph(inst, path)
faces = {f"s{i}{side}": ("Node_Shape", 320 + 160 * i, 480 + 160 * j)
         for i in range(len(SPIKES)) for j, side in enumerate("ab")}
g.add({
    "blob": ("Node_Shape", 0, 0), "soft": ("Node_Blur", 160, 0), "dot": ("Node_Shape", 0, 160),
    "shard": ("Node_Shape", 0, 480),
    "glow": ("Node_Shape", 0, 320), "glowsoft": ("Node_Blur", 160, 320),
    **faces,
    "chips": ("Node_Particle", 320, 0), "glints": ("Node_Particle", 480, 0), "shards": ("Node_Particle", 640, 0),
    "mist": ("Node_Particle", 800, 0), "inL": ("Node_Particle", 960, 0), "inR": ("Node_Particle", 960, 160),
    "flash": ("Node_Particle", 960, 320),
    **TAIL_NODES,
})

# sprites: soft round blob, small hard dot, thin shard triangle
g.dim("blob", 0, [32, 32]).set("blob", 17, [0.3, 0.3]).set("blob", 2, "Ellipse").set("blob", 1, 0).set("blob", 6, True)
g.link("blob", "soft", 0).set("soft", 1, 4)
g.dim("dot", 0, [6, 6]).set("dot", 17, [0.35, 0.35]).set("dot", 2, "Ellipse").set("dot", 1, 0).set("dot", 6, True)
g.dim("shard", 0, [8, 12]).set("shard", 2, "Triangle").set("shard", 1, 0).set("shard", 6, True).set("shard", 15, 2)
g.set("shard", 32, [4, 0], absolute=True).set("shard", 33, [0, 12], absolute=True).set("shard", 35, [8, 9], absolute=True)

# frost patch: wide and diffuse -> tight and bright during the telegraph, spreads on the bang, fades
g.set("glow", 2, "Ellipse").set("glow", 1, 0).set("glow", 6, True).set("glow", 15, 1)
g.set("glow", 16, [CX, GROUND], absolute=True).set("glow", 10, color(190, 235, 255))
g.anim("glow", 17, [(0, [30, 4]), (11, [5, 2]), (12, [44, 5]), (36, [44, 5]), (48, [32, 4]), (59, [10, 3])], absolute=True)
g.link("glow", "glowsoft", 0).anim("glowsoft", 1, [(0, 6), (11, 2), (12, 4)])  # >6 wraps to the top row

# spikes: Point 1 = outer foot, Point 2 = tip, Point 3 = ridge foot (shared by both faces)
prev = "glowsoft"
for i, (bx, hw, h, lean, rise) in enumerate(SPIKES):
    mid = round(bx + lean * 0.3)  # ridge foot, shifted toward the lean
    keys = [*rise, *CRUMBLE]
    for side, (foot, col) in {"a": (bx - hw, LIGHT), "b": (bx + hw, DARK)}.items():
        key = f"s{i}{side}"
        g.set(key, 2, "Triangle").set(key, 15, 2).set(key, 6, True).set(key, 10, color(*col))
        g.set(key, 1, 2).link(prev, key, 46)  # Background = Surface: draw over the layers below

        def at(k, real, hidden):
            return hidden if k is None else real(k)
        g.anim(key, 32, [(f, at(k, lambda _: [foot, BASE], OFF[0])) for f, k in keys], absolute=True)
        g.anim(key, 33, [(f, at(k, lambda k: [round(mid + (bx + lean - mid) * k), round(BASE - (BASE - GROUND + h) * k)],
                              OFF[1])) for f, k in keys], absolute=True)
        g.anim(key, 35, [(f, at(k, lambda _: [mid, BASE], OFF[2])) for f, k in keys], absolute=True)
        prev = key

ICE = [(0, (255, 255, 255)), (0.4, (190, 235, 255)), (0.75, (110, 190, 240)), (1, (60, 120, 200))]
emitter(g, "chips", "shard", prev, spawn=switch(12, 14), amount=[2, 3], area=[CX, 138, 20, 3],
        life=[16, 24], direction=[70, 110], speed=[4, 6], speed_curve=[(0, 1), (1, 0.6)],
        size=[0.7, 1.0], size_curve=[(0, 1), (1, 0.8)], colors=ICE, alpha_curve=[(0, 1), (0.8, 1), (1, 0)],
        gravity=[0.35, 0.45], rotation=[0, 360], spin=[-15, 15])
emitter(g, "glints", "dot", "chips", spawn=switch(16, 35), amount=[1, 1], area=[CX, 104, 26, 30],
        life=[3, 5], direction=[90, 90], speed=[0, 0], speed_curve=[(0, 1), (1, 1)],
        size=[0.6, 0.9], size_curve=[(0, 0.3), (0.5, 1.2), (1, 0.3)],
        colors=[(0, (255, 255, 255)), (1, (220, 245, 255))], alpha_curve=[(0, 1), (1, 1)])
# the crumble: shards burst out of where the spikes stood and fall
emitter(g, "shards", "shard", "glints", spawn=switch(36, 40), amount=[5, 6], area=[CX, 112, 30, 28],
        life=[12, 18], direction=[55, 125], speed=[1.5, 3], speed_curve=[(0, 1), (1, 0.6)],
        size=[0.8, 1.3], size_curve=[(0, 1), (1, 0.7)], colors=ICE, alpha_curve=[(0, 1), (0.8, 1), (1, 0)],
        gravity=[0.35, 0.45], rotation=[0, 360], spin=[-20, 20])
# many small faint puffs: a few big ones read as glowing balls once bloomed
emitter(g, "mist", "soft", "shards", spawn=switch(36, 54), amount=[2, 3], area=[CX, 132, 34, 10],
        life=[14, 20], direction=[80, 100], speed=[0.3, 0.7], speed_curve=[(0, 1), (1, 0.5)],
        size=[0.6, 0.9], size_curve=[(0, 0.6), (1, 1.3)],
        colors=[(0, (225, 245, 255)), (1, (185, 215, 235))], alpha_curve=[(0, 0), (0.25, 0.55), (1, 0)])
# telegraph: glints from both sides accelerate into the centre and die before the bang
CONVERGE = dict(spawn=switch(0, 9), amount=[1, 2], life=[9, 11], speed=[3.4, 3.8],
                speed_curve=[(0, 0.4), (1, 1)], size=[0.6, 0.9], size_curve=[(0, 0.6), (1, 1)],
                colors=[(0, (150, 210, 255)), (1, (255, 255, 255))], alpha_curve=[(0, 0), (0.2, 1), (0.85, 1), (1, 0)])
emitter(g, "inL", "dot", "mist", area=[CX - 30, 141, 6, 3], direction=[0, 0], **CONVERGE)
emitter(g, "inR", "dot", "inL", area=[CX + 30, 141, 6, 3], direction=[180, 180], **CONVERGE)
emitter(g, "flash", "soft", "inR", spawn=switch(12, 14), amount=[1, 1], area=[CX, 136, 0, 0],
        life=[4, 4], direction=[90, 90], speed=[0, 0], speed_curve=[(0, 1), (1, 1)],
        size=[2.0, 2.0], size_curve=[(0, 0.7), (0.4, 1), (1, 1)],
        colors=[(0, (255, 255, 255)), (1, (200, 240, 255))], alpha_curve=[(0, 1), (1, 0)])

# pixel version: 6 ice tones + mist grey-blue
PIXEL_PALETTE = [(255, 255, 255), (205, 240, 255), (135, 205, 245), (80, 150, 225), (45, 95, 175),
                 (25, 50, 110), (165, 195, 220)]
# threshold 0.5: anti-aliased spike edges below that are darkened by premultiplied alpha and
# would snap to the darkest blue as a dotted outline
output_tail(g, "flash", PIXEL_PALETTE, HERE / "ice", FPS, threshold=0.5)
g.apply()
print(g.export(timeout=240))
