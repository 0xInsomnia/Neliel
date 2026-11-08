import test from 'node:test';
import assert from 'node:assert/strict';
import { PerspectiveCamera } from '../vendor/three/three.module.min.js';
import { controlCamera } from '../src/camera.js';

function setup() {
  const handlers = new Map();
  const canvas = {
    addEventListener(type, handler) { handlers.set(type, handler); },
    setPointerCapture() {},
  };
  const camera = new PerspectiveCamera(37, 390 / 530, .035, 25);
  let mode;
  const controls = controlCamera(canvas, camera, value => { mode = value; });
  const send = (type, x = 100, y = 200, id = 1, extra = {}) => {
    const event = { type, clientX: x, clientY: y, pointerId: id, button: 0,
      pointerType: 'touch', preventDefault() {}, ...extra };
    handlers.get(type)?.(event);
    controls.update();
  };
  const position = () => { controls.update(); return camera.position.toArray(); };
  const distance = () => camera.position.distanceTo({ x: 0, y: .87, z: 0 });
  return { camera, controls, send, position, distance, mode: () => mode };
}

test('one finger rotates; release and cancellation stop movement', () => {
  const c = setup(), initial = c.position();
  c.send('pointerdown'); c.send('pointermove', 175);
  assert.notDeepEqual(c.position(), initial);
  c.send('pointerup', 175);
  const released = c.position();
  c.send('pointermove', 250);
  assert.deepEqual(c.position(), released);
  c.send('pointerdown'); c.send('pointercancel');
  c.send('pointermove', 300);
  assert.deepEqual(c.position(), released);
});

test('pinch zooms without rotating; double tap restores view', () => {
  const c = setup(), initial = c.position(), start = c.distance();
  c.send('pointerdown', 140, 200, 1);
  c.send('pointerdown', 200, 200, 2);
  c.send('pointermove', 260, 200, 2);
  assert.ok(c.distance() < start);
  assert.ok(Math.abs(c.camera.position.x / c.camera.position.z - initial[0] / initial[2]) < 1e-10);
  c.send('pointerup', 140, 200, 1); c.send('pointerup', 260, 200, 2);
  c.send('pointerdown'); c.send('pointerup');
  c.send('pointerdown'); c.send('pointerup');
  assert.deepEqual(c.position(), initial);
  assert.equal(c.mode(), 'body');
});

test('pinch is not a double tap; coincident pointers never create invalid coordinates', () => {
  const c = setup(); c.controls.reset('portrait');
  c.send('pointerdown'); c.send('pointerdown', 100, 200, 2);
  c.send('pointermove', 100, 200, 2);
  c.send('pointerup'); c.send('pointerup', 100, 200, 2);
  assert.equal(c.mode(), 'portrait');
  assert.ok(c.position().every(Number.isFinite));
});

test('lost capture and blur clear interrupted gestures', () => {
  const c = setup();
  c.send('pointerdown'); c.send('lostpointercapture');
  const base = c.position(); c.send('pointermove', 230);
  assert.deepEqual(c.position(), base);
  c.send('pointerdown'); c.send('pointerdown', 200, 200, 2); c.send('blur');
  c.send('pointerdown'); c.send('pointermove', 180);
  assert.notDeepEqual(c.position(), base);
});

test('zoom buttons and wheel are bounded, portrait and home reset framing', () => {
  const c = setup(), base = c.position();
  c.controls.zoomIn(); assert.notDeepEqual(c.position(), base);
  for (let i = 0; i < 100; i++) c.controls.zoomIn();
  const near = c.position(); c.controls.zoomIn(); assert.deepEqual(c.position(), near);
  for (let i = 0; i < 100; i++) c.controls.zoomOut();
  const far = c.position(); c.controls.zoomOut(); assert.deepEqual(c.position(), far);
  c.send('wheel', 0, 0, 0, { deltaY: -100, deltaMode: 0 });
  assert.notDeepEqual(c.position(), far);
  c.controls.reset('portrait'); assert.equal(c.mode(), 'portrait');
  assert.ok(c.position()[2] < base[2]);
  c.send('keydown', 0, 0, 0, { key: 'Home' });
  assert.deepEqual(c.position(), base);
});

test('keyboard orbit and zoom work at narrow and landscape aspect ratios', () => {
  const c = setup(), base = c.position();
  c.send('keydown', 0, 0, 0, { key: 'ArrowRight' });
  assert.notDeepEqual(c.position(), base);
  for (const aspect of [.3, 2.4]) {
    c.camera.aspect = aspect;
    c.send('keydown', 0, 0, 0, { key: '+' });
    assert.ok(c.position().every(Number.isFinite));
    assert.ok(c.camera.position.y > 0);
  }
});
