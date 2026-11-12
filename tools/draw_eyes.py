"""Drawn eyes: replace the stock eye parts with new shapes built from curves.

The former sclera, iris, catchlight, contour and lash primitives are removed
from the face mesh. One vertex-coloured primitive takes their place: an
almond opening, round iris clipped by the lids, catchlights, a thick upper
lash line with a wing and a thin lower lash. It lies just in front of the
skin and covers the eye opening of the face mesh. The four face morphs
(smile, surprised, blink, wink) are rebuilt for it from the same curves.

Used by refine_face_hair.py; the shapes are original.
"""
import numpy as np
from refine_mesh import smooth
from refine_subdivide import append, FLOAT, USHORT

MATERIAL = 'Sclera · occhi disegnati'
OLD_PARTS = ('Sclera', 'Iride viola', 'Riflesso occhi', 'Contorno occhi', 'Ciglia')

HALF_WIDTH = .0192
UPPER, LOWER = .0092, .0074
TILT = np.radians(11)
IRIS = .0086
COLUMNS = 30


def linear(rgb):
    c = np.asarray(rgb, dtype=np.float64)
    return np.where(c <= .04045, c / 12.92, ((c + .055) / 1.055) ** 2.4)


WHITE, SHADE = linear([.97, .96, .99]), linear([.70, .66, .84])
LASH, LOWER_LASH = linear([.07, .04, .11]), linear([.30, .16, .22])
RIM, PUPIL = linear([.20, .09, .42]), linear([.11, .05, .24])
IRIS_TOP, IRIS_BOTTOM, IRIS_RING = linear([.36, .17, .72]), linear([.74, .55, 1.0]), linear([.56, .34, .92])


def lids(pose):
    """Upper and lower lid curves b(t), t = -1 inner corner .. 1 outer corner."""
    def upper(t):
        return UPPER * np.clip(1 - t * t, 0, 1) ** .55 * (1 - .15 * t)

    def lower(t):
        return -LOWER * np.clip(1 - t * t, 0, 1) ** .8

    if pose == 'blink':
        return (lambda t: lower(t) * .55 + .0003 * np.clip(1 - t * t, 0, 1)), (lambda t: lower(t) * .55)
    if pose == 'surprised':
        return (lambda t: upper(t) * 1.30), (lambda t: lower(t) * 1.12)
    if pose == 'smile':
        return upper, (lambda t: lower(t) + .38 * (upper(t) - lower(t)))
    return upper, lower


