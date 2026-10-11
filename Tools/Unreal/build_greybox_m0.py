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
        lib.set_material_instance_parent(mi, self._water_material() if name == "water" else self._parent_material())
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
        if not collision:
            component.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)

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
                    backend.shape("box", f"{label}_{ix}_{iy}", folder, (cx, cy, base + t / 2), (sx / nx + 0.5, sy / ny + 0.5, t), (0, 0, 0), material, tags, collision)
            return
        for i, (cx, cy, radius) in enumerate(part["blobs"]):
            backend.shape("cylinder", f"{label}{i + 1}", folder, (cx, cy, base + part.get("thickness", 0.2) / 2),
                          (radius * 2, radius * 2, part.get("thickness", 0.2)), (0, 0, 0), material, tags, collision)

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
            if part.get("ragged_edge") and r > part["radius"] * (0.72 + 0.28 * (0.5 + 0.5 * math.sin(5 * angle + 11.0 * part["seed"]) * math.cos(2 * angle + part["seed"]))):
                continue  # ragged forest edge instead of a clean circle
            if any(math.hypot(px - c["center"][0], py - c["center"][1]) < c["radius"] for c in clearings):
                continue
            if "ground_range" in part and not part["ground_range"][0] <= ground(px, py) <= part["ground_range"][1]:
                continue  # e.g. shore boulders only where the bank meets the water
            if part.get("water_only") and ground(px, py) > -4.0:
                continue  # lake rocks: only where the basin is underwater
            d = rng.uniform(*part["diameter"])
            h = rng.uniform(*part["height"])
            size = (d, d * rng.uniform(0.7, 1.0), h) if shape == "box" else (d, d, h)
            placed += 1
            backend.shape(shape, f"{label}{placed}", folder, (px, py, base + ground(px, py) + h / 2), size, (0, rng.uniform(0, 360), 0),
                          material, tags, collision)

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
            "count": cfg.get("count", 0), "material": cfg.get("material"), "name": cfg.get("name", "Model")}


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
