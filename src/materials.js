import * as T from '../vendor/three/three.module.min.js';

// Profiles are intentionally separate: facial shading is softer than fabric.
export function materialProfile(name) {
  if (/Iride|Sclera|Riflesso|Contorno occhi|Ciglia|Sopracciglia|Bocca|Occhi extra/.test(name)) return 'eyes';
  if (/Viso/.test(name)) return 'face';
  if (/Capelli|Ciocche|Argento/.test(name)) return 'hair';
  if (/Fermaglio|Dettagli/.test(name)) return 'metal';
  return 'fabric';
}

function ramp(values) {
  const data = new Uint8Array(values.flatMap(v => [v, v, v, 255]));
  const texture = new T.DataTexture(data, values.length, 1, T.RGBAFormat);
  texture.minFilter = texture.magFilter = T.LinearFilter;
  texture.generateMipmaps = false;
  texture.needsUpdate = true;
  return texture;
}

export function createAnimeMaterial(source, ramps) {
  const profile = materialProfile(source.name);
  const options = {
    name: source.name, color: source.color.clone(), map: source.map,
    alphaMap: source.alphaMap, alphaTest: source.alphaTest,
    transparent: source.transparent, opacity: source.opacity, side: source.side,
    depthWrite: source.depthWrite, vertexColors: source.vertexColors,
  };
  // Preserve painted irises, lashes and catchlights instead of lighting them like skin.
  if (profile === 'eyes') return new T.MeshBasicMaterial(options);
  const material = new T.MeshToonMaterial({ ...options,
    gradientMap: ramps[profile === 'face' ? 'face' : 'body'],
    emissive: source.emissive.clone(), emissiveMap: source.emissiveMap,
    emissiveIntensity: source.emissiveIntensity,
  });
  material.userData.profile = profile;
  material.customProgramCacheKey = () => `neliel-toon-v1-${profile}`;
  material.onBeforeCompile = shader => {
    // Use the stock Three skinning/morph/normal pipeline, modifying only final light.
    const effect = `
      float facing = clamp(dot(normalize(normal), normalize(vViewPosition)), 0.0, 1.0);
      float edge = pow(1.0 - facing, 4.0);
      outgoingLight += vec3(0.19, 0.13, 0.29) * edge * ${profile === 'face' ? '0.10' : '0.32'};
      ${profile === 'hair' ? `
      float band = pow(max(0.0, dot(normalize(normal), normalize(vec3(-0.25, 0.65, 1.0)))), 24.0);
      outgoingLight += diffuseColor.rgb * vec3(0.23, 0.19, 0.29) * band;` : ''}
      ${profile === 'metal' ? 'outgoingLight += vec3(0.10, 0.07, 0.16) * pow(facing, 32.0);' : ''}
    `;
    shader.fragmentShader = shader.fragmentShader.replace('#include <opaque_fragment>', effect + '\n#include <opaque_fragment>');
  };
  return material;
}

export function applyAnimeMaterials(scene) {
  const ramps = {
    body: ramp([85, 85, 85, 85, 158, 158, 240, 240]),
    face: ramp([160, 166, 178, 200, 224, 242, 250, 255]),
  };
  const converted = new Map();
  const outlines = [];
  const candidates = [];
  scene.traverse(mesh => { if (mesh.isMesh) candidates.push(mesh); });
  for (const mesh of candidates) {
    const originals = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
    const materials = originals.map(source => {
      if (!converted.has(source)) converted.set(source, createAnimeMaterial(source, ramps));
      return converted.get(source);
    });
    mesh.material = Array.isArray(mesh.material) ? materials : materials[0];
    // Omit facial shells: expanded eyelashes/eyes create dark halos in close-ups.
    if (originals.length !== 1 || !['hair', 'fabric'].includes(materialProfile(originals[0].name)) || originals[0].transparent) continue;
    const ink = new T.MeshBasicMaterial({ color: 0x30243f, side: T.BackSide });
    ink.customProgramCacheKey = () => 'neliel-outline-v1';
    ink.onBeforeCompile = shader => {
      // MeshBasicMaterial doesn't otherwise request normals; include the skinned normal path.
      shader.vertexShader = shader.vertexShader.replace('#include <begin_vertex>',
        '#if !defined(USE_ENVMAP) && !defined(USE_SKINNING)\n#include <beginnormal_vertex>\n#include <morphnormal_vertex>\n#endif\n#include <begin_vertex>');
      shader.vertexShader = shader.vertexShader.replace('#include <project_vertex>',
        'transformed += normalize(objectNormal) * 0.00065;\n#include <project_vertex>');
    };
    const outline = mesh.isSkinnedMesh ? new T.SkinnedMesh(mesh.geometry, ink) : new T.Mesh(mesh.geometry, ink);
    outline.name = `${mesh.name}-outline`;
    outline.position.copy(mesh.position); outline.quaternion.copy(mesh.quaternion); outline.scale.copy(mesh.scale);
    if (mesh.isSkinnedMesh) { outline.bindMode = mesh.bindMode; outline.bind(mesh.skeleton, mesh.bindMatrix); }
    outline.morphTargetInfluences = mesh.morphTargetInfluences;
    outline.morphTargetDictionary = mesh.morphTargetDictionary;
    outline.frustumCulled = false;
    outline.visible = false;
    mesh.parent.add(outline);
    outlines.push({ outline, mesh });
  }
  let enabled = false;
  return {
    setOutlines(value) { enabled = value; this.update(); },
    update() { for (const { outline, mesh } of outlines) outline.visible = enabled && mesh.visible; },
  };
}
