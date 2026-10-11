"""Makes the Quidditch pitch model's grass plane use the project's pitch-green matte material.

The model's own grass material (an Interchange glTF instance with a photo texture) renders as a pale see-through sheet in the running game.
Run after Tools/Unreal/import_pitch_m2.py (re-importing resets the slot). Needs MI_Greybox_pitch from Tools/Unreal/build_greybox_m0.py.

Headless:  UnrealEditor-Cmd.exe HPWorld.uproject -run=pythonscript -script=Tools/Unreal/fix_pitch_m2.py
"""

import os

import unreal

FOLDER = "/Game/HPW/Quidditch/quidditch_pitch_baked/StaticMeshes"
green = unreal.load_asset("/Game/HPW/Greybox/Materials/MI_Greybox_pitch")
assert green is not None, "run Tools/Unreal/build_greybox_m0.py first: MI_Greybox_pitch is missing"
disk = os.path.join(unreal.SystemLibrary.get_project_directory(), "Content", FOLDER[len("/Game/"):])
fixed = 0
for name in sorted(f[:-len(".uasset")] for f in os.listdir(disk) if f.endswith(".uasset")):
    mesh = unreal.load_asset(f"{FOLDER}/{name}")
    for index, slot in enumerate(mesh.get_editor_property("static_materials")):
        material = slot.get_editor_property("material_interface")
        if material is not None and material.get_name().startswith("Grass"):
            mesh.set_material(index, green)
            unreal.EditorAssetLibrary.save_loaded_asset(mesh)
            fixed += 1
unreal.log(f"HPW: pitch grass slots set to green: {fixed}")
