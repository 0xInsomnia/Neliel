"""Bake the Neliel skin, sculpt edits and hair into a standard glTF 2.0 asset."""
import copy
import hashlib
import io
import json
import math
import struct
import sys
from pathlib import Path

import numpy as np
from PIL import Image

SOURCE_HASHES = (
    "f2bf78f28a24e2f75f5ca0b6c3b646654c394e4b03592dfaa0d0633ef0972b4d",
    "b1372131bdbf233f46320146d565f342a7e4f6f4b8f2aefb301f1a283ec07e1e",
)
TYPES = {5121: "u1", 5123: "<u2", 5125: "<u4", 5126: "<f4"}
WIDTHS = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}
MORPHS = {"smile": 1, "surprised": 4, "blink": 12, "wink": 14}


class Source:
    def __init__(self, path, digest):
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != digest:
            raise ValueError(f"Unexpected VRM source: {path}")
        size = struct.unpack_from("<I", data, 12)[0]
        self.doc = json.loads(data[20:20 + size])
        self.binary = data[28 + size:]
        if self.doc["extensions"]["VRM"]["meta"]["licenseName"] != "CC0":
            raise ValueError("Expected the CC0 edition")

    def view(self, index):
        view = self.doc["bufferViews"][index]
        offset = view.get("byteOffset", 0)
        return self.binary[offset:offset + view["byteLength"]]

    def array(self, index):
        accessor = self.doc["accessors"][index]
        view = self.doc["bufferViews"][accessor["bufferView"]]
        dtype = np.dtype(TYPES[accessor["componentType"]])
        width = WIDTHS[accessor["type"]]
        return np.ndarray(
            (accessor["count"], width), dtype, self.view(accessor["bufferView"]),
            accessor.get("byteOffset", 0),
            (view.get("byteStride", dtype.itemsize * width), dtype.itemsize),
        )

    def texture(self, material, max_size):
        pbr = self.doc["materials"][material]["pbrMetallicRoughness"]
        texture = self.doc["textures"][pbr["baseColorTexture"]["index"]]
        image = self.doc["images"][texture["source"]]
        result = Image.open(io.BytesIO(self.view(image["bufferView"]))).convert("RGBA")
        result.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
        return result


class GLB:
    def __init__(self, nodes, roots):
        self.binary = bytearray()
        self.doc = {
            "asset": {"version": "2.0", "generator": "Neliel build_avatar.py"},
            "scene": 0, "scenes": [{"nodes": roots}], "nodes": nodes,
            "meshes": [], "skins": [], "accessors": [], "bufferViews": [],
            "materials": [], "images": [], "textures": [],
        }

    def append(self, table, item):
        self.doc[table].append(item)
        return len(self.doc[table]) - 1

    def view(self, data):
        offset = len(self.binary)
        self.binary.extend(data)
        self.binary.extend(bytes(-len(self.binary) % 4))
        return self.append("bufferViews", {
            "buffer": 0, "byteOffset": offset, "byteLength": len(data),
        })

    def array(self, values, kind, component=5126, bounds=False, normalized=False):
        values = np.asarray(values, dtype=TYPES[component]).reshape(-1, WIDTHS[kind])
        accessor = {
            "bufferView": self.view(values.tobytes()), "componentType": component,
            "count": len(values), "type": kind,
        }
        if bounds:
            accessor.update(min=values.min(axis=0).tolist(), max=values.max(axis=0).tolist())
        if normalized:
            accessor["normalized"] = True
        return self.append("accessors", accessor)

    def material(self, name, image=None, mode="OPAQUE", double=False, color=(1, 1, 1)):
        pbr = {"metallicFactor": 0, "roughnessFactor": .88, "baseColorFactor": [*color, 1]}
        if image is not None:
            data = io.BytesIO()
            if mode == "OPAQUE":
                image.convert("RGB").save(data, "JPEG", quality=88, subsampling=0)
                mime = "image/jpeg"
            else:
                image.save(data, "PNG", optimize=True)
                mime = "image/png"
            index = self.append("images", {"mimeType": mime, "bufferView": self.view(data.getvalue())})
            pbr["baseColorTexture"] = {"index": self.append("textures", {"source": index})}
        return self.append("materials", {
            "name": name, "pbrMetallicRoughness": pbr, "alphaMode": mode,
            "doubleSided": double,
        })

    def write(self, output):
        self.doc["buffers"] = [{"byteLength": len(self.binary)}]
        metadata = json.dumps(self.doc, separators=(",", ":")).encode()
        metadata += b" " * (-len(metadata) % 4)
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("wb") as out:
            out.write(struct.pack("<4sII", b"glTF", 2, 28 + len(metadata) + len(self.binary)))
            out.write(struct.pack("<I4s", len(metadata), b"JSON") + metadata)
            out.write(struct.pack("<I4s", len(self.binary), b"BIN\x00") + self.binary)


