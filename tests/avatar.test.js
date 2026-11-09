import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { Vector3 } from '../vendor/three/three.module.min.js';
import { GLTFLoader } from '../vendor/three/addons/loaders/GLTFLoader.js';

// Parse the shipped geometry/rig using the actual loader, without a GPU or image decoder.
// Only material texture references are removed in this in-memory test copy.
async function loadGeometry(file) {
  const source = fs.readFileSync(new URL(`../assets/${file}`, import.meta.url));
  const jsonLength = source.readUInt32LE(12);
  const doc = JSON.parse(source.subarray(20, 20 + jsonLength));
  doc.materials = doc.materials.map(material => ({ name: material.name }));
  delete doc.textures;
  delete doc.images;
  const encoded = Buffer.from(JSON.stringify(doc));
  const json = Buffer.alloc(Math.ceil(encoded.length / 4) * 4, 32);
  encoded.copy(json);
  const binChunk = source.subarray(20 + jsonLength);
  const glb = Buffer.alloc(20 + json.length + binChunk.length);
  glb.writeUInt32LE(0x46546c67, 0); glb.writeUInt32LE(2, 4); glb.writeUInt32LE(glb.length, 8);
  glb.writeUInt32LE(json.length, 12); glb.writeUInt32LE(0x4e4f534a, 16);
  json.copy(glb, 20); binChunk.copy(glb, 20 + json.length);
  const { scene } = await new GLTFLoader().parseAsync(glb.buffer.slice(glb.byteOffset, glb.byteOffset + glb.length), '');
  scene.updateMatrixWorld(true);
  return scene;
}

for (const file of ['neliel.glb', 'neliel-refined.glb']) {
test(`${file}: the production loader reconstructs finite skinned geometry and facial targets`, async () => {
  const scene = await loadGeometry(file);
  let vertices = 0, skinned = 0, faces = 0;
  scene.traverse(mesh => {
    if (!mesh.isSkinnedMesh) return;
    skinned++;
    mesh.skeleton.update();
    const pos = mesh.geometry.attributes.position;
    for (let i = 0; i < pos.count; i++) {
      const v = mesh.applyBoneTransform(i, new Vector3().fromBufferAttribute(pos, i));
      assert.ok(v.toArray().every(Number.isFinite));
      assert.ok(v.length() < 4, 'rest geometry must not explode outside human-scale bounds');
      vertices++;
    }
    if (mesh.morphTargetDictionary?.smile !== undefined) faces++;
  });
  assert.ok(skinned >= 3 && vertices > 1000 && faces > 0);
});

test(`${file}: arm bones deform the mesh, and the long hair is bound to its own bone chain`, async () => {
  const scene = await loadGeometry(file);
  const samples = [];
  scene.traverse(mesh => {
    if (!mesh.isSkinnedMesh) return;
    const pos = mesh.geometry.attributes.position;
    for (let i = 0; i < pos.count; i += 10) {
      samples.push({ mesh, i, before: mesh.applyBoneTransform(i, new Vector3().fromBufferAttribute(pos, i)) });
    }
  });
  scene.getObjectByName('J_Bip_R_UpperArm').rotation.z = -.8;
  scene.updateMatrixWorld(true);
  const moved = samples.filter(({ mesh, i, before }) => {
    const after = mesh.applyBoneTransform(i, new Vector3().fromBufferAttribute(mesh.geometry.attributes.position, i));
    return after.distanceTo(before) > .01;
  });
  assert.ok(moved.length > 10, 'arm motion must deform vertices, not just an empty bone');
  const hair = scene.getObjectByName('Coda');
  assert.ok(hair.isSkinnedMesh);
  for (let i = 0; i < 4; i++) assert.ok(hair.skeleton.bones.some(bone => bone.name === `Ponytail_${i}`));
});


test(`${file}: each facial expression deforms vertices without invalid positions`, async () => {
  const scene = await loadGeometry(file);
  const faces = [];
  scene.traverse(mesh => {
    if (mesh.morphTargetDictionary?.smile !== undefined) faces.push(mesh);
  });
  for (const expression of ['smile', 'surprised', 'blink', 'wink']) {
    let changed = 0;
    for (const mesh of faces) {
      mesh.morphTargetInfluences.fill(0);
      const before = Array.from({length: mesh.geometry.attributes.position.count},
        (_, i) => mesh.getVertexPosition(i, new Vector3()));
      mesh.morphTargetInfluences[mesh.morphTargetDictionary[expression]] = 1;
      for (let i = 0; i < before.length; i++) {
        const after = mesh.getVertexPosition(i, new Vector3());
        assert.ok(after.toArray().every(Number.isFinite));
        assert.ok(after.distanceTo(before[i]) < .15, 'facial movement must remain local');
        if (after.distanceTo(before[i]) > .0001) changed++;
      }
    }
    assert.ok(changed > 10, `${expression} must move actual face vertices`);
  }
});
}

test('portrait locks follow the head without responding to arm movement', async () => {
  const scene = await loadGeometry('neliel-refined.glb');
  const locks = scene.getObjectByName('CioccheLaterali');
  assert.ok(locks?.isSkinnedMesh, 'temple locks must be an articulated mesh');
  const samples = [0, 199, 399, 599, 799];
  const positions = () => samples.map(i => locks.getVertexPosition(i, new Vector3()));
  const before = positions();
  scene.getObjectByName('J_Bip_R_UpperArm').rotation.z = -.8;
  scene.updateMatrixWorld(true);
  positions().forEach((v, i) => assert.ok(v.distanceTo(before[i]) < 1e-6));
  scene.getObjectByName('J_Bip_C_Head').rotation.z = .2;
  scene.updateMatrixWorld(true);
  const moved = positions();
  moved.forEach(v => assert.ok(v.toArray().every(Number.isFinite)));
  assert.ok(moved.every((v, i) => v.distanceTo(before[i]) > .001));
  // Rigid head binding must preserve distances along each lock.
  assert.ok(Math.abs(moved[0].distanceTo(moved[1]) - before[0].distanceTo(before[1])) < 1e-5);
});
