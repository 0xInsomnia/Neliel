"""Eye and brow design for the face stage (revision 14).

The shapes were measured on the private reference sheet (frontal head and
eye close-up) and are stored here only as numbers: an upturned almond
opening about three times wider than tall, a large round iris cut by both
lids, a bold upper lash line with a wing, a thin lower line.

Coordinates: each eye has a local frame (a, b) in metres, a along the line
through the corners toward the temple, b across it, on the frontal plane.
t = a / HALF_WIDTH runs from -1 (inner corner) to 1 (outer corner).
"""
import io
import numpy as np
from PIL import Image
from refine_mesh import smooth
from refine_subdivide import append, FLOAT, USHORT

HALF_WIDTH = .0198
TILT = np.radians(11)
UPPER, LOWER = .0049, .0084
IRIS_RADIUS = .0090
IRIS_CENTRE = np.array([-.0002, -.0009])
EYE_AT = .493              # eye centre from the midline, in H
BROW_INNER, BROW_OUTER = (.0165, .0200), (.0560, .0270)   # (|x|, height above the eye line)
BROW_ARCH = .0022
BROW_THICKNESS = (.0034, .0014)


def _upper(t):
    t = np.clip(t, -1, 1)
    return np.clip(1 - t * t, 0, 1) ** .9 * (1 - .45 * t) / 1.0507


def _lower(t):
    t = np.clip(t, -1, 1)
    return np.clip(1 - t * t, 0, 1) ** 1.1


def lash_thickness(t):
    """Thickness of the upper lash band above the lid line, metres."""
    t = np.asarray(t, float)
    return .0032 + .0021 * smooth(-.8, .5, t)


def lids(pose='rest'):
    """Upper and lower lid curves b(t) in metres for a named pose."""
    def upper(t):
        return UPPER * _upper(t)

    def lower(t):
        return -LOWER * _lower(t)

    if pose == 'blink':                    # relaxed closed eye: a shallow downward arc
        return (lambda t: .55 * lower(t)), (lambda t: .55 * lower(t))
    if pose == 'wink':                     # cheerful closed eye: an upward arc
        arc = lambda t: .0030 * np.clip(1 - np.clip(t, -1, 1) ** 2, 0, 1) - .0012
        return arc, arc
    if pose == 'smile':                    # lower lid pushed up by the cheek
        return (lambda t: .96 * upper(t)), (lambda t: lower(t) + .26 * (upper(t) - lower(t)))
    if pose == 'surprised':
        return (lambda t: 1.55 * upper(t) + .0010 * np.clip(1 - np.clip(t, -1, 1) ** 2, 0, 1)), \
               (lambda t: 1.08 * lower(t))
    return upper, lower


class EyeFrame:
    """Placement of one eye on the frontal plane. side = +1 or -1 (sign of x)."""

    def __init__(self, side, eye_y, height):
        self.side = side
        self.centre = np.array([EYE_AT * height, eye_y])
        self.cos, self.sin = np.cos(TILT), np.sin(TILT)

    def local(self, x, y):
        """Frontal (x, y) -> (a, b)."""
        dx, dy = self.side * np.asarray(x) - self.centre[0], np.asarray(y) - self.centre[1]
        return dx * self.cos + dy * self.sin, -dx * self.sin + dy * self.cos

    def frontal(self, a, b):
        """(a, b) -> frontal (x, y)."""
        a, b = np.asarray(a), np.asarray(b)
        return (self.side * (self.centre[0] + a * self.cos - b * self.sin),
                self.centre[1] + a * self.sin + b * self.cos)


def brow_line(ax):
    """Height of the brow centre line above the eye line, and its thickness, at |x|."""
    u = np.clip((np.asarray(ax, float) - BROW_INNER[0]) / (BROW_OUTER[0] - BROW_INNER[0]), 0, 1)
    height = BROW_INNER[1] + (BROW_OUTER[1] - BROW_INNER[1]) * u + BROW_ARCH * np.sin(np.pi * u) ** .9
    thickness = BROW_THICKNESS[0] + (BROW_THICKNESS[1] - BROW_THICKNESS[0]) * smooth(.15, 1, u)
    return height, thickness


