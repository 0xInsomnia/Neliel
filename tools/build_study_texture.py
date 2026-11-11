"""Build the body texture for the studio's proportion-study mode.

The shipped body texture has the provisional outfit painted over the skin.
This replaces every painted garment with skin and paints a plain two-piece
swimsuit, placed from the 3D rest position of each texel so it follows the
current body revision. The skirt, sleeves and boots are separate geometry and
are hidden by the studio at run time.

Usage: python3 tools/build_study_texture.py assets/neliel-refined.glb assets/body-study.png
Requires NumPy and Pillow.
"""
import io
import sys
import numpy as np
from PIL import Image, ImageFilter
from refine_mesh import Asset, smooth
from refine_body import world_positions

BODY_MATERIAL = 'Pelle e tessuto'
SUIT = np.array([52, 36, 86])
TRIM = np.array([168, 132, 232])


def body_primitive(asset):
    doc = asset.d
    for mesh in doc['meshes']:
        for primitive in mesh['primitives']:
            if doc['materials'][primitive['material']]['name'] == BODY_MATERIAL:
                return primitive
    raise ValueError('Body material not found')


def texel_positions(asset, primitive, size):
    """Rest-pose 3D position for every texel covered by the body UV layout."""
    attrs = primitive['attributes']
    points = asset.array(attrs['POSITION']).astype(np.float64)
    uv = asset.array(attrs['TEXCOORD_0']).astype(np.float64) * size
    position = np.zeros((size, size, 3))
    covered = np.zeros((size, size), dtype=bool)
    for triangle in asset.array(primitive['indices']).reshape(-1, 3):
        p = uv[triangle]
        low = np.maximum(np.floor(p.min(0)).astype(int) - 1, 0)
        high = np.minimum(np.ceil(p.max(0)).astype(int) + 1, size - 1)
        det = (p[1, 1] - p[2, 1]) * (p[0, 0] - p[2, 0]) + (p[2, 0] - p[1, 0]) * (p[0, 1] - p[2, 1])
        if abs(det) < 1e-9:
            continue
        x, y = np.meshgrid(np.arange(low[0], high[0] + 1) + .5, np.arange(low[1], high[1] + 1) + .5)
        a = ((p[1, 1] - p[2, 1]) * (x - p[2, 0]) + (p[2, 0] - p[1, 0]) * (y - p[2, 1])) / det
        b = ((p[2, 1] - p[0, 1]) * (x - p[2, 0]) + (p[0, 0] - p[2, 0]) * (y - p[2, 1])) / det
        weights = np.stack([a, b, 1 - a - b], -1)
        inside = weights.min(-1) >= -1e-6
        region = np.s_[low[1]:high[1] + 1, low[0]:high[0] + 1]
        fresh = inside & ~covered[region]
        position[region][fresh] = (weights @ points[triangle])[fresh]
        covered[region] |= inside
    return position, covered


def torso_island(asset, primitive, size):
    """Texture-space bounds of the UV island that holds the trunk."""
    triangles = asset.array(primitive['indices']).reshape(-1, 3).astype(int)
    parent = np.arange(int(triangles.max()) + 1)

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for triangle in triangles:
        root = find(triangle[0])
        for vertex in triangle[1:]:
            parent[find(vertex)] = root
    vertices = np.unique(triangles)
    roots = np.array([find(i) for i in vertices])
    largest = np.bincount(roots).argmax()
    uv = asset.array(primitive['attributes']['TEXCOORD_0'])[vertices[roots == largest]] * size
    low, high = np.floor(uv.min(0)).astype(int) - 4, np.ceil(uv.max(0)).astype(int) + 4
    return low[0], low[1], high[0], high[1]


