// World materials. Every lit material is a MeshStandardMaterial patched to add the baked static light (`aLit`) and the car
// headlights; `defs[key]` = { mat, extras (extra vertex attributes), bake (needs aLit), layer }.
import * as THREE from 'three';
import { phTextureSet } from '../core/assets.js';
import { G, HEADLIGHT_GLSL } from '../core/globals.js';
import { LAYER } from '../core/layers.js';
import { NOISE_GLSL, LIT_VERT_PARS, LIT_VERT_MAIN, LIT_FRAG_PARS, HEADLIGHTS_FRAG, BAKE_FRAG } from './glsl.js';
import { makeRoadMaterial } from './road_mat.js';
import { patchLit } from './litpatch.js';
import { makeFacade } from './facade_mat.js';
import { makeSignMaterial, makeScreenMaterial, makeHaloMaterial, makeHaloTexture, makeSteamMaterial, makeSteamTexture } from './signs_mat.js';
export { patchLit };

const PH_IDS = ['asphalt_track', 'asphalt_02', 'concrete_pavement', 'concrete_slab_wall', 'concrete_panels', 'concrete_tile_facade',
  'ribbed_concrete_wall', 'metal_plate', 'corrugated_iron_02', 'painted_metal_shutter', 'dark_brick_wall', 'rectangular_facade_tiles'];

export async function loadWorldTextures() {
  const sets = await Promise.all(PH_IDS.map(id => phTextureSet(id)));
  const t = {};
  PH_IDS.forEach((id, i) => { t[id] = sets[i]; });
  t.asphalt = t.asphalt_track; t.asphalt2 = t.asphalt_02;
  return t;
}

const rep = (tex, k) => { const c = tex.clone(); c.repeat.set(1 / k, 1 / k); c.needsUpdate = true; return c; };

const SOLID_MAP = /* glsl */`
#include <map_fragment>
{
  float mv = wNoise(vWPos.xz * .11 + vWPos.y * .07) * .6 + wNoise(vWPos.xz * .37 - vWPos.y * .2) * .4;
  diffuseColor.rgb *= mix(.7, 1.25, mv);
  float vert = 1. - abs(normalize(vNw).y);
  float st = smoothstep(.5, .95, wNoise(vec2(vMUv.x * 5.3, vMUv.y * .22)) * .7 + wNoise(vec2(vMUv.x * 17., vMUv.y * .6)) * .3);
  diffuseColor.rgb *= 1. - st * vert * STREAK;
}
`;

export function makeSolid(tex, { set, scale = 3, tint = 0xffffff, gain = 1, rough = 1, normalScale = 1, streak = 0.35, metal = 0, key, side } = {}) {
  const s = tex[set];
  const m = new THREE.MeshStandardMaterial({
    map: rep(s.map, scale), normalMap: rep(s.normalMap, scale), roughnessMap: rep(s.armMap, scale), metalnessMap: metal > 0 ? rep(s.armMap, scale) : null,
    aoMap: rep(s.armMap, scale), vertexColors: true, roughness: rough, metalness: metal, color: new THREE.Color(tint).multiplyScalar(gain),
  });
  m.normalScale.set(normalScale, normalScale);
  if (side) m.side = side;
  patchLit(m, {
    key: 'solid_' + (key ?? set),
    repl: {
      color_fragment: '#include <color_fragment>\ndiffuseColor.rgb *= diffuseColor.a; diffuseColor.a = 1.0;',
      map_fragment: SOLID_MAP.replace('STREAK', streak.toFixed(3)),
    },
  });
  return m;
}

/** Plain painted material (vertex colours, no textures). */
export function makePlain({ rough = 0.6, metal = 0, key = 'plain', gain = 1 } = {}) {
  const m = new THREE.MeshStandardMaterial({ vertexColors: true, roughness: rough, metalness: metal, color: new THREE.Color(gain, gain, gain) });
  patchLit(m, { key: 'plain_' + key, repl: { color_fragment: '#include <color_fragment>\ndiffuseColor.rgb *= diffuseColor.a; diffuseColor.a = 1.0;' } });
  return m;
}

