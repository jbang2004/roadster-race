// Shader-driven building façades (instanced, one material for every tower, podium, mega-block module).
// Styles (aStyle.x): 0 office curtain wall · 1 residential windows · 2 dark glass + LED strips · 3 LED media façade
//                    4 industrial / podium shops · 5 solid dark (masts, structure) · 6 mega-block module · 7 concrete mega-structure
import * as THREE from 'three';
import { makeFogUniforms } from './atmosphere.js';

const VERT = /* glsl */`
attribute vec4 aStyle;     // x style, y lit probability, z floor height (m), w module width (m)
attribute vec4 aTint;      // rgb dominant window colour, w seed
attribute vec4 aFaceUV;    // x u along the wall (unit), y scale axis (0 x / 1 z), z face id, w strip period (unit of the axis scale; 0 = whole face)
varying vec3 vNW;
varying vec3 vSize;
varying float vU;
varying float vWY;
varying float vTopDist;
varying float vFace;
varying float vFaceW;
varying vec4 vStyle;
varying vec4 vTint;
#include <fog_pars_vertex>
void main() {
  vec3 sc = vec3(length(instanceMatrix[0].xyz), length(instanceMatrix[1].xyz), length(instanceMatrix[2].xyz));
  vec4 wp = modelMatrix * (instanceMatrix * vec4(position, 1.0));
  vec4 mvPosition = viewMatrix * wp;
  gl_Position = projectionMatrix * mvPosition;
  vNW = normalize(mat3(modelMatrix) * (mat3(instanceMatrix) * (normal / sc)));
  vSize = sc;
  vU = aFaceUV.x * (aFaceUV.y < 0.5 ? sc.x : sc.z);
  vWY = wp.y;
  vTopDist = (1.0 - position.y) * sc.y;
  vFace = aFaceUV.z;
  vFaceW = (aFaceUV.y < 0.5 ? sc.x : sc.z) * (aFaceUV.w > 0.0 ? aFaceUV.w : 1.0);
  vStyle = aStyle; vTint = aTint;
  #include <fog_vertex>
}`;

