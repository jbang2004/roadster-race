// The wet asphalt material: MeshStandardMaterial patched with procedural lanes / wear / puddles / wheel tracks,
// baked static lamp light, planar wet reflection (RF) and car headlights (G.uHead*).
import * as THREE from 'three';
import { G, HEADLIGHT_GLSL } from '../core/globals.js';
import { RF, REFLECT_GLSL } from '../core/reflect.js';
import { NOISE_GLSL, LIT_VERT_PARS, LIT_VERT_MAIN, LIT_FRAG_PARS, HEADLIGHTS_FRAG, BAKE_FRAG } from './glsl.js';

const ROAD_FRAG_PARS = /* glsl */`
uniform sampler2D tAsph, tAsphN, tAsphR, tCrk, tCrkN;
uniform float uStartS;
uniform vec2 uSlot[8];
uniform float uSheen;
varying vec4 vRoad;
vec3 rdNw; float rdRoughF; float rdReflK; float rdWetF; float rdPudF;
${HEADLIGHT_GLSL}
${REFLECT_GLSL}
${NOISE_GLSL}
// zone: 0 boulevard 1 street 2 docks 3 ramp 4 expressway 5 descent 6 tunnel 7 market
vec4 zoneParams(float z) {            // lanes, doubleCentre, edgeLines, wear
  if (z < 0.5) return vec4(4., 1., 1., .22);
  if (z < 1.5) return vec4(2., 0., 1., .42);
  if (z < 2.5) return vec4(2., 1., 1., .68);
  if (z < 3.5) return vec4(3., 0., 1., .35);
  if (z < 4.5) return vec4(4., 0., 1., .26);
  if (z < 5.5) return vec4(3., 0., 1., .38);
  if (z < 6.5) return vec4(3., 0., 1., .30);
  return vec4(2., 0., 0., .86);
}
float zoneCrack(float z) { return z < .5 ? .25 : z < 1.5 ? .55 : z < 2.5 ? .95 : z < 3.5 ? .3 : z < 4.5 ? .2 : z < 5.5 ? .45 : z < 6.5 ? .3 : .95; }
float lineStripe(float x, float w) { float fw = max(fwidth(x), 1e-4); return clamp((w * .5 - abs(x)) / fw + .5, 0., 1.); }
float dashPat(float s, float period, float duty) {
  float t = s / period; float f = fract(t); float fw = max(fwidth(t), 1e-4);
  return clamp((duty - f) / fw + .5, 0., 1.) * clamp(f / fw + .5, 0., 1.);
}
vec2 rippleN(vec2 p, float t, float rain) {
  vec2 q = p * 1.7; vec2 id = floor(q); vec2 f = fract(q) - .5; float h = wHash12(id);
  vec2 off = (wHash22(id + 3.1) - .5) * .5; f -= off;
  float ph = fract(t * (.55 + .5 * h) + h * 7.0);
  float r = length(f); float x = r - ph * .45;
  float env = exp(-x * x / 0.0035) * (1. - ph) * step(h, rain * .8 + .08);
  float d = cos(x * 38.) * env;
  return (f / max(r, 1e-3)) * d * .55;
}
`;