def remove_garments(rgb):
    """Replace painted fabric with skin grown inward from the surrounding skin."""
    r, g, b = [rgb[..., i].astype(int) for i in range(3)]
    skin = (r > 160) & (r - b > 18) & (r >= g)
    # A flat tone avoids dragging nail and knuckle detail from neighbouring
    # UV islands into the limbs; the toon shader supplies the shading.
    tone = np.median(rgb[skin], axis=0)
    replace = ~np.asarray(Image.fromarray(skin).filter(ImageFilter.MinFilter(7)))
    soft = np.asarray(Image.fromarray((replace * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(5))) / 255
    soft = np.maximum(soft, replace)[..., None]
    return (rgb * (1 - soft) + tone * soft).round().astype(np.uint8)


def swimsuit(position, covered, torso, crotch, bust_y):
    """Coverage (0..1) and trim mask of a plain two-piece, in rest-pose space."""
    x, y, z = np.moveaxis(position, -1, 0)
    ax = np.abs(x)
    trunk = covered & (ax < .20)

    # Briefs: the torso UV island ends at the leg crease, so everything below
    # the waistband belongs to them; on the legs only the gusset is painted.
    waist = crotch + .130
    gusset = crotch - .01 + .8 * np.maximum(ax - .02, 0)
    briefs = trunk & (y < waist) & ((torso & (y > crotch)) | (y > gusset))

    # Top: two cups joined in front, a band around the back and neck straps.
    under = bust_y - .058
    cup = ((ax - .075) / .066) ** 2 + ((y - bust_y) / .060) ** 2 < 1
    band = (np.abs(y - (under + .012)) < .016)
    strap = (np.abs(ax - (.072 - .35 * (y - bust_y))) < .008) & (y > bust_y) & (y < bust_y + .12) & (z < .0)
    top = trunk & (ax < .17) & ((cup & (z < .01)) | band | strap)
    return briefs | top


def skin_details(rgb, position, covered, joint):
    """Painted finish: navel, abdomen lines, collarbones, knees, warm joints."""
    x, y, z = np.moveaxis(position, -1, 0)
    ax = np.abs(x)
    out = rgb.astype(np.float64)
    shade = np.zeros(x.shape)
    warm = np.zeros(x.shape)

    def g(v, centre, sigma):
        return np.exp(-((v - centre) / sigma) ** 2)

    navel = joint['J_Bip_C_Spine'][1] + .022
    under_bust = joint['J_Sec_L_Bust2'][1] - .075
    belly = 1 - smooth(-.075, -.045, z)                       # front of the abdomen
    span = smooth(navel + .015, navel + .04, y) * (1 - smooth(under_bust - .03, under_bust, y))
    shade += .62 * g(x, 0, .0055) * g(y, navel, .010) * belly
    shade += .20 * g(x, 0, .0045) * span * belly
    side_line = .046 + 1.4 * (y - (navel + .06)) ** 2
    shade += .13 * g(ax, side_line, .0065) * smooth(navel - .03, navel + .01, y) \
        * (1 - smooth(under_bust - .04, under_bust - .01, y)) * belly
    # Hip crease toward the briefs.
    crease = joint['J_Bip_L_UpperLeg'][1] + .085 - .55 * (ax - .06)
    shade += .12 * g(y, crease, .006) * smooth(.045, .07, ax) * (1 - smooth(.115, .135, ax)) * belly

    collar = joint['J_Bip_C_Neck'][1] - .052 + .16 * np.maximum(ax - .02, 0)
    chest = (1 - smooth(-.045, -.02, z)) * smooth(.012, .03, ax) * (1 - smooth(.115, .145, ax))
    shade += .26 * g(y, collar - .005, .0045) * chest
    shade -= .10 * g(y, collar + .004, .0045) * chest
    shade += .22 * g(x, 0, .010) * g(y, joint['J_Bip_C_Neck'][1] - .060, .008) * (1 - smooth(-.045, -.02, z))

    for side in (-1, 1):
        knee = joint['J_Bip_L_LowerLeg']
        cx = side * abs(knee[0])
        front = 1 - smooth(knee[2] - .03, knee[2] - .005, z)
        shade += .16 * g(x, cx, .026) * g(y, knee[1] - .022, .007) * front
        warm += .30 * g(x, cx, .030) * g(y, knee[1] + .004, .022) * front
        shoulder = joint['J_Bip_L_UpperArm']
        warm += .22 * g(x, side * (abs(shoulder[0]) + .035), .035) * g(y, shoulder[1] + .02, .03)

    shade = np.clip(shade, -.25, .8)[..., None] * covered[..., None]
    dark = out * [.72, .56, .55]
    light = np.minimum(out * 1.10, 255)
    out = np.where(shade >= 0, out + (dark - out) * shade, out + (light - out) * -shade / .25 * .25 * 4)
    blush = out * [1.02, .86, .84]
    out += (blush - out) * np.clip(warm, 0, 1)[..., None] * covered[..., None]
    return np.clip(out, 0, 255).round().astype(np.uint8)


def build(source, target):
    asset = Asset(source)
    primitive = body_primitive(asset)
    doc = asset.d
    texture = doc['materials'][primitive['material']]['pbrMetallicRoughness']['baseColorTexture']['index']
    view = doc['bufferViews'][doc['images'][doc['textures'][texture]['source']]['bufferView']]
    start = view.get('byteOffset', 0)
    image = Image.open(io.BytesIO(asset.b[start:start + view['byteLength']])).convert('RGBA')
    size = image.width
    if image.height != size:
        raise ValueError('Expected a square body texture')
    pixels = np.array(image)
    rgb = remove_garments(pixels[..., :3])

    position, covered = texel_positions(asset, primitive, size)
    torso = np.zeros_like(covered)
    left, top, right, bottom = torso_island(asset, primitive, size)
    torso[top:bottom, left:right] = True
    # Anchor the suit to the rig so it follows later body revisions.
    _, world = world_positions(doc['nodes'])
    joint = {node.get('name'): world[i] for i, node in enumerate(doc['nodes'])}
    crotch = joint['J_Bip_L_UpperLeg'][1] - .105
    bust_y = joint['J_Sec_L_Bust2'][1]
    rgb = skin_details(rgb, position, covered, joint)
    suit = swimsuit(position, covered, torso, crotch, bust_y)
    # Carry the fabric over UV seams so filtering cannot show a skin line there,
    # and keep the trim off those seams.
    grown = np.asarray(Image.fromarray(suit).filter(ImageFilter.MaxFilter(13)))
    suit = suit | (grown & ~covered)
    interior = np.asarray(Image.fromarray(suit | ~covered).filter(ImageFilter.MinFilter(9)))
    soft = np.asarray(Image.fromarray((suit * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.2))) / 255
    edge = np.asarray(Image.fromarray((interior * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1))) / 255
    colour = TRIM + (SUIT - TRIM) * smooth(.2, .9, edge)[..., None]
    rgb = (rgb * (1 - soft[..., None]) + colour * soft[..., None]).round().astype(np.uint8)

    pixels[..., :3] = rgb
    pixels[..., 3] = 255
    Image.fromarray(pixels).convert('RGB').save(target, optimize=True)
    print(f'Wrote {target}: crotch {crotch:.3f} m, bust line {bust_y:.3f} m')


if __name__ == '__main__':
    build(*sys.argv[1:])
