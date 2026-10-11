"""Imports SourceAssets/Cliff/cliff_face_v2_baked.glb ("Cliff Face V2" by James Tubbritt, CC-BY 4.0, see docs/CREDITS.md) into /Game/HPW/Cliff.

The baked file comes from Tools/bake_glb.py (the model places its parts with node transforms). The glb marks its material unlit, so this also builds
a lit material M_CliffScan from the photo texture and assigns it to every imported mesh.

Headless:  UnrealEditor-Cmd.exe HPWorld.uproject -run=pythonscript -script=Tools/Unreal/import_cliff_m2.py
"""

import os

import unreal

DEST = "/Game/HPW/Cliff"
here = os.path.dirname(os.path.abspath(__file__))
glb = os.path.normpath(os.path.join(here, "..", "..", "SourceAssets", "Cliff", "cliff_face_v2_baked.glb"))

MATERIAL_ONLY = os.environ.get("HPW_MATERIAL_ONLY") == "1"  # skip the 20 MB re-import, just rebuild M_CliffScan

task = unreal.AssetImportTask()
task.set_editor_property("filename", glb)
task.set_editor_property("destination_path", DEST)
task.set_editor_property("automated", True)
task.set_editor_property("replace_existing", True)
task.set_editor_property("save", True)
if not MATERIAL_ONLY:
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])

content = os.path.join(unreal.SystemLibrary.get_project_directory(), "Content", "HPW", "Cliff", "cliff_face_v2_baked")


def asset_names(sub):
    folder = os.path.join(content, sub)
    return sorted(f[:-len(".uasset")] for f in os.listdir(folder) if f.endswith(".uasset")) if os.path.isdir(folder) else []


textures = asset_names("Textures")
meshes = asset_names("StaticMeshes")
assert textures and meshes, "the cliff import produced no texture or no meshes"

# Lit material from the photo texture.
lib = unreal.MaterialEditingLibrary
material_path = f"{DEST}/M_CliffScan"
if unreal.EditorAssetLibrary.does_asset_exist(material_path):
    unreal.EditorAssetLibrary.delete_asset(material_path)
material = unreal.AssetToolsHelpers.get_asset_tools().create_asset("M_CliffScan", DEST, unreal.Material, unreal.MaterialFactoryNew())
sample = lib.create_material_expression(material, unreal.MaterialExpressionTextureSample, -500, 0)
sample.set_editor_property("texture", unreal.load_asset(f"{DEST}/cliff_face_v2_baked/Textures/{textures[0]}"))
# The scan photo has bright green grass and sand patches; keep mostly grey rock with only a hint of moss.
grey = lib.create_material_expression(material, unreal.MaterialExpressionDesaturation, -400, 0)
lib.connect_material_expressions(sample, "RGB", grey, "Input")
amount = lib.create_material_expression(material, unreal.MaterialExpressionConstant, -600, 120)
amount.set_editor_property("r", 0.7)
lib.connect_material_expressions(amount, "", grey, "Fraction")
tint = lib.create_material_expression(material, unreal.MaterialExpressionMultiply, -250, 0)
lib.connect_material_expressions(grey, "", tint, "A")
gain = lib.create_material_expression(material, unreal.MaterialExpressionConstant, -500, 200)
gain.set_editor_property("r", 0.42)  # the scan photos are bright; this keeps the rock from glowing
lib.connect_material_expressions(gain, "", tint, "B")
rough = lib.create_material_expression(material, unreal.MaterialExpressionConstant, -250, 250)
rough.set_editor_property("r", 0.9)
material.set_editor_property("two_sided", True)
material.set_editor_property("used_with_instanced_static_meshes", True)  # without these the game falls back to the grey checker material
material.set_editor_property("used_with_nanite", True)
lib.connect_material_property(tint, "", unreal.MaterialProperty.MP_BASE_COLOR)
lib.connect_material_property(rough, "", unreal.MaterialProperty.MP_ROUGHNESS)
lib.recompile_material(material)
unreal.EditorAssetLibrary.save_loaded_asset(material)

for name in meshes:
    mesh = unreal.load_asset(f"{DEST}/cliff_face_v2_baked/StaticMeshes/{name}")
    for slot in range(len(mesh.get_editor_property("static_materials"))):
        mesh.set_material(slot, material)
    unreal.EditorAssetLibrary.save_loaded_asset(mesh)
unreal.log(f"HPW: imported cliff scan: {len(meshes)} meshes, texture {textures[0]}, material M_CliffScan")
