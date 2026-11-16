import {
  AmbientLight, Box3, Color, DirectionalLight, GridHelper, HemisphereLight, MathUtils, Matrix3, Mesh,
  MeshBasicMaterial, PerspectiveCamera, Raycaster, Scene, SphereGeometry, Triangle, Vector2, Vector3, WebGLRenderer,
} from '../vendor/three/three.module.min.js';
import { GLTFLoader } from '../vendor/three/addons/loaders/GLTFLoader.js';
import {
  buildGlb, humanoidBones, mainBoneLabel, mirrorName, pairInfluence, parseGlb, patchNodes, positionAccessorProblem,
  resolveScales, shortName, writePositions,
} from './core.js';

const $ = id => document.getElementById(id);
const stage = $('stage');
const status = $('status');
const partSelect = $('part');

let renderer;
try {
  renderer = new WebGLRenderer({ antialias: true });
} catch {
  status.textContent = 'Questo browser non supporta WebGL: impossibile mostrare il modello.';
  status.classList.add('error');
  throw new Error('WebGL non disponibile');
}
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
const canvas = renderer.domElement;
canvas.tabIndex = 0;
canvas.setAttribute('aria-label', 'Vista 3D del modello');
stage.prepend(canvas);

const scene = new Scene();
scene.background = new Color(0x0c0915);
scene.add(new HemisphereLight(0xffffff, 0x54486e, 1.5), new AmbientLight(0xffffff, .6));
const sun = new DirectionalLight(0xffffff, 1.6);
scene.add(sun);
const camera = new PerspectiveCamera(32, 1, .01, 100);
const marker = new Mesh(new SphereGeometry(1, 20, 12),
  new MeshBasicMaterial({ color: 0xffd76a, depthTest: false, transparent: true, opacity: .85 }));
marker.renderOrder = 999;
marker.visible = false;
// Translucent spheres showing how far a free zone (and its twin) reaches.
const reach = [0, 1].map(() => new Mesh(marker.geometry,
  new MeshBasicMaterial({ color: 0xffd76a, depthTest: false, depthWrite: false, transparent: true, opacity: .1 })));
for (const sphere of reach) { sphere.renderOrder = 998; sphere.visible = false; }
scene.add(marker, ...reach);

let dirty = true;
const redraw = () => { dirty = true; };

// ---------------------------------------------------------------- camera
const view = { azimuth: 0, elevation: .05, distance: 3, target: new Vector3(), front: 1, size: 1.6 };

function placeCamera() {
  const { azimuth, elevation, distance, target } = view;
  camera.position.set(
    target.x + distance * Math.sin(azimuth) * Math.cos(elevation),
    target.y + distance * Math.sin(elevation),
    target.z + distance * Math.cos(azimuth) * Math.cos(elevation));
  camera.lookAt(target);
  camera.near = distance / 100;
  camera.far = distance * 100;
  camera.updateProjectionMatrix();
  sun.position.copy(camera.position).add(new Vector3(0, view.size, 0));
  redraw();
}

function frame(direction = 'front') {
  const fit = Math.min(1, camera.aspect / .6);
  view.distance = view.size * 1.15 / (2 * Math.tan(MathUtils.degToRad(camera.fov / 2))) / fit;
  view.target.copy(view.centre);
  view.elevation = .05;
  const front = view.front > 0 ? 0 : Math.PI;
  view.azimuth = front + { front: 0, side: Math.PI / 2, back: Math.PI }[direction];
  placeCamera();
}

function pan(dx, dy) {
  const scale = view.distance * 2 * Math.tan(MathUtils.degToRad(camera.fov / 2)) / canvas.clientHeight;
  const right = new Vector3().setFromMatrixColumn(camera.matrixWorld, 0);
  const up = new Vector3().setFromMatrixColumn(camera.matrixWorld, 1);
  view.target.addScaledVector(right, -dx * scale).addScaledVector(up, dy * scale);
}

