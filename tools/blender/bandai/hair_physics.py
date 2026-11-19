"""Baked spring physics for the hair bones of the Neliel rig.

The hair mesh is driven by MMD bone chains under the head bone (頭).  Each bone is
simulated as a lever from its head to the far end of the hair it moves (the bones are
shorter than the hair they drive), with:

- inertia and drag (the hair lags and swings after head/body motion),
- a spring back to the rest shape carried by the parent bone,
- gravity measured relative to the rest pose, so an upright head keeps the modelled
  shape and a bowed head lets the hair hang,
- collisions with the deformed body and head surfaces (nearest vertex + normal).

The result is keyed as rotations of the hair bones in the Action, like every other
channel, so it plays and can be edited per clip.  Parameters are in CHAINS.
"""
import math

import bpy
import numpy as np
from mathutils import Matrix, Quaternion, kdtree

# bones root -> tip; per bone: stiffness (1/s^2), drag (per substep), gravity factor,
# collision radius (m, armature space).  Lower stiffness = looser hair.
CHAINS = {
    'coda': [('Bip31', 300.0, 0.03, 1.0, 0.0),
             ('Bip40', 18.0, 0.025, 1.0, 0.035),
             ('Bip41', 10.0, 0.025, 1.0, 0.035),
             ('Bip42', 8.0, 0.025, 1.0, 0.03)],
    'ciocca destra': [('Bip29', 600.0, 0.2, 0.3, 0.012),
                      ('Bip36', 500.0, 0.2, 0.3, 0.012),
                      ('Bip37', 400.0, 0.2, 0.3, 0.012)],
    'ciocca sinistra': [('Bip30', 600.0, 0.2, 0.3, 0.012),
                        ('Bip38', 500.0, 0.2, 0.3, 0.012),
                        ('Bip39', 400.0, 0.2, 0.3, 0.012)],
}
HAIR_MESH = 'hair'
COLLIDERS = ['Body', 'head']
# surfaces each chain collides with: the side locks move with the head mesh already,
# and contacts with cheek and jaw only made them flip
CHAIN_COLLIDERS = {'coda': ['Body', 'head'], 'ciocca destra': ['Body'], 'ciocca sinistra': ['Body']}
BONE_COLLIDERS = {b: CHAIN_COLLIDERS[ch] for ch, bones in CHAINS.items() for b, *_ in bones}
# largest push out of the body per substep (None = at once); the stiff side locks are
# moved out gradually so a contact does not make them pop
CHAIN_MAX_PUSH = {'coda': None, 'ciocca destra': 0.003, 'ciocca sinistra': 0.003}
BONE_MAX_PUSH = {b: CHAIN_MAX_PUSH[ch] for ch, bones in CHAINS.items() for b, *_ in bones}
# largest bend (degrees) of a bone away from its rest direction under the parent
CHAIN_MAX_ANGLE = {'coda': None, 'ciocca destra': 70.0, 'ciocca sinistra': 70.0}
BONE_MAX_ANGLE = {b: CHAIN_MAX_ANGLE[ch] for ch, bones in CHAINS.items() for b, *_ in bones}
SUBSTEPS = 4
PREROLL = 60          # substeps run on the first frame so the clip starts settled
GRAVITY = 9.81        # m/s^2, divided by the armature scale below
SLOW_MODIFIERS = {'SUBSURF', 'SOLIDIFY', 'MASK'}


def _rot_between(a, b):
    a = a / np.linalg.norm(a)
    b = b / np.linalg.norm(b)
    v = np.cross(a, b)
    c = float(np.dot(a, b))
    if c < -0.999999:
        ax = np.cross(a, [1.0, 0, 0])
        if np.linalg.norm(ax) < 1e-6:
            ax = np.cross(a, [0, 1.0, 0])
        ax /= np.linalg.norm(ax)
        return 2 * np.outer(ax, ax) - np.eye(3)
    vx = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + vx + vx @ vx / (1 + c)


