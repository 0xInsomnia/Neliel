import numpy as np


def _rot(axis, deg):
    a = np.radians(deg)
    c, s = np.cos(a), np.sin(a)
    if axis == 'X':
        return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])
    if axis == 'Y':
        return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def load_bvh(path):
    lines = open(path).read().split('\n')
    joints = []  # dict(name, parent, offset, channels)
    stack = []
    i = 0
    while i < len(lines):
        t = lines[i].split()
        if not t:
            i += 1
            continue
        if t[0] in ('ROOT', 'JOINT'):
            joints.append(dict(name=t[1], parent=stack[-1] if stack else -1, offset=None, channels=[], end=None))
            cur = len(joints) - 1
            i += 1
            continue
        if t[0] == 'End':
            # skip end site block
            depth = 0
            while True:
                i += 1
                tt = lines[i].split()
                if tt and tt[0] == 'OFFSET':
                    joints[stack[-1]]['end'] = np.array(list(map(float, tt[1:4])))
                if tt and tt[0] == '{':
                    depth += 1
                if tt and tt[0] == '}':
                    depth -= 1
                    if depth == 0:
                        break
            i += 1
            continue
        if t[0] == '{':
            stack.append(cur)
        elif t[0] == '}':
            stack.pop()
        elif t[0] == 'OFFSET':
            joints[cur]['offset'] = np.array(list(map(float, t[1:4])))
        elif t[0] == 'CHANNELS':
            joints[cur]['channels'] = t[2:]
        elif t[0] == 'MOTION':
            break
        i += 1
    n = int(lines[i + 1].split()[1])
    ft = float(lines[i + 2].split()[2])
    data = np.array([list(map(float, l.split())) for l in lines[i + 3:i + 3 + n] if l.strip()])
    return joints, data, ft


def fk(joints, data):
    """Return global rotations (F,J,3,3) and positions (F,J,3) in BVH space."""
    F = len(data)
    J = len(joints)
    R = np.zeros((F, J, 3, 3))
    P = np.zeros((F, J, 3))
    col = 0
    cols = []
    for j in joints:
        cols.append(col)
        col += len(j['channels'])
    for f in range(F):
        row = data[f]
        for ji, j in enumerate(joints):
            c0 = cols[ji]
            loc = j['offset'].copy()
            rot = np.eye(3)
            pos_set = {}
            for k, ch in enumerate(j['channels']):
                v = row[c0 + k]
                if ch.endswith('position'):
                    pos_set[ch[0]] = v
                else:
                    rot = rot @ _rot(ch[0], v)
            if pos_set:
                loc = np.array([pos_set.get('X', loc[0]), pos_set.get('Y', loc[1]), pos_set.get('Z', loc[2])])
            p = j['parent']
            if p < 0:
                R[f, ji] = rot
                P[f, ji] = loc
            else:
                R[f, ji] = R[f, p] @ rot
                P[f, ji] = P[f, p] + R[f, p] @ loc
    return R, P
