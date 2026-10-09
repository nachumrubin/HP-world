"""Builds the M1 Landscape heightmap from the layout.

    python Tools/make_heightmap.py            # writes Tools/generated/HPW_Heightmap_4033.{png,r16} + a shaded preview
    python Tools/make_heightmap.py --size 1009 --preview-only

Needs numpy and Pillow (pip install numpy pillow). See docs/M1_LANDSCAPE.md for the Unreal import settings.
"""

import argparse
import json
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import terrain  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "generated")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--size", type=int, default=4033, help="Landscape vertices per side (4033, 2017, 1009 ...)")
    parser.add_argument("--preview-only", action="store_true", help="skip the full-size png/r16")
    args = parser.parse_args()

    with open(os.path.join(HERE, "greybox_layout.json"), encoding="utf-8") as handle:
        layout = json.load(handle)
    land = layout["landscape"]
    extent, z_scale_cm = land["size_m"], land["z_scale_cm"]
    metres_per_count = z_scale_cm / 100.0 / 128.0

    height = terrain.make_height_function(layout)
    n = args.size
    axis = np.linspace(-extent / 2, extent / 2, n)
    field = np.empty((n, n), dtype=np.float32)  # [row = Y, column = X]
    for start in range(0, n, 256):
        rows = axis[start:start + 256]
        xs, ys = np.meshgrid(axis, rows)
        field[start:start + 256] = height(xs, ys, np)

    lo, hi = float(field.min()), float(field.max())
    limit = 32768 * metres_per_count  # half the representable range, in metres
    print(f"{n}x{n} vertices, {extent / (n - 1):.2f} m per vertex, height {lo:.1f} .. {hi:.1f} m (limit +/-{limit:.0f} m)")
    if lo < -limit or hi >= limit:
        sys.exit("Heights exceed the Landscape range; raise landscape.z_scale_cm in the layout.")

    os.makedirs(OUT_DIR, exist_ok=True)
    preview_step = max(1, n // 1024)
    small = field[::preview_step, ::preview_step]
    gy, gx = np.gradient(small, extent / (small.shape[0] - 1))
    light = np.clip(0.55 - 0.9 * (gx * 0.6 + gy * -0.8), 0.0, 1.0)  # light from the north-west
    rgb = np.empty(small.shape + (3,), dtype=np.float32)
    base = np.clip((small + 25.0) / 160.0, 0.0, 1.0)
    rgb[..., 0] = 0.30 + 0.55 * base
    rgb[..., 1] = 0.45 + 0.35 * base
    rgb[..., 2] = 0.25 + 0.55 * base
    lake = next(p for z in layout["zones"] for p in z["parts"] if p["label"] == "BlackLake")
    sx, sy = np.meshgrid(np.linspace(-extent / 2, extent / 2, small.shape[1]), np.linspace(-extent / 2, extent / 2, small.shape[0]))
    in_lake = np.zeros(small.shape, dtype=bool)
    for bx, by, br in lake["blobs"]:
        in_lake |= np.hypot(sx - bx, sy - by) < br
    water = in_lake & (small < 0.05)
    rgb[water] = (0.12, 0.30, 0.55)
    rgb *= (0.45 + 0.75 * light)[..., None]
    Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8)).save(os.path.join(OUT_DIR, "HPW_Heightmap_preview.png"))

    if not args.preview_only:
        counts = np.clip(np.rint(32768 + field / metres_per_count), 0, 65535).astype("<u2")
        stem = os.path.join(OUT_DIR, f"HPW_Heightmap_{n}")
        Image.fromarray(counts, mode="I;16").save(stem + ".png")
        counts.tofile(stem + ".r16")
        print(f"Wrote {stem}.png and .r16")
    print(f"Preview: {os.path.join(OUT_DIR, 'HPW_Heightmap_preview.png')}")


if __name__ == "__main__":
    main()
