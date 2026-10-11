"""Flattens a .glb into ONE mesh with one primitive per material, node transforms baked in, recentred (X/Z on the footprint centre, lowest Y = 0) and scaled to 10 m tall.

For models built from thousands of nodes that re-use a few meshes (leaf cards, petals), which Tools/bake_glb.py cannot handle.
Keeps POSITION, NORMAL and TEXCOORD_0 only.

    python Tools/merge_glb.py in.glb out.glb          # everything as one mesh
    python Tools/merge_glb.py in.glb out.glb --split  # one mesh per mesh-bearing node, each recentred on its own (for packs of separate plants)
"""

import json
import struct
import sys

import numpy as np

COMPONENT = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
WIDTH = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}


def local_matrix(node):
    if "matrix" in node:
        return np.array(node["matrix"], dtype=np.float64).reshape(4, 4).T
    matrix = np.eye(4)
    if "scale" in node:
        matrix = matrix @ np.diag(list(node["scale"]) + [1.0])
    if "rotation" in node:
        x, y, z, w = node["rotation"]
        rot = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])
        m = np.eye(4)
        m[:3, :3] = rot
        matrix = m @ matrix
    if "translation" in node:
        t = np.eye(4)
        t[:3, 3] = node["translation"]
        matrix = t @ matrix
    return matrix