const pointers = new Map();
canvas.addEventListener('pointerdown', event => {
  if (pointers.size >= 2) return;
  canvas.setPointerCapture(event.pointerId);
  pointers.set(event.pointerId, { x: event.clientX, y: event.clientY, startX: event.clientX, startY: event.clientY, moved: pointers.size > 0 });
  if (pointers.size === 2) for (const pointer of pointers.values()) pointer.moved = true;
});
canvas.addEventListener('pointermove', event => {
  const pointer = pointers.get(event.pointerId);
  if (!pointer) return;
  const dx = event.clientX - pointer.x;
  const dy = event.clientY - pointer.y;
  if (pointers.size === 1) {
    if (Math.hypot(event.clientX - pointer.startX, event.clientY - pointer.startY) > 8) pointer.moved = true;
    if (pointer.moved) {
      if (event.shiftKey || event.buttons === 2) pan(dx, dy);
      else {
        view.azimuth -= dx * .009;
        view.elevation = MathUtils.clamp(view.elevation + dy * .006, -1.4, 1.4);
      }
    }
  } else {
    const other = [...pointers.values()].find(item => item !== pointer);
    const before = Math.hypot(pointer.x - other.x, pointer.y - other.y);
    const after = Math.hypot(event.clientX - other.x, event.clientY - other.y);
    if (before > 8 && after > 8) view.distance *= before / after;
    pan(dx / 2, dy / 2);
  }
  pointer.x = event.clientX;
  pointer.y = event.clientY;
  placeCamera();
});
for (const type of ['pointerup', 'pointercancel']) {
  canvas.addEventListener(type, event => {
    const pointer = pointers.get(event.pointerId);
    pointers.delete(event.pointerId);
    if (type === 'pointerup' && pointer && !pointer.moved && event.button === 0) pick(event);
  });
}
canvas.addEventListener('contextmenu', event => event.preventDefault());
canvas.addEventListener('wheel', event => {
  event.preventDefault();
  view.distance *= Math.exp(MathUtils.clamp(event.deltaY * .0015, -.5, .5));
  placeCamera();
}, { passive: false });
for (const button of $('views').querySelectorAll('button')) button.onclick = () => frame(button.dataset.view);

new ResizeObserver(() => {
  const { clientWidth: width, clientHeight: height } = stage;
  if (!width || !height) return;
  renderer.setSize(width, height, false);
  camera.aspect = width / height;
  camera.updateProjectionMatrix();
  redraw();
}).observe(stage);

renderer.setAnimationLoop(() => {
  if (!dirty) return;
  dirty = false;
  renderer.render(scene, camera);
});

// ----------------------------------------------------------------- model
let model = null; // { name, json, rest, root, parts, byObject, byName, grid }
let current = -1;

function dispose(root) {
  root.traverse(object => {
    object.geometry?.dispose();
    for (const material of [object.material].flat().filter(Boolean)) {
      for (const value of Object.values(material)) if (value?.isTexture) value.dispose();
      material.dispose();
    }
  });
}

function fail(message) {
  status.hidden = false;
  status.classList.add('error');
  status.textContent = message;
}

