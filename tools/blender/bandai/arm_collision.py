"""Keep hands and forearms out of the chest (skin, breasts and top) in a keyed clip.

The capture actress has a much smaller chest than Neliel: when she puts a hand on her
chest, crosses her arms or holds her hands in front of her, Neliel's hand and forearm
end up inside the breasts.  After the controls are keyed, every frame is evaluated and
the deformed forearm/hand vertices are tested against the deformed torso skin (nearest
vertex + normal), keeping the height of the top where it covers the skin.  Where they are inside, the HandIK control is moved out
by the smallest displacement that clears every penetrating vertex (plus MARGIN); the
elbow follows through the arm IK.  The displacement is spread over neighbouring frames
so the hand eases onto the surface instead of jumping, and the pass is repeated until
the remaining penetration is below TOLERANCE.
"""
import bpy
import numpy as np
from mathutils import kdtree

BODY = 'Body'
TOP = 'Fascia rifatta · superiore'
TORSO_BONES = ('chestLower', 'chestUpper', 'lPectoral', 'rPectoral', 'abdomenUpper', 'abdomenLower')
ARM_KEYS = ('Forearm', 'Hand', 'Carpal', 'Thumb', 'Index', 'Mid', 'Ring', 'Pinky')
SIDES = (('l', 'L'), ('r', 'R'))
MARGIN = 0.003        # clearance kept between hand and chest (armature units, ~3.6 mm)
TOLERANCE = 0.0015    # remaining penetration accepted after the last pass
REACH = 0.08          # deepest penetration looked for
LATERAL = 0.012       # a vertex counts only if it lies over the nearest surface vertex
TOP_COVER = 0.008     # skin vertices with top vertices this close are covered by the top
SPREAD = 6            # frames over which a correction eases in and out
SMOOTH = 2.5          # gaussian sigma (frames) of the correction
PASSES = 4
MAX_STEP = 1.25       # one correction moves the hand at most this times the deepest point
MAX_SHIFT = 0.09      # total correction of a hand (armature units, ~11 cm)
NEAR = 0.32           # frames with hand and forearm farther than this from the chest are skipped
SLOW_MODIFIERS = {'SUBSURF', 'SOLIDIFY', 'MASK'}


def _dominant(ob, bones):
    names = {g.index: g.name for g in ob.vertex_groups}
    out = []
    for v in ob.data.vertices:
        gs = [g for g in v.groups if names.get(g.group) in bones and g.weight > 0]
        out.append(names[max(gs, key=lambda g: g.weight).group] if gs else '')
    return out


def _evaluated(ob, inv):
    dg = bpy.context.evaluated_depsgraph_get()
    oe = ob.evaluated_get(dg)
    me = oe.to_mesh()
    n = len(me.vertices)
    c = np.empty(n * 3)
    me.vertices.foreach_get('co', c)
    nn = np.empty(n * 3)
    me.vertices.foreach_get('normal', nn)
    oe.to_mesh_clear()
    M = inv @ np.array(ob.matrix_world)
    c = c.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]
    nn = nn.reshape(-1, 3) @ M[:3, :3].T
    return c, nn / np.maximum(np.linalg.norm(nn, axis=1, keepdims=True), 1e-9)


def _tree(c):
    kd = kdtree.KDTree(len(c))
    for i, p in enumerate(c):
        kd.insert(p, i)
    kd.balance()
    return kd


