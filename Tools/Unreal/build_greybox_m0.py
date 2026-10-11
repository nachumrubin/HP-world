"""Builds the M0 greybox level (Hogwarts, grounds, forest, lake, pitch) from Tools/greybox_layout.json.

In the Unreal Editor (Python plugin is enabled by the project):
    Tools > Execute Python Script...  ->  Tools/Unreal/build_greybox_m0.py
or in the Output Log's Python console:
    py "Tools/Unreal/build_greybox_m0.py"

Re-running is safe: it reopens the map and replaces everything tagged HPW_Greybox.

Outside Unreal, `python3 Tools/Unreal/build_greybox_m0.py --dry-run` walks the same layout code and prints
what would be spawned, which is how the layout is checked in CI or without the editor.
"""

import json
import math
import os
import random
import sys

try:
    import unreal  # type: ignore
except ImportError:
    unreal = None

GREYBOX_TAG = "HPW_Greybox"
MATERIAL_DIR = "/Game/HPW/Greybox/Materials"
SHAPES = {
    "box": "/Engine/BasicShapes/Cube.Cube",
    "cylinder": "/Engine/BasicShapes/Cylinder.Cylinder",
    "cone": "/Engine/BasicShapes/Cone.Cone",
    "sphere": "/Engine/BasicShapes/Sphere.Sphere",
}
M_TO_CM = 100.0

# Set by build() once the Landscape is imported (layout "landscape.imported"): the shared terrain height function.
GROUND_HEIGHT = None


def layout_path():
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(here, "..", "greybox_layout.json"))


# --------------------------------------------------------------------------------------------------
# Backends
# --------------------------------------------------------------------------------------------------

class DryRunBackend:
    """Records spawns instead of talking to Unreal."""

    def __init__(self):
        self.spawned = []

    def begin(self, map_path, materials):
        self.map_path = map_path
        self.materials = materials

    def shape(self, shape, label, folder, center_m, scale_m, rotation, material, tags, collision):
        assert shape in SHAPES, shape
        assert material in self.materials, f"unknown material '{material}' on {label}"
        assert all(s > 0 for s in scale_m), f"non-positive size on {label}: {scale_m}"
        self.spawned.append((folder, label))

    def point_light(self, label, folder, position_m, color, intensity, radius_m):
        self.spawned.append((folder, label))

    def instanced_chunks(self, label, folder, mesh_folder, placements, collision):
        assert placements is not None
        self.spawned.append((folder, f"{label}: {len(placements)} cladding chunks"))

    def instanced_meshes(self, label, folder, groups, collision, cull_distance_m):
        assert groups is not None
        self.spawned.append((folder, f"{label}: {sum(len(v) for v in groups.values())} instances of {len(groups)} models"))

    def castle_model(self, placement):
        assert placement["scale"] > 0
        self.spawned.append((placement["name"], f"model scale {placement['scale']:.5f}"))

    def landscape(self, material):
        assert material in self.materials, material
        self.spawned.append(("Terrain", f"Landscape material {material}"))

    def lighting(self):
        self.spawned.append(("Lighting", "Sun/Sky/Fog/Clouds"))

    def player_start(self, position_m, yaw):
        self.spawned.append(("Gameplay", f"PlayerStart yaw={yaw:.0f}"))

    def finish(self):
        folders = {}
        for folder, _ in self.spawned:
            folders[folder] = folders.get(folder, 0) + 1
        print(f"Dry run: {len(self.spawned)} actors for {self.map_path}")
        if os.environ.get("HPW_VERBOSE"):
            for _, line in self.spawned:
                if "instances" in line:
                    print("  " + line)
        for folder, count in sorted(folders.items()):
            print(f"  {folder:<32} {count:>5}")


