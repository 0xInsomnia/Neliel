"""Revision 07: adult body proportions through one smooth space map.

Input must be r06. The same map moves every mesh layer, every morph endpoint
and every joint (node translations and inverse bind matrices), so skinning,
UVs, weights and topology are preserved. Normals are transformed with the
map's Jacobian instead of being recomputed, which keeps UV-seam shading intact.

Usage: python3 tools/refine_body.py r06.glb r07.glb
"""
import sys
from pathlib import Path
import numpy as np
from refine_mesh import Asset, smooth

SOURCE_GENERATOR = 'Neliel head balance 06 / tools/refine_head_balance.py'
GENERATOR = 'Neliel adult body 07 / tools/refine_body.py'

HEAD_MESHES = {'Frangia', 'Coda a ciocche', 'Fermaglio', 'Ciocche laterali'}
HEAD_PIVOT = np.array([0, 1.405, .010])
HEAD_SCALE = .93
SHOULDER_SHIFT = .022
LEG_STRETCH = .10          # relative lengthening between ankle and hip
LEG_RANGE = (.15, .93)


def gauss(v, centre, sigma):
    return np.exp(-((v - centre) / sigma) ** 2)


def warp(points, head_bound):
    """Map bind-pose points (T-pose, +Y up, face toward -Z).

    head_bound marks points that follow the head rigidly (hair, clip, hair
    joints) even where they hang below the neck.
    """
    p = np.asarray(points, dtype=np.float64)
    q = p.copy()
    x, y, z = p.T
    ax = np.abs(x)
    sign = np.sign(x)

    # Arms and shoulder girdle move outward; the neck and spine stay in place.
    # The head and everything bound to it must not follow the shoulders.
    w = np.where(head_bound, 1.0, smooth(1.385, 1.435, y))
    upper = smooth(1.12, 1.24, y) * (1 - w)
    q[:, 0] += sign * SHOULDER_SHIFT * smooth(.035, .105, ax) * upper
    torso = (1 - smooth(.15, .21, ax)) * (1 - w)    # excludes the T-pose arms
    # The studio no longer stretches the whole figure sideways at run time;
    # the trunk keeps that width here while the face becomes narrower.
    q[:, 0] += x * .06 * torso * smooth(.90, 1.00, y) * (1 - smooth(1.33, 1.40, y))

    # Arms keep their thickness without the former run-time sideways stretch.
    arm = smooth(.12, .17, ax) * smooth(1.10, 1.18, y) * (1 - w)
    q[:, 1] += (y - 1.342) * .03 * arm
    q[:, 2] += (z - .002) * .03 * arm

    # Ribcage slightly wider under the shoulders, narrower waist.
    q[:, 0] += x * torso * (.045 * gauss(y, 1.27, .055) - .075 * gauss(y, 1.11, .060))
    q[:, 2] += (z + .03) * torso * (-.050 * gauss(y, 1.11, .060))

    # Bust: inflate around each centre, mostly forward.
    for side in (-1, 1):
        centre = np.array([side * .062, 1.262, -.085])
        d = p - centre
        g = np.exp(-(d[:, 0] / .060) ** 2 - (d[:, 1] / .058) ** 2 - (d[:, 2] / .070) ** 2)
        g = g * (1 - w)
        q += d * (.12 * g)[:, None]
        q[:, 2] -= .016 * g

    # Pelvis: wider hips and fuller rear, including the skirt that covers them.
    hip = gauss(y, .93, .11) * (1 - smooth(1.02, 1.10, y))
    q[:, 0] += x * .13 * hip * (1 - w)
    q[:, 2] += np.maximum(z, 0) * .14 * hip * (1 - w)

    # Thighs and calves: radial growth around each leg axis, fading out with
    # distance so the skirt is pushed outward rather than crossed.
    for side in (-1, 1):
        t = np.clip((y - .571) / (.943 - .571), 0, 1)
        cx = side * (.055 + .022 * t)
        dx, dz = x - cx, z - .004
        r = np.hypot(dx, dz)
        amount = (.26 * gauss(y, .80, .17) + .10 * gauss(y, .40, .13)) * smooth(.14, .22, y)
        amount = amount * (1 - smooth(.060, .135, r)) * (sign == side) * (1 - w)
        # Less growth toward the midline keeps the inner thighs apart.
        inner = np.where(side * dx < 0, .55 * smooth(0, .03, side * x), 1.0)
        q[:, 0] += dx * amount * inner
        q[:, 2] += dz * amount

    # Smaller head, scaled about the base of the neck.
    q += (HEAD_PIVOT - q) * ((1 - HEAD_SCALE) * w)[:, None]

    # Longer legs; everything above the hips rises by the same amount.
    lo, hi = LEG_RANGE
    # Hair hanging below the hips still rises rigidly with the head.
    q[:, 1] += LEG_STRETCH * (np.where(head_bound, hi, np.clip(y, lo, hi)) - lo)
    return q