async function open(name, buffer) {
  status.hidden = false;
  status.classList.remove('error');
  status.textContent = `Caricamento di ${name}…`;
  let container, gltf;
  try {
    container = parseGlb(buffer);
    gltf = await new GLTFLoader().parseAsync(buffer, '');
  } catch (error) {
    console.error(error);
    const reason = /draco|meshopt|ktx|basis/i.test(error.message)
      ? 'usa una compressione (Draco/Meshopt/KTX2) che questo editor non legge.' : error.message;
    fail(`Non riesco ad aprire ${name}: ${reason}`);
    return;
  }
  if (model) {
    scene.remove(model.root, model.grid);
    dispose(model.root);
  }
  const root = gltf.scene;
  scene.add(root);
  root.updateMatrixWorld(true);

  const { json } = container;
  const joints = new Set((json.skins ?? []).flatMap(skin => skin.joints));
  const humanoid = humanoidBones(json);
  const objects = new Map();
  root.traverse(object => {
    const index = gltf.parser.associations.get(object)?.nodes;
    if (index !== undefined) objects.set(index, object);
    if (object.isSkinnedMesh) object.frustumCulled = false;
  });

  // A part is a bone, or a rigid (unskinned) mesh node. Traversal order is
  // parents-first, which resolveScales relies on.
  const parts = [];
  const byObject = new Map();
  const labels = new Map();
  root.traverse(object => {
    const index = gltf.parser.associations.get(object)?.nodes;
    if (index === undefined || objects.get(index) !== object) return;
    const node = json.nodes[index];
    const rigid = node.mesh !== undefined && node.skin === undefined;
    if (!joints.has(index) && !rigid) return;
    let parent = -1;
    for (let up = object.parent; up && parent < 0; up = up.parent) parent = byObject.get(up) ?? -1;
    const name = node.name || `nodo ${index}`;
    const label = joints.has(index) ? mainBoneLabel(name, humanoid.get(index)) : null;
    if (label) labels.set(label, (labels.get(label) ?? 0) + 1);
    byObject.set(object, parts.length);
    parts.push({
      index, object, name, label, parent, main: Boolean(label),
      basePosition: object.position.toArray(), baseScale: object.scale.toArray(),
      rotation: object.quaternion.toArray(),
      uniform: 1, axes: [1, 1, 1], offset: [0, 0, 0], follows: !label,
    });
  });
  if (!parts.length) {
    scene.remove(root);
    dispose(root);
    model = null;
    $('controls').disabled = true;
    fail(`${name} non contiene ossa né parti separate da modificare.`);
    return;
  }
  // Named body parts resize on their own; everything else (hair, fingers,
  // skirt) follows its parent, as does the whole rig when no name is known.
  for (const part of parts) {
    if (part.label && labels.get(part.label) > 1) part.label += ` (${shortName(part.name)})`;
    part.children = [];
    if (part.parent >= 0) parts[part.parent].children.push(part);
  }

  const box = new Box3().setFromObject(root);
  const size = box.getSize(new Vector3());
  view.size = Math.max(size.y, size.x, size.z * .6, 1e-3);
  view.centre = box.getCenter(new Vector3());
  const toe = parts.find(part => part.label?.startsWith('Punta del piede') && part.parent >= 0);
  view.front = toe && toe.object.getWorldPosition(new Vector3()).z
    < parts[toe.parent].object.getWorldPosition(new Vector3()).z ? -1 : 1;
  const grid = new GridHelper(view.size * 2, 20, 0x6a4a9c, 0x2a2140);
  grid.position.set(view.centre.x, box.min.y, view.centre.z);
  scene.add(grid);
  marker.scale.setScalar(view.size * .008);

  model = {
    name, ...container, root, parts, byObject, grid, byName: new Map(parts.map((part, i) => [part.name, i])),
    zones: [], ...buildTargets(gltf, json, root),
  };
  zoneIndex = -1;
  partSelect.replaceChildren();
  const groups = [['Parti principali', part => part.main], ['Altre parti', part => !part.main]];
  for (const [title, test] of groups) {
    const group = document.createElement('optgroup');
    group.label = title;
    parts.forEach((part, i) => { if (test(part)) group.append(new Option(part.label ?? shortName(part.name), i)); });
    if (group.children.length) partSelect.append(group);
  }
  buildSliders();
  $('controls').disabled = false;
  $('views').hidden = false;
  status.hidden = true;
  const extension = name.split('.').pop().toLowerCase();
  $('export-note').textContent = `Il file esportato (.${extension}) mantiene materiali, rig ed espressioni dell'originale: cambiano solo le ossa modificate e la forma delle zone ritoccate.`;
  frame();
  const first = parts.findIndex(part => part.label === 'Testa');
  select(first >= 0 ? first : Number(partSelect.value));
  refreshZones();
  setMode(mode);
  buildLayers(gltf, json, root);
}

// ----------------------------------------------------------------- edits
function apply() {
  const { parts } = model;
  const scales = resolveScales(parts.map(part => ({
    parent: part.parent, baseScale: part.baseScale, rotation: part.rotation,
    multiplier: part.axes.map(axis => axis * part.uniform), follows: part.follows,
  })));
  parts.forEach((part, i) => {
    part.object.scale.fromArray(scales[i]);
    part.object.position.fromArray(part.basePosition.map((value, axis) => value + part.offset[axis]));
  });
  model.root.updateMatrixWorld(true);
  model.root.traverse(object => {
    if (object.isSkinnedMesh) object.boundingSphere = object.boundingBox = null;
  });
  if (current >= 0 && mode === 'bones') parts[current].object.getWorldPosition(marker.position);
  redraw();
}

function mirrored(part) {
  if (!$('mirror').checked) return null;
  const other = mirrorName(part.name);
  return other === null ? null : model.parts[model.byName.get(other)] ?? null;
}

function edit(change) {
  const part = model.parts[current];
  change(part, 1);
  const twin = mirrored(part);
  if (twin) change(twin, -1);
  apply();
}