class UnrealBackend:
    def __init__(self):
        self.actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        self.levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
        self.meshes = {name: unreal.load_asset(path) for name, path in SHAPES.items()}
        self.material_instances = {}

    def begin(self, map_path, materials):
        if unreal.EditorAssetLibrary.does_asset_exist(map_path):
            self.levels.load_level(map_path)
            for actor in self.actors.get_all_level_actors():
                if unreal.Name(GREYBOX_TAG) in actor.tags:
                    self.actors.destroy_actor(actor)
        else:
            self.levels.new_level(map_path)
        for name, rgb in materials.items():
            self.material_instances[name] = self._material(name, rgb)

    def _water_material(self):
        """Glossy water: low roughness so it mirrors the sky, with slow large-scale tint variation for depth."""
        if unreal.EditorAssetLibrary.does_asset_exist("/Game/HPW/Lake/M_BlackLake"):
            return unreal.load_asset("/Game/HPW/Lake/M_BlackLake")  # built by Tools/Unreal/build_lake_materials_m2.py
        path = f"{MATERIAL_DIR}/M_Greybox_Water"
        if unreal.EditorAssetLibrary.does_asset_exist(path):
            return unreal.load_asset(path)
        lib = unreal.MaterialEditingLibrary
        mat = unreal.AssetToolsHelpers.get_asset_tools().create_asset("M_Greybox_Water", MATERIAL_DIR, unreal.Material, unreal.MaterialFactoryNew())
        deep = lib.create_material_expression(mat, unreal.MaterialExpressionVectorParameter, -700, 0)
        deep.set_editor_property("parameter_name", "Color")
        deep.set_editor_property("default_value", unreal.LinearColor(0.02, 0.15, 0.18, 1.0))
        shallow = lib.create_material_expression(mat, unreal.MaterialExpressionConstant3Vector, -700, 160)
        shallow.set_editor_property("constant", unreal.LinearColor(0.05, 0.3, 0.3, 1.0))
        pos = lib.create_material_expression(mat, unreal.MaterialExpressionWorldPosition, -900, 320)
        noise = lib.create_material_expression(mat, unreal.MaterialExpressionNoise, -700, 320)
        noise.set_editor_property("scale", 0.0006)
        noise.set_editor_property("quality", 1)
        noise.set_editor_property("levels", 3)
        noise.set_editor_property("output_min", 0.0)
        noise.set_editor_property("output_max", 1.0)
        lib.connect_material_expressions(pos, "", noise, "Position")
        mix = lib.create_material_expression(mat, unreal.MaterialExpressionLinearInterpolate, -450, 100)
        lib.connect_material_expressions(deep, "", mix, "A")
        lib.connect_material_expressions(shallow, "", mix, "B")
        lib.connect_material_expressions(noise, "", mix, "Alpha")
        rough = lib.create_material_expression(mat, unreal.MaterialExpressionConstant, -450, 300)
        rough.set_editor_property("r", 0.06)
        spec = lib.create_material_expression(mat, unreal.MaterialExpressionConstant, -450, 400)
        spec.set_editor_property("r", 0.9)
        lib.connect_material_property(mix, "", unreal.MaterialProperty.MP_BASE_COLOR)
        lib.connect_material_property(rough, "", unreal.MaterialProperty.MP_ROUGHNESS)
        lib.connect_material_property(spec, "", unreal.MaterialProperty.MP_SPECULAR)
        lib.recompile_material(mat)
        unreal.EditorAssetLibrary.save_loaded_asset(mat)
        return mat

    def _parent_material(self):
        """Plain matte material with one Color parameter. The engine's BasicShapeMaterial renders far brighter than its Color."""
        path = f"{MATERIAL_DIR}/M_Greybox"
        if unreal.EditorAssetLibrary.does_asset_exist(path):
            return unreal.load_asset(path)
        lib = unreal.MaterialEditingLibrary
        mat = unreal.AssetToolsHelpers.get_asset_tools().create_asset("M_Greybox", MATERIAL_DIR, unreal.Material, unreal.MaterialFactoryNew())
        color = lib.create_material_expression(mat, unreal.MaterialExpressionVectorParameter, -300, 0)
        color.set_editor_property("parameter_name", "Color")
        color.set_editor_property("default_value", unreal.LinearColor(0.5, 0.5, 0.5, 1.0))
        rough = lib.create_material_expression(mat, unreal.MaterialExpressionConstant, -300, 200)
        rough.set_editor_property("r", 0.85)
        lib.connect_material_property(color, "", unreal.MaterialProperty.MP_BASE_COLOR)
        lib.connect_material_property(rough, "", unreal.MaterialProperty.MP_ROUGHNESS)
        lib.recompile_material(mat)
        unreal.EditorAssetLibrary.save_loaded_asset(mat)
        return mat

    def _material(self, name, rgb):
        asset_name = f"MI_Greybox_{name}"
        path = f"{MATERIAL_DIR}/{asset_name}"
        if unreal.EditorAssetLibrary.does_asset_exist(path):
            mi = unreal.load_asset(path)
        else:
            mi = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
                asset_name, MATERIAL_DIR, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
        lib = unreal.MaterialEditingLibrary
        if name == "mist" and unreal.EditorAssetLibrary.does_asset_exist("/Game/HPW/Lake/M_LakeMist"):
            parent = unreal.load_asset("/Game/HPW/Lake/M_LakeMist")
        else:
            parent = self._water_material() if name == "water" else self._parent_material()
        lib.set_material_instance_parent(mi, parent)
        # The setter's bool return is unreliable across engine versions (False even when applied), so verify by reading back.
        color = unreal.LinearColor(rgb[0], rgb[1], rgb[2], 1.0)
        lib.set_material_instance_vector_parameter_value(mi, "Color", color)
        lib.update_material_instance(mi)
        if lib.get_material_instance_vector_parameter_value(mi, "Color") != color:
            unreal.log_warning(f"Greybox: could not set Color on {asset_name}")
        unreal.EditorAssetLibrary.save_loaded_asset(mi)
        return mi

    def _tag(self, actor, extra_tags):
        actor.set_editor_property("tags", [unreal.Name(GREYBOX_TAG)] + [unreal.Name(t) for t in extra_tags])

    def shape(self, shape, label, folder, center_m, scale_m, rotation, material, tags, collision):
        location = unreal.Vector(*(c * M_TO_CM for c in center_m))
        rotator = unreal.Rotator(roll=rotation[2], pitch=rotation[0], yaw=rotation[1])
        actor = self.actors.spawn_actor_from_class(unreal.StaticMeshActor, location, rotator)
        actor.static_mesh_component.set_static_mesh(self.meshes[shape])
        actor.set_actor_scale3d(unreal.Vector(*scale_m))
        actor.set_actor_label(label)
        actor.set_folder_path(f"Greybox/{folder}")
        self._tag(actor, tags)
        component = actor.static_mesh_component
        component.set_material(0, self.material_instances[material])
        if material == "mist":
            component.set_editor_property("translucency_sort_priority", 10)  # draw after the water tiles, or the sheet is hidden wherever a tile is nearer
        if not collision:
            component.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)

    def _instance_blueprint(self):
        """An Actor with one hierarchical instanced mesh component, created once and reused for every tree/plant model."""
        path = "/Game/HPW/Forest/BP_TreeInstances"
        if not unreal.EditorAssetLibrary.does_asset_exist(path):
            factory = unreal.BlueprintFactory()
            factory.set_editor_property("parent_class", unreal.Actor)
            blueprint = unreal.AssetToolsHelpers.get_asset_tools().create_asset("BP_TreeInstances", "/Game/HPW/Forest", unreal.Blueprint, factory)
            subsystem = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
            root = subsystem.k2_gather_subobject_data_for_blueprint(blueprint)[0]
            params = unreal.AddNewSubobjectParams(parent_handle=root, new_class=unreal.HierarchicalInstancedStaticMeshComponent, blueprint_context=blueprint)
            subsystem.add_new_subobject(params)
            unreal.BlueprintEditorLibrary.compile_blueprint(blueprint)
            unreal.EditorAssetLibrary.save_loaded_asset(blueprint)
        return unreal.load_asset(path)

    def _forest_mesh(self, key):
        """([static meshes], height in cm) for an imported model; ([], 0) if it was not imported.

        A key is a Kenney model name, or "ench:<model>:<meshA>+<meshB>" for meshes of an /Game/HPW/Enchanted model that share one origin
        (trunk first, then foliage). The height is that of the whole group; only the first mesh collides.
        """
        cache = self.__dict__.setdefault("_forest_meshes", {})
        if key not in cache:
            if key.startswith("ench:"):
                _, model, parts = key.split(":")
                paths = [f"/Game/HPW/Enchanted/{model}/{model}/StaticMeshes/{n}" for n in parts.split("+")]
            else:
                disk = os.path.join(unreal.SystemLibrary.get_project_directory(), "Content", "HPW", "Forest", key, key, "StaticMeshes")
                names = sorted(f[:-len(".uasset")] for f in os.listdir(disk) if f.endswith(".uasset")) if os.path.isdir(disk) else []
                paths = [f"/Game/HPW/Forest/{key}/{key}/StaticMeshes/{names[0]}"] if names else []
            meshes = [unreal.load_asset(p) for p in paths]
            if not meshes or any(m is None for m in meshes):
                unreal.log_warning(f"Greybox: forest model {key} is missing; run Tools/Unreal/import_forest_m2.py or import_enchanted_m2.py")
                cache[key] = ([], 0.0)
            else:
                body = meshes[0].get_editor_property("body_setup")
                if body.get_editor_property("collision_trace_flag") != unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE:
                    body.set_editor_property("collision_trace_flag", unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
                    unreal.EditorAssetLibrary.save_loaded_asset(meshes[0])  # the broom collides with the real trunk and branches
                top = max(m.get_bounds().origin.z + m.get_bounds().box_extent.z for m in meshes)
                cache[key] = (meshes, top)
        return cache[key]

    def instanced_chunks(self, label, folder, mesh_folder, placements, collision):
        """Instances every mesh in mesh_folder at each placement (the parts of one scanned chunk share an origin)."""
        disk = os.path.join(unreal.SystemLibrary.get_project_directory(), "Content", mesh_folder[len("/Game/"):])
        names = sorted(f[:-len(".uasset")] for f in os.listdir(disk) if f.endswith(".uasset"))
        blueprint_class = self._instance_blueprint().generated_class()
        transforms = []
        for x, y, z, tangent, normal, scale in placements:
            rotation = unreal.MathLibrary.make_rot_from_xz(unreal.Vector(*tangent), unreal.Vector(*normal))
            transforms.append(unreal.Transform(unreal.Vector(x * M_TO_CM, y * M_TO_CM, z * M_TO_CM), rotation, unreal.Vector(*scale)))
        for name in names:
            mesh = unreal.load_asset(f"{mesh_folder}/{name}")
            if mesh is None or not transforms:
                continue
            actor = self.actors.spawn_actor_from_class(blueprint_class, unreal.Vector(0, 0, 0))
            component = actor.get_component_by_class(unreal.HierarchicalInstancedStaticMeshComponent)
            component.set_static_mesh(mesh)
            component.add_instances(transforms, False)
            if not collision:
                component.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
            actor.set_actor_label(f"{label}_{name}")
            actor.set_folder_path(f"Greybox/{folder}")
            self._tag(actor, [])

    def instanced_meshes(self, label, folder, groups, collision, cull_distance_m):
        """groups: {model name: [(x_m, y_m, ground_z_m, yaw_deg, height_m), ...]}; one instanced-mesh actor per model."""
        blueprint_class = self._instance_blueprint().generated_class()
        for key, items in groups.items():
            meshes, mesh_height_cm = self._forest_mesh(key)
            if not meshes or not items:
                continue
            transforms = []
            for x, y, z, yaw, height in items:
                scale = height * M_TO_CM / mesh_height_cm
                transforms.append(unreal.Transform(unreal.Vector(x * M_TO_CM, y * M_TO_CM, (z - 0.3) * M_TO_CM),  # sunk 30 cm so roots never float
                                                   unreal.Rotator(roll=0, pitch=0, yaw=yaw), unreal.Vector(scale, scale, scale)))
            for index, mesh in enumerate(meshes):
                actor = self.actors.spawn_actor_from_class(blueprint_class, unreal.Vector(0, 0, 0))
                component = actor.get_component_by_class(unreal.HierarchicalInstancedStaticMeshComponent)
                component.set_static_mesh(mesh)
                component.add_instances(transforms, False)
                if cull_distance_m:
                    component.set_editor_property("instance_end_cull_distance", int(cull_distance_m * M_TO_CM))
                if not collision or index > 0:
                    component.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
                actor.set_actor_label(f"{label}_{key.split(':')[-1][:40]}_{index}")
                actor.set_folder_path(f"Greybox/{folder}")
                self._tag(actor, [])

    def point_light(self, label, folder, position_m, color, intensity, radius_m):
        """A small movable, shadowless point light (the forest trail's lanterns)."""
        actor = self.actors.spawn_actor_from_class(unreal.PointLight, unreal.Vector(*(c * M_TO_CM for c in position_m)))
        component = actor.get_component_by_class(unreal.PointLightComponent)
        component.set_mobility(unreal.ComponentMobility.MOVABLE)
        component.set_editor_property("intensity", intensity)
        component.set_editor_property("light_color", unreal.Color(r=color[0], g=color[1], b=color[2], a=255))  # Python orders Color as b, g, r, a
        component.set_editor_property("attenuation_radius", radius_m * M_TO_CM)
        component.set_editor_property("cast_shadows", False)
        actor.set_actor_label(label)
        actor.set_folder_path(f"Greybox/{folder}")
        self._tag(actor, [])

    def castle_model(self, placement):
        """Places an imported model (many static meshes sharing one origin) as one object.

        The meshes are the .uasset files in placement["folder"] (or Object_<first>..<first+count-1> when "first" is given).
        A material of None keeps the model's own materials.
        """
        material = self.material_instances[placement["material"]] if placement["material"] else None
        location = unreal.Vector(*(c * M_TO_CM for c in placement["location_m"]))
        rotation = unreal.Rotator(roll=0, pitch=0, yaw=placement["yaw"])
        folder = placement["folder"]
        if placement.get("first") is not None:
            names = [f"Object_{i}" for i in range(placement["first"], placement["first"] + placement["count"])]
        else:
            disk = os.path.join(unreal.SystemLibrary.get_project_directory(), "Content", folder[len("/Game/"):])
            names = sorted(f[:-len(".uasset")] for f in os.listdir(disk) if f.endswith(".uasset"))
        names = [n for n in names if n not in placement["exclude"]]  # e.g. the model's own rock mountain
        for index, name in enumerate(names):
            mesh = unreal.load_asset(f"{folder}/{name}")
            if mesh is None:
                unreal.log_warning(f"Greybox: model mesh {name} is missing in {folder}")
                continue
            body = mesh.get_editor_property("body_setup")
            if body.get_editor_property("collision_trace_flag") != unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE:
                body.set_editor_property("collision_trace_flag", unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
                unreal.EditorAssetLibrary.save_loaded_asset(mesh)  # so the broom collides with the real geometry
            actor = self.actors.spawn_actor_from_class(unreal.StaticMeshActor, location, rotation)
            actor.static_mesh_component.set_static_mesh(mesh)
            actor.set_actor_scale3d(unreal.Vector(placement["scale"], placement["scale"], placement["scale"]))
            actor.set_actor_label(f"{placement['name']}_{index}")
            actor.set_folder_path(f"Greybox/{placement['name']}")
            self._tag(actor, [])
            if material is not None:
                for slot in range(actor.static_mesh_component.get_num_materials()):
                    actor.static_mesh_component.set_material(slot, material)

    def landscape(self, material):
        for actor in self.actors.get_all_level_actors():
            if isinstance(actor, unreal.LandscapeProxy):
                # Prefer the procedural M1 material (Tools/Unreal/build_landscape_material_m1.py) over the flat greybox colour.
                m1 = unreal.load_asset("/Game/HPW/Landscape/M_HPW_Landscape") if unreal.EditorAssetLibrary.does_asset_exist("/Game/HPW/Landscape/M_HPW_Landscape") else None
                actor.set_editor_property("landscape_material", m1 or self.material_instances[material])
                return
        unreal.log_warning("Greybox: layout says the Landscape is imported but none was found in the level")

    def lighting(self):
        def spawn(cls, label, rotation=(0.0, 0.0, 0.0), height_cm=50000):
            actor = self.actors.spawn_actor_from_class(
                cls, unreal.Vector(0, 0, height_cm), unreal.Rotator(roll=rotation[2], pitch=rotation[0], yaw=rotation[1]))
            actor.set_actor_label(label)
            actor.set_folder_path("Greybox/Lighting")
            self._tag(actor, [])
            return actor

        # Golden hour, low sun over the lake: the "first flight" mood.
        sun = spawn(unreal.DirectionalLight, "Sun", (-9.0, 125.0, 0.0))
        try:
            sun.light_component.set_mobility(unreal.ComponentMobility.MOVABLE)  # a Static sun is never baked here, so it would light nothing
            sun.light_component.set_editor_property("atmosphere_sun_light", True)
            sun.light_component.set_editor_property("intensity", 8.0)
            sun.light_component.set_editor_property("light_color", unreal.Color(255, 214, 170, 255))
        except Exception as error:  # property names drift between engine versions; lighting is cosmetic
            unreal.log_warning(f"Greybox: sun setup incomplete: {error}")
        spawn(unreal.SkyAtmosphere, "SkyAtmosphere")
        sky = spawn(unreal.SkyLight, "SkyLight")
        try:
            sky.light_component.set_mobility(unreal.ComponentMobility.MOVABLE)
            sky.light_component.set_editor_property("real_time_capture", True)
        except Exception as error:
            unreal.log_warning(f"Greybox: sky light setup incomplete: {error}")
        fog = spawn(unreal.ExponentialHeightFog, "HighlandMist", height_cm=0)  # fog is densest at and below its own height
        try:
            fog.component.set_editor_property("fog_density", 0.0004)
            fog.component.set_editor_property("fog_height_falloff", 0.02)
            fog.component.set_editor_property("enable_volumetric_fog", False)
        except Exception as error:
            unreal.log_warning(f"Greybox: fog setup incomplete: {error}")
        spawn(unreal.VolumetricCloud, "Clouds")

        self._forest_mood(spawn)
        self._lake_mood(spawn)

    def _forest_mood(self, spawn):
        """Two soft-edged post-process boxes over the Forbidden Forest: the deeper (further east) the camera goes, the darker, colder and greener.

        A box brush is 2 m at scale 1; blend_radius fades the effect in over that distance outside the box, so there is no visible border.
        """
        zones = [("ForestMoodEdge", (-150, 1320, 100), (2500, 1500, 400), 700.0, 0.55, -0.35, (0.92, 1.05, 0.98)),
                 ("ForestMoodDeep", (-150, 1700, 100), (2300, 700, 400), 500.0, 1.0, -1.1, (0.8, 1.05, 1.0))]
        for label, centre_m, size_m, blend_m, weight, bias, tint in zones:
            volume = spawn(unreal.PostProcessVolume, label)
            volume.set_actor_location(unreal.Vector(*(c * M_TO_CM for c in centre_m)), False, True)
            volume.set_actor_scale3d(unreal.Vector(*(s * M_TO_CM / 2.0 for s in size_m)))
            try:
                volume.set_editor_property("unbound", False)
                volume.set_editor_property("blend_radius", blend_m * M_TO_CM)
                volume.set_editor_property("blend_weight", weight)
                settings = volume.get_editor_property("settings")
                settings.set_editor_property("override_auto_exposure_bias", True)
                settings.set_editor_property("auto_exposure_bias", bias)
                settings.set_editor_property("override_color_saturation", True)
                settings.set_editor_property("color_saturation", unreal.Vector4(0.85, 0.85, 0.85, 1.0))
                settings.set_editor_property("override_scene_color_tint", True)
                settings.set_editor_property("scene_color_tint", unreal.LinearColor(tint[0], tint[1], tint[2], 1.0))
                settings.set_editor_property("override_vignette_intensity", True)
                settings.set_editor_property("vignette_intensity", 0.6)
                volume.set_editor_property("settings", settings)
            except Exception as error:
                unreal.log_warning(f"Greybox: forest mood setup incomplete: {error}")

    def _lake_mood(self, spawn):
        """One soft-edged post-process box over the Black Lake: a touch darker, colder and less saturated."""
        volume = spawn(unreal.PostProcessVolume, "LakeMood")
        volume.set_actor_location(unreal.Vector(710 * M_TO_CM, -800 * M_TO_CM, 0), False, True)
        volume.set_actor_scale3d(unreal.Vector(2200 * M_TO_CM / 2.0, 1400 * M_TO_CM / 2.0, 800 * M_TO_CM / 2.0))
        try:
            volume.set_editor_property("unbound", False)
            volume.set_editor_property("blend_radius", 350 * M_TO_CM)
            volume.set_editor_property("blend_weight", 0.8)
            settings = volume.get_editor_property("settings")
            settings.set_editor_property("override_auto_exposure_bias", True)
            settings.set_editor_property("auto_exposure_bias", -0.4)
            settings.set_editor_property("override_color_saturation", True)
            settings.set_editor_property("color_saturation", unreal.Vector4(0.72, 0.78, 0.8, 1.0))
            settings.set_editor_property("override_scene_color_tint", True)
            settings.set_editor_property("scene_color_tint", unreal.LinearColor(0.9, 0.97, 1.04, 1.0))
            volume.set_editor_property("settings", settings)
        except Exception as error:
            unreal.log_warning(f"Greybox: lake mood setup incomplete: {error}")

    def player_start(self, position_m, yaw):
        actor = self.actors.spawn_actor_from_class(
            unreal.PlayerStart, unreal.Vector(*(c * M_TO_CM for c in position_m)), unreal.Rotator(roll=0, pitch=0, yaw=yaw))
        actor.set_actor_label("PlayerStart_BroomShed")
        actor.set_folder_path("Greybox/Gameplay")
        self._tag(actor, [])

    def finish(self):
        self.levels.save_current_level()
        unreal.log(f"Greybox: built and saved {self.levels.get_current_level()}")


# --------------------------------------------------------------------------------------------------
# Layout -> shapes
# --------------------------------------------------------------------------------------------------

def yaw_towards(src, dst):
    return math.degrees(math.atan2(dst[1] - src[1], dst[0] - src[0]))


def ground(x, y):
    return GROUND_HEIGHT(x, y) if GROUND_HEIGHT else 0.0


def distance_to_polyline(px, py, points):
    """Distance in metres from (px, py) to a polyline of [x, y] points."""
    best = 1e18
    for (ax, ay), (bx, by) in zip(points, points[1:]):
        dx, dy = bx - ax, by - ay
        t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy or 1.0)))
        best = min(best, math.hypot(px - ax - t * dx, py - ay - t * dy))
    return best


