"""Apply Bandai Namco BVH clips to the Neliel rig "Jean" as Blender Actions.

One Action per clip, named after the clip, keyed on the rig *controls*
(Torso, tweak_spine*, neck/head, collars, HandIK/ElbowIK, FootIK/KneeIK, toes).
The deform bones follow through the rig's own constraints and IK, so the
clips stay editable like a hand-made animation.

Command line (Blender 4.3 or newer):

    blender -b Neliel_rig_fasce_test_02.blend --python apply_bandai.py -- \
        --bvh-dir bvh --out Neliel_bandai_test.blend [--clips walk_normal,bow_feminine]
        [--verify] [--compress]

From Blender's Text Editor: put this file, bvh.py, retarget.py and the bvh/
folder next to the .blend, open the script and press Run Script.  The output
is written to Neliel_bandai_test.blend in the same folder.

The opened .blend is never written: the result is saved only to the output
path, and the script refuses an output path equal to the source file.
"""
import argparse
import math
import os
import sys
import time

import bpy
import numpy as np
from mathutils import Matrix, Quaternion


def _script_dir():
    f = globals().get('__file__')
    if f and os.path.exists(os.path.join(os.path.dirname(os.path.abspath(f)), 'retarget.py')):
        return os.path.dirname(os.path.abspath(f))
    return os.path.dirname(bpy.data.filepath)


HERE = _script_dir()
if HERE not in sys.path:
    sys.path.insert(0, HERE)
from retarget import retarget  # noqa: E402  (bvh.py and retarget.py live next to this script)
import hair_physics  # noqa: E402

ARM_NAME = 'Jean'
FPS = 30
FOOT = ['lFoot', 'rFoot', 'lToe', 'rToe', 'lMetatarsals', 'rMetatarsals']
# deform spine bone <- tweak bone it copies (Copy Transforms, world space)
SPINE_TWEAKS = [('DEF-spine', 'tweak_spine'), ('abdomenLower', 'tweak_spine.001'),
                ('abdomenUpper', 'tweak_spine.002'), ('chestLower', 'tweak_spine.003'),
                ('chestUpper', 'tweak_spine.004')]
# neckLower, neckUpper and head copy 1/3 of NeckControl's local rotation (Copy Rotation,
# REPLACE, influence 0.333).  With NeckControl at rest the result is own^(1 - 0.333),
# so the key is the wanted local rotation raised to 1 / (1 - 0.333).
NECK_BONES = ['neckLower', 'neckUpper', 'head']
REST_KEYED = ['Root', 'Hips', 'Chest', 'NeckControl', 'ToeIK.L', 'ToeIK.R']
# share of the wrist twist taken by the forearm bones (same as the rig's Hand_control=0 mode)
TWIST_SHARE = {'ForearmBend': 0.1, 'ForearmTwist': 0.6}
DEFAULT_CLIPS = ['walk_feminine', 'walk_normal', 'bow_feminine', 'bow_normal',
                 'bye_feminine', 'bye_normal', 'byebye_feminine', 'byebye_normal',
                 'guide_feminine', 'guide_normal', 'call_normal', 'respond_normal']
CHECK_BONES = [n for n, _ in SPINE_TWEAKS] + ['neckLower', 'head']
for _s in 'lr':
    CHECK_BONES += [f'{_s}Collar', f'{_s}ShldrBend', f'{_s}ShldrTwist', f'{_s}ForearmBend',
                    f'{_s}ForearmTwist', f'{_s}Hand', f'{_s}ThighBend', f'{_s}ThighTwist',
                    f'{_s}Shin', f'{_s}Foot', f'{_s}Toe']


# ----------------------------------------------------------------------------- args

def parse_args():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    base = os.path.dirname(bpy.data.filepath)
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--bvh-dir', default=os.path.join(base, 'bvh'))
    ap.add_argument('--out', default=os.path.join(base, 'Neliel_bandai_test.blend'))
    ap.add_argument('--clips', default='', help='comma separated clip names (default: all 12)')
    ap.add_argument('--verify', action='store_true', help='evaluate every frame and print errors')
    ap.add_argument('--compress', action='store_true', help='save the output compressed')
    ap.add_argument('--no-hair', action='store_true', help='skip the baked hair physics')
    a = ap.parse_args(argv)
    a.clips = [c for c in a.clips.split(',') if c] or DEFAULT_CLIPS
    return a


