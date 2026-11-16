// Pure helpers for the model editor: GLB container I/O, bone naming and the
// scale bookkeeping. No three.js here so that Node can test it directly.

const MAGIC = 0x46546c67; // 'glTF'
const JSON_CHUNK = 0x4e4f534a;

export function parseGlb(buffer) {
  const view = new DataView(buffer);
  if (buffer.byteLength < 20 || view.getUint32(0, true) !== MAGIC) {
    throw new Error('Il file non è un GLB/VRM binario valido.');
  }
  if (view.getUint32(4, true) !== 2) throw new Error('È supportato solo glTF 2.0.');
  const total = view.getUint32(8, true);
  if (total > buffer.byteLength) throw new Error('Il file è troncato.');
  const chunks = [];
  let offset = 12;
  while (offset + 8 <= total) {
    const length = view.getUint32(offset, true);
    const type = view.getUint32(offset + 4, true);
    if (offset + 8 + length > total) throw new Error('Il file è troncato.');
    chunks.push({ type, data: new Uint8Array(buffer, offset + 8, length) });
    offset += 8 + length;
  }
  if (chunks[0]?.type !== JSON_CHUNK) throw new Error('Blocco JSON mancante nel file.');
  const json = JSON.parse(new TextDecoder().decode(chunks[0].data));
  return { json, rest: chunks.slice(1) };
}

// Rebuilds the container around a new JSON chunk; every other chunk (the
// binary buffer with meshes, textures, morphs) is copied through untouched.
export function buildGlb(json, rest) {
  const text = new TextEncoder().encode(JSON.stringify(json));
  const jsonLength = Math.ceil(text.length / 4) * 4;
  const total = 12 + 8 + jsonLength + rest.reduce((sum, chunk) => sum + 8 + Math.ceil(chunk.data.length / 4) * 4, 0);
  const out = new Uint8Array(total);
  const view = new DataView(out.buffer);
  view.setUint32(0, MAGIC, true);
  view.setUint32(4, 2, true);
  view.setUint32(8, total, true);
  view.setUint32(12, jsonLength, true);
  view.setUint32(16, JSON_CHUNK, true);
  out.fill(0x20, 20, 20 + jsonLength);
  out.set(text, 20);
  let offset = 20 + jsonLength;
  for (const chunk of rest) {
    const length = Math.ceil(chunk.data.length / 4) * 4;
    view.setUint32(offset, length, true);
    view.setUint32(offset + 4, chunk.type, true);
    out.set(chunk.data, offset + 8);
    offset += 8 + length;
  }
  return out.buffer;
}

const tidy = value => Math.round(value * 1e6) / 1e6;

// edits: Map(nodeIndex → { translation, rotation, scale }). Returns a patched
// deep copy of the JSON; nodes not listed are left exactly as they were.
export function patchNodes(json, edits) {
  const copy = structuredClone(json);
  for (const [index, edit] of edits) {
    const node = copy.nodes[index];
    if (!node) throw new Error(`Nodo ${index} inesistente.`);
    if (node.matrix) {
      delete node.matrix;
      node.rotation = edit.rotation.map(tidy);
    }
    node.translation = edit.translation.map(tidy);
    node.scale = edit.scale.map(tidy);
  }
  return copy;
}

// VRM 0.x and 1.0 both name the humanoid bones; map node index → bone name.
export function humanoidBones(json) {
  const map = new Map();
  const old = json.extensions?.VRM?.humanoid?.humanBones;
  if (Array.isArray(old)) for (const { bone, node } of old) map.set(node, bone);
  const modern = json.extensions?.VRMC_vrm?.humanoid?.humanBones;
  if (modern) for (const [bone, { node }] of Object.entries(modern)) map.set(node, bone);
  return map;
}

const fingers = /thumb|index|middle|ring|little|pinky|finger/i;
const mainRules = [
  [/hips|pelvis/i, 'Bacino'], [/upper_?chest/i, 'Petto alto'], [/chest/i, 'Petto'],
  [/spine/i, 'Addome'], [/neck/i, 'Collo'], [/head/i, 'Testa'],
  [/shoulder|clavicle/i, 'Spalla'], [/upper_?arm/i, 'Braccio'],
  [/lower_?arm|fore_?arm/i, 'Avambraccio'], [/arm/i, 'Braccio'], [/hand/i, 'Mano'],
  [/upper_?leg|up_?leg|thigh/i, 'Coscia'], [/lower_?leg|calf|shin|leg/i, 'Polpaccio'],
  [/toe/i, 'Punta del piede'], [/foot/i, 'Piede'],
];
const secondary = /J_Sec_|J_Adj_|hair|skirt|sleeve|bust|tail|twist|roll/i;
const sideRules = [
  [/(^|[_. ])L([_. ]|$)|left/i, 'sx'], [/(^|[_. ])R([_. ]|$)|right/i, 'dx'],
];