def recolor(image, palette, protect_skin=False):
    pixels = np.array(image)
    rgb = pixels[..., :3].astype(float) / 255
    # Preserve the source folds and light piping while changing their pigment.
    value = np.maximum.reduce(rgb, axis=2)
    brightness = np.clip((value - .18) / .82, 0, 1)
    result = np.stack([
        np.interp(brightness, [0, .46, .78, 1], channel) for channel in np.array(palette).T
    ], axis=2)
    mask = (rgb[..., 0] < rgb[..., 2] + .02) if protect_skin else np.ones(value.shape, bool)
    pixels[..., :3][mask] = result[mask]
    return Image.fromarray(pixels)


def body_coordinates(source, image):
    """Interpolate rest-space XYZ over the skin UV atlas."""
    mesh = source.doc["meshes"][1]["primitives"]
    attrs = mesh[0]["attributes"]
    pos = source.array(attrs["POSITION"])
    uv = source.array(attrs["TEXCOORD_0"]) * [image.width, image.height] - .5
    result = np.full((image.height, image.width, 3), np.nan, dtype="f")
    for primitive in mesh[:4]:
        for ids in source.array(primitive["indices"]).reshape(-1, 3):
            a, b, c = uv[ids]
            lo = np.maximum(np.ceil(uv[ids].min(axis=0)).astype(int), 0)
            hi = np.minimum(np.floor(uv[ids].max(axis=0)).astype(int), [image.width - 1, image.height - 1])
            if np.any(lo > hi):
                continue
            ab, ac = b - a, c - a
            det = ab[0] * ac[1] - ab[1] * ac[0]
            if abs(det) < 1e-8:
                continue
            yy, xx = np.mgrid[lo[1]:hi[1] + 1, lo[0]:hi[0] + 1]
            dx, dy = xx - a[0], yy - a[1]
            u = (dx * ac[1] - dy * ac[0]) / det
            v = (ab[0] * dy - ab[1] * dx) / det
            inside = (u >= -.001) & (v >= -.001) & (u + v <= 1.001)
            result[yy[inside], xx[inside]] = (
                pos[ids[0]] + u[inside, None] * (pos[ids[1]] - pos[ids[0]])
                + v[inside, None] * (pos[ids[2]] - pos[ids[0]])
            )
    return result


def paint_thigh(image, coords):
    x, y, z = coords.transpose(2, 0, 1)
    rgba = np.array(image)
    # A three-part sigil projected onto the front of the left thigh and baked into its UVs.
    u, v = (-x - .104) / .028, (y - .771) / .040
    u, v = .95 * u + .31 * v, -.31 * u + .95 * v
    distance = np.full(u.shape, np.inf)
    for line in (
        [(-.73, .07), (-.98, .43), (-.55, .82), (0, .52), (.55, .82), (.98, .43), (.73, .07)],
        [(-.61, .12), (0, .47), (.61, .12), (0, -.69), (-.61, .12)],
        [(-.67, -.31), (0, -1.0), (.67, -.31)],
        [(-.22, .08), (0, .21), (.22, .08), (0, -.27), (-.22, .08)],
    ):
        for (ax, ay), (bx, by) in zip(line, line[1:]):
            dx, dy = bx - ax, by - ay
            along = np.clip(((u - ax) * dx + (v - ay) * dy) / (dx * dx + dy * dy), 0, 1)
            distance = np.minimum(distance, np.hypot(u - ax - along * dx, v - ay - along * dy))
    mask = (z < -.045) & (distance < .067) & (x < -.04)
    rgba[mask, :3] = (45, 28, 58)
    return Image.fromarray(rgba)


