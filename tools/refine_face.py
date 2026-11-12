"""Revision 14: the face rebuilt against the user's reference sheet.

Input must be r13. The targets were measured on the frontal "Neutrale" head
and the eye close-up of the private reference sheet, in units of the distance
H between the eye line and the chin; none of those images is stored here.

1. Proportions (one space map, so skinning, morphs and hair follow):
   fuller cheeks and jaw down to a small chin, nose and mouth a little
   higher, chin slightly forward, flatter eye plane.
2. Skin mesh: eye openings closed with a soft lid surface, one level of Loop
   subdivision (morph targets carried through the same operator), normals
   blended toward an ellipsoid so the cel shading stays clean.
3. Skin texture repainted at 2048 px (tools/face_paint.py).
4. Eyes and brows redrawn as textured layers (tools/face_eyes.py); the stock
   eye and brow parts are removed.

Usage: python3 tools/refine_face.py r13.glb r14.glb
"""
import sys
from pathlib import Path
import numpy as np
from refine_mesh import Asset, smooth
from refine_body import apply_map
from refine_hair import compact
from refine_subdivide import append, blend_weights, FLOAT, USHORT
from face_mesh import DepthMap, Loop, border_loops, fill_loop, uv_islands
from face_paint import paint
from face_eyes import HALF_WIDTH, EyeFrame, build as build_eyes

SOURCE_GENERATOR = 'Neliel face and hair 13 / tools/refine_face_hair.py'
GENERATOR = 'Neliel face 14 / tools/refine_face.py'
SKIN = 'Viso'

# Reference layout, as fractions of H measured downward from the eye line.
NOSE_AT, MOUTH_AT = .31, .605
# Half-width of the face outline (in H) at those fractions. The reference
# profile looked too round on the 3D head, twice; this keeps the incoming jaw
# and soft chin below the mouth and only fills the cheekbones above it.
OUTLINE = [(0, .875), (.17, .84), (.34, .79), (.45, .75), (.55, .70), (.63, .65), (.70, .60),
           (.76, .55), (.805, .50), (.86, .43), (.91, .34), (.94, .25), (.97, .15)]
WIDEN_LIMIT = 1.30
EYE_PLANE = .0035          # forward push of the outer eye area (metres)
CHEEK_FRONT = .0010        # fuller lower cheeks seen from the side
CHIN_FORWARD = .0020
LIPS_BACK = .0015
NOSE_TIP = .0015
MOUTH_CORNERS = .0012      # resting corners lifted for a soft smile
LID_LIFT = .0010           # the closed-lid surface bulges this much
ROUND_NORMALS = .80        # blend of the skin normals toward an ellipsoid
HEAD_RADII = np.array([.072, .100, .095])


def primitive_of(doc, material):
    for mesh in doc['meshes']:
        for primitive in mesh['primitives']:
            if doc['materials'][primitive['material']]['name'] == material:
                return mesh, primitive
    raise ValueError(f'{material} not found')


def gauss(v, centre, sigma):
    return np.exp(-((v - centre) / sigma) ** 2)


def monotone(xs, ys):
    """Monotone cubic (Fritsch-Carlson) through the knots; identity outside them."""
    xs, ys = np.asarray(xs, float), np.asarray(ys, float)
    h = np.diff(xs)
    delta = np.diff(ys) / h
    slope = np.empty(len(xs))
    slope[0], slope[-1] = 1.0, 1.0                 # meet the identity at both ends
    for i in range(1, len(xs) - 1):
        slope[i] = 0 if delta[i - 1] * delta[i] <= 0 else \
            3 * (h[i - 1] + h[i]) / ((2 * h[i] + h[i - 1]) / delta[i - 1] + (h[i] + 2 * h[i - 1]) / delta[i])

    def curve(v):
        v = np.asarray(v, float)
        i = np.clip(np.searchsorted(xs, v) - 1, 0, len(xs) - 2)
        t = np.clip((v - xs[i]) / h[i], 0, 1)
        value = ((2 * t ** 3 - 3 * t ** 2 + 1) * ys[i] + (t ** 3 - 2 * t ** 2 + t) * h[i] * slope[i]
                 + (-2 * t ** 3 + 3 * t ** 2) * ys[i + 1] + (t ** 3 - t ** 2) * h[i] * slope[i + 1])
        return np.where((v <= xs[0]) | (v >= xs[-1]), v, value)
    return curve