// A slider edits whatever its context points at: the selected bone or zone.
const sliders = [];
const boneContext = { sliders, get: () => model.parts[current], change: change => edit(change) };
let sliderCount = 0;
function addSlider(host, context, { label, min, max, step, read, write, format }) {
  const id = `slider-${sliderCount++}`;
  const wrap = document.createElement('div');
  wrap.className = 'slider';
  wrap.innerHTML = `<label for="${id}"></label><output for="${id}"></output>
    <div class="line"><button type="button" aria-label="Diminuisci">−</button>
    <input type="range" id="${id}" min="${min}" max="${max}" step="${step}">
    <button type="button" aria-label="Aumenta">+</button></div>`;
  const [labelNode, output] = wrap.children;
  if (typeof label === 'string') labelNode.textContent = label;
  const [minus, input, plus] = wrap.querySelector('.line').children;
  const set = value => {
    context.change((part, side) => write(part, MathUtils.clamp(value, min, max), side));
    output.textContent = format(read(context.get()));
    input.value = read(context.get());
  };
  input.oninput = () => set(Number(input.value));
  minus.onclick = () => set(Math.round((read(context.get()) - step) / step) * step);
  plus.onclick = () => set(Math.round((read(context.get()) + step) / step) * step);
  host.append(wrap);
  context.sliders.push({ refresh(part) {
    labelNode.textContent = typeof label === 'function' ? label(part) : label;
    input.value = read(part);
    output.textContent = format(read(part));
  } });
}

const percent = value => `${Math.round(value * 100)}%`;

// Rigs like VRoid keep every bone axis-aligned, so X/Y/Z can be given plain
// names; otherwise the sliders act on the bone's own axes and say so.
function axisNames(part) {
  const [x, y, z, w] = part.worldRotation ??= part.object.getWorldQuaternion(part.object.quaternion.clone()).toArray();
  const aligned = Math.abs(w) > .9995 || Math.hypot(x, y, z) < .03;
  const names = aligned ? ['Larghezza', 'Altezza', 'Profondità'] : ['Asse X', 'Asse Y', 'Asse Z'];
  const child = part.children.find(item => item.main);
  if (child) {
    const lengths = child.basePosition.map(Math.abs);
    const axis = lengths.indexOf(Math.max(...lengths));
    if (lengths[axis] > .6 * Math.hypot(...lengths) && !(aligned && axis === 1)) {
      names[axis] = aligned ? 'Lunghezza' : `Lunghezza (asse ${'XYZ'[axis]})`;
    }
  }
  return { aligned, names };
}

function buildSliders() {
  sliders.length = 0;
  $('scale').replaceChildren();
  $('move').replaceChildren();
  addSlider($('scale'), boneContext, {
    label: 'Tutta la parte', min: .5, max: 2, step: .01, format: percent,
    read: part => part.uniform, write: (part, value) => { part.uniform = value; },
  });
  for (const axis of [0, 1, 2]) {
    addSlider($('scale'), boneContext, {
      label: part => axisNames(part).names[axis], min: .5, max: 2, step: .01, format: percent,
      read: part => part.axes[axis], write: (part, value) => { part.axes[axis] = value; },
    });
  }
  const range = Number((view.size * .1).toPrecision(2));
  const step = range / 100;
  const moves = ['Destra / sinistra', 'Su / giù', 'Avanti / indietro'];
  for (const axis of [0, 1, 2]) {
    addSlider($('move'), boneContext, {
      label: part => axisNames(part).aligned ? moves[axis] : `Asse ${'XYZ'[axis]}`,
      min: -range, max: range, step,
      format: value => `${value > 0 ? '+' : ''}${(value * 100).toFixed(1)} cm`,
      read: part => part.offset[axis],
      // The twin moves the opposite way sideways so the pair stays symmetric.
      write: (part, value, side) => { part.offset[axis] = axis === 0 ? value * side : value; },
    });
  }
  buildZoneSliders();
}

function select(index) {
  current = index;
  const part = model.parts[index];
  partSelect.value = index;
  for (const slider of sliders) slider.refresh(part);
  $('follows').checked = part.follows;
  $('follows').disabled = part.parent < 0;
  $('parent').disabled = part.parent < 0;
  if (mode !== 'bones') return;
  marker.visible = true;
  part.object.getWorldPosition(marker.position);
  const twin = mirrored(part);
  $('chip').hidden = false;
  $('chip').textContent = (part.label ?? shortName(part.name)) + (twin ? ' + lato opposto' : '');
  redraw();
}

