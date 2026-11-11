"""Revision 08: one level of Loop subdivision on the body skin.

Input must be r07. Only the skin primitive is subdivided; garments keep their
geometry. Positions are smoothed on a topology welded across UV seams, so both
sides of a seam move together. UVs are interpolated per UV vertex, skin weights
are blended and reduced to four influences, and normals are recomputed on the
welded surface. Open borders (neck, wrists) stay in place so they still meet
the neighbouring meshes.

Usage: python3 tools/refine_subdivide.py r07.glb r08.glb
"""
import sys
from pathlib import Path
import numpy as np
from refine_mesh import Asset

SOURCE_GENERATOR = 'Neliel adult body 07 / tools/refine_body.py'
GENERATOR = 'Neliel smooth body 08 / tools/refine_subdivide.py'
SKIN_MATERIAL = 'Pelle e tessuto'
FLOAT, USHORT = 5126, 5123


def append(asset, values, kind, component, bounds=False, target=None):
    """Store a new array at the end of the binary chunk and return its accessor."""
    doc = asset.d
    data = np.ascontiguousarray(values, dtype='<f4' if component == FLOAT else '<u2')
    asset.b += b'\0' * (-len(asset.b) % 4)
    view = {'buffer': 0, 'byteOffset': len(asset.b), 'byteLength': data.nbytes}
    if target:
        view['target'] = target
    asset.b += data.tobytes()
    doc['bufferViews'].append(view)
    accessor = {'bufferView': len(doc['bufferViews']) - 1, 'componentType': component,
                'count': len(data), 'type': kind}
    if bounds:
        accessor['min'] = data.min(0).tolist()
        accessor['max'] = data.max(0).tolist()
    doc['accessors'].append(accessor)
    doc['buffers'][0]['byteLength'] = len(asset.b)
    return len(doc['accessors']) - 1


def blend_weights(joints, weights, a, b):
    """Average the influences of two vertices, keeping the four strongest."""
    out_j = np.zeros((len(a), 4), dtype=np.uint16)
    out_w = np.zeros((len(a), 4), dtype=np.float32)
    for row, (i, j) in enumerate(zip(a, b)):
        total = {}
        for vertex in (i, j):
            for joint, weight in zip(joints[vertex], weights[vertex]):
                if weight > 0:
                    total[int(joint)] = total.get(int(joint), 0.0) + .5 * float(weight)
        strongest = sorted(total.items(), key=lambda item: -item[1])[:4]
        scale = sum(weight for _, weight in strongest)
        for slot, (joint, weight) in enumerate(strongest):
            out_j[row, slot] = joint
            out_w[row, slot] = weight / scale
    return out_j, out_w