const ROAD_MAP = /* glsl */`
{
  vec2 wp = vec2(vWPos.x, -vWPos.z);
  float s = vRoad.x, u = vRoad.y, hw = vRoad.z;
  float zk = vRoad.w; float zone = floor(zk / 8.0 + 0.001); float kindv = zk - zone * 8.0;
  vec4 zp = zoneParams(zone);
  float nl = zp.x, wearK = zp.w;
  float lw = 2.0 * hw / nl;
  float wet = clamp(uWet, 0., 1.);
  float inTunnel = step(5.5, zone) * step(zone, 6.5);
  wet *= mix(1.0, 0.8, inTunnel);

  // --- base asphalt (two rotated scales, fine grain) ---
  vec2 uvA = wp / 2.1; mat2 R1 = wRot(0.9); vec2 uvB = R1 * wp / 3.4 + 0.37;
  vec3 aA = texture2D(tAsph, uvA).rgb, aB = texture2D(tAsph, uvB).rgb;
  vec3 alb = (aA + aB) * 0.5 * 1.7;
  vec3 nA = texture2D(tAsphN, uvA).xyz * 2. - 1., nB = texture2D(tAsphN, uvB).xyz * 2. - 1.;
  nB.xy = nB.xy * R1;
  vec3 nm = normalize(vec3(nA.xy + nB.xy, nA.z * nB.z));
  float armR = texture2D(tAsphR, uvA).g;
  // large-scale break-up of tone
  float macro = wFbm(wp * 0.035) * 0.6 + wFbm(wp * 0.21 + 5.) * 0.4;
  alb *= mix(0.75, 1.3, macro);

  // --- cracked / patched old asphalt (stochastic cells of asphalt_02) ---
  vec2 cc = wp / 9.0; vec2 ci = floor(cc), cf = fract(cc);
  float ch = wHash12(ci + 1.7);
  vec2 cuv = cf; if (ch > .5) cuv = cuv.yx; if (fract(ch * 7.) > .5) cuv.x = 1. - cuv.x; if (fract(ch * 13.) > .5) cuv.y = 1. - cuv.y;
  cuv += wHash22(ci);
  vec2 gx = dFdx(cc), gy = dFdy(cc); if (ch > .5) { gx = gx.yx; gy = gy.yx; }
  vec3 crk = textureGrad(tCrk, cuv, gx, gy).rgb;
  vec3 crkN = textureGrad(tCrkN, cuv, gx, gy).xyz * 2. - 1.;
  float cedge = smoothstep(0., .06, min(min(cf.x, 1. - cf.x), min(cf.y, 1. - cf.y)));
  float gate = smoothstep(.5, .72, wFbm(wp * 0.05 + 3.)) * cedge * zoneCrack(zone);
  float crackLum = dot(crk, vec3(.33));
  float crack = (1. - smoothstep(.025, .085, crackLum)) * gate;
  float oldA = smoothstep(.55, .75, wFbm(wp * 0.027 + 9.)) * zoneCrack(zone);   // whole old patches (no cell borders: tone modulation only)
  alb *= mix(1., clamp(crackLum / .2, .6, 1.25), oldA * .7);
  alb = mix(alb, vec3(0.004), crack * .8);
  nm.xy += crkN.xy * oldA * .6;

  // --- repair patches (rectangles in lane space) ---
  vec2 pc = vec2(s / 7.0, (u + hw) / (lw * .5));
  pc += (vec2(wFbm(wp * 1.1), wFbm(wp * 1.1 + 7.)) - .5) * .12;
  vec2 pid = floor(pc); float phh = wHash12(pid * 1.3 + zone * 13.7);
  vec2 pf = fract(pc);
  float inRect = step(.06, pf.x) * step(pf.x, .94) * step(.1, pf.y) * step(pf.y, .9) * step(0., pc.y) * step(pc.y, nl * 2.);
  float rpatch = step(.9 - wearK * .1, phh) * inRect;
  alb *= mix(1., .82 + .3 * wHash12(pid + 4.4), rpatch);

  // --- wheel tracks ---
  float lanePos = (u + hw) / lw; float laneId = floor(lanePos);
  float lc = (fract(lanePos) - .5) * lw;
  float usage = .5 + .5 * wNoise(vec2(s * .035, laneId * 5.3 + zone));
  float inLanes = step(0., lanePos) * step(lanePos, nl);
  float track = exp(-pow(abs(abs(lc) - .83), 2.) / (2. * .24 * .24)) * usage * inLanes;
  float gut = smoothstep(hw - .3, hw + .1, abs(u));

  // --- lane paint ---
  float yellowM = 0.0, paint = 0.0;
  float en = zp.z;
  float edge = lineStripe(abs(u) - (hw - .3), .17) * en;
  paint = max(paint, edge);
  float period = (zone > 3.5 && zone < 6.5) ? 12.0 : 9.0; float duty = (zone > 3.5 && zone < 6.5) ? .25 : .34;
  for (int k = 1; k < 5; k++) {
    if (float(k) >= nl - .01) break;
    float uk = -hw + lw * float(k);
    bool centre = abs(float(k) - nl * .5) < .01;
    if (centre && zp.y > .5) {
      float dbl = max(lineStripe(u - uk - .15, .11), lineStripe(u - uk + .15, .11));
      yellowM = max(yellowM, dbl); paint = max(paint, dbl);
    } else if (zone > 6.9 && centre) {
      float dl = lineStripe(u - uk, .13) * dashPat(s, 7., .4); yellowM = max(yellowM, dl); paint = max(paint, dl);
    } else if (zone < 6.9) {
      paint = max(paint, lineStripe(u - uk, .13) * dashPat(s, period, duty));
    }
  }
  // lane arrows: a few small chevrons just before zone changes are skipped; start/finish + grid boxes:
  float sd = s - uStartS;
  float chk = 0.0, startM = 0.0;
  if (abs(sd) < 50.0) {
    float cu = floor(u / .5), cs = floor((sd + .5) / .5);
    float inLine = step(abs(sd), .5) * step(abs(u), hw + .4);
    float chkv = mod(cu + cs, 2.);
    startM = inLine; chk = chkv;
    for (int k = 0; k < 8; k++) {
      vec2 sl = uSlot[k]; float ds = s - sl.x, du = u - sl.y;
      float ax = abs(du), ay = abs(ds);
      float hor = step(abs(ay - 2.9), .07) * step(.55, ax) * step(ax, 1.57);
      float ver = step(abs(ax - 1.5), .07) * step(2.0, ay) * step(ay, 2.97);
      float gb = max(hor, ver);
      paint = max(paint, gb);
    }
  }
  float pw = wFbm(wp * 1.9) * .65 + wFbm(wp * 8.) * .35;
  float vis = smoothstep(wearK * .85 - .1, wearK * .85 + .3, pw);
  float paintM = paint * vis;
  float startMask = startM * (1. - wearK * .4 * smoothstep(.5, .9, pw));
  vec3 white = vec3(.62, .62, .58), yel = vec3(.62, .40, .04);
  vec3 pcol = mix(white, yel, yellowM);

  // --- wetness / puddles ---
  float dryOld = max(oldA * .7, rpatch * .25);
  float wetP = wet * mix(.5, 1., smoothstep(.2, .8, wFbm(wp * .06 + 3.)));
  float pudd = wFbm(wp * .19 + 11.) + .13 * gut + .06 * track - (.605 + .05 * (1. - clamp(uRain, 0., 1.)));
  float puddle = smoothstep(0., .04, pudd) * wet * (1. - dryOld) * (1. - inTunnel * .6);
  float rough = mix(.62, .40, wetP);
  rough = mix(rough, .10, track * wet * .85);
  rough = mix(rough, .03, puddle);
  rough = mix(rough, .8, clamp(dryOld + crack * .6, 0., 1.));
  rough = mix(rough, .6, paintM * .8);
  rough = mix(rough, 0.75, gut * .35 * (1. - puddle));
  rough *= mix(.9, 1.1, armR);

  alb *= mix(1., .62, wet * (1. - dryOld * .8));
  alb *= mix(1., .82, track * wet);
  alb *= mix(1., .7, gut * .6);
  alb = mix(alb, pcol * mix(1., .7, wet), paintM);
  alb = mix(alb, mix(white, vec3(.02), chk) , startMask);
  alb *= mix(1., .62, puddle);
  rough = mix(rough, .45, startMask);

  // bump → world normal
  nm.xy *= mix(1., .5, wet) * (1. - puddle * .95) * (1. - paintM * .6);
  nm.xy += rippleN(wp, uTime, uRain) * puddle * .5;
  nm = normalize(vec3(nm.xy, max(nm.z, .3)));
  vec3 Ng = normalize(vNw);
  vec3 Tw = normalize(vec3(1., 0., 0.) - Ng * Ng.x);
  vec3 Bw = cross(Ng, Tw);
  rdNw = normalize(Tw * nm.x + Bw * nm.y + Ng * nm.z);
  rdRoughF = clamp(rough, .03, 1.);
  rdWetF = wet; rdPudF = puddle;
  rdReflK = mix(.35, 1., wetP) * (1. - paintM * .85) * (1. - dryOld * .85) * (1. - startMask * .8);
  diffuseColor.rgb = alb;
}
`;

