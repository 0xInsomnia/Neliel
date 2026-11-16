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
