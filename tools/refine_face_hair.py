"""Revision 13: smaller ears, painted face finish, first hair additions.

Input must be r12. Targets are the user's character sheet.

- Ears: the part that stands out from the head is 30% smaller.
- Ponytail: 25% longer below the shoulders (bones follow) and a purple
  scrunchie at the tie, painted with vertex colours in the same primitive.
- Face-framing locks and three thin fringe strands, built in the same thin
  style as the existing side locks and added to that mesh.
- Face texture: fuller coloured lips, a soft shadow under the nose and a
  darker upper eyelid.
- Upper eyelids lowered by baking a third of the blink into the rest shape;
  irises 10% smaller.
- The triangle clip sits on the fringe instead of floating in front of it.

Usage: python3 tools/refine_face_hair.py r12.glb r13.glb
"""
import io
import sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageFilter
from refine_mesh import Asset, smooth
from refine_body import apply_map, world_positions
from refine_subdivide import append, FLOAT, USHORT
from refine_identity import image_of
from refine_hair import compact
from build_study_texture import texel_positions

SOURCE_GENERATOR = 'Neliel figure 12 / tools/refine_figure.py'
GENERATOR = 'Neliel face and hair 13 / tools/refine_face_hair.py'

EAR_ROOT = np.array([.074, 1.600, .016])
EAR_SHRINK = .30
TAIL_FROM, TAIL_STRETCH = 1.45, .25
CLIP_BACK = .011
HAIR = np.array([.70, .64, .81])
SCRUNCHIE = np.array([.36, .12, .72])

# Control points (x for the right side of the figure, +x; mirrored for the
# left), then width in metres. z is given as a distance in front of the skin.
FRAMING = [      # absolute z here; the builder only keeps them clear of the skin
    ([(.070, 1.672, -.052), (.088, 1.600, -.058), (.092, 1.520, -.066), (.088, 1.450, -.082), (.082, 1.395, -.110)], .015),
    ([(.058, 1.676, -.070), (.074, 1.610, -.074), (.071, 1.545, -.078), (.064, 1.490, -.080), (.068, 1.455, -.084)], .011),
]
FRINGE = [
    ([(.010, 1.668, .010), (.002, 1.630, .012), (-.006, 1.600, .010), (.003, 1.574, .007)], .008),
    ([(-.026, 1.668, .010), (-.022, 1.632, .012), (-.014, 1.604, .009), (-.016, 1.586, .006)], .007),
    ([(.034, 1.664, .010), (.031, 1.630, .012), (.024, 1.606, .009), (.027, 1.590, .006)], .007),
]


def warp(points, head_bound):
    p = np.asarray(points, dtype=np.float64)
    q = p.copy()
    x, y, z = p.T
    ax, sign = np.abs(x), np.sign(x)
    hair = np.where(head_bound, 1.0, 0.0)

    # Ears belong to the face mesh; hair around them stays where it is.
    ear = smooth(.068, .080, ax) * smooth(1.55, 1.57, y) * (1 - smooth(1.66, 1.69, y)) \
        * smooth(-.015, .0, z) * (1 - hair)
    root = EAR_ROOT * np.stack([sign, np.ones_like(x), np.ones_like(x)], 1)
    q += (root - p) * (EAR_SHRINK * ear)[:, None]

    # Longer ponytail: only the part hanging behind the back is stretched.
    tail = hair * smooth(.04, .07, z)
    q[:, 1] -= TAIL_STRETCH * np.maximum(TAIL_FROM - y, 0) * tail
    return q


def catmull(points, count):
    p = np.array(points, dtype=np.float64)
    p = np.concatenate([2 * p[:1] - p[1:2], p, 2 * p[-1:] - p[-2:-1]])
    out = []
    for t in np.linspace(0, len(p) - 3, count):
        i = min(int(t), len(p) - 4)
        u = t - i
        a, b, c, d = p[i:i + 4]
        out.append(.5 * ((2 * b) + (-a + c) * u + (2 * a - 5 * b + 4 * c - d) * u * u
                         + (-a + 3 * b - 3 * c + d) * u ** 3))
    return np.array(out)


