import { Euler, Group, MathUtils, PropertyBinding, Quaternion } from '../vendor/three/three.module.min.js';
import { GLTFLoader } from '../vendor/three/addons/loaders/GLTFLoader.js';
import { applyAnimeMaterials } from './materials.js';

const poses = [
  { name: 'Neutra', head: 0, shoulder: .63 },
  { name: 'Curiosa', head: -.15, shoulder: .57 },
  { name: 'Dinamica', head: .10, shoulder: .51 },
];

const expressions = [
  { name: 'Neutra', weights: {} },
  { name: 'Sorridente', weights: { mouth_smile: .85, eyelid_smile1: .48 } },
  { name: 'Sorpresa', weights: { A: .65, eyelid_surprised: .92 } },
  { name: 'Occhiolino', weights: { eyelid_winkL: 1, mouth_smile: .56 } },
];

function rotationDriver(bone) {
  const rest = bone.quaternion.clone();
  const boneToWorld = bone.getWorldQuaternion(new Quaternion());
  const worldToBone = boneToWorld.clone().invert();
  const euler = new Euler();
  const offset = new Quaternion();
  return (x, y, z) => {
    offset.setFromEuler(euler.set(x, y, z)).premultiply(worldToBone).multiply(boneToWorld);
    bone.quaternion.copy(rest).multiply(offset);
  };
}

function nekoMaterialProfile(source) {
  const texture = source.map?.name ?? '';
  if (/tex_(Eye|Facial)_/i.test(texture)) return 'eyes';
  if (/tex_Head_/i.test(texture)) return 'face';
  if (/tex_Hair_/i.test(texture)) return 'hair';
  return 'fabric';
}

export async function loadNekoAvatar(url, reducedMotion) {
  const { scene } = await new GLTFLoader().loadAsync(url.href);
  scene.updateMatrixWorld(true);
  const bones = {};
  for (const [role, name] of Object.entries({
    head: 'Head1', left: 'L_UpperArm', right: 'R_UpperArm',
    forearm: 'R_Forearm', wrist: 'R_Hand',
  })) {
    const bone = scene.getObjectByName(PropertyBinding.sanitizeNodeName(`ValveBiped.Bip01_${name}`));
    if (!bone?.isBone) throw new Error(`Osso Neko mancante: ${name}`);
    bones[role] = rotationDriver(bone);
  }

  const faces = [];
  scene.traverse(mesh => {
    if (mesh.isSkinnedMesh) mesh.frustumCulled = false;
    if (mesh.morphTargetDictionary?.mouth_smile !== undefined) faces.push(mesh);
  });
  const outfit = scene.getObjectByName('Neliel_fuku_swimwear');
  if (!faces.length || !outfit?.isSkinnedMesh) throw new Error('Mesh o espressioni Neko mancanti');

  const materials = applyAnimeMaterials(scene, nekoMaterialProfile);
  const root = new Group();
  root.scale.setScalar(1.45);
  root.add(scene);

  let pose = 0;
  let expression = 0;
  let alternate = false;
  let time = 0;
  let waveTime = 0;
  let head = poses[0].head;
  let shoulder = poses[0].shoulder;
  return {
    root,
    setOutlines: enabled => materials.setOutlines(enabled),
    changePose() {
      pose = (pose + 1) % poses.length;
      return poses[pose].name;
    },
    changeExpression() {
      expression = (expression + 1) % expressions.length;
      return expressions[expression].name;
    },
    changeOutfit() {
      alternate = !alternate;
      outfit.material.color.set(alternate ? 0xc3a1ff : 0xffffff);
      return alternate ? 'Ametista' : 'Originale';
    },
    wave() { waveTime = 2.35; },
    update(delta) {
      time += delta;
      const motion = reducedMotion.matches ? 0 : 1;
      const elapsed = 2.35 - waveTime;
      const wave = waveTime > 0 ? MathUtils.smoothstep(Math.min(elapsed, waveTime), 0, .36) : 0;
      waveTime = Math.max(0, waveTime - delta);

      const goal = poses[pose];
      head = MathUtils.damp(head, goal.head, 11, delta);
      shoulder = MathUtils.damp(shoulder, goal.shoulder, 11, delta);
      bones.head(0, motion * Math.sin(time * 1.1) * .055, head);
      bones.left(0, 0, -shoulder);
      bones.right(0, 0, MathUtils.lerp(shoulder, -.25, wave));
      bones.forearm(0, .15 * wave, -1.65 * wave);
      bones.wrist(0, 0, .25 * wave * motion * Math.sin(elapsed * 15));

      const chosen = expressions[expression].weights;
      const blink = motion * Math.max(0, 1 - Math.abs((time + .7) % 4.8 - 2.4) / .108);
      for (const face of faces) {
        for (const [key, index] of Object.entries(face.morphTargetDictionary)) {
          const weight = key === 'blink' ? blink * (1 - (chosen.eyelid_winkL ?? 0)) : chosen[key] ?? 0;
          face.morphTargetInfluences[index] = MathUtils.damp(face.morphTargetInfluences[index], weight, 25, delta);
        }
      }
      materials.update();
    },
  };
}
