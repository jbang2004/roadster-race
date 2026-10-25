// Car materials: MeshPhysicalMaterial car paint (clear coat, metallic flake under the coat, orange peel, rain beads),
// tinted glass (premultiplied, double sided, interior visible), tyres, rims with a vertex-code material table,
// emissive lamps with LED patterns, interior, decals and the speed-blur wheel disc.
// Everything is patched with onBeforeCompile; programs are shared between cars (customProgramCacheKey = kind + LOD).
import * as THREE from 'three';
import { G } from '../core/globals.js';

// ------------------------------------------------------------------------------------------------ GLSL pieces
const VERT_PARS = /* glsl */`
varying vec3 vObjPos; varying vec3 vObjNrm; varying vec3 vNM0; varying vec3 vNM1; varying vec3 vNM2; varying vec2 vUvC;`;
const VERT_MAIN = /* glsl */`
vObjPos = position; vObjNrm = normal; vNM0 = normalMatrix[0]; vNM1 = normalMatrix[1]; vNM2 = normalMatrix[2]; vUvC = uv;`;

const FRAG_COMMON = /* glsl */`
varying vec3 vObjPos; varying vec3 vObjNrm; varying vec3 vNM0; varying vec3 vNM1; varying vec3 vNM2; varying vec2 vUvC;
uniform float uLodT; uniform float uLodDir;
float ign(vec2 p) { return fract(52.9829189 * fract(dot(p, vec2(0.06711056, 0.00583715)))); }
float hash13(vec3 p3) { p3 = fract(p3 * .1031); p3 += dot(p3, p3.zyx + 31.32); return fract((p3.x + p3.y) * p3.z); }
vec3 hash33(vec3 p3) { p3 = fract(p3 * vec3(.1031, .1030, .0973)); p3 += dot(p3, p3.yxz + 33.33); return fract((p3.xxy + p3.yxx) * p3.zyx); }
vec4 hash42(vec2 p) { vec4 p4 = fract(vec4(p.xyxy) * vec4(.1031, .1030, .0973, .1099)); p4 += dot(p4, p4.wzxy + 33.33); return fract((p4.xxyz + p4.yzzw) * p4.zywx); }
`;
const LOD_DISCARD = /* glsl */`
{ float lodN = ign(gl_FragCoord.xy); if (uLodDir > 0.5 ? (lodN < uLodT) : (lodN >= uLodT)) discard; }`;

// value noise with analytic derivatives (iq)
const NOISED = /* glsl */`
vec4 noised(vec3 x) {
  vec3 p = floor(x); vec3 w = fract(x);
  vec3 u = w * w * w * (w * (w * 6.0 - 15.0) + 10.0);
  vec3 du = 30.0 * w * w * (w * (w - 2.0) + 1.0);
  float a = hash13(p + vec3(0, 0, 0)), b = hash13(p + vec3(1, 0, 0)), c = hash13(p + vec3(0, 1, 0)), d = hash13(p + vec3(1, 1, 0));
  float e = hash13(p + vec3(0, 0, 1)), f = hash13(p + vec3(1, 0, 1)), g = hash13(p + vec3(0, 1, 1)), h = hash13(p + vec3(1, 1, 1));
  float k0 = a, k1 = b - a, k2 = c - a, k3 = e - a, k4 = a - b - c + d, k5 = a - c - e + g, k6 = a - b - e + f, k7 = -a + b + c - d + e - f - g + h;
  return vec4(k0 + k1 * u.x + k2 * u.y + k3 * u.z + k4 * u.x * u.y + k5 * u.y * u.z + k6 * u.z * u.x + k7 * u.x * u.y * u.z,
    du * vec3(k1 + k4 * u.y + k6 * u.z + k7 * u.y * u.z, k2 + k5 * u.z + k4 * u.x + k7 * u.z * u.x, k3 + k6 * u.x + k5 * u.y + k7 * u.x * u.y));
}`;

// rain beads: lattice of spherical-cap droplets projected on the dominant axis plane; returns an object-space
// tangent perturbation to add to the normal (sphere caps lean outward at their rim).
const BEADS = /* glsl */`
vec3 beads(vec3 p, vec3 nObj, float fw, float scale, float coverage, float rMin, float rMax) {
  vec3 an = abs(nObj); vec2 uv; vec3 T; vec3 B;
  if (an.y >= an.x && an.y >= an.z) { uv = p.xz; T = vec3(1, 0, 0); B = vec3(0, 0, 1); }
  else if (an.x >= an.z) { uv = p.zy; T = vec3(0, 0, 1); B = vec3(0, 1, 0); }
  else { uv = p.xy; T = vec3(1, 0, 0); B = vec3(0, 1, 0); }
  float res = clamp((1.0 / scale) / max(fw * 2.2, 1e-5), 0.0, 1.0);
  if (res <= 0.02 || coverage <= 0.001) return vec3(0.0);
  vec2 q = uv * scale; vec2 id = floor(q); vec2 f = q - id; vec2 acc = vec2(0.0);
  for (int j = -1; j <= 1; j++) for (int i = -1; i <= 1; i++) {
    vec2 o = vec2(float(i), float(j));
    vec4 h = hash42(id + o);
    float on = step(h.w, coverage);
    vec2 c = o + 0.15 + 0.7 * h.xy;
    float rad = mix(rMin, rMax, h.z * h.z);
    vec2 d = f - c; float dist = length(d);
    float m = smoothstep(rad, rad * 0.86, dist) * on;
    acc += d / rad * m * 0.85;
  }
  return (T * acc.x + B * acc.y) * res;
}`;

