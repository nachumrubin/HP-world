"""Imports the M1 heightmap (Tools/generated/HPW_Heightmap_4033.r16) as a Landscape into M0_Greybox and saves the map.

Headless:  UnrealEditor-Cmd.exe HPWorld.uproject -run=pythonscript -script=Tools/Unreal/import_landscape_m1.py
Needs the HPWorld editor module (UHPLandscapeTools). Skips if the level already has a Landscape, unless HPW_REPLACE=1:
then the existing Landscape is deleted first, which is how a regenerated heightmap gets in.
"""

import os
import unreal

REPLACE = os.environ.get("HPW_REPLACE") == "1"

MAP = "/Game/HPW/Maps/M0_Greybox"
SIZE = 4033
SCALE = unreal.Vector(173.6111, 173.6111, 300.0)
LOCATION = unreal.Vector(-350000.0, -350000.0, 0.0)

here = os.path.dirname(os.path.abspath(__file__))
r16 = os.path.normpath(os.path.join(here, "..", "generated", "HPW_Heightmap_4033.r16"))

unreal.EditorLevelLibrary.load_level(MAP)
if REPLACE:
    for _actor in unreal.EditorLevelLibrary.get_all_level_actors():
        if isinstance(_actor, unreal.LandscapeProxy):
            _actor.destroy_actor()
if any(
        isinstance(a, unreal.LandscapeProxy) for a in unreal.EditorLevelLibrary.get_all_level_actors()):
    unreal.log_warning("Landscape already present; nothing to do")
elif unreal.HPLandscapeTools.import_landscape_from_r16(r16, SIZE, LOCATION, SCALE, "HPW_Landscape"):
    unreal.EditorLevelLibrary.save_current_level()
    unreal.log("HPW: landscape imported and level saved")
else:
    raise RuntimeError("landscape import failed")