# ----------------------------------------------------------------------------- math

def rig_bones(arm):
    """Bone list in the format expected by retarget() (armature space, rest pose)."""
    bl = list(arm.data.bones)
    idx = {b.name: i for i, b in enumerate(bl)}
    return [dict(name=b.name, parent=idx[b.parent.name] if b.parent else -1,
                 head=np.array(b.head_local, float), tail=np.array(b.tail_local, float),
                 mat=np.array(b.matrix_local, float)) for b in bl]


def compose(R, H):
    """(F,3,3) rotations + (F,3) heads -> (F,4,4) matrices."""
    M = np.zeros((len(R), 4, 4))
    M[:, :3, :3] = R
    M[:, :3, 3] = H
    M[:, 3, 3] = 1
    return M


def local_basis(rest, rest_parent, pose_parent, pose):
    """matrix_basis that gives `pose` under `pose_parent` (full inheritance, no constraints)."""
    if rest_parent is None:
        return np.linalg.inv(rest) @ pose
    return np.linalg.inv(np.linalg.inv(rest_parent) @ rest) @ np.linalg.inv(pose_parent) @ pose


def quat_power(q, k):
    """q^k for unit quaternions (w, x, y, z), shortest arc."""
    q = q if q[0] >= 0 else -q
    w = min(1.0, max(-1.0, q[0]))
    ang = math.acos(w)
    s = math.sin(ang)
    if s < 1e-9:
        return np.array([1.0, 0, 0, 0])
    axis = q[1:] / s
    return np.concatenate([[math.cos(ang * k)], axis * math.sin(ang * k)])


def pole_positions(S, E, W, R_upper, R_upper_rest, pole_rest, elbow_rest):
    """IK pole on the bend side of the target chain S-E-W (shoulder/hip, elbow/knee, wrist/ankle).

    For a nearly straight limb the bend side is undefined, so the rest pole offset is
    carried by the target upper bone instead.
    """
    dist = np.linalg.norm(pole_rest - elbow_rest)
    out = np.zeros_like(E)
    for f in range(len(E)):
        sw = W[f] - S[f]
        u = sw / np.linalg.norm(sw)
        C = S[f] + u * np.dot(E[f] - S[f], u)
        v_bend = E[f] - C
        v_rigid = R_upper[f] @ R_upper_rest.T @ (pole_rest - elbow_rest)
        v_rigid -= u * np.dot(v_rigid, u)
        w = min(1.0, np.linalg.norm(v_bend) / 0.01)
        d = w * v_bend / max(np.linalg.norm(v_bend), 1e-9) + (1 - w) * v_rigid / np.linalg.norm(v_rigid)
        out[f] = E[f] + d / np.linalg.norm(d) * dist
    return out


