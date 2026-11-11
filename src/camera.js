import { MathUtils, Vector3 } from '../vendor/three/three.module.min.js';

const defaults = {
  body: { target: .87, span: 1.90, azimuth: .10, elevation: .04 },
  portrait: { target: 1.51, span: .53, azimuth: .12, elevation: .05 },
};
const tapRadius = 10;

export function controlCamera(canvas, camera, onView, framing = {}) {
  // Optional per-model framing, e.g. a taller revision of the avatar.
  const views = { body: { ...defaults.body, ...framing.body }, portrait: { ...defaults.portrait, ...framing.portrait } };
  const pointers = new Map();
  const target = new Vector3();
  let view = views.body;
  let azimuth, elevation, zoom, lastTap;
  let multiTouch = false;

  function reset(mode = 'body') {
    view = views[mode];
    azimuth = view.azimuth;
    elevation = view.elevation;
    zoom = 1;
    lastTap = undefined;
    onView(mode);
  }

  function orbit(dx, dy) {
    azimuth -= dx * .009;
    elevation = MathUtils.clamp(elevation + dy * .006, -.27, .77);
  }

  function dolly(factor) {
    zoom = MathUtils.clamp(zoom * factor, .64, 2.1);
  }

  function gap() {
    const [a, b] = pointers.values();
    return Math.hypot(a.x - b.x, a.y - b.y);
  }

  canvas.addEventListener('pointerdown', event => {
    if (event.button !== 0 || pointers.size >= 2) return;
    const { clientX: x, clientY: y, pointerId: id } = event;
    pointers.set(id, { x, y, startX: x, startY: y, time: performance.now(), moved: false });
    canvas.setPointerCapture(id);
    if (pointers.size === 2) {
      multiTouch = true;
      lastTap = undefined;
    }
  });

  canvas.addEventListener('pointermove', event => {
    const pointer = pointers.get(event.pointerId);
    if (!pointer) return;
    const oldGap = pointers.size === 2 ? gap() : 0;
    const { clientX: x, clientY: y } = event;
    if (pointers.size === 1) orbit(x - pointer.x, y - pointer.y);
    Object.assign(pointer, { x, y });
    pointer.moved ||= Math.hypot(x - pointer.startX, y - pointer.startY) > tapRadius;
    if (oldGap > 8 && gap() > 8) dolly(oldGap / gap());
  });

  function endPointer(event) {
    const pointer = pointers.get(event.pointerId);
    if (!pointer) return;
    pointers.delete(event.pointerId);
    const time = performance.now();
    const tapped = event.type === 'pointerup' && event.pointerType === 'touch'
      && !multiTouch && !pointer.moved && time - pointer.time < 300;
    if (tapped && lastTap && time - lastTap.time < 340
        && Math.hypot(pointer.x - lastTap.x, pointer.y - lastTap.y) < 24) {
      reset();
    } else {
      lastTap = tapped ? { x: pointer.x, y: pointer.y, time } : undefined;
    }
    if (!pointers.size) multiTouch = false;
  }

  // A browser/OS interruption must not leave the next gesture in pinch mode.
  function cancelGesture() {
    pointers.clear();
    multiTouch = false;
    lastTap = undefined;
  }
  canvas.addEventListener('blur', cancelGesture);

  for (const type of ['pointerup', 'pointercancel', 'lostpointercapture']) {
    canvas.addEventListener(type, endPointer);
  }
  canvas.addEventListener('dblclick', event => {
    if (event.pointerType !== 'touch') reset();
  });
  canvas.addEventListener('wheel', event => {
    event.preventDefault();
    const delta = event.deltaY * (event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? 100 : 1);
    dolly(Math.exp(MathUtils.clamp(delta * .0015, -.5, .5)));
  }, { passive: false });
  canvas.addEventListener('keydown', event => {
    const keys = {
      ArrowLeft: () => orbit(-15, 0), ArrowRight: () => orbit(15, 0),
      ArrowUp: () => orbit(0, -15), ArrowDown: () => orbit(0, 15),
      '+': () => dolly(.88), '-': () => dolly(1.14), Home: () => reset(),
    };
    if (!Object.hasOwn(keys, event.key)) return;
    event.preventDefault();
    keys[event.key]();
  });

  reset();
  return {
    reset,
    zoomIn: () => dolly(.85),
    zoomOut: () => dolly(1 / .85),
    update() {
      const fit = Math.min(1, camera.aspect / .62);
      const distance = view.span / (2 * Math.tan(MathUtils.degToRad(camera.fov / 2))) * zoom / fit;
      target.set(0, view.target, 0);
      camera.position.set(
        distance * Math.sin(azimuth) * Math.cos(elevation),
        Math.max(.075, target.y + distance * Math.sin(elevation)),
        distance * Math.cos(azimuth) * Math.cos(elevation),
      );
      camera.lookAt(target);
    },
  };
}