def eye(pose, light):
    """Local (a, b, layer) points, triangles and colours for one eye.

    a runs along the eye toward the temple, b across it. `light` is +1 or -1:
    which way along a the key light sits, so both eyes get the catchlight on
    the same world side.
    """
    upper, lower = lids(pose)
    rest_upper, rest_lower = lids('rest')
    points, colours, triangles = [], [], []

    def grid(rows):
        """rows: list of (a, b, layer, colour) arrays of equal length."""
        start = len(points)
        width = len(rows[0][0])
        for a, b, layer, colour in rows:
            for i in range(width):
                points.append([a[i], b[i], layer[i]])
                colours.append(colour[i] if np.ndim(colour) > 1 else colour)
        for r in range(len(rows) - 1):
            for i in range(width - 1):
                p, q = start + r * width + i, start + r * width + i + 1
                triangles.extend([[p, q, p + width], [q, q + width, p + width]])

    t = np.linspace(-1, 1, COLUMNS)
    a = t * HALF_WIDTH

    # Sclera, shaded under the upper lid.
    rows = []
    for k in np.linspace(0, 1, 7):
        b = lower(t) + k * (upper(t) - lower(t))
        tone = WHITE + (SHADE - WHITE) * smooth(.45, 1.0, k)
        rows.append((a, b, np.full(COLUMNS, 1.0), np.tile(tone, (COLUMNS, 1))))
    grid(rows)

    # Iris: a disc clipped by the lids. Colours come from the rest shape so
    # they do not swim when the lids move.
    angle = np.linspace(0, 2 * np.pi, 33)
    centre_b = .0006
    rows = []
    for radius in np.linspace(0, 1, 9):
        ia = IRIS * radius * np.cos(angle)
        ib = centre_b + IRIS * radius * np.sin(angle)
        it = np.clip(ia / HALF_WIDTH, -1, 1)
        clipped = np.clip(ib, lower(it) + .0002, np.maximum(upper(it) - .0002, lower(it) + .0002))
        height = (ib - centre_b) / IRIS
        body = IRIS_BOTTOM + (IRIS_TOP - IRIS_BOTTOM) * smooth(-.75, .45, height)[:, None]
        tone = np.where(radius > .86, RIM, np.where(radius < .36, PUPIL, np.where(radius < .5, IRIS_RING, body)))
        rows.append((ia, clipped, np.full(len(angle), 2.0), tone))
    grid(rows)

    # Catchlights, hidden when the lid passes them.
    for da, db, size in ((.0030 * light, .0034, .0019), (-.0030 * light, -.0030, .0010)):
        ring = np.linspace(0, 2 * np.pi, 13)
        rows = []
        for radius in (0, 1):
            ha, hb = da + size * radius * np.cos(ring), centre_b + db + size * radius * np.sin(ring)
            ht = np.clip(ha / HALF_WIDTH, -1, 1)
            hb = np.clip(hb, lower(ht) + .0002, np.maximum(upper(ht) - .0002, lower(ht) + .0002))
            rows.append((ha, hb, np.full(len(ring), 3.0), np.tile(WHITE, (len(ring), 1))))
        grid(rows)

    # Upper lash line, thicker toward the temple, ending in a wing.
    wing = np.linspace(1, 1.42, 8)[1:]
    lt = np.concatenate([np.linspace(-1.04, 1, COLUMNS), wing])
    la = lt * HALF_WIDTH
    inside = np.clip(lt, -1, 1)
    edge = np.where(lt <= 1, upper(inside), 0)
    past = np.clip((lt - 1) / .42, 0, 1)
    thickness = (.0016 + .0028 * smooth(-.7, .9, lt)) * (1 - past) ** 1.2
    rise = past * .0062
    grid([(la, edge - .0005 * (1 - past) + rise, np.full(len(lt), 4.0), np.tile(LASH, (len(lt), 1))),
          (la, edge + thickness + rise, np.full(len(lt), 4.0), np.tile(LASH, (len(lt), 1)))])
    for at, length in ((.74, .0022), (.93, .0028)):
        base = np.array([at - .06, at + .06])
        tip_a = (at + .16) * HALF_WIDTH
        top = upper(np.array([at]))[0] + .0016 + .0028 * float(smooth(-.7, .9, at))
        grid([(base * HALF_WIDTH, upper(base) + .0016 + .0024 * smooth(-.7, .9, base), np.full(2, 4.0), np.tile(LASH, (2, 1))),
              (np.array([tip_a, tip_a]), np.full(2, top + length), np.full(2, 4.0), np.tile(LASH, (2, 1)))])

    # Lower lash: a thin line on the outer two thirds.
    bt = np.linspace(-.25, 1, 20)
    width = .0005 + .0007 * smooth(-.2, .9, bt)
    grid([(bt * HALF_WIDTH, lower(bt) - width, np.full(20, 4.0), np.tile(LOWER_LASH, (20, 1))),
          (bt * HALF_WIDTH, lower(bt) + .0002, np.full(20, 4.0), np.tile(LOWER_LASH, (20, 1)))])
    return np.array(points), np.array(triangles), np.array(colours)


def surface(face_points, side, centre):
    """Quadratic fit z(x, y) of the skin around one eye opening."""
    p = face_points[(np.sign(face_points[:, 0]) == side)]
    dx, dy = np.abs(p[:, 0]) - centre[0], p[:, 1] - centre[1]
    near = (np.abs(dx) < .032) & (dy > -.020) & (dy < .022) & (p[:, 2] < -.02)
    dx, dy, z = dx[near], dy[near], p[near, 2]
    basis = np.stack([np.ones_like(dx), dx, dy, dx * dx, dx * dy, dy * dy], 1)
    coefficient = np.linalg.lstsq(basis, z, rcond=None)[0]
    return lambda ex, ey: np.stack([np.ones_like(ex), ex, ey, ex * ex, ex * ey, ey * ey], 1) @ coefficient


