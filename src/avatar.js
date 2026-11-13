import { Color, Group, MathUtils, SRGBColorSpace, TextureLoader } from '../vendor/three/three.module.min.js';
import { GLTFLoader } from '../vendor/three/addons/loaders/GLTFLoader.js';

const poses = [
  { name: 'Neutra', chest: 0, head: .025, left: 1.33, right: -1.36, leftElbow: .04, rightElbow: -.04 },
  { name: 'Curiosa', chest: -.045, head: -.11, left: 1.29, right: -1.46, leftElbow: .11, rightElbow: .10 },
  { name: 'Dinamica', chest: .035, head: .09, left: 1.13, right: -1.16, leftElbow: .17, rightElbow: -.18 },
];
const expressions = [
  { name: 'Neutra', weights: {} },
  { name: 'Sorridente', weights: { smile: .8 } },
  { name: 'Sorpresa', weights: { surprised: .83 } },
  { name: 'Occhiolino', weights: { wink: 1, smile: .58 } },
];

export async function loadAvatar(url, reducedMotion, prepareMaterials = () => null, { widen = 1.08, studyMap = null, stance = .048, lean = 0 } = {}) {
  const { scene } = await new GLTFLoader().loadAsync(url.href);
  const materialController = prepareMaterials(scene);
  const root = new Group();
  root.rotation.y = Math.PI;
  // The base 0.3 asset is stretched sideways; later revisions carry their own proportions.
  root.scale.x = widen;
  root.add(scene);
  const names = {
    chest: 'J_Bip_C_Chest', head: 'J_Bip_C_Head',
    left: 'J_Bip_L_UpperArm', right: 'J_Bip_R_UpperArm',
    leftElbow: 'J_Bip_L_LowerArm', rightElbow: 'J_Bip_R_LowerArm',
    wrist: 'J_Bip_R_Hand',
  };
  const bones = Object.fromEntries(Object.entries(names).map(([key, name]) => {
    const bone = scene.getObjectByName(name);
    if (!bone?.isBone) throw new Error(`Osso mancante: ${name}`);
    return [key, bone];
  }));
  bones.head.scale.set(.94, .96, .97);
  // Standing posture of the reference side view: the pelvis tips forward and
  // the spine arches back over it, so the legs slant behind the hips.
  scene.getObjectByName('J_Bip_C_Hips').rotation.x = -lean;
  scene.getObjectByName('J_Bip_C_Spine').rotation.x = lean * .6;
  bones.chest.rotation.x = lean * .4;
  for (const [side, angle] of [['L', -stance], ['R', stance]]) {
    const thigh = scene.getObjectByName(`J_Bip_${side}_UpperLeg`);
    const foot = scene.getObjectByName(`J_Bip_${side}_Foot`);
    thigh.rotation.z = angle;
    foot.rotation.z = -angle;
    foot.rotation.x = lean;
  }
  const tail = scene.getObjectByName('Coda');
  const hairBones = Array.from({ length: 4 }, (_, index) => scene.getObjectByName(`Ponytail_${index}`));
  const faces = [];
  const panels = new Set();
  const garments = [];
  let skin;
  scene.traverse(object => {
    if (['Pannelli', 'Stivali'].includes(object.material?.name)) garments.push(object);
    if (object.material?.name === 'Pelle e tessuto') skin = object.material;
    if (object.isSkinnedMesh) object.frustumCulled = false;
    if (object.morphTargetDictionary?.smile !== undefined) faces.push(object);
    if (['Pannelli', 'Stivali', 'Dettagli'].includes(object.material?.name)) panels.add(object.material);
  });
  if (!tail?.isSkinnedMesh || hairBones.some(bone => !bone?.isBone) || !faces.length || !panels.size) {
    throw new Error('Asset privo delle parti articolate richieste');
  }

  let pose = 0;
  let expression = 0;
  let look = 0;
  // Proportion study: the provisional outfit is replaced by a plain swimsuit.
  const paintedOutfit = skin?.map;
  let studyTexture;
  const setStudy = active => {
    if (active && !studyTexture) {
      studyTexture = new TextureLoader().load(studyMap.href);
      studyTexture.flipY = false;
      studyTexture.colorSpace = SRGBColorSpace;
    }
    for (const garment of garments) garment.visible = !active;
    skin.map = active ? studyTexture : paintedOutfit;
    skin.needsUpdate = true;
  };
  let waveTime = 0;
  let time = 0;
  const rest = { ...poses[0] };
  const palette = new Color();

  return {
    root,
    setOutlines: value => materialController?.setOutlines(value),
    changePose() {
      pose = (pose + 1) % poses.length;
      return poses[pose].name;
    },
    changeExpression() {
      expression = (expression + 1) % expressions.length;
      return expressions[expression].name;
    },
    changeOutfit() {
      look = (look + 1) % (studyMap && skin ? 3 : 2);
      const alternate = look === 1;
      if (studyMap && skin) setStudy(look === 2);
      palette.set(alternate ? 0xcfc3ff : 0xffffff);
      for (const material of panels) {
        material.color.copy(palette);
        material.emissive.set(alternate ? 0x382068 : 0x090414);
        material.emissiveIntensity = alternate ? .70 : .30;
      }
      return ['Notte', 'Ametista', 'Costume studio'][look];
    },
    changeHair() {
      tail.visible = !tail.visible;
      return tail.visible ? 'Lunghi' : 'Corti';
    },
    wave() { waveTime = 2.35; },
    update(delta) {
      materialController?.update();
      time += delta;
      const motion = reducedMotion.matches ? 0 : 1;
      const goal = poses[pose];
      for (const key of Object.keys(bones)) {
        if (key === 'wrist') continue;
        rest[key] = MathUtils.damp(rest[key], goal[key], motion ? 11 : 100, delta);
      }
      const elapsed = 2.35 - waveTime;
      const wave = waveTime > 0 ? MathUtils.smoothstep(Math.min(elapsed, waveTime), 0, .36) : 0;
      waveTime = Math.max(0, waveTime - delta);
      bones.chest.rotation.z = rest.chest + motion * Math.sin(time * 1.55) * .012;
      bones.head.rotation.set(-.025, motion * Math.sin(time * .86) * .072, rest.head);
      bones.left.rotation.set(.09, -.10, rest.left);
      bones.right.rotation.set(-.07, .12 + wave * .13, MathUtils.lerp(rest.right, -.36, wave));
      bones.leftElbow.rotation.set(0, -.12, rest.leftElbow);
      bones.rightElbow.rotation.set(wave * .12, .13 + wave * .19, MathUtils.lerp(rest.rightElbow, 1.59, wave));
      bones.wrist.rotation.z = wave * motion * Math.sin(elapsed * 15) * .27;
      for (const [index, bone] of hairBones.entries()) {
        bone.rotation.x = motion * Math.sin(time * 1.75 - index * .8) * .024;
        bone.rotation.z = motion * Math.sin(time * 1.32 - index * .62) * .036;
      }
      const chosen = expressions[expression].weights;
      const blink = motion * Math.max(0, 1 - Math.abs((time + .7) % 4.8 - 2.4) / .108);
      for (const face of faces) {
        for (const [key, index] of Object.entries(face.morphTargetDictionary)) {
          const weight = key === 'blink' ? blink * (1 - (chosen.wink ?? 0))
            : chosen[key] ?? (key === 'smile' ? wave * .54 : 0);
          face.morphTargetInfluences[index] = MathUtils.damp(face.morphTargetInfluences[index], weight, 25, delta);
        }
      }
    },
  };
}
