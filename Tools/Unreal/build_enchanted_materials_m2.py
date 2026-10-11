"""Builds one textured material per imported enchanted-forest material (/Game/HPW/Enchanted/Materials/M_Ench_<model>_<name>) and puts it on the meshes.

The materials Interchange makes for the glTF models cannot be used on instanced meshes (they render as the checker fallback), so these are plain
masters with the flags set: base colour (and normal) texture, alpha-masked when the original was blended (leaf cards), two-sided, and a glow
from the emissive texture where the model has one. "Tint" darkens everything toward the forest's mood. Run after import_enchanted_m2.py.

Headless:  UnrealEditor-Cmd.exe HPWorld.uproject -run=pythonscript -script=Tools/Unreal/build_enchanted_materials_m2.py
"""

import os

import unreal

mel = unreal.MaterialEditingLibrary
tools = unreal.AssetToolsHelpers.get_asset_tools()
DEST = "/Game/HPW/Enchanted/Materials"
TINT = {"trees": (0.55, 0.62, 0.5), "fantasy_tree": (0.6, 0.65, 0.6)}  # default 1,1,1
TINT_BY_MATERIAL = {"fantasy_tree/Blatt1": (0.12, 0.8, 0.65), "fantasy_tree/M_Wood": (0.55, 0.55, 0.9), "mushroom_b/2_002": (0.35, 0.55, 1.2), "mushroom_b/2_003": (0.35, 0.55, 1.2)}  # the leaf texture is autumn orange; this turns it teal-green
GLOW = {"mushroom_a": 6.0, "plant": 4.0}  # emissive multiplier for models with an emissive texture
root = os.path.join(unreal.SystemLibrary.get_project_directory(), "Content", "HPW", "Enchanted")
os.makedirs(os.path.join(root, "Materials"), exist_ok=True)


def param(inst, *names):
    wanted = {}
    for t in inst.get_editor_property("texture_parameter_values"):
        wanted[str(t.get_editor_property("parameter_info").get_editor_property("name"))] = t.get_editor_property("parameter_value")
    for n in names:
        if wanted.get(n):
            return wanted[n]
    return None


made = {}
for model in sorted(os.listdir(root)):
    mats = os.path.join(root, model, model, "Materials")
    if not os.path.isdir(mats):
        continue
    for name in sorted(f[:-len(".uasset")] for f in os.listdir(mats) if f.endswith(".uasset")):
        if name.startswith("M_Ench_"):
            continue
        inst = unreal.load_asset(f"/Game/HPW/Enchanted/{model}/{model}/Materials/{name}")
        parent = inst.get_editor_property("parent").get_name()
        base = param(inst, "BaseColorTexture", "DiffuseTexture")
        normal = param(inst, "NormalTexture")
        emissive = param(inst, "EmissiveTexture")
        asset_name = f"M_Ench_{model}_{name}"
        if unreal.EditorAssetLibrary.does_asset_exist(f"{DEST}/{asset_name}"):
            mat = unreal.load_asset(f"{DEST}/{asset_name}")  # rebuilt in place so the meshes keep pointing at it
            mel.delete_all_material_expressions(mat)
        else:
            mat = tools.create_asset(asset_name, DEST, unreal.Material, unreal.MaterialFactoryNew())
        sample = mel.create_material_expression(mat, unreal.MaterialExpressionTextureSample, -700, 0)
        sample.set_editor_property("texture", base)
        tint = mel.create_material_expression(mat, unreal.MaterialExpressionVectorParameter, -700, 200)
        tint.set_editor_property("parameter_name", "Tint")
        t = TINT_BY_MATERIAL.get(f"{model}/{name}", TINT.get(model, (1.0, 1.0, 1.0)))
        tint.set_editor_property("default_value", unreal.LinearColor(t[0], t[1], t[2], 1.0))
        mul = mel.create_material_expression(mat, unreal.MaterialExpressionMultiply, -400, 0)
        mel.connect_material_expressions(sample, "RGB", mul, "A")
        mel.connect_material_expressions(tint, "", mul, "B")
        mel.connect_material_property(mul, "", unreal.MaterialProperty.MP_BASE_COLOR)
        rough = mel.create_material_expression(mat, unreal.MaterialExpressionConstant, -400, 250)
        rough.set_editor_property("r", 0.85)
        mel.connect_material_property(rough, "", unreal.MaterialProperty.MP_ROUGHNESS)
        if normal:
            n = mel.create_material_expression(mat, unreal.MaterialExpressionTextureSample, -700, 400)
            n.set_editor_property("texture", normal)
            n.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL)
            mel.connect_material_property(n, "RGB", unreal.MaterialProperty.MP_NORMAL)
        if emissive and model in GLOW:
            e = mel.create_material_expression(mat, unreal.MaterialExpressionTextureSample, -700, 600)
            e.set_editor_property("texture", emissive)
            gain = mel.create_material_expression(mat, unreal.MaterialExpressionConstant, -700, 800)
            gain.set_editor_property("r", GLOW[model])
            em = mel.create_material_expression(mat, unreal.MaterialExpressionMultiply, -400, 650)
            mel.connect_material_expressions(e, "RGB", em, "A")
            mel.connect_material_expressions(gain, "", em, "B")
            mel.connect_material_property(em, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
        if "Blend" in parent:
            mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_MASKED)
            mat.set_editor_property("opacity_mask_clip_value", 0.4)
            mel.connect_material_property(sample, "A", unreal.MaterialProperty.MP_OPACITY_MASK)
        mat.set_editor_property("two_sided", True)
        mat.set_editor_property("used_with_instanced_static_meshes", True)
        mat.set_editor_property("used_with_nanite", True)
        mel.recompile_material(mat)
        unreal.EditorAssetLibrary.save_loaded_asset(mat)
        made[f"{model}/{name}"] = mat
        unreal.log(f"HPW: material {asset_name} from {parent} (mask={'Blend' in parent}, normal={normal is not None}, emissive={emissive is not None and model in GLOW})")

for model in sorted(os.listdir(root)):
    meshes = os.path.join(root, model, model, "StaticMeshes")
    if not os.path.isdir(meshes):
        continue
    for name in sorted(f[:-len(".uasset")] for f in os.listdir(meshes) if f.endswith(".uasset")):
        mesh = unreal.load_asset(f"/Game/HPW/Enchanted/{model}/{model}/StaticMeshes/{name}")
        for index, slot in enumerate(mesh.get_editor_property("static_materials")):
            current = slot.get_editor_property("material_interface")
            key = f"{model}/{current.get_name()}" if current else None
            if current and current.get_name().startswith(f"M_Ench_{model}_"):
                key = f"{model}/{current.get_name()[len(f'M_Ench_{model}_'):]}"  # already ours (the script was run before)
            if key in made:
                mesh.set_material(index, made[key])
        unreal.EditorAssetLibrary.save_loaded_asset(mesh)
