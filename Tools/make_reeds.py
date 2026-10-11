"""Generates SourceAssets/Enchanted/reeds.glb: one clump of curved reed blades (no textures; the material is assigned in Unreal).

Each blade is a ribbon of 6 segments that tapers to a point and bends over towards its tip; UV v runs 0 at the root to 1 at the tip, which the
reed material uses for a root-to-tip colour gradient. The clump is about 1 m across and 1.6 m tall (the layout scales it by height).

    python Tools/make_reeds.py
"""

import json
import math
import random
import struct

import numpy as np

SEGMENTS = 6
BLADES = 26


def blade(rng):
    heading = rng.uniform(0, 2 * math.pi)
    root = rng.uniform(0, 2 * math.pi), 0.38 * math.sqrt(rng.random())
    ox, oy = root[1] * math.cos(root[0]), root[1] * math.sin(root[0])
    height = rng.uniform(1.0, 1.6)
    lean = rng.uniform(0.05, 0.35)      # how far the tip ends up from the root, as a fraction of the height
    width = rng.uniform(0.022, 0.04)
    side = (-math.sin(heading + math.pi / 2), math.cos(heading + math.pi / 2))
    pts = []
    for i in range(SEGMENTS + 1):
        t = i / SEGMENTS
        out = lean * height * t * t
        pts.append((ox + math.cos(heading) * out, oy + math.sin(heading) * out, height * (t - 0.12 * t * t * lean), t))
    verts, uvs, idx = [], [], []
    for i, (x, y, z, t) in enumerate(pts):
        w = width * (1.0 - t) ** 0.8 * 0.5
        verts += [(x - side[0] * w, y - side[1] * w, z), (x + side[0] * w, y + side[1] * w, z)]
        uvs += [(0.0, t), (1.0, t)]
        if i:
            a = 2 * (i - 1)
            idx += [a, a + 1, a + 2, a + 1, a + 3, a + 2]
    return verts, uvs, idx


def main():
    rng = random.Random(5)
    pos, uv, idx = [], [], []
    for _ in range(BLADES):
        v, u, i = blade(rng)
        base = len(pos)
        pos += v
        uv += u
        idx += [base + k for k in i]
    # glTF is Y-up: swap so the blades grow along +Y
    pos = np.array([(x, z, -y) for x, y, z in pos], dtype=np.float32)
    nrm = np.tile(np.array([0.0, 0.7, 0.7], dtype=np.float32), (len(pos), 1))
    nrm /= np.linalg.norm(nrm, axis=1, keepdims=True)
    uv = np.array(uv, dtype=np.float32)
    idx = np.array(idx, dtype=np.uint32)
    blob = bytearray()
    views, accessors = [], []

    def add(array, ctype, atype, target, bounds=False):
        views.append({"buffer": 0, "byteOffset": len(blob), "byteLength": array.nbytes, "target": target})
        blob.extend(array.tobytes())
        acc = {"bufferView": len(views) - 1, "componentType": ctype, "count": len(array), "type": atype}
        if bounds:
            acc["min"], acc["max"] = array.min(axis=0).tolist(), array.max(axis=0).tolist()
        accessors.append(acc)
        return len(accessors) - 1

    prim = {"attributes": {"POSITION": add(pos, 5126, "VEC3", 34962, True), "NORMAL": add(nrm, 5126, "VEC3", 34962), "TEXCOORD_0": add(uv, 5126, "VEC2", 34962)},
            "indices": add(idx, 5125, "SCALAR", 34963), "mode": 4, "material": 0}
    gltf = {"asset": {"version": "2.0", "generator": "Tools/make_reeds.py"}, "scene": 0, "scenes": [{"nodes": [0]}], "nodes": [{"mesh": 0, "name": "reeds"}],
            "meshes": [{"name": "reeds", "primitives": [prim]}], "materials": [{"name": "Reed", "doubleSided": True}],
            "accessors": accessors, "bufferViews": views, "buffers": [{"byteLength": len(blob)}]}
    body = json.dumps(gltf, separators=(",", ":")).encode()
    body += b" " * (-len(body) % 4)
    blob.extend(b"\0" * (-len(blob) % 4))
    with open("SourceAssets/Enchanted/reeds.glb", "wb") as f:
        f.write(struct.pack("<4sII", b"glTF", 2, 12 + 8 + len(body) + 8 + len(blob)))
        f.write(struct.pack("<I4s", len(body), b"JSON") + body)
        f.write(struct.pack("<I4s", len(blob), b"BIN\x00") + bytes(blob))
    print(f"{len(pos)} vertices, {len(idx) // 3} triangles, height {pos[:, 1].max():.2f} m")


main()
