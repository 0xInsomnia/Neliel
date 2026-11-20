"""Face animation for the Bandai clips: blinks, gaze and expressions.

The visible anime head ("head" mesh) is shaped by MMD shape keys, not by the Daz face
bones, and in Blender 4.3 an armature Action cannot animate shape keys.  So the rig
gets four properties on the Root bone, keyed in each clip Action like any control,
and six shape keys are driven by them:

    Viso_ciglia        blink               -> ウィンク２, ｳｨﾝｸ２右 (neutral closed eyes)
    Viso_occhi_felici  happy closed eyes   -> ウィンク, ウィンク右 (smiling arcs)
    Viso_sorriso       smile               -> 口角上げ (from its value in the file to 1)
    Viso_bocca         open mouth          -> あ

With every property at 0 the face is exactly as in the source file.  The gaze is
keyed on the MMD eye control 両目.  Expressions per clip are in EXPRESSIONS: the mocap
has no face, so they are an interpretation and meant to be edited.
"""
import math
import zlib

import bpy
import numpy as np

PROPS = ('Viso_ciglia', 'Viso_occhi_felici', 'Viso_sorriso', 'Viso_bocca')
CONTROL_BONE = 'Root'
HEAD_MESH = 'head'
EYE_BONE = '両目'
# shape key -> (driver expression, variables); `base` is the value the key has in the file
DRIVEN = {
    'ウィンク': ('h', ('h',)),
    'ウィンク右': ('h', ('h',)),
    'ウィンク２': ('c*(1-h)', ('c', 'h')),
    'ｳｨﾝｸ２右': ('c*(1-h)', ('c', 'h')),
    '口角上げ': ('{base:.4f}+{rest:.4f}*s', ('s',)),
    'あ': ('b', ('b',)),
}
VAR_PROP = {'c': 'Viso_ciglia', 'h': 'Viso_occhi_felici', 's': 'Viso_sorriso', 'b': 'Viso_bocca'}

# expression at rest and at the peak of the gesture (hand raised / arm reaching, or the
# deepest point of a bow): smile, happy eyes, mouth
EXPRESSIONS = {
    'walk':    dict(rest=(0.2, 0.0, 0.0), gesture=(0.2, 0.0, 0.0)),
    'bow':     dict(rest=(0.25, 0.0, 0.0), gesture=(0.7, 0.35, 0.0)),
    'bye':     dict(rest=(0.3, 0.0, 0.0), gesture=(1.0, 0.3, 0.15)),
    'byebye':  dict(rest=(0.3, 0.0, 0.0), gesture=(1.0, 0.3, 0.2)),
    'respond': dict(rest=(0.2, 0.0, 0.0), gesture=(0.9, 0.15, 0.35)),
    'call':    dict(rest=(0.2, 0.0, 0.0), gesture=(0.5, 0.0, 0.7)),
    'guide':   dict(rest=(0.2, 0.0, 0.0), gesture=(0.8, 0.15, 0.1)),
}
FEMININE_HAPPY = 0.1        # extra happy-eye squint in the feminine clips during gestures
BLINK_EVERY = (1.8, 4.5)    # seconds between blinks (about 15-20 per minute)
BLINK_CURVE = (0.35, 0.75, 1.0, 0.6, 0.25)  # eyelid closure on consecutive frames (30 fps)
TURN_BLINK = 150.0          # deg/s of head turn that triggers a blink
SACCADE_EVERY = (0.8, 2.5)  # seconds between small gaze shifts
SACCADE_DEG = (3.0, 2.0)    # max horizontal / vertical gaze shift
LEAD_DEG = 6.0              # max lead of the eyes into a head turn
SMOOTH = 0.2                # seconds, low-pass on expressions


def _smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def _lowpass(x, fps, tau):
    a = 1.0 - math.exp(-1.0 / (fps * tau))
    y = x.astype(float).copy()
    for i in range(1, len(y)):
        y[i] = y[i - 1] + a * (y[i] - y[i - 1])
    for i in range(len(y) - 2, -1, -1):
        y[i] = y[i + 1] + a * (y[i] - y[i + 1])
    return y


# ----------------------------------------------------------------------------- rig setup

def setup(arm):
    """Add the Root properties and the shape key drivers (idempotent)."""
    pb = arm.pose.bones[CONTROL_BONE]
    for p in PROPS:
        if p not in pb.keys():
            pb[p] = 0.0
        ui = pb.id_properties_ui(p)
        ui.update(min=0.0, max=1.0, soft_min=0.0, soft_max=1.0, default=0.0,
                  description='Faccia (clip Bandai): 0 = come nel file originale')
    key = bpy.data.objects[HEAD_MESH].data.shape_keys
    kb = key.key_blocks
    for name, (expr, vars_) in DRIVEN.items():
        k = kb[name]
        path = f'key_blocks["{name}"].value'
        # the value in the source file is kept on the Key datablock, so a re-run on an
        # output file (where the key is already driven) still knows it
        store = f'neliel_base:{name}'
        if store not in key.keys():
            key[store] = k.value
        base = float(key[store])
        if key.animation_data and any(fc.data_path == path for fc in key.animation_data.drivers):
            key.driver_remove(path)
        fc = key.driver_add(path)
        for m in list(fc.modifiers):
            fc.modifiers.remove(m)
        d = fc.driver
        d.type = 'SCRIPTED'
        d.expression = expr.format(base=base, rest=1.0 - base)
        for v in vars_:
            var = d.variables.new()
            var.name = v
            var.type = 'SINGLE_PROP'
            var.targets[0].id_type = 'OBJECT'
            var.targets[0].id = arm
            var.targets[0].data_path = f'pose.bones["{CONTROL_BONE}"]["{VAR_PROP[v]}"]'
        k.value = base
    return [f'pose.bones["{CONTROL_BONE}"]["{p}"]' for p in PROPS]


