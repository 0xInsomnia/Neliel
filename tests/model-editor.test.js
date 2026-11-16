import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import {
  buildGlb, humanoidBones, mainBoneLabel, mirrorName, parentScaleInChild, parseGlb, patchNodes, resolveScales, shortName,
} from '../model-editor/core.js';

const asset = new URL('../assets/neliel-refined.glb', import.meta.url);
const load = async () => { const file = await readFile(asset); return file.buffer.slice(file.byteOffset, file.byteOffset + file.byteLength); };

test('an unedited GLB survives a parse/build round trip byte for byte in its binary chunk', async () => {
  const source = await load();
  const { json, rest } = parseGlb(source);
  const again = parseGlb(buildGlb(json, rest));
  assert.deepEqual(again.json, json);
  assert.equal(again.rest.length, rest.length);
  assert.ok(Buffer.from(again.rest[0].data).equals(Buffer.from(rest[0].data)));
});

test('patching touches only the listed nodes and leaves the source JSON alone', async () => {
  const { json, rest } = parseGlb(await load());
  const head = json.nodes.findIndex(node => node.name === 'J_Bip_C_Head');
  const before = structuredClone(json);
  const patched = patchNodes(json, new Map([[head, { translation: [0, .1, 0], rotation: [0, 0, 0, 1], scale: [1.2, 1, 1] }]]));
  assert.deepEqual(json, before);
  assert.deepEqual(patched.nodes[head].scale, [1.2, 1, 1]);
  assert.deepEqual(patched.nodes[head].translation, [0, .1, 0]);
  patched.nodes[head] = json.nodes[head];
  assert.deepEqual(patched, json);
  const out = parseGlb(buildGlb(patched, rest));
  assert.equal(out.json.nodes.length, json.nodes.length);
});

test('a matrix node is rewritten as translation/rotation/scale', () => {
  const json = { nodes: [{ matrix: [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1] }] };
  const [node] = patchNodes(json, new Map([[0, { translation: [1, 2, 3], rotation: [0, 0, 0, 1], scale: [2, 2, 2] }]])).nodes;
  assert.deepEqual(node, { rotation: [0, 0, 0, 1], translation: [1, 2, 3], scale: [2, 2, 2] });
});

test('truncated or foreign files are rejected', async () => {
  assert.throws(() => parseGlb(new ArrayBuffer(8)), /valido/);
  const cut = (await load()).slice(0, 16384);
  assert.throws(() => parseGlb(cut), /troncato/);
});

test('body bones get Italian labels, secondary bones do not', () => {
  assert.equal(mainBoneLabel('J_Bip_C_Head'), 'Testa');
  assert.equal(mainBoneLabel('J_Bip_L_UpperArm'), 'Braccio sx');
  assert.equal(mainBoneLabel('J_Bip_R_LowerLeg'), 'Polpaccio dx');
  assert.equal(mainBoneLabel('J_Bip_C_UpperChest'), 'Petto alto');
  assert.equal(mainBoneLabel('mixamorig:LeftForeArm'), 'Avambraccio sx');
  assert.equal(mainBoneLabel('Bone.042', 'rightHand'), 'Mano dx');
  for (const name of ['J_Bip_L_Index1', 'J_Sec_L_Bust1', 'J_Adj_L_FaceEye', 'HairJoint-245c', 'Ponytail_0', 'J_Bip_L_ToeBase_end', 'J_Sec_L_LowerSleeve']) {
    assert.equal(mainBoneLabel(name), null, name);
  }
});

test('mirror names swap sides and ignore centre bones', () => {
  assert.equal(mirrorName('J_Bip_L_Hand'), 'J_Bip_R_Hand');
  assert.equal(mirrorName('J_Bip_R_Hand'), 'J_Bip_L_Hand');
  assert.equal(mirrorName('mixamorig:LeftArm'), 'mixamorig:RightArm');
  assert.equal(mirrorName('hand.L'), 'hand.R');
  assert.equal(mirrorName('J_Bip_C_Head'), null);
  assert.equal(mirrorName('Ponytail_0'), null);
  assert.equal(shortName('HairJoint-245c78de-5156-428a-a204-d0d365e05ba6'), 'HairJoint 245c78');
  assert.equal(shortName('J_Bip_C_Head'), 'J_Bip_C_Head');
});

test('VRM 0.x and 1.0 humanoid maps are both read', () => {
  assert.deepEqual([...humanoidBones({ extensions: { VRM: { humanoid: { humanBones: [{ bone: 'head', node: 4 }] } } } })], [[4, 'head']]);
  assert.deepEqual([...humanoidBones({ extensions: { VRMC_vrm: { humanoid: { humanBones: { hips: { node: 2 } } } } } })], [[2, 'hips']]);
  assert.equal(humanoidBones({}).size, 0);
});

const identity = [0, 0, 0, 1];
const part = (parent, multiplier, follows = false, rotation = identity) => ({ parent, baseScale: [1, 1, 1], rotation, multiplier, follows });
const close = (actual, expected) => actual.forEach((value, i) => assert.ok(Math.abs(value - expected[i]) < 1e-9, `${actual} vs ${expected}`));

test('an independent child cancels its parent, a following child inherits it', () => {
  const scales = resolveScales([part(-1, [2, 1, 1]), part(0, [1, 1, 1]), part(0, [1, 1.5, 1], true), part(2, [1, 1, 1])]);
  close(scales[0], [2, 1, 1]);
  close(scales[1], [.5, 1, 1]);   // world size stays 1
  close(scales[2], [1, 1.5, 1]);  // world size 2 × 1.5 × 1
  close(scales[3], [.5, 1 / 1.5, 1]);
});

test('parent scale is re-expressed in a child rotated by a quarter turn', () => {
  const quarterZ = [0, 0, Math.SQRT1_2, Math.SQRT1_2];
  close(parentScaleInChild([2, 3, 4], quarterZ), [3, 2, 4]);
  close(resolveScales([part(-1, [2, 3, 4]), part(0, [1, 1, 1], false, quarterZ)])[1], [1 / 3, 1 / 2, 1 / 4]);
});
