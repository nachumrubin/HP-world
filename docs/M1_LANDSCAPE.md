# M1 — Landscape step

Replaces the flat greybox ground, the Owlery and Shrieking Shack hills and the cone mountains with a sculpted Landscape.
The terrain is defined in code (`Tools/terrain.py`), so it can be tuned and regenerated, and buildings keep matching it.

## 1. Generate the heightmap

```sh
pip install numpy pillow
python Tools/make_heightmap.py
```

Writes `Tools/generated/HPW_Heightmap_4033.png` (and `.r16`) plus `HPW_Heightmap_preview.png` (a shaded top-down view, north = right,
east = down). `--size 1009 --preview-only` is a fast check. Heights span -22 m (lake bed) to about 690 m (highland peaks).

## 2. Import it in Unreal (once)

1. Open `M0_Greybox`. Switch to **Landscape** mode (Shift+2) > **Manage** > **New** > **Import from File**.
2. Heightmap file: `Tools/generated/HPW_Heightmap_4033.png` (or the `.r16`, resolution 4033 x 4033).
3. Scale: **X = 173.6111, Y = 173.6111, Z = 300**. Location: **X = -350000, Y = -350000, Z = 0** (the Landscape corner; this centres the
   7 km map on the castle). Accept the suggested section size and component count for 4033 (63 quads, 64 x 64 components).
4. Layers: leave empty for now, then **Import**. Assign a grass/rock material later in M1 (slope-based).
5. Save. In the layout set `"landscape": { "imported": true }` in `Tools/greybox_layout.json`.

## 3. Rebuild the greybox on top of it

Run `Tools/Unreal/build_greybox_m0.py` again. With `imported: true` it skips the parts tagged `terrain` (ground box, hills, mountains, lake
island) and stands trees and Hogsmeade houses on the Landscape. Buildings, tower plinths and the viaduct already sit at the heights the
terrain produces (castle plateau 60 m, flat pads under the pitch, village, Hagrid's hut, greenhouses and gates).

The Black Lake water disc stays a greybox plane at z = 0.05; the basin is 22 m deep. The Water plugin replaces it later.

## Tuning

Edit the constants and features in `Tools/terrain.py` (`PADS`, `LAKE_DEPTH`, `CLIFF_HEIGHT`, noise amplitudes), regenerate, then re-import with
**Import from File** on the existing Landscape (Manage > Import) rather than creating a new one.

## Still to do in M1

World Partition conversion, per-zone blockout detail, Landscape material, landmark readability check from altitude.
