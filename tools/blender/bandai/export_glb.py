"""Export the Neliel "Jean" rig and its Bandai clips from a .blend to a GLB for the web.

glTF has no constraints or IK: the clips are keyed on the rig's controls (HandIK,
FootIK, Torso, tweaks...) and constraints move the deform bones.  The exporter samples
every frame and writes the evaluated pose of the deform bones, so constraints and IK are
baked.  glTF has no drivers either: the face expressions (shape keys driven by Root
custom properties) are baked here into shape-key actions, and each clip goes out as
one glTF animation (armature + face, NLA tracks merged by name), starting at time 0.

Usage (Blender 4.3+; the .blend with the clips, e.g. Neliel_bandai_test.blend):

    blender -b Neliel_bandai_test.blend --python export_glb.py -- \
        --out neliel_clips.glb [--clips walk_normal,bow_feminine] [--frame-step 1] [--images WEBP]

Only objects visible in the viewport and enabled for render are exported, without
modifiers (subdivision and the outline solidify are left to the web renderer), so
the shape keys survive.  The source .blend is not modified or saved.
"""
import argparse
import os
import sys

import bpy

ARM_NAME = 'Jean'


def parse_args():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--clips', default='', help='comma separated actions to export (default: all)')
    ap.add_argument('--frame-step', type=int, default=1)
    ap.add_argument('--images', default='AUTO', choices=['AUTO', 'WEBP', 'JPEG'],
                    help='texture format: AUTO keeps PNG/JPEG as in the .blend; WEBP is much smaller')
    return ap.parse_args(argv)


def _fcurve(action, owner, path, index):
    if hasattr(action, 'fcurve_ensure_for_datablock'):  # Blender 4.4+ (slotted actions)
        return action.fcurve_ensure_for_datablock(owner, path, index=index)
    return action.fcurves.find(path, index=index) or action.fcurves.new(path, index=index)


def bake_driven_shape_keys(arm, clips):
    """Shape keys driven by the rig (the face controls) -> one keyed action per clip.

    glTF has no drivers: the exporter would leave the expressions at 0.  The driven
    values are read frame by frame, keyed in an action of the mesh's shape keys, placed
    on an NLA track named like the clip (the exporter merges tracks by name), and the
    drivers are removed in this session only.
    """
    sc = bpy.context.scene
    keys = [o.data.shape_keys for o in bpy.data.objects
            if o.type == 'MESH' and o.data.shape_keys and o.data.shape_keys.animation_data
            and o.data.shape_keys.animation_data.drivers]
    keys = list({k.name: k for k in keys}.values())
    driven = {k.name: [fc.data_path for fc in k.animation_data.drivers] for k in keys}
    baked = {k.name: {} for k in keys}
    for clip in clips:
        act = bpy.data.actions[clip]
        arm.animation_data.action = act
        f0, f1 = int(act.frame_range[0]), int(act.frame_range[1])
        vals = {k.name: {p: [] for p in driven[k.name]} for k in keys}
        for f in range(f0, f1 + 1):
            sc.frame_set(f)
            dg = bpy.context.evaluated_depsgraph_get()
            for k in keys:
                ke = k.evaluated_get(dg)
                for p in driven[k.name]:
                    vals[k.name][p].append(ke.path_resolve(p))
        for k in keys:
            fa = bpy.data.actions.new(f'{clip}__{k.name}')
            if hasattr(fa, 'id_root'):
                fa.id_root = 'KEY'
            if k.animation_data is None:
                k.animation_data_create()
            k.animation_data.action = fa  # binds the slot in 4.4+
            for p, v in vals[k.name].items():
                fc = _fcurve(fa, k, p, 0)
                fc.keyframe_points.add(len(v))
                co = [c for pair in zip(range(f0, f1 + 1), v) for c in pair]
                fc.keyframe_points.foreach_set('co', co)
                fc.update()
            k.animation_data.action = None
            baked[k.name][clip] = (fa, f0)
    for k in keys:
        for fc in list(k.animation_data.drivers):
            k.animation_data.drivers.remove(fc)
        for clip, (fa, f0) in baked[k.name].items():
            tr = k.animation_data.nla_tracks.new()
            tr.name = clip
            tr.strips.new(clip, f0, fa)
    return [k.name for k in keys]