// Returns an Italian label for a main body bone, or null for secondary bones
// (hair, skirt, fingers, tips) that should simply follow their parent.
export function mainBoneLabel(name, humanoidName) {
  const source = humanoidName ?? name;
  if (fingers.test(source) || /_end$/i.test(name)) return null;
  if (/bust|breast/i.test(name) && !/2$/.test(name)) {
    const side = sideRules.find(([rule]) => rule.test(name));
    return side ? `Seno ${side[1]}` : 'Seno';
  }
  if (!humanoidName && secondary.test(name)) return null;
  const part = mainRules.find(([rule]) => rule.test(source));
  if (!part) return null;
  const side = sideRules.find(([rule]) => rule.test(source));
  return side ? `${part[1]} ${side[1]}` : part[1];
}

const swaps = [
  [/(^|[_. ])L([_. ]|$)/, '$1R$2'], [/(^|[_. ])R([_. ]|$)/, '$1L$2'],
  [/Left/, 'Right'], [/Right/, 'Left'], [/left/, 'right'], [/right/, 'left'],
];

// Generated names such as HairJoint-245c78de-5156-… are cut to a short tag.
export function shortName(name) {
  return name.replace(/[-_ ]?([0-9a-f]{6})[0-9a-f]{2}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i, ' $1');
}

// Name of the opposite-side bone, or null when the name carries no side.
export function mirrorName(name) {
  for (const [rule, replacement] of swaps) {
    if (rule.test(name)) return name.replace(rule, replacement);
  }
  return null;
}

function rotateAxis([x, y, z, w], axis) {
  // Column `axis` of the rotation matrix for a unit quaternion.
  if (axis === 0) return [1 - 2 * (y * y + z * z), 2 * (x * y + z * w), 2 * (x * z - y * w)];
  if (axis === 1) return [2 * (x * y - z * w), 1 - 2 * (x * x + z * z), 2 * (y * z + x * w)];
  return [2 * (x * z + y * w), 2 * (y * z - x * w), 1 - 2 * (x * x + y * y)];
}

// How much the parent's scale stretches each of the child's local axes.
// Exact when the child's rest rotation is a multiple of 90°, otherwise the
// closest per-axis value (non-uniform scale under rotation also shears).
export function parentScaleInChild(parentScale, rotation) {
  return [0, 1, 2].map(axis => {
    const direction = rotateAxis(rotation, axis);
    return Math.hypot(direction[0] * parentScale[0], direction[1] * parentScale[1], direction[2] * parentScale[2]);
  });
}

// parts must be ordered parents-first. Each: { parent (index into parts or
// -1), baseScale, rotation, multiplier, follows }. A part's multiplier is the
// size the user asked for; unless `follows` is set, the parent's size change
// is cancelled so widening the hips does not widen the legs and torso too.
export function resolveScales(parts) {
  const effective = [];
  return parts.map((part, index) => {
    const inherited = part.parent < 0 ? [1, 1, 1]
      : parentScaleInChild(effective[part.parent], part.rotation);
    effective[index] = part.multiplier.map((value, axis) => value * (part.follows ? inherited[axis] : 1));
    return part.baseScale.map((value, axis) => part.follows
      ? value * part.multiplier[axis]
      : value * part.multiplier[axis] / inherited[axis]);
  });
}

// ------------------------------------------------------------ free zones
// A zone deforms every vertex within `radius` of its centre, fading smoothly
// to nothing at the edge so the surrounding surface stays continuous.
export function falloff(distance, radius) {
  if (distance >= radius) return 0;
  const t = 1 - (distance / radius) ** 2;
  return t * t;
}