def solve_controls(arm, bones, r):
    """Return {bone_name: (F,4,4) matrix_basis} for every keyed control."""
    idx = {b['name']: i for i, b in enumerate(bones)}
    Mr = {b['name']: b['mat'] for b in bones}
    F = r['F']
    T = lambda n: compose(r['Rw'][:, idx[n]], r['Hw'][:, idx[n]])  # target pose, armature space
    parent = lambda n: arm.data.bones[n].parent.name
    rest_pose = lambda n: np.repeat(Mr[n][None], F, 0)
    basis = {}

    def from_pose(n, pose, pose_parent):
        p = arm.data.bones[n].parent
        basis[n] = local_basis(Mr[n], Mr[p.name] if p else None, pose_parent, pose)

    root = rest_pose('Root')
    # Torso moves rigidly with the pelvis (DEF-spine); MCH-spine chain follows Torso.
    torso = T('DEF-spine') @ np.linalg.inv(Mr['DEF-spine']) @ Mr['Torso']
    from_pose('Torso', torso, root)
    rigid = lambda n: torso @ np.linalg.inv(Mr['Torso']) @ Mr[n]  # bones rigid with Torso
    # Spine: each deform bone copies its tweak in world space, so tweak pose = target pose.
    for dname, tw in SPINE_TWEAKS:
        from_pose(tw, T(dname), rigid(parent(tw)))
    # Neck/head: chestUpper is driven by tweak_spine.004 -> its pose is the target.
    for n in NECK_BONES:
        infl = sum(c.influence for c in arm.pose.bones[n].constraints
                   if c.type == 'COPY_ROTATION' and c.subtarget == 'NeckControl' and not c.mute)
        k = 1.0 / (1.0 - infl)
        b = local_basis(Mr[n], Mr[parent(n)], T(parent(n)), T(n))
        for f in range(F):
            q = np.array(Matrix(b[f].tolist()).to_quaternion())
            b[f] = np.eye(4)
            b[f, :3, :3] = np.array(Quaternion(quat_power(q, k)).to_matrix())
        basis[n] = b
    for s, S_ in (('l', 'L'), ('r', 'R')):
        from_pose(f'{s}Collar', T(f'{s}Collar'), T('chestUpper'))
        # Hand: lHand copies HandIK's world rotation; IK puts the wrist at HandIK's head.
        hand = T(f'{s}Hand')
        from_pose(f'HandIK.{S_}', hand, root)
        # Foot: lFoot hangs from ToeIK <- FootIK; ToeIK stays at rest.
        foot = T(f'{s}Foot') @ np.linalg.inv(Mr[f'{s}Foot']) @ Mr[f'FootIK.{S_}']
        from_pose(f'FootIK.{S_}', foot, root)
        toeik = foot @ np.linalg.inv(Mr[f'FootIK.{S_}']) @ Mr[f'ToeIK.{S_}']
        from_pose(f'{s}Toe', T(f'{s}Toe'), toeik)
        # Poles
        for pole, upper, elbow, sh, wr in ((f'ElbowIK.{S_}', f'{s}ShldrTwist', f'Elbow.{S_}', f'{s}ShldrBend', f'{s}Hand'),
                                           (f'KneeIK.{S_}', f'{s}ThighTwist', f'Knee.{S_}', f'{s}ThighBend', f'{s}Foot')):
            Hw = r['Hw']
            P = pole_positions(Hw[:, idx[sh]], Hw[:, idx[elbow]], Hw[:, idx[wr]],
                               r['Rw'][:, idx[upper]], Mr[upper][:3, :3],
                               Mr[pole][:3, 3], Mr[elbow][:3, 3])
            pose = rest_pose(pole)
            pose[:, :3, 3] = P
            from_pose(pole, pose, root)
    for n in REST_KEYED:
        basis[n] = np.repeat(np.eye(4)[None], F, 0)
    return basis


# ----------------------------------------------------------------------------- actions

def new_fcurve(action, arm, path, index, group):
    if hasattr(action, 'fcurve_ensure_for_datablock'):  # Blender 4.4+ (slotted actions)
        return action.fcurve_ensure_for_datablock(arm, path, index=index, group_name=group)
    fc = action.fcurves.find(path, index=index)
    return fc or action.fcurves.new(path, index=index, action_group=group)


def write_curve(fc, frames, values):
    kp = fc.keyframe_points
    kp.add(len(frames))
    co = np.empty(2 * len(frames), np.float32)
    co[0::2] = frames
    co[1::2] = values
    kp.foreach_set('co', co)
    fc.update()


def to_channels(pb, B):
    """(F,4,4) basis -> dict of channel arrays matching the bone's rotation mode."""
    F = len(B)
    loc = B[:, :3, 3].copy()
    mode = pb.rotation_mode
    if mode == 'QUATERNION':
        rot = np.zeros((F, 4))
        prev = None
        for f in range(F):
            q = np.array(Matrix(B[f].tolist()).to_quaternion())
            if prev is not None and np.dot(q, prev) < 0:
                q = -q
            rot[f] = prev = q
        return dict(location=loc, rotation_quaternion=rot)
    if mode == 'AXIS_ANGLE':
        raise RuntimeError(f'{pb.name}: axis-angle rotation mode not supported')
    rot = np.zeros((F, 3))
    prev = None
    for f in range(F):
        m3 = Matrix(B[f].tolist()).to_3x3()
        e = m3.to_euler(mode, prev) if prev is not None else m3.to_euler(mode)
        rot[f] = e
        prev = e
    return dict(location=loc, rotation_euler=rot)


