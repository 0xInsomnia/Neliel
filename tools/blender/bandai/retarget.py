"""Retarget Bandai Namco BVH clips onto the Neliel rig (armature space, Blender Z-up)."""
import numpy as np
from bvh import load_bvh, fk

C = np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]], float)  # BVH(Y-up, +Z fwd) -> Blender(Z-up, -Y fwd)

# target bone <- (source joint, source child for direction or None)
MAP = {
    'DEF-spine': ('Hips', 'Spine'),
    'abdomenLower': ('Spine', 'Chest'),
    'chestLower': ('Chest', 'Neck'),
    'neckLower': ('Neck', 'Head'),
    'head': ('Head', None),
}
for s, S_ in (('l', 'L'), ('r', 'R')):
    MAP.update({
        f'{s}Collar': (f'Shoulder_{S_}', f'UpperArm_{S_}'),
        f'{s}ShldrBend': (f'UpperArm_{S_}', f'LowerArm_{S_}'),
        f'{s}ForearmBend': (f'LowerArm_{S_}', f'Hand_{S_}'),
        f'{s}Hand': (f'Hand_{S_}', None),
        f'{s}ThighBend': (f'UpperLeg_{S_}', f'LowerLeg_{S_}'),
        f'{s}Shin': (f'LowerLeg_{S_}', f'Foot_{S_}'),
        f'{s}Foot': (f'Foot_{S_}', None),
        f'{s}Toe': (f'Toes_{S_}', None),
    })

# Torso bones keep the rig's rest posture at the calibration frame: aligning them to the
# mocap segment directions bent the pelvis back, the chest forward and the head back
# (the mocap spine curve differs from the character's).  Only the motion relative to the
# calibration frame is transferred to them.
KEEP_REST = ('DEF-spine', 'abdomenLower', 'chestLower', 'neckLower', 'head')
FEET = (('lFoot', 'lToe', 'L'), ('rFoot', 'rToe', 'R'))


def _pitch(v):
    """Angle below the horizontal (radians)."""
    return np.arctan2(-v[2], np.hypot(v[0], v[1]))


def planted_frame(heel, tip, fps, heel_g, toe_g):
    """Contact frame of a foot: ball on the floor, heel too if it ever is; least motion."""
    contact = tip[:, 2] < toe_g + 0.01
    flat = contact & (heel[:, 2] < heel_g + 0.01)
    cand = np.where(flat)[0] if flat.any() else np.where(contact)[0]
    if len(cand) == 0:
        return int(np.argmin(tip[:, 2]))
    speed = np.r_[0, np.linalg.norm(np.diff(tip[:, :2], axis=0), axis=1)] * fps
    return int(cand[np.argmin(speed[cand])])


def logical_parents(bones):
    idx = {b['name']: i for i, b in enumerate(bones)}
    lp = [b['parent'] for b in bones]
    ov = {}
    for s, S_ in (('l', 'L'), ('r', 'R')):
        ov.update({
            f'{s}ShldrTwist': f'{s}ShldrBend',
            f'Elbow.{S_}': f'{s}ShldrTwist',
            f'{s}ForearmTwist': f'{s}ForearmBend',
            f'{s}Hand': f'{s}ForearmTwist',
            # In the Neliel rig lThighTwist hangs from the IK bone ThighBend.L.001, not from
            # lThighBend: without this the knee and shin stayed rigid with the pelvis.
            f'{s}ThighTwist': f'{s}ThighBend',
            f'{s}Shin': f'{s}ThighTwist',
            f'Knee.{S_}': f'{s}ThighTwist',
            f'{s}Foot': f'{s}Shin',
            f'{s}Toe': f'{s}Foot',
            f'ToeIK.{S_}': f'{s}Toe',
        })
    for k, v in ov.items():
        if k in idx and v in idx:
            lp[idx[k]] = idx[v]
    # ArmIK2 must follow the upper arm (forearm bend hangs from it): parent Elbow already ok.
    # topological order
    order = []
    seen = set()

    def visit(i):
        if i in seen:
            return
        if lp[i] >= 0:
            visit(lp[i])
        seen.add(i)
        order.append(i)

    for i in range(len(bones)):
        visit(i)
    return lp, order


def rot_between(a, b):
    a = a / np.linalg.norm(a)
    b = b / np.linalg.norm(b)
    v = np.cross(a, b)
    c = np.dot(a, b)
    if c < -0.999999:
        # 180 deg: any orthogonal axis
        ax = np.cross(a, [1, 0, 0])
        if np.linalg.norm(ax) < 1e-6:
            ax = np.cross(a, [0, 1, 0])
        ax /= np.linalg.norm(ax)
        return 2 * np.outer(ax, ax) - np.eye(3)
    vx = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + vx + vx @ vx / (1 + c)


def _rot_axis(axis, ang):
    axis = axis / np.linalg.norm(axis)
    K = np.array([[0, -axis[2], axis[1]], [axis[2], 0, -axis[0]], [-axis[1], axis[0], 0]])
    return np.eye(3) + np.sin(ang) * K + (1 - np.cos(ang)) * K @ K


