"""Continue the editable body study with a reversible silhouette adjustment.

Run with Blender in background on source/neliel-body-study.blend.
The first study and all source shape keys remain intact.
"""
import bpy, math, os, json
from mathutils import Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
body = bpy.data.objects['Body']
rig = bpy.data.objects['Jean']
M = body.matrix_world.copy()
inverse = M.inverted()
assert 'Neliel_body_study_01' in body.data.shape_keys.key_blocks
assert 'Neliel_body_study_02' not in body.data.shape_keys.key_blocks

# The additional key gently fills the high waist and blends the lateral hip
# into the upper thigh. The curves taper gradually to avoid a visible ledge.
# It does not move bones, alter weights, or assert dimensional accuracy.
key = body.shape_key_add(name='Neliel_body_study_02', from_mix=False)
def bell(z, center, width):
    return math.exp(-((z-center)/width)**2)
for basis, out in zip(body.data.shape_keys.key_blocks['Basis'].data, key.data):
    p = M @ basis.co
    z = p.z
    core = math.exp(-(abs(p.x)/0.30)**8)
    p.x *= 1 + core * (0.025*bell(z, 1.25, .13) + 0.018*bell(z, 1.10, .17))
    p.y *= 1 + core * (0.012*bell(z, 1.20, .15))
    out.co = inverse @ p
key.value = 1
bpy.context.view_layer.update()

# Rebuild temporary opaque fitting layers around the changed surface.
# These remain static review accessories, not final deformable clothing.
for name in ('Study_top', 'Study_shorts'):
    old = bpy.data.objects.get(name)
    if old: bpy.data.objects.remove(old, do_unlink=True)
def garment(name, predicate):
    dg = bpy.context.evaluated_depsgraph_get()
    obj = body.evaluated_get(dg)
    mesh = obj.to_mesh()
    faces = [f for f in mesh.polygons if predicate(sum((M @ mesh.vertices[i].co for i in f.vertices), Vector()) / len(f.vertices))]
    used = sorted({i for f in faces for i in f.vertices})
    mapping = {i:j for j,i in enumerate(used)}
    newmesh = bpy.data.meshes.new(name)
    newmesh.from_pydata([mesh.vertices[i].co for i in used], [], [[mapping[i] for i in f.vertices] for f in faces])
    newmesh.update()
    o = bpy.data.objects.new(name, newmesh)
    bpy.context.collection.objects.link(o)
    o.matrix_world = M
    mat = bpy.data.materials.new(name + '_02')
    mat.diffuse_color = (.12, .055, .22, 1)
    o.data.materials.append(mat)
    for face in newmesh.polygons: face.use_smooth = True
    o.modifiers.new('Fitting offset', 'SOLIDIFY').thickness = .004
    obj.to_mesh_clear()
    return o
garments = [garment('Study_top', lambda p: 1.36 < p.z < 1.57 and abs(p.x) < .23),
            garment('Study_shorts', lambda p: .84 < p.z < 1.15 and abs(p.x) < .25)]

dg = bpy.context.evaluated_depsgraph_get()
def sample():
    bpy.context.view_layer.update()
    obj = body.evaluated_get(dg); mesh = obj.to_mesh()
    pts = [obj.matrix_world @ v.co for v in mesh.vertices]
    obj.to_mesh_clear()
    return pts
constraints = [(c, c.mute) for p in rig.pose.bones for c in p.constraints]
for c, _ in constraints: c.mute = True
base = sample(); tests = []
for name, angle in [('lShldrBend',30), ('lForearmBend',65), ('lThighBend',35), ('lShin',65)]:
    bone = rig.pose.bones[name]; previous = bone.matrix_basis.copy()
    bone.rotation_mode = 'XYZ'; bone.rotation_euler.x += math.radians(angle)
    pts = sample(); ds = [(a-b).length for a,b in zip(base,pts)]
    tests.append({'bone':name, 'degrees':angle, 'max_displacement':max(ds),
                  'moved_vertices':sum(d > 1e-5 for d in ds),
                  'finite':all(math.isfinite(x) for p in pts for x in p),
                  'constraints_muted_for_FK_probe':True})
    bone.matrix_basis = previous
for c, state in constraints: c.mute = state
bpy.context.view_layer.update()
assert all(t['finite'] and t['moved_vertices'] > 0 for t in tests)
report = {'phase':'body-study-02, not approved', 'original_bones':len(rig.data.bones),
          'body_vertices':len(body.data.vertices), 'body_key_blocks':len(body.data.shape_keys.key_blocks),
          'tests':tests, 'limitations':['Static fitting garments are not final rigged clothing.',
          'FK probes mute constraints; full controller behavior is not tested.',
          'Reference drawings use different poses and are not calibrated orthographic measurements.']}
with open(ROOT+'/docs/body-study-audit.json','w') as f: json.dump(report,f,indent=2)
bpy.ops.wm.save_as_mainfile(filepath=ROOT+'/source/neliel-body-study.blend', compress=True)

# Export only the inspection model; source materials remain intact in the blend.
for o in bpy.context.selected_objects: o.select_set(False)
for o in [body,bpy.data.objects['head'],bpy.data.objects['hair'],rig,*garments]:
    o.hide_set(False); o.select_set(True)
for name in ['Body','head','hair']:
    o = bpy.data.objects[name]
    mat = bpy.data.materials.new('Study_export_'+name)
    mat.diffuse_color = {'Body':(.65,.42,.37,1), 'head':(.65,.42,.37,1), 'hair':(.62,.58,.72,1)}[name]
    o.data.materials.clear(); o.data.materials.append(mat)
    for p in o.data.polygons: p.material_index = 0
bpy.ops.export_scene.gltf(filepath=ROOT+'/assets/neliel-study.glb',export_format='GLB',use_selection=True,
    export_animations=False,export_morph=True,export_morph_normal=False,export_morph_tangent=False,
    export_skins=True,export_all_influences=False,export_yup=True)
