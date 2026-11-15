"""Revision v2-02: the base body fitted to the technical sheet and the skeleton.

Input: the T-posed base (tools/v2/tpose_base.py). The skeleton kept from
revision 15 fixes where the joints are; the sheet fixes the shapes.

1. Heights: piecewise smooth map of the base's landmarks (sole, ankle, knee,
   crotch, waist, bust, arm axis, neck, chin, crown) onto the skeleton's.
   The base has a much longer neck and legs and a larger head.
2. Head: scaled as one piece about the chin to the sheet's head height
   (7.5 heads for the figure), so the face keeps its proportions.
3. Arms: stretched along their length so shoulder, elbow, wrist and finger
   tips sit on the skeleton's joints.
4. Trunk and legs: the sheet tables of revision 15 (front outline, leg depth,
   rear and front profiles), reused from tools/refine_physique.py.

Usage: python3 tools/v2/fit_body.py tpose.glb out.glb
"""
import sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from refine_mesh import Asset, smooth                       # noqa: E402
import refine_physique as sheet                              # noqa: E402

sheet.SKIN = 'Pelle'

# (base height, skeleton height) in metres.
HEIGHTS = [(-1, -1.026), (.026, 0), (.110, .139), (.620, .550), (1.060, .931), (1.360, 1.230),
           (1.460, 1.354), (1.500, 1.455), (1.675, 1.547), (1.960, 1.775)]
CHIN, NECK_TOP = HEIGHTS[-2], 1.62          # base: chin, and where the head scaling starts to fade in
HEAD_SCALE = (HEIGHTS[-1][1] - HEIGHTS[-2][1]) / (HEIGHTS[-1][0] - HEIGHTS[-2][0])
# (base |x|, skeleton |x|) along the arm: attachment, elbow, wrist, finger tip.
ARM = [(0, 0), (.120, .120), (.175, .155), (.385, .366), (.580, .597), (.790, .765), (2, 1.975)]
ARM_BAND = (1.40, 1.60)                      # base heights the arms occupy in T-pose


def monotone(knots):
    xs, ys = np.array([k[0] for k in knots], float), np.array([k[1] for k in knots], float)
    h = np.diff(xs)
    delta = np.diff(ys) / h
    slope = np.empty(len(xs))
    slope[0], slope[-1] = delta[0], delta[-1]
    for i in range(1, len(xs) - 1):
        slope[i] = 0 if delta[i - 1] * delta[i] <= 0 else \
            3 * (h[i - 1] + h[i]) / ((2 * h[i] + h[i - 1]) / delta[i - 1] + (h[i] + 2 * h[i - 1]) / delta[i])

    def curve(v):
        v = np.asarray(v, float)
        i = np.clip(np.searchsorted(xs, v) - 1, 0, len(xs) - 2)
        t = (v - xs[i]) / h[i]
        return ((2 * t ** 3 - 3 * t ** 2 + 1) * ys[i] + (t ** 3 - 2 * t ** 2 + t) * h[i] * slope[i]
                + (-2 * t ** 3 + 3 * t ** 2) * ys[i + 1] + (t ** 3 - t ** 2) * h[i] * slope[i + 1])
    return curve


def proportions(points, head_bound):
    p = np.asarray(points, dtype=np.float64)
    q = p.copy()
    x, y, z = p.T
    ax, side = np.abs(x), np.where(x < 0, -1.0, 1.0)
    height, along = monotone(HEIGHTS), monotone(ARM)

    # Arms: only points out beyond the trunk, inside the arms' height band.
    arm = smooth(.10, .24, ax) * smooth(ARM_BAND[0] - .07, ARM_BAND[0] + .02, y) * (1 - smooth(ARM_BAND[1] - .02, ARM_BAND[1] + .06, y))
    q[:, 0] = side * (ax + (along(ax) - ax) * arm)

    # Head: one piece above the neck, scaled about the chin.
    head = smooth(NECK_TOP, CHIN[0], y)
    scaled_y = CHIN[1] + (y - CHIN[0]) * HEAD_SCALE
    # Arms keep their thickness: they move up or down as one piece with the
    # arm axis, while the chest beside them is stretched by the height map.
    axis_shift = HEIGHTS[7][1] - HEIGHTS[7][0]
    body_y = height(y) * (1 - arm) + (y + axis_shift) * arm
    q[:, 1] = body_y * (1 - head) + scaled_y * head
    scale = 1 + (HEAD_SCALE - 1) * head
    centre_z = .0
    q[:, 0] *= scale
    q[:, 2] = centre_z + (z - centre_z) * scale
    return q


def apply_map(asset, warp):
    """Move every mesh vertex through the map (this asset has no rig yet)."""
    done = set()
    for mesh in asset.d['meshes']:
        for primitive in mesh['primitives']:
            accessor = primitive['attributes']['POSITION']
            if accessor in done:
                continue
            done.add(accessor)
            points = asset.array(accessor).astype(np.float64)
            moved = warp(points, np.zeros(len(points), dtype=bool))
            asset.set(accessor, moved.astype(np.float32))


def build(source, target):
    asset = Asset(source)
    apply_map(asset, proportions)
    for fit in (sheet.fit_outline, sheet.fit_outline, sheet.fit_leg_depth, sheet.fit_leg_depth,
                sheet.fit_rear, sheet.fit_front, sheet.fit_rear):
        apply_map(asset, fit(sheet.Shape(asset)))
    sheet.renew_normals(asset)
    sheet.report(sheet.Shape(asset))
    asset.d['asset']['generator'] = 'Neliel v2-02 body / tools/v2/fit_body.py'
    asset.write(target)


if __name__ == '__main__':
    build(*sys.argv[1:])
