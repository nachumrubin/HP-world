"""Terrain height function for the M1 Landscape, derived from Tools/greybox_layout.json.

One definition of the ground, used twice:
  * Tools/make_heightmap.py evaluates it over a grid (numpy) and writes the Landscape heightmap.
  * Tools/Unreal/build_greybox_m0.py evaluates it at single points (pure Python, the editor has no numpy)
    to stand scatter objects like trees and houses on the Landscape once it has been imported.

Metres. Origin = centre of the castle. +X = north, +Y = east, +Z = up (same as the layout).
Everything is written with `where` instead of `if` so the same code works on floats and numpy arrays.
"""

import math
import random

try:
    import numpy as _np
except ImportError:  # inside the Unreal editor
    _np = None


class _Scalar:
    """The few numpy functions the height code needs, for plain floats."""
    pi = math.pi
    sin = staticmethod(math.sin)
    cos = staticmethod(math.cos)
    exp = staticmethod(math.exp)
    sqrt = staticmethod(math.sqrt)
    floor = staticmethod(math.floor)
    abs = staticmethod(abs)
    minimum = staticmethod(min)
    maximum = staticmethod(max)
    where = staticmethod(lambda cond, a, b: a if cond else b)
    clip = staticmethod(lambda v, lo, hi: min(max(v, lo), hi))
    hypot = staticmethod(math.hypot)


PAD_H = 0.6  # building pads sit just above the lake surface (z=0) so they never read as shore or flood
LAND_MIN = 1.0  # dry ground never dips below this outside the lake basin

# Flat pads: (label, x, y, radius, blend, height). Buildings in the layout sit at z=0 (or on their own plinth), so the
# ground is forced flat there, melting back into the rolling terrain over `blend` metres.
PADS = [
    ("QuidditchPitch", 975, -100, 130, 90, PAD_H),
    ("Hogsmeade", 1560, -2235, 230, 120, PAD_H),
    ("HogsmeadeStation", -450, -1365, 55, 60, PAD_H),
    ("HagridsHut", 650, 460, 30, 40, PAD_H),
    ("Greenhouses", 243, 500, 55, 50, PAD_H),
    ("StoneCircle", -250, 450, 32, 40, PAD_H),
    ("WhompingWillow", 503, 434, 24, 40, PAD_H),
    ("Gates", 1086, 80, 30, 50, PAD_H),
    ("Boathouse", -272, 80, 17, 24, 0.5),  # a landing cut into the foot of the cliff
]

LAKE_DEPTH = -22.0
CLIFF_HEIGHT = 60.0


def _ns(xp):
    return xp if xp is not None else _Scalar