const PAINT_PARS = /* glsl */`
uniform float uFlake; uniform vec3 uFlakeColor; uniform vec4 uPearl; uniform float uPeel; uniform float uBead;
${NOISED}
${BEADS}`;

const FLAKE = /* glsl */`
#if CAR_LOD < 2
if (gl_FrontFacing) {
  float fwO = length(fwidth(vObjPos));
  const float FS = 520.0;
  float vis = clamp((1.0 / FS) / max(fwO, 1e-5), 0.0, 1.0);
  float amp = uFlake * mix(0.04, 0.12, vis);
  vec3 h = hash33(floor(vObjPos * FS));
  float on = step(0.42, h.x);
  vec3 rv = normalize(h * 2.0 - 1.0 + 1e-4);
  vec3 rvV = mat3(vNM0, vNM1, vNM2) * rv;
  vec3 tang = rvV - normal * dot(rvV, normal);
  normal = normalize(normal + tang * amp * on * 0.9);
  diffuseColor.rgb *= 1.0 + (h.y - 0.5) * 0.45 * amp * on;
  diffuseColor.rgb = mix(diffuseColor.rgb, diffuseColor.rgb * uFlakeColor * 1.6, on * amp * h.z * 0.55);
}
#endif
if (gl_FrontFacing) {
  float nv = pow(1.0 - clamp(dot(normal, normalize(vViewPosition)), 0.0, 1.0), 3.0);
  diffuseColor.rgb = mix(diffuseColor.rgb, uPearl.rgb, nv * uPearl.a);
}`;

const PAINT_COAT = /* glsl */`
#ifdef USE_CLEARCOAT
{
  vec3 dp = vec3(0.0);
  float fwO = length(fwidth(vObjPos));
  #if CAR_LOD < 1
    vec4 n1 = noised(vObjPos * 46.0); vec4 n2 = noised(vObjPos * 120.0 + 7.3);
    dp += (n1.yzw + 0.5 * n2.yzw) * uPeel * clamp(0.02 / max(fwO, 1e-5), 0.0, 1.0);
  #endif
  float up = clamp(vObjNrm.y * 0.5 + 0.5, 0.25, 1.0);
  #ifndef IS_DECAL
  dp += beads(vObjPos, vObjNrm, fwO, 150.0, uBead * up * 0.7, 0.10, 0.30) * 0.9;
  dp += beads(vObjPos + 3.1, vObjNrm, fwO, 46.0, uBead * 0.3 * up, 0.12, 0.32);
  #else
  dp += beads(vObjPos, vObjNrm, fwO, 150.0, uBead * up, 0.10, 0.34) * 0.9;
  #endif
  vec3 dpv = mat3(vNM0, vNM1, vNM2) * dp;
  dpv -= clearcoatNormal * dot(dpv, clearcoatNormal);
  clearcoatNormal = normalize(clearcoatNormal + dpv);
}
#else
{ // matte paint (no clear coat): the rain beads perturb the base normal instead
  float fwO = length(fwidth(vObjPos));
  float up = clamp(vObjNrm.y * 0.5 + 0.5, 0.25, 1.0);
  vec3 dp = beads(vObjPos, vObjNrm, fwO, 150.0, uBead * up * 0.5, 0.10, 0.30) * 0.6;
  vec3 dpv = mat3(vNM0, vNM1, vNM2) * dp; dpv -= normal * dot(dpv, normal);
  normal = normalize(normal + dpv);
}
#endif`;

