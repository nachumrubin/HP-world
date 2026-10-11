"""In-game helper: waits for the level to settle, takes one HighResShot, quits. No C++ needed (see Tools/shot_at.sh).

Environment: HPW_SHOT_NAME (file name, no extension), HPW_SHOT_WAIT (seconds to wait, default 70).
"""

import os

import unreal

out = os.path.join(unreal.SystemLibrary.get_project_directory(), "Tools", "generated", "shots", os.environ.get("HPW_SHOT_NAME", "shot") + ".png").replace("\\", "/")
wait = float(os.environ.get("HPW_SHOT_WAIT", "70"))  # seconds: shaders and streaming need about a minute
state = {"t": 0.0, "shot": False, "handle": None}


def tick(delta):
    state["t"] += delta
    if state["t"] > wait and not state["shot"]:
        state["shot"] = True
        world = unreal.find_object(None, "/Game/HPW/Maps/M0_Greybox.M0_Greybox")  # the loaded UWorld (EditorLevelLibrary.get_game_world crashes in -game)
        unreal.log(f"HPW: shot world {world}")
        unreal.SystemLibrary.execute_console_command(world, f'HighResShot 1600x900 filename="{out}"')
    elif state["t"] > wait + 10:
        unreal.unregister_slate_post_tick_callback(state["handle"])
        unreal.SystemLibrary.execute_console_command(None, "quit")


state["handle"] = unreal.register_slate_post_tick_callback(tick)
