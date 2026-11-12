"""Revision 15: body proportions from the reference turnaround.

Input must be r14. Measured on the front and side figures of the private
sheet, scaled to the model's height (crown to floor); only the numbers are
kept here. Heights, shoulders and bust already matched within the reading
error and are left alone. What changes, through one space map (meshes,
garments, morphs and joints together):

- Torso: a long narrow waist. Half-width 74 mm under the bust, 73 mm at the
  waist, 82 mm at the navel, 108 mm at the top of the hips; the flare to the
  full hip width (178 mm) happens lower, over the last 12 cm.
- Legs: much fuller. One thigh is 161 mm wide a third of the way down and
  119 mm three quarters down, the knee 95 mm, the calf 91 mm, the ankle
  56 mm. Growth is mostly outward so the thighs keep a narrow gap; seen from
  the side only the middle of the thigh deepens.

Usage: python3 tools/refine_physique.py r14.glb r15.glb
"""
import sys
from pathlib import Path
import numpy as np
from refine_mesh import Asset, smooth
from refine_body import apply_map
from face_mesh import frontal_depth

SOURCE_GENERATOR = 'Neliel face 14 / tools/refine_face.py'
GENERATOR = 'Neliel physique 15 / tools/refine_physique.py'
SKIN = 'Pelle e tessuto'

# Sideways scale of the trunk by height (metres above the floor).
TORSO = [(.96, 1.0), (1.00, .90), (1.037, .84), (1.075, .76), (1.126, .81), (1.154, .83),
         (1.185, .86), (1.249, .80), (1.29, .93), (1.33, 1.0)]
TORSO_DEPTH = .5           # share of that scale also applied front to back, below the ribs
# Per leg: height, sideways scale, front-to-back scale.
LEGS = [(.00, 1.0, 1.0), (.06, 1.0, 1.0), (.12, 1.15, 1.0), (.18, 1.26, 1.05), (.297, 1.22, 1.0),
        (.434, 1.05, 1.0), (.52, 1.12, 1.0), (.613, 1.34, 1.0), (.689, 1.47, 1.18), (.75, 1.42, 1.12),
        (.816, 1.30, 1.03), (.87, 1.17, 1.0), (.916, 1.08, 1.0), (.97, 1.0, 1.0)]
PIVOT = .35                # 0 keeps the inner edge of the leg, 1 its centre line
RESOLUTION = 1000


def curve(knots, column=1):
    """Smooth lookup through the knots (linear, then a short running mean)."""
    ys = np.linspace(0, 1.5, 751)
    values = np.interp(ys, [k[0] for k in knots], [k[column] for k in knots])
    values = np.convolve(np.pad(values, 6, mode='edge'), np.ones(13) / 13, mode='valid')
    return lambda y: np.interp(y, ys, values)


class Silhouette:
    """Left leg and trunk outline of the skin, by height, from a frontal raster."""

    def __init__(self, asset):
        doc = asset.d
        part = next(p for mesh in doc['meshes'] for p in mesh['primitives']
                    if doc['materials'][p['material']]['name'] == SKIN)
        points = asset.array(part['attributes']['POSITION']).astype(np.float64)
        triangles = asset.array(part['indices']).reshape(-1, 3).astype(int)
        bounds = (-.30, .30, 0, 1.5)
        front = frontal_depth(points, triangles, bounds, RESOLUTION)
        mirrored = points * [1, 1, -1]
        back = -frontal_depth(mirrored, triangles, bounds, RESOLUTION)
        covered = np.isfinite(front)
        x = (np.arange(covered.shape[1]) + .5) / RESOLUTION + bounds[0]
        self.y = (np.arange(covered.shape[0]) + .5) / RESOLUTION
        left = covered & (x < 0)[None]
        any_left = left.any(1)
        outer = np.where(left, x[None], np.inf).min(1)
        inner = np.where(left, x[None], -np.inf).max(1)
        trunk = covered & (np.abs(x) < .215)[None]
        self.half = np.where(trunk, np.abs(x)[None], 0).max(1)
        with np.errstate(invalid='ignore'):    # rows the skin does not reach
            middle = np.clip(((outer + inner) / 2 - bounds[0]) * RESOLUTION, 0, covered.shape[1] - 1)
        rows = np.arange(covered.shape[0])
        column = np.where(any_left, middle, 0).astype(int)
        with np.errstate(invalid='ignore'):
            depth = (front[rows, column] + back[rows, column]) / 2
        valid = any_left & np.isfinite(depth)
        first = np.argmax(valid)

        def tidy(values):
            values = np.where(valid, values, np.nan)
            values[:first] = values[first]
            index = np.where(np.isnan(values), 0, np.arange(len(values)))
            np.maximum.accumulate(index, out=index)
            values = values[index]
            return np.convolve(np.pad(values, 6, mode='edge'), np.ones(13) / 13, mode='valid')
        self.outer, self.inner, self.depth = tidy(outer), tidy(np.minimum(inner, 0)), tidy(depth)
        self.width = self.inner - self.outer

    def at(self, y):
        return (np.interp(y, self.y, self.outer), np.interp(y, self.y, self.inner), np.interp(y, self.y, self.depth))


