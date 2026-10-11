"""Builds the Black Lake's materials in /Game/HPW/Lake:

M_BlackLake - translucent water that is murky olive in the shallows and nearly black where it is deep (the opacity and the colour come from how far
              the lake bed is below the surface), with slowly drifting swell and ripple normals and a cold grazing-angle sky glint.
M_LakeMist  - unlit cold mist sheets with drifting noise, faded where they meet the ground or the water.

Tools/Unreal/build_greybox_m0.py picks them up when they exist (the "water" and "mist" materials), so run this before it.

Headless:  UnrealEditor-Cmd.exe HPWorld.uproject -run=pythonscript -script=Tools/Unreal/build_lake_materials_m2.py
"""

import unreal

DEST = "/Game/HPW/Lake"
mel = unreal.MaterialEditingLibrary
tools = unreal.AssetToolsHelpers.get_asset_tools()
if not unreal.EditorAssetLibrary.does_directory_exist(DEST):
    unreal.EditorAssetLibrary.make_directory(DEST)


class Graph:
    def __init__(self, name):
        path = f"{DEST}/{name}"
        if unreal.EditorAssetLibrary.does_asset_exist(path):
            self.mat = unreal.load_asset(path)  # rebuilt in place so the level's material instances keep their parent
            mel.delete_all_material_expressions(self.mat)
        else:
            self.mat = tools.create_asset(name, DEST, unreal.Material, unreal.MaterialFactoryNew())
        self.y = 0

    def node(self, cls, **props):
        n = mel.create_material_expression(self.mat, cls, -800, self.y)
        self.y += 110
        for k, v in props.items():
            n.set_editor_property(k, v)
        return n

    def link(self, src, dst, dst_in, src_out=""):
        mel.connect_material_expressions(src, src_out, dst, dst_in)
        return dst

    def const(self, v):
        return self.node(unreal.MaterialExpressionConstant, r=v)

    def vec(self, rgb):
        return self.node(unreal.MaterialExpressionConstant3Vector, constant=unreal.LinearColor(rgb[0], rgb[1], rgb[2], 1.0))

    def param(self, name, rgb):
        return self.node(unreal.MaterialExpressionVectorParameter, parameter_name=name, default_value=unreal.LinearColor(rgb[0], rgb[1], rgb[2], 1.0))

    def op(self, cls, a, b):
        n = self.node(cls)
        self.link(a, n, "A")
        self.link(b, n, "B")
        return n

    def mul(self, a, b):
        return self.op(unreal.MaterialExpressionMultiply, a, self.const(b) if isinstance(b, (int, float)) else b)

    def add(self, a, b):
        return self.op(unreal.MaterialExpressionAdd, a, self.const(b) if isinstance(b, (int, float)) else b)

    def sub(self, a, b):
        return self.op(unreal.MaterialExpressionSubtract, a, self.const(b) if isinstance(b, (int, float)) else b)

    def lerp(self, a, b, alpha):
        n = self.node(unreal.MaterialExpressionLinearInterpolate)
        self.link(a, n, "A")
        self.link(b, n, "B")
        self.link(alpha, n, "Alpha")
        return n

    def saturate(self, v):
        return self.link(v, self.node(unreal.MaterialExpressionSaturate), "")

    def noise(self, position, scale, levels):
        n = self.node(unreal.MaterialExpressionNoise, scale=scale, quality=1, levels=levels, output_min=-1.0, output_max=1.0, turbulence=False)
        return self.link(position, n, "Position")

    def finish(self, props):
        for prop, node in props.items():
            mel.connect_material_property(node, "", prop)
        mel.recompile_material(self.mat)
        unreal.EditorAssetLibrary.save_loaded_asset(self.mat)


# ---------------------------------------------------------------------------------------------------------------------------------------------
# Water
# ---------------------------------------------------------------------------------------------------------------------------------------------
g = Graph("M_BlackLake")
g.mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
g.mat.set_editor_property("translucency_lighting_mode", unreal.TranslucencyLightingMode.TLM_SURFACE_PER_PIXEL_LIGHTING)
g.mat.set_editor_property("two_sided", True)

world = g.node(unreal.MaterialExpressionWorldPosition)
time = g.node(unreal.MaterialExpressionTime)