const raycaster = new Raycaster();

// Cut-out cloth and hair cards are mostly invisible polygons: a tap must go
// through wherever the texture is transparent, or it lands on thin air.
const alphaCache = new WeakMap();
function opaqueAt(hit) {
  const material = [hit.object.material].flat()[hit.face?.materialIndex ?? 0];
  const map = material?.map;
  if (!map?.image || !hit.uv || !(material.transparent || material.alphaTest > 0)) return true;
  let pixels = alphaCache.get(map);
  if (pixels === undefined) {
    try {
      const scale = Math.min(1, 512 / Math.max(map.image.width, map.image.height));
      const sheet = document.createElement('canvas');
      sheet.width = Math.max(1, Math.round(map.image.width * scale));
      sheet.height = Math.max(1, Math.round(map.image.height * scale));
      const context = sheet.getContext('2d', { willReadFrequently: true });
      context.drawImage(map.image, 0, 0, sheet.width, sheet.height);
      pixels = context.getImageData(0, 0, sheet.width, sheet.height);
    } catch {
      pixels = null;
    }
    alphaCache.set(map, pixels);
  }
  if (!pixels) return true;
  const uv = map.transformUv(hit.uv.clone());
  const x = Math.min(pixels.width - 1, Math.max(0, Math.floor(uv.x * pixels.width)));
  const y = Math.min(pixels.height - 1, Math.max(0, Math.floor(uv.y * pixels.height)));
  return pixels.data[(y * pixels.width + x) * 4 + 3] > 40;
}
function pick(event) {
  if (!model) return;
  const bounds = canvas.getBoundingClientRect();
  raycaster.setFromCamera(new Vector2(
    (event.clientX - bounds.left) / bounds.width * 2 - 1,
    -(event.clientY - bounds.top) / bounds.height * 2 + 1), camera);
  const shown = object => !object || (object.visible && shown(object.parent));
  const hit = raycaster.intersectObject(model.root, true).find(item => shown(item.object) && opaqueAt(item));
  if (!hit) return;
  if (mode === 'zones') return pickZone(hit);
  let object = hit.object;
  const { skinIndex, skinWeight } = hit.object.geometry.attributes;
  if (hit.object.isSkinnedMesh && skinIndex && hit.face) {
    // Take the bone that pulls hardest on the triangle that was touched.
    const weights = new Map();
    for (const vertex of [hit.face.a, hit.face.b, hit.face.c]) {
      for (let slot = 0; slot < 4; slot++) {
        const bone = skinIndex.getComponent(vertex, slot);
        weights.set(bone, (weights.get(bone) ?? 0) + skinWeight.getComponent(vertex, slot));
      }
    }
    const [best] = [...weights].sort((a, b) => b[1] - a[1])[0];
    object = hit.object.skeleton.bones[best];
  }
  for (; object; object = object.parent) {
    if (model.byObject.has(object)) return select(model.byObject.get(object));
  }
}

partSelect.onchange = () => select(Number(partSelect.value));
$('parent').onclick = () => select(model.parts[current].parent);
$('mirror').onchange = () => select(current);
$('follows').onchange = () => {
  edit(part => { part.follows = $('follows').checked; });
};
const clear = part => Object.assign(part, { uniform: 1, axes: [1, 1, 1], offset: [0, 0, 0], follows: !part.main });
$('reset-part').onclick = () => { edit(clear); select(current); };
$('reset-all').onclick = () => {
  if (!confirm('Annullare tutte le modifiche al modello?')) return;
  model.parts.forEach(clear);
  model.zones = [];
  apply();
  applyZones();
  select(current);
  refreshZones();
};

$('export').onclick = () => {
  const edits = new Map();
  const differs = (a, b) => a.some((value, i) => Math.abs(value - b[i]) > 1e-7);
  for (const part of model.parts) {
    const translation = part.object.position.toArray();
    const scale = part.object.scale.toArray();
    if (differs(translation, part.basePosition) || differs(scale, part.baseScale)) {
      edits.set(part.index, { translation, scale, rotation: part.rotation });
    }
  }
  const json = patchNodes(model.json, edits);
  let { rest } = model;
  const reshaped = [...model.targets.values()].filter(target => target.changed);
  if (reshaped.length) {
    const bin = rest[0].data.slice();
    for (const target of reshaped) writePositions(json, bin, target.accessor, target.work);
    rest = [{ type: rest[0].type, data: bin }, ...rest.slice(1)];
  }
  const buffer = buildGlb(json, rest);
  const dot = model.name.lastIndexOf('.');
  const link = document.createElement('a');
  link.href = URL.createObjectURL(new Blob([buffer], { type: 'model/gltf-binary' }));
  link.download = `${model.name.slice(0, dot)}-modificato${model.name.slice(dot)}`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(link.href), 60_000);
};