// points: flat xyz array. Returns the affected vertices with their weight for
// the zone (w1) and for its optional mirrored twin (w2). Where the two
// overlap, across the body's midline, the weights are scaled down so the
// pair never pushes harder than a single zone would.
export function pairInfluence(points, centre, twin, radius) {
  const index = [], w1 = [], w2 = [];
  for (let i = 0; i < points.length; i += 3) {
    const x = points[i], y = points[i + 1], z = points[i + 2];
    const a = falloff(Math.hypot(x - centre[0], y - centre[1], z - centre[2]), radius);
    const b = twin ? falloff(Math.hypot(x - twin[0], y - twin[1], z - twin[2]), radius) : 0;
    if (a === 0 && b === 0) continue;
    const scale = Math.max(a, b) / (a + b);
    index.push(i / 3);
    w1.push(a * scale);
    w2.push(b * scale);
  }
  return { index: Uint32Array.from(index), w1: Float32Array.from(w1), w2: Float32Array.from(w2) };
}

// Why a POSITION accessor cannot be rewritten in place, or null if it can.
export function positionAccessorProblem(json, accessorIndex) {
  const accessor = json.accessors?.[accessorIndex];
  if (!accessor) return 'accessor mancante';
  if (accessor.type !== 'VEC3' || accessor.componentType !== 5126) return 'posizioni non in virgola mobile';
  if (accessor.sparse) return 'accessor sparso';
  const view = json.bufferViews?.[accessor.bufferView];
  if (!view) return 'dati mancanti';
  if (view.buffer !== 0 || json.buffers?.[0]?.uri !== undefined) return 'dati esterni al file';
  return null;
}

// Overwrites the vertex positions of one accessor inside `bin` (a private
// copy of the binary chunk) and refreshes the accessor's bounds in `json`.
export function writePositions(json, bin, accessorIndex, values) {
  const problem = positionAccessorProblem(json, accessorIndex);
  if (problem) throw new Error(`Mesh non riscrivibile: ${problem}.`);
  const accessor = json.accessors[accessorIndex];
  if (values.length !== accessor.count * 3) throw new Error('Numero di vertici diverso dall\'originale.');
  const view = json.bufferViews[accessor.bufferView];
  const stride = view.byteStride || 12;
  const start = (view.byteOffset ?? 0) + (accessor.byteOffset ?? 0);
  const data = new DataView(bin.buffer, bin.byteOffset, bin.byteLength);
  const min = [Infinity, Infinity, Infinity], max = [-Infinity, -Infinity, -Infinity];
  for (let i = 0; i < accessor.count; i++) {
    for (let axis = 0; axis < 3; axis++) {
      const value = Math.fround(values[i * 3 + axis]);
      data.setFloat32(start + i * stride + axis * 4, value, true);
      if (value < min[axis]) min[axis] = value;
      if (value > max[axis]) max[axis] = value;
    }
  }
  accessor.min = min;
  accessor.max = max;
}

// Moves the vertices of one zone. `sides` holds the zone and, when mirrored,
// its twin; each has { centre, normal, shift, widen }. `shift` is a plain
// offset, `widen` stretches the surface sideways around the zone's axis
// (the line through the centre along the normal) without pushing it outward.
export function displaceZone(work, rest, { index, w1, w2 }, sides) {
  const weights = [w1, w2];
  sides.forEach(({ centre, normal, shift, widen }, side) => {
    const weight = weights[side];
    for (let i = 0; i < index.length; i++) {
      const w = weight[i];
      if (w === 0) continue;
      const at = index[i] * 3;
      let x = shift[0], y = shift[1], z = shift[2];
      if (widen) {
        const dx = rest[at] - centre[0], dy = rest[at + 1] - centre[1], dz = rest[at + 2] - centre[2];
        const along = dx * normal[0] + dy * normal[1] + dz * normal[2];
        x += widen * (dx - along * normal[0]);
        y += widen * (dy - along * normal[1]);
        z += widen * (dz - along * normal[2]);
      }
      work[at] += w * x;
      work[at + 1] += w * y;
      work[at + 2] += w * z;
    }
  });
}

// Models duplicate vertices along texture seams and between materials. They
// must be smoothed as one point or the surface would tear open there, so
// vertices sharing a position (across all given arrays) get one weld id.
export function weldVertices(arrays, tolerance = 1e-5) {
  const ids = new Map();
  const weldOf = arrays.map(points => {
    const out = new Uint32Array(points.length / 3);
    for (let i = 0; i < out.length; i++) {
      const key = `${Math.round(points[i * 3] / tolerance)},${Math.round(points[i * 3 + 1] / tolerance)},${Math.round(points[i * 3 + 2] / tolerance)}`;
      let id = ids.get(key);
      if (id === undefined) ids.set(key, id = ids.size);
      out[i] = id;
    }
    return out;
  });
  return { weldOf, count: ids.size };
}