# --------------------------------------------------------------------------
# Textures. Everything is drawn analytically (no image sources): each pixel
# is coloured from its position in the eye's local frame.

EYE_PIXELS = (1000, 516)          # one eyeball
UPPER_PIXELS = (1400, 330)        # upper lash strip, with the lid shadow under it
LOWER_PIXELS = (936, 94)
BROW_PIXELS = (720, 100)
EYE_MARGIN = .0015
UPPER_RANGE = (-1.12, 1.30)       # along the lid, in t
UPPER_ABOVE, SHADOW_BELOW = .0090, .0048
LOWER_RANGE = (-.80, 1.02)
LOWER_ABOVE, LOWER_BELOW = .0006, .0030
BROW_HALF = .0032

SCLERA = np.array([247, 243, 250.])
CORNER = np.array([236, 204, 206.])
IRIS_TOP, IRIS_MID, IRIS_LOW = np.array([58, 30, 126.]), np.array([120, 66, 198.]), np.array([198, 134, 240.])
IRIS_GLOW, IRIS_FIBRE = np.array([232, 176, 255.]), np.array([236, 196, 255.])
IRIS_RIM, PUPIL = np.array([42, 18, 84.]), np.array([30, 11, 58.])
LASH, LASH_LIGHT = np.array([26, 17, 28.]), np.array([86, 58, 64.])
LOWER_LASH = np.array([72, 40, 42.])
LID_SHADOW = np.array([70, 52, 112.])
BROW, BROW_LIGHT = np.array([78, 68, 94.]), np.array([112, 100, 130.])


def lerp(a, b, t):
    return a + (b - a) * np.asarray(t)[..., None]


def eye_extent():
    """(a half-range, lowest b, highest b) covered by the eyeball texture."""
    upper, lower = lids('surprised')
    t = np.linspace(-1, 1, 201)
    return HALF_WIDTH + EYE_MARGIN, float(lower(t).min()) - EYE_MARGIN, float(upper(t).max()) + EYE_MARGIN


def eyeball_image(side):
    """Sclera, iris, pupil and catchlights of one eye in its local frame.

    Columns run along a (inner corner on the left), rows from the top. The
    catchlights sit toward the viewer's left for both eyes, as on the sheet.
    """
    width, height = EYE_PIXELS
    reach, low, high = eye_extent()
    a = np.linspace(-reach, reach, width)[None, :]
    b = np.linspace(high, low, height)[:, None]
    t = a / HALF_WIDTH
    pixel = 2 * reach / width
    rgb = np.empty((height, width, 3))
    rgb[:] = SCLERA
    rgb = lerp(rgb, CORNER, .55 * smooth(-.72, -1.0, t + 0 * b) + .25 * smooth(.80, 1.0, t + 0 * b))

    da, db = (a - IRIS_CENTRE[0]) / IRIS_RADIUS, (b - IRIS_CENTRE[1]) / IRIS_RADIUS
    r = np.hypot(da, db)
    angle = np.arctan2(db, da)
    up = smooth(-1, 1, db)                                        # 0 at the bottom of the iris, 1 at the top
    body = lerp(np.broadcast_to(IRIS_LOW, rgb.shape), IRIS_MID, smooth(.05, .55, up))
    body = lerp(body, IRIS_TOP, smooth(.50, .98, up))
    body = body * (1 - .22 * smooth(.55, 1.0, r))[..., None]
    glow = np.exp(-((r - .60) / .24) ** 2) * smooth(.35, -.85, db)
    body = lerp(body, IRIS_GLOW, .60 * glow)
    fibre = (.5 + .5 * np.cos(angle * 44 + 2.6 * np.sin(angle * 7) + 1.3 * np.sin(angle * 17))) ** 5
    fibre = fibre * smooth(.40, .56, r) * (1 - smooth(.78, .92, r)) * (.35 + .65 * smooth(.6, -.6, db))
    body = lerp(body, IRIS_FIBRE, .30 * fibre)
    body = lerp(body, IRIS_RIM, .35 * np.exp(-((r - .47) / .07) ** 2))       # darker ring around the pupil
    pupil = 1 - smooth(.93, 1.07, np.hypot(da / .34, db / .43))
    inner = lerp(np.broadcast_to(PUPIL, rgb.shape), IRIS_TOP, .35 * smooth(.1, -.4, db) * np.ones_like(r))
    body = lerp(body, inner, pupil)
    body = lerp(body, IRIS_RIM, .92 * smooth(.87, .975, r))
    edge = pixel / IRIS_RADIUS * 1.5
    rgb = lerp(rgb, body, 1 - smooth(1 - edge, 1 + edge, r))

    def spot(ca, cb, ra, rb, turn):
        u, v = da - ca, db - cb
        c, s = np.cos(turn), np.sin(turn)
        d = np.hypot((u * c + v * s) / ra, (-u * s + v * c) / rb)
        return 1 - smooth(.86, 1.14, d)
    left = side                                                   # +a is the viewer's left for the +x eye
    rgb = lerp(rgb, np.array([255, 255, 255.]), spot(left * .30, .34, .215, .135, left * -.5))
    rgb = lerp(rgb, np.array([255, 255, 255.]), .95 * spot(left * .17, .47, .07, .05, 0))
    rgb = lerp(rgb, np.array([255, 250, 255.]), .92 * spot(-left * .74, .20, .125, .040, left * .12))
    rgb = lerp(rgb, np.array([250, 236, 255.]), .80 * spot(left * .60, -.42, .085, .045, left * .5))
    return np.clip(rgb, 0, 255).round().astype(np.uint8)