def _levers(arm, bones):
    """Far end of the hair each bone moves, in armature space (rest pose)."""
    o = bpy.data.objects[HAIR_MESH]
    M = np.array(arm.matrix_world.inverted() @ o.matrix_world)
    names = {g.index: g.name for g in o.vertex_groups}
    # rest shape including the shape keys (the ponytail length comes from them):
    # evaluate the mesh with its armature modifiers switched off
    arm_mods = [m for m in o.modifiers if m.type == 'ARMATURE' and m.show_viewport]
    for m in arm_mods:
        m.show_viewport = False
    try:
        bpy.context.view_layer.update()
        oe = o.evaluated_get(bpy.context.evaluated_depsgraph_get())
        me = oe.to_mesh()
        co = np.empty(len(me.vertices) * 3)
        me.vertices.foreach_get('co', co)
        oe.to_mesh_clear()
    finally:
        for m in arm_mods:
            m.show_viewport = True
        bpy.context.view_layer.update()
    co = co.reshape(-1, 3)
    if len(co) != len(o.data.vertices):
        raise RuntimeError('hair mesh topology changes in evaluation; disable topology modifiers')
    co = co @ M[:3, :3].T + M[:3, 3]
    owned = {b: [] for b in bones}
    for v in o.data.vertices:
        gs = [g for g in v.groups if names.get(g.group) in owned and g.weight > 0.3]
        if gs:
            owned[names[max(gs, key=lambda g: g.weight).group]].append(v.index)
    out = {}
    for b in bones:
        head = np.array(arm.data.bones[b].head_local)
        pts = co[owned[b]] if owned[b] else np.array([arm.data.bones[b].tail_local])
        d = np.linalg.norm(pts - head, axis=1)
        far = pts[d >= np.quantile(d, 0.8)] if len(pts) > 5 else pts
        out[b] = far.mean(axis=0)
    return out


class _Surface:
    """Deformed collider vertices with normals, in armature space, for nearest queries."""

    def __init__(self, arm):
        self.arm = arm
        self.objs = [bpy.data.objects[n] for n in COLLIDERS if n in bpy.data.objects]

    def update(self):
        dg = bpy.context.evaluated_depsgraph_get()
        self.parts = {}
        inv = np.array(self.arm.matrix_world.inverted())
        for o in self.objs:
            oe = o.evaluated_get(dg)
            me = oe.to_mesh()
            n = len(me.vertices)
            c = np.empty(n * 3)
            me.vertices.foreach_get('co', c)
            nn = np.empty(n * 3)
            me.vertices.foreach_get('normal', nn)
            oe.to_mesh_clear()
            M = inv @ np.array(o.matrix_world)
            c = c.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]
            nn = nn.reshape(-1, 3) @ M[:3, :3].T
            nn /= np.maximum(np.linalg.norm(nn, axis=1, keepdims=True), 1e-9)
            keep = c[:, 2] > 0.6
            c, nn = c[keep], nn[keep]
            kd = kdtree.KDTree(len(c))
            for i, p in enumerate(c):
                kd.insert(p, i)
            kd.balance()
            self.parts[o.name] = (c, nn, kd)

    def signed(self, p, names=COLLIDERS):
        """Signed distance along the normal of the nearest collider vertex."""
        best = None
        for n in names:
            if n not in self.parts:
                continue
            c, nn, kd = self.parts[n]
            _, i, dist = kd.find(p)
            if best is None or dist < best[0]:
                best = (dist, float(np.dot(p - c[i], nn[i])), nn[i])
        return best[1], best[2]


