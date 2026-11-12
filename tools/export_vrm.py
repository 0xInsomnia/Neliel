"""Export the refined model as VRM 0.0 for other apps (VRM viewers, Blender with
the VRM add-on, VSeeFace and similar).

The file is the same glTF with the VRM extension added: humanoid bone map from
the J_Bip_* rig, facial expressions mapped to VRM presets, the glTF materials
kept as they are (VRM_USE_GLTFSHADER), the ponytail chain as a spring bone.

Usage: python3 tools/export_vrm.py assets/neliel-refined.glb exports/neliel.vrm
"""
import sys
from refine_mesh import Asset

BONES = {
    'hips': 'J_Bip_C_Hips', 'spine': 'J_Bip_C_Spine', 'chest': 'J_Bip_C_Chest',
    'upperChest': 'J_Bip_C_UpperChest', 'neck': 'J_Bip_C_Neck', 'head': 'J_Bip_C_Head',
    'leftEye': 'J_Adj_L_FaceEye', 'rightEye': 'J_Adj_R_FaceEye',
}
for side, name in (('left', 'L'), ('right', 'R')):
    BONES.update({
        f'{side}Shoulder': f'J_Bip_{name}_Shoulder', f'{side}UpperArm': f'J_Bip_{name}_UpperArm',
        f'{side}LowerArm': f'J_Bip_{name}_LowerArm', f'{side}Hand': f'J_Bip_{name}_Hand',
        f'{side}UpperLeg': f'J_Bip_{name}_UpperLeg', f'{side}LowerLeg': f'J_Bip_{name}_LowerLeg',
        f'{side}Foot': f'J_Bip_{name}_Foot', f'{side}Toes': f'J_Bip_{name}_ToeBase',
    })
    for finger, vrm in (('Thumb', 'Thumb'), ('Index', 'Index'), ('Middle', 'Middle'), ('Ring', 'Ring'), ('Little', 'Little')):
        for joint, part in ((1, 'Proximal'), (2, 'Intermediate'), (3, 'Distal')):
            BONES[f'{side}{vrm}{part}'] = f'J_Bip_{name}_{finger}{joint}'

# VRM preset <- morph target of the face mesh. The 'wink' shape closes the
# character's left eye (the -x side).
EXPRESSIONS = [('Neutral', 'neutral', None), ('Joy', 'joy', 'smile'), ('Fun', 'fun', 'smile'),
               ('Surprised', 'unknown', 'surprised'), ('Blink', 'blink', 'blink'),
               ('Blink_L', 'blink_l', 'wink')]


def export(source, target):
    asset = Asset(source)
    doc = asset.d
    node = {n.get('name'): i for i, n in enumerate(doc['nodes'])}
    missing = [b for b in BONES.values() if b not in node]
    if missing:
        raise ValueError(f'Missing bones: {missing}')
    face = next(i for i, m in enumerate(doc['meshes']) if m['name'] == 'Viso')
    names = doc['meshes'][face]['extras']['targetNames']
    groups = []
    for name, preset, morph in EXPRESSIONS:
        binds = [] if morph is None else [{'mesh': face, 'index': names.index(morph), 'weight': 100}]
        groups.append({'name': name, 'presetName': preset, 'binds': binds, 'materialValues': [], 'isBinary': False})
    doc.setdefault('extensionsUsed', []).append('VRM')
    doc.setdefault('extensions', {})['VRM'] = {
        'exporterVersion': 'neliel-export-vrm-1', 'specVersion': '0.0',
        'meta': {'title': 'Neliel', 'version': doc['asset'].get('generator', ''), 'author': 'Neliel project',
                 'contactInformation': '', 'reference': '', 'allowedUserName': 'OnlyAuthor',
                 'violentUssageName': 'Disallow', 'sexualUssageName': 'Disallow',
                 'commercialUssageName': 'Disallow', 'otherPermissionUrl': '',
                 'licenseName': 'Redistribution_Prohibited', 'otherLicenseUrl': ''},
        'humanoid': {'humanBones': [{'bone': b, 'node': node[n], 'useDefaultValues': True} for b, n in BONES.items()],
                     'armStretch': .05, 'legStretch': .05, 'upperArmTwist': .5, 'lowerArmTwist': .5,
                     'upperLegTwist': .5, 'lowerLegTwist': .5, 'feetSpacing': 0, 'hasTranslationDoF': False},
        'firstPerson': {'firstPersonBone': node['J_Bip_C_Head'], 'firstPersonBoneOffset': {'x': 0, 'y': .06, 'z': 0},
                        'meshAnnotations': [], 'lookAtTypeName': 'Bone',
                        'lookAtHorizontalInner': {'curve': [0, 0, 0, 1, 1, 1, 1, 0], 'xRange': 90, 'yRange': 8},
                        'lookAtHorizontalOuter': {'curve': [0, 0, 0, 1, 1, 1, 1, 0], 'xRange': 90, 'yRange': 12},
                        'lookAtVerticalDown': {'curve': [0, 0, 0, 1, 1, 1, 1, 0], 'xRange': 90, 'yRange': 10},
                        'lookAtVerticalUp': {'curve': [0, 0, 0, 1, 1, 1, 1, 0], 'xRange': 90, 'yRange': 10}},
        'blendShapeMaster': {'blendShapeGroups': groups},
        'secondaryAnimation': {'boneGroups': [{'comment': 'Ponytail', 'stiffiness': .8, 'gravityPower': .2,
                                               'gravityDir': {'x': 0, 'y': -1, 'z': 0}, 'dragForce': .4,
                                               'center': -1, 'hitRadius': .03, 'bones': [node['Ponytail_0']],
                                               'colliderGroups': []}],
                               'colliderGroups': []},
        'materialProperties': [{'name': m['name'], 'shader': 'VRM_USE_GLTFSHADER', 'renderQueue': -1,
                                'floatProperties': {}, 'vectorProperties': {}, 'textureProperties': {},
                                'keywordMap': {}, 'tagMap': {}} for m in doc['materials']],
    }
    asset.write(target)
    print(f'Wrote {target}: {len(BONES)} humanoid bones, {len(groups)} expressions')


if __name__ == '__main__':
    export(*sys.argv[1:])