// meshes: [{ weldOf, indices }] with `indices` a triangle list (or null for
// unindexed geometry). Returns each welded point's neighbours, CSR-packed.
export function buildNeighbours(count, meshes) {
  const sets = Array.from({ length: count }, () => new Set());
  for (const { weldOf, indices } of meshes) {
    const corners = indices ? indices.length : weldOf.length;
    for (let i = 0; i + 2 < corners; i += 3) {
      const a = weldOf[indices ? indices[i] : i];
      const b = weldOf[indices ? indices[i + 1] : i + 1];
      const c = weldOf[indices ? indices[i + 2] : i + 2];
      if (a !== b) { sets[a].add(b); sets[b].add(a); }
      if (b !== c) { sets[b].add(c); sets[c].add(b); }
      if (a !== c) { sets[a].add(c); sets[c].add(a); }
    }
  }
  const offsets = new Uint32Array(count + 1);
  sets.forEach((set, i) => { offsets[i + 1] = offsets[i] + set.size; });
  const list = new Uint32Array(offsets[count]);
  sets.forEach((set, i) => list.set([...set], offsets[i]));
  return { offsets, list };
}

// Relaxes the welded points `ids` towards the average of their neighbours.
// `weights` (0–1, the zone falloff) keeps the edge of the zone anchored.
export function smoothPoints(positions, { offsets, list }, ids, weights, strength, iterations = 6) {
  const next = new Float32Array(ids.length * 3);
  for (let pass = 0; pass < iterations; pass++) {
    for (let k = 0; k < ids.length; k++) {
      const at = ids[k] * 3;
      const from = offsets[ids[k]], to = offsets[ids[k] + 1];
      let x = 0, y = 0, z = 0;
      for (let n = from; n < to; n++) {
        x += positions[list[n] * 3];
        y += positions[list[n] * 3 + 1];
        z += positions[list[n] * 3 + 2];
      }
      const pull = to > from ? .5 * strength * weights[k] : 0;
      const count = to - from || 1;
      next[k * 3] = positions[at] + pull * (x / count - positions[at]);
      next[k * 3 + 1] = positions[at + 1] + pull * (y / count - positions[at + 1]);
      next[k * 3 + 2] = positions[at + 2] + pull * (z / count - positions[at + 2]);
    }
    for (let k = 0; k < ids.length; k++) positions.set(next.subarray(k * 3, k * 3 + 3), ids[k] * 3);
  }
}

// ------------------------------------------------------------ saved edits
// Checks a saved-edits file before it touches the model; anything malformed
// is rejected, numbers are clamped to what the sliders allow.
export function sanitizeState(data) {
  const fail = () => { throw new Error('Il file non contiene modifiche valide.'); };
  if (!data || typeof data !== 'object' || !data.parts || typeof data.parts !== 'object' || !Array.isArray(data.zones)) fail();
  const number = (value, fallback, min = -Infinity, max = Infinity) =>
    Number.isFinite(value) ? Math.min(max, Math.max(min, value)) : fallback;
  const vector = (value, fallback, min, max) => Array.isArray(value) && value.length === 3
    ? value.map((item, axis) => number(item, fallback[axis], min, max)) : [...fallback];
  const point = value => Array.isArray(value) && value.length === 3 && value.every(Number.isFinite) ? [...value] : fail();
  const parts = {};
  for (const [name, part] of Object.entries(data.parts)) {
    if (!part || typeof part !== 'object') fail();
    parts[name] = {
      uniform: number(part.uniform, 1, .5, 2), axes: vector(part.axes, [1, 1, 1], .5, 2),
      offset: vector(part.offset, [0, 0, 0]), follows: Boolean(part.follows),
    };
  }
  const zones = data.zones.map(zone => {
    if (!zone || typeof zone !== 'object') fail();
    return {
      centre: point(zone.centre), normal: point(zone.normal), world: point(zone.world),
      radius: number(zone.radius, NaN, 1e-6), push: number(zone.push, 0), widen: number(zone.widen, 0, -.9, 2),
      smooth: number(zone.smooth, 0, 0, 1), offset: vector(zone.offset, [0, 0, 0]), mirror: Boolean(zone.mirror),
    };
  });
  if (zones.some(zone => Number.isNaN(zone.radius))) fail();
  const materials = {};
  for (const [index, item] of Object.entries(data.materials ?? {})) {
    if (!item || typeof item !== 'object') fail();
    materials[index] = {
      colour: /^#[0-9a-f]{6}$/i.test(item.colour) ? item.colour.toLowerCase() : null,
      opacity: number(item.opacity, 1, 0, 1), glow: number(item.glow, null, 0, 1),
    };
  }
  const images = {};
  for (const [index, item] of Object.entries(data.images ?? {})) {
    if (!item || typeof item !== 'object') fail();
    images[index] = {
      hue: number(item.hue, 0, -180, 180), saturation: number(item.saturation, 0, -1, 1),
      lightness: number(item.lightness, 0, -1, 1), contrast: number(item.contrast, 0, -1, 1),
    };
  }
  return { parts, zones, materials, images };
}