// ------------------------------------------------------------------ zones
// A free zone reshapes the vertices themselves, for areas with no bone of
// their own. Zones live in the bind pose ("common" space shared by every
// mesh), so skin, clothes and hair layers inside the radius move together
// and bone edits still apply on top.
let mode = 'bones';
let zoneIndex = -1;
const zoneSelect = $('zone');
const zoneContext = {
  sliders: [],
  get: () => model.zones[zoneIndex],
  change(change) { change(model.zones[zoneIndex], 1); applyZones(); showZone(); },
};

function buildTargets(gltf, json, root) {
  const targets = new Map();
  let skipped = 0;
  const point = new Vector3();
  root.traverse(mesh => {
    if (!mesh.isMesh) return;
    const attribute = mesh.geometry.attributes.position;
    const known = targets.get(attribute);
    if (known) return known.geometries.add(mesh.geometry);
    const link = gltf.parser.associations.get(mesh);
    const accessor = json.meshes[link?.meshes]?.primitives[link.primitives ?? 0]?.attributes.POSITION;
    if (accessor === undefined || positionAccessorProblem(json, accessor) || json.accessors[accessor].count !== attribute.count) {
      skipped++;
      return;
    }
    const toCommon = (mesh.isSkinnedMesh ? mesh.bindMatrix : mesh.matrixWorld).clone();
    const base = new Float32Array(attribute.count * 3);
    const common = new Float32Array(base.length);
    for (let i = 0; i < attribute.count; i++) {
      point.fromBufferAttribute(attribute, i).toArray(base, i * 3);
      point.applyMatrix4(toCommon).toArray(common, i * 3);
    }
    targets.set(attribute, {
      attribute, accessor, base, common, work: base.slice(), changed: false, geometries: new Set([mesh.geometry]),
      toCommon: new Matrix3().setFromMatrix4(toCommon), toLocal: new Matrix3().setFromMatrix4(toCommon).invert(),
    });
  });
  return { targets, skipped };
}

const idle = zone => !zone.push && !zone.offset.some(Boolean);
const flipX = ([x, y, z]) => [-x, y, z];
const zoneTwin = zone => zone.mirror
  ? { centre: flipX(zone.centre), normal: flipX(zone.normal), offset: flipX(zone.offset), world: flipX(zone.world) } : null;

function applyZones() {
  const shift = zone => new Vector3(...zone.normal).multiplyScalar(zone.push).add(new Vector3(...zone.offset));
  for (const target of model.targets.values()) {
    target.stale = target.changed;
    target.changed = false;
    if (target.stale) target.work.set(target.base);
  }
  for (const zone of model.zones) {
    if (idle(zone)) continue;
    const twin = zoneTwin(zone);
    zone.cache ??= new Map();
    for (const target of model.targets.values()) {
      let reachOf = zone.cache.get(target);
      if (!reachOf) zone.cache.set(target, reachOf = pairInfluence(target.common, zone.centre, twin?.centre ?? null, zone.radius));
      const { index, w1, w2 } = reachOf;
      if (!index.length) continue;
      const [ax, ay, az] = shift(zone).applyMatrix3(target.toLocal).toArray();
      const [bx, by, bz] = twin ? shift({ ...twin, push: zone.push }).applyMatrix3(target.toLocal).toArray() : [0, 0, 0];
      const { work } = target;
      for (let i = 0; i < index.length; i++) {
        const at = index[i] * 3;
        work[at] += w1[i] * ax + w2[i] * bx;
        work[at + 1] += w1[i] * ay + w2[i] * by;
        work[at + 2] += w1[i] * az + w2[i] * bz;
      }
      target.changed = true;
    }
  }
  for (const target of model.targets.values()) {
    if (!target.changed && !target.stale) continue;
    const { attribute, work } = target;
    if (!attribute.isInterleavedBufferAttribute && attribute.array instanceof Float32Array) attribute.array.set(work);
    else for (let i = 0; i < attribute.count; i++) attribute.setXYZ(i, work[i * 3], work[i * 3 + 1], work[i * 3 + 2]);
    (attribute.data ?? attribute).needsUpdate = true;
    for (const geometry of target.geometries) geometry.boundingSphere = geometry.boundingBox = null;
  }
  model.root.traverse(object => {
    if (object.isSkinnedMesh) object.boundingSphere = object.boundingBox = null;
  });
  redraw();
}

