"""Builds /Game/HPW/Landscape/M_HPW_Landscape (slope + height blended grass / rock / snow / shore) and assigns it to the level's Landscape.

Headless:  UnrealEditor-Cmd.exe HPWorld.uproject -run=pythonscript -script=Tools/Unreal/build_landscape_material_m1.py
Everything is procedural (no textures): slope from the vertex normal, height from world Z, so it needs no painted layers.
All thresholds and colours are material parameters, so they can be tuned on a material instance.
"""

import unreal

MAP = "/Game/HPW/Maps/M0_Greybox"
MAT_DIR = "/Game/HPW/Landscape"
MAT_NAME = "M_HPW_Landscape"

mel = unreal.MaterialEditingLibrary
ME = unreal.MaterialExpressionVertexNormalWS  # noqa: F841 (fail early if the API moved)


def make_material():
    path = f"{MAT_DIR}/{MAT_NAME}"
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        unreal.EditorAssetLibrary.delete_asset(path)
    tools = unreal.AssetToolsHelpers.get_asset_tools()
    mat = tools.create_asset(MAT_NAME, MAT_DIR, unreal.Material, unreal.MaterialFactoryNew())
    pos = [0, 0]

    def node(cls, **props):
        n = mel.create_material_expression(mat, cls, pos[0], pos[1])
        pos[1] += 120
        for k, v in props.items():
            n.set_editor_property(k, v)
        return n

    def link(src, dst, dst_in, src_out=""):
        mel.connect_material_expressions(src, src_out, dst, dst_in)
        return dst

    def scalar(name, value):
        return node(unreal.MaterialExpressionScalarParameter, parameter_name=name, default_value=value)

    def color(name, rgb):
        return node(unreal.MaterialExpressionVectorParameter, parameter_name=name,
                    default_value=unreal.LinearColor(rgb[0], rgb[1], rgb[2], 1.0))

    def ramp(value, start, end):
        """saturate((value - start) / (end - start))"""
        sub = link(value, node(unreal.MaterialExpressionSubtract), "A")
        link(start, sub, "B")
        span = link(end, node(unreal.MaterialExpressionSubtract), "A")
        link(start, span, "B")
        div = link(sub, node(unreal.MaterialExpressionDivide), "A")
        link(span, div, "B")
        return link(div, node(unreal.MaterialExpressionSaturate), "")

    def lerp(a, b, alpha):
        n = node(unreal.MaterialExpressionLinearInterpolate)
        link(a, n, "A")
        link(b, n, "B")
        link(alpha, n, "Alpha")
        return n

    # Slope: vertex normal Z (1 = flat, 0 = vertical).
    normal = node(unreal.MaterialExpressionVertexNormalWS)
    nz = link(normal, node(unreal.MaterialExpressionComponentMask, r=False, g=False, b=True, a=False), "")
    rock_mask = ramp(nz, scalar("RockSlopeFlat", 0.88), scalar("RockSlopeSteep", 0.62))
    # ramp goes 0 at flat -> 1 when steep: start > end gives a falling ramp, saturate clamps it.

    # Height in cm (world Z of the pixel).
    world = node(unreal.MaterialExpressionWorldPosition)
    z = link(world, node(unreal.MaterialExpressionComponentMask, r=False, g=False, b=True, a=False), "")
    snow_mask = ramp(z, scalar("SnowStartCm", 38000.0), scalar("SnowFullCm", 52000.0))
    shore_mask = ramp(z, scalar("ShoreTopCm", 40.0), scalar("ShoreBottomCm", -100.0))

    # Large-scale grass variation so the plains don't read as one flat colour.
    noise = node(unreal.MaterialExpressionNoise, scale=0.00004, quality=1, levels=3, output_min=0.0, output_max=1.0,
                 turbulence=False)
    link(world, noise, "Position")
    grass = lerp(color("GrassDark", (0.035, 0.09, 0.02)), color("GrassLight", (0.09, 0.17, 0.035)), noise)
    rock = color("Rock", (0.11, 0.10, 0.09))
    snow = color("Snow", (0.75, 0.78, 0.82))
    shore = color("Shore", (0.10, 0.075, 0.045))

    # Forbidden Forest: the layout scatters trees around (-50 m, 1500 m) with radius 950 m (UE cm: X = north, Y = east).
    # Far too few cones to read as a forest from the air, so the ground under them goes dark conifer green.
    xy = link(world, node(unreal.MaterialExpressionComponentMask, r=True, g=True, b=False, a=False), "")
    centre = node(unreal.MaterialExpressionConstant2Vector, r=-5000.0, g=150000.0)
    dist = link(xy, node(unreal.MaterialExpressionDistance), "A")
    link(centre, dist, "B")
    forest_mask = ramp(dist, scalar("ForestEdgeCm", 100000.0), scalar("ForestCoreCm", 60000.0))
    forest = color("ForestGround", (0.012, 0.04, 0.02))

    # West side (negative Y, the Hogsmeade side) is dry golden hill country on the illustrated map.
    wy = link(world, node(unreal.MaterialExpressionComponentMask, r=False, g=True, b=False, a=False), "")
    west = ramp(wy, scalar("OchreStartCm", -60000.0), scalar("OchreFullCm", -220000.0))
    grass = lerp(grass, color("GrassDry", (0.2, 0.15, 0.04)), west)

    base = lerp(grass, rock, rock_mask)
    base = lerp(base, forest, forest_mask)
    # snow settles on flatter high ground, not on near-vertical faces
    snow_amount = link(snow_mask, node(unreal.MaterialExpressionMultiply), "A")
    link(ramp(nz, scalar("SnowSlopeMax", 0.35), scalar("SnowSlopeFull", 0.7)), snow_amount, "B")
    base = lerp(base, snow, snow_amount)
    base = lerp(base, shore, shore_mask)

    mel.connect_material_property(base, "", unreal.MaterialProperty.MP_BASE_COLOR)
    mel.connect_material_property(node(unreal.MaterialExpressionConstant, r=0.92), "", unreal.MaterialProperty.MP_ROUGHNESS)
    mel.recompile_material(mat)
    unreal.EditorAssetLibrary.save_loaded_asset(mat)
    return mat


mat = make_material()
unreal.EditorLevelLibrary.load_level(MAP)
count = 0
for actor in unreal.EditorLevelLibrary.get_all_level_actors():
    if isinstance(actor, unreal.LandscapeProxy):
        actor.set_editor_property("landscape_material", mat)
        count += 1
if count:
    unreal.EditorLevelLibrary.save_current_level()
unreal.log(f"HPW: landscape material built, assigned to {count} landscape actor(s)")
