import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import { inflateSync } from 'node:zlib';
import {
  adjustPixels, buildGlb, buildNeighbours, colourMatrix, displaceZone, encodePng, falloff, humanoidBones, mainBoneLabel,
  mirrorName, pairInfluence, parentScaleInChild, parseGlb, patchMaterial, patchNodes, positionAccessorProblem, repackBuffer,
  resolveScales, sanitizeState, shortName, smoothPoints, weldVertices, writePositions,
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
  assert.equal(mainBoneLabel('J_Sec_L_Bust1'), 'Seno sx');
  assert.equal(mainBoneLabel('J_Sec_R_Bust1'), 'Seno dx');
  for (const name of ['J_Bip_L_Index1', 'J_Sec_L_Bust2', 'J_Adj_L_FaceEye', 'HairJoint-245c', 'Ponytail_0', 'J_Bip_L_ToeBase_end', 'J_Sec_L_LowerSleeve']) {
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

test('zone falloff is 1 at the centre, 0 at the edge and smooth between', () => {
  assert.equal(falloff(0, 2), 1);
  assert.equal(falloff(2, 2), 0);
  assert.equal(falloff(5, 2), 0);
  assert.ok(falloff(.5, 2) > falloff(1, 2) && falloff(1, 2) > falloff(1.9, 2));
});

test('a mirrored pair of zones never pushes harder than one zone', () => {
  const points = Float32Array.from([0, 0, 0, .5, 0, 0, -.5, 0, 0, 3, 0, 0, .9, 0, 0]);
  const pair = pairInfluence(points, [.5, 0, 0], [-.5, 0, 0], 1);
  assert.deepEqual([...pair.index], [0, 1, 2, 4]);
  pair.index.forEach((_, i) => assert.ok(pair.w1[i] + pair.w2[i] <= 1 + 1e-6));
  assert.ok(Math.abs(pair.w1[0] - pair.w2[0]) < 1e-6);          // midline: split evenly
  assert.ok(Math.abs(pair.w1[1] + pair.w2[1] - 1) < 1e-6);       // at a centre: full strength
  const single = pairInfluence(points, [.5, 0, 0], null, 1);
  assert.deepEqual([...single.index], [0, 1, 4]);
  assert.equal(single.w1[1], 1);
  assert.equal(single.w2[1], 0);
});

test('vertex positions are rewritten in the binary chunk and stay valid', async () => {
  const { json, rest } = parseGlb(await load());
  const index = json.meshes.find(mesh => mesh.name === 'Corpo').primitives[0].attributes.POSITION;
  assert.equal(positionAccessorProblem(json, index), null);
  const accessor = json.accessors[index];
  const view = json.bufferViews[accessor.bufferView];
  const offset = (view.byteOffset ?? 0) + (accessor.byteOffset ?? 0);
  const stride = view.byteStride || 12;
  const original = new DataView(rest[0].data.buffer, rest[0].data.byteOffset);
  const values = new Float32Array(accessor.count * 3);
  for (let i = 0; i < values.length; i++) values[i] = original.getFloat32(offset + Math.floor(i / 3) * stride + (i % 3) * 4, true);
  const before = Buffer.from(rest[0].data);
  values[1] += 5;
  const copy = structuredClone(json);
  const bin = rest[0].data.slice();
  writePositions(copy, bin, index, values);
  assert.ok(Buffer.from(rest[0].data).equals(before), 'the source chunk is untouched');
  assert.equal(copy.accessors[index].max[1], Math.fround(values[1]));
  const out = parseGlb(buildGlb(copy, [{ type: rest[0].type, data: bin }]));
  assert.equal(new DataView(out.rest[0].data.buffer, out.rest[0].data.byteOffset).getFloat32(offset + 4, true), Math.fround(values[1]));
  assert.throws(() => writePositions(copy, bin, index, values.subarray(3)), /vertici/);
  assert.match(positionAccessorProblem({ accessors: [{ type: 'VEC3', componentType: 5123 }] }, 0), /virgola/);
});

test('a zone shifts by its weight and widens only sideways to its axis', () => {
  const rest = Float32Array.from([0, 0, 0, 1, 0, 0, 0, 0, 1]);
  const reach = { index: Uint32Array.from([0, 1, 2]), w1: Float32Array.from([1, .5, .5]), w2: new Float32Array(3) };
  const work = rest.slice();
  displaceZone(work, rest, reach, [{ centre: [0, 0, 0], normal: [0, 0, 1], shift: [0, 2, 0], widen: 0 }]);
  close([...work], [0, 2, 0, 1, 1, 0, 0, 1, 1]);
  const wide = rest.slice();
  displaceZone(wide, rest, reach, [{ centre: [0, 0, 0], normal: [0, 0, 1], shift: [0, 0, 0], widen: 1 }]);
  close([...wide], [0, 0, 0, 1.5, 0, 0, 0, 0, 1]); // the point on the axis does not move
});

test('seam duplicates are welded and smoothed as one point', () => {
  // A flat strip of two triangles pairs, with a spike at the duplicated vertex.
  const a = Float32Array.from([0, 0, 0, 1, 0, 0, 1, 1, 5, 0, 1, 0]);
  const b = Float32Array.from([1, 0, 0, 2, 0, 0, 2, 1, 0, 1, 1, 5]);
  const { weldOf, count } = weldVertices([a, b]);
  assert.equal(count, 6);
  assert.equal(weldOf[0][1], weldOf[1][0]);
  assert.equal(weldOf[0][2], weldOf[1][3]);
  const quad = [0, 1, 2, 0, 2, 3];
  const neighbours = buildNeighbours(count, [{ weldOf: weldOf[0], indices: quad }, { weldOf: weldOf[1], indices: null }]);
  const spike = weldOf[0][2];
  assert.ok(neighbours.offsets[spike + 1] - neighbours.offsets[spike] >= 3);
  const positions = new Float32Array(count * 3);
  [[a, weldOf[0]], [b, weldOf[1]]].forEach(([points, ids]) => ids.forEach((id, i) => positions.set(points.subarray(i * 3, i * 3 + 3), id * 3)));
  smoothPoints(positions, neighbours, Uint32Array.from([spike]), Float32Array.from([1]), 1);
  assert.ok(positions[spike * 3 + 2] < 1, 'the spike is flattened');
  const still = positions.slice();
  smoothPoints(positions, neighbours, Uint32Array.from([spike]), Float32Array.from([0]), 1);
  assert.deepEqual(positions, still, 'zero weight leaves a point alone');
});

test('saved edits are validated and clamped before use', () => {
  const zone = { centre: [0, 1, 0], normal: [0, 0, 1], world: [0, 1, 0], radius: .1, push: .02, offset: [0, 0, 0], mirror: true };
  const clean = sanitizeState({ parts: { Head: { uniform: 9, axes: [1, 'x', 1], offset: [0, .1, 0], follows: 0 } }, zones: [zone] });
  assert.deepEqual(clean.parts.Head, { uniform: 2, axes: [1, 1, 1], offset: [0, .1, 0], follows: false });
  assert.deepEqual(clean.zones[0], { ...zone, widen: 0, smooth: 0 });
  assert.deepEqual(clean.materials, {});
  const paint = sanitizeState({ parts: {}, zones: [], materials: { 3: { colour: '#FF00aa', opacity: 7 } }, images: { 2: { hue: 999, saturation: 'x' } } });
  assert.deepEqual(paint.materials[3], { colour: '#ff00aa', opacity: 1, glow: null });
  assert.deepEqual(paint.images[2], { hue: 180, saturation: 0, lightness: 0, contrast: 0 });
  for (const bad of [null, {}, { parts: {}, zones: [{}] }, { parts: { a: 1 }, zones: [] }, { parts: {}, zones: [{ ...zone, radius: 'x' }] }]) {
    assert.throws(() => sanitizeState(bad), /valide/);
  }
});

test('colour adjustment is exact when neutral and keeps alpha', () => {
  const source = Uint8Array.from([10, 200, 90, 0, 255, 0, 0, 128, 12, 12, 12, 255]);
  const same = new Uint8Array(source.length);
  adjustPixels(source, same, colourMatrix({}));
  assert.deepEqual(same, source);
  const turned = new Uint8Array(source.length);
  adjustPixels(source, turned, colourMatrix({ hue: 120 }));
  assert.ok(turned[5] > turned[4] && turned[5] > turned[6], 'red rotates towards green');
  assert.deepEqual([turned[3], turned[7], turned[11]], [0, 128, 255]);
  const grey = new Uint8Array(source.length);
  adjustPixels(source, grey, colourMatrix({ saturation: -1 }));
  assert.ok(Math.abs(grey[4] - grey[5]) <= 1 && Math.abs(grey[5] - grey[6]) <= 1);
  const dark = new Uint8Array(source.length);
  adjustPixels(source, dark, colourMatrix({ lightness: -1 }));
  assert.deepEqual([...dark.subarray(0, 3)], [0, 0, 0]);
});

function decodePng(file) {
  const view = new DataView(file.buffer, file.byteOffset);
  const width = view.getUint32(16), height = view.getUint32(20);
  const idat = [];
  for (let offset = 8; offset < file.length;) {
    const length = view.getUint32(offset);
    if (String.fromCharCode(...file.subarray(offset + 4, offset + 8)) === 'IDAT') idat.push(file.subarray(offset + 8, offset + 8 + length));
    offset += 12 + length;
  }
  const raw = inflateSync(Buffer.concat(idat));
  const stride = width * 4;
  const pixels = new Uint8Array(stride * height);
  for (let y = 0; y < height; y++) {
    const filter = raw[y * (stride + 1)];
    for (let x = 0; x < stride; x++) {
      const before = filter === 1 ? (x >= 4 ? pixels[y * stride + x - 4] : 0) : filter === 2 ? (y ? pixels[(y - 1) * stride + x] : 0) : 0;
      pixels[y * stride + x] = raw[y * (stride + 1) + 1 + x] + before;
    }
  }
  return { width, height, pixels };
}

test('the PNG writer round-trips pixels, including colour under zero alpha', async () => {
  const width = 5, height = 4;
  const pixels = Uint8Array.from({ length: width * height * 4 }, (_, i) => (i * 37 + (i >> 3) * 11) & 255);
  pixels.set([200, 100, 50, 0], 0); // transparent but coloured
  const file = await encodePng(pixels, width, height);
  assert.deepEqual([...file.subarray(0, 8)], [137, 80, 78, 71, 13, 10, 26, 10]);
  const back = decodePng(file);
  assert.equal(back.width, width);
  assert.equal(back.height, height);
  assert.deepEqual(back.pixels, pixels);
});

test('repacking swaps one buffer view and keeps every other byte', async () => {
  const { json, rest } = parseGlb(await load());
  const copy = structuredClone(json);
  const target = copy.images[8].bufferView;
  const fresh = Uint8Array.from({ length: 1001 }, (_, i) => i & 255);
  const bin = repackBuffer(copy, rest[0].data, new Map([[target, fresh]]));
  assert.equal(copy.buffers[0].byteLength, bin.length);
  assert.equal(bin.length % 4, 0);
  copy.bufferViews.forEach((view, i) => {
    assert.equal(view.byteOffset % 4, 0);
    const now = bin.subarray(view.byteOffset, view.byteOffset + view.byteLength);
    const old = json.bufferViews[i];
    const before = i === target ? fresh : rest[0].data.subarray(old.byteOffset ?? 0, (old.byteOffset ?? 0) + old.byteLength);
    assert.ok(Buffer.from(now).equals(Buffer.from(before)), `view ${i}`);
  });
  assert.ok(bin.length < rest[0].data.length, 'the old image is dropped, not left behind');
});

test('material edits reach glTF and both VRM flavours', () => {
  const json = {
    materials: [{ pbrMetallicRoughness: { baseColorFactor: [1, .5, 1, 1] }, extensions: { VRMC_materials_mtoon: { shadeColorFactor: [.8, .4, .8] } } }, {}],
    extensions: { VRM: { materialProperties: [{ vectorProperties: { _Color: [1, 1, 1, 1] } }] } },
  };
  patchMaterial(json, 0, { linear: [.5, .5, .25], srgb: [.73, .73, .54], opacity: .5, emissive: [.2, 3, 0] });
  assert.deepEqual(json.materials[0].pbrMetallicRoughness.baseColorFactor, [.5, .5, .25, .5]);
  assert.equal(json.materials[0].alphaMode, 'BLEND');
  assert.deepEqual(json.materials[0].emissiveFactor, [.2, 1, 0]);
  assert.deepEqual(json.extensions.VRM.materialProperties[0].vectorProperties._Color, [.73, .73, .54, .5]);
  assert.deepEqual(json.materials[0].extensions.VRMC_materials_mtoon.shadeColorFactor, [.4, .4, .2]);
  patchMaterial(json, 1, { linear: [1, 0, 0], srgb: [1, 0, 0], opacity: 1 });
  assert.deepEqual(json.materials[1], { pbrMetallicRoughness: { baseColorFactor: [1, 0, 0, 1] } });
});
