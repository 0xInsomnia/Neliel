"""Revision 15: body proportions from the reference turnaround.

Input must be r14. Measured on the front and side figures of the private
sheet and checked by drawing the model's outline over the front figure
(chin and crotch aligned); only the numbers are kept here. Heights of chin,
shoulders, bust and waist, the shoulder joints and the bust width already
matched and are left alone. One space map moves meshes, garments, morphs
and joints together:

- Trunk: waist 80 mm half-width (the sheet reads 76; the user found that too
  narrow), a slim belly below it, and the hip flare moved down: the pelvis is
  much narrower between waist and crotch, the widest point (about 168 mm)
  sits at the top of the thighs.
- Legs: fuller thighs, knees and ankles, growing outward; the inner thighs
  close the gap under the crotch; the knee is 4 cm lower (longer thigh).
- Bust, seen from the side: lifted and rounder instead of pear-shaped.

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
TORSO = [(.88, 1.0), (.916, .95), (.93, .94), (.964, .88), (1.00, .79), (1.037, .73), (1.06, .72),
         (1.088, .75), (1.11, .78), (1.14, .84), (1.185, .92), (1.249, .83), (1.29, .95), (1.33, 1.0)]
BELLY_DEPTH = .4           # share of that scale applied to the front of the belly
# Per leg: height, sideways scale, front-to-back scale.
LEGS = [(.00, 1.0, 1.0), (.06, 1.0, 1.0), (.12, 1.15, 1.0), (.18, 1.26, 1.05), (.297, 1.22, 1.0),
        (.434, 1.05, 1.0), (.52, 1.12, 1.0), (.613, 1.34, 1.0), (.689, 1.47, 1.18), (.75, 1.40, 1.12),
        (.816, 1.24, 1.03), (.87, 1.08, 1.0), (.916, 1.0, 1.0), (.97, 1.0, 1.0)]
PIVOT = .35                # 0 keeps the inner edge of the leg, 1 its centre line
# Where the inner edge of the leg ends up, as a share of its old distance
# from the midline: the thighs nearly meet under the crotch.
INNER = [(.0, 1.0), (.5, 1.0), (.613, .85), (.70, .5), (.80, .2), (.97, .2)]
KNEE_Y, KNEE_DROP, LEG_FIXED = .613, .040, (.20, .90)
BUST = (.082, 1.31, -.13)  # centre of the region, right side
BUST_LIFT, BUST_TOP, BUST_UNDER = .020, .010, .012
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
    leg_x, leg_z, close = curve(LEGS, 1), curve(LEGS, 2), curve(INNER)

    def warp(points, head_bound):
        p = np.asarray(points, dtype=np.float64)
        q = p.copy()
        x, y, z = p.T
        ax = np.abs(x)
        side = np.where(x < 0, -1.0, 1.0)
        body = np.where(head_bound, 0.0, 1.0)

        # Legs, in the left leg's frame (xm <= 0).
        outer, inner, centre_z = shape.at(y)
        inner = np.minimum(inner, -1e-4)
        xm = -ax
        pivot = np.minimum(inner + ((outer + inner) / 2 - inner) * PIVOT, inner - 1e-4)
        beyond = np.maximum(outer - xm, 0)                    # garments outside the leg
        fade = (1 - smooth(.05, .14, beyond)) * (1 - smooth(.90, .97, y)) * body
        outside = (np.maximum(xm, outer) - pivot) * (leg_x(y) - 1)
        # Inner side: the old inner edge moves to `edge`; everything between
        # the pivot and the midline follows in proportion.
        edge = inner * close(y)
        inside = np.where(xm <= inner, (xm - pivot) * ((edge - pivot) / (inner - pivot) - 1), xm * (edge / inner - 1))
        q[:, 0] -= side * np.where(xm < pivot, outside, inside) * fade
        q[:, 2] += (z - centre_z) * (leg_z(y) - 1) * fade

        # Trunk: narrower about the spine; the bust keeps its width.
        amount = torso(y) - 1
        bust = smooth(1.22, 1.27, y) * (1 - smooth(-.11, -.08, z))
        trunk = (1 - smooth(.19, .23, ax)) * (1 - bust) * body
        q[:, 0] += x * amount * trunk
        q[:, 2] += np.minimum(z + .015, 0) * amount * BELLY_DEPTH * (1 - smooth(1.20, 1.26, y)) * trunk

        # Bust: lifted where it projects, fuller on top, tucked underneath.
        dx = ax - BUST[0]
        near = np.exp(-(dx / .075) ** 2 - ((y - BUST[1]) / .085) ** 2) * body * (ax < .19)
        forward = smooth(-.095, -.165, z)
        q[:, 1] += BUST_LIFT * forward * near
        q[:, 2] -= BUST_TOP * np.exp(-((y - 1.375) / .030) ** 2 - (dx / .060) ** 2) * smooth(-.06, -.10, z) * body
        q[:, 2] += BUST_UNDER * forward * np.exp(-((y - 1.275) / .030) ** 2 - (dx / .070) ** 2) * body

        # Longer thigh, shorter shin: the knee comes down.
        low, high = LEG_FIXED
        tent = np.where(y < KNEE_Y, (y - low) / (KNEE_Y - low), (high - y) / (high - KNEE_Y))
        q[:, 1] -= KNEE_DROP * np.clip(tent, 0, 1) * body * (ax < .30)
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
    apply_map(asset, make_warp(shape))
    report(Silhouette(asset), 'After ')
    for node in asset.d['nodes']:              # rounding dust must not read as a transform
        if 'translation' in node:
            node['translation'] = [0.0 if abs(v) < 1e-12 else v for v in node['translation']]
    asset.d['asset']['generator'] = GENERATOR
    asset.write(target)


if __name__ == '__main__':
    build(*sys.argv[1:])
