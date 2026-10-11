"""Recolours the imported Kenney nature materials (/Game/HPW/Forest/*/*/Materials) with the project's dark forest palette.

Kenney's .glb files give base colours as linear factors, which come out bright and flat in Unreal (teal leaves, orange bark), and mark every
material fully metallic, so trees and rocks render as grey mirrors. This replaces each material's BaseColorFactor by name and sets it non-metallic. Run it after Tools/Unreal/import_forest_m2.py (re-importing resets the colours).

Headless:  UnrealEditor-Cmd.exe HPWorld.uproject -run=pythonscript -script=Tools/Unreal/recolor_forest_m2.py
"""

import os

import unreal

PALETTE = {  # linear RGB
    "leafsDark": (0.012, 0.05, 0.028),
    "leafsGreen": (0.035, 0.11, 0.035),
    "woodBarkDark": (0.05, 0.03, 0.02),
    "woodBark": (0.07, 0.045, 0.03),
    "woodInner": (0.2, 0.14, 0.09),
    "dirt": (0.09, 0.075, 0.06),     # rock bodies
    "grass": (0.04, 0.09, 0.035),    # moss on the rocks
    "_defaultMat": (0.12, 0.11, 0.10),
    "colorRed": (0.5, 0.04, 0.03),
    "colorTan": (0.35, 0.28, 0.18),
}

root = os.path.join(unreal.SystemLibrary.get_project_directory(), "Content", "HPW", "Forest")
done = 0
for model in sorted(os.listdir(root)):
    folder = os.path.join(root, model, model, "Materials")
    if not os.path.isdir(folder):
        continue
    for name in sorted(f[:-len(".uasset")] for f in os.listdir(folder) if f.endswith(".uasset")):
        material = unreal.load_asset(f"/Game/HPW/Forest/{model}/{model}/Materials/{name}")
        if not isinstance(material, unreal.MaterialInstanceConstant):
            continue
        if name in PALETTE:
            rgb = PALETTE[name]
        else:  # unknown material: keep its hue but make it much darker
            current = unreal.MaterialEditingLibrary.get_material_instance_vector_parameter_value(material, "BaseColorFactor")
            rgb = (current.r * 0.2, current.g * 0.2, current.b * 0.2)
        unreal.MaterialEditingLibrary.set_material_instance_vector_parameter_value(material, "BaseColorFactor", unreal.LinearColor(rgb[0], rgb[1], rgb[2], 1.0))
        unreal.MaterialEditingLibrary.set_material_instance_scalar_parameter_value(material, "MetallicFactor", 0.0)
        unreal.MaterialEditingLibrary.set_material_instance_scalar_parameter_value(material, "RoughnessFactor", 0.85)
        unreal.MaterialEditingLibrary.update_material_instance(material)
        unreal.EditorAssetLibrary.save_loaded_asset(material)
        done += 1
unreal.log(f"HPW: recoloured {done} nature materials")