def forest_depth(part, py):
    """0 at the forest's open (west) edge, 1 in its deepest part; the part's "depth_y" is [y at 0, y at 1] in metres."""
    y0, y1 = part["depth_y"]
    return max(0.0, min(1.0, (py - y0) / (y1 - y0)))


_SHORE_GRIDS = {}


def shore_grid(bbox, cell):
    """([[ground height m]] indexed [ix][iy], [[distance to water m]], cell) over bbox = [x0, x1, y0, y1]; water is ground below 0.3 m."""
    key = (tuple(bbox), cell)
    if key not in _SHORE_GRIDS:
        x0, x1, y0, y1 = bbox
        nx, ny = int((x1 - x0) / cell), int((y1 - y0) / cell)
        heights = [[ground(x0 + (i + 0.5) * cell, y0 + (j + 0.5) * cell) for j in range(ny)] for i in range(nx)]
        far = 1e9
        dist = [[0.0 if heights[i][j] < 0.3 else far for j in range(ny)] for i in range(nx)]
        diag = cell * 1.4142
        for i in range(nx):  # two-pass chamfer distance transform
            for j in range(ny):
                d = dist[i][j]
                for di, dj, w in ((-1, 0, cell), (0, -1, cell), (-1, -1, diag), (-1, 1, diag)):
                    a, b = i + di, j + dj
                    if 0 <= a < nx and 0 <= b < ny and dist[a][b] + w < d:
                        d = dist[a][b] + w
                dist[i][j] = d
        for i in range(nx - 1, -1, -1):
            for j in range(ny - 1, -1, -1):
                d = dist[i][j]
                for di, dj, w in ((1, 0, cell), (0, 1, cell), (1, 1, diag), (1, -1, diag)):
                    a, b = i + di, j + dj
                    if 0 <= a < nx and 0 <= b < ny and dist[a][b] + w < d:
                        d = dist[a][b] + w
                dist[i][j] = d
        _SHORE_GRIDS[key] = (heights, dist, cell)
    return _SHORE_GRIDS[key]


