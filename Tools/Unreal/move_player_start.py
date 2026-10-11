"""Editor-side helper for Tools/shot_at.sh: moves the level's PlayerStart (metres; yaw/pitch in degrees) and saves the map.

Environment: HPW_POS="x,y,z", HPW_LOOK="x,y,z" (the point to face).
"""

import os

import unreal

pos = [float(v) * 100.0 for v in os.environ["HPW_POS"].split(",")]
look = [float(v) * 100.0 for v in os.environ["HPW_LOOK"].split(",")]
rot = unreal.MathLibrary.find_look_at_rotation(unreal.Vector(*pos), unreal.Vector(*look))
unreal.EditorLevelLibrary.load_level("/Game/HPW/Maps/M0_Greybox")
for actor in unreal.EditorLevelLibrary.get_all_level_actors():
    if isinstance(actor, unreal.PlayerStart):
        actor.set_actor_location_and_rotation(unreal.Vector(*pos), rot, False, True)
        unreal.EditorLevelLibrary.save_current_level()
        unreal.log("HPW: PlayerStart moved")
        break