# ----------------------------------------------------------------------------- animation

def _style(clip):
    kind = clip.split('_')[0]
    return EXPRESSIONS.get(kind, EXPRESSIONS['walk']), clip.endswith('feminine')


def _head_yaw_pitch(arm, r, idx):
    """Facing direction of the head over the clip (degrees): yaw positive to her left."""
    R0 = np.array(arm.data.bones['head'].matrix_local)[:3, :3]
    fwd_local = R0.T @ np.array([0.0, -1.0, 0.0])
    fwd = np.einsum('fij,j->fi', r['Rw'][:, idx['head']], fwd_local)
    yaw = np.degrees(np.unwrap(np.arctan2(fwd[:, 0], -fwd[:, 1])))
    pitch = np.degrees(np.arctan2(-fwd[:, 2], np.hypot(fwd[:, 0], fwd[:, 1])))
    return yaw, pitch


def _bow_weight(arm, r, idx):
    R0 = np.array(arm.data.bones['chestUpper'].matrix_local)[:3, :3]
    up_local = R0.T @ np.array([0.0, 0.0, 1.0])
    up = np.einsum('fij,j->fi', r['Rw'][:, idx['chestUpper']], up_local)
    forward_tilt = np.degrees(np.arctan2(-up[:, 1], up[:, 2]))  # leaning towards -Y
    return _smoothstep(15.0, 40.0, forward_tilt)


def animate(arm, r, idx, clip, gesture):
    """Per-frame values: {'props': {name: (F,)}, 'eyes': (F,4,4) matrix_basis of 両目}.

    `gesture` is the hand openness (0..1) per frame, from hand_pose.
    """
    F, fps = r['F'], r['fps']
    rng = np.random.RandomState(zlib.crc32(clip.encode()) & 0xffffffff)
    yaw, pitch = _head_yaw_pitch(arm, r, idx)
    turn = np.abs(np.gradient(yaw)) * fps + np.abs(np.gradient(pitch)) * fps

    # blinks: random intervals, plus one on fast head turns
    blink = np.zeros(F)
    starts = []
    t = rng.uniform(0.5, BLINK_EVERY[1]) * fps
    while t < F:
        starts.append(int(t))
        t += rng.uniform(*BLINK_EVERY) * fps
    for f in np.where(turn > TURN_BLINK)[0]:
        if all(abs(f - s) > 0.8 * fps for s in starts):
            starts.append(int(f))
    for s in starts:
        for k, v in enumerate(BLINK_CURVE):
            if 0 <= s + k < F:
                blink[s + k] = max(blink[s + k], v)

    # expressions follow the gesture (or the bow)
    style, feminine = _style(clip)
    w = np.maximum(gesture, _bow_weight(arm, r, idx)) if clip.startswith('bow') else gesture
    w = _lowpass(w, fps, SMOOTH)
    rest = np.array(style['rest'])
    peak = np.array(style['gesture']) + (np.array([0, FEMININE_HAPPY, 0]) if feminine else 0)
    expr = rest[None] + (peak - rest)[None] * w[:, None]
    smile, happy, mouth = (np.clip(_lowpass(expr[:, i], fps, SMOOTH), 0, 1) for i in range(3))

    # gaze: small saccades plus a lead into head turns
    sac = np.zeros((F, 2))
    cur = np.zeros(2)
    t = 0.0
    while t < F:
        nxt = t + rng.uniform(*SACCADE_EVERY) * fps
        cur = np.array([rng.uniform(-1, 1) * SACCADE_DEG[0], rng.uniform(-1, 1) * SACCADE_DEG[1]])
        sac[int(t):int(nxt)] = cur
        t = nxt
    sac = np.stack([_lowpass(sac[:, i], fps, 0.03) for i in range(2)], 1)  # fast but not instant
    look_ahead = int(round(0.17 * fps))
    lead = np.clip(0.6 * (np.r_[yaw[look_ahead:], np.repeat(yaw[-1], look_ahead)] - yaw), -LEAD_DEG, LEAD_DEG)
    eye_left = sac[:, 0] + lead        # degrees, towards her left
    eye_up = sac[:, 1]
    # 両目: rotating about its local X turns the eyes to her right, about Z upwards
    eyes = np.repeat(np.eye(4)[None], F, 0)
    ax, az = np.radians(-eye_left), np.radians(eye_up)
    for f in range(F):
        cx, sx, cz, sz = math.cos(ax[f]), math.sin(ax[f]), math.cos(az[f]), math.sin(az[f])
        Rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
        Rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
        eyes[f, :3, :3] = Rx @ Rz
    return dict(props=dict(Viso_ciglia=blink, Viso_occhi_felici=happy, Viso_sorriso=smile, Viso_bocca=mouth),
                eyes=eyes)