def scatter_ok(part, clearings, px, py, r, angle):
    """Shared placement filter for scatter and tree_scatter parts: ragged edge, clearings, ground height range, water only."""
    if part.get("ragged_edge"):
        limit = part["radius"] * (0.72 + 0.28 * (0.5 + 0.5 * math.sin(5 * angle + 11.0 * part["seed"]) * math.cos(2 * angle + part["seed"])))
        if r > limit:
            return False  # ragged forest edge instead of a clean circle
        if r < limit * part.get("min_edge_frac", 0.0):
            return False  # a wall of trees only along the outer rim
    if any(math.hypot(px - cx, py - cy) < rad for cx, cy, rad in part.get("inside_others", [])):
        return False  # the rim of one overlapping circle that lies inside another is not the forest's outside
    if any(math.hypot(px - c["center"][0], py - c["center"][1]) < c["radius"] for c in clearings):
        return False
    for path, clearance in part.get("avoid_paths", []):
        if distance_to_polyline(px, py, path) < clearance:
            return False  # keep trails open through the forest
    if "ground_range" in part and not part["ground_range"][0] <= ground(px, py) <= part["ground_range"][1]:
        return False  # e.g. shore boulders only where the bank meets the water
    if "min_slope" in part:
        step = 3.0  # m; central differences of the terrain height
        slope = math.hypot((ground(px + step, py) - ground(px - step, py)) / (2 * step),
                           (ground(px, py + step) - ground(px, py - step)) / (2 * step))
        if slope < part["min_slope"]:
            return False  # e.g. cliff rocks only on the steep cliff face
    if part.get("water_only") and ground(px, py) > -4.0:
        return False  # lake rocks: only where the basin is underwater
    return True


