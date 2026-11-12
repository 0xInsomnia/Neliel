"""Revision 12: fuller hips and thighs, shorter lower face.

Input must be r11. Same space-map approach as revisions 07 and 11. Targets
come from the user's character sheet (front standing figure): hips clearly
wider than the waist, full thighs, and a 12% shorter lower face (the chin
moves up; asked for after the head was narrowed). The eyes are no longer
touched here: revision 14 rebuilds them.

Usage: python3 tools/refine_figure.py r11.glb r12.glb
"""
import sys
from pathlib import Path
import numpy as np
from refine_mesh import Asset, smooth
from refine_body import apply_map, gauss

SOURCE_GENERATOR = 'Neliel proportions 11 / tools/refine_proportions.py'
GENERATOR = 'Neliel figure 12 / tools/refine_figure.py'

HIP_WIDTH = .11
REAR = .12
THIGH = .15
CALF = .04
FACE_TOP, CHIN_Y = 1.600, 1.503
FACE_SQUASH = .12          # lower face shortened, the chin moves up
CHIN_WIDEN, CHIN_FLATTEN = .20, .004   # softer chin tip
EAR_LEVEL, EAR_WIDEN = 1.600, .035     # a touch wider at ear height


def warp(points, head_bound):
    p = np.asarray(points, dtype=np.float64)
    q = p.copy()
    x, y, z = p.T
    ax, sign = np.abs(x), np.sign(x)
    body = np.where(head_bound, 0.0, 1.0)

    # Pelvis: wider and a little fuller behind; the waist above is untouched.
    hip = gauss(y, 1.00, .095) * (1 - smooth(1.10, 1.17, y)) * body
    q[:, 0] += x * HIP_WIDTH * hip
    q[:, 2] += np.maximum(z, 0) * REAR * gauss(y, .98, .09) * body

    # Thighs and calves grow around each leg axis, less toward the midline.
    for side in (-1, 1):
        t = np.clip((y - .613) / (1.021 - .613), 0, 1)
        cx = side * (.057 + .026 * t)
        dx, dz = x - cx, z - .004
        r = np.hypot(dx, dz)
        amount = (THIGH * gauss(y, .86, .17) + CALF * gauss(y, .42, .12)) * smooth(.14, .22, y)
        amount = amount * (1 - smooth(.075, .150, r)) * (sign == side) * body
        inner = np.where(side * dx < 0, .55 * smooth(0, .03, side * x), 1.0)
        q[:, 0] += dx * amount * inner
        q[:, 2] += dz * amount

    # Shorter lower face: everything between the eye line and the chin moves
    # up toward the eye line; the neck below takes up the difference.
    lift = FACE_SQUASH * (FACE_TOP - np.clip(y, CHIN_Y, FACE_TOP))
    q[:, 1] += lift * smooth(CHIN_Y - .045, CHIN_Y, y)

    # Slightly wider at ear height; face, ears and hair move together.
    q[:, 0] += x * EAR_WIDEN * gauss(y, EAR_LEVEL, .035) * smooth(1.47, 1.52, y)

    # Softer chin: the tip is a little wider and flatter, the jaw is untouched.
    chin_front = 1 - smooth(-.045, -.025, z)
    q[:, 0] += x * CHIN_WIDEN * gauss(y, CHIN_Y + .010, .013) * (1 - smooth(.035, .065, ax)) * chin_front
    q[:, 1] += CHIN_FLATTEN * gauss(ax, 0, .018) * gauss(y, CHIN_Y, .010) * chin_front
    return q


def build(source, target):
    if Path(source).resolve() == Path(target).resolve():
        raise ValueError('Preserve the source revision')
    asset = Asset(source)
    if asset.d['asset'].get('generator') != SOURCE_GENERATOR:
        raise ValueError('Expected revision 11; do not apply cumulatively')
    apply_map(asset, warp)
    asset.d['asset']['generator'] = GENERATOR
    asset.write(target)


if __name__ == '__main__':
    build(*sys.argv[1:])