def strand(line, width, rings=18, around=6, clear=None):
    """A thin flattened lock along `line`, facing the front, pointed tip."""
    line = catmull(line, rings)
    if clear is not None:
        # Keep the lock just in front of the skin, then even out the depth.
        line[:, 2] = np.minimum(line[:, 2], [clear(x, y) - .007 for x, y, _ in line])
        line[1:-1, 2] = np.convolve(line[:, 2], [.25, .5, .25], mode='valid')
    s = np.linspace(0, 1, rings)
    tangent = np.gradient(line, axis=0)
    tangent /= np.linalg.norm(tangent, axis=1)[:, None]
    side = np.cross(tangent, [0, 0, -1.0])
    side /= np.linalg.norm(side, axis=1)[:, None]
    normal = np.cross(side, tangent)
    w = width * (.55 + .45 * smooth(0, .25, s)) * np.cos(np.pi / 2 * np.clip((s - .45) / .55, 0, 1)) ** .8
    theta = 2 * np.pi * np.arange(around) / around
    ring = (line[:, None] + side[:, None] * (w[:, None] * np.cos(theta) / 2)[..., None]
            + normal[:, None] * (w[:, None] * .16 * np.sin(theta))[..., None])
    points = np.concatenate([ring[:-1].reshape(-1, 3), line[-1:]])
    tip = len(points) - 1
    triangles = []
    for r in range(rings - 2):
        for k in range(around):
            i, j = r * around + k, r * around + (k + 1) % around
            triangles += [[i, j, i + around], [j, j + around, i + around]]
    last = (rings - 2) * around
    triangles += [[last + k, last + (k + 1) % around, tip] for k in range(around)]
    shade = 1.0 + .06 * np.sin(theta)[None] - .10 * np.abs(np.cos(theta))[None] ** 3 - .05 * s[:-1, None]
    colour = HAIR[None] * np.concatenate([shade.reshape(-1), [.92]])[:, None]
    return points, np.array(triangles), colour


def smooth_normals(points, triangles):
    corner = points[triangles]
    face = np.cross(corner[:, 1] - corner[:, 0], corner[:, 2] - corner[:, 0])
    normal = np.zeros_like(points)
    for k in range(3):
        np.add.at(normal, triangles[:, k], face)
    length = np.linalg.norm(normal, axis=1)
    normal[length > 1e-12] /= length[length > 1e-12, None]
    normal[length <= 1e-12] = [0, 0, -1]
    return normal


def primitive_of(doc, material):
    for mesh in doc['meshes']:
        for primitive in mesh['primitives']:
            if doc['materials'][primitive['material']]['name'] == material:
                return mesh, primitive
    raise ValueError(f'{material} not found')


def extend(asset, primitive, points, triangles, colour, joint):
    """Append geometry to a skinned vertex-colour primitive, all on one joint."""
    attrs = primitive['attributes']
    old = {k: asset.array(v).astype(np.float64) for k, v in attrs.items()}
    old_colour = old['COLOR_0'] / (255 if asset.d['accessors'][attrs['COLOR_0']]['componentType'] == 5121 else 1)
    old_triangles = asset.array(primitive['indices']).reshape(-1, 3).astype(int)
    count = len(old['POSITION'])
    joints = np.zeros((len(points), 4))
    joints[:, 0] = joint
    weights = np.zeros((len(points), 4))
    weights[:, 0] = 1
    rgba = np.concatenate([np.clip(colour, 0, 1), np.ones((len(colour), 1))], 1)
    merged = np.concatenate([old_triangles, triangles + count])
    if merged.max() > 65535:
        raise ValueError('Too many vertices for 16-bit indices')
    primitive['attributes'] = {
        'POSITION': append(asset, np.concatenate([old['POSITION'], points]), 'VEC3', FLOAT, bounds=True, target=34962),
        'NORMAL': append(asset, np.concatenate([old['NORMAL'], smooth_normals(points, triangles)]), 'VEC3', FLOAT, target=34962),
        'COLOR_0': append(asset, np.concatenate([old_colour, rgba]), 'VEC4', FLOAT, target=34962),
        'JOINTS_0': append(asset, np.concatenate([old['JOINTS_0'], joints]), 'VEC4', USHORT, target=34962),
        'WEIGHTS_0': append(asset, np.concatenate([old['WEIGHTS_0'], weights]), 'VEC4', FLOAT, target=34962),
    }
    primitive['indices'] = append(asset, merged.reshape(-1, 1), 'SCALAR', USHORT, target=34963)


def outward(points, triangles):
    """Wind a closed, roughly convex-in-section shape so normals point out."""
    normal = smooth_normals(points, triangles)
    return triangles if (np.einsum('ij,ij->i', normal, points - points.mean(0)) > 0).mean() > .5 else triangles[:, ::-1]


