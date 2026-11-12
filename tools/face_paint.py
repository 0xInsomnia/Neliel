"""Skin texture of the face, painted from scratch (revision 14).

Every texel is coloured from its 3D rest position on the final skin mesh, so
the paint sits where the geometry is: lips on the mouth opening, the nose
mark on the nose tip, lid shading around the drawn eyes. Only the ears keep
the shading of the stock texture, re-toned to the new skin colour.

The colours and shapes follow the private reference sheet: warm tan skin,
soft pink cheeks, rose lips with a dark parting line, a light point on the
nose tip.
"""
import io
import numpy as np
from PIL import Image
from refine_mesh import smooth
from refine_identity import SKIN_TONE, image_of
from face_mesh import uv_islands
from face_eyes import HALF_WIDTH, EyeFrame, lids, lash_thickness

SIZE = 2048
BLUSH = np.array([236, 120, 116])
LIP_UPPER = np.array([172, 84, 90])
LIP_LOWER = np.array([204, 100, 108])
LIP_LIGHT = np.array([244, 170, 168])
LIP_LINE = np.array([92, 36, 44])
NOSE_LIGHT = np.array([255, 234, 216])
NOSE_SHADE = np.array([150, 82, 70])
CREASE = np.array([128, 68, 62])


def texel_map(points, uv, triangles, labels, size):
    """Rest position, coverage and island label of every texel."""
    position = np.zeros((size, size, 3), dtype=np.float32)
    island = np.full((size, size), -1, dtype=np.int32)
    scaled = uv * size
    for triangle, label in zip(triangles, labels):
        p = scaled[triangle]
        low = np.maximum(np.floor(p.min(0)).astype(int) - 1, 0)
        high = np.minimum(np.ceil(p.max(0)).astype(int) + 1, size - 1)
        det = (p[1, 1] - p[2, 1]) * (p[0, 0] - p[2, 0]) + (p[2, 0] - p[1, 0]) * (p[0, 1] - p[2, 1])
        if abs(det) < 1e-9:
            continue
        x, y = np.meshgrid(np.arange(low[0], high[0] + 1) + .5, np.arange(low[1], high[1] + 1) + .5)
        a = ((p[1, 1] - p[2, 1]) * (x - p[2, 0]) + (p[2, 0] - p[1, 0]) * (y - p[2, 1])) / det
        b = ((p[2, 1] - p[0, 1]) * (x - p[2, 0]) + (p[0, 0] - p[2, 0]) * (y - p[2, 1])) / det
        weights = np.stack([a, b, 1 - a - b], -1)
        # One texel of slack so neighbouring triangles leave no seams.
        inside = weights.min(-1) >= -.6 / max(abs(det) ** .5, 1e-6)
        region = np.s_[low[1]:high[1] + 1, low[0]:high[0] + 1]
        strict = weights.min(-1) >= 0
        fresh = inside & ((island[region] < 0) | strict)
        position[region][fresh] = (weights @ points[triangle])[fresh]
        island[region][fresh] = label
    return position, island


def spread(rgb, covered, steps=24):
    """Carry colours outward over uncovered texels so filtering finds no dark fringe."""
    rgb, known = rgb.copy(), covered.copy()
    for _ in range(steps):
        total = np.zeros_like(rgb)
        weight = np.zeros(known.shape, dtype=np.float32)
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            total += np.roll(np.where(known[..., None], rgb, 0), (dy, dx), axis=(0, 1))
            weight += np.roll(known, (dy, dx), axis=(0, 1))
        grow = ~known & (weight > 0)
        rgb[grow] = total[grow] / weight[grow][:, None]
        known |= grow
    return rgb


class Painter:
    def __init__(self, x, y, z, face):
        self.x, self.y, self.z = x, y, z
        self.ax = np.abs(x)
        self.rgb = np.tile(SKIN_TONE.astype(np.float32), (*x.shape, 1))
        self.front = (1 - smooth(-.035, -.01, z)).astype(np.float32)
        self.face = face

    def mix(self, colour, alpha):
        alpha = np.clip(alpha, 0, 1)[..., None].astype(np.float32)
        self.rgb += (np.asarray(colour, np.float32) - self.rgb) * alpha

    def shade(self, factor, alpha):
        alpha = np.clip(alpha, 0, 1)[..., None].astype(np.float32)
        self.rgb *= 1 + (np.asarray(factor, np.float32) - 1) * alpha

    def blob(self, cx, cy, rx, ry, angle=0.0, x=None):
        dx, dy = (self.x if x is None else x) - cx, self.y - cy
        c, s = np.cos(angle), np.sin(angle)
        u, v = dx * c + dy * s, -dx * s + dy * c
        return np.exp(-(u / rx) ** 2 - (v / ry) ** 2)


