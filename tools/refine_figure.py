"""Revision 12: fuller hips and thighs, almond eyes.

Input must be r11. Same space-map approach as revisions 07 and 11. Targets
come from the user's character sheet (front standing figure): hips clearly
wider than the waist, full thighs, narrower, slightly upturned eyes, and a 12% shorter lower face (the chin
moves up; asked for after the head was narrowed).

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
EYE_X, EYE_Y = .035, 1.597
EYE_FLATTEN = .18          # vertical compression of the eye opening
EYE_TILT = .0035           # outer corner up, inner corner down (metres)
FACE_TOP, CHIN_Y = 1.600, 1.503
FACE_SQUASH = .12          # lower face shortened, the chin moves up


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

    # Eyes: lower opening and a slight upward tilt; lashes and brows follow.
    front = 1 - smooth(-.035, -.015, z)
    for side in (-1, 1):
        g = np.exp(-((x - side * EYE_X) / .034) ** 2 - ((y - EYE_Y) / .024) ** 2) * front
        q[:, 1] -= (y - EYE_Y) * EYE_FLATTEN * g
        q[:, 1] += EYE_TILT * (side * x - EYE_X) / .030 * g

    # Shorter lower face: everything between the eye line and the chin moves
    # up toward the eye line; the neck below takes up the difference.
    lift = FACE_SQUASH * (FACE_TOP - np.clip(y, CHIN_Y, FACE_TOP))
    q[:, 1] += lift * smooth(CHIN_Y - .045, CHIN_Y, y)
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