def add_locks(asset):
    doc = asset.d
    _, skin = primitive_of(doc, 'Pelle e tessuto')
    _, face = primitive_of(doc, 'Viso')
    surface = np.concatenate([asset.array(skin['attributes']['POSITION']), asset.array(face['attributes']['POSITION'])])
    surface = surface[surface[:, 2] < .02]

    def depth(x, y):
        near = surface[np.hypot(surface[:, 0] - x, surface[:, 1] - y) < .012]
        return near[:, 2].min() if len(near) else 1.0

    def in_front(point):
        x, y, gap = point
        z = depth(x, y)
        return [x, y, (z if z < 1 else -.09) - gap]

    mesh, primitive = primitive_of(doc, 'Argento · ciocche laterali')
    node = next(n for n in doc['nodes'] if n.get('mesh') == doc['meshes'].index(mesh))
    joint = doc['skins'][node['skin']]['joints'].index(
        next(i for i, n in enumerate(doc['nodes']) if n.get('name') == 'J_Bip_C_Head'))
    parts, faces, colours, offset = [], [], [], 0
    specs = [(line, width, side, True) for line, width in FRAMING for side in (1, -1)] \
        + [(line, width, 1, False) for line, width in FRINGE]
    for line, width, side, absolute in specs:
        if absolute:
            points, triangles, colour = strand([(side * x, y, z) for x, y, z in line], width, clear=depth)
        else:
            points, triangles, colour = strand([in_front((side * x, y, gap)) for x, y, gap in line], width)
        triangles = outward(points, triangles)
        parts.append(points)
        faces.append(triangles + offset)
        colours.append(colour)
        offset += len(points)
    extend(asset, primitive, np.concatenate(parts), np.concatenate(faces), np.concatenate(colours), joint)
    return len(specs)


def add_scrunchie(asset):
    doc = asset.d
    mesh, primitive = primitive_of(doc, 'Argento · coda')
    node = next(n for n in doc['nodes'] if n.get('mesh') == doc['meshes'].index(mesh))
    _, world = world_positions(doc['nodes'])
    bone = world[doc['skins'][node['skin']]['joints'][0]]
    tail = asset.array(primitive['attributes']['POSITION']).astype(np.float64)
    near = tail[np.linalg.norm(tail - bone, axis=1) < .055]
    centre = near.mean(0)
    # The tail leaves the tie along the main axis of the strands around it.
    axis = np.linalg.svd(near - centre)[2][0]
    u = np.cross(axis, [1, 0, 0])
    u /= np.linalg.norm(u)
    v = np.cross(axis, u)
    radial = np.hypot((near - centre) @ u, (near - centre) @ v)
    major, minor = np.percentile(radial, 80) + .004, .011
    a = 2 * np.pi * np.arange(20) / 20
    b = 2 * np.pi * np.arange(8) / 8
    ring = (major + minor * np.cos(b))[None]
    # A few lobes so it reads as gathered fabric rather than a plain ring.
    ring = ring * (1 + .06 * np.sin(5 * a))[:, None]
    points = (centre + ring[..., None] * (np.cos(a)[:, None, None] * u + np.sin(a)[:, None, None] * v)
              + (minor * 1.25 * np.sin(b))[None, :, None] * axis).reshape(-1, 3)
    triangles = []
    for i in range(20):
        for j in range(8):
            p, q = i * 8 + j, i * 8 + (j + 1) % 8
            r, s = ((i + 1) % 20) * 8 + j, ((i + 1) % 20) * 8 + (j + 1) % 8
            triangles += [[p, r, q], [q, r, s]]
    triangles = np.array(triangles)
    normal = smooth_normals(points, triangles)
    centreline = centre + major * ((points - centre) - ((points - centre) @ axis)[:, None] * axis) \
        / np.linalg.norm((points - centre) - ((points - centre) @ axis)[:, None] * axis, axis=1)[:, None]
    if (np.einsum('ij,ij->i', normal, points - centreline) > 0).mean() < .5:
        triangles = triangles[:, ::-1]
    colour = SCRUNCHIE[None] * (1 + .25 * np.tile(np.cos(b), 20))[:, None]
    extend(asset, primitive, points, triangles, colour, 0)