def paint_form(p):
    """Soft shading that gives the face its roundness even in full light."""
    face = p.face
    reach = np.maximum(face.half_width(p.y), .012)
    side = smooth(.62, 1.03, p.ax / reach) * (1 - smooth(.01, .03, p.z))
    p.shade([.89, .79, .80], .95 * side)
    under_hair = smooth(face.eye_y + .030, face.eye_y + .062, p.y) * p.front
    p.shade([.90, .80, .83], .60 * under_hair)
    jaw = smooth(face.chin_y + .010, face.chin_y - .002, p.y) * (1 - smooth(.0, .03, p.z))
    p.shade([.94, .86, .86], .6 * jaw)


def paint_cheeks(p):
    face = p.face
    for side in (-1, 1):
        blush = p.blob(side * .0400, face.eye_y - .0215, .0215, .0098, side * .22)
        p.mix(BLUSH, .52 * blush * p.front)


def paint_nose(p, nose_y):
    light = p.blob(0, nose_y + .0006, .0012, .0017)
    under = p.blob(0, nose_y - .0052, .0026, .0009)
    p.shade([.90, .78, .76], .55 * under * p.front)
    ridge = p.blob(.0031, nose_y + .0022, .0008, .0034, .22)
    p.shade([.90, .80, .80], .30 * ridge * p.front)
    for side in (-1, 1):
        nostril = p.blob(side * .0033, nose_y - .0046, .0011, .0006, -side * .45)
        p.mix(NOSE_SHADE, .44 * nostril * p.front)
    p.mix(NOSE_LIGHT, .85 * light * p.front)


def paint_mouth(p, slit, corner):
    """Lips around the mouth opening. slit(x) is the height of the parting line."""
    x, ax = p.x, p.ax
    line = slit(x)
    inside = np.clip(1 - (ax / corner) ** 2, 0, 1)
    bow = 1 + .22 * np.exp(-((ax - .0040) / .0026) ** 2) - .32 * np.exp(-(x / .0020) ** 2)
    upper = .0024 * inside ** .55 * bow
    lower = .0041 * np.clip(1 - (ax / (.84 * corner)) ** 2, 0, 1) ** .8
    soft = .00035
    above = smooth(-soft, soft, p.y - line) * (1 - smooth(upper - soft, upper + 2 * soft, p.y - line)) \
        * (1 - smooth(corner - .0010, corner, ax))
    below = smooth(-soft, soft, line - p.y) * (1 - smooth(lower - 2 * soft, lower + 3 * soft, line - p.y)) \
        * (1 - smooth(.84 * corner - .0012, .84 * corner, ax))
    under = np.exp(-(x / .0078) ** 2 - ((p.y - (line - lower - .0019)) / .0015) ** 2)
    p.shade([.92, .82, .82], .55 * under * p.front)
    p.mix(LIP_UPPER, .44 * above * p.front)
    p.mix(LIP_LOWER, .56 * below * p.front)
    light = np.exp(-((x - .0008) / .0034) ** 2 - ((p.y - (line - .0019)) / .0008) ** 2)
    p.mix(LIP_LIGHT, .40 * light * p.front)
    # The parting line runs a little past the corners and is heavier near them.
    reach = 1 - smooth(corner - .0002, corner + .0009, ax)
    width = .00040 + .00018 * np.exp(-((ax - (corner - .0012)) / .0022) ** 2)
    stroke = np.exp(-((p.y - line) / width) ** 2)
    p.mix(LIP_LINE, .92 * stroke * reach * p.front)