def upper_extent(t):
    """Depth of the lid shadow below the lid line: never more than the opening allows."""
    upper, lower = lids()
    return np.minimum(SHADOW_BELOW, .46 * (upper(t) - lower(t)))


def _spikes(s, v, top, items):
    """Lash clumps as pointed shapes rising from the band's top edge (metres)."""
    mask = np.zeros(np.broadcast(s, v).shape)
    for centre, height, half, lean in items:
        rise = np.clip((v - (top - .0006)) / (height + .0006), 0, 1)
        middle = centre * HALF_WIDTH + lean * height * rise ** 1.6
        wide = half * (1 - rise) ** 1.25
        mask = np.maximum(mask, smooth(-.00012, .00012, wide - np.abs(s - middle)) * (v > top - .0007) * (rise < 1))
    return mask


def upper_image():
    """Upper lash band with its wing, clumps and the lid shadow, as RGBA.

    Columns run along the lid from inner to outer; row 0 is the top. The lid
    line is the row at v = 0; below it lies only the translucent shadow.
    """
    width, height = UPPER_PIXELS
    tau = np.linspace(*UPPER_RANGE, width)[None, :]
    v = np.linspace(UPPER_ABOVE, -SHADOW_BELOW, height)[:, None]
    s = tau * HALF_WIDTH
    inside = np.clip(tau, -1, 1)
    thick = lash_thickness(inside) * smooth(UPPER_RANGE[0], -.80, tau) ** .8 \
        * (1 - smooth(.98, UPPER_RANGE[1] - .02, tau)) ** .9
    band = smooth(-.00013, .00013, v + .0004) * smooth(-.00013, .00013, thick - v)
    clumps = _spikes(s, v, thick, [(-.34, .0009, .0012, .9), (.06, .0014, .0014, 1.0), (.38, .0020, .0016, 1.1),
                                   (.66, .0025, .0017, 1.2), (.90, .0028, .0017, 1.3)])
    lash = np.maximum(band, clumps)
    streak = np.exp(-((v - .46 * thick) / .00030) ** 2) * smooth(-.6, -.2, tau) * (1 - smooth(.7, 1.05, tau))
    colour = lerp(np.broadcast_to(LASH, (height, width, 3)), LASH_LIGHT, .55 * streak * band)
    shadow = .70 * smooth(-1.0, .0, v / SHADOW_BELOW) ** 1.3 * (v < 0) * (np.abs(tau) < 1.0) \
        * smooth(1.0, .86, np.abs(tau) + 0 * v)
    alpha = np.maximum(lash, shadow * (1 - lash))
    colour = lerp(colour, LID_SHADOW, (1 - lash) * (shadow > 0))
    return np.dstack([np.clip(colour, 0, 255), 255 * np.clip(alpha, 0, 1)]).round().astype(np.uint8)


