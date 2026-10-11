"""Turns Nanite on for the heavy photo-scanned and tree meshes (/Game/HPW/Enchanted/<model>/<model>/StaticMeshes), which have no LODs.

Nanite streams and culls their triangles, so a few thousand instances of a 100k-triangle oak or boulder stay affordable.
Models: HPW_NANITE=oaks,pines,... (default: the list below).

Headless:  UnrealEditor-Cmd.exe HPWorld.uproject -run=pythonscript -script=Tools/Unreal/enable_nanite_m2.py
"""

import os

import unreal

MODELS = os.environ.get("HPW_NANITE", "oaks,boulder_beach,boulders_mossy,rock_table,pines,sacred_roots").split(",")
root = os.path.join(unreal.SystemLibrary.get_project_directory(), "Content", "HPW", "Enchanted")
for model in MODELS:
    folder = os.path.join(root, model, model, "StaticMeshes")
    for name in sorted(f[:-len(".uasset")] for f in os.listdir(folder) if f.endswith(".uasset")):
        mesh = unreal.load_asset(f"/Game/HPW/Enchanted/{model}/{model}/StaticMeshes/{name}")
        settings = mesh.get_editor_property("nanite_settings")
        settings.set_editor_property("enabled", True)
        mesh.set_editor_property("nanite_settings", settings)
        unreal.EditorAssetLibrary.save_loaded_asset(mesh)
        unreal.log(f"HPW: nanite on for {model}/{name}: {mesh.get_editor_property('nanite_settings').get_editor_property('enabled')}")
