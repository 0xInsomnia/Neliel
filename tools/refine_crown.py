"""Revision 04: lower the ponytail arch while retaining its rig and topology.

Run on revision 03 only; input and output must differ.
"""
import sys
from pathlib import Path
import numpy as np
from refine_mesh import Asset, normals, smooth


def build(source, target):
    if Path(source).resolve() == Path(target).resolve():
        raise ValueError('Preserve the source revision')
    asset = Asset(source)
    if asset.d['asset'].get('generator') != 'Neliel portrait study 03 / tools/refine_portrait.py':
        raise ValueError('Expected revision 03; do not apply cumulatively')
    mesh = next(m for m in asset.d['meshes'] if m['name'] == 'Coda a ciocche')
    attrs = mesh['primitives'][0]['attributes']
    points = asset.array(attrs['POSITION']).copy()
    crown = smooth(1.63, 1.79, points[:, 1])
    # A smooth map flattens the tall loop above the tie without moving the ends.
    # Its vertical derivative remains positive, avoiding folded-over surfaces.
    points[:, 1] -= .065 * crown
    points[:, 0] *= 1 - .22 * crown
    triangles = np.concatenate([asset.array(p['indices']).reshape(-1, 3)
                                for p in mesh['primitives']])
    n = normals(points, triangles)
    unused = np.linalg.norm(n, axis=1) < .1
    n[unused] = asset.array(attrs['NORMAL'])[unused]
    asset.set(attrs['POSITION'], points)
    asset.set(attrs['NORMAL'], n)
    asset.d['asset']['generator'] = 'Neliel crown study 04 / tools/refine_crown.py'
    asset.write(target)


if __name__ == '__main__':
    build(*sys.argv[1:])