class _Chest:
    def __init__(self, arm):
        self.arm = arm
        self.body = bpy.data.objects[BODY]
        self.top = bpy.data.objects.get(TOP)
        bones = {b.name for b in arm.data.bones}
        dom = _dominant(self.body, bones)
        self.torso = np.array([i for i, d in enumerate(dom) if d in TORSO_BONES])
        self.arm_idx = {s: np.array([i for i, d in enumerate(dom)
                                     if d[:1] == s and any(k in d for k in ARM_KEYS)]) for s, _ in SIDES}
        self.clear = None

    def _clearance(self, bc, bn, inv):
        """Clearance per torso vertex: MARGIN, plus the top's height where it covers the skin.

        The top itself is not tested: near its open edges the nearest top vertex has a
        normal along the band (up or down), which reported hands below the band as deep
        inside.  The cover is measured once; the top is skinned to the same bones.
        """
        c, n = bc[self.torso], bn[self.torso]
        extra = np.zeros(len(c))
        if self.top is not None:
            tc, _ = _evaluated(self.top, inv)
            kd = _tree(tc)
            for k, p in enumerate(c):
                found = kd.find_range(p, TOP_COVER)
                if found:
                    # height of the top above this skin vertex, along its normal
                    extra[k] = max(0.0, max(float(np.dot(np.array(q) - p, n[k])) for q, _, _ in found))
        return MARGIN + extra

    def penetration(self):
        """Per side: (depth, normal) arrays of forearm/hand vertices inside the chest."""
        inv = np.array(self.arm.matrix_world.inverted())
        bc, bn = _evaluated(self.body, inv)
        if self.clear is None:
            self.clear = self._clearance(bc, bn, inv)
        c, n = bc[self.torso], bn[self.torso]
        kd = _tree(c)
        out = {}
        pose = self.arm.pose.bones
        chest = np.array(pose['chestUpper'].head)
        for s, _ in SIDES:
            depth, normal = [], []
            pts = (np.array(pose[f'{s}Hand'].head), np.array(pose[f'{s}ForearmBend'].head))
            if min(np.linalg.norm(p - chest) for p in pts) > NEAR:
                out[s] = (np.zeros(0), np.zeros((0, 3)))
                continue
            for p in bc[self.arm_idx[s]]:
                _, i, d = kd.find(p)
                if d > REACH:
                    continue
                v = p - c[i]
                sd = float(np.dot(v, n[i]))
                if np.linalg.norm(v - sd * n[i]) > LATERAL:
                    continue
                if sd < self.clear[i]:
                    depth.append(self.clear[i] - sd)
                    normal.append(n[i])
            out[s] = (np.array(depth), np.array(normal).reshape(-1, 3))
        return out


def _clearing_vector(depth, normal, iters=12):
    """Displacement that clears the penetrating vertices in the least-squares sense.

    Minimises sum(max(0, depth_i - n_i.v)^2) + small * |v|^2 by re-solving on the
    vertices still inside; vertices pushing in opposite directions (a hand between the
    breasts) give a compromise instead of a runaway.  Capped at the deepest point.
    """
    v = np.zeros(3)
    if len(depth) == 0:
        return v
    w = depth / depth.max()          # deeper vertices count more
    inside = np.ones(len(depth), bool)
    for _ in range(iters):
        A = normal[inside] * w[inside, None]
        b = depth[inside] * w[inside]
        M = A.T @ A + 1e-3 * (w[inside] ** 2).sum() * np.eye(3)
        v = np.linalg.solve(M, A.T @ b)
        now = depth - normal @ v > 1e-5
        if not (now & ~inside).any():
            break
        inside |= now
    n = np.linalg.norm(v)
    cap = MAX_STEP * depth.max()
    return v if n <= cap else v * cap / n


def _ease(D):
    """Spread per-frame corrections over neighbouring frames, then smooth them."""
    F = len(D)
    A = D.copy()
    for k in range(1, SPREAD + 1):
        w = 1.0 - k / (SPREAD + 1)
        for sh in (k, -k):
            src = np.roll(D, sh, axis=0) * w
            if sh > 0:
                src[:sh] = 0
            else:
                src[sh:] = 0
            bigger = np.linalg.norm(src, axis=1) > np.linalg.norm(A, axis=1)
            A[bigger] = src[bigger]
    r = int(3 * SMOOTH)
    ker = np.exp(-0.5 * (np.arange(-r, r + 1) / SMOOTH) ** 2)
    ker /= ker.sum()
    pad = np.pad(A, ((r, r), (0, 0)), mode='edge')
    return np.stack([np.convolve(pad[:, j], ker, mode='valid') for j in range(3)], axis=1)[:F]


