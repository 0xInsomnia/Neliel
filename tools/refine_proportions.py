"""Revision 11: shoulder, arm and jaw proportions.

Input must be r10. Uses the same kind of space map as revision 07, so meshes,
morph endpoints and the rig move together. The target values were measured on
a commercial cel-shaded character the user supplied as a study reference;
only the proportions are matched, no data from that file is used.

- Shoulders: undo the 22 mm outward shift of revision 07 (arm joint 136 -> 115 mm
  from the midline).
- Arms: 8% longer between shoulder and wrist; the hands keep their size.
- Jaw: lower face up to 15% narrower around the cheek line, nothing at the
  chin tip or at eye level.

Usage: python3 tools/refine_proportions.py r10.glb r11.glb
"""
import sys
from pathlib import Path
import numpy as np
from refine_mesh import Asset, smooth
from refine_body import apply_map, gauss

SOURCE_GENERATOR = 'Neliel hair 10 / tools/refine_hair.py'
GENERATOR = 'Neliel proportions 11 / tools/refine_proportions.py'

SHOULDER_SHIFT = -.021
SHOULDER_X = .115          # arm joint after the shift
WRIST_X = .542
ARM_STRETCH = .08
JAW_NARROW = .15
JAW_Y, JAW_SIGMA = 1.577, .042


def warp(points, head_bound):
    p = np.asarray(points, dtype=np.float64)
    q = p.copy()
    x, y, z = p.T
    ax, sign = np.abs(x), np.sign(x)
    head = np.where(head_bound, 1.0, smooth(1.463, 1.513, y))

    # Shoulder girdle and arms move back toward the spine.
    upper = smooth(1.198, 1.318, y) * (1 - head)
    shift = SHOULDER_SHIFT * smooth(.035, .105, ax) * upper
    # Longer arms: stretch from the shoulder to the wrist, carry the hand.
    arm = smooth(.135, .190, ax) * smooth(1.30, 1.36, y) * (1 - head)
    stretch = ARM_STRETCH * (np.minimum(ax, WRIST_X + .021) - (SHOULDER_X + .021)) * arm
    q[:, 0] += sign * (shift + np.maximum(stretch, 0))

    # Narrower jaw; hair and ears beside the cheeks follow, the back does not.
    front = 1 - smooth(-.01, .05, z)
    q[:, 0] -= x * JAW_NARROW * gauss(y, JAW_Y, JAW_SIGMA) * front
    return q


def build(source, target):
    if Path(source).resolve() == Path(target).resolve():
        raise ValueError('Preserve the source revision')
    asset = Asset(source)
    if asset.d['asset'].get('generator') != SOURCE_GENERATOR:
        raise ValueError('Expected revision 10; do not apply cumulatively')
    apply_map(asset, warp)
    asset.d['asset']['generator'] = GENERATOR
    asset.write(target)


if __name__ == '__main__':
    build(*sys.argv[1:])