def make_warp(shape):
    torso = curve(TORSO)
    leg_x, leg_z = curve(LEGS, 1), curve(LEGS, 2)

    def warp(points, head_bound):
        p = np.asarray(points, dtype=np.float64)
        q = p.copy()
        x, y, z = p.T
        ax = np.abs(x)
        side = np.where(x < 0, -1.0, 1.0)
        body = np.where(head_bound, 0.0, 1.0)

        # Legs, in the left leg's frame (xm <= 0).
        outer, inner, centre_z = shape.at(y)
        xm = -ax
        pivot = np.minimum(inner + ((outer + inner) / 2 - inner) * PIVOT, -1e-4)
        grow = leg_x(y) - 1
        beyond = np.maximum(outer - xm, 0)                    # garments outside the leg
        fade = (1 - smooth(.05, .14, beyond)) * (1 - smooth(.90, .97, y)) * body
        outside = (np.maximum(xm, outer) - pivot) * grow      # outward: the full scale
        inside = (xm - pivot) * (xm / pivot) * grow           # toward the midline: eases to nothing at x = 0
        shift = np.where(xm < pivot, outside, inside) * fade
        q[:, 0] -= side * shift
        q[:, 2] += (z - centre_z) * (leg_z(y) - 1) * fade

        # Trunk: narrower about the spine; the bust keeps its width.
        amount = torso(y) - 1
        bust = smooth(1.22, 1.27, y) * (1 - smooth(-.11, -.08, z))
        trunk = (1 - smooth(.19, .23, ax)) * (1 - bust) * body
        q[:, 0] += x * amount * trunk
        q[:, 2] += (z + .015) * amount * TORSO_DEPTH * (1 - smooth(1.20, 1.26, y)) * trunk
        return q
    return warp


def report(shape, label):
    def leg(y):
        return np.interp(y, shape.y, shape.width)

    def trunk(y):
        return np.interp(y, shape.y, shape.half)
    print(f'{label}: trunk half-width (mm) under bust {trunk(1.249) * 1e3:.0f}, waist {trunk(1.185) * 1e3:.0f}, '
          f'navel {trunk(1.14) * 1e3:.0f}, hip top {trunk(1.075) * 1e3:.0f}, hips {trunk(.964) * 1e3:.0f}; '
          f'leg width upper thigh {leg(.816) * 1e3:.0f}, lower thigh {leg(.689) * 1e3:.0f}, knee {leg(.613) * 1e3:.0f}, '
          f'calf {leg(.434) * 1e3:.0f}, ankle {leg(.18) * 1e3:.0f}')


def build(source, target):
    if Path(source).resolve() == Path(target).resolve():
        raise ValueError('Preserve the source revision')
    asset = Asset(source)
    if asset.d['asset'].get('generator') != SOURCE_GENERATOR:
        raise ValueError('Expected revision 14; do not apply cumulatively')
    shape = Silhouette(asset)
    report(shape, 'Before')
    print('Target: trunk 74, 73, 82, 108, 178; leg 161, 119, 95, 91, 56')
    apply_map(asset, make_warp(shape))
    report(Silhouette(asset), 'After ')
    for node in asset.d['nodes']:              # rounding dust must not read as a transform
        if 'translation' in node:
            node['translation'] = [0.0 if abs(v) < 1e-12 else v for v in node['translation']]
    asset.d['asset']['generator'] = GENERATOR
    asset.write(target)


if __name__ == '__main__':
    build(*sys.argv[1:])
