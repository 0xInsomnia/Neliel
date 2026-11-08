import test from 'node:test';
import assert from 'node:assert/strict';
import * as T from '../vendor/three/three.module.min.js';
import { applyAnimeMaterials, materialProfile } from '../src/materials.js';

test('toon conversion preserves texture, alpha and material sharing; eyes remain painted', () => {
  const scene = new T.Group();
  const map = new T.Texture();
  const skin = new T.MeshStandardMaterial({ name: 'Viso', map, alphaTest: .5, side: T.DoubleSide });
  const a = new T.Mesh(new T.BufferGeometry(), skin);
  const b = new T.Mesh(new T.BufferGeometry(), skin);
  const eye = new T.Mesh(new T.BufferGeometry(), new T.MeshStandardMaterial({ name: 'Iride viola', map }));
  scene.add(a, b, eye);
  applyAnimeMaterials(scene);
  assert.ok(a.material.isMeshToonMaterial);
  assert.equal(a.material, b.material);
  assert.equal(a.material.map, map);
  assert.equal(a.material.alphaTest, .5);
  assert.equal(a.material.side, T.DoubleSide);
  assert.ok(eye.material.isMeshBasicMaterial);
  assert.equal(eye.material.map, map);
  assert.equal(scene.children.length, 3, 'no facial shells');
  assert.equal(materialProfile('Argento · coda'), 'hair');
});

test('optional contours share the animated skeleton and follow hair visibility', () => {
  const scene = new T.Group();
  const geo = new T.BufferGeometry();
  geo.setAttribute('position', new T.Float32BufferAttribute([0,0,0], 3));
  geo.setAttribute('skinIndex', new T.Uint16BufferAttribute([0,0,0,0], 4));
  geo.setAttribute('skinWeight', new T.Float32BufferAttribute([1,0,0,0], 4));
  const mesh = new T.SkinnedMesh(geo, new T.MeshStandardMaterial({ name: 'Argento · coda' }));
  const bone = new T.Bone(); scene.add(bone, mesh);
  mesh.bind(new T.Skeleton([bone]));
  const style = applyAnimeMaterials(scene);
  const shell = scene.children.find(item => item.name.endsWith('-outline'));
  assert.equal(shell.skeleton, mesh.skeleton);
  assert.equal(shell.geometry, mesh.geometry);
  assert.equal(shell.visible, false);
  style.setOutlines(true); assert.equal(shell.visible, true);
  mesh.visible = false; style.update(); assert.equal(shell.visible, false);
  bone.position.x = .3; scene.updateMatrixWorld(true);
  const p = new T.Vector3(); const q = new T.Vector3();
  mesh.applyBoneTransform(0,p); shell.applyBoneTransform(0,q);
  assert.ok(p.distanceTo(q) < 1e-8);
});

test('shader hooks target shipped r170 chunks without dropping morph/skinning stages', () => {
  const scene = new T.Group();
  scene.add(new T.Mesh(new T.BufferGeometry(), new T.MeshStandardMaterial({ name: 'Capelli' })));
  applyAnimeMaterials(scene);
  const shader = { ...T.ShaderLib.toon };
  scene.children[0].material.onBeforeCompile(shader);
  assert.match(shader.fragmentShader, /float band/);
  assert.match(shader.fragmentShader, /#include <opaque_fragment>/);
  const outline = { ...T.ShaderLib.basic };
  scene.children[1].material.onBeforeCompile(outline);
  assert.match(outline.vertexShader, /#include <skinning_vertex>/);
  assert.match(outline.vertexShader, /#include <morphtarget_vertex>/);
  assert.match(outline.vertexShader, /!defined\(USE_SKINNING\)/);
  assert.match(outline.vertexShader, /normalize\(objectNormal\)/);
});