// --------------------------------------------------------------- textures
// Hue (degrees), saturation, lightness and contrast (each −1…1, 0 = as is)
// folded into one colour matrix: rows of [r, g, b, offset] on 0–255 values.
export function colourMatrix({ hue = 0, saturation = 0, lightness = 0, contrast = 0 }) {
  const lr = .213, lg = .715, lb = .072;
  const cos = Math.cos(hue * Math.PI / 180), sin = Math.sin(hue * Math.PI / 180);
  const rotate = [
    lr + cos * (1 - lr) - sin * lr, lg - cos * lg - sin * lg, lb - cos * lb + sin * (1 - lb),
    lr - cos * lr + sin * .143, lg + cos * (1 - lg) + sin * .14, lb - cos * lb - sin * .283,
    lr - cos * lr - sin * (1 - lr), lg - cos * lg + sin * lg, lb + cos * (1 - lb) + sin * lb,
  ];
  const s = 1 + saturation;
  const saturate = [
    lr + (1 - lr) * s, lg - lg * s, lb - lb * s,
    lr - lr * s, lg + (1 - lg) * s, lb - lb * s,
    lr - lr * s, lg - lg * s, lb + (1 - lb) * s,
  ];
  const gain = (1 + lightness) * (1 + contrast);
  const offset = 127.5 * (1 - (1 + contrast));
  const out = [];
  for (let row = 0; row < 3; row++) {
    for (let column = 0; column < 3; column++) {
      out.push(gain * (saturate[row * 3] * rotate[column] + saturate[row * 3 + 1] * rotate[3 + column]
        + saturate[row * 3 + 2] * rotate[6 + column]));
    }
    out.push(offset);
  }
  return out;
}

// RGBA bytes in, RGBA bytes out; alpha is copied untouched.
export function adjustPixels(source, target, m) {
  for (let i = 0; i < source.length; i += 4) {
    const r = source[i], g = source[i + 1], b = source[i + 2];
    target[i] = Math.min(255, Math.max(0, m[0] * r + m[1] * g + m[2] * b + m[3] + .5));
    target[i + 1] = Math.min(255, Math.max(0, m[4] * r + m[5] * g + m[6] * b + m[7] + .5));
    target[i + 2] = Math.min(255, Math.max(0, m[8] * r + m[9] * g + m[10] * b + m[11] + .5));
    target[i + 3] = source[i + 3];
  }
}

let crcTable;
function crc32(bytes, crc = -1) {
  crcTable ??= Uint32Array.from({ length: 256 }, (_, n) => {
    for (let k = 0; k < 8; k++) n = n & 1 ? 0xedb88320 ^ (n >>> 1) : n >>> 1;
    return n >>> 0;
  });
  for (let i = 0; i < bytes.length; i++) crc = crcTable[(crc ^ bytes[i]) & 255] ^ (crc >>> 8);
  return crc;
}