def merge_materials(primitives):
    groups = {}
    for primitive in primitives:
        groups.setdefault(primitive["material"], []).append(primitive)
    return groups.values()


def skin_influences(joints, weights):
    # Legacy VRM exports can repeat a joint and leave the remaining weights unnormalized.
    joints, weights = joints.copy(), weights.copy()
    for slot in range(1, 4):
        for earlier in range(slot):
            duplicate = joints[:, slot] == joints[:, earlier]
            weights[duplicate, earlier] += weights[duplicate, slot]
            weights[duplicate, slot] = 0
    total = weights.sum(axis=1, keepdims=True)
    if np.any(total <= 0):
        raise ValueError("Vertex has no skin influence")
    joints[weights == 0] = 0
    return joints, weights / total


def export_mesh(glb, source, mesh, name, edit=None, morphs=False):
    primitives = []
    cache = {}
    for group in merge_materials(mesh):
        original = group[0]
        attributes = original["attributes"]
        key = tuple(attributes.items())
        if key not in cache:
            result = {}
            joints, weights = skin_influences(source.array(attributes["JOINTS_0"]),
                                              source.array(attributes["WEIGHTS_0"]))
            influences = {"JOINTS_0": joints, "WEIGHTS_0": weights}
            for attribute, index in attributes.items():
                accessor = source.doc["accessors"][index]
                values = influences[attribute] if attribute in influences else source.array(index)
                if edit and attribute == "POSITION":
                    values = edit(values.copy())
                result[attribute] = glb.array(
                    values, accessor["type"], accessor["componentType"], attribute == "POSITION",
                )
            targets = []
            if morphs:
                for index in MORPHS.values():
                    target = original["targets"][index]
                    targets.append({key: glb.array(source.array(value), "VEC3", bounds=key == "POSITION")
                                    for key, value in target.items()})
            cache[key] = result, targets
        result, targets = cache[key]
        indices = np.concatenate([source.array(p["indices"]) for p in group])
        primitive = {"attributes": result, "indices": glb.array(indices, "SCALAR", 5123),
                     "material": original["material"]}
        if morphs:
            primitive["targets"] = targets
        primitives.append(primitive)
    result = {"name": name, "primitives": primitives}
    if morphs:
        result["extras"] = {"targetNames": list(MORPHS)}
    return glb.append("meshes", result)


def sculpt_face(positions, ears):
    points = positions[ears]
    if not len(points):
        return positions
    strength = np.clip((np.abs(points[:, 0]) - .086) / .021, 0, 1)
    strength *= np.clip((points[:, 1] - 1.494) / .035, 0, 1)
    points[:, 0] += np.sign(points[:, 0]) * .067 * strength
    points[:, 1] += .031 * strength
    points[:, 2] += .008 * strength
    positions[ears] = points
    return positions


