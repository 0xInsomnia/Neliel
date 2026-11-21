"""Keep planted feet still (no sliding) in the retargeted clips.

For each foot the heel and the ball of the foot are tracked.  A point is in contact
when it is near its lowest height in the clip and almost still (with hysteresis).
While in contact, the point on the floor is locked: the heel while it is down (heel
strike and flat foot), the ball once the heel lifts or when the foot stays on its toes.  The lock is applied as a
horizontal shift of the foot (and its toes) in the retarget result, plus a turn
about the vertical axis that keeps the foot's heading from the moment it touched down
(the mocap foot twists slightly on the floor), so FootIK, the
knee pole and the checks all use the locked position; the IK bends the leg.

When the pivot changes (heel -> ball) the lock restarts from where the point is shown,
and after the contact the shift fades out over a few frames, so the foot never jumps.
A shift that would need a leg longer than the rig's is reduced.
"""
import numpy as np

# thresholds in metres / metres per second (world); converted with the armature scale
Z_ON, Z_OFF = 0.010, 0.020
V_ON, V_OFF = 0.25, 0.50
MIN_FRAMES = 3      # shorter contacts are ignored
GAP_FRAMES = 2      # shorter gaps inside a contact are filled
FADE_FRAMES = 5     # shift fades out over these frames after a contact
REACH = 0.995       # fraction of the full leg length the ankle may reach
LEG_CHAINS = {'l': ('ThighBend.L.001', 'Knee.L', 'ShinIK.L'), 'r': ('ThighBend.R.001', 'Knee.R', 'ShinIK.R')}


def _contacts(p, fps, scale):
    """Boolean contact per frame for a point track (F,3) in armature space."""
    h = (p[:, 2] - p[:, 2].min()) * scale
    v = np.r_[0, np.linalg.norm(np.diff(p[:, :2], axis=0), axis=1)] * fps * scale
    on = np.zeros(len(p), bool)
    state = False
    for f in range(len(p)):
        if not state and h[f] < Z_ON and v[f] < V_ON:
            state = True
        elif state and (h[f] > Z_OFF or v[f] > V_OFF):
            state = False
        on[f] = state
    # fill short gaps, drop short contacts
    f = 0
    while f < len(on):
        if not on[f]:
            g = f
            while g < len(on) and not on[g]:
                g += 1
            if 0 < f and g < len(on) and g - f <= GAP_FRAMES:
                on[f:g] = True
            f = g
        else:
            f += 1
    f = 0
    while f < len(on):
        if on[f]:
            g = f
            while g < len(on) and on[g]:
                g += 1
            if g - f < MIN_FRAMES:
                on[f:g] = False
            f = g
        else:
            f += 1
    return on


def _apply(p, th, c, tr):
    """Rotate the xy point p by th about c, then shift by tr."""
    cs, sn = np.cos(th), np.sin(th)
    d = p - c
    return c + np.array([cs * d[0] - sn * d[1], sn * d[0] + cs * d[1]]) + tr


def _subtree(lp, root):
    kids = {}
    for i, p in enumerate(lp):
        kids.setdefault(p, []).append(i)
    out, stack = [], [root]
    while stack:
        i = stack.pop()
        out.append(i)
        stack += kids.get(i, [])
    return out