function showZone() {
  const zone = mode === 'zones' ? model?.zones[zoneIndex] : null;
  const twin = zone && zoneTwin(zone);
  [zone, twin].forEach((item, i) => {
    reach[i].visible = Boolean(item);
    if (!item) return;
    reach[i].position.fromArray(item.world);
    reach[i].scale.setScalar(zone.radius);
  });
  if (mode === 'zones') {
    marker.visible = Boolean(zone);
    if (zone) marker.position.fromArray(zone.world);
    $('chip').hidden = !zone;
    if (zone) $('chip').textContent = `Zona ${zoneIndex + 1}` + (twin ? ' + lato opposto' : '');
  }
  redraw();
}

function selectZone(index) {
  zoneIndex = index;
  const zone = model.zones[index];
  $('zone-controls').disabled = !zone;
  if (zone) {
    zoneSelect.value = index;
    $('zone-mirror').checked = zone.mirror;
    for (const slider of zoneContext.sliders) slider.refresh(zone);
  }
  showZone();
}

function refreshZones() {
  zoneSelect.replaceChildren(...model.zones.map((_, i) => new Option(`Zona ${i + 1}`, i)));
  $('zone-hint').textContent = 'Tocca il modello nel punto da modificare: la zona è il cerchio chiaro attorno al punto.'
    + (model.skipped ? ` ${model.skipped} mesh di questo file non sono modificabili a zone.` : '');
  selectZone(Math.min(zoneIndex, model.zones.length - 1));
}

let wantNewZone = false;
function pickZone(hit) {
  const mesh = hit.object;
  const target = model.targets.get(mesh.geometry.attributes.position);
  if (!target || !hit.face) return;
  // Find where on the untouched bind-pose surface the finger landed.
  const corners = [hit.face.a, hit.face.b, hit.face.c];
  const posed = corners.map(vertex => mesh.getVertexPosition(vertex, new Vector3()));
  const weights = Triangle.getBarycoord(mesh.worldToLocal(hit.point.clone()), ...posed, new Vector3())
    ?? new Vector3(1 / 3, 1 / 3, 1 / 3);
  const centre = new Vector3();
  const normal = new Vector3();
  const normals = mesh.geometry.attributes.normal;
  corners.forEach((vertex, i) => {
    const weight = weights.getComponent(i);
    centre.addScaledVector(new Vector3().fromArray(target.common, vertex * 3), weight);
    if (normals) normal.addScaledVector(new Vector3().fromBufferAttribute(normals, vertex), weight);
  });
  if (normals) normal.applyMatrix3(target.toCommon).normalize();
  if (normal.lengthSq() < .5) {
    const [a, b, c] = corners.map(vertex => new Vector3().fromArray(target.common, vertex * 3));
    normal.subVectors(b, a).cross(c.sub(a)).normalize();
  }
  const place = { centre: centre.toArray(), normal: normal.toArray(), world: hit.point.toArray(), cache: null };
  const zone = model.zones[zoneIndex];
  if (zone && idle(zone) && !wantNewZone) Object.assign(zone, place);
  else {
    model.zones.push({ ...place, radius: zone?.radius ?? defaultRadius(), push: 0, offset: [0, 0, 0], mirror: $('zone-mirror').checked });
    zoneIndex = model.zones.length - 1;
  }
  wantNewZone = false;
  refreshZones();
}

