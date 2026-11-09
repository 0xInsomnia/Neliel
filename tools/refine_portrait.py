"""Revision 03: facial proportions and head-bound tapered temple locks.

Input must be revision 02 generated with refine_mesh.py; never apply cumulatively.
Usage: python tools/refine_portrait.py revision02.glb assets/neliel-refined.glb
"""
import sys
from pathlib import Path
import numpy as np
from refine_mesh import Asset, normals, smooth
from build_avatar import GLB


def build(source, target):
    if Path(source).resolve() == Path(target).resolve():
        raise ValueError('Preserve the source revision')
    asset = Asset(source)
    if asset.d['asset'].get('generator') != 'Neliel mesh study 02 / tools/refine_mesh.py':
        raise ValueError('Expected revision 02; regenerate it with refine_mesh.py first')
    # Sculpt every facial layer and its morph endpoints with the same mapping.
    # This preserves alignment of eyelids, irises and mouth in expressions.
    def face_shape(points):
        q = points.copy()
        x, y, z = points.T
        front = smooth(.0, .045, -z)
        lower = (1 - smooth(1.465, 1.525, y)) * smooth(1.395, 1.43, y)
        q[:, 1] -= .008 * lower * front
        cheek = np.exp(-((y - 1.485) / .034)**2) * smooth(.035, .070, abs(x))
        q[:, 0] *= 1 - .045 * cheek * front
        eye = np.exp(-((abs(x)-.045)/.038)**4-((y-1.527)/.033)**4) * front
        q[:, 1] += eye * (-.07*(y-1.527) + .002*(abs(x)-.042)/.035)
        return q

    for mesh in asset.d['meshes']:
        if mesh['name'] != 'Viso':
            continue
        prim = mesh['primitives'][0]
        attrs = prim['attributes']
        base = asset.array(attrs['POSITION']).copy()
        shaped = face_shape(base)
        triangles = np.concatenate([asset.array(p['indices']).reshape(-1, 3) for p in mesh['primitives']])
        n = normals(shaped, triangles)
        unused = np.linalg.norm(n, axis=1) < .1
        n[unused] = asset.array(attrs['NORMAL'])[unused]
        for morph in prim.get('targets', []):
            posed = face_shape(base + asset.array(morph['POSITION']).copy())
            asset.set(morph['POSITION'], posed-shaped)
            if 'NORMAL' in morph:
                pn = normals(posed, triangles)
                pn[unused] = n[unused]
                asset.set(morph['NORMAL'], pn-n)
        asset.set(attrs['POSITION'], shaped)
        asset.set(attrs['NORMAL'], n)

    for mesh in asset.d['meshes']:
        kind = mesh['name']
        if kind not in ('Frangia', 'Coda a ciocche'):
            continue
        prim = mesh['primitives'][0]
        p = asset.array(prim['attributes']['POSITION']).copy()
        if kind == 'Frangia':
            # Taper the round side-cap without touching the eye or face geometry.
            side = smooth(.065, .12, np.abs(p[:, 0]))
            lower = 1 - smooth(1.55, 1.67, p[:, 1])
            p[:, 0] *= 1 - .18 * side * lower
        else:
            # Lift the swept crown, leaving the long weighted ends intact.
            crown = smooth(1.52, 1.69, p[:, 1])
            p[:, 1] += .025 * crown
            p[:, 2] += .025 * crown
        triangles = np.concatenate([asset.array(v['indices']).reshape(-1, 3)
                                    for v in mesh['primitives']])
        n = normals(p, triangles)
        old = asset.array(prim['attributes']['NORMAL']).copy()
        zero = np.linalg.norm(n, axis=1) < .1
        n[zero] = old[zero]
        asset.set(prim['attributes']['POSITION'], p)
        asset.set(prim['attributes']['NORMAL'], n)

    glb = GLB([], [])
    glb.doc, glb.binary = asset.d, asset.b
    # Closed, flattened tapered locks, bound to the existing head joint.
    # They are authored mesh surfaces rather than scene primitives.
    points, colors, indices = [], [], []
    for side in (-1, 1):
        for layer in range(2):
            controls = np.array([
                [side * (.075 + layer * .012), 1.645 - layer * .012, -.066],
                [side * (.108 + layer * .008), 1.55, -.104 + layer * .018],
                [side * (.083 + layer * .018), 1.40, -.111 + layer * .024],
                [side * (.120 + layer * .012), 1.32 + layer * .055, -.073 + layer * .023],
            ])
            start = len(points)
            rings, sides = 25, 8
            for ring in range(rings):
                t = ring / (rings - 1)
                q = 1 - t
                a, b, c, d = controls
                center = q**3*a + 3*q*q*t*b + 3*q*t*t*c + t**3*d
                tangent = 3*q*q*(b-a) + 6*q*t*(c-b) + 3*t*t*(d-c)
                across = np.cross(tangent, [0, 0, 1])
                across /= np.linalg.norm(across)
                depth = np.cross(tangent, across)
                depth /= np.linalg.norm(depth)
                width = (.006 + .006*np.sin(np.pi*t)) * (1-t)**.65 + .00015
                for s in range(sides):
                    angle = s*2*np.pi/sides
                    points.append(center + width*(np.cos(angle)*across + .24*np.sin(angle)*depth))
                    shade = .88 + .12*abs(np.sin(angle))
                    colors.append([.73*shade, .66*shade, .84*shade, 1])
                    if ring:
                        prev = start+(ring-1)*sides
                        here = prev+sides
                        nxt = (s+1)%sides
                        indices.extend([prev+s, prev+nxt, here+s, prev+nxt, here+nxt, here+s])
            # Cap both ends so inspection from profile/rear has no open tubes.
            for s in range(1, sides-1):
                indices.extend([start, start+s+1, start+s])
                end = start+(rings-1)*sides
                indices.extend([end, end+s, end+s+1])
    points = np.asarray(points, dtype='f')
    tri = np.asarray(indices).reshape(-1, 3)
    head = next(i for i, n in enumerate(glb.doc['nodes']) if n.get('name') == 'J_Bip_C_Head')
    skin_index = next(n['skin'] for n in glb.doc['nodes'] if n.get('mesh') is not None and glb.doc['meshes'][n['mesh']]['name'] == 'Frangia')
    joint = glb.doc['skins'][skin_index]['joints'].index(head)
    weights = np.tile([1, 0, 0, 0], (len(points), 1))
    joints = np.tile([joint, 0, 0, 0], (len(points), 1))
    material = glb.material('Argento · ciocche laterali', double=True)
    mesh = glb.append('meshes', {'name': 'Ciocche laterali', 'primitives': [{
        'material': material, 'indices': glb.array(indices, 'SCALAR', 5123),
        'attributes': {
            'POSITION': glb.array(points, 'VEC3', bounds=True),
            'NORMAL': glb.array(normals(points, tri), 'VEC3'),
            'COLOR_0': glb.array(colors, 'VEC4'),
            'JOINTS_0': glb.array(joints, 'VEC4', 5121),
            'WEIGHTS_0': glb.array(weights, 'VEC4'),
        },
    }]})
    node = glb.append('nodes', {'name': 'CioccheLaterali', 'mesh': mesh, 'skin': skin_index})
    glb.doc['scenes'][0]['nodes'].append(node)
    glb.doc['asset']['generator'] = 'Neliel portrait study 03 / tools/refine_portrait.py'
    glb.write(Path(target))


if __name__ == '__main__':
    build(*sys.argv[1:])
