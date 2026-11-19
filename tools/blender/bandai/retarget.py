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


def retarget(bones, bvh_path, ref_frame=0, foot_bones=None):
    joints, data, ft = load_bvh(bvh_path)
    Rs, Ps = fk(joints, data)
    names = [j['name'] for j in joints]
    F = len(data)
    # to blender space, meters
    G = np.einsum('ij,fkjl,ml->fkim', C, Rs, C)
    P = np.einsum('ij,fkj->fki', C, Ps) * 0.01

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
            if c is not None:
                d0 = P[ref_frame, c] - P[ref_frame, s]
                if np.linalg.norm(d0) > 1e-6:
                    Rcarry = rot_between(Rcarry[:, 1], d0) @ Rcarry
            Cal[i] = G[ref_frame, s].T @ Rcarry
        Rref[i] = Rcarry

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
    # skinning matrices (armature space): M = Pose @ Rest^-1
    return dict(Rw=Rw, Hw=Hw, fps=1.0 / ft, F=F, lp=lp, order=order, mapped=list(mapped.keys()))
