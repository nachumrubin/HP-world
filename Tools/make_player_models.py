"""Builds the player's models from the two Sketchfab downloads in SourceAssets/Player/raw (see docs/CREDITS.md):

    SourceAssets/Enchanted/harry_rider.glb   "Harry Potter" by Matthew Tew, posed for riding
    SourceAssets/Enchanted/nimbus.glb        "Nimbus 2000" by Alizee Bourbon, in metres, long axis along glTF +Z, bristles at -Z, centred

Harry is a T-posed static mesh with no skeleton, so he is posed by blending rigid rotations by hand (a tiny hand-rolled skin):
the arms swing forward to the handle, the whole body pitches forward into the racing lean and the knees bend so the feet trail up behind.
The result is one mesh (one primitive per material), origin at his hips, facing glTF +Z, 1.75 m tall when standing.

    python Tools/make_player_models.py
"""

import json
import os
import struct
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from merge_glb import COMPONENT, WIDTH, local_matrix  # noqa: E402

RAW = os.path.join(ROOT, "SourceAssets", "Player", "raw")
OUT = os.path.join(ROOT, "SourceAssets", "Enchanted")

TORSO_LEAN = 42.0     # degrees the torso leans forward from upright, about the hips
THIGH_LIFT = 80.0     # degrees the thighs swing forward (90 = horizontal along the broom)
HEIGHT_M = 1.75
SKIRT_MATERIAL = 11    # 'material_1.007': the long robe


def load(path):
    data = open(path, "rb").read()
    n = struct.unpack("<I", data[12:16])[0]
    return json.loads(data[20:20 + n]), data[20 + n + 8:]


def read(gltf, blob, index):
    acc = gltf["accessors"][index]
    view = gltf["bufferViews"][acc["bufferView"]]
    dtype = COMPONENT[acc["componentType"]]
    width = WIDTH[acc["type"]]
    item = width * np.dtype(dtype).itemsize
    off = view.get("byteOffset", 0) + acc.get("byteOffset", 0)
    stride = view.get("byteStride") or item
    raw = np.frombuffer(blob, dtype=np.uint8, count=stride * (acc["count"] - 1) + item, offset=off)
    rows = np.lib.stride_tricks.as_strided(raw, shape=(acc["count"], item), strides=(stride, 1))
    out = np.frombuffer(np.ascontiguousarray(rows).tobytes(), dtype=dtype).reshape(acc["count"], width)
    if acc.get("normalized"):
        out = out.astype(np.float32) / np.iinfo(dtype).max
    return out


def smooth(v, a, b):
    t = np.clip((v - a) / (b - a), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def rot_x(deg):
    c, s = np.cos(np.radians(deg)), np.sin(np.radians(deg))
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def rot_between(a, b):
    """Rotation matrix taking unit vector a to unit vector b."""
    a, b = a / np.linalg.norm(a), b / np.linalg.norm(b)
    v = np.cross(a, b)
    c = float(np.dot(a, b))
    if np.linalg.norm(v) < 1e-9:
        return np.eye(3)
    k = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + k + k @ k * (1.0 / (1.0 + c))


def pose_harry(pos, nrm, skirt=False):
    """pos, nrm: raw model space (Z up, face towards -Y, T-pose, 3.7 units tall). Returns posed copies in the same space.

    A seated riding pose from a T-pose: arms forward-down to the handle, torso leaning forward about the hips, thighs forward along
    the broom, shins hanging down. Every step blends rigid rotations with smooth weights (a hand-made linear-blend skin).
    """
    p, n = pos.astype(np.float64).copy(), nrm.astype(np.float64).copy()
    hip = np.array([0.0, 0.0, 1.95])
    knee = np.array([0.0, 0.0, 1.05])

    # 1. Arms (in the torso's own frame): the shoulder is about x = +-0.55, z = 2.65; the T-pose arm points out and a little down.
    for side in (1.0, -1.0):
        pivot = np.array([side * 0.55, 0.0, 2.65])
        along = np.array([side * 0.76, 0.0, -0.65])
        target = np.array([side * 0.20, -0.88, 0.05])  # forward, and with the lean below it ends up forward-down at the handle
        rot = rot_between(along, target)
        w = smooth(side * p[:, 0], 0.40, 0.66)
        w = np.where(side * p[:, 0] > 0, w, 0.0)
        moved = (p - pivot) @ rot.T + pivot
        p = p + (moved - p) * w[:, None]
        n = n + (n @ rot.T - n) * w[:, None]

    # 2. Legs: thighs swing forward about the hips, shins stay hanging (a translation only), blended around the knee.
    thigh = rot_x(-THIGH_LIFT)
    knee_new = hip + thigh @ (knee - hip)
    thigh_p = (p - hip) @ thigh.T + hip
    thigh_n = n @ thigh.T
    shin_p = p + (knee_new - knee)
    wk = smooth(p[:, 2], 0.80, 1.28)                      # 0 below the knee, 1 in the thigh
    leg_p = shin_p + (thigh_p - shin_p) * wk[:, None]
    leg_n = n + (thigh_n - n) * wk[:, None]
    if skirt:  # the robe hangs from the hips instead of swinging up with the thighs
        leg_p, leg_n = p.copy(), n.copy()

    # 3. Torso (and arms, head) lean forward about the hips; the hip zone blends torso and thigh.
    lean = rot_x(TORSO_LEAN)
    torso_p = (p - hip) @ lean.T + hip
    torso_n = n @ lean.T
    wh = smooth(p[:, 2], 1.65, 2.25)                      # 0 in the legs, 1 in the torso
    p = leg_p + (torso_p - leg_p) * wh[:, None]
    n = leg_n + (torso_n - leg_n) * wh[:, None]
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-9)
    return p - hip, n


