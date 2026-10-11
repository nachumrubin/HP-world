"""Bakes node transforms into vertex positions of a .glb and recentres it, so every mesh shares one origin.

Some Sketchfab models place their parts with per-node transforms. Unreal imports each mesh in its own local space, so the parts
no longer fit together unless the transforms are baked. This only works when each mesh is used by exactly one node (checked).

    python Tools/bake_glb.py in.glb out.glb          # recentre X/Z on the footprint centre and put the lowest point at Y = 0
"""

import json
import struct
import sys

import numpy as np


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
        m = np.eye(4)
        m[:3, 3] = node["translation"]
        matrix = m @ matrix
    return matrix


def read_glb(path):
    with open(path, "rb") as handle:
        magic, version, _ = struct.unpack("<4sII", handle.read(12))
        assert magic == b"glTF" and version == 2
        json_len, _ = struct.unpack("<I4s", handle.read(8))
        doc = json.loads(handle.read(json_len))
        bin_len, _ = struct.unpack("<I4s", handle.read(8))
        blob = bytearray(handle.read(bin_len))
    return doc, blob


def write_glb(path, doc, blob):
    payload = json.dumps(doc, separators=(",", ":")).encode("utf-8")
    payload += b" " * (-len(payload) % 4)
    blob += b"\0" * (-len(blob) % 4)
    with open(path, "wb") as handle:
        handle.write(struct.pack("<4sII", b"glTF", 2, 12 + 8 + len(payload) + 8 + len(blob)))
        handle.write(struct.pack("<I4s", len(payload), b"JSON") + payload)
        handle.write(struct.pack("<I4s", len(blob), b"BIN\0") + blob)


def accessor_view(doc, blob, index, count_components):
    acc = doc["accessors"][index]
    view = doc["bufferViews"][acc["bufferView"]]
    assert acc["componentType"] == 5126 and acc["type"] == "VEC3", "expected float VEC3"
    stride = view.get("byteStride", 12)
    base = view.get("byteOffset", 0) + acc.get("byteOffset", 0)
    return acc, base, stride


def world_matrices(doc):
    result = {}

    def walk(index, parent):
        node = doc["nodes"][index]
        world = parent @ local_matrix(node)
        if "mesh" in node:
            result[index] = world
        for child in node.get("children", []):
            walk(child, world)

    for root in doc["scenes"][doc.get("scene", 0)]["nodes"]:
        walk(root, np.eye(4))
    return result


def main(src, dst):
    doc, blob = read_glb(src)
    matrices = world_matrices(doc)
    used = [doc["nodes"][i]["mesh"] for i in matrices]
    assert len(used) == len(set(used)), "a mesh is shared by several nodes; baking in place is not safe"

    lo = np.full(3, np.inf)
    hi = np.full(3, -np.inf)
    for i, world in matrices.items():
        for prim in doc["meshes"][doc["nodes"][i]["mesh"]]["primitives"]:
            acc = doc["accessors"][prim["attributes"]["POSITION"]]
            for corner in np.array(np.meshgrid(*zip(acc["min"], acc["max"]))).reshape(3, -1).T:
                p = (world @ np.append(corner, 1.0))[:3]
                lo, hi = np.minimum(lo, p), np.maximum(hi, p)
    shift = np.array([-(lo[0] + hi[0]) / 2, -lo[1], -(lo[2] + hi[2]) / 2])

    for i, world in matrices.items():
        full = np.eye(4)
        full[:3, 3] = shift
        full = full @ world
        normal_matrix = np.linalg.inv(world[:3, :3]).T
        for prim in doc["meshes"][doc["nodes"][i]["mesh"]]["primitives"]:
            for name, matrix, translate in (("POSITION", full, True), ("NORMAL", normal_matrix, False)):
                if name not in prim["attributes"]:
                    continue
                acc, base, stride = accessor_view(doc, blob, prim["attributes"][name], 3)
                count = acc["count"]
                data = np.frombuffer(blob, dtype=np.uint8)
                raw = np.stack([np.frombuffer(blob, dtype="<f4", count=3, offset=base + k * stride) for k in range(count)]).astype(np.float64)
                out = (raw @ matrix[:3, :3].T) + (matrix[:3, 3] if translate else 0.0)
                if not translate:
                    out /= np.maximum(np.linalg.norm(out, axis=1, keepdims=True), 1e-12)
                for k in range(count):
                    blob[base + k * stride: base + k * stride + 12] = out[k].astype("<f4").tobytes()
                if translate:
                    acc["min"], acc["max"] = out.min(axis=0).tolist(), out.max(axis=0).tolist()
        doc["nodes"][i].pop("matrix", None)
        for key in ("translation", "rotation", "scale"):
            doc["nodes"][i].pop(key, None)
    for node in doc["nodes"]:  # ancestors keep no transform either, or the baked vertices would be moved twice
        for key in ("matrix", "translation", "rotation", "scale"):
            node.pop(key, None)
    write_glb(dst, doc, blob)
    size = hi - lo
    print(f"baked {len(matrices)} meshes; footprint {size[0]:.1f} x {size[2]:.1f}, height {size[1]:.1f} (glTF units)")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
