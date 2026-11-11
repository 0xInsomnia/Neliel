"""Revision 11: rebuild the ponytail from wide sculpted locks.

Input must be r10. The former tail (31 thin tubes) is replaced by a small
number of broad, flattened locks that overlap into one mass near the tie and
separate into pointed tips, the usual construction for cel-shaded hair. The
geometry is generated here from curves; nothing is taken from another model.
Shading is painted into the vertex colours (light ridge, darker edges and
underside). The mesh keeps its node, material and the four ponytail bones.

Usage: python3 tools/refine_ponytail.py r10.glb r11.glb
"""
import sys
from pathlib import Path
import numpy as np
from refine_mesh import Asset, smooth
from refine_body import world_positions
from refine_subdivide import append, FLOAT, USHORT
from refine_hair import compact

SOURCE_GENERATOR = 'Neliel hair 10 / tools/refine_hair.py'
GENERATOR = 'Neliel ponytail 11 / tools/refine_ponytail.py'
MESH = 'Coda a ciocche'
BONES = [f'Ponytail_{i}' for i in range(4)]

TIE = np.array([0, 1.712, .078])       # where the tail leaves the crown
RINGS, AROUND = 24, 10
COLOUR = np.array([146, 136, 173]) / 255

# Each lock: fan position (-1 left .. 1 right), layer (0 against the back ..
# 1 outermost), tip height, width, sideways curl of the tip.
LOCKS = [
    # outer layer, seen from behind
    (-.95, .55, .98, .100, -.075), (-.62, .85, .79, .115, -.050), (-.30, 1.0, .88, .120, .045),
    (.02, 1.0, .64, .125, -.030), (.33, 1.0, .80, .120, .050), (.64, .85, .70, .115, .055),
    (.96, .55, 1.02, .100, .080),
    # inner layer, fills the gaps and shows between the outer tips
    (-.80, .25, .84, .110, .050), (-.46, .40, .66, .120, -.060), (-.14, .45, .74, .125, .055),
    (.18, .45, .60, .125, -.050), (.50, .40, .86, .120, .060), (.82, .25, .76, .110, -.050),
    # short locks over the arch, so the top reads as a full bunch
    (-.50, 1.25, 1.22, .095, -.030), (.05, 1.35, 1.14, .100, .020), (.55, 1.25, 1.25, .095, .030),
]


def centreline(a, layer, tip_y, curl, s):
    """Cubic Bezier from the tie, over the arch, down to the tip."""
    depth = .135 + .125 * layer * (1 - .45 * a * a)
    p0 = TIE + [a * .018, 0, .010 * layer]
    p1 = TIE + [a * .070, .085 + .040 * layer, .100 + .055 * layer]
    p2 = np.array([a * .215, 1.34 + .10 * (tip_y - .66), depth + .050])
    p3 = np.array([a * .320 + curl, tip_y, depth - .020])
    s = s[:, None]
    line = (1 - s) ** 3 * p0 + 3 * (1 - s) ** 2 * s * p1 + 3 * (1 - s) * s ** 2 * p2 + s ** 3 * p3
    # A gentle S-curve in the lower half keeps the tips from looking combed.
    wave = smooth(.45, 1, s[:, 0])
    line[:, 0] += curl * .9 * np.sin(np.pi * 1.6 * s[:, 0] + a * 2) * wave * (1 - s[:, 0] * .4)
    return line


def lock(a, layer, tip_y, width, curl):
    """One closed lock: lens-shaped rings along the centreline, pointed tip."""
    s = np.linspace(0, 1, RINGS) ** .9
    line = centreline(a, layer, tip_y, curl, s)
    tangent = np.gradient(line, axis=0)
    tangent /= np.linalg.norm(tangent, axis=1)[:, None]
    outward = np.array([a * .9, .2, .35 + .6 * (layer - .4)])
    normal = outward - tangent * (tangent @ outward)[:, None]
    normal /= np.linalg.norm(normal, axis=1)[:, None]
    side = np.cross(tangent, normal)

    grow = .42 + .58 * smooth(0, .24, s)
    taper = np.where(s < .50, 1, np.cos(np.pi / 2 * np.clip((s - .50) / .50, 0, 1)) ** .9)
    w = width * grow * taper
    thick = w * (.40 - .12 * smooth(.3, 1, s))

    theta = 2 * np.pi * np.arange(AROUND) / AROUND
    cos, sin = np.cos(theta), np.sin(theta)
    across = np.sign(cos) * np.abs(cos) ** .8 / 2             # sharper edges
    out = np.where(sin > 0, .68 * sin, .32 * sin)             # ridge on the outside
    points = (line[:, None] + side[:, None] * (w[:, None] * across)[..., None]
              + normal[:, None] * (thick[:, None] * out)[..., None])
    points = np.concatenate([points[:-1].reshape(-1, 3), line[-1:], line[:1]])
    tip, root = len(points) - 2, len(points) - 1

    triangles = []
    for ring in range(RINGS - 2):
        for k in range(AROUND):
            i, j = ring * AROUND + k, ring * AROUND + (k + 1) % AROUND
            triangles += [[i, i + AROUND, j], [j, i + AROUND, j + AROUND]]
    last = (RINGS - 2) * AROUND
    for k in range(AROUND):
        triangles.append([last + k, tip, last + (k + 1) % AROUND])
        triangles.append([root, k, (k + 1) % AROUND])
    triangles = np.array(triangles)

    # Painted shading: light along the ridge, darker toward both edges, on the
    # underside, near the tie and slightly toward the tips.
    ridge = np.clip(sin, 0, 1) ** 1.5
    edge = np.abs(cos) ** 3
    shade_ring = 1.0 + .20 * ridge - .30 * edge - .32 * np.clip(-sin, 0, 1)
    along = 1 - .14 * (1 - smooth(0, .16, s)) - .07 * smooth(.6, 1, s) + .05 * np.exp(-((s - .30) / .07) ** 2)
    shade = (along[:-1, None] * shade_ring[None]).reshape(-1)
    shade = np.concatenate([shade, [along[-1] * .9, .8]]) * (.80 + .20 * min(layer, 1))
    return points, triangles, shade, np.concatenate([np.repeat(s[:-1], AROUND), [1, 0]])


