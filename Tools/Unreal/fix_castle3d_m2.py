"""Post-import fixes for /Game/HPW/Castle3D (run after import_castle3d_m2.py; re-importing resets the slots).

- The model's black roof materials become dark slate (matte instances of M_Greybox).
- Logs the combined bounds of the castle meshes without the model's own rock mountain (EXCLUDE), for castle_model.bounds_cm in the layout.

Headless:  UnrealEditor-Cmd.exe HPWorld.uproject -run=pythonscript -script=Tools/Unreal/fix_castle3d_m2.py
"""

import os

import unreal

FOLDER = "/Game/HPW/Castle3D/hogwarts_3d_baked/StaticMeshes"
ROCK_MATERIAL = "JANELAS1"  # the model's rock mountain (the project has its own crag); the layout lists these meshes under "exclude"
SLATE = (0.02, 0.026, 0.038)
BLACK = {"Material_002", "Material_013", "Material_012", "Material_007"}

parent = unreal.load_asset("/Game/HPW/Greybox/Materials/M_Greybox")
assert parent is not None, "run Tools/Unreal/build_greybox_m0.py first"
lib = unreal.MaterialEditingLibrary
path = "/Game/HPW/Castle3D/MI_Slate"
if unreal.EditorAssetLibrary.does_asset_exist(path):
    slate = unreal.load_asset(path)
else:
    slate = unreal.AssetToolsHelpers.get_asset_tools().create_asset("MI_Slate", "/Game/HPW/Castle3D", unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
lib.set_material_instance_parent(slate, parent)
lib.set_material_instance_vector_parameter_value(slate, "Color", unreal.LinearColor(*SLATE, 1.0))
lib.update_material_instance(slate)
unreal.EditorAssetLibrary.save_loaded_asset(slate)

disk = os.path.join(unreal.SystemLibrary.get_project_directory(), "Content", FOLDER[len("/Game/"):])
mn, mx, fixed, kept, rock = [1e18] * 3, [-1e18] * 3, 0, 0, []
for name in sorted(f[:-len(".uasset")] for f in os.listdir(disk) if f.endswith(".uasset")):
    mesh = unreal.load_asset(f"{FOLDER}/{name}")
    changed = False
    for index, slot in enumerate(mesh.get_editor_property("static_materials")):
        current = slot.get_editor_property("material_interface")
        if current and current.get_name() in BLACK:
            mesh.set_material(index, slate)
            changed = True
            fixed += 1
    if changed:
        unreal.EditorAssetLibrary.save_loaded_asset(mesh)
    if any(s.get_editor_property("material_interface").get_name() == ROCK_MATERIAL for s in mesh.get_editor_property("static_materials")):
        rock.append(name)
        continue
    kept += 1
    box = mesh.get_bounds()
    for i, (o, e) in enumerate(((box.origin.x, box.box_extent.x), (box.origin.y, box.box_extent.y), (box.origin.z, box.box_extent.z))):
        mn[i], mx[i] = min(mn[i], o - e), max(mx[i], o + e)
unreal.log(f"HPW: castle3d slate slots {fixed}; {kept} meshes kept; exclude {rock}; bounds_cm [[{mn[0]:.2f}, {mn[1]:.2f}, {mn[2]:.2f}], [{mx[0]:.2f}, {mx[1]:.2f}, {mx[2]:.2f}]]")
