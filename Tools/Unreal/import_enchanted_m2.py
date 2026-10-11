"""Imports the enchanted-forest models from SourceAssets/Enchanted/*.glb (CC-BY 4.0, see docs/CREDITS.md) into /Game/HPW/Enchanted/<name>.

Interchange's glTF materials fall back to the checker material on instanced meshes unless they are marked for instancing and Nanite, so every
imported material gets those flags. Logs each mesh's size, triangles and materials.

Headless:  UnrealEditor-Cmd.exe HPWorld.uproject -run=pythonscript -script=Tools/Unreal/import_enchanted_m2.py
Set HPW_ONLY=name1,name2 to import only some of them.
"""

import os

import unreal

here = os.path.dirname(os.path.abspath(__file__))
src = os.path.normpath(os.path.join(here, "..", "..", "SourceAssets", "Enchanted"))
names = [n[:-4] for n in sorted(os.listdir(src)) if n.endswith(".glb")]
if os.environ.get("HPW_ONLY"):
    names = [n for n in names if n in os.environ["HPW_ONLY"].split(",")]

tools = unreal.AssetToolsHelpers.get_asset_tools()
for name in names:
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", os.path.join(src, name + ".glb"))
    task.set_editor_property("destination_path", f"/Game/HPW/Enchanted/{name}")
    task.set_editor_property("automated", True)
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("save", True)
    tools.import_asset_tasks([task])
    paths = list(task.get_editor_property("imported_object_paths"))
    for path in paths:
        asset = unreal.load_asset(path)
        if isinstance(asset, unreal.Material):
            asset.set_editor_property("used_with_instanced_static_meshes", True)
            asset.set_editor_property("used_with_nanite", True)
            unreal.MaterialEditingLibrary.recompile_material(asset)
            unreal.EditorAssetLibrary.save_loaded_asset(asset)
            unreal.log(f"HPW: {name} material {asset.get_name()} blend={asset.get_editor_property('blend_mode')} two_sided={asset.get_editor_property('two_sided')}")
        elif isinstance(asset, unreal.StaticMesh):
            box = asset.get_bounds()
            e = box.box_extent
            unreal.log(f"HPW: {name} mesh {asset.get_name()} size_cm {2 * e.x:.0f} x {2 * e.y:.0f} x {2 * e.z:.0f} slots {len(asset.get_editor_property('static_materials'))} tris {unreal.EditorStaticMeshLibrary.get_number_verts(asset, 0)} verts")