class _fast_body:
    def __enter__(self):
        self.saved = [m for n in (BODY, TOP) if n in bpy.data.objects
                      for m in bpy.data.objects[n].modifiers if m.type in SLOW_MODIFIERS and m.show_viewport]
        for m in self.saved:
            m.show_viewport = False
        return self

    def __exit__(self, *exc):
        for m in self.saved:
            m.show_viewport = True
        return False


def _to_basis(pb):
    """Matrix turning an armature-space offset into a location offset of pb."""
    rest = np.array(pb.bone.matrix_local)
    if pb.parent is None:
        return np.linalg.inv(rest[:3, :3])
    rest = np.linalg.inv(np.array(pb.parent.bone.matrix_local)) @ rest
    return np.linalg.inv((np.array(pb.parent.matrix) @ rest)[:3, :3])


def resolve(arm, F, basis, rekey):
    """Move HandIK keys of the active action so forearms and hands stay out of the chest.

    basis: the clip's control bases ({bone: (F,4,4)}), updated in place.
    rekey(bases): writes the given bases into the action again.
    Returns per side: frames corrected, largest correction and penetration before/after
    (armature units).
    """
    sc = bpy.context.scene
    chest = _Chest(arm)
    total = {S: np.zeros((F, 3)) for _, S in SIDES}
    conv = {S: np.zeros((F, 3, 3)) for _, S in SIDES}
    todo = np.ones(F, bool)
    first = None
    with _fast_body():
        for it in range(PASSES + 1):
            D = {S: np.zeros((F, 3)) for _, S in SIDES}
            worst = {S: 0.0 for _, S in SIDES}
            for f in np.nonzero(todo)[0]:
                sc.frame_set(int(f) + 1)
                pen = chest.penetration()
                for s, S in SIDES:
                    depth, normal = pen[s]
                    if len(depth):
                        worst[S] = max(worst[S], float(depth.max()) - MARGIN)
                        D[S][f] = _clearing_vector(depth, normal)
                    conv[S][f] = _to_basis(arm.pose.bones[f'HandIK.{S}'])
            if first is None:
                first = dict(worst)
            if it == PASSES or all(w <= TOLERANCE for w in worst.values()):
                break
            changed = {}
            for _, S in SIDES:
                if not D[S].any():
                    continue
                E = _ease(D[S])
                new = total[S] + E
                n = np.linalg.norm(new, axis=1, keepdims=True)
                new = np.where(n > MAX_SHIFT, new * MAX_SHIFT / np.maximum(n, 1e-9), new)
                E = new - total[S]
                total[S] = new
                name = f'HandIK.{S}'
                B = np.array(basis[name], dtype=float)
                if len(B) != F:
                    B = np.repeat(B[:1], F, axis=0)
                known = np.nonzero(np.abs(conv[S]).sum(axis=(1, 2)) > 0)[0]
                for f in np.nonzero(np.linalg.norm(E, axis=1) > 1e-7)[0]:
                    Cv = conv[S][f] if f in known else conv[S][known[np.argmin(np.abs(known - f))]]
                    B[f, :3, 3] += Cv @ E[f]
                basis[name] = B
                changed[name] = B
            if not changed:
                break
            rekey(changed)
            # next pass: only frames that a correction reached
            hit = np.zeros(F, bool)
            for _, S in SIDES:
                hit |= np.linalg.norm(total[S], axis=1) > 1e-7
            todo = hit
    stats = {}
    for _, S in SIDES:
        m = np.linalg.norm(total[S], axis=1)
        stats[S] = dict(frames=int((m > 1e-4).sum()), max_shift=float(m.max()),
                        before=first[S], after=worst[S])
    return stats
