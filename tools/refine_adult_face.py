"""Revision 05: reference-led adult facial proportions, applied once to revision 04.
Preserves all facial layers, morph endpoints, UVs and rig weights.
"""
import sys
from pathlib import Path
import numpy as np
from refine_mesh import Asset, normals, smooth


def build(source, target):
    if Path(source).resolve() == Path(target).resolve():
        raise ValueError('Preserve the source revision')
    asset = Asset(source)
    if asset.d['asset'].get('generator') != 'Neliel crown study 04 / tools/refine_crown.py':
        raise ValueError('Expected revision 04; do not apply cumulatively')
    # Sculpt every facial layer and its morph endpoints with the same mapping.
    # This preserves alignment of eyelids, irises and mouth in expressions.
    def face_shape(points):
        q = points.copy()
        x, y, z = points.T
        front = smooth(.0, .045, -z)
        lower = (1 - smooth(1.465, 1.525, y)) * smooth(1.395, 1.43, y)
        q[:, 1] -= .006 * lower * front
        cheek = np.exp(-((y - 1.485) / .034)**2) * smooth(.035, .070, abs(x))
        q[:, 0] *= 1 - .025 * cheek * front
        eye = np.exp(-((abs(x)-.045)/.038)**4-((y-1.527)/.033)**4) * front
        q[:, 1] += eye * (-.13*(y-1.527) + .001*(abs(x)-.042)/.035)
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

    asset.d['asset']['generator'] = 'Neliel face study 05 / tools/refine_adult_face.py'
    asset.write(target)


if __name__ == '__main__':
    build(*sys.argv[1:])