def cladding_placements(part):
    """Where to put the scanned cliff chunks so they cover the cliff face of the castle crag.

    For each height level the terrain contour is traced with rays from the centre; chunks are spaced evenly along it, tilted to the local slope
    (their relief points out of the slope, their long axis runs along the contour) and sunk part_sink metres into the ground.
    Returns [(x_m, y_m, z_m, tangent, normal, (sx, sy, sz))].
    """
    rng = random.Random(part["seed"])
    cx, cy = part["center"]
    spacing = part["face_width_m"] * part.get("overlap", 0.8)
    scale, depth, sink = part["scale"], part["depth_scale"], part["sink_m"]
    placements = []
    for row, level in enumerate(part["levels_m"]):
        contour = []
        for i in range(720):
            theta = 2 * math.pi * i / 720
            dx, dy = math.cos(theta), math.sin(theta)
            for r in range(20, 450):
                if ground(cx + r * dx, cy + r * dy) < level:
                    contour.append((theta, cx + r * dx, cy + r * dy))
                    break
        lengths = [math.hypot(contour[(i + 1) % len(contour)][1] - contour[i][1], contour[(i + 1) % len(contour)][2] - contour[i][2])
                   for i in range(len(contour))]
        total = sum(lengths)
        count = max(1, round(total / spacing))
        walked, k = 0.0, 0
        for i, length in enumerate(lengths):
            while k < count and walked + length >= (k + 0.5 + 0.5 * (row % 2) + rng.uniform(-0.2, 0.2)) * total / count:
                theta, x, y = contour[i]
                k += 1
                if any(abs((math.degrees(theta) - c + 180) % 360 - 180) < w for c, w in part.get("skip_arcs", [])):
                    continue  # e.g. leave the waterfall column bare
                step = 2.0
                hx = (ground(x + step, y) - ground(x - step, y)) / (2 * step)
                hy = (ground(x, y + step) - ground(x, y - step)) / (2 * step)
                norm = math.sqrt(hx * hx + hy * hy + 1.0)
                n = (-hx / norm, -hy / norm, 1.0 / norm)  # outward and up
                t = (-n[1], n[0], 0.0)
                t_len = math.hypot(t[0], t[1]) or 1.0
                t = (t[0] / t_len, t[1] / t_len, 0.0)
                # Break up the tiling: random quarter turn about the outward axis, scale and burial depth, rows staggered above.
                y_axis = (n[1] * t[2] - n[2] * t[1], n[2] * t[0] - n[0] * t[2], n[0] * t[1] - n[1] * t[0])
                turn = rng.choice([0, 90, 180, 270])
                c, s_ = math.cos(math.radians(turn)), math.sin(math.radians(turn))
                t = tuple(c * t[i] + s_ * y_axis[i] for i in range(3))
                size = rng.uniform(0.85, 1.25)
                dig = sink * rng.uniform(0.5, 1.5)
                z = level + rng.uniform(-5.0, 5.0)
                placements.append((x - dig * n[0], y - dig * n[1], z - dig * n[2], t, n, (scale * size, scale * size, scale * size * depth)))
            walked += length
    return placements


