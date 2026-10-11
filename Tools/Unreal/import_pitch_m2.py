"""Imports SourceAssets/Quidditch/quidditch_pitch_baked.glb (CC-BY 4.0, see docs/CREDITS.md) into /Game/HPW/Quidditch.

The baked file comes from Tools/bake_glb.py (the model places its parts with node transforms).

Headless:  UnrealEditor-Cmd.exe HPWorld.uproject -run=pythonscript -script=Tools/Unreal/import_pitch_m2.py
"""

import os
import unreal

DEST = "/Game/HPW/Quidditch"
here = os.path.dirname(os.path.abspath(__file__))
glb = os.path.normpath(os.path.join(here, "..", "..", "SourceAssets", "Quidditch", "quidditch_pitch_baked.glb"))

task = unreal.AssetImportTask()
task.set_editor_property("filename", glb)
task.set_editor_property("destination_path", DEST)
task.set_editor_property("automated", True)
task.set_editor_property("replace_existing", True)
task.set_editor_property("save", True)
unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
paths = list(task.get_editor_property("imported_object_paths"))
unreal.log(f"HPW: imported {len(paths)} objects from the pitch model")
for path in paths[:40]:
    unreal.log(f"HPW: imported {path}")