def ponytail(glb, nodes, head, head_world):
    """Sculpt layered, tapered locks with a four-joint deformation chain."""
    joint_positions = np.array([[0, 1.655, .10], [0, 1.49, .205],
                                [.015, 1.24, .205], [-.014, .97, .212]])
    joints = []
    parent = head
    parent_world = head_world
    for i, point in enumerate(joint_positions):
        joint = glb.append("nodes", {"name": f"Ponytail_{i}", "translation": (point - parent_world).tolist()})
        nodes[parent].setdefault("children", []).append(joint)
        joints.append(joint)
        parent, parent_world = joint, point
    inverses = np.repeat(np.eye(4)[None, :, :], len(joints), axis=0)
    inverses[:, 3, :3] = -joint_positions
    skin = glb.append("skins", {"name": "Hair rig", "joints": joints, "skeleton": head,
                                "inverseBindMatrices": glb.array(inverses, "MAT4")})

    rng = np.random.default_rng(17)
    points, normals, colors, weights, joint_ids, triangles = [], [], [], [], [], []
    rings, sides, locks = 31, 9, 31
    for strand in range(locks):
        a = strand * 2.39996
        radius = math.sqrt((strand + .5) / locks)
        spread = math.cos(a) * radius
        depth = math.sin(a) * radius
        length = rng.uniform(.58, .91)
        start = np.array([.017 * spread, 1.65 + .021 * depth, .104 + .013 * depth])
        c1 = np.array([.105 * spread, 1.88, .24 + .05 * depth])
        c2 = np.array([.17 * spread + .046, 1.48, .198 + .08 * depth])
        end = np.array([.19 * spread - .023, 1.63 - length, .205 + .091 * depth])
        start_vertex = len(points)
        tint = rng.uniform(.78, 1)
        for ring in range(rings):
            t = ring / (rings - 1)
            q = 1 - t
            center = q**3 * start + 3*q*q*t*c1 + 3*q*t*t*c2 + t**3*end
            center[0] += .043 * t * math.sin(t * 8 + a)
            tangent = 3*q*q*(c1-start) + 6*q*t*(c2-c1) + 3*t*t*(end-c2)
            across = np.cross(tangent, [0, 0, 1])
            across /= np.linalg.norm(across)
            back = np.cross(tangent, across)
            back /= np.linalg.norm(back)
            width = (.008 + .024 * math.sin(math.pi * t)**.65) * (1 - t**3) + .0004
            progress = np.interp(center[1], joint_positions[::-1, 1], [3, 2, 1, 0])
            base = min(int(progress), 2)
            mix = progress - base
            for side in range(sides):
                angle = 2 * math.pi * side / sides
                normal = math.cos(angle) * across + math.sin(angle) * back
                points.append(center + width * (math.cos(angle)*across + .54*math.sin(angle)*back))
                normals.append(normal)
                shade = tint * (.81 + .19 * abs(math.sin(angle)))
                colors.append([*(round(255 * shade * c) for c in (.70, .65, .83)), 255])
                weights.append([1-mix, mix, 0, 0])
                joint_ids.append([base if mix < 1 else 0, base+1 if mix > 0 else 0, 0, 0])
                if ring:
                    prev = start_vertex + (ring-1)*sides
                    here = prev + sides
                    nxt = (side+1) % sides
                    triangles.extend([prev+side, prev+nxt, here+side, prev+nxt, here+nxt, here+side])
    mat = glb.material("Argento · coda", double=True)
    mesh = glb.append("meshes", {"name": "Coda a ciocche", "primitives": [{
        "material": mat, "indices": glb.array(triangles, "SCALAR", 5123), "attributes": {
            "POSITION": glb.array(points, "VEC3", bounds=True), "NORMAL": glb.array(normals, "VEC3"),
            "COLOR_0": glb.array(colors, "VEC4", 5121, normalized=True),
            "WEIGHTS_0": glb.array(weights, "VEC4"), "JOINTS_0": glb.array(joint_ids, "VEC4", 5121),
        },
    }]})
    glb.doc["scenes"][0]["nodes"].append(glb.append("nodes", {"name": "Coda", "mesh": mesh, "skin": skin}))