const CROWD_MAP = /* glsl */`
{
  vec2 q = floor(vMUv * vec2(4.0, 3.0)); float h = wHash12(q), h2 = wHash12(q + 7.3);
  vec3 cloth = mix(vec3(.03, .03, .04), vec3(.12, .08, .06), h2) * (.6 + .8 * wHash12(q * 1.7));
  float spark = step(.9, h) * (.35 + .65 * sin(uTime * (1.5 + h2 * 5.) + h * 60.) * .5 + .325);
  vec3 wand = mix(vec3(.3, .9, 1.), mix(vec3(1., .3, .8), vec3(1., .75, .3), step(.5, h2)), step(.33, h2));
  diffuseColor.rgb = cloth;
  totalEmissiveRadiance += wand * spark * .9 * step(.5, 1. - fract(vMUv.y * 3.));
}
`;

export function makeGlass() {
  const m = new THREE.MeshStandardMaterial({ vertexColors: true, transparent: true, opacity: 0.32, roughness: 0.12, metalness: 0.0, depthWrite: false, side: THREE.DoubleSide });
  patchLit(m, { key: 'glass', repl: { color_fragment: '#include <color_fragment>\ndiffuseColor.rgb *= 0.5;' } });
  return m;
}

const WATER_NORMAL = /* glsl */`
{
  vec2 w1 = vWPos.xz * 0.28 + vec2(uTime * .04, uTime * .025);
  vec2 w2 = vWPos.xz * 0.9 - vec2(uTime * .06, -uTime * .05);
  float h0 = wFbm(w1) + wFbm(w2) * .3, hx = wFbm(w1 + vec2(.03, 0.)) + wFbm(w2 + vec2(.03, 0.)) * .3, hz = wFbm(w1 + vec2(0., .03)) + wFbm(w2 + vec2(0., .03)) * .3;
  vec3 nw = normalize(vec3(-(hx - h0) * 5., 1., -(hz - h0) * 5.));
  wNw = nw;
  normal = normalize((viewMatrix * vec4(nw, 0.)).xyz);
}
`;
const WATER_END = /* glsl */`
{
  float gz = pow(1.0 - clamp(dot(geometryNormal, geometryViewDir), 0., 1.), 2.0);
  reflectedLight.indirectSpecular += vLit * (RECIPROCAL_PI * (0.06 + 0.8 * gz));
  // mirror glints of the 8 lights nearest to the camera (updated by world.update): lamps, neon, boat lights, cranes
  vec3 Vw = normalize(cameraPosition - vWPos);
  vec3 Rw = reflect(-Vw, wNw);
  vec3 gl = vec3(0.);
  for (int i = 0; i < 8; i++) {
    float rg = uWL[i].w; if (rg <= 0.) continue;
    vec3 Ld = uWL[i].xyz - vWPos; float dd = length(Ld); vec3 l = Ld / max(dd, .5);
    float sp = pow(max(dot(l, Rw), 0.), 150.);
    float fall = clamp(1. - dd / rg, 0., 1.);
    gl += uWC[i] * sp * fall;
  }
  float fr = .08 + .92 * pow(1.0 - clamp(dot(geometryNormal, geometryViewDir), 0., 1.), 4.0);
  reflectedLight.indirectSpecular += min(gl, vec3(2.5)) * fr;
}
`;
export function makeWater() {
  const m = new THREE.MeshStandardMaterial({ color: 0x07262c, roughness: 0.05, metalness: 0.0, vertexColors: true });
  const uniforms = { uWL: { value: Array.from({ length: 8 }, () => new THREE.Vector4(0, 0, 0, 0)) }, uWC: { value: Array.from({ length: 8 }, () => new THREE.Vector3()) } };
  m.userData.uniforms = uniforms;
  patchLit(m, { key: 'water', uniforms, fragPars: 'vec3 wNw = vec3(0.,1.,0.); uniform vec4 uWL[8]; uniform vec3 uWC[8];', repl: {
    normal_fragment_maps: WATER_NORMAL,
    lights_fragment_end: WATER_END + '\n#include <lights_fragment_end>',
  } });
  return m;
}

export function makeEmissive(gain) {
  const m = new THREE.MeshBasicMaterial({ vertexColors: true, color: new THREE.Color(gain, gain, gain) });
  return m;
}