const ROAD_END = /* glsl */`
{
  // planar wet reflection replaces the HDRI reflection on the road when R provides it
  radiance *= mix(1.0, 0.15, uReflectOn);
  vec3 envB = EnvironmentBRDF(geometryNormal, geometryViewDir, material.specularColorBlended, material.specularF90, material.roughness);
  vec3 refl = roadReflection(vWPos, rdNw, rdRoughF, mix(.85, .12, rdPudF));
  reflectedLight.indirectSpecular += refl * envB * rdReflK;
  // hazy lamp pools on the wet surface (sheen of the baked light at grazing angles)
  float gz = pow(1.0 - clamp(dot(geometryNormal, geometryViewDir), 0., 1.), 3.);
  reflectedLight.indirectSpecular += vLit * (RECIPROCAL_PI * uSheen * rdWetF * (0.15 + gz) * (1.0 - rdRoughF * .5));
}
`;

export function makeRoadMaterial(tex) {
  const m = new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 0.5, metalness: 0 });
  m.polygonOffset = true; m.polygonOffsetFactor = -2; m.polygonOffsetUnits = -6;
  const uniforms = {
    tAsph: { value: tex.asphalt.map }, tAsphN: { value: tex.asphalt.normalMap }, tAsphR: { value: tex.asphalt.armMap },
    tCrk: { value: tex.asphalt2.map }, tCrkN: { value: tex.asphalt2.normalMap },
    uStartS: { value: 0 }, uSlot: { value: Array.from({ length: 8 }, () => new THREE.Vector2(-1e4, 0)) },
    uWet: G.uWet, uRain: G.uRain, uTime: G.uTime, uSheen: { value: 0.06 },
    uHeadK: { value: 1 }, uBakeK: { value: 1 },
    uHeadCount: G.uHeadCount, uHeadPos: G.uHeadPos, uHeadDir: G.uHeadDir, uHeadColor: G.uHeadColor,
    tReflect: RF.tReflect, uReflectMatrix: RF.uReflectMatrix, uReflectOn: RF.uReflectOn, uReflectLod: RF.uReflectLod,
  };
  m.userData.uniforms = uniforms;
  m.onBeforeCompile = (sh) => {
    Object.assign(sh.uniforms, uniforms);
    sh.vertexShader = sh.vertexShader
      .replace('#include <common>', `#include <common>\n${LIT_VERT_PARS}\nattribute vec4 aRoad;\nvarying vec4 vRoad;`)
      .replace('#include <begin_vertex>', `#include <begin_vertex>\n${LIT_VERT_MAIN}\nvRoad = aRoad;`);
    sh.fragmentShader = sh.fragmentShader
      .replace('#include <common>', `#include <common>\n${LIT_FRAG_PARS}\n${ROAD_FRAG_PARS}`)
      .replace('#include <map_fragment>', () => ROAD_MAP)
      .replace('#include <roughnessmap_fragment>', () => 'float roughnessFactor = rdRoughF;')
      .replace('#include <metalnessmap_fragment>', () => 'float metalnessFactor = 0.0;')
      .replace('#include <normal_fragment_maps>', () => 'normal = normalize((viewMatrix * vec4(rdNw, 0.0)).xyz);')
      .replace('#include <lights_fragment_end>', () => `${BAKE_FRAG}\n${HEADLIGHTS_FRAG}\n${ROAD_END}\n#include <lights_fragment_end>`);
  };
  m.customProgramCacheKey = () => 'world_road_v1';
  return m;
}