def hair_clip(glb, head, head_world):
    # An open triangular badge following the curve of the left side of the fringe.
    outer = np.array([[.042, 1.596, -.124], [.082, 1.587, -.102], [.064, 1.629, -.111]])
    center = outer.mean(axis=0)
    inner = center + .54 * (outer - center)
    points = np.concatenate((outer, inner)) - head_world
    normal = np.cross(outer[1] - outer[0], outer[2] - outer[0])
    normal /= np.linalg.norm(normal)
    indices = [0, 3, 1, 1, 3, 4, 1, 4, 2, 2, 4, 5, 2, 5, 0, 0, 5, 3]
    material = glb.material("Fermaglio · viola", color=(.29, .075, .56), double=True)
    glb.doc["materials"][material]["emissiveFactor"] = [.10, .022, .23]
    mesh = glb.append("meshes", {"name": "Fermaglio", "primitives": [{
        "attributes": {"POSITION": glb.array(points, "VEC3", bounds=True),
                       "NORMAL": glb.array(np.tile(-normal, (6, 1)), "VEC3")},
        "material": material, "indices": glb.array(indices, "SCALAR", 5123),
    }]})
    glb.doc["nodes"][head]["children"].append(glb.append("nodes", {"name": "Fermaglio", "mesh": mesh}))


def build(vita, victoria, output):
    original = vita.doc
    # Promote the legacy fringe node to a scene root for standard glTF skinning.
    nodes = copy.deepcopy(original["nodes"][:157] + original["nodes"][158:159])
    glb = GLB(nodes, [0, 1, 2, 157])
    for skin in original["skins"]:
        skin = copy.deepcopy(skin)
        skin["inverseBindMatrices"] = glb.array(vita.array(skin["inverseBindMatrices"]), "MAT4")
        glb.append("skins", skin)

    night = [(12, 9, 20), (35, 23, 51), (100, 52, 156), (175, 120, 228)]
    trim = [(12, 9, 20), (33, 21, 51), (72, 37, 124), (128, 74, 191)]
    silver = [(62, 49, 79), (151, 129, 182), (214, 204, 236), (249, 244, 255)]
    names = ["Bocca", "Sclera", "Contorno occhi", "Ciglia", "Sopracciglia", "Iride viola",
             "Riflesso occhi", "Viso", "Occhi extra", "Pelle e tessuto", "Pannelli",
             "Stivali", "Dettagli", "Capelli", "Ciocche", "Antenne"]
    for i, material in enumerate(original["materials"]):
        base = victoria if i in (5, 7) else vita
        image = base.texture(i, 1024 if i == 9 else 512 if i in (7, 10, 11, 12) else 256)
        if i == 5:
            image = recolor(image, [(25, 10, 41), (108, 46, 175), (176, 105, 247), (244, 200, 255)])
        if i in (9, 10, 11, 12):
            image = recolor(image, trim if i == 10 else night, protect_skin=i == 9)
        if i == 9:
            image = paint_thigh(image, body_coordinates(vita, image))
        if i in (13, 14):
            image = recolor(image, silver)
        glb.material(names[i], image if i not in (8, 15) else None,
                     material["alphaMode"], material["doubleSided"])

    face, body, hair = (mesh["primitives"] for mesh in original["meshes"])
    ears = np.unique(vita.array(face[8]["indices"]))
    nodes[0]["mesh"] = export_mesh(glb, vita, face[:9], "Viso", lambda p: sculpt_face(p, ears), True)
    nodes[1]["mesh"] = export_mesh(glb, vita, body, "Corpo")
    nodes[157]["mesh"] = export_mesh(glb, vita, [p for p in hair if p["material"] != 15], "Frangia")
    head = next(b["node"] for b in original["extensions"]["VRM"]["humanoid"]["humanBones"] if b["bone"] == "head")
    head_world = np.sum([nodes[i]["translation"] for i in (2, 3, 12, 13, 14, 19, head)], axis=0)
    ponytail(glb, nodes, head, head_world)
    hair_clip(glb, head, head_world)
    glb.write(output)


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit("usage: build_avatar.py Vita.vrm Victoria_Rubin.vrm output.glb")
    build(Source(Path(sys.argv[1]), SOURCE_HASHES[0]),
          Source(Path(sys.argv[2]), SOURCE_HASHES[1]), Path(sys.argv[3]))
