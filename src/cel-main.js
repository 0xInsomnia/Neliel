import * as T from '../vendor/three/three.module.min.js';
import { loadAvatar } from './avatar.js';
import { applyAnimeMaterials } from './materials.js';
import { controlCamera } from './camera.js';

const el = id => document.getElementById(id);
const stage = el('stage');
const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');
const say = message => { el('status').textContent = message; };
const renderer = new T.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'high-performance' });
renderer.setClearColor(0x100a1a, 0);
renderer.toneMapping = T.ACESFilmicToneMapping;
renderer.toneMappingExposure = .99;
const canvas = renderer.domElement;
canvas.tabIndex = 0;
canvas.setAttribute('aria-label', 'Vista di Neliel. Usa le frecce per ruotare, più e meno per lo zoom.');
canvas.setAttribute('aria-describedby', 'guide');
stage.prepend(canvas);

const scene = new T.Scene();
const camera = new T.PerspectiveCamera(37, 1, .035, 25);
const orbit = controlCamera(canvas, camera, mode => {
  el('home').setAttribute('aria-pressed', String(mode === 'body'));
  el('portrait').setAttribute('aria-pressed', String(mode === 'portrait'));
});

scene.add(new T.HemisphereLight(0xffeef8, 0x59436e, .85));
function light(color, intensity, position) {
  const key = new T.DirectionalLight(color, intensity);
  key.position.set(...position);
  scene.add(key);
}
light(0xffeadc, 2.05, [2.7, 4.3, 5]);
light(0x9c71ff, .40, [-3, 3, -3]);
light(0xd6b9ff, .18, [-3, 1.8, 2]);

const platform = new T.Mesh(new T.CylinderGeometry(.73, .76, .036, 72), new T.MeshStandardMaterial({
  color: 0x1a122b, metalness: .44, roughness: .58,
}));
platform.position.y = -.022;
scene.add(platform);
const ring = new T.Mesh(new T.RingGeometry(.67, .674, 96), new T.MeshBasicMaterial({
  color: 0xbe84ff, transparent: true, opacity: .7, side: T.DoubleSide,
}));
ring.rotation.x = -Math.PI / 2;
ring.position.y = -.003;
scene.add(ring);
const grid = new T.GridHelper(9, 44, 0x7e4f9e, 0x583a75);
grid.position.y = -.042;
grid.material.transparent = true;
grid.material.opacity = .25;
scene.add(grid);
scene.fog = new T.FogExp2(0x21162f, .14);

// The contact shadow uses a small gradient texture so mobile rendering needs no shadow pass.
const shadowCanvas = document.createElement('canvas');
shadowCanvas.width = shadowCanvas.height = 64;
const context = shadowCanvas.getContext('2d');
const gradient = context.createRadialGradient(32, 32, 2, 32, 32, 31);
gradient.addColorStop(0, '#08040caa');
gradient.addColorStop(1, '#08040c00');
context.fillStyle = gradient;
context.fillRect(0, 0, 64, 64);
const shadow = new T.Mesh(new T.PlaneGeometry(.52, .35), new T.MeshBasicMaterial({
  map: new T.CanvasTexture(shadowCanvas), transparent: true, depthWrite: false,
}));
shadow.rotation.x = -Math.PI / 2;
shadow.position.y = -.002;
scene.add(shadow);

new ResizeObserver(() => {
  const { clientWidth: width, clientHeight: height } = stage;
  if (!width || !height) return;
  renderer.setPixelRatio(Math.min(devicePixelRatio || 1, 1.65));
  renderer.setSize(width, height, false);
  camera.aspect = width / height;
  camera.updateProjectionMatrix();
}).observe(stage);

let avatar;
let lastFrame;
let paused = false;
function renderFrame(now) {
  const delta = lastFrame === undefined ? 0 : Math.min((now - lastFrame) / 1000, .05);
  lastFrame = now;
  if (!paused) avatar?.update(delta);
  orbit.update();
  renderer.render(scene, camera);
}
renderer.setAnimationLoop(renderFrame);
let contextLost = false;
document.addEventListener('visibilitychange', () => {
  lastFrame = undefined;
  renderer.setAnimationLoop(document.hidden || contextLost ? null : renderFrame);
});

function failure(message) {
  el('commands').disabled = true;
  el('status').hidden = true;
  el('error').textContent = message;
  el('failure').hidden = false;
  el('retry').onclick = () => location.reload();
}

canvas.addEventListener('webglcontextlost', () => {
  contextLost = true;
  renderer.setAnimationLoop(null);
  failure('Il contesto grafico è stato interrotto. Ricarica per riprendere.');
});

el('home').onclick = () => { orbit.reset('body'); say('Figura intera'); };
el('portrait').onclick = () => { orbit.reset('portrait'); say('Primo piano'); };
el('zoom-in').onclick = () => { orbit.zoomIn(); say('Zoom avanti'); };
el('zoom-out').onclick = () => { orbit.zoomOut(); say('Zoom indietro'); };

try {
  const original = new URLSearchParams(location.search).get('model') === 'original';
  const modelName = original ? 'Base 0.3' : 'Revisione 03';
  el('model-label').textContent = modelName;
  el('compare-model').href = original ? './' : '?model=original';
  el('compare-model').textContent = original ? 'Mostra revisione 03' : 'Confronta con la base 0.3';
  avatar = await loadAvatar(new URL(original ? '../assets/neliel.glb' : '../assets/neliel-refined.glb', import.meta.url), reducedMotion, applyAnimeMaterials);
  scene.add(avatar.root);
  for (const [id, action, label] of [
    ['outfit', 'changeOutfit', 'Outfit'], ['hair', 'changeHair', 'Capelli'],
    ['pose', 'changePose', 'Posa'], ['expression', 'changeExpression', 'Espressione'],
  ]) {
    el(id).onclick = () => {
      const value = avatar[action]();
      el(`${id}-label`).textContent = value;
      say(`${label} · ${value}`);
    };
  }
  el('pause').onclick = () => {
    paused = !paused;
    el('pause').setAttribute('aria-pressed', String(paused));
    el('pause').textContent = paused ? 'Riprendi animazione' : 'Ferma animazione';
    say(paused ? 'Posa ferma · puoi ruotare la camera' : 'Animazione attiva');
  };
  let outlines = false;
  el('outline').onclick = () => {
    outlines = !outlines; avatar.setOutlines(outlines);
    el('outline').setAttribute('aria-pressed', String(outlines));
    say(outlines ? 'Contorni sottili attivi' : 'Contorni disattivati');
  };
  el('wave').onclick = () => { avatar.wave(); say('Ciao! ✦'); };
  if (!renderer.getContext().isContextLost()) {
    el('commands').disabled = false;
    say(`${modelName} · modello in lavorazione`);
  }
} catch (error) {
  console.error(error);
  failure('Impossibile caricare il modello 3D di Neliel.');
}