def trail_points(path, start_y, spacing):
    """Points along a polyline from where it first reaches y = start_y, with the given spacing in metres (a number or a (near, far) pair that
    widens as y grows). Returns [(x, y, unit tangent x, unit tangent y)]."""
    out = []
    carry = 0.0
    for (ax, ay), (bx, by) in zip(path, path[1:]):
        length = math.hypot(bx - ax, by - ay)
        tx, ty = (bx - ax) / length, (by - ay) / length
        d = 0.0
        while d < length:
            x, y = ax + tx * d, ay + ty * d
            if y >= start_y:
                if carry <= 0.0:
                    out.append((x, y, tx, ty))
                    if isinstance(spacing, (list, tuple)):
                        carry = spacing[0] + (spacing[1] - spacing[0]) * min(1.0, max(0.0, (y - start_y) / 1300.0))
                    else:
                        carry = spacing
                step = min(2.0, length - d)
                carry -= step
                d += step
            else:
                d += 2.0
    return out


def build_part(backend, folder, part):
    kind = part["type"]
    label = part["label"]
    material = part.get("material")
    tags = part.get("tags", [])
    collision = part.get("collision", True)
    base = part.get("base", 0.0)

    if kind == "box":
        sx, sy, sz = part["size"]
        cx, cy = part["center"]
        backend.shape("box", label, folder, (cx, cy, base + sz / 2), (sx, sy, sz), (0, part.get("yaw", 0), 0), material, tags, collision)

    elif kind in ("cylinder", "cone"):
        d, h = part["diameter"], part["height"]
        cx, cy = part["center"]
        backend.shape(kind, label, folder, (cx, cy, base + h / 2), (d, d, h), (0, 0, 0), material, tags, collision)

    elif kind == "lake":
        # The lake is a union of overlapping discs; the Landscape basin (Tools/terrain.py) shapes the shore.
        if "plane" in part:
            # The Landscape basin decides where the shoreline is, so the lake is a grid of water tiles under it.
            # Tiles, not one huge slab: a 2.5 km thin box renders with blocky lighting artefacts.
            px, py = part["plane"]["center"]; sx, sy = part["plane"]["size"]
            t = part.get("thickness", 0.2)
            tile = part["plane"].get("tile", 300.0)
            nx, ny = max(1, round(sx / tile)), max(1, round(sy / tile))
            for ix in range(nx):
                for iy in range(ny):
                    cx = px - sx / 2 + (ix + 0.5) * sx / nx
                    cy = py - sy / 2 + (iy + 0.5) * sy / ny
                    backend.shape("box", f"{label}_{ix}_{iy}", folder, (cx, cy, base + t / 2), (sx / nx, sy / ny, t), (0, 0, 0), material, tags, collision)
            return
        for i, (cx, cy, radius) in enumerate(part["blobs"]):
            backend.shape("cylinder", f"{label}{i + 1}", folder, (cx, cy, base + part.get("thickness", 0.2) / 2),
                          (radius * 2, radius * 2, part.get("thickness", 0.2)), (0, 0, 0), material, tags, collision)

    elif kind == "lake_mist":
        # Flat cold-mist sheets over the lake (collision off): the material fades them where they meet the water, shore or trees.
        px, py = part["plane"]["center"]; sx, sy = part["plane"]["size"]
        for i, height in enumerate(part["heights_m"]):
            backend.shape("box", f"{label}{i + 1}", folder, (px, py, base + height), (sx, sy, 0.2), (0, 0, 0), material, tags, False)

    elif kind == "sphere":
        d = part["diameter"]
        cx, cy = part["center"]
        backend.shape("sphere", label, folder, (cx, cy, base + d / 2), (d, d, d), (0, 0, 0), material, tags, collision)

    elif kind == "disc":
        dx, dy = part["diameter"]
        t = part["thickness"]
        cx, cy = part["center"]
        backend.shape("cylinder", label, folder, (cx, cy, base + t / 2), (dx, dy, t), (0, 0, 0), material, tags, collision)

    elif kind == "tower":
        # Round tower with a pointed roof, the castle's signature silhouette.
        d, h = part["diameter"], part["height"]
        cx, cy = part["center"]
        backend.shape("cylinder", label, folder, (cx, cy, base + h / 2), (d, d, h), (0, 0, 0), material, tags, collision)
        roof_h = d * 1.3
        backend.shape("cone", f"{label}Roof", folder, (cx, cy, base + h + roof_h / 2), (d * 1.25, d * 1.25, roof_h), (0, 0, 0),
                      part.get("roof_material", "roof"), tags, collision)

    elif kind == "span":
        # Bridges and viaducts: a deck from A to B with optional pillars down to the ground.
        a, b = part["from"], part["to"]
        dx, dy, dz = b[0] - a[0], b[1] - a[1], b[2] - a[2]
        horizontal = math.hypot(dx, dy)
        length = math.sqrt(horizontal * horizontal + dz * dz)
        yaw = math.degrees(math.atan2(dy, dx))
        pitch = math.degrees(math.atan2(dz, horizontal))
        w, h = part["width"], part["height"]
        center = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, (a[2] + b[2]) / 2 + h / 2)
        backend.shape("box", label, folder, center, (length, w, h), (pitch, yaw, 0), material, tags, collision)
        spacing = part.get("pillar_spacing")
        if spacing:
            count = int(horizontal // spacing)
            for i in range(1, count + 1):
                t = (i * spacing) / horizontal
                if t >= 1.0:
                    break
                px, py, pz = a[0] + dx * t, a[1] + dy * t, a[2] + dz * t
                if pz > 1.0:
                    backend.shape("box", f"{label}Pillar{i}", folder, (px, py, pz / 2), (w * 0.6, w * 0.6, pz), (0, yaw, 0),
                                  material, tags, collision)

    elif kind == "ring":
        # Evenly spaced blocks on an ellipse (stone circle, Quidditch stands).
        rx, ry = part["radii"]
        sx, sy, sz = part["size"]
        cx, cy = part["center"]
        materials = part.get("materials", [material])
        for i in range(part["count"]):
            angle = 2 * math.pi * i / part["count"]
            px, py = cx + rx * math.cos(angle), cy + ry * math.sin(angle)
            yaw = yaw_towards((px, py), (cx, cy))
            backend.shape("box", f"{label}{i + 1}", folder, (px, py, base + sz / 2), (sx, sy, sz), (0, yaw, 0),
                          materials[i % len(materials)], tags, collision)

    elif kind == "hoops":
        # Three goal hoops at each end of the pitch; hoops have no collision so you can fly through them.
        cx, cy = part["center"]
        d = part["diameter"]
        for end, sign in (("North", 1), ("South", -1)):
            x = cx + sign * part["end_offset"]
            for i, height in enumerate(part["heights"]):
                y = cy + (i - 1) * part["spacing"]
                backend.shape("cylinder", f"{label}{end}{i + 1}Post", folder, (x, y, height / 2), (0.4, 0.4, height), (0, 0, 0),
                              material, tags, True)
                backend.shape("cylinder", f"{label}{end}{i + 1}", folder, (x, y, height + d / 2), (d, d, 0.3), (90, 0, 0),
                              material, tags, False)

    elif kind == "scatter":
        rng = random.Random(part["seed"])
        cx, cy = part["center"]
        clearings = part.get("clearings", [])
        shape = part["shape"]
        placed = attempts = 0
        while placed < part["count"] and attempts < part["count"] * 20:
            attempts += 1
            r = part["radius"] * math.sqrt(rng.random())
            angle = rng.random() * 2 * math.pi
            px, py = cx + r * math.cos(angle), cy + r * math.sin(angle)
            if not scatter_ok(part, clearings, px, py, r, angle):
                continue
            d = rng.uniform(*part["diameter"])
            h = rng.uniform(*part["height"])
            size = (d, d * rng.uniform(0.7, 1.0), h) if shape == "box" else (d, d, h)
            placed += 1
            backend.shape(shape, f"{label}{placed}", folder, (px, py, base + ground(px, py) + h / 2), size, (0, rng.uniform(0, 360), 0),
                          material, tags, collision)

    elif kind == "cladding":
        backend.instanced_chunks(label, folder, part["mesh_folder"], cladding_placements(part), collision)

    elif kind == "tree_scatter":
        # Real tree models as instances: one instanced-mesh actor per model, not one actor per tree.
        rng = random.Random(part["seed"])
        cx, cy = part["center"]
        clearings = part.get("clearings", [])
        meshes = part["meshes"]
        weights = [m.get("weight", 1) for m in meshes]
        groups = {}
        placed = attempts = 0
        while placed < part["count"] and attempts < part["count"] * 20:
            attempts += 1
            r = part["radius"] * math.sqrt(rng.random())
            angle = rng.random() * 2 * math.pi
            px, py = cx + r * math.cos(angle), cy + r * math.sin(angle)
            if not scatter_ok(part, clearings, px, py, r, angle):
                continue
            if "depth_y" in part:
                depth = forest_depth(part, py)
                usable = [(m, w) for m, w in zip(meshes, weights) if m.get("depth", [0, 1])[0] <= depth <= m.get("depth", [0, 1])[1]]
                if not usable:
                    continue
                choice = rng.choices([m for m, _ in usable], [w for _, w in usable])[0]
                if "depth_density" in part and rng.random() > part["depth_density"][0] + (part["depth_density"][1] - part["depth_density"][0]) * depth:
                    continue  # thin out toward one end
            else:
                choice = rng.choices(meshes, weights)[0]
            height = rng.uniform(*choice["height_m"])
            groups.setdefault(choice["mesh"], []).append((px, py, base + ground(px, py) - part.get("sink", 0.0) * height, rng.uniform(0, 360), height))
            placed += 1
        backend.instanced_meshes(label, folder, groups, collision, part.get("cull_distance_m"))

    elif kind == "shore_scatter":
        # Reeds, boulders, moss and trees along the lake shore. A grid over the lake gives each cell its ground height and its distance to the nearest
        # water; each mesh entry takes the cells whose height ("z_range", m) and distance to water ("water_dist_m") fit, keeps a fraction ("keep") of them
        # and places one instance at a random spot in the cell.
        rng = random.Random(part["seed"])
        heights, water_dist, cell = shore_grid(part["bbox"], part["cell_m"])
        x0, _, y0, _ = part["bbox"]
        groups = {}
        for m in part["meshes"]:
            lo, hi = m["z_range"]
            dlo, dhi = m.get("water_dist_m", [0.0, 1e9])
            for ix, column in enumerate(heights):
                for iy, z in enumerate(column):
                    if not lo <= z <= hi or not dlo <= water_dist[ix][iy] <= dhi or rng.random() > m["keep"]:
                        continue
                    px, py = x0 + (ix + rng.random()) * cell, y0 + (iy + rng.random()) * cell
                    pz = ground(px, py)
                    if not lo <= pz <= hi or any(math.hypot(px - cx, py - cy) < r for cx, cy, r in part.get("avoid", [])):
                        continue
                    if any(distance_to_polyline(px, py, path) < clearance for path, clearance in part.get("avoid_paths", [])):
                        continue
                    if "max_slope" in m:
                        step = 4.0
                        if math.hypot((ground(px + step, py) - ground(px - step, py)) / (2 * step), (ground(px, py + step) - ground(px, py - step)) / (2 * step)) > m["max_slope"]:
                            continue  # too steep for trees
                    groups.setdefault(m["mesh"], []).append((px, py, base + pz - m.get("sink", 0.0) * m["height_m"][1], rng.uniform(0, 360), rng.uniform(*m["height_m"])))
        backend.instanced_meshes(label, folder, groups, collision, part.get("cull_distance_m"))

    elif kind == "placed_models":
        groups = {}
        for item in part["items"]:
            groups.setdefault(item["mesh"], []).append((item["x"], item["y"], base + ground(item["x"], item["y"]) + item.get("raise_m", 0.0), item.get("yaw", 0.0), item["height_m"]))
        backend.instanced_meshes(label, folder, groups, collision, None)

    elif kind == "forest_trail":
        # Lanterns on posts along the trail (fewer and further apart the deeper it goes), hero mossy trees beside it, and a small light in each lantern.
        rng = random.Random(part["seed"])
        lantern_groups, hero_groups = {}, {}
        for i, (x, y, tx, ty) in enumerate(trail_points(part["path"], part["start_y"], part["lantern_spacing_m"])):
            side = 1 if i % 2 == 0 else -1
            nx, ny = -ty * side, tx * side  # to the left or right of the direction of travel
            offset = part["lantern_side_m"] + rng.uniform(-0.8, 0.8)
            lx, ly = x + nx * offset, y + ny * offset
            ground_z = base + ground(lx, ly)
            post_h = part["post_height_m"]
            backend.shape("cylinder", f"{label}Post{i}", folder, (lx, ly, ground_z + post_h / 2), (0.22, 0.22, post_h), (0, 0, 0), part["post_material"], tags, False)
            mesh = rng.choice(part["lantern_meshes"])
            lantern_groups.setdefault(mesh, []).append((lx, ly, ground_z + post_h - 0.1, rng.uniform(0, 360), part["lantern_height_m"]))
            backend.point_light(f"{label}Light{i}", folder, (lx, ly, ground_z + post_h + 0.4), part["light_color"], part["light_intensity"], part["light_radius_m"])
        for i, (x, y, tx, ty) in enumerate(trail_points(part["path"], part["start_y"], part["hero_spacing_m"])):
            side = 1 if rng.random() < 0.5 else -1
            nx, ny = -ty * side, tx * side
            offset = rng.uniform(*part["hero_side_m"])
            hx, hy = x + nx * offset, y + ny * offset
            hero_h = rng.uniform(*part["hero_height_m"])
            hero_groups.setdefault(rng.choice(part["hero_meshes"]), []).append((hx, hy, base + ground(hx, hy) - part.get("hero_sink", 0.0) * hero_h, rng.uniform(0, 360), hero_h))
        backend.instanced_meshes(label + "Lanterns", folder, lantern_groups, False, 400)
        backend.instanced_meshes(label + "Heroes", folder, hero_groups, True, 700)

    elif kind == "mountains":
        rng = random.Random(part["seed"])
        r_min, r_max = part["radius"]
        for i in range(part["count"]):
            angle = 2 * math.pi * (i + rng.uniform(-0.3, 0.3)) / part["count"]
            r = rng.uniform(r_min, r_max)
            d = rng.uniform(*part["diameter"])
            h = rng.uniform(*part["height"])
            backend.shape("cone", f"{label}{i + 1}", folder, (r * math.cos(angle), r * math.sin(angle), h / 2), (d, d, h),
                          (0, 0, 0), material, tags, collision)

    else:
        raise ValueError(f"Unknown part type '{kind}' ({label})")


def castle_placement(cfg):
    """Scale, location (m) and yaw for the castle model so it fits the crag.

    The model's meshes share one origin, so the placement is worked out from their combined bounds: scale the width
    to cfg["width_m"], centre the footprint on cfg["target_center_m"] (after yaw) and sit the base at cfg["base_z_m"].
    """
    (lo_x, lo_y, lo_z), (hi_x, hi_y, hi_z) = cfg["bounds_cm"]
    scale = cfg["width_m"] * M_TO_CM / (hi_x - lo_x)
    cx, cy = (lo_x + hi_x) / 2 * scale, (lo_y + hi_y) / 2 * scale
    yaw = math.radians(cfg.get("yaw", 0.0))
    rx, ry = cx * math.cos(yaw) - cy * math.sin(yaw), cx * math.sin(yaw) + cy * math.cos(yaw)
    tx, ty = cfg["target_center_m"]
    location = ((tx * M_TO_CM - rx) / M_TO_CM, (ty * M_TO_CM - ry) / M_TO_CM, cfg["base_z_m"] - lo_z * scale / M_TO_CM)
    return {"scale": scale, "location_m": location, "yaw": cfg.get("yaw", 0.0), "folder": cfg["folder"], "first": cfg.get("first"),
            "count": cfg.get("count", 0), "material": cfg.get("material"), "name": cfg.get("name", "Model"),
            "exclude": set(cfg.get("exclude", []))}


def build(backend, layout):
    global GROUND_HEIGHT
    landscape = layout.get("landscape", {}).get("imported", False)
    if landscape:
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
        import terrain
        GROUND_HEIGHT = terrain.make_height_function(layout)
    backend.begin(layout["map_path"], layout["materials"])
    zones = layout["zones"]
    models = {key: layout[key] for key in ("castle_model", "pitch_model") if layout.get(key, {}).get("enabled")}
    task = unreal.ScopedSlowTask(len(zones), "Building Hogwarts greybox...") if unreal else None
    if task:
        task.make_dialog(True)
    for zone in zones:
        if task:
            task.enter_progress_frame(1, f"Building {zone['name']}...")
        for part in zone["parts"]:
            if part.get("replaced_by") in models:
                continue  # replaced by the imported castle model
            if landscape and part.get("terrain"):
                continue  # the Landscape provides this ground, hill or mountain
            build_part(backend, zone["name"], part)
    for cfg in models.values():
        backend.castle_model(castle_placement(cfg))
    if landscape:
        backend.landscape("grass")
    backend.lighting()
    start = layout["player_start"]
    backend.player_start(start["position"], yaw_towards(start["position"], start["face"]))
    backend.finish()


def main(argv):
    with open(layout_path(), encoding="utf-8") as handle:
        layout = json.load(handle)
    dry_run = "--dry-run" in argv or unreal is None
    build(DryRunBackend() if dry_run else UnrealBackend(), layout)


if __name__ == "__main__":
    main(sys.argv[1:])