class HairSim:
    def __init__(self, arm):
        self.arm = arm
        self.scale = arm.matrix_world.to_scale()[2]
        self.g = np.array([0, 0, -GRAVITY / self.scale])
        bones = [b for ch in CHAINS.values() for b, *_ in ch]
        self.rest = {b.name: np.array(b.matrix_local) for b in arm.data.bones}
        lever_pts = _levers(arm, bones)
        self.lever_local = {b: np.linalg.inv(self.rest[b]) @ np.append(lever_pts[b], 1.0) for b in bones}
        self.surface = _Surface(arm)
        self.radius = {}

    # -- helpers
    def _carried(self, parent_pose, parent, b):
        return parent_pose @ np.linalg.inv(self.rest[parent]) @ self.rest[b]

    def _chain_root_pose(self, chain, poses):
        first = chain[0][0]
        parent = self.arm.data.bones[first].parent.name
        if parent in poses:
            return parent, poses[parent]
        # parent outside the simulated set (e.g. Bip31.001 under 頭): carried rigidly from 頭
        pp = self.arm.data.bones[parent].parent.name
        return parent, self._carried(poses[pp], pp, parent)

    def calibrate(self):
        """Collision radius per lever, never larger than the rest clearance."""
        self.surface.update()
        for ch in CHAINS.values():
            for b, k, drag, gf, r in ch:
                rest_end = (self.rest[b] @ self.lever_local[b])[:3]
                head = self.rest[b][:3, 3]
                rr = []
                for frac in (0.5, 1.0):
                    d0, _ = self.surface.signed(head + (rest_end - head) * frac, BONE_COLLIDERS[b])
                    rr.append(None if (r <= 0 or d0 < 0.002) else min(r, d0 - 0.002))
                self.radius[b] = rr

    def run(self, F):
        """Simulate frames 1..F of the active action; return {bone: (F,4,4) matrix_basis}."""
        sc = bpy.context.scene
        arm = self.arm
        root = '頭'
        out = {b: np.zeros((F, 4, 4)) for ch in CHAINS.values() for b, *_ in ch}
        x = {}
        xp = {}
        tp = {}
        dt = 1.0 / sc.render.fps / SUBSTEPS
        prev_root = None
        for f in range(F):
            sc.frame_set(f + 1)
            self.surface.update()
            cur_root = np.array(arm.pose.bones[root].matrix)
            if prev_root is None:
                prev_root = cur_root
            steps = PREROLL if f == 0 else SUBSTEPS
            for s in range(steps):
                t = 1.0 if f == 0 else (s + 1) / SUBSTEPS
                Rr = _slerp_mat(prev_root[:3, :3], cur_root[:3, :3], t)
                Pr = np.eye(4)
                Pr[:3, :3] = Rr
                Pr[:3, 3] = prev_root[:3, 3] * (1 - t) + cur_root[:3, 3] * t
                poses = {root: Pr}
                for ch in CHAINS.values():
                    parent, ppose = self._chain_root_pose(ch, poses)
                    for b, k, drag, gf, _ in ch:
                        C = self._carried(ppose, parent, b)
                        h = C[:3, 3]
                        target = (C @ self.lever_local[b])[:3]
                        L = np.linalg.norm(target - h)
                        if b not in x:
                            x[b] = target.copy()
                            xp[b] = target.copy()
                            tp[b] = target.copy()
                        Rh = C[:3, :3] @ self.rest[b][:3, :3].T
                        g_eff = gf * (self.g - Rh @ self.g)
                        # displacement per substep; drag acts on the motion relative to the
                        # carried target, so steady walking adds no lag but accelerations swing
                        vt = target - tp[b]
                        v = vt if (f == 1 and s == 0) else x[b] - xp[b]
                        v = v - drag * (v - vt)
                        nx = x[b] + v + (k * (target - x[b]) + g_eff) * dt * dt
                        nx = h + (nx - h) / max(np.linalg.norm(nx - h), 1e-9) * L
                        for frac, r in zip((0.5, 1.0), self.radius[b]):
                            if r is None:
                                continue
                            p = h + (nx - h) * frac
                            d, n = self.surface.signed(p, BONE_COLLIDERS[b])
                            if d < r:
                                push = (r - d) / frac
                                if BONE_MAX_PUSH[b] is not None and f > 0:
                                    push = min(push, BONE_MAX_PUSH[b])
                                nx = nx + n * push
                                nx = h + (nx - h) / max(np.linalg.norm(nx - h), 1e-9) * L
                        lim = BONE_MAX_ANGLE[b]
                        if lim is not None:
                            a0, a1 = target - h, nx - h
                            cosang = np.dot(a0, a1) / (np.linalg.norm(a0) * np.linalg.norm(a1))
                            ang = math.degrees(math.acos(max(-1.0, min(1.0, cosang))))
                            if ang > lim:
                                S = _rot_between(a0, a1)
                                q = Matrix(S.tolist()).to_quaternion()
                                q = Quaternion((1, 0, 0, 0)).slerp(q, lim / ang)
                                nx = h + np.array(q.to_matrix()) @ a0
                        xp[b], x[b], tp[b] = x[b], nx, target
                        P = np.eye(4)
                        P[:3, :3] = _rot_between(target - h, nx - h) @ C[:3, :3]
                        P[:3, 3] = h
                        poses[b] = P
                        parent, ppose = b, P
            prev_root = cur_root
            for b in out:
                p = arm.data.bones[b].parent.name
                pp = poses[p] if p in poses else self._carried(poses[root], root, p)
                out[b][f] = np.linalg.inv(np.linalg.inv(self.rest[p]) @ self.rest[b]) @ np.linalg.inv(pp) @ poses[b]
        return out