// carbon fibre: 2x2 twill of 6 mm tows projected on the dominant axis plane; each tow is a shallow cylinder (normal tilts
// across it, brighter along its crown) under a smooth clear coat. Fades to the average colour when the tows go sub-pixel.
const CARBON_PARS = /* glsl */`
float cfTow = 1.0; float cfWarp = 0.0; float cfBulge = 0.0; float cfVis = 0.0; vec3 cfT = vec3(1, 0, 0); vec3 cfB = vec3(0, 1, 0);`;
const CARBON_COLOR = /* glsl */`
#if CAR_LOD < 2
{
  vec3 an = abs(vObjNrm); vec2 uv;
  if (an.y >= an.x && an.y >= an.z) { uv = vObjPos.xz; cfT = vec3(1, 0, 0); cfB = vec3(0, 0, 1); }
  else if (an.x >= an.z) { uv = vObjPos.zy; cfT = vec3(0, 0, 1); cfB = vec3(0, 1, 0); }
  else { uv = vObjPos.xy; cfT = vec3(1, 0, 0); cfB = vec3(0, 1, 0); }
  vec2 q = uv * 220.0;
  float fw = max(length(fwidth(q)), 1e-4);
  cfVis = 1.0 - smoothstep(0.22, 0.65, fw);
  vec2 id = floor(q); vec2 f = fract(q);
  cfWarp = step(mod(id.x + id.y, 4.0), 1.5);
  cfBulge = (mix(f.x, f.y, cfWarp) - 0.5) * 2.0;
  cfTow = mix(0.86, (1.0 - 0.32 * cfBulge * cfBulge) * (0.88 + 0.24 * cfWarp), cfVis);
  diffuseColor.rgb *= cfTow;
}
#endif`;
const CARBON_NORMAL = /* glsl */`
#if CAR_LOD < 2
{
  vec3 dp = mix(cfT, cfB, cfWarp) * cfBulge * 0.3 * cfVis;
  vec3 dpv = mat3(vNM0, vNM1, vNM2) * dp; dpv -= normal * dot(dpv, normal);
  normal = normalize(normal + dpv);
}
#endif`;

// ----------------------------------------------------------------------------------------------- patching
const lodDefine = (lod) => ({ CAR_LOD: lod });

