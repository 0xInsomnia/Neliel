"""Revision 15: body proportions from the user's technical sheet.

Input must be r14. The sheet ("Scheda Tecnica Modello 3D", private, not in
the repository) has front, side and rear views at one scale. They were read
row by row; only the numbers are kept here, in metres on the finished model
(sheet chin and ankle on the model's: 3.601 mm per sheet pixel). The figure
on the sheet stands on tiptoe; the model stays flat-footed, so heights are
matched from the ankle up.

The stage works by measuring the model and moving it onto the tables:

1. Heights and shoulders: knee 6 cm lower (longer thigh, shorter shin),
   crotch, waist and bust placed as on the sheet, shoulders 21 mm wider.
2. Front outline: half-width of the trunk and the outer and inner edge of
   each leg by height. The thighs meet from the crotch down to mid-thigh.
3. Leg depth by height, from the side view.
4. Rear profile behind the back of the thigh, from the side view.
5. Front profile (bust, belly) ahead of the waist line, from the side view.

Every step is one space map applied to meshes, garments, morph targets and
joints together.

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
RESOLUTION = 1000
GRID = (np.arange(1500) + .5) / RESOLUTION          # heights of the raster rows

# Heights: incoming -> finished (ankle, knee, crotch, waist, chin); rigid above.
HEIGHTS = [(-1, -1), (.08, .08), (.141, .139), (.613, .5495), (.916, .931), (1.191, 1.230), (1.519, 1.547)]
RISE = HEIGHTS[-1][1] - HEIGHTS[-1][0]
HEIGHT_IN = [k[0] for k in HEIGHTS] + [3.0]
HEIGHT_OUT = [k[1] for k in HEIGHTS] + [3.0 + RISE]
SHOULDER_SHIFT = .021

# Front view, one side: height, outer edge and inner edge from the midline.
OUTLINE = [
    (.1750, .090, .029), (.1966, .094, .031), (.2182, .097, .029), (.2398, .103, .029), (.2614, .108, .029),
    (.2830, .112, .025), (.3046, .119, .025), (.3263, .122, .022), (.3479, .128, .018), (.3695, .133, .016),
    (.3911, .137, .014), (.4127, .140, .013), (.4343, .140, .013), (.4559, .140, .014), (.4775, .139, .018),
    (.4991, .135, .020), (.5207, .130, .023), (.5423, .122, .018), (.5639, .119, .011), (.5855, .119, .011),
    (.6071, .119, .009), (.6287, .119, .011), (.6503, .122, .011), (.6719, .128, .007), (.6935, .133, .007),
    (.7152, .140, .007), (.7368, .148, .005), (.7584, .153, 0), (.7800, .160, 0), (.8016, .167, 0),
    (.8232, .173, 0), (.8448, .178, 0), (.8664, .184, 0), (.8880, .187, 0), (.9096, .189, 0),
    (.9312, .191, 0), (.9528, .191, 0), (.9744, .187, 0), (.9960, .187, 0), (1.0177, .180, 0),
    (1.0393, .171, 0), (1.0609, .162, 0), (1.0825, .151, 0), (1.1041, .144, 0), (1.1257, .131, 0),
    (1.1473, .121, 0), (1.1689, .112, 0), (1.1905, .097, 0), (1.2121, .088, 0), (1.2337, .0864, 0),
    (1.2553, .092, 0), (1.2769, .097, 0), (1.2985, .099, 0)]
MIN_GAP = .0004            # the thighs touch, but the map must stay invertible

# Side view: height, depth of one leg.
LEG_DEPTH = [
    (.1750, .072), (.1966, .076), (.2182, .079), (.2398, .083), (.2614, .090), (.2830, .097), (.3046, .104),
    (.3263, .112), (.3479, .122), (.3695, .130), (.3911, .137), (.4127, .140), (.4343, .144), (.4559, .144),
    (.4775, .140), (.4991, .135), (.5207, .137), (.5423, .133), (.5639, .133), (.5855, .133), (.6071, .130),
    (.6287, .130), (.6503, .137), (.6719, .148), (.6935, .158), (.7152, .169), (.7368, .180), (.7584, .191),
    (.7800, .194), (.8016, .209), (.8232, .216), (.8448, .223), (.8664, .223)]
# Side view: height, how far the rear stands behind the back of the thigh.
# Above 1.08 m the sheet's back is behind the forearm and the hair: the values
# there follow the forearm's edge, which the rear emerges from.
REAR = [(.888, .004), (.910, .018), (.931, .036), (.953, .047), (.974, .050), (.996, .047), (1.018, .047),
        (1.039, .036), (1.061, .022), (1.082, -.007), (1.104, -.038), (1.126, -.052), (1.18, -.058)]
REAR_FADE = .05            # the top of the table blends into the model's own back
REAR_REFERENCE = (.845, .866)
# Side view: height, how far the front stands ahead of the waist line.
FRONT = [(.9168, .004), (.9492, .004), (.9708, 0), (.9924, -.007), (1.0032, -.011), (1.0248, -.014),
         (1.0464, -.011), (1.0789, -.011), (1.0897, -.007), (1.1113, -.004), (1.1221, 0), (1.2193, 0),
         (1.2301, .004), (1.2517, .007), (1.2625, .011), (1.2733, .014), (1.2841, .018), (1.2949, .022),
         (1.3057, .032), (1.3165, .040), (1.3273, .047), (1.3381, .054), (1.3705, .054), (1.3814, .050),
         (1.3922, .043), (1.4030, .032)]
FRONT_REFERENCE = (1.125, 1.22)


def table(rows, column=1):
    return np.interp(GRID, [r[0] for r in rows], [r[column] for r in rows])


def running_mean(values, width=9):
    return np.convolve(np.pad(values, width // 2, mode='edge'), np.ones(width) / width, mode='valid')


def at(values):
    return lambda y: np.interp(y, GRID, values)


def reshape_heights(points, head_bound):
    """Step 1, in the incoming model's coordinates."""
    p = np.asarray(points, dtype=np.float64)
    q = p.copy()
    x, y, z = p.T
    ax = np.abs(x)
    head = np.where(head_bound, 1.0, smooth(1.463, 1.513, y))
    girdle = smooth(1.198, 1.318, y) * (1 - head)
    bust = .5 + .5 * smooth(-.11, -.07, z)               # the bust follows only half way
    q[:, 0] += np.sign(x) * SHOULDER_SHIFT * smooth(.035, .105, ax) * girdle * bust
    # Whatever hangs from the head rises with it as one piece.
    q[:, 1] += np.where(head_bound, RISE, np.interp(y, HEIGHT_IN, HEIGHT_OUT) - y)
    return q