class Landmarks:
    """Where the features of the incoming face are, measured on the mesh."""

    def __init__(self, asset, eyes=None):
        doc = asset.d
        _, part = primitive_of(doc, SKIN)
        points = asset.array(part['attributes']['POSITION']).astype(np.float64)
        triangles = asset.array(part['indices']).reshape(-1, 3).astype(int)
        label = uv_islands(triangles, len(points))
        values, counts = np.unique(label, return_counts=True)
        front = triangles[label == values[np.argmax(counts)]]      # the face without the ears
        self.eyes, self.mouth = {}, None
        for loop in border_loops(points, front):
            ring = points[loop]
            centre, extent = ring.mean(0), ring.max(0) - ring.min(0)
            if extent[0] > .06 or centre[2] > -.03:
                continue                                           # the outer border of the skin
            if abs(centre[0]) > .015:
                self.eyes[int(np.sign(centre[0]))] = ring
            elif self.mouth is None or centre[1] < self.mouth.mean(0)[1]:
                self.mouth = ring
        if self.mouth is None:
            raise ValueError('Mouth opening not found')
        if eyes is None:                   # measure the openings; later the lids are closed
            if set(self.eyes) != {-1, 1}:
                raise ValueError('Eye openings not found')
            corners = [ring[[np.abs(ring[:, 0]).argmin(), np.abs(ring[:, 0]).argmax()]] for ring in self.eyes.values()]
            eyes = (float(np.mean([c[:, 1].mean() for c in corners])),
                    float(np.mean([np.abs(c[:, 0]).mean() for c in corners])))
        self.eye_y, self.eye_x = eyes
        used = points[np.unique(front)]
        middle = used[(np.abs(used[:, 0]) < .005) & (used[:, 2] < -.04)]
        self.chin_y = float(middle[:, 1].min())
        tip = middle[middle[:, 2].argmin()]
        self.nose_y, self.nose_z = float(tip[1]), float(tip[2])
        self.mouth_y = float(self.mouth[:, 1].mean())
        self.mouth_x = float(np.abs(self.mouth[:, 0]).max())
        self.height = self.eye_y - self.chin_y
        bounds = (-.11, .11, self.chin_y - .03, self.eye_y + .12)
        self.depth = DepthMap(points, front, bounds, 2000)
        rows = np.linspace(bounds[2], bounds[3], 400)
        reach = self.depth.half_width(rows)
        kernel = np.ones(5) / 5
        self.outline = (rows, np.convolve(np.pad(reach, 2, mode='edge'), kernel, mode='valid'))

    def half_width(self, y):
        return np.interp(y, *self.outline)

    def fraction(self, y):
        return (self.eye_y - np.asarray(y)) / self.height

    def describe(self):
        return (f'eye line {self.eye_y:.4f} (x {self.eye_x:.4f}), nose {self.nose_y:.4f}, mouth {self.mouth_y:.4f}, '
                f'chin {self.chin_y:.4f}; H {self.height:.4f}; nose at {self.fraction(self.nose_y):.2f} H, '
                f'mouth at {self.fraction(self.mouth_y):.2f} H; half-width at the eyes '
                f'{self.half_width(self.eye_y) / self.height:.2f} H')


