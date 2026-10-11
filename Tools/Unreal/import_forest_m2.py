"""Imports the Kenney Nature Kit models in SourceAssets/Kenney/nature (CC0, see SourceAssets/Kenney/LICENSE.txt) into /Game/HPW/Forest/<name>.

Headless:  UnrealEditor-Cmd.exe HPWorld.uproject -run=pythonscript -script=Tools/Unreal/import_forest_m2.py
"""

import glob
import os

import unreal

DEST = "/Game/HPW/Forest"
here = os.path.dirname(os.path.abspath(__file__))
source = os.path.normpath(os.path.join(here, "..", "..", "SourceAssets", "Kenney", "nature"))

tasks = []
for path in sorted(glob.glob(os.path.join(source, "*.glb"))):
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", path)
    task.set_editor_property("destination_path", f"{DEST}/{os.path.splitext(os.path.basename(path))[0]}")
    task.set_editor_property("automated", True)
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("save", True)
    tasks.append(task)
unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks(tasks)
unreal.log(f"HPW: imported {len(tasks)} nature models into {DEST}")