class Shape:
    """Outline and profiles of the skin by height, from a front and a rear raster."""

    def __init__(self, asset):
        doc = asset.d
        part = next(p for mesh in doc['meshes'] for p in mesh['primitives']
                    if doc['materials'][p['material']]['name'] == SKIN)
        points = asset.array(part['attributes']['POSITION']).astype(np.float64)
        triangles = asset.array(part['indices']).reshape(-1, 3).astype(int)
        bounds = (-.30, .30, 0, 1.5)
        front = frontal_depth(points, triangles, bounds, RESOLUTION)
        back = -frontal_depth(points * [1, 1, -1], triangles, bounds, RESOLUTION)
        covered = np.isfinite(front)
        x = (np.arange(covered.shape[1]) + .5) / RESOLUTION + bounds[0]
        left = covered & (x < 0)[None]
        trunk = covered & (np.abs(x) < .19)[None]

        def tidy(values, valid):
            values = np.where(valid, values, np.nan)
            first = np.argmax(valid)
            values[:first] = values[first]
            index = np.where(np.isnan(values), 0, np.arange(len(values)))
            np.maximum.accumulate(index, out=index)
            return running_mean(values[index])
        some = left.any(1)
        self.outer = tidy(np.where(left, x[None], np.inf).min(1), some)
        self.inner = np.minimum(tidy(np.where(left, x[None], -np.inf).max(1), some), -1e-4)
        self.leg_front = tidy(np.where(left, front, np.inf).min(1), some)
        self.leg_back = tidy(np.where(left, back, -np.inf).max(1), some)
        some = trunk.any(1)
        self.front = tidy(np.where(trunk, front, np.inf).min(1), some)
        self.back = tidy(np.where(trunk, back, -np.inf).max(1), some)

    def rear_offset(self):
        reference = np.median(self.back[(GRID > REAR_REFERENCE[0]) & (GRID < REAR_REFERENCE[1])])
        return self.back - reference

    def front_offset(self):
        reference = np.median(self.front[(GRID > FRONT_REFERENCE[0]) & (GRID < FRONT_REFERENCE[1])])
        return reference - self.front


