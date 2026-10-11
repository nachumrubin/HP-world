"""Builds /Game/HPW/Castle/M_CastleStone and assigns it to every imported castle mesh (/Game/HPW/Castle/hogwarts_castle/StaticMeshes).

The castle model ("Hogwarts castle" by jvasishta2013, CC-BY 4.0) has no textures and only one flat material, so the stone is procedural:
steep/vertical surfaces get dressed stone (courses and blocks from world position, each block a slightly different tone, grime lower down),
surfaces that face up (tower cones, flat tops) get dark slate. Detail fades out with distance so it does not shimmer from the air.
Set "material": null on the castle_model part of Tools/greybox_layout.json and rebuild the level, so the actors use the mesh's own slots.

Headless:  UnrealEditor-Cmd.exe HPWorld.uproject -run=pythonscript -script=Tools/Unreal/build_castle_material_m2.py
"""

import os

import unreal

MAT_DIR = "/Game/HPW/Castle"
MAT_NAME = "M_CastleStone"
MESH_DIR = "/Game/HPW/Castle/hogwarts_castle/StaticMeshes"

mel = unreal.MaterialEditingLibrary
path = f"{MAT_DIR}/{MAT_NAME}"
if unreal.EditorAssetLibrary.does_asset_exist(path):
    unreal.EditorAssetLibrary.delete_asset(path)
mat = unreal.AssetToolsHelpers.get_asset_tools().create_asset(MAT_NAME, MAT_DIR, unreal.Material, unreal.MaterialFactoryNew())
pos = [0, 0]


def node(cls, **props):
    n = mel.create_material_expression(mat, cls, pos[0], pos[1])
    pos[1] += 110
    for k, v in props.items():
        n.set_editor_property(k, v)
    return n


def link(src, dst, dst_in, src_out=""):
    mel.connect_material_expressions(src, src_out, dst, dst_in)
    return dst


def const(v):
    return node(unreal.MaterialExpressionConstant, r=v)


def scalar(name, value):
    return node(unreal.MaterialExpressionScalarParameter, parameter_name=name, default_value=value)


def color(name, rgb):
    return node(unreal.MaterialExpressionVectorParameter, parameter_name=name, default_value=unreal.LinearColor(rgb[0], rgb[1], rgb[2], 1.0))


def binary(cls, a, b):
    n = node(cls)
    link(a, n, "A")
    link(b, n, "B")
    return n


def mul(a, b):
    return binary(unreal.MaterialExpressionMultiply, a, b if not isinstance(b, (int, float)) else const(b))


def add(a, b):
    return binary(unreal.MaterialExpressionAdd, a, b if not isinstance(b, (int, float)) else const(b))


def sub(a, b):
    return binary(unreal.MaterialExpressionSubtract, a, b if not isinstance(b, (int, float)) else const(b))


def ramp(value, start, end):
    """saturate((value - start) / (end - start)); start > end gives a falling ramp."""
    span = const(end - start)
    return link(binary(unreal.MaterialExpressionDivide, sub(value, start), span), node(unreal.MaterialExpressionSaturate), "")


def lerp(a, b, alpha):
    n = node(unreal.MaterialExpressionLinearInterpolate)
    link(a, n, "A")
    link(b, n, "B")
    link(alpha, n, "Alpha")
    return n


def channel(vec, r=False, g=False, b=False, a=False):
    return link(vec, node(unreal.MaterialExpressionComponentMask, r=r, g=g, b=b, a=a), "")


def frac(v):
    return link(v, node(unreal.MaterialExpressionFrac), "")


def floor(v):
    return link(v, node(unreal.MaterialExpressionFloor), "")


def edge_line(fraction, width):
    """1 on a thin line where the 0..1 fraction wraps (a mortar joint), else 0."""
    centred = link(sub(mul(fraction, 2.0), 1.0), node(unreal.MaterialExpressionAbs), "")  # 0 mid-block .. 1 at the joint
    return ramp(centred, 1.0 - width * 2.0, 1.0 - width)