def new_action(arm, name):
    old = bpy.data.actions.get(name)
    if old is not None:
        bpy.data.actions.remove(old)
    act = bpy.data.actions.new(name)
    act.use_fake_user = True
    if arm.animation_data is None:
        arm.animation_data_create()
    arm.animation_data.action = act
    return act


def key_basis(arm, act, basis, F, keyed=None):
    frames = np.arange(1, F + 1, dtype=np.float32)
    for bname, B in basis.items():
        pb = arm.pose.bones[bname]
        constant = np.allclose(B, B[0], atol=1e-7)
        for prop, vals in to_channels(pb, B).items():
            path = pb.path_from_id(prop)
            for i in range(vals.shape[1]):
                fc = new_fcurve(act, arm, path, i, bname)
                if constant:
                    write_curve(fc, frames[:1], vals[:1, i])
                else:
                    write_curve(fc, frames, vals[:, i])
                if keyed is not None:
                    keyed.add((bname, prop, i))


def action_curves(act):
    if hasattr(act, 'fcurves'):  # Blender 4.3/4.4
        return list(act.fcurves)
    return [fc for layer in act.layers for strip in layer.strips
            for bag in strip.channelbags for fc in bag.fcurves]


def protect_actions(arm, actions, keyed, snapshot):
    """Give other actions one key for each channel the clips animate and they don't.

    Blender keeps un-animated channels at their last value when the active action
    changes: without this, switching from a clip back to the user's action would leave
    Torso, spine tweaks, hair... in the clip's last pose.  The key holds the value the
    channel had in the source file, so those actions look as before.
    """
    current = arm.animation_data.action
    for act in actions:
        have = {(fc.data_path, fc.array_index) for fc in action_curves(act)}
        arm.animation_data.action = act
        added = 0
        for bname, prop, i in sorted(keyed):
            pb = arm.pose.bones[bname]
            path = pb.path_from_id(prop)
            if (path, i) in have:
                continue
            fc = new_fcurve(act, arm, path, i, bname)
            write_curve(fc, np.array([act.frame_range[0]], np.float32), np.array([snapshot[bname][prop][i]]))
            added += 1
        print(f'"{act.name}": {added} rest keys added for channels animated only by the clips')
    arm.animation_data.action = current


def twist_about_y(R_parent, R_child, R0_parent, R0_child):
    """Twist angle (rad) of child about its own Y axis, relative to the rest relation."""
    D = (R0_parent.T @ R0_child).T @ (R_parent.T @ R_child)
    q = Matrix(D.tolist()).to_quaternion()
    return 2 * math.atan2(q.y, q.w)


def forearm_twist(arm, F):
    """Pronation for the forearm bones, measured on the evaluated IK result.

    The IK rolls the forearm with the elbow hinge while lHand copies the mocap hand
    orientation, so without this the whole difference would sit at the wrist.  The
    shares are the ones the rig uses itself when Root["Hand_control"] is 0.
    """
    sc = bpy.context.scene
    out = {}
    for s, S_ in (('l', 'L'), ('r', 'R')):
        ik2, hand = f'ArmIK2.{S_}', f'{s}Hand'
        R0p = np.array(arm.data.bones[ik2].matrix_local)[:3, :3]
        R0c = np.array(arm.data.bones[hand].matrix_local)[:3, :3]
        tau = np.zeros(F)
        for f in range(F):
            sc.frame_set(f + 1)
            tau[f] = twist_about_y(np.array(arm.pose.bones[ik2].matrix)[:3, :3],
                                   np.array(arm.pose.bones[hand].matrix)[:3, :3], R0p, R0c)
        tau = np.unwrap(tau)
        for bone, share in TWIST_SHARE.items():
            B = np.repeat(np.eye(4)[None], F, 0)
            c, sn = np.cos(share * tau), np.sin(share * tau)
            B[:, 0, 0], B[:, 0, 2], B[:, 2, 0], B[:, 2, 2] = c, sn, -sn, c
            out[s + bone] = B
    return out