def _slerp_mat(A, B, t):
    qa = Matrix(A.tolist()).to_quaternion()
    qb = Matrix(B.tolist()).to_quaternion()
    return np.array(qa.slerp(qb, t).to_matrix())


class fast_colliders:
    """Temporarily hide slow modifiers (subdivision, solidify, mask) while simulating."""

    def __init__(self):
        self.saved = []

    def __enter__(self):
        for n in COLLIDERS + [HAIR_MESH]:
            o = bpy.data.objects.get(n)
            if o is None:
                continue
            for m in o.modifiers:
                if m.type in SLOW_MODIFIERS and m.show_viewport:
                    self.saved.append(m)
                    m.show_viewport = False
        return self

    def __exit__(self, *exc):
        for m in self.saved:
            m.show_viewport = True
        return False


def simulate(arm, F):
    """Hair bone bases for frames 1..F of the action currently assigned to arm."""
    with fast_colliders():
        sim = HairSim(arm)
        # rest calibration with hair bones at rest
        saved_action = arm.animation_data.action
        arm.animation_data.action = None
        saved = {pb.name: pb.matrix_basis.copy() for pb in arm.pose.bones}
        for pb in arm.pose.bones:
            pb.matrix_basis = Matrix.Identity(4)
        bpy.context.view_layer.update()
        sim.calibrate()
        for pb in arm.pose.bones:
            pb.matrix_basis = saved[pb.name]
        arm.animation_data.action = saved_action
        return sim.run(F)


def penetration(arm, F, bones=None):
    """Fraction of frames where any hair lever point is inside the body (diagnostic)."""
    with fast_colliders():
        sim = HairSim(arm)
        sc = bpy.context.scene
        bones = bones or [b for ch in CHAINS.values() for b, *_ in ch if b != 'Bip31']
        bad = 0
        worst = 0.0
        for f in range(F):
            sc.frame_set(f + 1)
            sim.surface.update()
            hit = False
            for b in bones:
                M = np.array(arm.pose.bones[b].matrix)
                end = (M @ sim.lever_local[b])[:3]
                d, _ = sim.surface.signed(end, BONE_COLLIDERS[b])
                if d < 0:
                    hit = True
                    worst = min(worst, d)
            bad += hit
        return bad / F, worst