/** shared: { lod: {uLodT, uLodDir}, ...uniform objects } */
function patch(mat, kind, lod, shared) {
  mat.defines = { ...(mat.defines || {}), ...lodDefine(lod) };
  if (kind === 'decal') mat.defines.IS_DECAL = '';
  // lamps differ only in their emissive pattern: it has to be part of the key or they all share the first lamp's program
  mat.customProgramCacheKey = () => `car:${kind}${shared.lampKind ? '-' + shared.lampKind : ''}:${lod}:${mat.clearcoat > 0 ? 'cc' : 'nc'}`;
  mat.onBeforeCompile = (shader) => {
    const U = shader.uniforms;
    U.uLodT = shared.lod.uLodT; U.uLodDir = shared.lod.uLodDir;
    let pars = FRAG_COMMON, main = '', afterNormal = '', afterCoat = '', afterEmissive = '', afterColor = '', afterMetal = '',
      afterPhys = '', beforeEnd = '', opaque = null;

    if (kind === 'paint' || kind === 'decal') {
      U.uFlake = shared.paint.uFlake; U.uFlakeColor = shared.paint.uFlakeColor; U.uPearl = shared.paint.uPearl;
      U.uPeel = shared.paint.uPeel; U.uBead = shared.car.uBead;
      pars += PAINT_PARS;
      if (kind === 'paint') {
        afterMetal = `if (!gl_FrontFacing) { diffuseColor.rgb = vec3(0.016, 0.016, 0.018); metalnessFactor = 0.0; roughnessFactor = 0.72; }`;
        afterNormal = FLAKE;
        afterPhys = `#ifdef USE_CLEARCOAT\nif (!gl_FrontFacing) { material.clearcoat = 0.0; }\n#endif`;
        beforeEnd = `#if defined( RE_IndirectSpecular )\nif (!gl_FrontFacing) { radiance *= 0.12; clearcoatRadiance *= 0.0; }\n#endif`;
      }
      afterCoat = PAINT_COAT;
    } else if (kind === 'glass') {
      U.uBead = shared.car.uBead; U.uGlassAbs = shared.car.uGlassAbs;
      pars += `uniform float uBead; uniform float uGlassAbs;\n${BEADS}`;
      afterNormal = `
      {
        float fwO = length(fwidth(vObjPos));
        vec3 dp = beads(vObjPos, vObjNrm, fwO, 95.0, uBead * 0.30, 0.10, 0.26) * 0.8 + beads(vObjPos + 5.7, vObjNrm, fwO, 30.0, uBead * 0.10, 0.12, 0.30) * 0.9;
        vec3 dpv = mat3(vNM0, vNM1, vNM2) * dp; dpv -= normal * dot(dpv, normal);
        normal = normalize(normal + dpv);
      }`;
      beforeEnd = `#if defined( RE_IndirectSpecular )\nif (!gl_FrontFacing) { radiance *= 0.18; }\n#endif`;
      opaque = `
      float glassFr = pow(1.0 - clamp(dot(normal, normalize(vViewPosition)), 0.0, 1.0), 4.0);
      float glassA = clamp(uGlassAbs + glassFr * 0.55, 0.0, 1.0);
      gl_FragColor = vec4(outgoingLight, glassA);`;
    } else if (kind === 'rim') {
      U.uAccent = shared.paint.uAccent; U.uPaintC = shared.paint.uPaintC; U.uHeat = shared.car.uHeat; U.uWetK = shared.car.uWetK;
      pars += `uniform vec3 uAccent; uniform vec3 uPaintC; uniform float uHeat; uniform float uWetK;`;
      afterMetal = `
      float rCode = vColor.a;
      float isRub = 1.0 - step(0.075, rCode);
      float isGloss = step(0.075, rCode) * (1.0 - step(0.2, rCode));       // 0.15: gloss black of the spoke channels (deep, mirror-like: roughness 0.12)
      float isSat = step(0.2, rCode) * (1.0 - step(0.35, rCode));          // 0.25: graphite satin (bevels along the panels, star hub, lip)
      float isBody = step(0.35, rCode) * (1.0 - step(0.48, rCode));
      float isSilver = step(0.48, rCode) * (1.0 - step(0.68, rCode));
      float isChrome = step(0.68, rCode) * (1.0 - step(0.9, rCode));
      float isAccent = step(0.9, rCode);
      diffuseColor.rgb = mix(diffuseColor.rgb, uAccent, isAccent);
      diffuseColor.rgb = mix(diffuseColor.rgb, uPaintC, isBody);
      metalnessFactor = isSilver * 0.55 + isChrome + isAccent * 0.55 + isBody * 0.35 + isSat * 0.45;
      roughnessFactor = isRub * mix(0.70, 0.52, uWetK) + isGloss * 0.12 + isSat * 0.48 + isSilver * 0.36 + isChrome * 0.08 + isAccent * 0.30 + isBody * 0.3;`;
      afterPhys = `#ifdef USE_CLEARCOAT\nmaterial.clearcoat *= 1.0 - isRub;\n#endif`;          // r3: the lod wheels' rubber (code 0.0) gets no clear coat: it matches the hi tyre (black, satin)
      afterEmissive = `
      {
        float rr = length(vObjPos.xz);
        float band = smoothstep(0.10, 0.27, rr) * (1.0 - 0.35 * smoothstep(0.27, 0.30, rr));
        vec3 hot = mix(vec3(1.0, 0.18, 0.02), vec3(1.0, 0.55, 0.12), uHeat);
        totalEmissiveRadiance += hot * uHeat * uHeat * (isSilver * band * 2.2 + isSat * band * 1.4 + isAccent * 6.0 + isGloss * band * 0.25);
      }`;
    } else if (kind === 'tyre') {
      U.uWetK = shared.car.uWetK;
      pars += `uniform float uWetK;`;
      afterColor = `
      {
        float rr = length(vObjPos.xz); float ang = atan(vObjPos.z, vObjPos.x);
        float side = smoothstep(0.55, 0.8, abs(vObjNrm.y));
        // sidewall: moulded rings + a band of block lettering
        // (FRONT r3: the sidewall now runs r 0.30 .. 0.39 under a 0.313 rim lip, flush with the rim: rings moved with it, and the print is a faint satin mark, not a grey line: 0.05 -> 0.022)
        float ring = smoothstep(0.0016, 0.0, abs(rr - 0.326)) + smoothstep(0.0012, 0.0, abs(rr - 0.334)) * 0.6 + smoothstep(0.0016, 0.0, abs(rr - 0.372));
        vec2 gc = vec2(ang * rr * 130.0, (rr - 0.338) * 200.0);
        vec2 gi = floor(gc); vec2 gf = fract(gc);
        float inBand = step(0.0, gc.y) * step(gc.y, 5.0);
        float glyph = step(0.5, hash13(vec3(floor(gi.x / 5.0), gi.y, 3.0)) + (hash13(vec3(gi, 7.0)) - 0.5) * 0.9) * step(0.12, gf.x) * step(gf.x, 0.88) * step(0.12, gf.y) * step(gf.y, 0.88);
        float gapC = step(mod(gi.x, 5.0), 3.5);
        float print = clamp(ring * 0.7 + glyph * gapC * inBand, 0.0, 1.0) * side;
        diffuseColor.rgb += vec3(0.022, 0.022, 0.024) * print;
        // tread grooves (the flat tread is |y| < 0.055 now)
        float gy = abs(vObjPos.y);
        float groove = (smoothstep(0.0035, 0.0018, abs(gy - 0.018)) + smoothstep(0.0035, 0.0018, abs(gy - 0.046))) * (1.0 - side);
        diffuseColor.rgb *= 1.0 - 0.6 * groove;
        tyrePrint = print;
      }`;
      pars += `float tyrePrint = 0.0;`;
      afterMetal = `roughnessFactor = mix(0.70, 0.52, uWetK) + tyrePrint * 0.1;`;           // r3: black rubber with a faint satin sheen (was 0.82: a flat grey)
    } else if (kind === 'nozzle') {
      U.uJet = shared.car.uJet;
      pars += `uniform float uJet;`;
      // thrusters firing: a faint cold sheen inside the bells and throats (bell a 0.30, throat a 0.85). The black ports and
      // the deep bell share a 0.45 and stay dark.
      afterEmissive = `#ifdef USE_COLOR_ALPHA
      { float a = vColor.a; float bell = step(0.27, a) * (1.0 - step(0.34, a)); float thr = step(0.8, a) * (1.0 - step(0.87, a));
        totalEmissiveRadiance += vec3(0.40, 0.62, 1.0) * uJet * (bell * 0.22 + thr * 0.9); }
      #endif`;
      // vertex alpha = roughness; rough parts (> 0.7: fan shrouds, blades, backing) are dark paint, not metal
      afterMetal = `#ifdef USE_COLOR_ALPHA\nroughnessFactor = clamp(vColor.a, 0.05, 1.0); metalnessFactor = 1.0 - step(0.7, vColor.a);\n#endif`;
      // no shadows in this renderer: the rough parts sit deep in the diffuser bays, so they get a fixed cavity occlusion
      beforeEnd = `#ifdef USE_COLOR_ALPHA
      { float occ = vColor.a > 0.85 ? 0.08 : (vColor.a > 0.7 ? 0.3 : 1.0);
        radiance *= occ; iblIrradiance *= occ; irradiance *= occ; reflectedLight.directDiffuse *= occ; reflectedLight.directSpecular *= occ; }
      #endif`;
    } else if (kind === 'carbon') {
      U.uWetK = shared.car.uWetK;
      pars += `uniform float uWetK;` + CARBON_PARS;
      afterColor = CARBON_COLOR;
      afterMetal = `roughnessFactor = mix(roughnessFactor * (1.15 - 0.3 * cfTow), roughnessFactor * 0.7, uWetK);`;
      afterNormal = CARBON_NORMAL;
    } else if (kind === 'trim') {
      U.uWetK = shared.car.uWetK;
      pars += `uniform float uWetK;`;
      afterMetal = `roughnessFactor *= mix(1.0, 0.62, uWetK);`;
    } else if (kind === 'lamp') {
      const pat = {
        head: `{ float u = vUvC.x, v = vUvC.y; float cell = fract(u * 15.0); float led = smoothstep(0.0, 0.16, cell) * smoothstep(1.0, 0.84, cell);
          float e = smoothstep(0.0, 0.22, v) * smoothstep(1.0, 0.78, v) * smoothstep(0.0, 0.05, u) * smoothstep(1.0, 0.95, u);
          totalEmissiveRadiance *= (0.28 + 0.72 * led) * (0.25 + 0.75 * e) * (1.0 + 0.5 * smoothstep(0.3, 0.0, abs(v - 0.5))); }`,
        brake: `{ float u = vUvC.x, v = vUvC.y;     // continuous light guide: soft top / bottom, no LED cells
          float e = smoothstep(0.0, 0.4, v) * smoothstep(1.0, 0.6, v) * smoothstep(0.0, 0.02, u) * smoothstep(1.0, 0.98, u);
          totalEmissiveRadiance *= 0.15 + 0.85 * e; }`,
        rev: `{ float u = vUvC.x, v = vUvC.y; float e = smoothstep(0.0, 0.25, v) * smoothstep(1.0, 0.75, v) * smoothstep(0.0, 0.1, u) * smoothstep(1.0, 0.9, u);
          totalEmissiveRadiance *= 0.3 + 0.7 * e; }`,
      }[shared.lampKind] ?? '';
      afterEmissive = pat;
    }

    // hot probe pixels (lamp heads, signs) would bloom the whole body white at grazing angles: cap the reflected radiance
    beforeEnd = `#if defined( RE_IndirectSpecular )\nradiance = min(radiance, vec3(3.0)); clearcoatRadiance = min(clearcoatRadiance, vec3(3.0));\n#endif\n` + beforeEnd;
    shader.vertexShader = shader.vertexShader
      .replace('#include <common>', '#include <common>\n' + VERT_PARS)
      .replace('#include <begin_vertex>', '#include <begin_vertex>\n' + VERT_MAIN);
    let f = shader.fragmentShader;
    f = f.replace('#include <common>', '#include <common>\n' + pars);
    f = f.replace('void main() {', 'void main() {\n' + LOD_DISCARD);
    if (afterColor) f = f.replace('#include <color_fragment>', '#include <color_fragment>\n' + afterColor);
    if (afterMetal) f = f.replace('#include <metalnessmap_fragment>', '#include <metalnessmap_fragment>\n' + afterMetal);
    if (afterNormal) f = f.replace('#include <normal_fragment_maps>', '#include <normal_fragment_maps>\n' + afterNormal);
    if (afterCoat) f = f.replace('#include <clearcoat_normal_fragment_maps>', '#include <clearcoat_normal_fragment_maps>\n' + afterCoat);
    if (afterEmissive) f = f.replace('#include <emissivemap_fragment>', '#include <emissivemap_fragment>\n' + afterEmissive);
    if (afterPhys) f = f.replace('#include <lights_physical_fragment>', '#include <lights_physical_fragment>\n' + afterPhys);
    if (beforeEnd) f = f.replace('#include <lights_fragment_end>', beforeEnd + '\n#include <lights_fragment_end>');
    if (opaque) f = f.replace('#include <opaque_fragment>', opaque);
    shader.fragmentShader = f;
  };
  return mat;
}