def world_matrices(gltf):
    world = {}

    def walk(i, parent):
        m = parent @ local_matrix(gltf["nodes"][i])
        world[i] = m
        for c in gltf["nodes"][i].get("children", []):
            walk(c, m)

    for r in gltf["scenes"][gltf.get("scene", 0)]["nodes"]:
        walk(r, np.eye(4))
    return world


class Writer:
    def __init__(self, src_gltf, src_blob):
        self.src_gltf, self.src_blob = src_gltf, src_blob
        self.blob = bytearray()
        self.views, self.accessors, self.prims = [], [], []
        self.all_positions = []

    def add(self, array, ctype, atype, target, bounds=False):
        while len(self.blob) % 4:
            self.blob.append(0)
        self.views.append({"buffer": 0, "byteOffset": len(self.blob), "byteLength": array.nbytes, "target": target})
        self.blob.extend(array.tobytes())
        acc = {"bufferView": len(self.views) - 1, "componentType": ctype, "count": len(array), "type": atype}
        if bounds:
            acc["min"], acc["max"] = array.min(axis=0).tolist(), array.max(axis=0).tolist()
        self.accessors.append(acc)
        return len(self.accessors) - 1

    def primitive(self, pos, nrm, uv, idx, material):
        self.all_positions.append(pos)
        self.prims.append({"attributes": {"POSITION": self.add(pos.astype(np.float32), 5126, "VEC3", 34962, True),
                                          "NORMAL": self.add(nrm.astype(np.float32), 5126, "VEC3", 34962),
                                          "TEXCOORD_0": self.add(uv.astype(np.float32), 5126, "VEC2", 34962)},
                           "indices": self.add(idx.astype(np.uint32), 5125, "SCALAR", 34963), "mode": 4, "material": material})

    def save(self, path, name):
        images = []
        for image in self.src_gltf.get("images", []):
            view = self.src_gltf["bufferViews"][image["bufferView"]]
            chunk = self.src_blob[view.get("byteOffset", 0):view.get("byteOffset", 0) + view["byteLength"]]
            while len(self.blob) % 4:
                self.blob.append(0)
            self.views.append({"buffer": 0, "byteOffset": len(self.blob), "byteLength": len(chunk)})
            self.blob.extend(chunk)
            images.append({"bufferView": len(self.views) - 1, "mimeType": image.get("mimeType", "image/png")})
        gltf = {"asset": self.src_gltf["asset"], "scene": 0, "scenes": [{"nodes": [0]}], "nodes": [{"mesh": 0, "name": name}],
                "meshes": [{"name": name, "primitives": self.prims}], "materials": self.src_gltf.get("materials", []),
                "accessors": self.accessors, "bufferViews": self.views, "buffers": [{"byteLength": len(self.blob)}]}
        for key in ("textures", "samplers", "extensionsUsed"):
            if key in self.src_gltf:
                gltf[key] = self.src_gltf[key]
        if images:
            gltf["images"] = images
        body = json.dumps(gltf, separators=(",", ":")).encode()
        body += b" " * (-len(body) % 4)
        while len(self.blob) % 4:
            self.blob.append(0)
        with open(path, "wb") as f:
            f.write(struct.pack("<4sII", b"glTF", 2, 12 + 8 + len(body) + 8 + len(self.blob)))
            f.write(struct.pack("<I4s", len(body), b"JSON") + body)
            f.write(struct.pack("<I4s", len(self.blob), b"BIN\x00") + bytes(self.blob))
        allp = np.concatenate(self.all_positions)
        print(f"{name}: x {allp[:, 0].min():.2f}..{allp[:, 0].max():.2f}  y {allp[:, 1].min():.2f}..{allp[:, 1].max():.2f}  z {allp[:, 2].min():.2f}..{allp[:, 2].max():.2f}")


