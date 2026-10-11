"""Imports SourceAssets/Hogwarts/hogwarts_3d_baked.glb (textured castle with windows and doors, see docs/CREDITS.md) into /Game/HPW/Castle3D.

Headless:  UnrealEditor-Cmd.exe HPWorld.uproject -run=pythonscript -script=Tools/Unreal/import_castle3d_m2.py
"""

import os
import unreal

DEST = "/Game/HPW/Castle3D"
here = os.path.dirname(os.path.abspath(__file__))
glb = os.path.normpath(os.path.join(here, "..", "..", "SourceAssets", "Hogwarts", "hogwarts_3d_baked.glb"))

task = unreal.AssetImportTask()
task.set_editor_property("filename", glb)
task.set_editor_property("destination_path", DEST)
task.set_editor_property("automated", True)
task.set_editor_property("replace_existing", True)
task.set_editor_property("save", True)
unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
paths = list(task.get_editor_property("imported_object_paths"))
unreal.log(f"HPW: imported {len(paths)} objects from the textured castle")
for p in paths:
    if "StaticMeshes" not in p:
        unreal.log(f"HPW: imported {p}")
