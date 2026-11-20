"""Procedural finger poses for the Bandai clips (the mocap has no finger data).

Each finger of the rig is driven by its base bone (lIndex1, lMid1, lRing1, lPinky1,
lThumb1): the other phalanges copy its local rotation, so a base rotation curls the
whole finger.  lCarpal4 cups the palm (the other carpals copy part of it).

The hand is relaxed (fingers curled progressively from index to pinky) and opens
when it rises towards the chest or the arm reaches far from the body, as in waving
or showing the way.  The curl axis of every finger comes from the rest geometry:
perpendicular to the finger and to the palm normal, so fingers close towards the palm.
"""
import math

import numpy as np

# curl of each base bone in degrees (the two other phalanges copy it)
RELAXED = {'Thumb1': 8.0, 'Index1': 12.0, 'Mid1': 15.0, 'Ring1': 18.0, 'Pinky1': 21.0, 'Carpal4': 8.0}
OPEN = {'Thumb1': 2.0, 'Index1': 3.0, 'Mid1': 3.0, 'Ring1': 4.0, 'Pinky1': 5.0, 'Carpal4': 0.0}
# hand height between pelvis (0) and shoulder (1), and horizontal reach from the
# pelvis in arm lengths: the hand opens across these ranges
HEIGHT = (0.35, 0.7)
REACH = (0.85, 1.05)
SMOOTH = 0.15  # seconds, low-pass on the openness so fingers do not flicker
# movements where the arms swing high without a gesture: hands stay closed, a bit more
CLOSED_KINDS = ('run', 'dash')
CLOSED_CURL = 1.6


def _smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def _lowpass(x, fps, tau):
    a = 1.0 - math.exp(-1.0 / (fps * tau))
    y = x.copy()
    for i in range(1, len(y)):  # forward then backward: no lag
        y[i] = y[i - 1] + a * (y[i] - y[i - 1])
    for i in range(len(y) - 2, -1, -1):
        y[i] = y[i + 1] + a * (y[i] - y[i + 1])
    return y


def palm_normal(arm, s):
    """Unit normal of the palm side at rest (palms face down in the rest A-pose)."""
    B = arm.data.bones
    across = np.array(B[f'{s}Pinky1'].head_local - B[f'{s}Index1'].head_local)
    along = np.array(B[f'{s}Mid1'].tail_local - B[f'{s}Mid1'].head_local)
    n = np.cross(across, along)
    n /= np.linalg.norm(n)
    return n if n[2] < 0 else -n


def curl_axes(arm, s):
    """Local axis of each controlled bone that curls it towards the palm."""
    B = arm.data.bones
    n = palm_normal(arm, s)
    out = {}
    for key in RELAXED:
        b = B[f'{s}{key}']
        d = np.array(b.tail_local - b.head_local)
        d /= np.linalg.norm(d)
        a = np.cross(d, n)  # rotating d about d x n moves it towards n
        a /= np.linalg.norm(a)
        out[key] = np.array(b.matrix_local)[:3, :3].T @ a
    return out


def openness(arm, r, idx, s):
    """0 = relaxed, 1 = open, per frame, from the retargeted hand position."""
    B = arm.data.bones
    H = r['Hw']
    L = np.linalg.norm(np.array(B[f'{s}ShldrBend'].head_local) - np.array(B[f'{s}Hand'].head_local))
    zw = H[:, idx['DEF-spine'], 2]
    zs = H[:, idx[f'{s}ShldrBend'], 2]
    hand = H[:, idx[f'{s}Hand']]
    height = (hand[:, 2] - zw) / np.maximum(zs - zw, 1e-6)
    reach = np.linalg.norm(hand[:, :2] - H[:, idx['DEF-spine'], :2], axis=1) / L
    w = np.maximum(_smoothstep(*HEIGHT, height), _smoothstep(*REACH, reach))
    return _lowpass(w, r['fps'], SMOOTH)


def gesture_weight(arm, r, idx, kind):
    """Openness of the more open hand, 0 for movements without gestures (running)."""
    if kind in CLOSED_KINDS:
        return np.zeros(r['F'])
    return np.maximum(openness(arm, r, idx, 'l'), openness(arm, r, idx, 'r'))


def finger_bases(arm, r, idx, kind=''):
    """{bone: (F,4,4) matrix_basis} for the finger controls of both hands."""
    out = {}
    closed = kind in CLOSED_KINDS
    for s in 'lr':
        axes = curl_axes(arm, s)
        w = np.zeros(r['F']) if closed else openness(arm, r, idx, s)
        for key, ax in axes.items():
            relaxed = RELAXED[key] * (CLOSED_CURL if closed else 1.0)
            ang = np.radians(relaxed * (1 - w) + OPEN[key] * w)
            B = np.repeat(np.eye(4)[None], len(w), 0)
            c, sn = np.cos(ang), np.sin(ang)
            x, y, z = ax
            # Rodrigues rotation matrix about the fixed local axis, per frame
            B[:, 0, 0] = c + x * x * (1 - c)
            B[:, 0, 1] = x * y * (1 - c) - z * sn
            B[:, 0, 2] = x * z * (1 - c) + y * sn
            B[:, 1, 0] = y * x * (1 - c) + z * sn
            B[:, 1, 1] = c + y * y * (1 - c)
            B[:, 1, 2] = y * z * (1 - c) - x * sn
            B[:, 2, 0] = z * x * (1 - c) - y * sn
            B[:, 2, 1] = z * y * (1 - c) + x * sn
            B[:, 2, 2] = c + z * z * (1 - c)
            out[f'{s}{key}'] = B
    return out
