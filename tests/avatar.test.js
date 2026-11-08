import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { Vector3 } from '../vendor/three/three.module.min.js';
import { GLTFLoader } from '../vendor/three/addons/loaders/GLTFLoader.js';

// Parse the shipped geometry/rig using the actual loader, without a GPU or image decoder.
// Only material texture references are removed in this in-memory test copy.
async function loadGeometry() {
  const source = fs.readFileSync(new URL('../assets/neliel.glb', import.meta.url));
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

test('the production loader reconstructs finite skinned geometry and facial targets', async () => {
  const scene = await loadGeometry();
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

test('arm bones deform the mesh, and the long hair is bound to its own bone chain', async () => {
  const scene = await loadGeometry();
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