// ------------------------------------------------------------------------------------- material set per LOD
const lin = (h) => new THREE.Color(h);   // THREE.Color(hex) interprets sRGB and stores linear

/**
 * @returns {{ mats: Record<string, THREE.Material>, lamps, dyn }} materials for one LOD of one car.
 * shared: { lod:{uLodT,uLodDir}, car:{uBead,uHeat,uWetK,uGlassAbs,uJet}, paint:{uFlake,uFlakeColor,uPearl,uPeel,uAccent} }
 */
export function createMaterialSet(livery, lod, shared, { env = null, atlas = null } = {}) {
  const P = livery.paint;
  const mats = {};
  const envI = (m, k) => { m.envMap = env; m.envMapIntensity = k; return m; };
  const sh = (extra = {}) => ({ ...shared, ...extra });

  // ---- paint
  const paint = new THREE.MeshPhysicalMaterial({
    color: lin(P.color), metalness: P.metalness, roughness: P.roughness, clearcoat: P.clearcoat, clearcoatRoughness: P.coatRough,
    side: THREE.DoubleSide, ior: 1.5, specularIntensity: 1,
  });
  envI(paint, 1.25);
  mats.Paint = patch(paint, 'paint', lod, shared);

  // ---- glass: premultiplied alpha, double sided (back faces first), tinted reflections
  const glass = new THREE.MeshPhysicalMaterial({
    color: new THREE.Color(0x0a0603), metalness: 0, roughness: 0.035, ior: 1.52, specularIntensity: 1,
    specularColor: new THREE.Color(1.0, 0.82, 0.62), side: lod < 2 ? THREE.DoubleSide : THREE.FrontSide, transparent: true, depthWrite: false,
    blending: THREE.CustomBlending, blendSrc: THREE.OneFactor, blendDst: THREE.OneMinusSrcAlphaFactor, blendEquation: THREE.AddEquation,
    premultipliedAlpha: false,
  });
  envI(glass, 1.7);
  mats.Glass = patch(glass, 'glass', lod, shared);

  // ---- trim / panel gaps
  const trim = new THREE.MeshStandardMaterial({ color: new THREE.Color(0x0b0b0c), roughness: 0.5, metalness: 0.0, side: THREE.DoubleSide });
  envI(trim, 0.8);
  mats.Trim = patch(trim, 'trim', lod, shared);
  // carbon (diffuser, skirts, splitter, wing struts): clear-coated twill
  const carbon = new THREE.MeshPhysicalMaterial({ color: new THREE.Color(0x1d1e22), roughness: 0.34, metalness: 0.25, clearcoat: 0.8,
    clearcoatRoughness: 0.1, side: THREE.DoubleSide });
  envI(carbon, 1.0);
  mats.Carbon = patch(carbon, 'carbon', lod, shared);
  // piano-black acrylic (light band, wing well)
  const gloss = new THREE.MeshPhysicalMaterial({ color: new THREE.Color(0x020203), roughness: 0.16, metalness: 0, clearcoat: 1,
    clearcoatRoughness: 0.02, side: THREE.DoubleSide });
  envI(gloss, 1.3);
  mats.GlossBlack = patch(gloss, 'plain', lod, shared);
  // thruster nozzles / ports / diffuser fans: bare metal, colour per vertex (polished brass lip, heat-tinted bell, dark fans)
  const nozzle = new THREE.MeshStandardMaterial({ color: 0xffffff, vertexColors: true, roughness: 0.24, metalness: 1.0, side: THREE.DoubleSide });
  envI(nozzle, 1.25);
  mats.Nozzle = patch(nozzle, 'nozzle', lod, shared);
  const gap = new THREE.MeshStandardMaterial({ color: new THREE.Color(0x050506), roughness: 0.85, metalness: 0.0 });
  envI(gap, 0.5); gap.polygonOffset = true; gap.polygonOffsetFactor = -1; gap.polygonOffsetUnits = -1;
  mats.PanelGap = patch(gap, 'plain', lod, shared);
  // q8: the intake's insides (liner, slats, frame; hi only) read as a deep black hole in the photos, not lit slats
  const gapDark = new THREE.MeshStandardMaterial({ color: new THREE.Color(0x000000), roughness: 1.0, metalness: 0.0 });
  envI(gapDark, 0.0);
  mats.PanelGapDark = patch(gapDark, 'plain', lod, shared);

  // ---- lamps (emissive intensities are driven every frame)
  const lamp = (name, base, emis, kind) => {
    const m = new THREE.MeshStandardMaterial({ color: base, roughness: 0.18, metalness: 0, emissive: emis, emissiveIntensity: 0, toneMapped: false, side: THREE.DoubleSide });
    envI(m, 0.9);
    const lampShared = { ...shared, lampKind: kind };
    mats[name] = patch(m, 'lamp', lod, lampShared);
    return m;
  };
  const lamps = {
    // FRONT r2: the photo's night view has ONE lit line, the light bar.  HeadLens (the dark strip under it) never glows: black emissive, so index.js's `head` intensity (60 * headS) does nothing; the
    // headlight output it used to carry is added to the bar: index.js drives the bar at 48 * headS, so its emissive colour is scaled by 1.6 (HDR, > 1 is fine; 1.6 not (48 + 60) / 48 = 2.25: the photo's bar is a crisp line, not a wide bloom).  Lamps off = both dark, as before.
    head: lamp('HeadLens', new THREE.Color(0x0b0c0f), new THREE.Color(0, 0, 0), 'head'),
    drl: lamp('HeadDRL', new THREE.Color(0x303640), new THREE.Color(0.92 * 1.6, 0.96 * 1.6, 1.0 * 1.6), 'none'),
    tail: lamp('TailLamp', new THREE.Color(0x2a0405), new THREE.Color(1.0, 0.05, 0.035), 'none'),
    brake: lamp('BrakeLamp', new THREE.Color(0x230304), new THREE.Color(1.0, 0.04, 0.025), 'brake'),
    reverse: lamp('ReverseLamp', new THREE.Color(0x3a3d42), new THREE.Color(0.95, 0.97, 1.0), 'rev'),
    side: lamp('SideMarker', new THREE.Color(0x2a1004), new THREE.Color(1.0, 0.32, 0.06), 'none'),
  };
  // the bar stands only 0.6 mm off the nose face (FRONT r2): without a depth bias the face z-fights through it and the bar breaks into dashes
  lamps.drl.polygonOffset = true; lamps.drl.polygonOffsetFactor = -1; lamps.drl.polygonOffsetUnits = -2;

  // ---- tyres, rims, brakes
  const tyre = new THREE.MeshStandardMaterial({ color: new THREE.Color(0x0a0a0b), roughness: 0.70, metalness: 0 });     // FRONT r3: black (the photos' rubber reads 5-13 / 255)
  envI(tyre, 0.9);
  mats.Tyre = patch(tyre, 'tyre', lod, shared);
  const rim = new THREE.MeshPhysicalMaterial({ color: 0xffffff, vertexColors: true, roughness: 0.4, metalness: 0.0, clearcoat: 0.6, clearcoatRoughness: 0.08, side: THREE.DoubleSide });
  envI(rim, 1.2);
  mats.Rim = patch(rim, 'rim', lod, shared);
  const disc = new THREE.MeshStandardMaterial({ color: new THREE.Color(0x4a4a50), roughness: 0.45, metalness: 0.9 });
  mats.BrakeDisc = patch(envI(disc, 1.0), 'plain', lod, shared);
  const cal = new THREE.MeshStandardMaterial({ color: lin(livery.rim.accent), roughness: 0.3, metalness: 0.45 });
  mats.Caliper = patch(envI(cal, 1.0), 'plain', lod, shared);
  // side / rear red reflectors: fixed dark red (not the livery accent), glossy so they catch light, never lit
  const refl = new THREE.MeshStandardMaterial({ color: new THREE.Color(0x7a0e08), roughness: 0.22, metalness: 0 });
  mats.Reflector = patch(envI(refl, 1.1), 'plain', lod, shared);

  // ---- interior (dark, low env: light only comes in through the tinted glass)
  const leather = new THREE.MeshStandardMaterial({ color: new THREE.Color(0x1a1a1e), roughness: 0.52, metalness: 0 });
  mats.IntLeather = patch(envI(leather, 0.55), 'plain', lod, shared);
  const plastic = new THREE.MeshStandardMaterial({ color: new THREE.Color(0x0e0e10), roughness: 0.62, metalness: 0 });
  mats.IntPlastic = patch(envI(plastic, 0.45), 'plain', lod, shared);
  const screen = new THREE.MeshStandardMaterial({ color: 0x050a10, roughness: 0.25, metalness: 0, emissive: 0xffffff, emissiveIntensity: 1.0, toneMapped: false });
  mats.IntScreen = patch(envI(screen, 0.5), 'plain', lod, shared);
  const accent = new THREE.MeshStandardMaterial({ color: lin(livery.rim.accent), roughness: 0.3, metalness: 1.0 });
  mats.IntAccent = patch(envI(accent, 0.9), 'plain', lod, shared);

  // ---- decals: vinyl under the clear coat
  const decal = new THREE.MeshPhysicalMaterial({
    color: 0xffffff, map: atlas, transparent: true, depthWrite: false, roughness: 0.38, metalness: 0.0, clearcoat: 1, clearcoatRoughness: 0.04,
    polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2, side: THREE.FrontSide,
  });
  envI(decal, 1.1);
  mats.Decal = patch(decal, 'decal', lod, shared);

  return { mats, lamps };
}

