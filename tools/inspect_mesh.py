"""CPU orthographic inspection of embedded GLB geometry and textures.
Not a WebGL/toon preview: bind pose, unlit sRGB textures, no animation.
Usage: python tools/inspect_mesh.py model.glb output.png
Requires NumPy and Pillow. Output is an inspection intermediate, not an asset.
"""
import io
import sys
import numpy as np
from PIL import Image, ImageDraw
from refine_mesh import Asset


def render(asset, angle, size=600, portrait=True):
    canvas = np.full((size, size, 3), [47, 43, 60], dtype=np.uint8)
    depth = np.full((size, size), np.inf)
    c, s = np.cos(angle), np.sin(angle)
    rotation = np.array([[c, 0, -s], [0, 1, 0], [s, 0, c]])
    scale = size / (.40 if portrait else 1.9)
    center = 1.50 if portrait else .85
    textures = {}
    for i, texture in enumerate(asset.d['textures']):
        image = asset.d['images'][texture['source']]
        view = asset.d['bufferViews'][image['bufferView']]
        start = view.get('byteOffset', 0)
        textures[i] = np.array(Image.open(io.BytesIO(asset.b[start:start+view['byteLength']])).convert('RGBA'))
    for mesh in asset.d['meshes']:
        for primitive in mesh['primitives']:
            attrs = primitive['attributes']
            points = asset.array(attrs['POSITION']) @ rotation.T
            screen = points[:, :2] * [scale, -scale] + [size/2, size/2+center*scale]
            uv = asset.array(attrs['TEXCOORD_0']) if 'TEXCOORD_0' in attrs else np.zeros((len(points), 2))
            material = asset.d['materials'][primitive['material']]
            pbr = material.get('pbrMetallicRoughness', {})
            factor = np.array(pbr.get('baseColorFactor', [1, 1, 1, 1]))
            tex = textures.get(pbr.get('baseColorTexture', {}).get('index'))
            for triangle in asset.array(primitive['indices']).reshape(-1, 3):
                p = screen[triangle]
                low = np.maximum(np.floor(p.min(0)).astype(int), 0)
                high = np.minimum(np.ceil(p.max(0)).astype(int), size-1)
                if np.any(low > high): continue
                x, y = np.meshgrid(np.arange(low[0], high[0]+1)+.5, np.arange(low[1], high[1]+1)+.5)
                denominator = (p[1,1]-p[2,1])*(p[0,0]-p[2,0])+(p[2,0]-p[1,0])*(p[0,1]-p[2,1])
                if abs(denominator) < 1e-8: continue
                a = ((p[1,1]-p[2,1])*(x-p[2,0])+(p[2,0]-p[1,0])*(y-p[2,1]))/denominator
                b = ((p[2,1]-p[0,1])*(x-p[2,0])+(p[0,0]-p[2,0])*(y-p[2,1]))/denominator
                weights = np.stack([a, b, 1-a-b], -1)
                z = weights @ points[triangle, 2]
                region = np.s_[low[1]:high[1]+1, low[0]:high[0]+1]
                mask = (weights.min(-1) >= -1e-7) & (z < depth[region])
                if not mask.any(): continue
                rgba = np.ones((*x.shape, 4))
                if tex is not None:
                    coords = (weights @ uv[triangle]) % 1
                    tx = np.clip((coords[...,0]*tex.shape[1]).astype(int), 0, tex.shape[1]-1)
                    ty = np.clip((coords[...,1]*tex.shape[0]).astype(int), 0, tex.shape[0]-1)
                    rgba = tex[ty, tx]/255
                rgb = rgba[...,:3]
                linear = np.where(rgb <= .04045, rgb/12.92, ((rgb+.055)/1.055)**2.4) * factor[:3]
                rgb = np.where(linear <= .0031308, linear*12.92, 1.055*linear**(1/2.4)-.055)
                alpha = rgba[...,3]*factor[3]
                mask &= alpha >= material.get('alphaCutoff', .5)
                canvas[region][mask] = np.clip(rgb[mask]*255, 0, 255).astype(np.uint8)
                depth[region][mask] = z[mask]
    return Image.fromarray(canvas)


def main():
    asset = Asset(sys.argv[1])
    size = 600
    sheet = Image.new('RGB', (size*3, size+36), '#2f2b3c')
    for i, (angle, label) in enumerate([(0, 'FRONT'), (np.pi/2, 'PROFILE'), (np.pi, 'REAR')]):
        sheet.paste(render(asset, angle), (i*size, 36))
        ImageDraw.Draw(sheet).text((i*size+12, 10), label+' / CPU texture inspection', fill='white')
    sheet.save(sys.argv[2])

if __name__ == '__main__': main()
