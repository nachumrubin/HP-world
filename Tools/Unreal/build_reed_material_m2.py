"""Builds /Game/HPW/Enchanted/Materials/M_Reed (dark olive at the root, paler dry tips, two-sided, flagged for instancing) and puts it on the reeds mesh.

The reeds come from Tools/make_reeds.py (SourceAssets/Enchanted/reeds.glb, imported by import_enchanted_m2.py). UV v is 0 at the root and 1 at the tip.

Headless:  UnrealEditor-Cmd.exe HPWorld.uproject -run=pythonscript -script=Tools/Unreal/build_reed_material_m2.py
"""

import unreal

DEST = "/Game/HPW/Enchanted/Materials"
mel = unreal.MaterialEditingLibrary
path = f"{DEST}/M_Reed"
if unreal.EditorAssetLibrary.does_asset_exist(path):
    mat = unreal.load_asset(path)
    mel.delete_all_material_expressions(mat)
else:
    mat = unreal.AssetToolsHelpers.get_asset_tools().create_asset("M_Reed", DEST, unreal.Material, unreal.MaterialFactoryNew())


def node(cls, y, **props):
    n = mel.create_material_expression(mat, cls, -600, y)
    for k, v in props.items():
        n.set_editor_property(k, v)
    return n


uv = node(unreal.MaterialExpressionTextureCoordinate, 0)
v = node(unreal.MaterialExpressionComponentMask, 100, r=False, g=True, b=False, a=False)
mel.connect_material_expressions(uv, "", v, "")
root = node(unreal.MaterialExpressionConstant3Vector, 200, constant=unreal.LinearColor(0.008, 0.016, 0.006, 1.0))
tip = node(unreal.MaterialExpressionConstant3Vector, 300, constant=unreal.LinearColor(0.07, 0.065, 0.025, 1.0))
mix = node(unreal.MaterialExpressionLinearInterpolate, 400)
mel.connect_material_expressions(root, "", mix, "A")
mel.connect_material_expressions(tip, "", mix, "B")
mel.connect_material_expressions(v, "", mix, "Alpha")
rough = node(unreal.MaterialExpressionConstant, 500, r=0.8)
mat.set_editor_property("two_sided", True)
mat.set_editor_property("used_with_instanced_static_meshes", True)
mat.set_editor_property("used_with_nanite", True)
mel.connect_material_property(mix, "", unreal.MaterialProperty.MP_BASE_COLOR)
mel.connect_material_property(rough, "", unreal.MaterialProperty.MP_ROUGHNESS)
mel.recompile_material(mat)
unreal.EditorAssetLibrary.save_loaded_asset(mat)

mesh = unreal.load_asset("/Game/HPW/Enchanted/reeds/reeds/StaticMeshes/reeds")
assert mesh is not None, "import reeds.glb first (import_enchanted_m2.py with HPW_ONLY=reeds)"
for slot in range(len(mesh.get_editor_property("static_materials"))):
    mesh.set_material(slot, mat)
unreal.EditorAssetLibrary.save_loaded_asset(mesh)
unreal.log("HPW: reed material built and assigned")