def flatten_static_shape_keys():
    """Meshes whose shape keys are not animated: store the shape shown in Blender as the
    mesh itself and drop the keys.

    glTF morph targets are offsets from one base mesh.  The body's keys are relative to
    two different keys ("Basis" and the reference "fix.001"), which glTF cannot express:
    exported as they are, legs, hips and shoulders bulge.  Animated keys (the face) are
    kept; they must all be relative to the reference key.
    """
    done = []
    for o in bpy.data.objects:
        if o.type != 'MESH' or not o.data.shape_keys:
            continue
        k = o.data.shape_keys
        animated = k.animation_data and (k.animation_data.drivers or k.animation_data.action
                                         or k.animation_data.nla_tracks)
        if animated:
            odd = [kb.name for kb in k.key_blocks if kb.relative_key != k.reference_key]
            if odd:
                print(f'warning: {o.name}: animated shape keys with another relative key: {odd}')
            continue
        # evaluate the shape-key mix without the armature (rest pose), same topology
        mods = [m for m in o.modifiers if m.show_viewport]
        for m in mods:
            m.show_viewport = False
        try:
            bpy.context.view_layer.update()
            oe = o.evaluated_get(bpy.context.evaluated_depsgraph_get())
            me = oe.to_mesh()
            co = [0.0] * (len(me.vertices) * 3)
            me.vertices.foreach_get('co', co)
            oe.to_mesh_clear()
        finally:
            for m in mods:
                m.show_viewport = True
        if len(co) != len(o.data.vertices) * 3:
            print(f'warning: {o.name}: topology changes without modifiers, keys left as they are')
            continue
        o.shape_key_clear()
        o.data.vertices.foreach_set('co', co)
        o.data.update()
        done.append(o.name)
    bpy.context.view_layer.update()
    return done


def clips_to_nla(arm, clips):
    ad = arm.animation_data
    ad.action = None
    for clip in clips:
        act = bpy.data.actions[clip]
        tr = ad.nla_tracks.new()
        tr.name = clip
        tr.strips.new(clip, int(act.frame_range[0]), act)


def main():
    a = parse_args()
    arm = bpy.data.objects[ARM_NAME]
    arm_actions = [act for act in bpy.data.actions if act.id_root in ('OBJECT', '')
                   and any(fc.data_path.startswith('pose.bones') for fc in _curves(act))]
    clips = [c for c in a.clips.split(',') if c] or [act.name for act in arm_actions]
    missing = [c for c in clips if c not in bpy.data.actions]
    if missing:
        raise SystemExit(f'unknown actions: {missing}')
    faces = bake_driven_shape_keys(arm, clips)
    print('face expressions baked for', faces)
    print('static shape keys stored in the mesh for', flatten_static_shape_keys())
    clips_to_nla(arm, clips)
    out = os.path.abspath(a.out)
    bpy.ops.export_scene.gltf(
        filepath=out, export_format='GLB',
        use_visible=True, use_renderable=True,
        export_apply=False,
        export_animations=True, export_animation_mode='NLA_TRACKS',
        export_force_sampling=True, export_frame_step=a.frame_step,
        export_anim_slide_to_zero=True,
        export_def_bones=True, export_optimize_animation_size=True,
        export_anim_single_armature=True,
        export_morph=True, export_morph_animation=True, export_morph_normal=False,
        export_image_format=a.images,
        export_yup=True)
    print('exported', len(clips), 'clips to', out, round(os.path.getsize(out) / 1e6, 1), 'MB')


def _curves(act):
    if hasattr(act, 'fcurves'):
        return list(act.fcurves)
    return [fc for layer in act.layers for strip in layer.strips for bag in strip.channelbags for fc in bag.fcurves]


if __name__ == '__main__':
    main()