def paint_eyes(p):
    """Skin around the eyes: lid shading, crease and a faint lower shadow."""
    face = p.face
    upper, lower = lids()
    for side in (-1, 1):
        frame = EyeFrame(side, face.eye_y, face.height)
        near = (np.sign(p.x) == side) & (np.abs(p.y - face.eye_y) < .03)
        a, b = frame.local(p.x, p.y)
        t = a / HALF_WIDTH
        socket = np.exp(-(a / .027) ** 2 - ((b - .0045) / .0125) ** 2)
        p.shade([.95, .88, .89], .55 * socket * near * p.front)
        top = upper(t) + lash_thickness(t)
        fold = top + .0021 * np.clip(1 - np.clip(t, -1, 1) ** 2, 0, 1) ** .5 + .0004
        span = smooth(-.86, -.55, t) * (1 - smooth(.62, .92, t))
        lid = smooth(-.0004, .0004, b - upper(t)) * (1 - smooth(-.0003, .0005, b - fold)) * (np.abs(t) < 1.05)
        p.shade([.90, .78, .80], .58 * lid * near * p.front)
        outer = np.exp(-((a - 1.02 * HALF_WIDTH) / .0035) ** 2 - ((b - .0005) / .0030) ** 2)
        p.shade([.88, .74, .76], .45 * outer * near * p.front)
        crease = np.exp(-((b - fold) / .00030) ** 2) * span
        p.mix(CREASE, .78 * crease * near * p.front)
        below = np.exp(-((b - (lower(t) - .0012)) / .0011) ** 2) * smooth(-.7, -.3, t) * (1 - smooth(.8, 1.0, t))
        p.shade([.92, .82, .82], .40 * below * near * p.front)


def mouth_line(points):
    """Even quartic through the mouth opening: height of the parting line at x."""
    x, y = points[:, 0], points[:, 1]
    basis = np.stack([np.ones_like(x), x ** 2, x ** 4], 1)
    c = np.linalg.lstsq(basis, y, rcond=None)[0]
    corner = float(np.abs(x).max())

    def slit(v):
        v = np.clip(np.abs(v), 0, corner + .002)
        return c[0] + c[1] * v ** 2 + c[2] * v ** 4
    return slit, corner


def paint(asset, part, face, mouth, nose_y):
    """Replace the face texture. `face` holds the landmarks, `mouth` the opening's points."""
    doc = asset.d
    material = doc['materials'][part['material']]
    image, stock = image_of(asset, material)
    points = asset.array(part['attributes']['POSITION']).astype(np.float64)
    uv = asset.array(part['attributes']['TEXCOORD_0']).astype(np.float64)
    triangles = asset.array(part['indices']).reshape(-1, 3).astype(int)
    label = uv_islands(triangles, len(points))
    values, counts = np.unique(label, return_counts=True)
    front_label = values[np.argmax(counts)]
    position, island = texel_map(points, uv, triangles, label, SIZE)
    covered = island >= 0
    main = island == front_label

    painter = Painter(position[..., 0], position[..., 1], position[..., 2], face)
    paint_form(painter)
    paint_cheeks(painter)
    paint_eyes(painter)
    paint_nose(painter, nose_y)
    slit, corner = mouth_line(mouth)
    paint_mouth(painter, slit, corner)
    rgb = painter.rgb

    # Ears: stock shading, re-toned to the new skin colour.
    old = np.asarray(stock.convert('RGB').resize((SIZE, SIZE), Image.BICUBIC), dtype=np.float32)
    old_skin = np.median(np.asarray(stock.convert('RGB'), dtype=np.float32).reshape(-1, 3), axis=0)
    ears = covered & ~main
    relative = np.clip(old / old_skin, .55, 1.12) ** 1.6
    rgb[ears] = (SKIN_TONE * relative)[ears]

    rgb = spread(np.where(covered[..., None], rgb, 0), covered)
    rgb[~np.isfinite(rgb)] = 0
    picture = Image.fromarray(np.clip(rgb, 0, 255).round().astype(np.uint8))
    encoded = io.BytesIO()
    picture.save(encoded, format='JPEG', quality=92, subsampling=0)
    data = encoded.getvalue()
    asset.b += b'\0' * (-len(asset.b) % 4)
    doc['bufferViews'].append({'buffer': 0, 'byteOffset': len(asset.b), 'byteLength': len(data)})
    asset.b += data
    asset.b += b'\0' * (-len(asset.b) % 4)
    doc['buffers'][0]['byteLength'] = len(asset.b)
    image['bufferView'] = len(doc['bufferViews']) - 1
    image['mimeType'] = 'image/jpeg'
    material['pbrMetallicRoughness']['baseColorFactor'] = [1, 1, 1, 1]
    return picture