const FRAG = /* glsl */`
varying vec3 vNW;
varying vec3 vSize;
varying float vU;
varying float vWY;
varying float vTopDist;
varying float vFace;
varying float vFaceW;
varying vec4 vStyle;
varying vec4 vTint;
#include <fog_pars_fragment>

float hash13(vec3 p3) { p3 = fract(p3 * .1031); p3 += dot(p3, p3.zyx + 31.32); return fract((p3.x + p3.y) * p3.z); }
float hash12(vec2 p) { vec3 p3 = fract(vec3(p.xyx) * .1031); p3 += dot(p3, p3.yzx + 33.33); return fract((p3.x + p3.y) * p3.z); }

vec3 accentColor(float k) {
  if (k < 0.28) return vec3(0.10, 0.95, 1.00);
  if (k < 0.52) return vec3(1.00, 0.12, 0.62);
  if (k < 0.70) return vec3(0.55, 0.28, 1.00);
  if (k < 0.84) return vec3(1.00, 0.52, 0.12);
  return vec3(0.85, 0.93, 1.00);
}
vec3 windowHue(float h, float h2, vec3 tint) {
  vec3 c = h < 0.46 ? vec3(1.0, 0.66, 0.34) : (h < 0.80 ? vec3(0.50, 0.72, 1.0) : vec3(1.0, 0.50, 0.20));
  return mix(c, tint, step(0.62, h2) * 0.8);
}
float vn2(vec2 p, float sd) {
  vec2 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f);
  float a = hash13(vec3(i, sd)), b = hash13(vec3(i + vec2(1.0, 0.0), sd)), c = hash13(vec3(i + vec2(0.0, 1.0), sd)), d = hash13(vec3(i + 1.0, sd));
  return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}
float box1(float x, float lo, float hi, float aa) { return smoothstep(lo - aa, lo + aa, x) * (1.0 - smoothstep(hi - aa, hi + aa, x)); }

// far-LOD lit-window estimate shared by office/residential: row ribbons × bays, blended to blobs when rows are sub-pixel
float farLit(vec2 uv, float fh, float mw, float bays, float lit, float seed, out vec3 hue) {
  float rowId = floor(uv.y / fh);
  float fy = fwidth(uv.y) / fh;
  float rowK = 1.0 - smoothstep(0.30, 0.85, fy);
  float rowH = hash13(vec3(rowId, seed, 3.0));
  float nx = vn2(vec2(uv.x / (mw * bays), rowId), seed);
  float nB = vn2(uv / vec2(mw * 14.0, fh * 5.0), seed + 4.0);
  float nA = vn2(uv / vec2(mw * 5.0, fh * 1.6), seed + 1.0);
  float ribbon = smoothstep(0.30, 0.85, nx) * (0.25 + 0.9 * rowH * rowH);
  float blob = nA * nB;
  float k = mix(blob * 1.4, ribbon * (0.5 + nB), rowK);
  hue = mix(windowHue(nB, nA, vTint.rgb), vec3(0.95, 0.78, 0.6), 0.35);
  return lit * (0.12 + 2.4 * k) * (0.75 + 0.5 * hash13(vec3(rowId, 3.0, seed)));
}

// ---- each style returns emission (em), glass reflectivity (gl) and base albedo (alb) ----
void styleOffice(vec2 uv, float fh, float mw, float lit, float seed, float detail, out vec3 em, out float gl, out vec3 alb) {
  vec2 c = uv / vec2(mw, fh); vec2 id = floor(c), f = fract(c); vec2 aa = fwidth(c) + 1e-4;
  float fl = hash13(vec3(id.y, seed, 3.0));
  float occ = 0.6 + 0.4 * sin(uv.y * 0.017 + seed * 6.28);
  float p = lit * mix(0.12, 2.6, fl * fl) * occ;
  float h0 = hash13(vec3(id, seed)), h1 = hash13(vec3(id + 31.7, seed)), h2 = hash13(vec3(id.yx + 9.1, seed + 2.0));
  float open = box1(f.x, 0.05, 0.97, aa.x) * box1(f.y, 0.14, 0.90, aa.y);
  float on = step(h0, p);
  float flick = step(0.992, h1) * step(0.5, sin(uTimeK() * 3.0 + h0 * 40.0));
  on = clamp(on - flick, 0.0, 1.0);
  float room = 0.35 + 0.65 * smoothstep(0.1, 0.9, f.y) ;
  vec3 hue = windowHue(h1, h2, vTint.rgb);
  float bright = mix(0.30, 1.5, h2 * h2);
  float blind = step(0.78, hash13(vec3(id + 4.4, seed))) * (0.35 + 0.35 * step(0.5, fract(f.y * 7.0)));
  em = hue * bright * room * on * open * (1.0 - blind);
  gl = open * (1.0 - on) * 0.9 + (1.0 - open) * 0.12;
  alb = mix(vec3(0.020, 0.024, 0.032), vec3(0.05, 0.055, 0.065), step(0.9, f.y));
  // far LOD: lit floors read as horizontal ribbons broken into bays, fading to soft patches when floors are sub-pixel
  vec3 hueM; float meanOn = farLit(uv, fh, mw, 6.0, lit, seed + 7.0, hueM);
  em = mix(hueM * meanOn * 0.29, em, detail);
}
void styleResid(vec2 uv, float fh, float mw, float lit, float seed, float detail, out vec3 em, out float gl, out vec3 alb) {
  vec2 c = uv / vec2(mw, fh); vec2 id = floor(c), f = fract(c); vec2 aa = fwidth(c) + 1e-4;
  float h0 = hash13(vec3(id, seed)), h1 = hash13(vec3(id + 17.3, seed * 1.7)), h2 = hash13(vec3(id.yx - 9.1, seed + 3.1)), h3 = hash13(vec3(id * 1.3 + 5.0, seed));
  float open = box1(f.x, 0.17, 0.83, aa.x) * box1(f.y, 0.28, 0.84, aa.y);
  float on = step(h0, lit);
  vec3 hue = windowHue(h1, h2, vTint.rgb);
  float lamp = 0.55 + 0.9 * smoothstep(0.9, 0.0, length((f - vec2(0.5, 0.82)) * vec2(1.0, 1.4)));
  float tv = step(0.93, h3) * (0.65 + 0.35 * sin(uTimeK() * (5.0 + h1 * 6.0) + h2 * 30.0));
  float blind = step(0.72, h3) * step(fract(f.y * 5.0 + h2), 0.5 + 0.4 * h1);
  float bright = mix(0.30, 1.3, h2 * h2) * (1.0 + 0.5 * tv);
  vec3 col = hue * bright * lamp * (1.0 - 0.6 * blind);
  if (tv > 0.0) col = mix(col, vec3(0.35, 0.55, 1.0) * bright, 0.7);
  em = col * on * open;
  gl = open * (1.0 - on) * 0.35 + 0.04;
  float ac = step(0.9, hash13(vec3(id + 77.0, seed))) * box1(f.x, 0.05, 0.15, aa.x) * box1(f.y, 0.1, 0.25, aa.y);
  alb = mix(vec3(0.045, 0.040, 0.042), vec3(0.075, 0.07, 0.07), ac) * (0.7 + 0.6 * hash13(vec3(floor(c * 0.25), seed)));
  alb *= 1.0 - 0.5 * box1(f.y, 0.0, 0.1, aa.y);        // balcony slab shadow
  vec3 hueM; float meanOn = farLit(uv, fh, mw, 4.0, lit, seed + 5.0, hueM);
  em = mix(hueM * meanOn * 0.25, em, detail);
}
void styleDark(vec2 uv, float fh, float mw, float lit, float seed, float detail, float W, out vec3 em, out float gl, out vec3 alb) {
  vec2 c = uv / vec2(mw, fh); vec2 id = floor(c), f = fract(c); vec2 aa = fwidth(c) + 1e-4;
  float fl = hash13(vec3(id.y, seed, 5.0));
  float h0 = hash13(vec3(id, seed)), h2 = hash13(vec3(id.yx + 9.1, seed + 2.0));
  float open = box1(f.x, 0.04, 0.96, aa.x) * box1(f.y, 0.1, 0.92, aa.y);
  float on = step(h0, lit * mix(0.0, 3.0, step(0.8, fl)));
  em = windowHue(h0, h2, vTint.rgb) * open * on * mix(0.4, 1.4, h2);
  gl = 0.95 * open + 0.1;
  alb = vec3(0.012, 0.014, 0.020);
  // corner + mid vertical LED strips
  vec3 acc = accentColor(fract(seed * 7.13));
  float um = mod(vU, W);
  float sx = min(um, W - um);
  float edge = (1.0 - smoothstep(0.55, 0.75 + fwidth(vU), sx));
  float chase = 0.55 + 0.45 * sin(uv.y * 0.09 - uTimeK() * 2.4 + seed * 20.0);
  em += acc * edge * chase * 2.4 * step(0.35, fract(seed * 3.7));
  float mid = (1.0 - smoothstep(0.18, 0.3 + fwidth(vU), abs(um - 0.5 * W))) * step(0.7, fract(seed * 5.3));
  em += acc * mid * (0.6 + 0.4 * chase) * 1.6;
  vec3 meanEm = vec3(0.9, 0.8, 0.7) * lit * 0.5 * 0.5;
  em = mix(meanEm + acc * (edge * step(0.35, fract(seed * 3.7)) * 1.2 + mid * 0.8), em, detail);
}
void styleLED(vec2 uv, float yn, float seed, float detail, out vec3 em, out float gl, out vec3 alb) {
  float px = 1.2;
  vec2 c = uv / px; vec2 id = floor(c), f = fract(c);
  float t = uK1.x;
  float mode = floor(fract(seed * 0.37) * 3.0);
  vec3 a1 = accentColor(fract(seed * 3.1)), a2 = accentColor(fract(seed * 3.1 + 0.31));
  vec3 col;
  if (mode < 0.5) {            // flowing colour waves
    float w = 0.5 + 0.5 * sin(id.x * 0.030 + id.y * 0.021 + t * 0.8 + sin(id.y * 0.05 - t * 0.5) * 2.0);
    float k = smoothstep(0.2, 0.85, 0.5 + 0.5 * sin(id.y * 0.045 - t * 1.4 + seed * 3.0));
    col = mix(a1, a2, w) * (0.12 + 1.5 * k);
  } else if (mode < 1.5) {     // equaliser bars
    float cid = floor(id.x / 4.0);
    float hgt = 0.15 + 0.85 * (0.5 + 0.5 * sin(cid * 1.7 + t * 2.1 + seed * 9.0) * sin(cid * 0.37 + t * 0.8));
    float on = step(yn, hgt) * step(0.12, fract(id.x / 4.0 + 0.5)) ;
    col = mix(a1, a2, yn) * on * 1.5 + a1 * 0.03;
  } else {                     // diagonal scrolling stripes with black gaps
    float s = fract((id.x + id.y) * 0.025 - t * 0.35 + seed);
    col = (s < 0.35 ? a1 : s < 0.5 ? vec3(1.0) * 0.7 : s < 0.85 ? a2 : vec3(0.0)) * 1.3;
  }
  float ledMask = smoothstep(0.5, 0.3, abs(f.x - 0.5)) * smoothstep(0.5, 0.3, abs(f.y - 0.5));
  ledMask = mix(0.5, ledMask, detail);
  float band = step(0.14, fract(uv.y / 36.0));
  em = col * ledMask * (0.4 + 0.6 * band) * 1.0;
  gl = 0.08; alb = vec3(0.008, 0.009, 0.013);
}
void styleIndustrial(vec2 uv, float fh, float mw, float lit, float seed, float detail, out vec3 em, out float gl, out vec3 alb) {
  float rib = 0.5 + 0.5 * sin(vU * 6.28 / 0.35);
  alb = vec3(0.030, 0.032, 0.036) * (0.7 + 0.5 * rib * detail) * (0.8 + 0.4 * hash13(vec3(floor(uv.x / 6.0), floor(uv.y / 5.0), seed)));
  vec2 c = uv / vec2(mw * 2.0, fh * 1.4); vec2 id = floor(c), f = fract(c); vec2 aa = fwidth(c) + 1e-4;
  float h0 = hash13(vec3(id, seed)), h1 = hash13(vec3(id.yx, seed + 8.0));
  float open = box1(f.x, 0.1, 0.9, aa.x) * box1(f.y, 0.35, 0.65, aa.y);
  float on = step(h0, lit * 0.8);
  em = windowHue(h0 * 3.0, h1, vTint.rgb) * open * on * 1.1;
  gl = 0.06 + open * 0.3;
  em = mix(vec3(0.8, 0.7, 0.6) * lit * 0.1, em, detail);
}
void styleMegaModule(vec2 uv, float fh, float mw, float lit, float seed, float detail, out vec3 em, out float gl, out vec3 alb) {
  vec2 c = uv / vec2(mw, fh); vec2 id = floor(c), f = fract(c); vec2 aa = fwidth(c) + 1e-4;
  float h0 = hash13(vec3(id, seed)), h1 = hash13(vec3(id + 5.5, seed)), h2 = hash13(vec3(id.yx - 3.0, seed));
  float open = box1(f.x, 0.12, 0.88, aa.x) * box1(f.y, 0.2, 0.8, aa.y);
  float on = step(h0, lit);
  vec3 hue = windowHue(h1, h2, vTint.rgb);
  em = hue * open * on * mix(0.5, 1.6, h2) * (0.6 + 0.8 * smoothstep(1.0, 0.0, f.y));
  gl = open * (1.0 - on) * 0.4;
  alb = vec3(0.05, 0.048, 0.05) * (0.6 + 0.8 * hash13(vec3(floor(c * 0.5), seed + 1.0)));
  em = mix(vec3(0.8, 0.7, 0.6) * lit * 0.38, em, detail);
}

void styleTrain(float yn, out vec3 em, out float gl, out vec3 alb) {
  float band = box1(yn, 0.36, 0.82, 0.02);
  float win = box1(fract(vU / 3.1), 0.05, 0.95, 0.03);
  em = vec3(1.0, 0.92, 0.75) * 1.5 * band * win + vec3(0.1, 0.8, 1.0) * 2.2 * box1(yn, 0.03, 0.1, 0.02);
  gl = 0.35; alb = vec3(0.05, 0.055, 0.065);
}

void main() {
  vec3 V = normalize(-vFogRay);
  vec3 N = normalize(vNW);
  float seed = vTint.w;
  float style = vStyle.x, lit = vStyle.y, fh = vStyle.z, mw = vStyle.w;
  float wy = vWY;
  bool roof = N.y > 0.5;
  vec2 uv = vec2(vU + vFace * 13.37 * 0.0, wy);
  float W = vFaceW;
  float fu = fwidth(vU) / mw, fy = fwidth(wy) / fh;
  float detail = 1.0 - smoothstep(0.20, 0.68, max(fu, fy));
  float faceSeed = seed + vFace * 0.173;
  vec3 em = vec3(0.0), alb = vec3(0.02); float gl = 0.3;

  if (roof) {
    // roof: dark with scattered plant / warning lights
    vec2 q = vec2(vU * 0.0, 0.0);
    alb = vec3(0.012, 0.013, 0.017); gl = 0.05;
    em = vec3(0.0);
  } else if (style < 0.5) styleOffice(uv, fh, mw, lit, faceSeed, detail, em, gl, alb);
  else if (style < 1.5) styleResid(uv, fh, mw, lit, faceSeed, detail, em, gl, alb);
  else if (style < 2.5) styleDark(uv, fh, mw, lit, faceSeed, detail, W, em, gl, alb);
  else if (style < 3.5) styleLED(uv, clamp((vSize.y - vTopDist) / vSize.y, 0.0, 1.0), faceSeed, detail, em, gl, alb);
  else if (style < 4.5) styleIndustrial(uv, fh, mw, lit, faceSeed, detail, em, gl, alb);
  else if (style < 5.5) { alb = vec3(0.016, 0.017, 0.022); gl = 0.15; }
  else if (style < 6.5) styleMegaModule(uv, fh, mw, lit, faceSeed, detail, em, gl, alb);
  else if (style > 7.5) styleTrain(clamp((vSize.y - vTopDist) / vSize.y, 0.0, 1.0), em, gl, alb);
  else { alb = vec3(0.045, 0.043, 0.046) * (0.6 + 0.6 * hash13(vec3(floor(vec2(vU, wy) * 0.3), seed))); gl = 0.05; em = vec3(0.0); }

  // --- street level: shop glow + neon signs on the lowest floors (style < 5 only)
  if (!roof && style < 4.5 && wy < 26.0) {
    float sgn = floor(vU / 3.4);
    float hs = hash13(vec3(sgn, floor(wy / 3.0), seed + 4.0));
    float sh = smoothstep(26.0, 3.0, wy);
    float shopRow = step(wy, 6.0);
    vec3 acc = accentColor(hash13(vec3(sgn, seed, 2.0)));
    float blade = step(0.82, hs) * box1(fract(vU / 3.4), 0.25, 0.75, fwidth(vU / 3.4) + 0.01) * box1(wy, 4.0, 4.0 + 10.0 * hash13(vec3(sgn, seed, 9.0)), 0.3 + fwidth(wy));
    float shop = shopRow * step(0.35, hash13(vec3(sgn, seed, 6.0))) * box1(wy, 0.6, 4.2, fwidth(wy) + 0.05);
    em += acc * blade * 3.2 * detail + vec3(1.0, 0.72, 0.42) * shop * 1.1 * mix(0.5, 1.0, detail);
    em += vec3(1.0, 0.62, 0.3) * sh * 0.04;
  }
  // --- crown line: neon edge on top of each tier
  if (!roof && style < 5.5 && style != 3.0) {
    float cr = step(0.78, fract(seed * 11.3));
    vec3 acc = accentColor(fract(seed * 5.7 + 0.15));
    float line = (1.0 - smoothstep(0.18, 0.32 + fwidth(vTopDist), abs(vTopDist - 0.6)));
    em += acc * line * cr * 3.0;
  }

  // --- lighting: sky/glow reflection (Fresnel), city uplight, moon rim
  float ndv = clamp(dot(N, V), 0.0, 1.0);
  float fres = 0.04 + 0.96 * pow(1.0 - ndv, 5.0);
  vec3 R = reflect(-V, N);
  float upR = smoothstep(-0.12, 0.3, R.y);
  vec3 rr = normalize(vec3(R.x, max(R.y, 0.0) * 0.8 + 0.03, R.z));
  vec3 skyR = kFogColor(rr) * (1.7 + 0.6 * sin(vU * 0.19 + seed * 9.0) * sin(wy * 0.037 + seed * 5.0));
  vec3 gndR = kHorizon(normalize(R.xz + 1e-4)) * 0.22 + vec3(0.004, 0.003, 0.003);   // the lit city below
  vec3 sky = mix(gndR, skyR, upR);
  vec3 refl = sky * (gl * (0.10 + 0.55 * fres) + 0.015);
  float up = clamp(1.0 - wy / 140.0, 0.0, 1.0);
  vec3 amb = kHorizon(N.xz * (1.0 / max(length(N.xz), 1e-3))) * (0.10 + 0.5 * up * up) * (0.35 + 0.65 * (1.0 - abs(N.y)));
  vec3 moon = vec3(0.45, 0.62, 1.0) * 0.045 * max(dot(N, normalize(uK7.xyz)), 0.0);
  vec3 col = alb * (amb * 3.2 + moon * 8.0) + refl + em;
  gl_FragColor = vec4(col, 1.0);
  #include <fog_fragment>
  #include <tonemapping_fragment>
  #include <colorspace_fragment>
}`;