def fit_outline(shape):
    """Step 2: outer and inner edge of each half onto the sheet's outline."""
    low, high = OUTLINE[0][0], OUTLINE[-1][0]
    outer_t, inner_t = table(OUTLINE, 1), np.maximum(table(OUTLINE, 2), MIN_GAP)
    centre = (shape.outer + shape.inner) / 2
    scale = (outer_t - inner_t) / np.maximum(shape.inner - shape.outer, 1e-3)
    shift = -(outer_t + inner_t) / 2 - centre
    k_low, k_high = np.searchsorted(GRID, low), np.searchsorted(GRID, high) - 1
    below, above = GRID < low, GRID > high
    # The foot keeps its size and follows the ankle; identity above the table.
    scale = np.where(below, 1 + (scale[k_low] - 1) * smooth(low - .065, low, GRID), scale)
    shift = np.where(below, shift[k_low], shift)
    fade = 1 - smooth(high, high + .035, GRID)
    scale = np.where(above, 1 + (scale[k_high] - 1) * fade, scale)
    shift = np.where(above, shift[k_high] * fade, shift)
    scale, shift = running_mean(scale), running_mean(shift)
    inner_ratio = (centre + shift + (shape.inner - centre) * scale) / shape.inner
    c, s, d, o, i, r = (at(v) for v in (centre, scale, shift, shape.outer, shape.inner, inner_ratio))

    def warp(points, head_bound):
        q = np.asarray(points, dtype=np.float64).copy()
        x, y = q[:, 0].copy(), q[:, 1]
        xm = -np.abs(x)
        side = np.where(x < 0, -1.0, 1.0)
        mapped = np.where(xm < o(y), c(y) + d(y) + (o(y) - c(y)) * s(y) + (xm - o(y)),    # garments: carried
                          np.where(xm <= i(y), c(y) + d(y) + (xm - c(y)) * s(y), xm * r(y)))
        q[:, 0] = np.where(head_bound, x, -side * mapped)
        return q
    return warp


def fit_leg_depth(shape):
    """Step 3: each leg as deep as on the side view, about its own middle."""
    low, high = LEG_DEPTH[0][0], LEG_DEPTH[-1][0]
    scale = table(LEG_DEPTH) / np.maximum(shape.leg_back - shape.leg_front, 1e-3)
    k_low, k_high = np.searchsorted(GRID, low), np.searchsorted(GRID, high) - 1
    scale = np.where(GRID < low, 1 + (scale[k_low] - 1) * smooth(low - .065, low, GRID), scale)
    scale = np.where(GRID > high, 1 + (scale[k_high] - 1) * (1 - smooth(high, high + .08, GRID)), scale)
    scale = running_mean(scale)
    middle = (shape.leg_front + shape.leg_back) / 2
    s, m = at(scale), at(middle)

    def warp(points, head_bound):
        q = np.asarray(points, dtype=np.float64).copy()
        y, z = q[:, 1], q[:, 2].copy()
        q[:, 2] = np.where(head_bound, z, m(y) + (z - m(y)) * s(y))
        return q
    return warp


def fit_rear(shape):
    """Step 4: the rear onto its profile, front to back only."""
    low, high = REAR[0][0], REAR[-1][0]
    shift = np.clip(table(REAR) - shape.rear_offset(), -.04, .07)
    shift = np.where((GRID >= low) & (GRID <= high), shift, 0) * (1 - smooth(high - REAR_FADE, high, GRID))
    shift = running_mean(shift, 11)
    d, reach = at(shift), at(np.maximum(shape.back, .03))

    def warp(points, head_bound):
        q = np.asarray(points, dtype=np.float64).copy()
        x, y, z = q.T
        weight = smooth(.25, .85, z / reach(y)) * (1 - smooth(.14, .20, np.abs(x))) * np.where(head_bound, 0.0, 1.0)
        q[:, 2] += d(y) * weight
        return q
    return warp