def lower_image():
    width, height = LOWER_PIXELS
    tau = np.linspace(*LOWER_RANGE, width)[None, :]
    v = np.linspace(LOWER_ABOVE, -LOWER_BELOW, height)[:, None]
    s = tau * HALF_WIDTH
    weight = smooth(LOWER_RANGE[0], -.25, tau) * (1 - smooth(.96, LOWER_RANGE[1], tau))
    half = (.00030 + .00022 * smooth(-.2, .9, tau)) * weight
    line = smooth(-.00012, .00012, half - np.abs(v + .00022)) * (weight > 0)
    lashes = np.zeros_like(line)
    for centre, length, lean in ((.02, .0010, .25), (.22, .0012, .32), (.42, .0015, .40), (.60, .0016, .46),
                                 (.76, .0016, .52), (.90, .0013, .60)):
        drop = np.clip((-.0004 - v) / length, 0, 1)
        middle = centre * HALF_WIDTH + lean * length * drop
        lashes = np.maximum(lashes, smooth(-.0001, .0001, .00030 * (1 - drop) ** 1.2 - np.abs(s - middle))
                            * (v < -.0003) * (drop < 1))
    alpha = np.maximum(.95 * line, .90 * lashes)
    colour = np.broadcast_to(LOWER_LASH, (height, width, 3))
    return np.dstack([colour, 255 * np.clip(alpha, 0, 1)]).round().astype(np.uint8)


def brow_image():
    width, height = BROW_PIXELS
    u = np.linspace(0, 1, width)[None, :]
    v = np.linspace(BROW_HALF, -BROW_HALF, height)[:, None]
    thickness = BROW_THICKNESS[0] + (BROW_THICKNESS[1] - BROW_THICKNESS[0]) * smooth(.15, 1, u)
    thickness = thickness * smooth(-.02, .09, u) ** .6 * (1 - smooth(.86, 1.0, u)) ** .7
    alpha = .96 * smooth(-.00030, .00030, thickness / 2 - np.abs(v))
    colour = lerp(np.broadcast_to(BROW, (height, width, 3)), BROW_LIGHT, .45 * smooth(0, 1, v / (thickness / 2 + 1e-6)))
    return np.dstack([np.clip(colour, 0, 255), 255 * alpha]).round().astype(np.uint8)


# --------------------------------------------------------------------------
# Geometry. Thin layers lying just in front of the skin; each is rebuilt for
# every expression from the same curves, so the lids clip the eye exactly.

EYE_COLUMNS = 41
WING_ANGLE = np.radians(8)
OFFSET = {'eye': .0007, 'lower': .0010, 'upper': .0013, 'brow': .0006}
EYE_MATERIAL, LASH_MATERIAL = 'Sclera e iride', 'Ciglia e sopracciglia'
STOCK_PARTS = ('Sclera', 'Iride viola', 'Riflesso occhi', 'Contorno occhi', 'Ciglia', 'Sopracciglia')


def _quads(rows, columns, flip):
    index = np.arange(rows * columns).reshape(rows, columns)
    a, b, c, d = index[:-1, :-1].ravel(), index[:-1, 1:].ravel(), index[1:, :-1].ravel(), index[1:, 1:].ravel()
    triangles = np.concatenate([np.stack([a, c, b], 1), np.stack([b, c, d], 1)])
    return triangles[:, ::-1] if flip else triangles


