// Colours and textures: per-material tint, opacity and glow; recolouring,
// download and replacement of base-colour textures; a flat UV view; and an
// optional cel-shaded preview. Everything here is undone/saved through the
// plain state object handed to snapshot()/setState().
import { Color, DataTexture, RGBAFormat, UnsignedByteType } from '../vendor/three/three.module.min.js';
import { applyAnimeMaterials } from '../src/materials.js';
import { adjustPixels, colourMatrix, encodePng, patchMaterial } from './core.js';

const neutral = () => ({ hue: 0, saturation: 0, lightness: 0, contrast: 0 });
const isNeutral = adjust => !adjust.hue && !adjust.saturation && !adjust.lightness && !adjust.contrast;

// Reads an image file into raw RGBA bytes. Going through WebGL instead of a
// 2D canvas keeps the colour of fully transparent pixels, which cut-out
// textures need at their edges.
async function decodeImage(bytes, type) {
  const blob = new Blob([bytes], { type });
  try {
    const bitmap = await createImageBitmap(blob, { premultiplyAlpha: 'none', colorSpaceConversion: 'none' });
    const { width, height } = bitmap;
    const gl = Object.assign(document.createElement('canvas'), { width, height })
      .getContext('webgl', { premultipliedAlpha: false, alpha: true });
    if (!gl || Math.max(width, height) > gl.getParameter(gl.MAX_TEXTURE_SIZE)) throw new Error('WebGL non adatto');
    gl.bindTexture(gl.TEXTURE_2D, gl.createTexture());
    gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, false);
    gl.pixelStorei(gl.UNPACK_COLORSPACE_CONVERSION_WEBGL, gl.NONE);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, bitmap);
    gl.bindFramebuffer(gl.FRAMEBUFFER, gl.createFramebuffer());
    gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, gl.getParameter(gl.TEXTURE_BINDING_2D), 0);
    if (gl.checkFramebufferStatus(gl.FRAMEBUFFER) !== gl.FRAMEBUFFER_COMPLETE) throw new Error('lettura non riuscita');
    const data = new Uint8Array(width * height * 4);
    gl.readPixels(0, 0, width, height, gl.RGBA, gl.UNSIGNED_BYTE, data);
    bitmap.close();
    gl.getExtension('WEBGL_lose_context')?.loseContext();
    return { data, width, height };
  } catch (error) {
    console.warn('Decodifica precisa non disponibile, uso il canvas:', error);
    const bitmap = await createImageBitmap(blob);
    const canvas = Object.assign(document.createElement('canvas'), { width: bitmap.width, height: bitmap.height });
    const context = canvas.getContext('2d');
    context.drawImage(bitmap, 0, 0);
    const { data } = context.getImageData(0, 0, canvas.width, canvas.height);
    return { data: new Uint8Array(data.buffer), width: canvas.width, height: canvas.height };
  }
}