def fit_front(shape):
    """Step 5: bust and belly onto their profile, front to back only."""
    low, high = FRONT[0][0], FRONT[-1][0]
    shift = np.clip(table(FRONT) - shape.front_offset(), -.03, .03)
    shift = shift * smooth(low, low + .02, GRID) * (1 - smooth(high, high + .025, GRID))
    shift = running_mean(shift, 11)
    d, front, depth = at(shift), at(shape.front), at(np.maximum(shape.back - shape.front, .03))

    def warp(points, head_bound):
        q = np.asarray(points, dtype=np.float64).copy()
        x, y, z = q.T
        deep = (z - front(y)) / depth(y)
        weight = (1 - smooth(.15, .75, deep)) * (1 - smooth(.14, .20, np.abs(x))) * np.where(head_bound, 0.0, 1.0)
        q[:, 2] -= d(y) * weight
        return q
    return warp


def renew_normals(asset):
    """Smooth normals of the skin from its finished geometry, shared across UV seams.

    Seven maps in a row leave the carried normals slightly uneven, which shows
    as a ragged edge on the cel shadow.
    """
    doc = asset.d
    part = next(p for mesh in doc['meshes'] for p in mesh['primitives']
                if doc['materials'][p['material']]['name'] == SKIN)
    points = asset.array(part['attributes']['POSITION']).astype(np.float64)
    triangles = asset.array(part['indices']).reshape(-1, 3).astype(int)
    _, weld = np.unique(np.round(points, 6), axis=0, return_inverse=True)
    weld = weld.reshape(-1)
    corner = points[triangles]
    face = np.cross(corner[:, 1] - corner[:, 0], corner[:, 2] - corner[:, 0])
    summed = np.zeros((weld.max() + 1, 3))
    for k in range(3):
        np.add.at(summed, weld[triangles[:, k]], face)
    normal = summed[weld]
    length = np.linalg.norm(normal, axis=1)
    old = asset.array(part['attributes']['NORMAL']).astype(np.float64)
    normal = np.where(length[:, None] > 1e-12, normal / np.maximum(length, 1e-12)[:, None], old)
    asset.set(part['attributes']['NORMAL'], normal.astype(np.float32))


def report(shape):
    def row(label, target, value, heights):
        cells = ' '.join(f'{h:.2f}:{np.interp(h, GRID, target) * 1e3:.0f}/{np.interp(h, GRID, value) * 1e3:.0f}'
                         for h in heights)
        print(f'{label} (height: sheet/model, mm): {cells}')
    row('Outer edge', table(OUTLINE, 1), -shape.outer, (.20, .30, .43, .55, .63, .74, .87, .95, 1.04, 1.13, 1.23, 1.29))
    row('Inner edge', table(OUTLINE, 2), -shape.inner, (.20, .30, .43, .55, .63, .74, .80, .90))
    row('Leg depth', table(LEG_DEPTH), shape.leg_back - shape.leg_front, (.20, .30, .43, .55, .63, .74, .86))
    row('Rear behind thigh', table(REAR), shape.rear_offset(), (.91, .95, .97, 1.02, 1.06, 1.10, 1.13, 1.17, 1.22))
    row('Front ahead of waist', table(FRONT), shape.front_offset(), (.95, 1.02, 1.08, 1.25, 1.30, 1.34, 1.37, 1.40))


def build(source, target):
    if Path(source).resolve() == Path(target).resolve():
        raise ValueError('Preserve the source revision')
    asset = Asset(source)
    if asset.d['asset'].get('generator') != SOURCE_GENERATOR:
        raise ValueError('Expected revision 14; do not apply cumulatively')
    apply_map(asset, reshape_heights)
    for fit in (fit_outline, fit_outline, fit_leg_depth, fit_leg_depth, fit_rear, fit_front, fit_rear):
        apply_map(asset, fit(Shape(asset)))
    renew_normals(asset)
    report(Shape(asset))
    for node in asset.d['nodes']:              # rounding dust must not read as a transform
        if 'translation' in node:
            node['translation'] = [0.0 if abs(v) < 1e-12 else v for v in node['translation']]
    asset.d['asset']['generator'] = GENERATOR
    asset.write(target)


if __name__ == '__main__':
    build(*sys.argv[1:])
