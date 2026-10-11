"""Makes the Blueprint player: Harry on a Nimbus 2000 instead of the greybox cylinders.

Creates /Game/HPW/Player/BP_HarryBroomPawn (a Blueprint subclass of ABroomPawn: the greybox parts are hidden, Harry and the broom are added
as static mesh components on the collision sphere) and /Game/HPW/Player/BP_HarryGameMode (a subclass of AHPFlightGameMode that spawns it).
No C++ change, so no rebuild. Config/DefaultEngine.ini points GlobalDefaultGameMode at BP_HarryGameMode.

Run after import_enchanted_m2.py (HPW_ONLY=harry_rider,nimbus) and build_enchanted_materials_m2.py. Tuning: environment variables
HPW_YAW (degrees, turns the glb's forward axis to +X), HPW_HARRY="x,y,z" and HPW_BROOM="x,y,z" (cm, relative to the pawn).

Headless:  UnrealEditor-Cmd.exe HPWorld.uproject -run=pythonscript -script=Tools/Unreal/create_player_m2.py
"""

import os

import unreal

DEST = "/Game/HPW/Player"
YAW = float(os.environ.get("HPW_YAW", "-90"))
HARRY_AT = [float(v) for v in os.environ.get("HPW_HARRY", "-20,0,-12").split(",")]
BROOM_AT = [float(v) for v in os.environ.get("HPW_BROOM", "10,0,-25").split(",")]
GREYBOX = ("BroomHandle", "BroomBristles", "RiderBody", "RiderHead")

tools = unreal.AssetToolsHelpers.get_asset_tools()
subsystem = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
lib = unreal.SubobjectDataBlueprintFunctionLibrary


# The game mode references the pawn, so the mode goes first or the pawn cannot be deleted (and the new one would not be created).
for old in ("BP_HarryGameMode", "BP_HarryBroomPawn"):
    if unreal.EditorAssetLibrary.does_asset_exist(f"{DEST}/{old}"):
        unreal.EditorAssetLibrary.delete_asset(f"{DEST}/{old}")


def make_blueprint(name, parent):
    factory = unreal.BlueprintFactory()
    factory.set_editor_property("parent_class", parent)
    return tools.create_asset(name, DEST, unreal.Blueprint, factory)


def components(blueprint):
    """{variable name: (handle, object)} for every component of the blueprint, inherited ones included."""
    found = {}
    for handle in subsystem.k2_gather_subobject_data_for_blueprint(blueprint):
        data = subsystem.k2_find_subobject_data_from_handle(handle)
        obj = lib.get_object_for_blueprint(data, blueprint) if hasattr(lib, "get_object_for_blueprint") else lib.get_object(data)
        if obj is not None:
            found[obj.get_name().replace("_GEN_VARIABLE", "")] = (handle, obj)
    return found


def add_mesh(blueprint, parent_handle, name, mesh_path, location, yaw):
    params = unreal.AddNewSubobjectParams(parent_handle=parent_handle, new_class=unreal.StaticMeshComponent, blueprint_context=blueprint)
    handle, reason = subsystem.add_new_subobject(params)
    assert lib.is_handle_valid(handle), f"could not add {name}: {reason}"
    subsystem.rename_subobject(handle, name)
    data = subsystem.k2_find_subobject_data_from_handle(handle)
    component = lib.get_object_for_blueprint(data, blueprint) if hasattr(lib, "get_object_for_blueprint") else lib.get_object(data)
    component.set_editor_property("static_mesh", unreal.load_asset(mesh_path))
    component.set_editor_property("relative_location", unreal.Vector(*location))
    component.set_editor_property("relative_rotation", unreal.Rotator(roll=0.0, pitch=0.0, yaw=yaw))
    component.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    component.set_editor_property("cast_shadow", True)
    return component


pawn_bp = make_blueprint("BP_HarryBroomPawn", unreal.BroomPawn)
unreal.BlueprintEditorLibrary.compile_blueprint(pawn_bp)  # without a compiled skeleton class the component list comes back empty
parts = components(pawn_bp)
unreal.log(f"HPW: pawn components: {sorted(parts)}")
for name in GREYBOX:
    parts[name][1].set_editor_property("hidden_in_game", True)
    parts[name][1].set_editor_property("visible", False)
root = parts["Collision"][0]
add_mesh(pawn_bp, root, "BroomVisual", "/Game/HPW/Enchanted/nimbus/nimbus/StaticMeshes/nimbus", BROOM_AT, YAW)
add_mesh(pawn_bp, root, "HarryVisual", "/Game/HPW/Enchanted/harry_rider/harry_rider/StaticMeshes/harry_rider", HARRY_AT, YAW)
unreal.BlueprintEditorLibrary.compile_blueprint(pawn_bp)
unreal.EditorAssetLibrary.save_loaded_asset(pawn_bp)

mode_bp = make_blueprint("BP_HarryGameMode", unreal.HPFlightGameMode)
unreal.BlueprintEditorLibrary.compile_blueprint(mode_bp)
mode_class = unreal.load_object(None, f"{DEST}/BP_HarryGameMode.BP_HarryGameMode_C")
pawn_class = unreal.load_object(None, f"{DEST}/BP_HarryBroomPawn.BP_HarryBroomPawn_C")
unreal.get_default_object(mode_class).set_editor_property("default_pawn_class", pawn_class)
unreal.EditorAssetLibrary.save_loaded_asset(mode_bp)
unreal.log("HPW: player blueprints built")