def collect(gltf, blob, world):
    """[(material, pos (N,3) in node-local space, nrm, uv, idx, world matrix)] for every mesh node."""
    out = []
    for index, node in enumerate(gltf["nodes"]):
        if node.get("mesh") is None:
            continue
        for prim in gltf["meshes"][node["mesh"]]["primitives"]:
            if prim.get("mode", 4) != 4:
                continue
            a = prim["attributes"]
            pos = read(gltf, blob, a["POSITION"]).astype(np.float64)
            nrm = read(gltf, blob, a["NORMAL"]).astype(np.float64) if "NORMAL" in a else np.tile([0.0, 0.0, 1.0], (len(pos), 1))
            uv = read(gltf, blob, a["TEXCOORD_0"]).astype(np.float32) if "TEXCOORD_0" in a else np.zeros((len(pos), 2), np.float32)
            idx = read(gltf, blob, prim["indices"]).reshape(-1).astype(np.int64) if "indices" in prim else np.arange(len(pos))
            out.append((prim.get("material", 0), pos, nrm, uv, idx, world[index]))
    return out


def build_harry():
    gltf, blob = load(os.path.join(RAW, "harry_src.glb"))
    world = world_matrices(gltf)
    writer = Writer(gltf, blob)
    scale = HEIGHT_M / 3.7
    for material, pos, nrm, uv, idx, matrix in collect(gltf, blob, world):
        # The meshes are in the model's own Z-up space; the node matrix only turns that into glTF Y-up, so pose before it.
        p, n = pose_harry(pos, nrm, skirt=material == SKIRT_MATERIAL)
        # raw (x, y, z) -> glTF (x, z, -y): up stays up, the face (-y) points to glTF +Z.
        p = np.stack([p[:, 0], p[:, 2], -p[:, 1]], axis=1) * scale
        n = np.stack([n[:, 0], n[:, 2], -n[:, 1]], axis=1)
        writer.primitive(p, n, uv, idx, material)
    writer.save(os.path.join(OUT, "harry_rider.glb"), "harry_rider")


def build_nimbus():
    gltf, blob = load(os.path.join(RAW, "nimbus_src.glb"))
    world = world_matrices(gltf)
    writer = Writer(gltf, blob)
    parts = collect(gltf, blob, world)
    verts = [np.concatenate([p, np.ones((len(p), 1))], axis=1) @ w.T for _, p, _, _, _, w in parts]
    allp = np.concatenate([v[:, :3] for v in verts])
    extent = allp.max(axis=0) - allp.min(axis=0)
    long_axis = int(np.argmax(extent))
    centre = (allp.max(axis=0) + allp.min(axis=0)) / 2
    print("nimbus extents", extent.round(2), "long axis", long_axis)
    # Which end carries the bristles? The one with the wider cross-section.
    coord = allp[:, long_axis] - centre[long_axis]
    others = [i for i in range(3) if i != long_axis]

    def spread(sel):
        return float(np.ptp(allp[sel][:, others[0]]) * np.ptp(allp[sel][:, others[1]]))

    positive_wider = spread(coord > extent[long_axis] * 0.3) > spread(coord < -extent[long_axis] * 0.3)
    sign = -1.0 if positive_wider else 1.0   # we want the bristles at -Z
    scale = 1.9 / extent[long_axis]
    rest = sorted(others, key=lambda i: -extent[i])
    order = [rest[0], rest[1], long_axis]
    flip = np.array([1.0, 1.0, sign])
    for material, pos, nrm, uv, idx, matrix in parts:
        pw = (np.concatenate([pos, np.ones((len(pos), 1))], axis=1) @ matrix.T)[:, :3] - centre
        nw = nrm @ np.linalg.inv(matrix[:3, :3])
        nw /= np.maximum(np.linalg.norm(nw, axis=1, keepdims=True), 1e-9)
        writer.primitive(pw[:, order] * flip * scale, nw[:, order] * flip, uv, idx, material)
    writer.save(os.path.join(OUT, "nimbus.glb"), "nimbus")
    print("nimbus: bristles were at the", "+" if positive_wider else "-", "end of axis", long_axis, "(now -Z)")


if __name__ == "__main__":
    build_harry()
    build_nimbus()
