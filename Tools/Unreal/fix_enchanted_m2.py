"""Marks the imported enchanted-forest materials for instancing and Nanite (otherwise instanced meshes show Unreal's checker fallback) and
logs every mesh's centre and size so models made of several meshes can be paired. Run after Tools/Unreal/import_enchanted_m2.py.

Headless:  UnrealEditor-Cmd.exe HPWorld.uproject -run=pythonscript -script=Tools/Unreal/fix_enchanted_m2.py
"""

import os

import unreal

root = os.path.join(unreal.SystemLibrary.get_project_directory(), "Content", "HPW", "Enchanted")
for model in sorted(os.listdir(root)):
    base = os.path.join(root, model, model)
    for sub in ("Materials", "StaticMeshes"):
        folder = os.path.join(base, sub)
        if not os.path.isdir(folder):
            continue
        for name in sorted(f[:-len(".uasset")] for f in os.listdir(folder) if f.endswith(".uasset")):
            asset = unreal.load_asset(f"/Game/HPW/Enchanted/{model}/{model}/{sub}/{name}")
            if isinstance(asset, unreal.Material):
                asset.set_editor_property("used_with_instanced_static_meshes", True)
                asset.set_editor_property("used_with_nanite", True)
                unreal.MaterialEditingLibrary.recompile_material(asset)
                unreal.EditorAssetLibrary.save_loaded_asset(asset)
                unreal.log(f"HPW: {model} material {name} blend={asset.get_editor_property('blend_mode')} two_sided={asset.get_editor_property('two_sided')}")
            elif isinstance(asset, unreal.StaticMesh):
                box = asset.get_bounds()
                o, e = box.origin, box.box_extent
                unreal.log(f"HPW: {model} mesh {name} centre {o.x:.0f},{o.y:.0f},{o.z:.0f} half {e.x:.0f},{e.y:.0f},{e.z:.0f}")