def smoothstep(e0, e1, v, xp):
    t = xp.clip((v - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _hash(ix, iy, seed, xp):
    s = xp.sin(ix * 127.1 + iy * 311.7 + seed * 74.7) * 43758.5453
    return s - xp.floor(s)


def value_noise(x, y, seed, xp):
    """Smooth 2D value noise in 0..1, lattice spacing 1."""
    x0, y0 = xp.floor(x), xp.floor(y)
    fx, fy = x - x0, y - y0
    fx, fy = fx * fx * (3.0 - 2.0 * fx), fy * fy * (3.0 - 2.0 * fy)
    a, b = _hash(x0, y0, seed, xp), _hash(x0 + 1, y0, seed, xp)
    c, d = _hash(x0, y0 + 1, seed, xp), _hash(x0 + 1, y0 + 1, seed, xp)
    return (a + (b - a) * fx) + ((c + (d - c) * fx) - (a + (b - a) * fx)) * fy


def fbm(x, y, wavelength, octaves, seed, xp):
    """Fractal noise in roughly -1..1."""
    total, amp, norm, freq = 0.0, 1.0, 0.0, 1.0 / wavelength
    for i in range(octaves):
        total = total + (value_noise(x * freq, y * freq, seed + i * 13, xp) * 2.0 - 1.0) * amp
        norm += amp
        amp *= 0.5
        freq *= 2.0
    return total / norm


def mountain_specs(layout):
    """Re-derives the mountain ring with the same RNG the greybox cones use, so both agree on where peaks are."""
    part = next(p for z in layout["zones"] for p in z["parts"] if p["type"] == "mountains")
    rng = random.Random(part["seed"])
    r_min, r_max = part["radius"]
    specs = []
    for i in range(part["count"]):
        angle = 2 * math.pi * (i + rng.uniform(-0.3, 0.3)) / part["count"]
        r = rng.uniform(r_min, r_max)
        d = rng.uniform(*part["diameter"])
        h = rng.uniform(*part["height"])
        specs.append((r * math.cos(angle), r * math.sin(angle), d / 2, h))
    return specs


def find_part(layout, label):
    return next(p for z in layout["zones"] for p in z["parts"] if p["label"] == label)


def dome(x, y, cx, cy, radius, peak, xp):
    dist = xp.hypot(x - cx, y - cy)
    t = xp.clip(dist / radius, 0.0, 1.0)
    return peak * (0.5 + 0.5 * xp.cos(xp.pi * t))


def make_height_function(layout):
    """Returns height(x, y, xp=None) in metres. xp is numpy for arrays, or None for single floats."""
    mountains = mountain_specs(layout)
    owlery = find_part(layout, "OwleryHill")
    shack = find_part(layout, "ShriekingShackHill")
    blobs = find_part(layout, "BlackLake")["blobs"]
    island = find_part(layout, "LakeIsland")
    castle = find_part(layout, "CastleCliff")

    half_x, half_y = castle["size"][0] / 2, castle["size"][1] / 2

    def height(x, y, xp=None):
        xp = _ns(xp if xp is not None else (_np if _np is not None and hasattr(x, "shape") else None))
        r_center = xp.hypot(x, y)

        # Rolling Scottish ground: gentle everywhere, livelier in the forest valley and the highlands.
        rolling = 3.5 + fbm(x, y, 260.0, 4, 11, xp) * 2.5  # sits above the lake surface (z=0) everywhere on land
        forest_dist = xp.hypot(x + 50.0, y - 1500.0)
        forest_w = 1.0 - smoothstep(500.0, 1100.0, forest_dist, xp)
        hills = fbm(x, y, 420.0, 4, 23, xp) * 7.0 * forest_w
        valley = -1.0 * forest_w
        highland_rise = 45.0 * smoothstep(1800.0, 3300.0, r_center, xp)
        h = xp.maximum(rolling + hills + valley, LAND_MIN) + highland_rise

        # Dome hills for the Owlery and the Shrieking Shack.
        for part in (owlery, shack):
            cx, cy = part["center"]
            h = xp.maximum(h, dome(x, y, cx, cy, part["diameter"] / 2, part["height"], xp))

        # Mountains: the greybox cones, roughened with ridged noise.
        ridge = 1.0 + 0.30 * fbm(x, y, 220.0, 4, 37, xp)
        for mx, my, mr, mh in mountains:
            t = xp.clip(1.0 - xp.hypot(x - mx, y - my) / mr, 0.0, 1.0)
            h = xp.maximum(h, mh * (t ** 1.25) * ridge * smoothstep(0.0, 0.08, t, xp))

        # Black Lake basin with a soft bank, plus the island.
        rn = None  # normalised distance to the nearest lake circle: < 1 is inside the lake
        for bx, by, br in blobs:
            r_i = xp.hypot(x - bx, y - by) / br
            rn = r_i if rn is None else xp.minimum(rn, r_i)
        basin = 1.0 - smoothstep(0.55, 1.02, rn, xp)
        h = h * (1.0 - basin) + LAKE_DEPTH * basin
        ix, iy = island["center"]
        island_dome = LAKE_DEPTH + (island["height"] - LAKE_DEPTH) * (
            0.5 + 0.5 * xp.cos(xp.pi * xp.clip(xp.hypot(x - ix, y - iy) / 48.0, 0.0, 1.0)))
        h = xp.maximum(h, island_dome)

        # Castle cliff: a squared-off plateau, steep over the lake and gentler on the landward side.
        d = ((xp.abs(x) / half_x) ** 6 + (xp.abs(y) / half_y) ** 6) ** (1.0 / 6.0)
        width = 0.08 + 0.17 * smoothstep(-1.0, 1.0, x / half_x, xp)
        plateau = CLIFF_HEIGHT * (1.0 - smoothstep(1.0, 1.0 + width, d, xp))
        crag = fbm(x, y, 30.0, 3, 51, xp) * 5.0 * smoothstep(0.7, 1.0, d, xp) * (1.0 - smoothstep(1.0, 1.3, d, xp))
        h = xp.where(plateau > 0.01, xp.maximum(h, plateau + crag * (plateau > 1.0)), h)

        # Flat pads under the buildings.
        for _, px, py, radius, blend, pad_h in PADS:
            w = 1.0 - smoothstep(radius, radius + blend, xp.hypot(x - px, y - py), xp)
            h = h * (1.0 - w) + pad_h * w
        return h

    return height
