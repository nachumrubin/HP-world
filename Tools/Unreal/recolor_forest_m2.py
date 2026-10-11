"""Gives the imported Kenney nature models (/Game/HPW/Forest/<name>/<name>/StaticMeshes) the project's dark forest materials.

The materials Interchange makes for these .glb files do not work in the running game: they come out as Unreal's white checker fallback, and
the glTF data marks them fully metallic with bright linear colours anyway. So every mesh slot is pointed at a plain matte instance of
/Game/HPW/Greybox/Materials/M_Greybox (made by Tools/Unreal/build_greybox_m0.py), one per Kenney material name, coloured from PALETTE.
Run it after Tools/Unreal/import_forest_m2.py (re-importing resets the slots).

Headless:  UnrealEditor-Cmd.exe HPWorld.uproject -run=pythonscript -script=Tools/Unreal/recolor_forest_m2.py
"""

import os

import unreal

PALETTE = {  # linear RGB
    "leafsDark": (0.006, 0.03, 0.018),
    "leafsGreen": (0.025, 0.08, 0.03),
    "woodBarkDark": (0.05, 0.03, 0.02),
    "woodBark": (0.07, 0.045, 0.03),
    "woodInner": (0.2, 0.14, 0.09),
    "dirt": (0.09, 0.075, 0.06),     # rock bodies
    "grass": (0.04, 0.09, 0.035),    # moss on the rocks
    "_defaultMat": (0.12, 0.11, 0.10),
    "colorRed": (0.5, 0.04, 0.03),
    "colorTan": (0.35, 0.28, 0.18),
}
FALLBACK = (0.05, 0.05, 0.05)
MI_DIR = "/Game/HPW/Forest/MI_Forest"

parent = unreal.load_asset("/Game/HPW/Greybox/Materials/M_Greybox")
assert parent is not None, "run Tools/Unreal/build_greybox_m0.py first: M_Greybox is missing"
lib = unreal.MaterialEditingLibrary
instances = {}


def instance_for(name):
    if name not in instances:
        path = f"{MI_DIR}/MI_{name}"
        if unreal.EditorAssetLibrary.does_asset_exist(path):
            mi = unreal.load_asset(path)
        else:
            mi = unreal.AssetToolsHelpers.get_asset_tools().create_asset(f"MI_{name}", MI_DIR, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
        lib.set_material_instance_parent(mi, parent)
        rgb = PALETTE.get(name, FALLBACK)
        lib.set_material_instance_vector_parameter_value(mi, "Color", unreal.LinearColor(rgb[0], rgb[1], rgb[2], 1.0))
        lib.update_material_instance(mi)
        unreal.EditorAssetLibrary.save_loaded_asset(mi)
        instances[name] = mi
    return instances[name]


root = os.path.join(unreal.SystemLibrary.get_project_directory(), "Content", "HPW", "Forest")
meshes_done = slots_done = 0
for model in sorted(os.listdir(root)):
    folder = os.path.join(root, model, model, "StaticMeshes")
    if not os.path.isdir(folder):
        continue
    for name in sorted(f[:-len(".uasset")] for f in os.listdir(folder) if f.endswith(".uasset")):
        mesh = unreal.load_asset(f"/Game/HPW/Forest/{model}/{model}/StaticMeshes/{name}")
        for index, slot in enumerate(mesh.get_editor_property("static_materials")):
            current = slot.get_editor_property("material_interface")
            key = current.get_name() if current else "_defaultMat"
            if key.startswith("MI_"):
                key = key[3:]  # already ours (the script was run before)
            mesh.set_material(index, instance_for(key))
            slots_done += 1
        unreal.EditorAssetLibrary.save_loaded_asset(mesh)
        meshes_done += 1
unreal.log(f"HPW: pointed {slots_done} slots of {meshes_done} nature meshes at {len(instances)} matte materials")