// Writes RGBA bytes as a PNG without going through a canvas, which would
// throw away the colour of fully transparent pixels and leave dark fringes
// around cut-out hair and cloth.
export async function encodePng(pixels, width, height) {
  const stride = width * 4;
  const raw = new Uint8Array((stride + 1) * height);
  for (let y = 0; y < height; y++) {
    const row = y * stride, out = y * (stride + 1);
    // Pick whichever of the "left" and "above" predictors leaves less to store.
    let left = 0, above = 0;
    for (let x = 0; x < stride; x += 7) {
      const value = pixels[row + x];
      left += Math.abs((value - (x >= 4 ? pixels[row + x - 4] : 0)) << 24 >> 24);
      above += Math.abs((value - (y ? pixels[row + x - stride] : 0)) << 24 >> 24);
    }
    const filter = above < left ? 2 : 1;
    raw[out] = filter;
    for (let x = 0; x < stride; x++) {
      const before = filter === 1 ? (x >= 4 ? pixels[row + x - 4] : 0) : (y ? pixels[row + x - stride] : 0);
      raw[out + 1 + x] = pixels[row + x] - before;
    }
  }
  const packed = new Uint8Array(await new Response(
    new Blob([raw]).stream().pipeThrough(new CompressionStream('deflate'))).arrayBuffer());
  const header = new Uint8Array(13);
  const view = new DataView(header.buffer);
  view.setUint32(0, width);
  view.setUint32(4, height);
  header.set([8, 6, 0, 0, 0], 8);
  const chunks = [['IHDR', header], ['IDAT', packed], ['IEND', new Uint8Array(0)]];
  const file = new Uint8Array(8 + chunks.reduce((sum, [, data]) => sum + 12 + data.length, 0));
  file.set([137, 80, 78, 71, 13, 10, 26, 10]);
  const out = new DataView(file.buffer);
  let offset = 8;
  for (const [type, data] of chunks) {
    const tag = new TextEncoder().encode(type);
    out.setUint32(offset, data.length);
    file.set(tag, offset + 4);
    file.set(data, offset + 8);
    out.setUint32(offset + 8 + data.length, ~crc32(data, crc32(tag)) >>> 0);
    offset += 12 + data.length;
  }
  return file;
}

// Rebuilds the binary chunk with some buffer views swapped for new bytes
// (replacements: Map(bufferView index → Uint8Array)), e.g. a re-coloured
// image of a different size. Offsets in `json` are updated to match.
export function repackBuffer(json, bin, replacements) {
  const views = json.bufferViews.map((view, index) => ({ view, index }))
    .filter(({ view }) => view.buffer === 0)
    .sort((a, b) => (a.view.byteOffset ?? 0) - (b.view.byteOffset ?? 0));
  const parts = views.map(({ view, index }) => replacements.get(index)
    ?? bin.subarray(view.byteOffset ?? 0, (view.byteOffset ?? 0) + view.byteLength));
  const total = parts.reduce((sum, part) => sum + Math.ceil(part.length / 4) * 4, 0);
  const out = new Uint8Array(total);
  let offset = 0;
  views.forEach(({ view }, i) => {
    out.set(parts[i], offset);
    view.byteOffset = offset;
    view.byteLength = parts[i].length;
    offset += Math.ceil(parts[i].length / 4) * 4;
  });
  json.buffers[0].byteLength = total;
  return out;
}

// Writes a material's colour edits. `linear` and `srgb` are the same tint in
// the two encodings: glTF stores linear, VRM 0.x keeps an sRGB copy that VRM
// viewers read instead.
export function patchMaterial(json, index, { linear, srgb, opacity, emissive }) {
  const material = json.materials[index];
  const pbr = material.pbrMetallicRoughness ??= {};
  const before = pbr.baseColorFactor ?? [1, 1, 1, 1];
  pbr.baseColorFactor = [...linear.map(tidy), tidy(opacity)];
  if (opacity < 1 && (material.alphaMode ?? 'OPAQUE') === 'OPAQUE') material.alphaMode = 'BLEND';
  if (emissive) material.emissiveFactor = emissive.map(value => tidy(Math.min(1, Math.max(0, value))));
  const legacy = json.extensions?.VRM?.materialProperties?.[index]?.vectorProperties;
  if (legacy?._Color) legacy._Color = [...srgb.map(tidy), tidy(opacity)];
  const toon = material.extensions?.VRMC_materials_mtoon;
  if (toon?.shadeColorFactor) {
    toon.shadeColorFactor = toon.shadeColorFactor.map((value, axis) =>
      tidy(Math.min(1, before[axis] > 1e-4 ? value * linear[axis] / before[axis] : value)));
  }
}
