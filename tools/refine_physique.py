"""Revision 15: body proportions from the reference turnaround.

Input must be r14. Measured on enlarged crops of the front and side figures
of the private sheet (1.523 mm per source pixel, chin and crotch aligned
with the model) and checked by drawing the model's outline over the front
figure; only the numbers are kept here. Head, neck, shoulders, bust width
and the heights of bust and waist already matched and are left alone. One
space map moves meshes, garments, morphs and joints together:

- Trunk: waist 80 mm half-width, a slim belly, and the hip flare moved down
  so the widest point (about 165 mm) sits at the top of the thighs.
- Crotch: on the stock mesh the legs part 5 cm too high and leave a slot.
  The inner thighs are brought together up to that point, so the legs now
  part where the drawing's do and open gradually below.
- Legs: 28 mm longer, with a longer thigh (knee 16 mm lower); much fuller
  in width and in depth, calves included. Widths in mm from 12 cm below the
  crotch down to the ankle: 157, 144, 120, 107, 97 (knee), 101, 115 (calf),
  107, 83, 63, 57; depths: 198, 169, 140, 127, 113, 124, 134, 122, 100, 77.
- Bust, seen from the side: lifted and rounder instead of pear-shaped.
- Rear, seen from the side: its profile is set from the side figure in a
  second pass (`round_rear`): a round curve whose fullest point sits low,
  about 4 cm behind the thigh, just above the fold.

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
# Per leg, by height on the incoming mesh: sideways scale, front-to-back scale.
LEGS = [(.00, 1.0, 1.0), (.06, 1.05, 1.0), (.14, 1.25, 1.10), (.188, 1.32, 1.13), (.22, 1.45, 1.20),
        (.299, 1.49, 1.33), (.392, 1.41, 1.26), (.472, 1.41, 1.26), (.55, 1.37, 1.30), (.5965, 1.33, 1.19),
        (.639, 1.44, 1.27), (.679, 1.46, 1.40), (.745, 1.41, 1.35), (.811, 1.22, 1.28), (.87, 1.08, 1.13),
        (.916, 1.0, 1.05), (.97, 1.0, 1.0)]
PIVOT = .35                # 0 keeps the inner edge of the leg, 1 its centre line
# Where the inner edge of the leg ends up, as a share of its old distance
# from the midline. Next to nothing from the drawing's crotch upward closes the slot.
INNER = [(.0, 1.0), (.5, 1.0), (.5965, .68), (.639, .55), (.70, .38), (.80, .22), (.85, .08),
         (.88, .04), (1.5, .04)]       # not quite zero: the map must stay invertible
# Heights: incoming -> outgoing. Longer legs, the knee lower on the leg.
HEIGHTS = [(-1, -1), (.08, .08), (.613, .597), (.90, .928)]
HEIGHT_IN = [k[0] for k in HEIGHTS] + [3.0]
HEIGHT_OUT = [k[1] for k in HEIGHTS] + [3.0 + HEIGHTS[-1][1] - HEIGHTS[-1][0]]
RISE = HEIGHTS[-1][1] - HEIGHTS[-1][0]
BUST = (.082, 1.31, -.13)  # centre of the region, right side
BUST_LIFT, BUST_TOP, BUST_UNDER = .020, .010, .012
# Rear profile on the finished figure: height, distance behind the back of
# the thigh. Read on the side figure from the fold up to the jacket hem; the
# part above, hidden there, keeps the model's own slope to the waist.
REAR = [(.915, 0), (.93, -.002), (.945, .020), (.96, .034), (.975, .041), (.99, .043), (1.01, .041),
        (1.03, .037), (1.055, .028), (1.08, .018), (1.11, -.004), (1.14, -.030), (1.17, -.055),
        (1.20, -.075), (1.225, -.086)]
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
        outside = (np.maximum(xm, outer) - pivot) * (leg_x(y) - 1) * fade
        # Inner side: the old inner edge moves to `edge`; everything between
        # the pivot and the midline follows in proportion. No fade by height:
        # it has to reach the point where the legs join.
        edge = inner * close(y)
        inside = np.where(xm <= inner, (xm - pivot) * ((edge - pivot) / (inner - pivot) - 1), xm * (edge / inner - 1))
        q[:, 0] -= side * np.where(xm < pivot, outside, inside * body)
        q[:, 2] += (z - centre_z) * (leg_z(y) - 1) * fade

        # Trunk: narrower about the spine; the bust keeps its width.
        amount = torso(y) - 1
        bust = smooth(1.22, 1.27, y) * (1 - smooth(-.11, -.08, z))
        trunk = (1 - smooth(.19, .23, ax)) * (1 - bust) * body
        q[:, 0] *= 1 + amount * trunk
        q[:, 2] += np.minimum(z + .015, 0) * amount * BELLY_DEPTH * (1 - smooth(1.20, 1.26, y)) * trunk

        # Bust: lifted where it projects, fuller on top, tucked underneath.
        dx = ax - BUST[0]
        near = np.exp(-(dx / .075) ** 2 - ((y - BUST[1]) / .085) ** 2) * body * (ax < .19)
        forward = smooth(-.095, -.165, z)
        q[:, 1] += BUST_LIFT * forward * near
        q[:, 2] -= BUST_TOP * np.exp(-((y - 1.375) / .030) ** 2 - (dx / .060) ** 2) * smooth(-.06, -.10, z) * body
        q[:, 2] += BUST_UNDER * forward * np.exp(-((y - 1.275) / .030) ** 2 - (dx / .070) ** 2) * body

        # Heights. Whatever hangs from the head rises with it as one piece.
        q[:, 1] += np.where(head_bound, RISE, np.interp(y, HEIGHT_IN, HEIGHT_OUT) - y)
        return q
    return warp


def report(shape, label, rise=0.0):
    def leg(y):
        return np.interp(np.interp(y, HEIGHT_IN, HEIGHT_OUT) if rise else y, shape.y, shape.width)

    def trunk(y):
        return np.interp(y + rise, shape.y, shape.half)
    print(f'{label}: trunk half-width (mm) under bust {trunk(1.249) * 1e3:.0f}, waist {trunk(1.185) * 1e3:.0f}, '
          f'navel {trunk(1.14) * 1e3:.0f}, hip top {trunk(1.075) * 1e3:.0f}, hips {trunk(.964) * 1e3:.0f}; '
          f'leg width upper thigh {leg(.816) * 1e3:.0f}, lower thigh {leg(.689) * 1e3:.0f}, knee {leg(.613) * 1e3:.0f}, '
          f'calf {leg(.434) * 1e3:.0f}, ankle {leg(.18) * 1e3:.0f}')


def rear_profile(asset):
    """Rear-most z of the skin by height, within the trunk's width."""
    doc = asset.d
    part = next(p for mesh in doc['meshes'] for p in mesh['primitives']
                if doc['materials'][p['material']]['name'] == SKIN)
    points = asset.array(part['attributes']['POSITION']).astype(np.float64)
    triangles = asset.array(part['indices']).reshape(-1, 3).astype(int)
    bounds = (-.20, .20, .80, 1.30)
    back = -frontal_depth(points * [1, 1, -1], triangles, bounds, RESOLUTION)
    y = (np.arange(back.shape[0]) + .5) / RESOLUTION + bounds[2]
    profile = np.where(np.isfinite(back), back, -np.inf).max(1)
    return y, np.convolve(np.pad(profile, 4, mode='edge'), np.ones(9) / 9, mode='valid')