def paint_face(asset):
    doc = asset.d
    _, primitive = primitive_of(doc, 'Viso')
    material = doc['materials'][primitive['material']]
    image, picture = image_of(asset, material)
    rgb = np.array(picture.convert('RGB')).astype(np.float64)
    position, covered = texel_positions(asset, primitive, picture.width)
    x, y, z = np.moveaxis(position, -1, 0)
    ax = np.abs(x)
    front = covered * (1 - smooth(-.06, -.04, z))

    centre = asset.array(primitive['attributes']['POSITION'])
    centre = centre[(np.abs(centre[:, 0]) < .004) & (centre[:, 2] < -.05)]
    _, mouth = primitive_of(doc, 'Bocca')
    lips = asset.array(mouth['attributes']['POSITION'])[np.unique(asset.array(mouth['indices']))]
    line = np.median(lips[lips[:, 2] < np.percentile(lips[:, 2], 30)][:, 1])   # mouth line height
    nose = centre[np.argmin(centre[:, 2])][1]
    _, lashes = primitive_of(doc, 'Ciglia')
    lash = asset.array(lashes['attributes']['POSITION'])[np.unique(asset.array(lashes['indices']))]
    lid = lash[:, 1].max()

    def blob(cx, cy, rx, ry):
        return np.exp(-((x - cx) / rx) ** 2 - ((y - cy) / ry) ** 2)

    def tint(mask, colour, strength):
        m = np.clip(mask * strength, 0, 1)[..., None] * front[..., None]
        rgb[:] = rgb + (rgb * colour - rgb) * m

    lower = blob(0, line - .0052, .0125, .0040)
    upper = blob(0, line + .0030, .0120, .0024) * (1 - .5 * blob(0, line + .0045, .0030, .0020))
    tint(lower, np.array([1.00, .70, .72]), .70)
    tint(upper, np.array([.93, .60, .64]), .75)
    tint(blob(0, line - .0058, .0045, .0014), np.array([1.10, 1.08, 1.06]), .55)        # lip highlight
    tint(np.exp(-((y - line) / .0009) ** 2) * (ax < .0135), np.array([.62, .40, .44]), .55)
    tint(blob(0, nose - .0062, .0060, .0026), np.array([.80, .64, .62]), .55)           # under the nose
    for side in (-1, 1):
        tint(blob(side * .0052, nose - .0040, .0020, .0016), np.array([.70, .52, .52]), .45)
        tint(blob(side * .036, lid + .0035, .026, .0045), np.array([.80, .62, .74]), .55)  # eyelid

    encoded = io.BytesIO()
    Image.fromarray(np.clip(rgb, 0, 255).round().astype(np.uint8)).save(encoded, format='JPEG', quality=93)
    data = encoded.getvalue()
    asset.b += b'\0' * (-len(asset.b) % 4)
    doc['bufferViews'].append({'buffer': 0, 'byteOffset': len(asset.b), 'byteLength': len(data)})
    asset.b += data
    asset.b += b'\0' * (-len(asset.b) % 4)
    doc['buffers'][0]['byteLength'] = len(asset.b)
    image['bufferView'] = len(doc['bufferViews']) - 1
    image['mimeType'] = 'image/jpeg'


def half_lids(asset, amount=.32, iris=.90):
    """Lowered upper lids with round irises, as in the reference close-ups.

    Part of the blink morph is baked into the rest shape; blink and wink keep
    closing the eye fully. The irises become slightly smaller.
    """
    doc = asset.d
    mesh = next(m for m in doc['meshes'] if m['name'] == 'Viso')
    names = mesh['extras']['targetNames']
    blink, wink = names.index('blink'), names.index('wink')
    done = set()
    for primitive in mesh['primitives']:
        accessor = primitive['attributes']['POSITION']
        if accessor in done:
            continue
        done.add(accessor)
        base = asset.array(accessor).astype(np.float64)
        closing = asset.array(primitive['targets'][blink]['POSITION']).astype(np.float64)
        base += amount * closing
        for index in (blink, wink):
            target = primitive['targets'][index]['POSITION']
            asset.set(target, (asset.array(target) * (1 - amount)).astype(np.float32))
        for name in ('Iride viola', 'Riflesso occhi'):
            part = next(p for p in mesh['primitives'] if doc['materials'][p['material']]['name'] == name)
            if part['attributes']['POSITION'] != accessor:
                raise ValueError('Eye parts must share the face vertex buffer')
            used = np.unique(asset.array(part['indices']))
            for side in (-1, 1):
                eye = used[np.sign(base[used, 0]) == side]
                centre = base[eye].mean(0)
                base[eye, :2] = centre[:2] + (base[eye, :2] - centre[:2]) * iris
        asset.set(accessor, base.astype(np.float32))
        entry = doc['accessors'][accessor]
        entry['min'], entry['max'] = base.astype(np.float32).min(0).tolist(), base.astype(np.float32).max(0).tolist()


def build(source, target):
    if Path(source).resolve() == Path(target).resolve():
        raise ValueError('Preserve the source revision')
    asset = Asset(source)
    doc = asset.d
    if doc['asset'].get('generator') != SOURCE_GENERATOR:
        raise ValueError('Expected revision 12; do not apply cumulatively')
    apply_map(asset, warp)
    clip = next(n for n in doc['nodes'] if n.get('name') == 'Fermaglio')
    offset = clip.get('translation', [0, 0, 0])
    clip['translation'] = [offset[0], offset[1], offset[2] + CLIP_BACK]
    locks = add_locks(asset)
    add_scrunchie(asset)
    paint_face(asset)
    half_lids(asset)
    compact(asset)
    doc['asset']['generator'] = GENERATOR
    asset.write(target)
    print(f'Added {locks} locks and the scrunchie')


if __name__ == '__main__':
    build(*sys.argv[1:])