def smooth_normals(points, triangles):
    corner = points[triangles]
    face = np.cross(corner[:, 1] - corner[:, 0], corner[:, 2] - corner[:, 0])
    normal = np.zeros_like(points)
    for k in range(3):
        np.add.at(normal, triangles[:, k], face)
    length = np.linalg.norm(normal, axis=1)
    normal[length > 1e-12] /= length[length > 1e-12, None]
    normal[length <= 1e-12] = [0, 0, 1]
    return normal


def bone_weights(points, along, bone_y):
    """Blend down the chain by height; the arch above the tie follows bone 0."""
    joints = np.zeros((len(points), 4), dtype=np.uint16)
    weights = np.zeros((len(points), 4), dtype=np.float32)
    y = np.where(along < .12, bone_y[0], np.minimum(points[:, 1], bone_y[0]))
    for i, value in enumerate(y):
        k = int(np.clip(np.searchsorted(-bone_y, -value, side='right') - 1, 0, 3))
        if k == 3:
            joints[i, 0], weights[i, 0] = 3, 1
            continue
        t = float(smooth(.15, 1.0, (bone_y[k] - value) / (bone_y[k] - bone_y[k + 1])))
        joints[i, :2] = [k, k + 1] if t < 1 else [k + 1, 0]
        weights[i, :2] = [1 - t, t] if t < 1 else [1, 0]
        if weights[i, 1] == 0:
            joints[i, 1] = 0
    return joints, weights


def build(source, target):
    if Path(source).resolve() == Path(target).resolve():
        raise ValueError('Preserve the source revision')
    asset = Asset(source)
    doc = asset.d
    if doc['asset'].get('generator') != SOURCE_GENERATOR:
        raise ValueError('Expected revision 10; do not apply cumulatively')
    mesh_index = next(i for i, mesh in enumerate(doc['meshes']) if mesh['name'] == MESH)
    node = next(n for n in doc['nodes'] if n.get('mesh') == mesh_index)
    skin = doc['skins'][node['skin']]
    if [doc['nodes'][j].get('name') for j in skin['joints']] != BONES:
        raise ValueError('Unexpected ponytail rig')
    _, world = world_positions(doc['nodes'])
    bone_y = np.array([world[j][1] for j in skin['joints']])
    primitive, = doc['meshes'][mesh_index]['primitives']

    parts, faces, shades, alongs, offset = [], [], [], [], 0
    for spec in LOCKS:
        points, triangles, shade, along = lock(*spec)
        parts.append(points)
        faces.append(triangles + offset)
        shades.append(shade)
        alongs.append(along)
        offset += len(points)
    points, triangles = np.concatenate(parts), np.concatenate(faces)
    normal = smooth_normals(points, triangles)
    # Wind every lock outward.
    centre_out = points - np.repeat([p.mean(0) for p in parts], [len(p) for p in parts], axis=0)
    if (np.einsum('ij,ij->i', normal, centre_out) < 0).mean() > .5:
        triangles = triangles[:, ::-1]
        normal = -normal
    colour = np.clip(COLOUR[None] * np.concatenate(shades)[:, None], 0, 1)
    colour = np.concatenate([colour, np.ones((len(colour), 1))], 1)
    joints, weights = bone_weights(points, np.concatenate(alongs), bone_y)

    primitive['attributes'] = {
        'POSITION': append(asset, points, 'VEC3', FLOAT, bounds=True, target=34962),
        'NORMAL': append(asset, normal, 'VEC3', FLOAT, target=34962),
        'COLOR_0': append(asset, colour, 'VEC4', FLOAT, target=34962),
        'JOINTS_0': append(asset, joints, 'VEC4', USHORT, target=34962),
        'WEIGHTS_0': append(asset, weights, 'VEC4', FLOAT, target=34962),
    }
    primitive['indices'] = append(asset, triangles.reshape(-1, 1), 'SCALAR', USHORT, target=34963)
    compact(asset)
    doc['asset']['generator'] = GENERATOR
    asset.write(target)
    print(f'Ponytail: {len(LOCKS)} locks, {len(triangles)} triangles, {len(points)} vertices')


if __name__ == '__main__':
    build(*sys.argv[1:])