def lock_feet(arm, bones, r):
    """Shift the feet in r['Hw'] so planted points stay still. Returns stats per side."""
    idx = {b['name']: i for i, b in enumerate(bones)}
    Mr = {b['name']: b['mat'] for b in bones}
    Rw, Hw, fps, F = r['Rw'], r['Hw'], r['fps'], r['F']
    scale = arm.matrix_world.to_scale()[2]
    stats = {}
    for s in 'lr':
        foot, toe = f'{s}Foot', f'{s}Toe'
        fi, ti = idx[foot], idx[toe]
        head_rest = Mr[foot][:3, 3]
        heel_rest = np.array([head_rest[0], head_rest[1] + 0.01, 0.0])
        heel = Hw[:, fi] + np.einsum('fij,j->fi', Rw[:, fi], Mr[foot][:3, :3].T @ (heel_rest - head_rest))
        ball = Hw[:, ti].copy()
        heel_on, ball_on = _contacts(heel, fps, scale), _contacts(ball, fps, scale)
        hip = Hw[:, idx[LEG_CHAINS[s][0]]]
        leg = sum(arm.data.bones[n].length for n in LEG_CHAINS[s])  # IK chain hip -> ankle
        heading = np.unwrap(np.arctan2(ball[:, 1] - heel[:, 1], ball[:, 0] - heel[:, 0]))
        # per-frame correction: rotate about c by th (vertical axis), then shift by tr
        th, tr, c = 0.0, np.zeros(2), heel[0, :2].copy()
        TH, TR, CC = np.zeros(F), np.zeros((F, 2)), np.zeros((F, 2))
        lock = yaw_lock = None
        shown = None  # where heel and ball were shown in the previous frame
        prev = None
        fade = None
        clamped = 0
        for f in range(F):
            pv = 'heel' if heel_on[f] else ('ball' if ball_on[f] else None)
            if pv is not None:
                P = (ball if pv == 'ball' else heel)[f, :2]
                if prev is None:
                    lock = _apply(P, th, c, tr)  # contact starts where the point is shown
                    yaw_lock = heading[f] + th
                elif pv != prev:
                    # heel -> ball: the ball stays where it was shown in the previous frame
                    # (the mocap ball already moves forward while the heel lifts)
                    lock = shown[pv].copy()
                c = P.copy()
                th = yaw_lock - heading[f]
                tr = lock - P
                fade = None
            else:
                if prev is not None:
                    fade = (th, tr.copy(), prev, 0)
                lock = None
                if fade is not None:
                    th0, tr0, last, k = fade
                    k += 1
                    u = min(1.0, k / FADE_FRAMES)
                    w = 1 - u * u * (3 - 2 * u)
                    th, tr = th0 * w, tr0 * w
                    c = (ball if last == 'ball' else heel)[f, :2].copy()
                    fade = (th0, tr0, last, k) if k < FADE_FRAMES else None
                else:
                    th, tr = 0.0, np.zeros(2)
            # keep the ankle reachable: never ask more leg than REACH, or than the mocap
            # itself already asks when the leg is straight
            ankle = Hw[f, fi]
            limit = max(REACH * leg, np.linalg.norm(ankle - hip[f]))

            def moved(sc):
                a = _apply(ankle[:2], th * sc, c, tr * sc)
                return np.linalg.norm(np.array([a[0], a[1], ankle[2]]) - hip[f])
            if moved(1.0) > limit:
                lo, hi = 0.0, 1.0
                for _ in range(20):
                    mid = 0.5 * (lo + hi)
                    lo, hi = (mid, hi) if moved(mid) <= limit else (lo, mid)
                th, tr = th * lo, tr * lo
                clamped += 1
            TH[f], TR[f], CC[f] = th, tr, c
            shown = {'heel': _apply(heel[f, :2], th, c, tr), 'ball': _apply(ball[f, :2], th, c, tr)}
            prev = pv
        sub = _subtree(r['lp'], fi)
        before = Hw[:, fi].copy()
        for f in range(F):
            cs, sn = np.cos(TH[f]), np.sin(TH[f])
            Rz = np.array([[cs, -sn, 0], [sn, cs, 0], [0, 0, 1]])
            for b in sub:
                Hw[f, b, :2] = _apply(Hw[f, b, :2], TH[f], CC[f], TR[f])
                Rw[f, b] = Rz @ Rw[f, b]
        shift = Hw[:, fi] - before
        stats[s] = dict(contacts=int(np.sum(np.diff(np.r_[0, (heel_on | ball_on).astype(int)]) == 1)),
                        clamped=clamped, max_shift_mm=float(1000 * scale * np.linalg.norm(shift, axis=1).max()),
                        max_turn_deg=float(np.degrees(np.abs(TH).max())))
    return stats