def ball_contact(bones, idx, lp, Rw, Hw, Rrest, Hrest, tails, tips, toe_g, g0):
    """Where the source ball of the foot is on the floor, pitch the rig foot about the
    ankle until it touches the floor too (the toes keep their orientation).

    With the character's proportions a foot on its ball (heel raised) otherwise hovered
    about 2 cm above the floor.
    """
    children = {i: [] for i in range(len(bones))}
    for i, p in enumerate(lp):
        if p >= 0:
            children[p].append(i)

    def subtree(i):
        out = [i]
        for c in children[i]:
            out += subtree(c)
        return out

    for foot, toe, S_ in FEET:
        if foot not in idx or toe not in idx:
            continue
        fi, ti = idx[foot], idx[toe]
        toe_set = subtree(ti)
        rot_set = [b for b in subtree(fi) if b not in toe_set]
        probe = [b for b in (fi, idx.get(foot[0] + 'Metatarsals'), ti) if b is not None]
        w = np.clip(1 - (tips[S_][:, 2] - toe_g) / 0.02, 0, 1)
        for f in range(len(Rw)):
            if w[f] <= 0:
                continue
            ankle = Hw[f, fi].copy()
            fwd = Rw[f, fi] @ Rrest[fi].T @ (tails[fi] - Hrest[fi])
            fwd[2] = 0
            if np.linalg.norm(fwd) < 1e-6:
                continue
            axis = np.cross([0, 0, 1.0], fwd)  # positive angle tips the toes down

            def lowest(ang):
                R = _rot_axis(axis, ang)
                pts = []
                for b in probe:
                    if b in rot_set:
                        h = ankle + R @ (Hw[f, b] - ankle)
                        rb = R @ Rw[f, b]
                    else:  # toe: moves with the foot, keeps its orientation
                        h = ankle + R @ (Hw[f, ti] - ankle) + (Hw[f, b] - Hw[f, ti])
                        rb = Rw[f, b]
                    pts += [h[2], (h + rb @ Rrest[b].T @ (tails[b] - Hrest[b]))[2]]
                return min(pts)

            gap = lowest(0.0) - g0
            if gap < 0.001:
                continue
            target = g0 + gap * (1 - w[f])
            lo, hi = 0.0, np.radians(35)
            if lowest(hi) > target:
                ang = hi
            else:
                for _ in range(14):
                    mid = 0.5 * (lo + hi)
                    lo, hi = (mid, hi) if lowest(mid) > target else (lo, mid)
                ang = hi
            R = _rot_axis(axis, ang)
            shift = ankle + R @ (Hw[f, ti] - ankle) - Hw[f, ti]
            for b in rot_set:
                Hw[f, b] = ankle + R @ (Hw[f, b] - ankle)
                Rw[f, b] = R @ Rw[f, b]
            for b in toe_set:
                Hw[f, b] = Hw[f, b] + shift