export function createPaint({ $, addSlider, redraw, commit, download, getModel, onSelect }) {
  let materials = [];        // one entry per glTF material in use
  let images = new Map();    // glTF image index → entry, for base-colour textures
  let lookup = new Map();    // three.js material (plain or toon) → entry
  let current = null;
  let showOriginal = false;
  let toon = null;           // { on, outlines, pairs: [{ mesh, plain, cel }], controller }
  let root = null;

  const hex = colour => `#${colour.getHexString()}`;
  const imageOf = entry => entry && images.get(entry.image);

  // ------------------------------------------------------------- building
  function build(gltf, json, scene) {
    root = scene;
    materials = [];
    images = new Map();
    lookup = new Map();
    toon = null;
    current = null;
    showOriginal = false;
    $('toon').checked = $('outline').checked = false;
    $('outline').disabled = true;
    const byIndex = new Map();
    const { associations } = gltf.parser;
    scene.traverse(mesh => {
      if (!mesh.isMesh) return;
      for (const material of [mesh.material].flat()) {
        const index = associations.get(material)?.materials;
        if (index === undefined) continue;
        let entry = byIndex.get(index);
        if (!entry) {
          const definition = json.materials[index];
          const emissive = material.emissive?.clone() ?? new Color(0);
          entry = {
            index, name: definition.name || `Materiale ${index + 1}`, instances: new Set(), meshes: new Set(), image: null,
            base: { colour: material.color.clone(), hex: hex(material.color), opacity: material.opacity,
              transparent: material.transparent, emissive, glows: emissive.r + emissive.g + emissive.b > 0 },
          };
          entry.colour = entry.base.hex;
          entry.opacity = entry.base.opacity;
          entry.glow = entry.base.glows ? 1 : 0;
          byIndex.set(index, entry);
          materials.push(entry);
        }
        entry.instances.add(material);
        entry.meshes.add(mesh);
        lookup.set(material, entry);
        // Every texture slot that shows an editable image gets tracked, so a
        // recoloured image also updates e.g. an emissive map that reuses it.
        for (const [key, texture] of Object.entries(material)) {
          if (!texture?.isTexture) continue;
          const source = json.textures?.[associations.get(texture)?.textures]?.source;
          const definition = json.images?.[source];
          if (definition?.bufferView === undefined || json.bufferViews[definition.bufferView].buffer !== 0) continue;
          if (!images.has(source)) {
            images.set(source, { index: source, view: definition.bufferView, mime: definition.mimeType ?? 'image/png',
              slots: [], users: new Set(), adjust: neutral(), pixels: null, replaced: false, output: null, loading: null });
          }
          const image = images.get(source);
          image.slots.push({ material, key, original: texture, edited: null });
          if (key === 'map') {
            image.users.add(entry);
            entry.image = source;
          }
        }
      }
    });
    materials.sort((a, b) => a.name.localeCompare(b.name));
    // Only images used as a base colour are offered for editing.
    for (const [index, image] of images) if (!image.users.size) images.delete(index);
    $('material').replaceChildren(...materials.map((entry, i) => new Option(entry.name, i)));
    select(materials[0] ?? null);
  }

  // ------------------------------------------------------------- applying
  function applyMaterial(entry) {
    const { base } = entry;
    const edited = !showOriginal;
    const colour = edited && entry.colour !== base.hex ? new Color(entry.colour) : base.colour;
    const opacity = edited ? entry.opacity : base.opacity;
    const glowBase = base.glows ? base.emissive : colour;
    const glow = edited ? entry.glow : (base.glows ? 1 : 0);
    for (const material of entry.instances) {
      material.color.copy(colour);
      material.opacity = opacity;
      const transparent = base.transparent || opacity < 1;
      if (material.transparent !== transparent) {
        material.transparent = transparent;
        material.needsUpdate = true;
      }
      material.emissive?.copy(glowBase).multiplyScalar(glow);
    }
  }

  async function loadPixels(image) {
    if (image.pixels) return image;
    image.loading ??= (async () => {
      const { json, rest } = getModel();
      const view = json.bufferViews[image.view];
      const bytes = rest[0].data.subarray(view.byteOffset ?? 0, (view.byteOffset ?? 0) + view.byteLength);
      Object.assign(image, { pixels: await decodeImage(bytes, image.mime) });
    })();
    await image.loading;
    return image;
  }

  function editedTexture(slot, image) {
    const { data, width, height } = image.output;
    if (slot.edited && (slot.edited.image.width !== width || slot.edited.image.height !== height)) {
      slot.edited.dispose();
      slot.edited = null;
    }
    if (!slot.edited) {
      const from = slot.original;
      const texture = new DataTexture(data, width, height, RGBAFormat, UnsignedByteType);
      for (const key of ['wrapS', 'wrapT', 'magFilter', 'minFilter', 'anisotropy', 'colorSpace', 'channel', 'rotation', 'name']) {
        texture[key] = from[key];
      }
      texture.offset.copy(from.offset);
      texture.repeat.copy(from.repeat);
      texture.center.copy(from.center);
      texture.flipY = false;
      texture.generateMipmaps = true;
      slot.edited = texture;
    }
    slot.edited.image.data = data;
    slot.edited.needsUpdate = true;
    return slot.edited;
  }

  // Shows either the untouched texture or the recoloured/replaced pixels.
  function renderImage(image) {
    const edited = !showOriginal && image.pixels && (image.replaced || !isNeutral(image.adjust));
    if (edited) {
      const { data, width, height } = image.pixels;
      if (image.output?.data.length !== data.length) image.output = { data: new Uint8Array(data.length), width, height };
      Object.assign(image.output, { width, height });
      adjustPixels(data, image.output.data, colourMatrix(image.adjust));
    }
    for (const slot of image.slots) slot.material[slot.key] = edited ? editedTexture(slot, image) : slot.original;
    image.shown = edited;
  }

  function syncToon() {
    if (!toon) return;
    for (const { mesh, plain, cel } of toon.pairs) {
      [plain].flat().forEach((source, i) => {
        const target = [cel].flat()[i];
        for (const key of ['map', 'emissiveMap', 'opacity', 'transparent']) if (key in target) target[key] = source[key];
        target.color.copy(source.color);
        target.emissive?.copy(source.emissive);
      });
      mesh.material = toon.on ? cel : plain;
    }
    for (const { shell, plain } of toon.shells) {
      if (shell.material.map !== plain.map) {
        shell.material.needsUpdate = !shell.material.map;
        shell.material.map = plain.map;
      }
    }
    toon.controller.setOutlines(toon.on && toon.outlines);
  }

  function refresh() {
    for (const entry of materials) applyMaterial(entry);
    for (const image of images.values()) renderImage(image);
    syncToon();
    drawUv();
    redraw();
  }

  // -------------------------------------------------------------- UV view
  let uvQueued = false;
  function drawUv() {
    if (uvQueued) return;
    uvQueued = true;
    requestAnimationFrame(() => {
      uvQueued = false;
      const canvas = $('uv');
      const image = imageOf(current);
      canvas.hidden = !image?.pixels || $('paint-mode').hidden;
      if (canvas.hidden) return;
      const shown = image.shown ? image.output : image.pixels;
      const scale = Math.min(1, 768 / Math.max(shown.width, shown.height));
      canvas.width = Math.round(shown.width * scale);
      canvas.height = Math.round(shown.height * scale);
      const context = canvas.getContext('2d');
      const sheet = Object.assign(document.createElement('canvas'), { width: shown.width, height: shown.height });
      sheet.getContext('2d').putImageData(new ImageData(new Uint8ClampedArray(shown.data.buffer, shown.data.byteOffset, shown.data.length), shown.width, shown.height), 0, 0);
      context.drawImage(sheet, 0, 0, canvas.width, canvas.height);
      if (!$('uv-grid').checked) return;
      context.lineWidth = .6;
      context.strokeStyle = '#ffffffa0';
      context.beginPath();
      for (const mesh of current.meshes) {
        const material = [mesh.material].flat()[0];
        const uv = mesh.geometry.attributes[material.map?.channel ? `uv${material.map.channel}` : 'uv'];
        if (!uv) continue;
        const index = mesh.geometry.index;
        const corners = index ? index.count : uv.count;
        const at = i => (index ? index.getX(i) : i);
        for (let i = 0; i + 2 < corners; i += 3) {
          const [a, b, c] = [at(i), at(i + 1), at(i + 2)];
          context.moveTo(uv.getX(a) * canvas.width, uv.getY(a) * canvas.height);
          context.lineTo(uv.getX(b) * canvas.width, uv.getY(b) * canvas.height);
          context.lineTo(uv.getX(c) * canvas.width, uv.getY(c) * canvas.height);
          context.closePath();
        }
      }
      context.stroke();
    });
  }

  // ------------------------------------------------------------- controls
  const materialSliders = { sliders: [], get: () => current, change(change) { change(current); applyMaterial(current); syncToon(); redraw(); } };
  const textureSliders = {
    sliders: [], get: () => imageOf(current),
    change(change) { const image = imageOf(current); change(image); renderImage(image); syncToon(); drawUv(); redraw(); },
  };
  const percent = value => `${Math.round(value * 100)}%`;
  const signed = value => `${value > 0 ? '+' : ''}${Math.round(value * 100)}%`;
  addSlider($('material-sliders'), materialSliders, {
    label: 'Opacità', min: 0, max: 1, step: .01, format: percent,
    read: entry => entry.opacity, write: (entry, value) => { entry.opacity = value; },
  });
  addSlider($('material-sliders'), materialSliders, {
    label: 'Bagliore', min: 0, max: 1, step: .01, format: percent,
    read: entry => entry.glow, write: (entry, value) => { entry.glow = value; },
  });
  addSlider($('texture-sliders'), textureSliders, {
    label: 'Tonalità', min: -180, max: 180, step: 1, format: value => `${value > 0 ? '+' : ''}${Math.round(value)}°`,
    read: image => image.adjust.hue, write: (image, value) => { image.adjust.hue = value; },
  });
  for (const [label, key] of [['Saturazione', 'saturation'], ['Luminosità', 'lightness'], ['Contrasto', 'contrast']]) {
    addSlider($('texture-sliders'), textureSliders, {
      label, min: -1, max: 1, step: .01, format: signed,
      read: image => image.adjust[key], write: (image, value) => { image.adjust[key] = value; },
    });
  }

  async function select(entry) {
    current = entry;
    onSelect(entry?.name ?? null);
    $('material-controls').disabled = !entry;
    $('texture-controls').disabled = true;
    if (!entry) {
      $('texture-note').textContent = 'Questo modello non ha materiali modificabili.';
      return;
    }
    $('material').value = materials.indexOf(entry);
    $('tint').value = entry.colour;
    for (const slider of materialSliders.sliders) slider.refresh(entry);
    const image = imageOf(entry);
    const note = $('texture-note');
    if (!image) {
      note.textContent = 'Questo materiale non ha una texture modificabile: puoi cambiare solo tinta, opacità e bagliore.';
      drawUv();
      return;
    }
    note.textContent = 'Caricamento della texture…';
    try {
      await loadPixels(image);
    } catch (error) {
      console.error(error);
      if (current === entry) note.textContent = 'Non riesco a leggere questa texture.';
      return;
    }
    if (current !== entry) return;
    const others = [...image.users].filter(user => user !== entry).map(user => user.name);
    note.textContent = `${image.pixels.width} × ${image.pixels.height} px.`
      + (others.length ? ` Usata anche da: ${others.join(', ')}; le modifiche valgono per tutti.` : '');
    $('texture-controls').disabled = false;
    for (const slider of textureSliders.sliders) slider.refresh(image);
    drawUv();
  }

  $('material').onchange = () => select(materials[Number($('material').value)]);
  $('tint').oninput = () => materialSliders.change(entry => { entry.colour = $('tint').value; });
  $('tint').onchange = commit;
  $('tint-reset').onclick = () => {
    Object.assign(current, { colour: current.base.hex, opacity: current.base.opacity, glow: current.base.glows ? 1 : 0 });
    refresh();
    select(current);
    commit();
  };
  $('uv-grid').onchange = drawUv;
  $('texture-save').onclick = async () => {
    const image = imageOf(current);
    const { data, width, height } = image.shown ? image.output : image.pixels;
    download(new Blob([await encodePng(data, width, height)], { type: 'image/png' }), `${current.name.replace(/[^\p{L}\p{N}]+/gu, '-')}.png`);
  };
  $('texture-file').onchange = async event => {
    const [file] = event.target.files;
    event.target.value = '';
    const image = imageOf(current);
    if (!file || !image) return;
    try {
      image.pixels = await decodeImage(new Uint8Array(await file.arrayBuffer()), file.type);
      image.replaced = true;
      refresh();
      select(current);
    } catch (error) {
      console.error(error);
      $('texture-note').textContent = `Non riesco ad aprire ${file.name} come immagine.`;
    }
  };
  $('texture-reset').onclick = async () => {
    const image = imageOf(current);
    Object.assign(image, { pixels: null, loading: null, replaced: false, adjust: neutral() });
    await loadPixels(image);
    refresh();
    select(current);
    commit();
  };
  $('toon').onchange = () => {
    if (!root) return;
    if (!toon) {
      // The studio's own anime shader, swapped in for viewing only.
      const before = new Map();
      root.traverse(mesh => { if (mesh.isMesh) before.set(mesh, mesh.material); });
      const controller = applyAnimeMaterials(root);
      toon = { on: false, outlines: false, controller, shells: [], pairs: [...before].map(([mesh, plain]) => ({ mesh, plain, cel: mesh.material })) };
      for (const { mesh, plain, cel } of toon.pairs) {
        [plain].flat().forEach((source, i) => { if (lookup.has(source)) lookup.set([cel].flat()[i], lookup.get(source)); });
        // The ink shell of cut-out cloth must be cut out too, or the hidden
        // parts of its polygons show up as solid dark shapes.
        const shell = mesh.parent.children.find(child => child.name === `${mesh.name}-outline`);
        if (shell && !Array.isArray(plain) && plain.alphaTest > 0) {
          toon.shells.push({ shell, plain });
          shell.material.alphaTest = plain.alphaTest;
        }
      }
    }
    toon.on = $('toon').checked;
    $('outline').disabled = !toon.on;
    syncToon();
    redraw();
  };
  $('outline').onchange = () => {
    toon.outlines = $('outline').checked;
    syncToon();
    redraw();
  };

  // ------------------------------------------------------------ interface
  return {
    build,
    drawUv,
    current: () => current?.name ?? null,
    pick(hit) {
      const material = [hit.object.material].flat()[hit.face?.materialIndex ?? 0];
      const entry = lookup.get(material);
      if (entry) select(entry);
      return Boolean(entry);
    },
    refreshOutlines() { toon?.controller.update(); },
    original(flag) {
      showOriginal = flag;
      refresh();
    },
    forgetReplacements() {
      for (const image of images.values()) if (image.replaced) Object.assign(image, { pixels: null, loading: null, replaced: false });
    },
    snapshot() {
      const state = { materials: {}, images: {} };
      for (const entry of materials) {
        const glow = entry.base.glows ? 1 : 0;
        if (entry.colour !== entry.base.hex || entry.opacity !== entry.base.opacity || entry.glow !== glow) {
          state.materials[entry.index] = { colour: entry.colour, opacity: entry.opacity, glow: entry.glow };
        }
      }
      for (const image of images.values()) if (!isNeutral(image.adjust)) state.images[image.index] = { ...image.adjust };
      return state;
    },
    async setState(state) {
      for (const entry of materials) {
        const saved = state.materials?.[entry.index];
        entry.colour = saved?.colour ?? entry.base.hex;
        entry.opacity = saved?.opacity ?? entry.base.opacity;
        entry.glow = saved?.glow ?? (entry.base.glows ? 1 : 0);
      }
      for (const image of images.values()) image.adjust = { ...neutral(), ...state.images?.[image.index] };
      refresh();
      if (current) select(current);
      // Textures that were never opened still need their pixels to be shown.
      const pending = [...images.values()].filter(image => !image.pixels && !isNeutral(image.adjust));
      if (!pending.length) return;
      await Promise.all(pending.map(loadPixels));
      refresh();
    },
    // Writes the colour edits into `json` and returns the re-encoded images
    // as Map(bufferView index → PNG bytes) for the caller to repack.
    async exportInto(json) {
      const swapped = new Map();
      for (const entry of materials) {
        const glow = entry.base.glows ? 1 : 0;
        if (entry.colour === entry.base.hex && entry.opacity === entry.base.opacity && entry.glow === glow) continue;
        const colour = entry.colour !== entry.base.hex ? new Color(entry.colour) : entry.base.colour;
        const srgb = colour.clone().convertLinearToSRGB();
        const emissive = entry.glow !== glow
          ? (entry.base.glows ? entry.base.emissive : colour).clone().multiplyScalar(entry.glow).toArray() : null;
        patchMaterial(json, entry.index, { linear: colour.toArray(), srgb: srgb.toArray(), opacity: entry.opacity, emissive });
      }
      for (const image of images.values()) {
        if (!image.replaced && isNeutral(image.adjust)) continue;
        await loadPixels(image);
        const { data, width, height } = image.pixels;
        const output = new Uint8Array(data.length);
        adjustPixels(data, output, colourMatrix(image.adjust));
        swapped.set(image.view, await encodePng(output, width, height));
        json.images[image.index].mimeType = 'image/png';
      }
      return swapped;
    },
  };
}
