"""Revision v2-02, step 1: base body from A-pose to T-pose, shape keys baked.

The base stands with its arms about 37 degrees down; Neliel's skeleton is
bound in a T-pose. Each arm is swung up about its shoulder pivot by a smooth
rotation field: full rotation inside a cone around the arm's axis, none on
the trunk, the breast or the neck, blended over the shoulder. The shape
keys are first mixed into the body and dropped, because the proportions are
fitted to the reference sheet afterwards anyway.

The output faces -Z with +Y up, like the rest of the project.
Usage: python3 tools/v2/tpose_base.py assets/v2/base-onizaki.glb out.glb
"""
import sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from refine_mesh import Asset, smooth                      # noqa: E402

MIX = {'Breast Size': 1.0, 'Hip Width': .8, 'Thigh Width': 1.0, 'Calf Width': .6, 'Upper Arm Size': .3}
PIVOT = np.array([.150, 1.500])          # arm pivot (|x|, height), base metres
CONE = (np.radians(26), np.radians(42))  # full rotation inside, none beyond
BLEND = (-.015, .060)                    # along the arm, from the pivot


def rotation_field(points):
    """Angle (radians, mirrored half) by which each point is swung up about the pivot."""
    x, y = points[:, 0], points[:, 1]
    ax = np.abs(x)
    tip = points[np.argmax(ax)]
    axis = np.array([abs(tip[0]) - PIVOT[0], tip[1] - PIVOT[1]])
    lift = np.arctan2(-axis[1], axis[0])                      # how far below horizontal
    axis /= np.linalg.norm(axis)
    rel = np.stack([ax - PIVOT[0], y - PIVOT[1]], 1)
    along = rel @ axis
    across = np.abs(rel @ np.array([-axis[1], axis[0]]))
    off_axis = np.arctan2(across, np.maximum(along, 1e-6))
    # Legs are never part of an arm; the hands hang as low as the hips but far out.
    not_leg = 1 - (1 - smooth(1.05, 1.20, y)) * (1 - smooth(.22, .30, ax))
    weight = smooth(*BLEND, along) * (1 - smooth(*CONE, off_axis)) * not_leg
    return lift * weight, lift


def build(source, target):
    asset = Asset(source)
    doc = asset.d
    mesh = doc['meshes'][0]
    primitive = mesh['primitives'][0]
    names = mesh['extras']['targetNames']
    points = asset.array(primitive['attributes']['POSITION']).astype(np.float64)
    for name, target_ in zip(names, primitive['targets']):
        points += MIX.get(name, 0) * asset.array(target_['POSITION'])
    points *= [-1, 1, -1]                                     # face -Z

    turn, lift = rotation_field(points)
    side = np.where(points[:, 0] < 0, -1.0, 1.0)
    x, y = np.abs(points[:, 0]) - PIVOT[0], points[:, 1] - PIVOT[1]
    c, s = np.cos(turn), np.sin(turn)
    # Rotate (|x|, y) about the pivot, counter-clockwise lifts the arm.
    nx, ny = x * c - y * s, x * s + y * c
    points[:, 0] = side * (PIVOT[0] + nx)
    points[:, 1] = PIVOT[1] + ny

    triangles = asset.array(primitive['indices']).reshape(-1, 3).astype(int)
    _, weld = np.unique(np.round(points, 6), axis=0, return_inverse=True)
    weld = weld.reshape(-1)
    corner = points[triangles]
    face = np.cross(corner[:, 1] - corner[:, 0], corner[:, 2] - corner[:, 0])
    summed = np.zeros((weld.max() + 1, 3))
    for k in range(3):
        np.add.at(summed, weld[triangles[:, k]], face)
    normal = summed[weld]
    normal /= np.maximum(np.linalg.norm(normal, axis=1), 1e-12)[:, None]

    asset.set(primitive['attributes']['POSITION'], points.astype(np.float32))
    asset.set(primitive['attributes']['NORMAL'], normal.astype(np.float32))
    primitive.pop('targets', None)
    mesh.pop('extras', None)
    mesh.pop('weights', None)
    doc['asset']['generator'] = 'Neliel v2 T-pose / tools/v2/tpose_base.py'
    asset.write(target)
    print(f'arms raised by {np.degrees(lift):.1f} degrees; span {2 * np.abs(points[:, 0]).max():.3f} m')


if __name__ == '__main__':
    build(*sys.argv[1:])