def draw(asset, hole_of):
    """Replace the eye parts of the face mesh. hole_of(side) -> boundary points."""
    doc = asset.d
    mesh = next(m for m in doc['meshes'] if m['name'] == 'Viso')
    names = mesh['extras']['targetNames']
    skin_part = next(p for p in mesh['primitives'] if doc['materials'][p['material']]['name'] == 'Viso')
    face = asset.array(skin_part['attributes']['POSITION']).astype(np.float64)
    node = next(n for n in doc['nodes'] if n.get('mesh') == doc['meshes'].index(mesh))
    head = doc['skins'][node['skin']]['joints'].index(
        next(i for i, n in enumerate(doc['nodes']) if n.get('name') == 'J_Bip_C_Head'))

    poses = {}
    offset = 0
    all_triangles = []
    colours = []
    for side in (1, -1):
        hole = hole_of(side)
        centre = np.array([(np.abs(hole[:, 0]).min() + np.abs(hole[:, 0]).max()) / 2,
                           (hole[:, 1].min() + hole[:, 1].max()) / 2])
        fit = surface(face, side, centre)
        cos, sin = np.cos(TILT), np.sin(TILT)

        def place(local):
            ex = local[:, 0] * cos - local[:, 1] * sin
            ey = local[:, 0] * sin + local[:, 1] * cos
            z = fit(ex, ey) - .0010 - .0004 * local[:, 2]
            return np.stack([side * (centre[0] + ex), centre[1] + ey, z], 1)

        # Key light from the figure's right in both eyes.
        rest, triangles, colour = eye('rest', light=side)
        if side < 0:
            triangles = triangles[:, ::-1]
        # The drawn opening and lash must hide the opening of the skin mesh.
        hx, hy = np.abs(hole[:, 0]) - centre[0], hole[:, 1] - centre[1]
        ha, hb = hx * cos + hy * sin, -hx * sin + hy * cos
        upper, lower = lids('rest')
        ht = np.clip(ha / HALF_WIDTH, -1, 1)
        if (np.abs(ha) > HALF_WIDTH).any() or (hb > upper(ht) + .0010).any() or (hb < lower(ht) - .0003).any():
            raise ValueError('Drawn eye does not cover the eye opening of the face mesh')
        base = place(rest)
        poses.setdefault('rest', []).append(base)
        for name in names:
            active = name if name != 'wink' else ('blink' if side < 0 else 'rest')
            poses.setdefault(name, []).append(place(eye(active, light=side)[0]) - base)
        all_triangles.append(triangles + offset)
        colours.append(colour)
        offset += len(rest)

    points = np.concatenate(poses['rest'])
    colour = np.concatenate(colours)
    count = len(points)
    joints = np.zeros((count, 4))
    joints[:, 0] = head
    weights = np.zeros((count, 4))
    weights[:, 0] = 1
    normal = np.tile([0, 0, -1.0], (count, 1))
    doc['materials'].append({'name': MATERIAL, 'doubleSided': True, 'alphaMode': 'OPAQUE',
                             'pbrMetallicRoughness': {'metallicFactor': 0, 'roughnessFactor': .88,
                                                      'baseColorFactor': [1, 1, 1, 1]}})
    primitive = {
        'attributes': {
            'POSITION': append(asset, points, 'VEC3', FLOAT, bounds=True, target=34962),
            'NORMAL': append(asset, normal, 'VEC3', FLOAT, target=34962),
            'COLOR_0': append(asset, np.concatenate([colour, np.ones((count, 1))], 1), 'VEC4', FLOAT, target=34962),
            'JOINTS_0': append(asset, joints, 'VEC4', USHORT, target=34962),
            'WEIGHTS_0': append(asset, weights, 'VEC4', FLOAT, target=34962),
        },
        'indices': append(asset, np.concatenate(all_triangles).reshape(-1, 1), 'SCALAR', USHORT, target=34963),
        'material': len(doc['materials']) - 1,
        'targets': [{'POSITION': append(asset, np.concatenate(poses[name]), 'VEC3', FLOAT, bounds=True, target=34962)}
                    for name in names],
    }
    mesh['primitives'] = [p for p in mesh['primitives']
                          if doc['materials'][p['material']]['name'] not in OLD_PARTS] + [primitive]
    return count
