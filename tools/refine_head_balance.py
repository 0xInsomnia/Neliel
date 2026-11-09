"""Revision 06: reduce head/crown dominance with one map across all mesh layers.

Input must be r05. Keeps topology, UVs, weights and skeleton; transforms each
morph endpoint as well as the base so eyelids and iris layers stay aligned.
"""
import sys
from pathlib import Path
import numpy as np
from refine_mesh import Asset, normals, smooth


def shape(points):
    result = points.copy()
    y = points[:, 1]
    head = smooth(1.37, 1.46, y)
    result[:, 0] *= 1 - .085 * head
    result[:, 2] *= 1 - .055 * head
    # Preserve lower-face length; remove height from the oversized upper crown.
    result[:, 1] -= .020 * smooth(1.53, 1.68, y)
    return result


def build(source, target):
    if Path(source).resolve() == Path(target).resolve():
        raise ValueError('Preserve the source revision')
    asset = Asset(source)
    if asset.d['asset'].get('generator') != 'Neliel face study 05 / tools/refine_adult_face.py':
        raise ValueError('Expected revision 05; do not apply cumulatively')
    for mesh in asset.d['meshes']:
        groups = {}
        for primitive in mesh['primitives']:
            groups.setdefault(primitive['attributes']['POSITION'], []).append(primitive)
        for pos_id, primitives in groups.items():
            attrs = primitives[0]['attributes']
            base = asset.array(pos_id).copy()
            shaped = shape(base)
            if np.array_equal(base, shaped):
                continue
            triangles = np.concatenate([asset.array(p['indices']).reshape(-1, 3) for p in primitives])
            normal = normals(shaped, triangles)
            unused = np.linalg.norm(normal, axis=1) < .1
            normal[unused] = asset.array(attrs['NORMAL'])[unused]
            for morph in primitives[0].get('targets', []):
                posed = shape(base + asset.array(morph['POSITION']).copy())
                asset.set(morph['POSITION'], posed - shaped)
                if 'NORMAL' in morph:
                    pn = normals(posed, triangles)
                    pn[unused] = normal[unused]
                    asset.set(morph['NORMAL'], pn - normal)
            asset.set(pos_id, shaped)
            asset.set(attrs['NORMAL'], normal)
    asset.d['asset']['generator'] = 'Neliel head balance 06 / tools/refine_head_balance.py'
    asset.write(target)


if __name__ == '__main__':
    build(*sys.argv[1:])