def make_warp(face):
    """The space map from the incoming proportions to the reference ones."""
    H, eye_y = face.height, face.eye_y
    layout = monotone([0, face.fraction(face.nose_y), face.fraction(face.mouth_y), 1],
                      [0, NOSE_AT, MOUTH_AT, 1])
    nose_y, mouth_y = eye_y - NOSE_AT * H, eye_y - MOUTH_AT * H

    # Sideways scale of the outline, from the measured and the reference profile.
    f = np.linspace(-.6, 1.25, 186)
    measured = np.maximum(face.half_width(eye_y - f * H), 1e-4)
    wanted = np.interp(f, *zip(*OUTLINE)) * H
    scale = np.clip(wanted / measured, 1, WIDEN_LIMIT)
    scale = np.where(f < 0, 1 + (np.interp(0, f, scale) - 1) * smooth(-.45, 0, f), scale)
    scale = np.where(f > .97, 1 + (np.interp(.97, f, scale) - 1) * (1 - smooth(1.02, 1.22, f)), scale)
    scale = np.convolve(np.pad(scale, 4, mode='edge'), np.ones(9) / 9, mode='valid')

    def warp(points, head_bound):
        p = np.asarray(points, dtype=np.float64)
        q = p.copy()
        x, y, z = p.T
        ax, sign = np.abs(x), np.sign(x)
        fraction = (eye_y - y) / H
        reach = np.maximum(face.half_width(y), .01)
        front = 1 - smooth(-.035, -.005, z)

        # Nose and mouth move up along the middle of the face; the outline stays.
        middle = (1 - smooth(.45, .95, ax / reach)) * front
        lifted = y + (eye_y - layout(fraction) * H - y) * middle
        q[:, 1] = lifted

        # Fuller cheeks and jaw. The middle keeps its width so nose and mouth
        # are not stretched; ears move out with the cheeks. Hair beside the
        # face follows by height only and returns to its place gradually below
        # the chin, so wavy locks are not bent by their own depth.
        skin_scale = (np.interp(fraction, f, scale) - 1) * (1 - smooth(.0, .035, z))
        hair_scale = (np.interp(np.minimum(fraction, .97), f, scale) - 1) \
            * (1 - smooth(1.0, 2.4, fraction)) * (1 - smooth(.03, .10, z))
        widen = np.where(head_bound, hair_scale, skin_scale) * smooth(.2, .8, ax / reach)
        q[:, 0] += x * widen

        # Depth: a flatter plane across the eyes, fuller lower cheeks, chin
        # forward, lips a touch back and a slightly sharper nose tip.
        q[:, 2] -= EYE_PLANE * gauss(ax, .052, .014) * gauss(y, eye_y - .002, .020) * front
        q[:, 2] -= CHEEK_FRONT * gauss(ax, .032, .014) * gauss(lifted, mouth_y + .004, .020) * front
        q[:, 2] -= CHIN_FORWARD * gauss(lifted, face.chin_y + .011, .013) * gauss(ax, 0, .028) * front
        q[:, 2] += LIPS_BACK * gauss(lifted, mouth_y, .007) * gauss(ax, 0, .022) * front
        q[:, 2] -= NOSE_TIP * gauss(lifted, nose_y, .005) * gauss(ax, 0, .006) * front

        # Resting mouth: corners a little higher than the middle.
        corner = smooth(.3, 1, ax / face.mouth_x) * (1 - smooth(1.3, 2.2, ax / face.mouth_x))
        q[:, 1] += MOUTH_CORNERS * corner * gauss(lifted, mouth_y, .006) * front
        return q
    return warp


