"""Revision v2-01: clean copy of the anime base mesh by David Onizaki (CC BY).

Opens the author's .blend with scripts disabled, keeps only the body mesh
with its shape keys, drops the materials, shader groups, text notes and
helper objects (they came with a toon shader the author built from game
models and are not part of the body), and exports one plain glTF.

Needs Blender as a Python module: pip install bpy (Python 3.13).
Usage: python3 tools/v2/import_base.py "Anime Base Female.blend" assets/v2/base-onizaki.glb
"""
import sys
import bpy

source, target = sys.argv[-2:]
bpy.context.preferences.filepaths.use_scripts_auto_execute = False
bpy.ops.wm.open_mainfile(filepath=source, load_ui=False, use_scripts=False)
body = bpy.data.objects['Character']
for obj in list(bpy.data.objects):
    if obj is not body:
        bpy.data.objects.remove(obj)
for text in list(bpy.data.texts):
    bpy.data.texts.remove(text)
body.data.materials.clear()
skin = bpy.data.materials.new('Pelle')
skin.diffuse_color = (.98, .79, .84, 1)
body.data.materials.append(skin)
for key in body.data.shape_keys.key_blocks:
    key.value = 0
body.name = body.data.name = 'Corpo base'
# Bake the object's own rotation and scale into the vertices and shape keys.
bpy.context.view_layer.objects.active = body
body.select_set(True)
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
bpy.ops.export_scene.gltf(filepath=target, export_format='GLB', use_selection=False,
                          export_morph=True, export_morph_normal=False, export_apply=False, export_try_sparse_sk=False,
                          export_texcoords=True, export_normals=True, export_materials='EXPORT')
print('exported', target, len(body.data.vertices), 'vertices,',
      len(body.data.shape_keys.key_blocks) - 1, 'shape keys')
