"""Revision 10: hair and head clean-up.

Input must be r09. Removes the two antenna strands on the crown, gives the
ponytail more volume and a soft wave toward the tips, and brings the ear
texels of the face texture to the same tone as the rest of the skin.

Usage: python3 tools/refine_hair.py r09.glb r10.glb
Requires NumPy and Pillow.
"""
import io
import sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageFilter
from refine_mesh import Asset, smooth
from refine_subdivide import append, USHORT
from refine_identity import image_of, skin_mask
from build_study_texture import texel_positions

SOURCE_GENERATOR = 'Neliel identity 09 / tools/refine_identity.py'
GENERATOR = 'Neliel hair 10 / tools/refine_hair.py'


def components(points, triangles):
    """Label triangles by connected component, welding coincident vertices."""
    used = np.unique(triangles)
    _, weld = np.unique(np.round(points[used], 5), axis=0, return_inverse=True)
    lookup = np.zeros(len(points), dtype=int)
    lookup[used] = weld.reshape(-1)
    welded = lookup[triangles]
    parent = np.arange(welded.max() + 1)

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for triangle in welded:
        root = find(triangle[0])
        for vertex in triangle[1:]:
            parent[find(vertex)] = root
    return np.array([find(i) for i in welded[:, 0]])


def remove_antennae(asset):
    removed = 0
    for mesh in asset.d['meshes']:
        if mesh['name'] != 'Frangia':
            continue
        for primitive in mesh['primitives']:
            points = asset.array(primitive['attributes']['POSITION']).copy()
            triangles = asset.array(primitive['indices']).reshape(-1, 3).astype(int)
            label = components(points, triangles)
            keep = np.ones(len(triangles), dtype=bool)
            for root in np.unique(label):
                part = label == root
                # Small strands that live entirely above the crown.
                if part.sum() < 120 and points[np.unique(triangles[part]), 1].min() > 1.70:
                    keep[part] = False
            if not keep.all():
                removed += int((~keep).sum())
                primitive['indices'] = append(asset, triangles[keep].reshape(-1, 1), 'SCALAR', USHORT, target=34963)
    if removed != 152:
        raise ValueError(f'Expected to remove the two antenna strands (152 triangles), got {removed}')


def shape_tail(asset):
    for mesh in asset.d['meshes']:
        if mesh['name'] != 'Coda a ciocche':
            continue
        for primitive in mesh['primitives']:
            attrs = primitive['attributes']
            p = asset.array(attrs['POSITION']).astype(np.float64)
            x, y, z = p.T
            t = np.clip((1.66 - y) / 1.05, 0, 1)        # 0 at the tie, 1 at the tips
            q = p.copy()
            # Fan out sideways and in depth, then wave the lower half.
            q[:, 0] = x * (1 + .75 * t ** .8) + .030 * np.sin(9 * t + 14 * x) * t
            q[:, 2] = z + (z - .20) * .45 * t + .028 * np.sin(7 * t + 22 * x) * t
            triangles = asset.array(primitive['indices']).reshape(-1, 3).astype(int)
            normal = np.zeros_like(q)
            corner = q[triangles]
            face = np.cross(corner[:, 1] - corner[:, 0], corner[:, 2] - corner[:, 0])
            for k in range(3):
                np.add.at(normal, triangles[:, k], face)
            length = np.linalg.norm(normal, axis=1)
            old = asset.array(attrs['NORMAL']).copy()
            ok = length > 1e-12
            normal[ok] /= length[ok, None]
            normal[~ok] = old[~ok]
            asset.set(attrs['POSITION'], q.astype(np.float32))
            asset.set(attrs['NORMAL'], normal.astype(np.float32))