def eyeball_layer(pose):
    """Local positions and texture coordinates of the eyeball grid for a pose.

    The rows are the lid curves of the still expressions plus a few between
    them, so clamping to the lids of any of those poses cuts the eye along a
    row and leaves no stretched cells.
    """
    tau = np.linspace(-1, 1, EYE_COLUMNS)
    (up, lo), (up_s, lo_s), (up_p, lo_p) = lids(), lids('smile'), lids('surprised')
    between = [lo_s(tau) + k / 5 * (up_s(tau) - lo_s(tau)) for k in range(1, 5)]
    design = np.stack([lo_p(tau), lo(tau), lo_s(tau), *between, up_s(tau), up(tau), up_p(tau)])
    upper, lower = lids(pose)
    b = np.clip(design, lower(tau)[None], np.maximum(upper(tau), lower(tau))[None])
    a = np.broadcast_to(tau * HALF_WIDTH, design.shape)
    reach, low, high = eye_extent()
    uv = np.stack([(a + reach) / (2 * reach), (high - design) / (high - low)], -1)
    return a.ravel(), b.ravel(), uv.reshape(-1, 2), design.shape


def _lid_path(tau, curve):
    """Point on a lid curve, continued past the corners (wing, inner hook)."""
    a = tau * HALF_WIDTH
    b = curve(tau)
    past = np.maximum(tau - 1, 0) * HALF_WIDTH
    before = np.minimum(tau + 1, 0) * HALF_WIDTH
    a = np.where(tau < -1, -HALF_WIDTH + .75 * before, a)
    b = b + past * np.tan(WING_ANGLE) + .75 * before
    return a, b


def _levels(parts):
    """Stack rows and their texture v from (curve, v) pairs."""
    rows = np.stack([row for row, _ in parts])
    v = np.array([value for _, value in parts])[:, None]
    return rows, np.broadcast_to(v, rows.shape)


def upper_layer(pose, columns=52):
    """Lash band and lid shadow. Rows are close together so the strip hugs the skin."""
    tau = np.linspace(*UPPER_RANGE, columns)
    upper, lower = lids(pose)
    a, b = _lid_path(tau, upper)
    room = np.where(np.abs(tau) < 1, np.minimum(upper_extent(tau), np.maximum(upper(tau) - lower(tau), 0)), 0)
    lid_row = UPPER_ABOVE / (UPPER_ABOVE + SHADOW_BELOW)
    parts = [(b - k * room, lid_row + k * (1 - lid_row)) for k in (1, .75, .5, .25)]
    parts += [(b + k * UPPER_ABOVE, lid_row * (1 - k)) for k in (0, .15, .3, .45, .6, .8, 1)]
    rows, v = _levels(parts)
    u = (tau - UPPER_RANGE[0]) / (UPPER_RANGE[1] - UPPER_RANGE[0])
    uv = np.stack([np.broadcast_to(u, rows.shape), v], -1)
    return np.broadcast_to(a, rows.shape).ravel(), rows.ravel(), uv.reshape(-1, 2), rows.shape


def lower_layer(pose, columns=30):
    tau = np.linspace(*LOWER_RANGE, columns)
    _, lower = lids(pose)
    a, b = _lid_path(tau, lower)
    total = LOWER_ABOVE + LOWER_BELOW
    rows, v = _levels([(b - LOWER_BELOW, 1), (b - .5 * LOWER_BELOW, (LOWER_ABOVE + .5 * LOWER_BELOW) / total),
                       (b, LOWER_ABOVE / total), (b + LOWER_ABOVE, 0)])
    u = (tau - LOWER_RANGE[0]) / (LOWER_RANGE[1] - LOWER_RANGE[0])
    uv = np.stack([np.broadcast_to(u, rows.shape), v], -1)
    return np.broadcast_to(a, rows.shape).ravel(), rows.ravel(), uv.reshape(-1, 2), rows.shape