def jacobian(points, head_bound, h=1e-4):
    j = np.empty((len(points), 3, 3))
    for axis in range(3):
        step = np.zeros(3)
        step[axis] = h
        j[:, :, axis] = (warp(points + step, head_bound) - warp(points - step, head_bound)) / (2 * h)
    return j


def map_normals(normal, points, head_bound):
    """n' = normalize(J^-T n); zero-length input normals stay untouched."""
    inverse_t = np.linalg.inv(jacobian(points, head_bound)).transpose(0, 2, 1)
    out = np.einsum('nij,nj->ni', inverse_t, normal.astype(np.float64))
    length = np.linalg.norm(out, axis=1)
    ok = length > 1e-9
    out[ok] /= length[ok, None]
    out[~ok] = normal[~ok]
    return out


def world_positions(nodes):
    parent = {child: i for i, node in enumerate(nodes) for child in node.get('children', [])}
    cache = {}

    def world(i):
        if i not in cache:
            local = np.array(nodes[i].get('translation', [0, 0, 0]), dtype=np.float64)
            cache[i] = local + (world(parent[i]) if i in parent else 0)
        return cache[i]
    return parent, np.array([world(i) for i in range(len(nodes))])


def build(source, target):
    if Path(source).resolve() == Path(target).resolve():
        raise ValueError('Preserve the source revision')
    asset = Asset(source)
    doc = asset.d
    if doc['asset'].get('generator') != SOURCE_GENERATOR:
        raise ValueError('Expected revision 06; do not apply cumulatively')
    nodes = doc['nodes']
    for node in nodes:
        if np.abs(np.array(node.get('rotation', [0, 0, 0, 1])) - [0, 0, 0, 1]).max() > 1e-6 \
                or np.abs(np.array(node.get('scale', [1, 1, 1])) - 1).max() > 1e-6:
            raise ValueError('Rig must be translation-only in bind pose')

    parent, old_world = world_positions(nodes)
    head = next(i for i, node in enumerate(nodes) if node.get('name') == 'J_Bip_C_Head')

    def under_head(i):
        while i in parent:
            i = parent[i]
            if i == head:
                return True
        return False
    node_head = np.array([under_head(i) for i in range(len(nodes))])
    new_world = warp(old_world, node_head)
    mesh_nodes = {node['mesh']: i for i, node in enumerate(nodes) if 'mesh' in node}

    done = set()
    for mesh_index, mesh in enumerate(doc['meshes']):
        node_index = mesh_nodes[mesh_index]
        skinned = 'skin' in nodes[node_index]
        # Unskinned meshes are stored relative to their parent bone.
        origin = np.zeros(3) if skinned else old_world[node_index]
        new_origin = np.zeros(3) if skinned else new_world[node_index]
        bound = mesh['name'] in HEAD_MESHES
        for primitive in mesh['primitives']:
            attrs = primitive['attributes']
            if attrs['POSITION'] in done:
                continue
            done.add(attrs['POSITION'])
            base = asset.array(attrs['POSITION']).astype(np.float64) + origin
            flags = np.full(len(base), bound)
            shaped = warp(base, flags)
            base_normal = asset.array(attrs['NORMAL']).copy()
            normal = map_normals(base_normal, base, flags)
            for morph in primitive.get('targets', []):
                posed = base + asset.array(morph['POSITION'])
                asset.set(morph['POSITION'], (warp(posed, flags) - shaped).astype(np.float32))
                if 'NORMAL' in morph:
                    posed_normal = base_normal + asset.array(morph['NORMAL'])
                    asset.set(morph['NORMAL'], (map_normals(posed_normal, posed, flags) - normal).astype(np.float32))
            asset.set(attrs['POSITION'], (shaped - new_origin).astype(np.float32))
            asset.set(attrs['NORMAL'], normal.astype(np.float32))

    for i, node in enumerate(nodes):
        local = new_world[i] - (new_world[parent[i]] if i in parent else 0)
        if 'translation' in node or np.abs(local).max() > 1e-9:
            node['translation'] = [float(v) for v in local]
    for skin in doc['skins']:
        matrices = asset.array(skin['inverseBindMatrices']).reshape(-1, 4, 4).copy()
        if np.abs(matrices[:, :3, :3] - np.eye(3)).max() > 1e-6:
            raise ValueError('Inverse bind matrices must be pure translations')
        # glTF stores column-major matrices: the translation is the fourth row here.
        matrices[:, 3, :3] = -new_world[skin['joints']]
        asset.set(skin['inverseBindMatrices'], matrices.reshape(-1, 16).astype(np.float32))

    doc['asset']['generator'] = GENERATOR
    asset.write(target)


if __name__ == '__main__':
    build(*sys.argv[1:])