def even_ears(asset):
    doc = asset.d
    material = next(m for m in doc['materials'] if m['name'] == 'Viso')
    primitive = next(p for mesh in doc['meshes'] for p in mesh['primitives']
                     if doc['materials'][p['material']] is material)
    image, picture = image_of(asset, material)
    rgb = np.array(picture.convert('RGB')).astype(np.float64)
    position, covered = texel_positions(asset, primitive, picture.width)
    ear = covered * smooth(.082, .090, np.abs(position[..., 0]))
    ear = np.asarray(Image.fromarray((ear * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(2))) / 255
    tone = np.median(rgb[skin_mask(rgb.astype(np.uint8))], axis=0)
    rgb += (tone - rgb) * (.75 * ear)[..., None]
    encoded = io.BytesIO()
    Image.fromarray(rgb.round().astype(np.uint8)).save(encoded, format='JPEG', quality=93)
    data = encoded.getvalue()
    asset.b += b'\0' * (-len(asset.b) % 4)
    doc['bufferViews'].append({'buffer': 0, 'byteOffset': len(asset.b), 'byteLength': len(data)})
    asset.b += data
    asset.b += b'\0' * (-len(asset.b) % 4)
    doc['buffers'][0]['byteLength'] = len(asset.b)
    image['bufferView'] = len(doc['bufferViews']) - 1
    image['mimeType'] = 'image/jpeg'


def compact(asset):
    """Drop accessors and buffer views that nothing references any more."""
    doc = asset.d
    used = set()
    for mesh in doc['meshes']:
        for primitive in mesh['primitives']:
            used.update(primitive['attributes'].values())
            if 'indices' in primitive:
                used.add(primitive['indices'])
            for target in primitive.get('targets', []):
                used.update(target.values())
    for skin in doc.get('skins', []):
        if 'inverseBindMatrices' in skin:
            used.add(skin['inverseBindMatrices'])
    if doc.get('animations'):
        raise ValueError('Compaction does not handle animations')
    accessor_map = {old: new for new, old in enumerate(sorted(used))}
    accessors = [doc['accessors'][old] for old in sorted(used)]
    views = sorted({a['bufferView'] for a in accessors} | {i['bufferView'] for i in doc['images']})
    view_map = {old: new for new, old in enumerate(views)}
    data = bytearray()
    new_views = []
    for old in views:
        view = dict(doc['bufferViews'][old])
        start = view.get('byteOffset', 0)
        data += b'\0' * (-len(data) % 4)
        view['byteOffset'] = len(data)
        data += asset.b[start:start + view['byteLength']]
        new_views.append(view)
    data += b'\0' * (-len(data) % 4)
    for accessor in accessors:
        accessor['bufferView'] = view_map[accessor['bufferView']]
    for image in doc['images']:
        image['bufferView'] = view_map[image['bufferView']]
    for mesh in doc['meshes']:
        for primitive in mesh['primitives']:
            primitive['attributes'] = {k: accessor_map[v] for k, v in primitive['attributes'].items()}
            if 'indices' in primitive:
                primitive['indices'] = accessor_map[primitive['indices']]
            if 'targets' in primitive:
                primitive['targets'] = [{k: accessor_map[v] for k, v in t.items()} for t in primitive['targets']]
    for skin in doc.get('skins', []):
        if 'inverseBindMatrices' in skin:
            skin['inverseBindMatrices'] = accessor_map[skin['inverseBindMatrices']]
    doc['accessors'], doc['bufferViews'] = accessors, new_views
    asset.b = data
    doc['buffers'][0]['byteLength'] = len(data)


def build(source, target):
    if Path(source).resolve() == Path(target).resolve():
        raise ValueError('Preserve the source revision')
    asset = Asset(source)
    if asset.d['asset'].get('generator') != SOURCE_GENERATOR:
        raise ValueError('Expected revision 09; do not apply cumulatively')
    remove_antennae(asset)
    shape_tail(asset)
    even_ears(asset)
    compact(asset)
    asset.d['asset']['generator'] = GENERATOR
    asset.write(target)


if __name__ == '__main__':
    build(*sys.argv[1:])