def build_action(arm, name, basis, F, keyed, hair=True):
    act = new_action(arm, name)
    act.use_frame_range = True
    act.frame_start, act.frame_end = 1, F
    key_basis(arm, act, basis, F, keyed)
    key_basis(arm, act, forearm_twist(arm, F), F, keyed)
    if hair:
        key_basis(arm, act, hair_physics.simulate(arm, F), F, keyed)
    return act


# ----------------------------------------------------------------------------- checks

def verify(arm, bones, r, act):
    """Evaluate the action frame by frame and compare deform bones with the retarget."""
    idx = {b['name']: i for i, b in enumerate(bones)}
    sc = bpy.context.scene
    arm.animation_data.action = act
    names = [n for n in CHECK_BONES if n in idx]
    pos = {n: [] for n in names}
    ang = {n: [] for n in names}
    for f in range(r['F']):
        sc.frame_set(f + 1)
        for n in names:
            M = np.array(arm.pose.bones[n].matrix)
            Rt, Ht = r['Rw'][f, idx[n]], r['Hw'][f, idx[n]]
            pos[n].append(np.linalg.norm(M[:3, 3] - Ht))
            c = (np.trace(Rt.T @ M[:3, :3]) - 1) / 2
            ang[n].append(math.degrees(math.acos(max(-1, min(1, c)))))
    rows = []
    for n in names:
        rows.append((n, 1000 * np.mean(pos[n]), 1000 * np.max(pos[n]), np.mean(ang[n]), np.max(ang[n])))
    return rows


# ----------------------------------------------------------------------------- main

def main():
    a = parse_args()
    src = bpy.data.filepath
    out = os.path.abspath(bpy.path.abspath(a.out))
    if src and os.path.realpath(out) == os.path.realpath(src):
        raise SystemExit('Refusing to overwrite the source .blend: choose another --out path.')
    arm = bpy.data.objects[ARM_NAME]
    bones = rig_bones(arm)
    sc = bpy.context.scene
    # values of every pose channel in the source file, and the user's own actions
    snapshot = {pb.name: dict(location=list(pb.location), rotation_quaternion=list(pb.rotation_quaternion),
                              rotation_euler=list(pb.rotation_euler)) for pb in arm.pose.bones}
    user_actions = [act for act in bpy.data.actions if act.name not in a.clips]
    # keep the user's existing actions alive when Jean gets a new active action
    for act in user_actions:
        if act.users > 0 and not act.use_fake_user:
            act.use_fake_user = True
            print(f'fake user set on existing action "{act.name}"')
    sc.render.fps, sc.render.fps_base = FPS, 1.0
    made = []
    keyed = set()
    for clip in a.clips:
        path = os.path.join(a.bvh_dir, clip + '.bvh')
        t0 = time.time()
        r = retarget(bones, path, foot_bones=FOOT)
        if abs(r['fps'] - FPS) > 0.01:
            print(f'warning: {clip} is {r["fps"]:.2f} fps, keyed 1:1 at {FPS} fps')
        basis = solve_controls(arm, bones, r)
        act = build_action(arm, clip, basis, r['F'], keyed, hair=not a.no_hair)
        made.append((act, r))
        print(f'{clip}: {r["F"]} frames, {len(basis)} controls, {time.time() - t0:.1f}s')
    protect_actions(arm, user_actions, keyed, snapshot)
    first_act, first_r = made[0]
    arm.animation_data.action = first_act
    sc.frame_start, sc.frame_end = 1, first_r['F']
    if a.verify:
        for act, r in made:
            print(f'\nverify {act.name}: bone, mean/max head error mm, mean/max angle deg')
            for n, pm, px, am, ax in verify(arm, bones, r, act):
                print(f'  {n:14s} {pm:7.1f} {px:7.1f}   {am:6.1f} {ax:6.1f}')
        arm.animation_data.action = first_act
    sc.frame_set(1)
    bpy.ops.wm.save_as_mainfile(filepath=out, copy=True, compress=a.compress)
    print('saved', out)


if __name__ == '__main__':
    main()
