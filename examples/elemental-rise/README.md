# Elemental rise effects

Skill effects that erupt from the ground under an enemy, in a 2D side-view game: fire (explosive
burst), ice (spikes), water (column). Each element comes in a pixel-art and an illustrated style,
as one-shot PNG sprite sheets.

All three share one casting rhythm: energy gathers on the ground (frames 0-11), everything goes off
at once on frame 12, the effect holds, then dissipates.

## Sheets

Frame size 128x160 for all, ground line at y=144 (the effect's base). The sheets are grids read left
to right, top to bottom. The pixel sheets take every 2nd frame of the same animation, so pixel frame
n = illustration frame 2n.

| File | Frames | fps | Grid | Sheet size | Hit frame |
|---|---|---|---|---|---|
| `fire_illust.png` | 60 | 24 | 10x6 | 1280x960 | 17 |
| `fire_pixel.png` | 30 | 12 | 10x3 | 1280x480 | 8 |
| `ice_illust.png` | 60 | 24 | 10x6 | 1280x960 | 13 |
| `ice_pixel.png` | 30 | 12 | 10x3 | 1280x480 | 7 |
| `water_illust.png` | 60 | 24 | 10x6 | 1280x960 | 13 |
| `water_pixel.png` | 30 | 12 | 10x3 | 1280x480 | 7 |

Hit frame = the first frame where the effect is over ~100 px tall. For a hit on the bang itself,
use frame 12 (pixel 6). `*.gif` are previews of the same animations.

Pixel sheets have hard alpha (0 or 255) and 6-7 colours. Illustrated sheets have soft alpha and
baked-in bloom. Both use normal alpha blending.

### Check results

`check_sheet` (frame count, empty frames, edges, height 100-140 px, peak frame window, ground
contact; for pixel sheets also binary alpha and at most 8 colours):

```
fire_illust.png   ok  frames 60  peak_frame 21  peak_height 132
fire_pixel.png    ok  frames 30  peak_frame 11  peak_height 127  colours 7
ice_illust.png    ok  frames 60  peak_frame 14  peak_height 116
ice_pixel.png     ok  frames 30  peak_frame 7   peak_height 113  colours 7
water_illust.png  ok  frames 60  peak_frame 22  peak_height 122
water_pixel.png   ok  frames 30  peak_frame 11  peak_height 122  colours 6
```

## Rebuilding

Each `build_<element>.py` builds `<element>.pxc` from scratch in a running Pixel Composer (it
starts one if needed), sets every value, and exports the sheets and GIFs:

```
uv run python examples/elemental-rise/build_fire.py
```

Particles are not seeded, so a rebuild is similar but not identical; check it again with
`check_sheet`. To re-export an existing project without rebuilding it, use the MCP tools
`open_project("examples/elemental-rise/fire.pxc")` and then `export()`.

## What to change

All values live in the build scripts. `pxgraph.py` holds the shared parts: `emitter()` (one
particle layer) and `output_tail()` (pixel/illustration branches, sheets, GIFs).

- **Timing.** Particle layers spawn only inside their `switch(on, off)` window (frames). Shapes move
  through keyframe lists `[(frame, value), ...]`. The bang is frame 12 everywhere.
- **Fire height:** `core` emitter `speed` (`[10, 22]`) and `life`. **Fire spread:** `blast`
  `direction`/`speed`.
- **Ice height:** the third value in each `SPIKES` row (centre spike 118). **Ice rise speed:**
  `LEAD`/`TRAIL`. **Ice crumble:** `CRUMBLE`.
- **Water height:** `HEIGHT` (104) plus the `crown` emitter `speed`. **Water rise/collapse:**
  `COLUMN`.
- **Colours:** the gradient lists per emitter, the shape colours, and `PIXEL_PALETTE` for the pixel
  sheets.
- **Pixel threshold:** `output_tail(..., threshold=)`. Fire uses 0.2; ice and water use 0.5,
  because anti-aliased shape edges below that turn into a dark dotted outline.
