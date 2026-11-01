"""Build fire.pxc: an explosive flame burst erupting from the ground line, two styles.

Canvas 128x160, ground y=144, 60 frames @ 24 fps. Timeline: telegraph 0-11 (energy condenses:
embers converge on the centre while the ground glow shrinks and sharpens), bang at 12 (flash,
column and sideways blast spawned in 2 frames), rolling flame to ~32, smoke and falling embers to 59.
Layers are chained through each particle node's Background input (back to front).
Illustration = the chain's output; pixel = alpha threshold + 6-colour hard gradient map + De-Stray,
sampled every 2nd frame (12 fps).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from pixel_composer_mcp.app import Instance  # noqa: E402
from pixel_composer_mcp.graph import Graph, color, emitter, new_project, switch  # noqa: E402
from pxgraph import TAIL_NODES, output_tail  # noqa: E402

HERE = Path(__file__).parent
W, H, FRAMES, FPS, GROUND, CX = 128, 160, 60, 24, 144, 64


inst = Instance()
path = new_project(HERE / "fire.pxc", W, H, FRAMES, FPS)
g = Graph(inst, path)
g.add({
    "blob": ("Node_Shape", 0, 0), "soft": ("Node_Blur", 160, 0), "dot": ("Node_Shape", 0, 160),
    "tongue": ("Node_Shape", 0, 480), "tongsoft": ("Node_Blur", 160, 480),
    "glow": ("Node_Shape", 0, 320), "glowsoft": ("Node_Blur", 160, 320),
    "smoke": ("Node_Particle", 320, 0), "hold": ("Node_Particle", 480, 0), "core": ("Node_Particle", 640, 0),
    "sparks": ("Node_Particle", 800, 0), "inL": ("Node_Particle", 960, 0), "inR": ("Node_Particle", 960, 160),
    "blast": ("Node_Particle", 480, 160), "flash": ("Node_Particle", 960, 320),
    **TAIL_NODES,
})

# sprites: soft round blob, tall flame tongue, small hard dot
g.dim("blob", 0, [32, 32]).set("blob", 17, [0.3, 0.3]).set("blob", 2, "Ellipse").set("blob", 1, 0).set("blob", 6, True)
g.link("blob", "soft", 0).set("soft", 1, 4)
g.dim("tongue", 0, [24, 40]).set("tongue", 17, [0.28, 0.4]).set("tongue", 2, "Ellipse").set("tongue", 1, 0).set("tongue", 6, True)
g.link("tongue", "tongsoft", 0).set("tongsoft", 1, 4)
g.dim("dot", 0, [6, 6]).set("dot", 17, [0.35, 0.35]).set("dot", 2, "Ellipse").set("dot", 1, 0).set("dot", 6, True)

# ground glow: wide and diffuse -> tight and hot during the telegraph (condensing), flashes wide on the bang
g.set("glow", 2, "Ellipse").set("glow", 1, 0).set("glow", 6, True).set("glow", 15, 1)
g.set("glow", 16, [CX, GROUND], absolute=True).set("glow", 10, color(255, 170, 80))
g.anim("glow", 17, [(0, [30, 4]), (11, [5, 2]), (12, [32, 4]), (16, [34, 5]), (26, [10, 2]), (30, [0, 0])], absolute=True)
g.link("glow", "glowsoft", 0).anim("glowsoft", 1, [(0, 6), (11, 2), (12, 6)])  # >6 wraps the ground glow to the top row

FIRE = [(0, (255, 250, 220)), (0.2, (255, 220, 90)), (0.45, (255, 140, 40)), (0.7, (230, 70, 30)), (1, (150, 30, 30))]
emitter(g, "smoke", "soft", "glowsoft", spawn=switch(20, 50), amount=[1, 2], area=[CX, 122, 16, 14],
        life=[16, 22], direction=[80, 100], speed=[0.3, 0.8], speed_curve=[(0, 1), (1, 0.5)],
        size=[1.0, 1.4], size_curve=[(0, 0.6), (1, 1.3)],
        colors=[(0, (190, 140, 120)), (1, (140, 120, 125))], alpha_curve=[(0, 0), (0.25, 0.6), (1, 0)])
emitter(g, "hold", "tongsoft", "smoke", spawn=switch(16, 34), amount=[3, 4], area=[CX, 141, 16, 2],
        life=[10, 16], direction=[82, 98], speed=[4, 7], speed_curve=[(0, 1), (1, 0.3)],
        size=[0.6, 0.9], size_curve=[(0, 0.5), (0.3, 1), (1, 0.3)],
        colors=FIRE, alpha_curve=[(0, 1), (0.75, 0.9), (1, 0)])
# the bang: everything below spawns in frames 12-13 only
emitter(g, "blast", "soft", "hold", spawn=switch(12, 14), amount=[8, 10], area=[CX, 140, 4, 2],
        life=[10, 14], direction=[20, 160], speed=[9, 11], speed_curve=[(0, 1), (0.3, 0.25), (1, 0.05)],
        size=[0.7, 1.0], size_curve=[(0, 0.6), (0.3, 1.1), (1, 0.3)],
        colors=FIRE, alpha_curve=[(0, 1), (0.6, 0.9), (1, 0)])
# wide speed range: particles spawned together still stretch into one column instead of a lump
emitter(g, "core", "tongsoft", "blast", spawn=switch(12, 14), amount=[22, 26], area=[CX, 143, 12, 2],
        life=[8, 13], direction=[80, 100], speed=[10, 22], speed_curve=[(0, 1), (0.5, 0.35), (1, 0.15)],
        size=[0.9, 1.3], size_curve=[(0, 0.5), (0.25, 1.15), (1, 0.35)],
        colors=FIRE, alpha_curve=[(0, 1), (0.6, 0.9), (1, 0)])
emitter(g, "sparks", "dot", "core", spawn=switch(12, 16), amount=[3, 5], area=[CX, 140, 10, 4],
        life=[30, 44], direction=[72, 108], speed=[3, 5], speed_curve=[(0, 1), (1, 0.4)],
        size=[0.6, 1.0], size_curve=[(0, 1), (1, 0.6)],
        colors=[(0, (255, 250, 200)), (0.5, (255, 180, 60)), (1, (220, 70, 30))],
        alpha_curve=[(0, 1), (0.8, 1), (1, 0)], gravity=[0.3, 0.4])
# telegraph: embers from both sides accelerate into the centre and die before the bang
# (spread comes from the area height, not the angle, so directions stay exactly 0 / 180)
CONVERGE = dict(spawn=switch(0, 9), amount=[1, 2], life=[9, 11], speed=[3.4, 3.8],
                speed_curve=[(0, 0.4), (1, 1)], size=[0.6, 0.9], size_curve=[(0, 0.6), (1, 1)],
                colors=[(0, (255, 160, 60)), (1, (255, 240, 170))], alpha_curve=[(0, 0), (0.2, 1), (0.85, 1), (1, 0)])
emitter(g, "inL", "dot", "sparks", area=[CX - 30, 141, 6, 3], direction=[0, 0], **CONVERGE)
emitter(g, "inR", "dot", "inL", area=[CX + 30, 141, 6, 3], direction=[180, 180], **CONVERGE)
# white flash on the bang frame, in front of everything
emitter(g, "flash", "soft", "inR", spawn=switch(12, 14), amount=[1, 1], area=[CX, 136, 0, 0],
        life=[4, 4], direction=[90, 90], speed=[0, 0], speed_curve=[(0, 1), (1, 1)],
        size=[2.0, 2.0], size_curve=[(0, 0.7), (0.4, 1), (1, 1)],
        colors=[(0, (255, 255, 240)), (1, (255, 230, 140))], alpha_curve=[(0, 1), (1, 0)])

# pixel version: hard alpha, snap to a 7-colour palette (2 smoke greys + 5 fire), remove stray pixels
PIXEL_PALETTE = [(110, 90, 100), (165, 135, 130), (150, 35, 35), (225, 75, 35), (255, 145, 45),
                 (255, 215, 95), (255, 250, 215)]
output_tail(g, "flash", PIXEL_PALETTE, HERE / "fire", FPS)
g.apply()
print(g.export(timeout=240))