/** a 'plain' kind = lod dither + object varyings only */
// (handled by patch(): unknown kinds add no extra code)

// -------------------------------------------------------------------------------- speed-blur wheel disc
/**
 * Transparent disc over the rim face. Shows the six spokes (2026-10-25: a gloss-black blade, half width 2.5 cm, with a graphite band to 3.1 cm and a bright
 * edge line to 3.6 cm; a dark slot out to the aero panel's edge, 4.7 cm from the spoke axis at r 0.26 leaning out to 5.6 cm at r 0.14) and the body-colour
 * panels, box-blurred over the rotation angle covered in one shutter time; alpha ramps in with spin rate so the strobing of the real spokes disappears.
 * The star hub (r < 11 cm) is left to the real geometry. Numbers = build_game_car.py (BL_BANDS, CH_E, S_ARM) at the nominal rim (FACE_R 0.296; the disc
 * node is scaled per axle by car_meta.json rimScale); spoke 0 points up, so the pattern is turned by 90 degrees.
 */
export function createBlurDiscMaterial(shared, accentColor) {
  const m = new THREE.MeshStandardMaterial({
    color: 0xffffff, transparent: true, depthWrite: false, roughness: 0.4, metalness: 0.4, side: THREE.DoubleSide,
    polygonOffset: true, polygonOffsetFactor: -3, polygonOffsetUnits: -3,
  });
  m.envMap = null; m.envMapIntensity = 1.0;
  const U = { uSpin: { value: 0 }, uBlurW: { value: 0 }, uBlurA: { value: 0 }, uAcc: { value: new THREE.Color(accentColor) }, uHeatB: shared.car.uHeat,
    uPlateC: shared.paint?.uPaintC ?? { value: new THREE.Color(0.6, 0.61, 0.63) } };
  m.userData.U = U;
  m.defines = { CAR_LOD: 0 };
  m.customProgramCacheKey = () => 'car:blur';
  m.onBeforeCompile = (shader) => {
    Object.assign(shader.uniforms, U);
    shader.uniforms.uLodT = shared.lod.uLodT; shader.uniforms.uLodDir = shared.lod.uLodDir;
    shader.vertexShader = shader.vertexShader
      .replace('#include <common>', '#include <common>\n' + VERT_PARS)
      .replace('#include <begin_vertex>', '#include <begin_vertex>\n' + VERT_MAIN);
    shader.fragmentShader = shader.fragmentShader
      .replace('#include <common>', `#include <common>\n${FRAG_COMMON}
        uniform float uSpin; uniform float uBlurW; uniform float uBlurA; uniform vec3 uAcc; uniform float uHeatB; uniform vec3 uPlateC;
        const float PERIOD = 1.0471975512;
        float cum(float x, float th) { float k = floor((x + th) / PERIOD); return k * 2.0 * th + clamp(x - k * PERIOD + th, 0.0, 2.0 * th); }
        float cover(float a, float w, float th) { return (cum(a + w, th) - cum(a - w, th)) / (2.0 * w); }
        float chHalf(float r, float t) { return r > t ? min(asin(t / r), 0.5236) : 0.5236; }`)
      .replace('void main() {', 'void main() {\n' + LOD_DISCARD)
      .replace('#include <color_fragment>', `#include <color_fragment>
        {
          float r = length(vObjPos.xy);
          float ang = atan(vObjPos.y, vObjPos.x) - uSpin - 1.5707963268;
          float w = max(uBlurW, 0.03);
          float open_ = cover(ang, w, chHalf(r, 0.0665 - 0.075 * r));       // everything between two panels' edges
          float line = cover(ang, w, chHalf(r, 0.036));                       // the blade, out to its bright edge lines
          float band = cover(ang, w, chHalf(r, 0.031));
          float core = cover(ang, w, chHalf(r, 0.025));                       // its gloss-black core
          vec3 slot = mix(vec3(0.004), uAcc * 0.3, 0.35 * (1.0 - smoothstep(0.105, 0.265, r)));      // dark slots, a little copper from their walls near the hub
          vec3 col = uPlateC * 0.9 * (1.0 - open_) + slot * max(open_ - line, 0.0) + vec3(0.55) * max(line - band, 0.0)
                   + vec3(0.05, 0.052, 0.058) * max(band - core, 0.0) + vec3(0.004) * core;
          float hub = smoothstep(0.122, 0.104, r);
          diffuseColor.rgb = col;
          diffuseColor.a = uBlurA * (1.0 - hub) * smoothstep(0.299, 0.293, r);
        }`)
      .replace('#include <emissivemap_fragment>', `#include <emissivemap_fragment>
        totalEmissiveRadiance += vec3(1.0, 0.25, 0.04) * uHeatB * uHeatB * 0.5 * smoothstep(0.12, 0.27, length(vObjPos.xy)) * diffuseColor.a;`);
  };
  return m;
}
