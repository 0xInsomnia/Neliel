import bpy, math, json, os
from mathutils import Vector
OUT=os.environ.get('STUDY_OUT','/workspace/scratch/e2491e58c4d8/previews')
os.makedirs(OUT,exist_ok=True)
scene=bpy.context.scene
# Keep actual skinned objects; helper meshes are rig widgets, not anatomy.
visible={'Body','head','hair','Study_top','Study_shorts'}
for o in bpy.data.objects:
 if o.type=='MESH': o.hide_render=o.name not in visible
scene.render.engine='BLENDER_WORKBENCH'
scene.display.shading.light='STUDIO';scene.display.shading.color_type='MATERIAL'
scene.display.shading.single_color=(0.57,0.53,0.64)
scene.display.shading.show_shadows=True;scene.display.shading.show_cavity=True
scene.display.shading.background_type='WORLD';scene.world.color=(0.055,0.045,0.075)
scene.render.resolution_x=600;scene.render.resolution_y=850;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG'
cam=scene.camera;cam.data.type='ORTHO';cam.data.ortho_scale=2.15
# World-space bounds reflect original rig and current shape keys.
dg=bpy.context.evaluated_depsgraph_get()
report={}
for name in ['Body','head','hair']:
 o=bpy.data.objects[name].evaluated_get(dg);pts=[o.matrix_world@v.co for v in o.data.vertices]
 report[name]={'min':[min(p[i] for p in pts) for i in range(3)],'max':[max(p[i] for p in pts) for i in range(3)]}
print('BOUNDS',json.dumps(report))
target=Vector((0,0,0.95))
for name,angle in [('front',0),('side',90),('back',180),('threequarter',35)]:
 a=math.radians(angle);cam.location=(4*math.sin(a),-4*math.cos(a),0.95)
 cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler()
 scene.render.filepath=OUT+'/'+name+'.png';bpy.ops.render.render(write_still=True)