def drifting(direction, shift):
    """World position moved by direction (cm/s) over time, plus a fixed shift so each noise call is independent."""
    return g.add(g.add(world, g.mul(time, g.vec(direction))), g.vec(shift))


# Slow broad swell plus finer ripples, travelling in different directions. Two noise values make the x and y slope of the surface.
swell_x = g.noise(drifting((18, 7, 0), (0, 0, 0)), 0.0015, 2)
swell_y = g.noise(drifting((18, 7, 0), (7300, 4100, 0)), 0.0015, 2)
ripple_x = g.noise(drifting((-30, 22, 0), (1900, 5200, 0)), 0.005, 2)
ripple_y = g.noise(drifting((-30, 22, 0), (8800, 300, 0)), 0.005, 2)
slope_x = g.add(g.mul(swell_x, 0.22), g.mul(ripple_x, 0.05))
slope_y = g.add(g.mul(swell_y, 0.22), g.mul(ripple_y, 0.05))
xy = g.link(slope_x, g.node(unreal.MaterialExpressionAppendVector), "A")
g.link(slope_y, xy, "B")
xyz = g.link(xy, g.node(unreal.MaterialExpressionAppendVector), "A")
g.link(g.const(1.0), xyz, "B")
normal = g.link(xyz, g.node(unreal.MaterialExpressionNormalize), "VectorInput")

# How far the lake bed lies behind this pixel (cm): shallows near the shore, deep in the middle.
scene_depth = g.node(unreal.MaterialExpressionSceneDepth)
pixel_depth = g.node(unreal.MaterialExpressionPixelDepth)
thickness = g.sub(scene_depth, pixel_depth)
deep_mix = g.saturate(g.mul(thickness, 1.0 / 1400.0))
colour = g.lerp(g.vec((0.014, 0.022, 0.012)), g.param("Color", (0.0008, 0.0016, 0.0018)), deep_mix)
swell_tone = g.saturate(g.add(g.mul(swell_x, 0.5), 0.5))
colour = g.mul(colour, g.lerp(g.const(0.85), g.const(1.15), swell_tone))  # faint dark and lighter streaks on the surface
opacity = g.lerp(g.const(0.3), g.const(0.985), g.saturate(g.mul(thickness, 1.0 / 450.0)))

# Cold sky glint at grazing angles, so the black water still reads as water from the air.
glint = g.mul(g.node(unreal.MaterialExpressionFresnel, exponent=4.0, base_reflect_fraction=0.0), g.vec((0.012, 0.02, 0.025)))

g.finish({unreal.MaterialProperty.MP_BASE_COLOR: colour, unreal.MaterialProperty.MP_NORMAL: normal,
          unreal.MaterialProperty.MP_ROUGHNESS: g.const(0.07), unreal.MaterialProperty.MP_SPECULAR: g.const(0.22),
          unreal.MaterialProperty.MP_OPACITY: opacity, unreal.MaterialProperty.MP_EMISSIVE_COLOR: glint})

# ---------------------------------------------------------------------------------------------------------------------------------------------
# Mist
# ---------------------------------------------------------------------------------------------------------------------------------------------
m = Graph("M_LakeMist")
m.mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
m.mat.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
m.mat.set_editor_property("two_sided", True)
world = m.node(unreal.MaterialExpressionWorldPosition)
time = m.node(unreal.MaterialExpressionTime)
moving = m.add(world, m.mul(time, m.vec((60, 25, 0))))
puffs = m.noise(moving, 0.00012, 3)  # -1..1
wisps = m.noise(m.add(world, m.mul(time, m.vec((-35, 40, 0)))), 0.0004, 2)
density = m.saturate(m.add(m.mul(m.add(puffs, m.mul(wisps, 0.3)), 0.5), 0.45))
gap = m.sub(m.node(unreal.MaterialExpressionSceneDepth), m.node(unreal.MaterialExpressionPixelDepth))  # soft where the sheet meets water, shore or trees
fade = m.mul(m.mul(density, 0.22), m.saturate(m.mul(gap, 1.0 / 900.0)))
m.finish({unreal.MaterialProperty.MP_EMISSIVE_COLOR: m.param("Color", (0.025, 0.033, 0.04)), unreal.MaterialProperty.MP_OPACITY: fade})
unreal.log("HPW: built M_BlackLake and M_LakeMist")