export function createFacadeMaterial() {
  const m = new THREE.ShaderMaterial({
    vertexShader: VERT,
    fragmentShader: FRAG.replace(/uTimeK\(\)/g, 'uK1.x'),
    uniforms: makeFogUniforms(),
    fog: true,
  });
  m.name = 'K-facade';
  return m;
}

// ---------- geometry (with aFaceUV) ----------
export function makeBoxGeometry() {
  const P = [], Nn = [], UV = [], I = [];
  const face = (n, verts, u, axis, id) => {
    const base = P.length / 3;
    for (let i = 0; i < 4; i++) { P.push(...verts[i]); Nn.push(...n); UV.push(u[i], axis, id, 0); }
    I.push(base, base + 1, base + 2, base, base + 2, base + 3);
  };
  face([0, 0, 1], [[-.5, 0, .5], [.5, 0, .5], [.5, 1, .5], [-.5, 1, .5]], [0, 1, 1, 0], 0, 0);
  face([0, 0, -1], [[.5, 0, -.5], [-.5, 0, -.5], [-.5, 1, -.5], [.5, 1, -.5]], [0, 1, 1, 0], 0, 1);
  face([1, 0, 0], [[.5, 0, .5], [.5, 0, -.5], [.5, 1, -.5], [.5, 1, .5]], [0, 1, 1, 0], 1, 2);
  face([-1, 0, 0], [[-.5, 0, -.5], [-.5, 0, .5], [-.5, 1, .5], [-.5, 1, -.5]], [0, 1, 1, 0], 1, 3);
  face([0, 1, 0], [[-.5, 1, .5], [.5, 1, .5], [.5, 1, -.5], [-.5, 1, -.5]], [0, 1, 1, 0], 0, 4);
  return finish(P, Nn, UV, I);
}
/** Box whose roof slopes down towards +z by `slope` (fraction of the height): slanted-crown towers. */
export function makeWedgeGeometry(slope = 0.2) {
  const P = [], Nn = [], UV = [], I = [];
  const face = (n, verts, u, axis, id) => {
    const base = P.length / 3;
    for (let i = 0; i < 4; i++) { P.push(...verts[i]); Nn.push(...n); UV.push(u[i], axis, id, 0); }
    I.push(base, base + 1, base + 2, base, base + 2, base + 3);
  };
  const t = 1 - slope;
  face([0, 0, 1], [[-.5, 0, .5], [.5, 0, .5], [.5, t, .5], [-.5, t, .5]], [0, 1, 1, 0], 0, 0);
  face([0, 0, -1], [[.5, 0, -.5], [-.5, 0, -.5], [-.5, 1, -.5], [.5, 1, -.5]], [0, 1, 1, 0], 0, 1);
  face([1, 0, 0], [[.5, 0, .5], [.5, 0, -.5], [.5, 1, -.5], [.5, t, .5]], [0, 1, 1, 0], 1, 2);
  face([-1, 0, 0], [[-.5, 0, -.5], [-.5, 0, .5], [-.5, t, .5], [-.5, 1, -.5]], [0, 1, 1, 0], 1, 3);
  const ny = 1, nz = slope, l = Math.hypot(ny, nz);
  face([0, ny / l, nz / l], [[-.5, t, .5], [.5, t, .5], [.5, 1, -.5], [-.5, 1, -.5]], [0, 1, 1, 0], 0, 4);
  return finish(P, Nn, UV, I);
}
/** smooth = true: radial smooth normals (cylinder); false: faceted prism (octagon). Diameter 1, height 1. */
export function makePrismGeometry(seg, smooth) {
  const P = [], Nn = [], UV = [], I = [];
  const side = 2 * Math.sin(Math.PI / seg);   // side length for diameter 1 (radius .5)
  for (let i = 0; i < seg; i++) {
    const a0 = (i / seg) * Math.PI * 2, a1 = ((i + 1) / seg) * Math.PI * 2;
    const x0 = Math.cos(a0) * 0.5, z0 = Math.sin(a0) * 0.5, x1 = Math.cos(a1) * 0.5, z1 = Math.sin(a1) * 0.5;
    const am = (a0 + a1) / 2, fnx = Math.cos(am), fnz = Math.sin(am);
    const base = P.length / 3;
    const n0 = smooth ? [Math.cos(a0), 0, Math.sin(a0)] : [fnx, 0, fnz];
    const n1 = smooth ? [Math.cos(a1), 0, Math.sin(a1)] : [fnx, 0, fnz];
    const u0 = smooth ? a0 * 0.5 : i * side * 0.5, u1 = smooth ? a1 * 0.5 : (i + 1) * side * 0.5;
    P.push(x0, 0, z0, x1, 0, z1, x1, 1, z1, x0, 1, z0);
    Nn.push(...n0, ...n1, ...n1, ...n0);
    const per = smooth ? 0.39 : side * 0.5;
    UV.push(u0, 0, i % 4, per, u1, 0, i % 4, per, u1, 0, i % 4, per, u0, 0, i % 4, per);
    I.push(base, base + 2, base + 1, base, base + 3, base + 2);
  }
  // top cap
  const c = P.length / 3;
  P.push(0, 1, 0); Nn.push(0, 1, 0); UV.push(0, 0, 4, 0);
  for (let i = 0; i <= seg; i++) { const a = (i / seg) * Math.PI * 2; P.push(Math.cos(a) * 0.5, 1, Math.sin(a) * 0.5); Nn.push(0, 1, 0); UV.push(0, 0, 4, 0); }
  for (let i = 0; i < seg; i++) I.push(c, c + 2 + i, c + 1 + i);
  return finish(P, Nn, UV, I);
}
/** UV sphere, diameter 1, sitting on y in [0,1]; u = arc along the equator (unit of sc.x), face id 0. */
export function makeSphereGeometry(segU = 28, segV = 16) {
  const P = [], Nn = [], UV = [], I = [];
  for (let j = 0; j <= segV; j++) {
    const v = j / segV, phi = v * Math.PI;
    for (let i = 0; i <= segU; i++) {
      const u = i / segU, th = u * Math.PI * 2;
      const x = Math.sin(phi) * Math.cos(th), y = Math.cos(phi), z = Math.sin(phi) * Math.sin(th);
      P.push(x * 0.5, 0.5 + y * 0.5, z * 0.5); Nn.push(x, y, z); UV.push(th * 0.5 * Math.sin(phi), 0, 0, 0.39);
    }
  }
  const row = segU + 1;
  for (let j = 0; j < segV; j++) for (let i = 0; i < segU; i++) {
    const a = j * row + i, b = a + row;
    I.push(a, a + 1, b, a + 1, b + 1, b);
  }
  return finish(P, Nn, UV, I);
}
function finish(P, Nn, UV, I) {
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(P, 3));
  g.setAttribute('normal', new THREE.Float32BufferAttribute(Nn, 3));
  g.setAttribute('aFaceUV', new THREE.Float32BufferAttribute(UV, 4));
  g.setIndex(I);
  return g;
}