world = node(unreal.MaterialExpressionWorldPosition)
wx = channel(world, r=True)
wy = channel(world, g=True)
wz = channel(world, b=True)
normal = node(unreal.MaterialExpressionPixelNormalWS)
nz = channel(normal, b=True)
depth = node(unreal.MaterialExpressionPixelDepth)

# Close-up detail strength: full inside 150 m, gone beyond 500 m.
near = ramp(depth, 50000.0, 15000.0)

# Walls: courses 2.5 m high, blocks 5 m wide, every other course shifted by half a block.
course = mul(wz, 1.0 / 250.0)
row = floor(course)
along = mul(add(wx, wy), 1.0 / 500.0)
shifted = add(along, mul(frac(mul(row, 0.5)), 1.0))  # 0 or 0.5 depending on the row's parity
col = floor(shifted)
mortar = binary(unreal.MaterialExpressionMax, edge_line(frac(course), 0.04), edge_line(frac(shifted), 0.03))
block_id = link(row, node(unreal.MaterialExpressionAppendVector), "A")
link(col, block_id, "B")
hash_dot = link(block_id, node(unreal.MaterialExpressionDotProduct), "A")
link(node(unreal.MaterialExpressionConstant2Vector, r=12.9898, g=78.233), hash_dot, "B")
block_tone = frac(mul(link(hash_dot, node(unreal.MaterialExpressionSine), ""), 43758.5453))

# Large-scale variation (streaks, patches) and grime that is heavier lower down.
patch = node(unreal.MaterialExpressionNoise, scale=0.004, quality=1, levels=4, output_min=0.0, output_max=1.0, turbulence=False)
link(world, patch, "Position")
grime = ramp(wz, 24000.0, 9500.0)  # castle base is about 95 m up

stone_dark = color("StoneDark", (0.045, 0.038, 0.03))
stone_light = color("StoneLight", (0.13, 0.105, 0.075))
mortar_color = color("Mortar", (0.045, 0.04, 0.035))
tone_mix = add(mul(block_tone, 0.55), mul(patch, 0.45))
stone_avg = lerp(stone_dark, stone_light, patch)
stone_detail = lerp(stone_dark, stone_light, tone_mix)
stone_detail = lerp(stone_detail, mortar_color, mul(mortar, 0.8))
wall = lerp(stone_avg, stone_detail, near)
wall = lerp(wall, color("Grime", (0.03, 0.032, 0.03)), mul(grime, 0.6))

# Roofs: dark blue-grey slate, with rows of tiles close up.
slate_dark = color("SlateDark", (0.018, 0.022, 0.03))
slate_light = color("SlateLight", (0.06, 0.07, 0.09))
tile_rows = edge_line(frac(mul(wz, 1.0 / 60.0)), 0.06)
slate_mix = add(mul(patch, 0.7), mul(block_tone, 0.0))
slate = lerp(slate_dark, slate_light, slate_mix)
slate = lerp(slate, slate_dark, mul(mul(tile_rows, near), 0.7))

roof_mask = ramp(nz, 0.3, 0.5)
base = lerp(wall, slate, roof_mask)

rough = const(0.88)
mat.set_editor_property("two_sided", True)
mel.connect_material_property(base, "", unreal.MaterialProperty.MP_BASE_COLOR)
mel.connect_material_property(rough, "", unreal.MaterialProperty.MP_ROUGHNESS)
mel.recompile_material(mat)
unreal.EditorAssetLibrary.save_loaded_asset(mat)

folder = os.path.join(unreal.SystemLibrary.get_project_directory(), "Content", MESH_DIR[len("/Game/"):])
names = sorted(f[:-len(".uasset")] for f in os.listdir(folder) if f.endswith(".uasset"))
for name in names:
    mesh = unreal.load_asset(f"{MESH_DIR}/{name}")
    for slot in range(len(mesh.get_editor_property("static_materials"))):
        mesh.set_material(slot, mat)
    unreal.EditorAssetLibrary.save_loaded_asset(mesh)
unreal.log(f"HPW: castle stone material built and assigned to {len(names)} meshes")