def retarget(bones, bvh_path, ref_frame=0, foot_bones=None, keep_rest=KEEP_REST, face_forward=True):
    joints, data, ft = load_bvh(bvh_path)
    Rs, Ps = fk(joints, data)
    names = [j['name'] for j in joints]
    F = len(data)
    # to blender space, meters
    G = np.einsum('ij,fkjl,ml->fkim', C, Rs, C)
    P = np.einsum('ij,fkj->fki', C, Ps) * 0.01
    if face_forward:
        # Turn the whole clip about the vertical so the hips face forward (-Y) at the
        # calibration frame.  Several clips start with the body turned 30-50 degrees,
        # which left the torso facing forward and the limbs turned.
        L = P[ref_frame, names.index('UpperLeg_L')] - P[ref_frame, names.index('UpperLeg_R')]
        a = -np.arctan2(L[1], L[0])
        Y = np.array([[np.cos(a), -np.sin(a), 0], [np.sin(a), np.cos(a), 0], [0, 0, 1]])
        G = np.einsum('ij,fkjl->fkil', Y, G)
        P = np.einsum('ij,fkj->fki', Y, P)

    idx = {b['name']: i for i, b in enumerate(bones)}
    lp, order = logical_parents(bones)
    NB = len(bones)
    Rrest = np.array([b['mat'][:3, :3] for b in bones])
    Hrest = np.array([b['head'] for b in bones])

    mapped = {idx[t]: (names.index(s), names.index(c) if c else None) for t, (s, c) in MAP.items() if t in idx}

    # ---- calibration at reference frame
    Rref = np.zeros((NB, 3, 3))
    Cal = {}
    for i in order:
        p = lp[i]
        if p >= 0:
            Rcarry = Rref[p] @ Rrest[p].T @ Rrest[i]
        else:
            Rcarry = Rrest[i]
        if i in mapped:
            s, c = mapped[i]
            if c is not None and bones[i]['name'] not in keep_rest:
                d0 = P[ref_frame, c] - P[ref_frame, s]
                if np.linalg.norm(d0) > 1e-6:
                    Rcarry = rot_between(Rcarry[:, 1], d0) @ Rcarry
            Cal[i] = G[ref_frame, s].T @ Rcarry
        Rref[i] = Rcarry

    # ---- feet: flat on the ground at a frame where the source foot is planted
    # Calibrating them at ref_frame copied the ankle angle of that instant (a lifted
    # foot when a clip starts mid-step) onto the whole clip: one planted foot ended
    # heel-down and the other on its toes, and the pelvis bobbed unevenly (limp).
    # A foot that never puts its heel down (feminine stance on the ball of the foot)
    # keeps its pitch relative to a flat foot of the same actor.
    tails = np.array([b['tail'] for b in bones])
    heels = {S_: P[:, names.index(f'Foot_{S_}')] for S_ in 'LR'}
    tips = {S_: P[:, names.index(f'Toes_{S_}')] for S_ in 'LR'}
    heel_g = min(h[:, 2].min() for h in heels.values())
    toe_g = min(t[:, 2].min() for t in tips.values())
    flat_pitches = np.concatenate([
        _pitch((tips[S_] - heels[S_])[(heels[S_][:, 2] < heel_g + 0.01) & (tips[S_][:, 2] < toe_g + 0.01)].T)
        for S_ in 'LR'])
    flat_pitch = float(np.median(flat_pitches)) if len(flat_pitches) else None
    for foot, toe, S_ in FEET:
        if foot not in idx:
            continue
        c = planted_frame(heels[S_], tips[S_], 1.0 / ft, heel_g, toe_g)
        d_src = tips[S_][c] - heels[S_][c]
        d_rig = tails[idx[foot]] - Hrest[idx[foot]]
        heading = np.arctan2(d_src[1], d_src[0])
        a = heading - np.arctan2(d_rig[1], d_rig[0])
        Yf = np.array([[np.cos(a), -np.sin(a), 0], [np.sin(a), np.cos(a), 0], [0, 0, 1]])
        pitch = _pitch(d_rig) + (_pitch(d_src) - flat_pitch if flat_pitch is not None else 0.0)
        d_t = np.array([np.cos(pitch) * np.cos(heading), np.cos(pitch) * np.sin(heading), -np.sin(pitch)])
        R_foot = rot_between(Yf @ d_rig, d_t) @ Yf @ Rrest[idx[foot]]
        Cal[idx[foot]] = G[c, names.index(f'Foot_{S_}')].T @ R_foot
        if toe in idx:  # toes lie on the floor at contact
            Cal[idx[toe]] = G[c, names.index(f'Toes_{S_}')].T @ Yf @ Rrest[idx[toe]]

    # ---- per-frame pose
    Rw = np.zeros((F, NB, 3, 3))
    Hw = np.zeros((F, NB, 3))
    root = idx['DEF-spine']
    hips = names.index('Hips')
    # scale root motion by leg length ratio
    tl = np.linalg.norm(Hrest[idx['lShin']] - Hrest[idx['lThighBend']]) + np.linalg.norm(Hrest[idx['lFoot']] - Hrest[idx['lShin']])
    sl = np.linalg.norm(P[ref_frame, names.index('LowerLeg_L')] - P[ref_frame, names.index('UpperLeg_L')]) + \
        np.linalg.norm(P[ref_frame, names.index('Foot_L')] - P[ref_frame, names.index('LowerLeg_L')])
    k = tl / sl
    for f in range(F):
        for i in order:
            p = lp[i]
            if i in mapped:
                Rw[f, i] = G[f, mapped[i][0]] @ Cal[i]
            elif p >= 0:
                Rw[f, i] = Rw[f, p] @ Rrest[p].T @ Rrest[i]
            else:
                Rw[f, i] = Rrest[i]
            if i == root:
                Hw[f, i] = Hrest[i] + k * (P[f, hips] - P[ref_frame, hips])
            elif p >= 0:
                Hw[f, i] = Hw[f, p] + Rw[f, p] @ Rrest[p].T @ (Hrest[i] - Hrest[p])
            else:
                Hw[f, i] = Hrest[i]
    # ---- ground contact: keep lowest foot point at rest ground level
    if foot_bones:
        fb = [idx[n] for n in foot_bones if n in idx]
        tails = np.array([b['tail'] for b in bones])
        def low(Rw_f, Hw_f):
            pts = []
            for i in fb:
                pts.append(Hw_f[i])
                pts.append(Hw_f[i] + Rw_f[i] @ Rrest[i].T @ (tails[i] - Hrest[i]))
            return min(p[2] for p in pts)
        g0 = min(min(Hrest[i][2], tails[i][2]) for i in fb)
        dz = np.array([g0 - low(Rw[f], Hw[f]) for f in range(F)])
        # light smoothing
        ker = np.ones(5) / 5
        dz = np.convolve(np.pad(dz, 2, mode='edge'), ker, mode='valid')
        Hw[:, :, 2] += dz[:, None]
        ball_contact(bones, idx, lp, Rw, Hw, Rrest, Hrest, tails, tips, toe_g, g0)
    # skinning matrices (armature space): M = Pose @ Rest^-1
    return dict(Rw=Rw, Hw=Hw, fps=1.0 / ft, F=F, lp=lp, order=order, mapped=list(mapped.keys()))