const defaultRadius = () => Number((view.size * .05).toPrecision(2));
const centimetres = value => `${value > 0 ? '+' : ''}${(value * 100).toFixed(1)} cm`;
function buildZoneSliders() {
  zoneContext.sliders.length = 0;
  $('zone-sliders').replaceChildren();
  const unit = Number((view.size * .01).toPrecision(1));
  addSlider($('zone-sliders'), zoneContext, {
    label: 'Raggio', min: unit, max: unit * 25, step: unit / 4, format: value => `${(value * 100).toFixed(1)} cm`,
    read: zone => zone.radius, write: (zone, value) => { zone.radius = value; zone.cache = null; },
  });
  addSlider($('zone-sliders'), zoneContext, {
    label: 'Gonfia / sgonfia', min: -unit * 6, max: unit * 6, step: unit / 20, format: centimetres,
    read: zone => zone.push, write: (zone, value) => { zone.push = value; },
  });
  // "Forward" follows the way the model faces, which differs between files.
  const moves = [['Su / giù', 1, 1], ['Destra / sinistra', 0, 1], ['Avanti / indietro', 2, view.front]];
  for (const [label, axis, sign] of moves) {
    addSlider($('zone-sliders'), zoneContext, {
      label, min: -unit * 6, max: unit * 6, step: unit / 20, format: centimetres,
      read: zone => zone.offset[axis] * sign, write: (zone, value) => { zone.offset[axis] = value * sign; },
    });
  }
}

function setMode(next) {
  mode = next;
  $('mode-bones').setAttribute('aria-pressed', mode === 'bones');
  $('mode-zones').setAttribute('aria-pressed', mode === 'zones');
  $('bone-mode').hidden = mode !== 'bones';
  $('zone-mode').hidden = mode !== 'zones';
  if (!model) return;
  if (mode === 'bones') select(current);
  showZone();
}
$('mode-bones').onclick = () => setMode('bones');
$('mode-zones').onclick = () => setMode('zones');
zoneSelect.onchange = () => selectZone(Number(zoneSelect.value));
$('zone-new').onclick = () => {
  wantNewZone = true;
  $('zone-hint').textContent = 'Ora tocca il modello nel punto della nuova zona.';
};
$('zone-delete').onclick = () => {
  model.zones.splice(zoneIndex, 1);
  applyZones();
  refreshZones();
};
$('zone-mirror').onchange = () => {
  const zone = model.zones[zoneIndex];
  if (!zone) return;
  zone.mirror = $('zone-mirror').checked;
  zone.cache = null;
  applyZones();
  showZone();
};

// One checkbox per mesh, so hair or clothes can be hidden to reach what
// they cover. Visibility is a viewing aid only and is never exported.
function buildLayers(gltf, json, root) {
  const layers = new Map();
  root.traverse(object => {
    const index = gltf.parser.associations.get(object)?.meshes;
    if (index === undefined || (object.parent && gltf.parser.associations.get(object.parent)?.meshes === index)) return;
    if (!layers.has(index)) layers.set(index, []);
    layers.get(index).push(object);
  });
  $('layers').replaceChildren(...[...layers].map(([index, objects]) => {
    const label = document.createElement('label');
    label.className = 'check';
    const box = Object.assign(document.createElement('input'), { type: 'checkbox', checked: true });
    box.onchange = () => {
      for (const object of objects) object.visible = box.checked;
      redraw();
    };
    label.append(box, ` ${json.meshes[index].name || `Mesh ${index + 1}`}`);
    return label;
  }));
}

// ------------------------------------------------------------------ files
async function openFile(file) {
  if (!file) return;
  if (!/\.(glb|vrm)$/i.test(file.name)) return fail('Formato non supportato: servono file .glb o .vrm.');
  await open(file.name, await file.arrayBuffer());
}
$('file').onchange = event => { openFile(event.target.files[0]); event.target.value = ''; };
stage.addEventListener('dragover', event => { event.preventDefault(); stage.classList.add('drop'); });
stage.addEventListener('dragleave', () => stage.classList.remove('drop'));
stage.addEventListener('drop', event => {
  event.preventDefault();
  stage.classList.remove('drop');
  openFile(event.dataTransfer.files[0]);
});
// The bundled Neliel assets are only reachable when served from the repo.
if (location.protocol.startsWith('http') && !globalThis.NELIEL_STANDALONE) {
  $('samples').hidden = false;
  for (const button of $('samples').querySelectorAll('button')) {
    button.onclick = async () => {
      const url = new URL(button.dataset.sample, location.href);
      try {
        const response = await fetch(url);
        if (!response.ok) throw new Error(response.status);
        await open(url.pathname.split('/').pop(), await response.arrayBuffer());
      } catch (error) {
        console.error(error);
        fail('Modello di esempio non trovato: apri un file dal tuo dispositivo.');
      }
    };
  }
}
