"""Reproducible, non-destructive body study from the supplied Jean source.
Run: blender -b --disable-autoexec source/jean-original.blend -P tools/rebuild_body.py
"""
import bpy, math, os, json
from mathutils import Vector
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
rig=bpy.data.objects['Jean'];body=bpy.data.objects['Body']
# Remove visual obstruction without deleting the original clothes or rig widgets.
keep={'Body','head','hair'}
for o in bpy.data.objects:
 if o.type=='MESH':
  o.hide_render=o.name not in keep
  
  if o.name in bpy.context.view_layer.objects: o.hide_set(o.name not in keep)
for m in body.modifiers:
 if m.type=='MASK':m.show_viewport=False;m.show_render=False
# An additive shape retains every original key, UV and vertex weight.
key=body.shape_key_add(name='Neliel_body_study_01',from_mix=False)
M=body.matrix_world.copy();I=M.inverted()
def bell(z,c,w):return math.exp(-((z-c)/w)**2)
for v,k in zip(body.data.shape_keys.key_blocks[0].data,key.data):
 p=M@v.co;z=p.z
 # Work around the pelvis and waist; do not move joints or change limb lengths.
 core=math.exp(-(abs(p.x)/0.29)**8)
 sx=1+core*(0.095*bell(z,1.035,.115)-0.055*bell(z,1.30,.09))
 sy=1+core*(0.045*bell(z,1.01,.10))
 p.x*=sx;p.y*=sy;k.co=I@p
key.value=1
# Temporary opaque fitting garment, derived from the source body topology.
# It is deliberately not the final outfit; it keeps study images readable.
def garment(name,predicate):
 dg=bpy.context.evaluated_depsgraph_get();ob=body.evaluated_get(dg);me=ob.to_mesh()
 ids=[p for p in me.polygons if predicate(sum((M@me.vertices[i].co for i in p.vertices),Vector())/len(p.vertices))]
 used=sorted({i for p in ids for i in p.vertices});remap={i:j for j,i in enumerate(used)}
 mesh=bpy.data.meshes.new(name);mesh.from_pydata([me.vertices[i].co for i in used],[],[[remap[i] for i in p.vertices] for p in ids]);mesh.update()
 o=bpy.data.objects.new(name,mesh);bpy.context.collection.objects.link(o);o.matrix_world=M
 # Evaluated garment is a static review accessory, not shipped as a rigged outfit.
 mat=bpy.data.materials.new(name);mat.diffuse_color=(.12,.055,.22,1);o.data.materials.append(mat)
 for p in mesh.polygons:p.use_smooth=True
 s=o.modifiers.new('Fitting offset','SOLIDIFY');s.thickness=.004
 ob.to_mesh_clear();return o
# Geometry coordinates are in the same world scale as the source.
garments=[garment('Study_top',lambda p:1.36<p.z<1.57 and abs(p.x)<.23),garment('Study_shorts',lambda p:.84<p.z<1.15 and abs(p.x)<.25)]
# Measure actual deformation under isolated FK rotations, restoring all controls.
dg=bpy.context.evaluated_depsgraph_get()
def sample():
 bpy.context.view_layer.update();e=body.evaluated_get(dg);m=e.to_mesh();pts=[e.matrix_world@v.co for v in m.vertices];e.to_mesh_clear();return pts
constraints=[(c,c.mute) for p in rig.pose.bones for c in p.constraints]
for c,_ in constraints:c.mute=True
base=sample();tests=[]
for name,angle in [('lShldrBend',30),('lForearmBend',65),('lThighBend',35),('lShin',65)]:
 p=rig.pose.bones[name];old=p.matrix_basis.copy();p.rotation_mode='XYZ';p.rotation_euler.x+=math.radians(angle)
 pts=sample();ds=[(a-b).length for a,b in zip(base,pts)]
 tests.append({'bone':name,'degrees':angle,'max_displacement':max(ds),'moved_vertices':sum(d>1e-5 for d in ds),'finite':all(math.isfinite(x) for v in pts for x in v),'constraints_muted_for_FK_probe':True})
 p.matrix_basis=old
for c,state in constraints:c.mute=state
bpy.context.view_layer.update()
report={'phase':'body-study-01, not approved','original_bones':len(rig.data.bones),'body_vertices':len(body.data.vertices),'body_key_blocks':len(body.data.shape_keys.key_blocks),'tests':tests,'limitations':['Garment is static fitting accessory; final outfit not started.','Joint tests isolate FK with constraints muted, not full controller validation.','Reference body proportions still require visual iteration.']}
with open(ROOT+'/docs/body-study-audit.json','w') as f:json.dump(report,f,indent=2)
bpy.ops.wm.save_as_mainfile(filepath=ROOT+'/source/neliel-body-study.blend',compress=True)
# Export visible study as a browser inspection asset. Source remains fully editable.
for o in bpy.context.selected_objects:o.select_set(False)
for o in [body,bpy.data.objects['head'],bpy.data.objects['hair'],rig,*garments]:o.hide_set(False);o.select_set(True)
# Export neutral materials, not unsupported source node shaders.
for name in ['Body','head','hair']:
 o=bpy.data.objects[name];mat=bpy.data.materials.new('Study_'+name);mat.diffuse_color={'Body':(.65,.42,.37,1),'head':(.65,.42,.37,1),'hair':(.62,.58,.72,1)}[name]
 o.data.materials.clear();o.data.materials.append(mat)
 for p in o.data.polygons:p.material_index=0
bpy.ops.export_scene.gltf(filepath=ROOT+'/assets/neliel-study.glb',export_format='GLB',use_selection=True,export_animations=False,export_morph=True,export_morph_normal=False,export_morph_tangent=False,export_skins=True,export_all_influences=False,export_yup=True)
print('AUDIT',json.dumps(report))