/** Build the material table. Returns defs: key → { mat, extras, bake, layer }. */
export function createDefs(tex, atlas, rs, boardTex, graf) {
  const D = {};
  const lit = (key, mat, extras = {}, layer = LAYER.DEFAULT) => { D[key] = { key, mat, extras, bake: true, layer }; return D[key]; };
  const unlit = (key, mat, extras = {}, layer = LAYER.DEFAULT) => { D[key] = { key, mat, extras, bake: false, layer }; return D[key]; };

  const road = makeRoadMaterial(tex);
  lit('road', road, { aRoad: 4 }, LAYER.MAIN_ONLY);
  lit('conc', makeSolid(tex, { set: 'concrete_slab_wall', scale: 3.5, gain: 0.9 }));
  lit('concD', makeSolid(tex, { set: 'concrete_panels', scale: 4, gain: 0.8 }));
  lit('rib', makeSolid(tex, { set: 'ribbed_concrete_wall', scale: 3, gain: 1.1 }));
  lit('pave', makeSolid(tex, { set: 'concrete_pavement', scale: 3.2, gain: 0.85, streak: 0.1 }));
  const gm = makeSolid(tex, { set: 'concrete_pavement', scale: 4.5, gain: 0.6, streak: 0.0, key: 'gnd' });
  gm.polygonOffset = true; gm.polygonOffsetFactor = -1; gm.polygonOffsetUnits = -4;
  lit('gnd', gm);
  lit('tile', makeSolid(tex, { set: 'rectangular_facade_tiles', scale: 2.6, gain: 1.05, tint: 0xd8e4ff, streak: 0.15 }));
  lit('brick', makeSolid(tex, { set: 'dark_brick_wall', scale: 3, gain: 1.0 }));
  lit('corr', makeSolid(tex, { set: 'corrugated_iron_02', scale: 3, gain: 1.2 }));
  lit('shut', makeSolid(tex, { set: 'painted_metal_shutter', scale: 2.4, gain: 0.8 }));
  lit('plate', makeSolid(tex, { set: 'metal_plate', scale: 1.5, gain: 1.2, metal: 0.6 }));
  lit('steel', makePlain({ rough: 0.42, metal: 0.75, key: 'steel' }));
  lit('paint', makePlain({ rough: 0.55, metal: 0.1, key: 'paint' }));
  lit('bldgA', makeFacade(tex, { set: 'concrete_panels', key: 'A', scale: 4 }), { aFac: 4, aFac2: 4 });
  lit('bldgB', makeFacade(tex, { set: 'dark_brick_wall', key: 'B', scale: 3 }), { aFac: 4, aFac2: 4 });
  lit('bldgC', makeFacade(tex, { set: 'corrugated_iron_02', key: 'C', scale: 3 }), { aFac: 4, aFac2: 4 });
  lit('glass', makeGlass());
  lit('water', makeWater());
  for (const g of [2, 6, 16, 40]) unlit('em' + g, makeEmissive(g));
  unlit('sign', makeSignMaterial(atlas), { aFl: 2 });
  unlit('screen', makeScreenMaterial(atlas), { aScr: 4 });
  { const bm = new THREE.MeshBasicMaterial({ map: boardTex, vertexColors: true, color: new THREE.Color(2.6, 2.6, 2.6) }); unlit('board', bm); }
  { const rm = new THREE.MeshStandardMaterial({ map: rs.tex, emissiveMap: rs.tex, emissive: new THREE.Color(0.55, 0.55, 0.55), vertexColors: true, roughness: 0.5, metalness: 0.0 });
    patchLit(rm, { key: 'roadsign' }); lit('roadsign', rm); }
  { const cm = new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.9, metalness: 0 });
    patchLit(cm, { key: 'crowd', repl: { map_fragment: CROWD_MAP, color_fragment: '' } }); lit('crowd', cm); }
  unlit('halo', makeHaloMaterial(makeHaloTexture()), { aCorner: 3 });
  D.halo.mat.userData.noReflect = true;
  if (graf) {
    const gm = new THREE.MeshStandardMaterial({ map: graf.tex, vertexColors: true, alphaTest: 0.3, roughness: 0.85, metalness: 0 });
    gm.polygonOffset = true; gm.polygonOffsetFactor = -2; gm.polygonOffsetUnits = -4;
    patchLit(gm, { key: 'graf' });
    lit('graf', gm);
  }
  lit('steam', makeSteamMaterial(makeSteamTexture()), { aCorner: 3, aSt: 3 }, LAYER.LATE);
  return D;
}