def rebuild_skin(asset, face):
    """Close the eye openings, subdivide the skin once and round its normals.

    The skin gets its own vertex buffers; the mouth interior keeps the shared
    one, and still meets the lips because open borders do not move.
    """
    doc = asset.d
    mesh, part = primitive_of(doc, SKIN)
    attrs = part['attributes']
    index = asset.array(part['indices']).reshape(-1, 3).astype(int)
    used, inverse = np.unique(index, return_inverse=True)
    triangles = inverse.reshape(-1, 3)
    points = asset.array(attrs['POSITION']).astype(np.float64)[used]
    uv = asset.array(attrs['TEXCOORD_0']).astype(np.float64)[used]
    joints = asset.array(attrs['JOINTS_0']).astype(np.int64)[used]
    weights = asset.array(attrs['WEIGHTS_0']).astype(np.float64)[used]
    deltas = [asset.array(target['POSITION']).astype(np.float64)[used] for target in part['targets']]
    node = next(n for n in doc['nodes'] if n.get('mesh') == doc['meshes'].index(mesh))
    head = doc['skins'][node['skin']]['joints'].index(
        next(i for i, n in enumerate(doc['nodes']) if n.get('name') == 'J_Bip_C_Head'))

    # The drawn eyes now open and close by themselves. The stock shapes must
    # not slide the lid skin over them: blink and wink leave the skin still,
    # smile and surprise keep moving everything except the eye area.
    still = np.zeros(len(points))
    for side in (-1, 1):
        a, b = EyeFrame(side, face.eye_y, face.height).local(points[:, 0], points[:, 1])
        reach = np.hypot(a / (1.15 * HALF_WIDTH), (b + .0015) / .0125)
        still = np.maximum(still, (1 - smooth(1.0, 1.5, reach)) * (points[:, 2] < -.02) * (np.sign(points[:, 0]) == side))
    for name, delta in zip(mesh['extras']['targetNames'], deltas):
        delta *= 0 if name in ('blink', 'wink') else (1 - still)[:, None]

    label = uv_islands(triangles, len(points))
    values, counts = np.unique(label, return_counts=True)
    front = triangles[label == values[np.argmax(counts)]]
    closed = 0
    for loop in border_loops(points, front):
        ring = points[loop]
        centre, extent = ring.mean(0), ring.max(0) - ring.min(0)
        if extent[0] > .06 or centre[2] > -.03 or abs(centre[0]) < .015:
            continue                                   # outer border or mouth
        middle, fan = fill_loop(points, loop, LID_LIFT)
        fan[:, 2] = len(points)
        points = np.concatenate([points, middle[None]])
        uv = np.concatenate([uv, uv[loop].mean(0)[None]])
        joints = np.concatenate([joints, [[head, 0, 0, 0]]])
        weights = np.concatenate([weights, [[1, 0, 0, 0]]])
        deltas = [np.concatenate([d, d[loop].mean(0)[None]]) for d in deltas]
        triangles = np.concatenate([triangles, fan])
        closed += 1
    if closed != 2:
        raise ValueError(f'Expected two eye openings, closed {closed}')

    loop = Loop(points, triangles)
    fine = loop.positions(points)
    fine_deltas = [loop.positions(points + d) - fine for d in deltas]
    a, b = loop.pairs()
    odd_joints, odd_weights = blend_weights(joints, weights, a, b)
    normal = loop.normals(fine)
    centre = np.array([0, face.eye_y + .010, .005])
    round_normal = (fine - centre) / HEAD_RADII ** 2
    round_normal /= np.linalg.norm(round_normal, axis=1)[:, None]
    normal = (1 - ROUND_NORMALS) * normal + ROUND_NORMALS * round_normal
    normal /= np.linalg.norm(normal, axis=1)[:, None]
    if len(fine) > 65535:
        raise ValueError('Subdivided skin exceeds 16-bit indices')

    part['attributes'] = {
        'POSITION': append(asset, fine, 'VEC3', FLOAT, bounds=True, target=34962),
        'NORMAL': append(asset, normal, 'VEC3', FLOAT, target=34962),
        'TEXCOORD_0': append(asset, loop.linear(uv), 'VEC2', FLOAT, target=34962),
        'JOINTS_0': append(asset, np.concatenate([joints, odd_joints]), 'VEC4', USHORT, target=34962),
        'WEIGHTS_0': append(asset, np.concatenate([weights, odd_weights]), 'VEC4', FLOAT, target=34962),
    }
    part['indices'] = append(asset, loop.triangles.reshape(-1, 1), 'SCALAR', USHORT, target=34963)
    part['targets'] = [{'POSITION': append(asset, d, 'VEC3', FLOAT, bounds=True, target=34962)} for d in fine_deltas]
    return {'before': len(triangles), 'triangles': loop.triangles, 'points': fine, 'deltas': fine_deltas, 'head': head}


def build(source, target, preview=None):
    if Path(source).resolve() == Path(target).resolve():
        raise ValueError('Preserve the source revision')
    asset = Asset(source)
    doc = asset.d
    if doc['asset'].get('generator') != SOURCE_GENERATOR:
        raise ValueError('Expected revision 13; do not apply cumulatively')
    before = Landmarks(asset)
    print('Before:', before.describe())
    apply_map(asset, make_warp(before))
    mapped = Landmarks(asset)
    print('After: ', mapped.describe())
    skin = rebuild_skin(asset, mapped)
    print('Skin: %d -> %d triangles, %d vertices' % (skin['before'], len(skin['triangles']), len(skin['points'])))
    face = Landmarks(asset, eyes=(mapped.eye_y, mapped.eye_x))
    print('Outline, reference/result in H:', ' '.join(
        f'{f:.2f}:{w:.2f}/{face.half_width(face.eye_y - f * face.height) / face.height:.2f}' for f, w in OUTLINE))
    mesh, part = primitive_of(doc, SKIN)
    picture = paint(asset, part, face, face.mouth, face.nose_y)
    if preview:
        picture.save(preview)
    bounds = (-.090, .090, face.eye_y - .035, face.eye_y + .055)
    depth = DepthMap(skin['points'], skin['triangles'], bounds, 5000)
    drawn = build_eyes(asset, mesh, face, depth, skin['points'], skin['deltas'], skin['head'])
    print(f'Eyes and brows: {drawn} triangles')
    compact(asset)
    doc['asset']['generator'] = GENERATOR
    asset.write(target)


if __name__ == '__main__':
    build(*sys.argv[1:])
