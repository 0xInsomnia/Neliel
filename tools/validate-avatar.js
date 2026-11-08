import fs from 'node:fs';
import assert from 'node:assert/strict';
import validator from 'gltf-validator';

const bytes = fs.readFileSync(new URL('../assets/neliel.glb', import.meta.url));
const report = await validator.validateBytes(new Uint8Array(bytes), { maxIssues: 0 });
console.log(JSON.stringify({ bytes: bytes.length, errors: report.issues.numErrors,
  warnings: report.issues.numWarnings, infos: report.issues.numInfos, hints: report.issues.numHints,
  codes: [...new Set(report.issues.messages.map(message => message.code))] }, null, 2));
assert.equal(report.issues.numErrors, 0, 'glTF validation errors');
assert.equal(report.issues.numWarnings, 0, 'glTF validation warnings');
const gltf = JSON.parse(bytes.subarray(20, 20 + bytes.readUInt32LE(12)));
const nodes = new Set(gltf.nodes.map(node => node.name));
for (const name of ['J_Bip_C_Head', 'J_Bip_C_Chest', 'J_Bip_L_UpperArm', 'J_Bip_R_UpperArm',
  'J_Bip_L_LowerArm', 'J_Bip_R_LowerArm', 'J_Bip_R_Hand', 'J_Bip_L_UpperLeg',
  'J_Bip_R_UpperLeg', 'J_Bip_L_Foot', 'J_Bip_R_Foot', 'Coda',
  'Ponytail_0', 'Ponytail_1', 'Ponytail_2', 'Ponytail_3']) {
  assert.ok(nodes.has(name), `Missing rig node: ${name}`);
}
assert.ok(gltf.skins.length >= 1);
const face = gltf.meshes.find(mesh => mesh.name === 'Viso');
for (const name of ['smile', 'surprised', 'blink', 'wink']) {
  assert.ok(face.extras.targetNames.includes(name), `Missing expression: ${name}`);
}
for (const name of ['Pannelli', 'Stivali', 'Dettagli']) {
  assert.ok(gltf.materials.some(material => material.name === name));
}
assert.ok(gltf.images.every(image => image.bufferView !== undefined), 'Textures must be embedded');
console.log('PASS: complete articulated avatar, embedded textures and facial targets');