def round_rear(asset):
    """Move the rear surface to the reference profile, front to back only."""
    y, profile = rear_profile(asset)
    thigh = float(np.median(profile[(y > .865) & (y < .895)]))
    wanted = thigh + np.interp(y, [k[0] for k in REAR], [k[1] for k in REAR])
    inside = (y >= REAR[0][0]) & (y <= REAR[-1][0])
    shift = np.where(inside, np.clip(wanted - profile, -.03, .04), 0)
    shift = np.convolve(np.pad(shift, 5, mode='edge'), np.ones(11) / 11, mode='valid')

    def warp(points, head_bound):
        q = np.asarray(points, dtype=np.float64).copy()
        x, height, z = q.T
        reach = np.maximum(np.interp(height, y, profile), .03)
        weight = smooth(.25, .85, z / reach) * (1 - smooth(.13, .19, np.abs(x))) * np.where(head_bound, 0.0, 1.0)
        q[:, 2] += np.interp(height, y, shift) * weight
        return q
    apply_map(asset, warp)
    after = rear_profile(asset)[1]
    return thigh, [(h, float(np.interp(h, y, after)) - thigh) for h in (.93, .96, .99, 1.03, 1.08, 1.14)]


def build(source, target):
    if Path(source).resolve() == Path(target).resolve():
        raise ValueError('Preserve the source revision')
    asset = Asset(source)
    if asset.d['asset'].get('generator') != SOURCE_GENERATOR:
        raise ValueError('Expected revision 14; do not apply cumulatively')
    shape = Silhouette(asset)
    report(shape, 'Before')
    apply_map(asset, make_warp(shape))
    report(Silhouette(asset), 'After ', RISE)
    thigh, rear = round_rear(asset)
    print('Rear behind the thigh (mm):', ', '.join(f'{h:.2f} m: {v * 1e3:+.0f}' for h, v in rear))
    for node in asset.d['nodes']:              # rounding dust must not read as a transform
        if 'translation' in node:
            node['translation'] = [0.0 if abs(v) < 1e-12 else v for v in node['translation']]
    asset.d['asset']['generator'] = GENERATOR
    asset.write(target)


if __name__ == '__main__':
    build(*sys.argv[1:])