def main(src, dst, split=False):
    data = open(src, "rb").read()
    json_len = struct.unpack("<I", data[12:16])[0]
    gltf = json.loads(data[20:20 + json_len])
    bin_start = 20 + json_len + 8
    blob = data[bin_start:]

    def read(index):
        acc = gltf["accessors"][index]
        view = gltf["bufferViews"][acc["bufferView"]]
        dtype = COMPONENT[acc["componentType"]]
        width = WIDTH[acc["type"]]
        offset = view.get("byteOffset", 0) + acc.get("byteOffset", 0)
        stride = view.get("byteStride") or width * np.dtype(dtype).itemsize
        raw = np.frombuffer(blob, dtype=np.uint8, count=stride * (acc["count"] - 1) + width * np.dtype(dtype).itemsize, offset=offset)
        rows = np.lib.stride_tricks.as_strided(raw, shape=(acc["count"], width * np.dtype(dtype).itemsize), strides=(stride, 1))
        out = np.frombuffer(np.ascontiguousarray(rows).tobytes(), dtype=dtype).reshape(acc["count"], width)
        if acc.get("normalized"):
            out = out.astype(np.float32) / np.iinfo(dtype).max
        return out

    world = {}

    def walk(index, parent):
        matrix = parent @ local_matrix(gltf["nodes"][index])
        world[index] = matrix
        for child in gltf["nodes"][index].get("children", []):
            walk(child, matrix)

    for root in gltf["scenes"][gltf.get("scene", 0)]["nodes"]:
        walk(root, np.eye(4))

    parts = {}  # (group, material index) -> lists
    for index, matrix in world.items():
        mesh_index = gltf["nodes"][index].get("mesh")
        if mesh_index is None:
            continue
        normal_matrix = np.linalg.inv(matrix[:3, :3]).T
        flip = np.linalg.det(matrix[:3, :3]) < 0
        for prim in gltf["meshes"][mesh_index]["primitives"]:
            if prim.get("mode", 4) != 4:
                continue
            attrs = prim["attributes"]
            pos = read(attrs["POSITION"]).astype(np.float64)
            pos = pos @ matrix[:3, :3].T + matrix[:3, 3]
            nrm = read(attrs["NORMAL"]).astype(np.float64) @ normal_matrix.T if "NORMAL" in attrs else np.zeros_like(pos)
            length = np.linalg.norm(nrm, axis=1, keepdims=True)
            nrm = nrm / np.where(length == 0, 1, length)
            uv = read(attrs["TEXCOORD_0"]).astype(np.float32) if "TEXCOORD_0" in attrs else np.zeros((len(pos), 2), np.float32)
            idx = read(prim["indices"]).reshape(-1).astype(np.int64) if "indices" in prim else np.arange(len(pos))
            if flip:
                idx = idx.reshape(-1, 3)[:, ::-1].reshape(-1)
            bucket = parts.setdefault((index if split else 0, prim.get("material", -1)), {"pos": [], "nrm": [], "uv": [], "idx": [], "base": 0})
            bucket["pos"].append(pos)
            bucket["nrm"].append(nrm)
            bucket["uv"].append(uv)
            bucket["idx"].append(idx + bucket["base"])
            bucket["base"] += len(pos)

    out_blob = bytearray()
    views, accessors, meshes = [], [], []

    def add(array, ctype, atype, target, with_bounds=False):
        while len(out_blob) % 4:
            out_blob.append(0)
        views.append({"buffer": 0, "byteOffset": len(out_blob), "byteLength": array.nbytes, "target": target})
        out_blob.extend(array.tobytes())
        acc = {"bufferView": len(views) - 1, "componentType": ctype, "count": len(array), "type": atype}
        if with_bounds:
            acc["min"], acc["max"] = array.min(axis=0).tolist(), array.max(axis=0).tolist()
        accessors.append(acc)
        return len(accessors) - 1

    sizes = []
    for group in sorted({g for g, _ in parts}):
        members = {m: b for (g, m), b in parts.items() if g == group}
        allpos = np.concatenate([np.concatenate(b["pos"]) for b in members.values()])
        lo, hi = allpos.min(axis=0), allpos.max(axis=0)
        shift = np.array([(lo[0] + hi[0]) / 2, lo[1], (lo[2] + hi[2]) / 2])
        unit = 10.0 / max(hi[1] - lo[1], 1e-9)  # normalise to a 10 m tall model; the layout scales by height anyway
        prims = []
        for material, b in members.items():
            pos = ((np.concatenate(b["pos"]) - shift) * unit).astype(np.float32)
            prim = {"attributes": {"POSITION": add(pos, 5126, "VEC3", 34962, True),
                                   "NORMAL": add(np.concatenate(b["nrm"]).astype(np.float32), 5126, "VEC3", 34962),
                                   "TEXCOORD_0": add(np.concatenate(b["uv"]), 5126, "VEC2", 34962)},
                    "indices": add(np.concatenate(b["idx"]).astype(np.uint32), 5125, "SCALAR", 34963), "mode": 4}
            if material >= 0:
                prim["material"] = material
            prims.append(prim)
        meshes.append({"name": f"Merged{group}", "primitives": prims})
        sizes.append((hi - lo) * unit)

    # Keep images in the new binary chunk.
    images = []
    for image in gltf.get("images", []):
        view = gltf["bufferViews"][image["bufferView"]]
        chunk = blob[view.get("byteOffset", 0):view.get("byteOffset", 0) + view["byteLength"]]
        while len(out_blob) % 4:
            out_blob.append(0)
        views.append({"buffer": 0, "byteOffset": len(out_blob), "byteLength": len(chunk)})
        out_blob.extend(chunk)
        images.append({"bufferView": len(views) - 1, "mimeType": image.get("mimeType", "image/png")})

    new = {"asset": gltf["asset"], "scene": 0, "scenes": [{"nodes": list(range(len(meshes)))}], "nodes": [{"mesh": i, "name": m["name"]} for i, m in enumerate(meshes)],
           "meshes": meshes, "materials": gltf.get("materials", []), "accessors": accessors,
           "bufferViews": views, "buffers": [{"byteLength": len(out_blob)}]}
    for key in ("textures", "samplers", "extensionsUsed"):
        if key in gltf:
            new[key] = gltf[key]
    if images:
        new["images"] = images
    body = json.dumps(new, separators=(",", ":")).encode()
    body += b" " * (-len(body) % 4)
    while len(out_blob) % 4:
        out_blob.append(0)
    total = 12 + 8 + len(body) + 8 + len(out_blob)
    with open(dst, "wb") as f:
        f.write(struct.pack("<4sII", b"glTF", 2, total))
        f.write(struct.pack("<I4s", len(body), b"JSON") + body)
        f.write(struct.pack("<I4s", len(out_blob), b"BIN\x00") + bytes(out_blob))
    for i, size in enumerate(sizes):
        print(f"mesh {i}: size {size[0]:.2f} x {size[2]:.2f}, height {size[1]:.2f} m (normalised)")
    print(f"merged {len(world)} nodes into {len(meshes)} mesh(es)")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], "--split" in sys.argv)