def brow_layer(eye_y, columns=36):
    """Frontal |x|, y and texture coordinates of one brow."""
    ax = np.linspace(BROW_INNER[0] - .002, BROW_OUTER[0] + .002, columns)
    u = np.linspace(0, 1, columns)
    height, _ = brow_line(np.clip(ax, BROW_INNER[0], BROW_OUTER[0]))
    slope = (BROW_OUTER[1] - BROW_INNER[1]) / (BROW_OUTER[0] - BROW_INNER[0])
    middle = eye_y + height + slope * (ax - np.clip(ax, BROW_INNER[0], BROW_OUTER[0]))
    rows, v = _levels([(middle - BROW_HALF, 1), (middle - .33 * BROW_HALF, .665), (middle + .33 * BROW_HALF, .335),
                       (middle + BROW_HALF, 0)])
    uv = np.stack([np.broadcast_to(u, rows.shape), v], -1)
    return np.broadcast_to(ax, rows.shape).ravel(), rows.ravel(), uv.reshape(-1, 2), rows.shape


def _encode(asset, picture, kind):
    doc = asset.d
    encoded = io.BytesIO()
    if kind == 'image/png':
        picture.save(encoded, format='PNG', optimize=True)
    else:
        picture.save(encoded, format='JPEG', quality=93, subsampling=0)
    data = encoded.getvalue()
    asset.b += b'\0' * (-len(asset.b) % 4)
    doc['bufferViews'].append({'buffer': 0, 'byteOffset': len(asset.b), 'byteLength': len(data)})
    asset.b += data
    asset.b += b'\0' * (-len(asset.b) % 4)
    doc['buffers'][0]['byteLength'] = len(asset.b)
    doc['images'].append({'mimeType': kind, 'bufferView': len(doc['bufferViews']) - 1})
    texture = {'source': len(doc['images']) - 1}
    if doc.get('samplers'):
        texture['sampler'] = 0
    doc['textures'].append(texture)
    return len(doc['textures']) - 1


def _material(doc, name, texture, mode):
    doc['materials'].append({'name': name, 'doubleSided': True, 'alphaMode': mode,
                             'pbrMetallicRoughness': {'baseColorTexture': {'index': texture}, 'metallicFactor': 0,
                                                      'roughnessFactor': .88, 'baseColorFactor': [1, 1, 1, 1]}})
    return len(doc['materials']) - 1


