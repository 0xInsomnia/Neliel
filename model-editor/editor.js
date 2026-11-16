import {
  AmbientLight, Box3, Color, DirectionalLight, GridHelper, HemisphereLight, MathUtils, Mesh,
  MeshBasicMaterial, PerspectiveCamera, Raycaster, Scene, SphereGeometry, Vector2, Vector3, WebGLRenderer,
} from '../vendor/three/three.module.min.js';
import { GLTFLoader } from '../vendor/three/addons/loaders/GLTFLoader.js';
import { buildGlb, humanoidBones, mainBoneLabel, mirrorName, parseGlb, patchNodes, resolveScales, shortName } from './core.js';

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
scene.add(marker);

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

  model = { name, ...container, root, parts, byObject, grid, byName: new Map(parts.map((part, i) => [part.name, i])) };
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
  $('export-note').textContent = `Il file esportato (.${extension}) mantiene mesh, materiali, rig ed espressioni dell'originale: cambiano solo dimensione e posizione delle parti.`;
  frame();
  const first = parts.findIndex(part => part.label === 'Testa');
  select(first >= 0 ? first : Number(partSelect.value));
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
  if (current >= 0) parts[current].object.getWorldPosition(marker.position);
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

const sliders = [];
function addSlider(host, { label, min, max, step, read, write, format }) {
  const id = `slider-${sliders.length}`;
  const wrap = document.createElement('div');
  wrap.className = 'slider';
  wrap.innerHTML = `<label for="${id}"></label><output for="${id}"></output>
    <div class="line"><button type="button" aria-label="Diminuisci">−</button>
    <input type="range" id="${id}" min="${min}" max="${max}" step="${step}">
    <button type="button" aria-label="Aumenta">+</button></div>`;
  const [labelNode, output] = wrap.children;
  const [minus, input, plus] = wrap.querySelector('.line').children;
  const set = value => {
    edit((part, side) => write(part, MathUtils.clamp(value, min, max), side));
    output.textContent = format(read(model.parts[current]));
    input.value = read(model.parts[current]);
  };
  input.oninput = () => set(Number(input.value));
  minus.onclick = () => set(Math.round((read(model.parts[current]) - step) / step) * step);
  plus.onclick = () => set(Math.round((read(model.parts[current]) + step) / step) * step);
  host.append(wrap);
  sliders.push({ refresh(part) {
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
  addSlider($('scale'), {
    label: 'Tutta la parte', min: .5, max: 2, step: .01, format: percent,
    read: part => part.uniform, write: (part, value) => { part.uniform = value; },
  });
  for (const axis of [0, 1, 2]) {
    addSlider($('scale'), {
      label: part => axisNames(part).names[axis], min: .5, max: 2, step: .01, format: percent,
      read: part => part.axes[axis], write: (part, value) => { part.axes[axis] = value; },
    });
  }
  const range = Number((view.size * .1).toPrecision(2));
  const step = range / 100;
  const moves = ['Destra / sinistra', 'Su / giù', 'Avanti / indietro'];
  for (const axis of [0, 1, 2]) {
    addSlider($('move'), {
      label: part => axisNames(part).aligned ? moves[axis] : `Asse ${'XYZ'[axis]}`,
      min: -range, max: range, step,
      format: value => `${value > 0 ? '+' : ''}${(value * 100).toFixed(1)} cm`,
      read: part => part.offset[axis],
      // The twin moves the opposite way sideways so the pair stays symmetric.
      write: (part, value, side) => { part.offset[axis] = axis === 0 ? value * side : value; },
    });
  }
}

function select(index) {
  current = index;
  const part = model.parts[index];
  partSelect.value = index;
  for (const slider of sliders) slider.refresh(part);
  $('follows').checked = part.follows;
  $('follows').disabled = part.parent < 0;
  $('parent').disabled = part.parent < 0;
  marker.visible = true;
  part.object.getWorldPosition(marker.position);
  const twin = mirrored(part);
  $('chip').hidden = false;
  $('chip').textContent = (part.label ?? shortName(part.name)) + (twin ? ' + lato opposto' : '');
  redraw();
}

const raycaster = new Raycaster();
function pick(event) {
  if (!model) return;
  const bounds = canvas.getBoundingClientRect();
  raycaster.setFromCamera(new Vector2(
    (event.clientX - bounds.left) / bounds.width * 2 - 1,
    -(event.clientY - bounds.top) / bounds.height * 2 + 1), camera);
  const hit = raycaster.intersectObject(model.root, true).find(item => item.object.visible);
  if (!hit) return;
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
  apply();
  select(current);
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
  const buffer = buildGlb(patchNodes(model.json, edits), model.rest);
  const dot = model.name.lastIndexOf('.');
  const link = document.createElement('a');
  link.href = URL.createObjectURL(new Blob([buffer], { type: 'model/gltf-binary' }));
  link.download = `${model.name.slice(0, dot)}-modificato${model.name.slice(dot)}`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(link.href), 60_000);
};

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