def subdivide(points, uv, joints, weights, triangles):
    used, compact = np.unique(triangles, return_inverse=True)
    triangles = compact.reshape(-1, 3)
    points, uv, joints, weights = points[used].astype(np.float64), uv[used], joints[used], weights[used]
    count = len(points)

    # Weld vertices that share a position (UV seams) for the geometric rules.
    _, weld = np.unique(np.round(points, 6), axis=0, return_inverse=True)
    weld = weld.reshape(-1)
    welded = np.zeros((weld.max() + 1, 3))
    welded[weld] = points
    wtri = weld[triangles]

    corners = np.array([[0, 1, 2], [1, 2, 0], [2, 0, 1]])       # edge a-b, opposite c
    wa, wb, wc = (wtri[:, corners[:, k]].reshape(-1) for k in range(3))
    key = np.stack([np.minimum(wa, wb), np.maximum(wa, wb)], 1)
    edges, edge_of, faces = np.unique(key, axis=0, return_inverse=True, return_counts=True)
    edge_of = edge_of.reshape(-1)
    opposite = np.zeros((len(edges), 3))
    np.add.at(opposite, edge_of, welded[wc])
    manifold = faces == 2
    middle = welded[edges].mean(1)
    odd = np.where(manifold[:, None], .75 * middle + .125 * opposite, middle)

    # Even vertices: Loop's rule inside the surface, fixed on borders and
    # wherever the welded surface is not a simple two-sided sheet.
    valence = np.zeros(len(welded))
    around = np.zeros((len(welded), 3))
    border = np.zeros(len(welded), dtype=bool)
    for end, other in ((0, 1), (1, 0)):
        np.add.at(valence, edges[:, end], 1)
        np.add.at(around, edges[:, end], welded[edges[:, other]])
        border[edges[~manifold, end]] = True
    n = np.maximum(valence, 3)
    beta = (.625 - (.375 + .25 * np.cos(2 * np.pi / n)) ** 2) / n
    even = (1 - (n * beta)[:, None]) * welded + beta[:, None] * around
    even[border] = welded[border]

    # One new vertex per UV edge; seams produce two that share a position.
    va, vb = (triangles[:, corners[:, k]].reshape(-1) for k in range(2))
    attribute_key = np.stack([np.minimum(va, vb), np.maximum(va, vb)], 1)
    attribute_edges, attribute_of = np.unique(attribute_key, axis=0, return_inverse=True)
    attribute_of = attribute_of.reshape(-1)
    welded_edge = np.zeros(len(attribute_edges), dtype=int)
    welded_edge[attribute_of] = edge_of
    a, b = attribute_edges.T

    new_points = np.concatenate([even[weld], odd[welded_edge]])
    new_uv = np.concatenate([uv, (uv[a] + uv[b]) / 2])
    odd_joints, odd_weights = blend_weights(joints, weights, a, b)
    new_joints = np.concatenate([joints, odd_joints])
    new_weights = np.concatenate([weights, odd_weights])

    mid = count + attribute_of.reshape(-1, 3)                 # per triangle: ab, bc, ca
    t0, t1, t2 = triangles.T
    ab, bc, ca = mid.T
    new_triangles = np.concatenate([
        np.stack([t0, ab, ca], 1), np.stack([t1, bc, ab], 1),
        np.stack([t2, ca, bc], 1), np.stack([ab, bc, ca], 1)])

    # Smooth normals on the welded surface, shared by both sides of each seam.
    new_weld = np.concatenate([weld, len(welded) + welded_edge])
    corner_points = new_points[new_triangles]
    face = np.cross(corner_points[:, 1] - corner_points[:, 0], corner_points[:, 2] - corner_points[:, 0])
    summed = np.zeros((new_weld.max() + 1, 3))
    for k in range(3):
        np.add.at(summed, new_weld[new_triangles[:, k]], face)
    normal = summed[new_weld]
    length = np.linalg.norm(normal, axis=1)
    normal[length > 1e-12] /= length[length > 1e-12, None]
    normal[length <= 1e-12] = [0, 1, 0]
    return new_points, normal, new_uv, new_joints, new_weights, new_triangles


def build(source, target):
    if Path(source).resolve() == Path(target).resolve():
        raise ValueError('Preserve the source revision')
    asset = Asset(source)
    doc = asset.d
    if doc['asset'].get('generator') != SOURCE_GENERATOR:
        raise ValueError('Expected revision 07; do not apply cumulatively')
    skin = [p for mesh in doc['meshes'] for p in mesh['primitives']
            if doc['materials'][p['material']]['name'] == SKIN_MATERIAL]
    if len(skin) != 1 or skin[0].get('targets'):
        raise ValueError('Expected one skin primitive without morph targets')
    primitive = skin[0]
    attrs = primitive['attributes']
    if set(attrs) != {'POSITION', 'NORMAL', 'TEXCOORD_0', 'JOINTS_0', 'WEIGHTS_0'}:
        raise ValueError('Unexpected skin attributes')
    points, normal, uv, joints, weights, triangles = subdivide(
        asset.array(attrs['POSITION']).copy(), asset.array(attrs['TEXCOORD_0']).copy(),
        asset.array(attrs['JOINTS_0']).copy(), asset.array(attrs['WEIGHTS_0']).copy(),
        asset.array(primitive['indices']).reshape(-1, 3).astype(int))
    if len(points) > 65535:
        raise ValueError('Subdivided skin exceeds 16-bit indices')
    primitive['attributes'] = {
        'POSITION': append(asset, points, 'VEC3', FLOAT, bounds=True, target=34962),
        'NORMAL': append(asset, normal, 'VEC3', FLOAT, target=34962),
        'TEXCOORD_0': append(asset, uv, 'VEC2', FLOAT, target=34962),
        'JOINTS_0': append(asset, joints, 'VEC4', USHORT, target=34962),
        'WEIGHTS_0': append(asset, weights, 'VEC4', FLOAT, target=34962),
    }
    primitive['indices'] = append(asset, triangles.reshape(-1, 1), 'SCALAR', USHORT, target=34963)
    doc['asset']['generator'] = GENERATOR
    asset.write(target)
    print(f'Skin: {len(triangles) // 4} -> {len(triangles)} triangles, {len(points)} vertices')


if __name__ == '__main__':
    build(*sys.argv[1:])