def build(asset, mesh, face, depth, skin_points, skin_deltas, head_joint):
    """Add the drawn eyes and brows to the face mesh and drop the stock parts.

    depth(x, y) is the frontal depth of the finished skin; skin_points and
    skin_deltas let the brows ride on the skin's own expression shapes.
    """
    doc = asset.d
    names = mesh['extras']['targetNames']

    # Texture sheets: the two eyeballs stacked, and the translucent strips.
    gap = 8
    eyes_sheet = Image.new('RGB', (EYE_PIXELS[0], 2 * EYE_PIXELS[1] + gap), (247, 243, 250))
    eye_rows = {1: 0, -1: EYE_PIXELS[1] + gap}
    for side, top in eye_rows.items():
        eyes_sheet.paste(Image.fromarray(eyeball_image(side)), (0, top))
    parts = {'upper': upper_image(), 'lower': lower_image(), 'brow': brow_image()}
    sheet_width = max(image.shape[1] for image in parts.values()) + 2 * gap
    sheet_height = sum(image.shape[0] for image in parts.values()) + 4 * gap
    lash_sheet = np.zeros((sheet_height, sheet_width, 4), dtype=np.uint8)
    lash_sheet[..., :3] = LASH.astype(np.uint8)
    place, top = {}, gap
    for key, image in parts.items():
        lash_sheet[top:top + image.shape[0], gap:gap + image.shape[1]] = image
        place[key] = (gap, top, image.shape[1], image.shape[0])
        top += image.shape[0] + gap
    eye_material = _material(doc, EYE_MATERIAL, _encode(asset, eyes_sheet, 'image/jpeg'), 'OPAQUE')
    lash_material = _material(doc, LASH_MATERIAL, _encode(asset, Image.fromarray(lash_sheet), 'image/png'), 'BLEND')

    def sheet_uv(uv, key):
        x, y, w, h = place[key]
        return np.stack([(x + uv[:, 0] * (w - 1) + .5) / sheet_width, (y + uv[:, 1] * (h - 1) + .5) / sheet_height], 1)

    def on_skin(x, y, offset):
        return np.stack([x, y, depth(x, y) - offset], 1)

    # Brows follow the nearest skin vertices in every expression.
    front = skin_points[:, 2] < -.02

    def ride(points):
        distance = np.hypot(points[:, None, 0] - skin_points[None, front, 0], points[:, None, 1] - skin_points[None, front, 1])
        weight = np.exp(-(distance / .006) ** 2) + 1e-12
        weight /= weight.sum(1, keepdims=True)
        return [weight @ delta[front] for delta in skin_deltas]

    solid = {'points': [], 'uv': [], 'triangles': [], 'targets': [[] for _ in names]}
    sheer = {'points': [], 'uv': [], 'triangles': [], 'targets': [[] for _ in names]}

    def add(group, points, uv, shape, flip, deltas):
        offset = sum(len(p) for p in group['points'])
        group['points'].append(points)
        group['uv'].append(uv)
        group['triangles'].append(_quads(*shape, flip) + offset)
        for store, delta in zip(group['targets'], deltas):
            store.append(delta)

    for side in (1, -1):
        frame = EyeFrame(side, face.eye_y, face.height)
        flip = side < 0

        def posed(layer, pose, offset):
            a, b, uv, shape = layer(pose)
            return on_skin(*frame.frontal(a, b), offset), uv, shape

        def pose_of(name):
            return ('wink' if side < 0 else 'rest') if name == 'wink' else name

        base, uv, shape = posed(eyeball_layer, 'rest', OFFSET['eye'])
        uv = np.stack([(uv[:, 0] * (EYE_PIXELS[0] - 1) + .5) / EYE_PIXELS[0],
                       (eye_rows[side] + uv[:, 1] * (EYE_PIXELS[1] - 1) + .5) / eyes_sheet.height], 1)
        add(solid, base, uv, shape, flip, [posed(eyeball_layer, pose_of(n), OFFSET['eye'])[0] - base for n in names])
        for key, layer in (('lower', lower_layer), ('upper', upper_layer)):
            base, uv, shape = posed(layer, 'rest', OFFSET[key])
            add(sheer, base, sheet_uv(uv, key), shape, flip,
                [posed(layer, pose_of(n), OFFSET[key])[0] - base for n in names])
        ax, y, uv, shape = brow_layer(face.eye_y)
        base = on_skin(side * ax, y, OFFSET['brow'])
        add(sheer, base, sheet_uv(uv, 'brow'), shape, flip, ride(base))

    added = []
    for group, material in ((solid, eye_material), (sheer, lash_material)):
        points = np.concatenate(group['points'])
        count = len(points)
        joints = np.zeros((count, 4))
        joints[:, 0] = head_joint
        weights = np.zeros((count, 4))
        weights[:, 0] = 1
        added.append({
            'attributes': {
                'POSITION': append(asset, points, 'VEC3', FLOAT, bounds=True, target=34962),
                'NORMAL': append(asset, np.tile([0, 0, -1.0], (count, 1)), 'VEC3', FLOAT, target=34962),
                'TEXCOORD_0': append(asset, np.concatenate(group['uv']), 'VEC2', FLOAT, target=34962),
                'JOINTS_0': append(asset, joints, 'VEC4', USHORT, target=34962),
                'WEIGHTS_0': append(asset, weights, 'VEC4', FLOAT, target=34962),
            },
            'indices': append(asset, np.concatenate(group['triangles']).reshape(-1, 1), 'SCALAR', USHORT, target=34963),
            'material': material,
            'targets': [{'POSITION': append(asset, np.concatenate(store), 'VEC3', FLOAT, bounds=True, target=34962)}
                        for store in group['targets']],
        })
    mesh['primitives'] = [p for p in mesh['primitives']
                          if doc['materials'][p['material']]['name'] not in STOCK_PARTS] + added
    return sum(len(np.concatenate(g['triangles'])) for g in (solid, sheer))
