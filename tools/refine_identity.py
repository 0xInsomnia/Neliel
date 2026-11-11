"""Revision 09: amber skin tone shared by face and body, shorter, wider lower face.

Input must be r08. The body texture is retinted only where it shows skin, so
the provisional outfit keeps its colours; the face material receives a colour
factor that brings its texture to the same tone. The lower face is shortened and the cheeks widened
on every facial layer and morph endpoint.

Usage: python3 tools/refine_identity.py r08.glb r09.glb
Requires NumPy and Pillow.
"""
import io
import sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageFilter
from refine_mesh import Asset, smooth
from refine_body import HEAD_PIVOT, HEAD_SCALE, LEG_RANGE, LEG_STRETCH

SOURCE_GENERATOR = 'Neliel smooth body 08 / tools/refine_subdivide.py'
GENERATOR = 'Neliel identity 09 / tools/refine_identity.py'
SKIN_TONE = np.array([226, 170, 138])       # lit skin, sRGB
LIFT = np.array([0, LEG_STRETCH * (LEG_RANGE[1] - LEG_RANGE[0]), 0])
CHIN_RISE = .009      # shorter lower face, as in the reference
CHEEK_WIDTH = .045


def to_linear(c):
    c = np.asarray(c, dtype=np.float64) / 255
    return np.where(c <= .04045, c / 12.92, ((c + .055) / 1.055) ** 2.4)


def to_srgb(c):
    c = np.clip(c, 0, 1)
    return np.where(c <= .0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - .055) * 255


def skin_mask(rgb):
    r, g, b = [rgb[..., i].astype(int) for i in range(3)]
    return (r > 175) & (r - b > 18) & (r >= g)


def image_of(asset, material):
    doc = asset.d
    texture = material['pbrMetallicRoughness']['baseColorTexture']['index']
    image = doc['images'][doc['textures'][texture]['source']]
    view = doc['bufferViews'][image['bufferView']]
    start = view.get('byteOffset', 0)
    return image, Image.open(io.BytesIO(asset.b[start:start + view['byteLength']]))


def retint_body(asset, material):
    image, picture = image_of(asset, material)
    pixels = np.array(picture.convert('RGBA'))
    rgb = pixels[..., :3]
    mask = skin_mask(rgb)
    gain = to_linear(SKIN_TONE) / to_linear(np.median(rgb[mask], axis=0))
    soft = np.asarray(Image.fromarray((mask * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.5))) / 255
    tinted = to_srgb(to_linear(rgb) * gain)
    pixels[..., :3] = (rgb * (1 - soft[..., None]) + tinted * soft[..., None]).round().astype(np.uint8)
    encoded = io.BytesIO()
    Image.fromarray(pixels).save(encoded, format='PNG', optimize=True)
    data = encoded.getvalue()
    asset.b += b'\0' * (-len(asset.b) % 4)
    asset.d['bufferViews'].append({'buffer': 0, 'byteOffset': len(asset.b), 'byteLength': len(data)})
    asset.b += data
    asset.b += b'\0' * (-len(asset.b) % 4)
    asset.d['buffers'][0]['byteLength'] = len(asset.b)
    image['bufferView'] = len(asset.d['bufferViews']) - 1
    image['mimeType'] = 'image/png'


def tint_face(asset, material):
    _, picture = image_of(asset, material)
    rgb = np.array(picture.convert('RGB'))
    gain = to_linear(SKIN_TONE) / to_linear(np.median(rgb[skin_mask(rgb)], axis=0))
    material['pbrMetallicRoughness']['baseColorFactor'] = [float(v) for v in gain] + [1.0]


def lengthen_chin(points, _flags=None):
    """Work in the head's r06 frame, where the facial landmarks were measured."""
    p = np.asarray(points, dtype=np.float64)
    local = HEAD_PIVOT + (p - LIFT - HEAD_PIVOT) / HEAD_SCALE
    x, y, z = local.T
    front = smooth(.0, .045, -z)
    lower = (1 - smooth(1.465, 1.525, y)) * smooth(1.395, 1.43, y)
    q = p.copy()
    q[:, 1] += CHIN_RISE * HEAD_SCALE * lower * front
    # Fuller cheeks: the reference face is short and wide, tapering to a small chin.
    cheek = np.exp(-((y - 1.482) / .040) ** 2)
    q[:, 0] += x * HEAD_SCALE * CHEEK_WIDTH * cheek * front
    return q


def jacobian(points, h=1e-4):
    j = np.empty((len(points), 3, 3))
    for axis in range(3):
        step = np.zeros(3)
        step[axis] = h
        j[:, :, axis] = (lengthen_chin(points + step) - lengthen_chin(points - step)) / (2 * h)
    return j


def mapped_normals(normal, points):
    inverse_t = np.linalg.inv(jacobian(points)).transpose(0, 2, 1)
    out = np.einsum('nij,nj->ni', inverse_t, normal.astype(np.float64))
    length = np.linalg.norm(out, axis=1)
    ok = length > 1e-9
    out[ok] /= length[ok, None]
    out[~ok] = normal[~ok]
    return out


def reshape_face(asset):
    done = set()
    for mesh in asset.d['meshes']:
        if mesh['name'] != 'Viso':
            continue
        for primitive in mesh['primitives']:
            attrs = primitive['attributes']
            if attrs['POSITION'] in done:
                continue
            done.add(attrs['POSITION'])
            base = asset.array(attrs['POSITION']).astype(np.float64)
            shaped = lengthen_chin(base)
            base_normal = asset.array(attrs['NORMAL']).copy()
            normal = mapped_normals(base_normal, base)
            for morph in primitive.get('targets', []):
                posed = base + asset.array(morph['POSITION'])
                asset.set(morph['POSITION'], (lengthen_chin(posed) - shaped).astype(np.float32))
                if 'NORMAL' in morph:
                    posed_normal = base_normal + asset.array(morph['NORMAL'])
                    asset.set(morph['NORMAL'], (mapped_normals(posed_normal, posed) - normal).astype(np.float32))
            asset.set(attrs['POSITION'], shaped.astype(np.float32))
            asset.set(attrs['NORMAL'], normal.astype(np.float32))


def build(source, target):
    if Path(source).resolve() == Path(target).resolve():
        raise ValueError('Preserve the source revision')
    asset = Asset(source)
    doc = asset.d
    if doc['asset'].get('generator') != SOURCE_GENERATOR:
        raise ValueError('Expected revision 08; do not apply cumulatively')
    materials = {material['name']: material for material in doc['materials']}
    reshape_face(asset)
    tint_face(asset, materials['Viso'])
    retint_body(asset, materials['Pelle e tessuto'])
    doc['asset']['generator'] = GENERATOR
    asset.write(target)


if __name__ == '__main__':
    build(*sys.argv[1:])
