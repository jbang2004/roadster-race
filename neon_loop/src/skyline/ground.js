// Far ground (y = -0.05) from ~120 m out to the horizon, plus the canal continuing out of the dressed area.
// One big plane; a distance-field texture decides where it is drawn (discard within 120 m of any road, and over the
// canal strip), so it never needs geometry cut-outs and always leaves the near band to W.
import * as THREE from 'three';
import { makeFogUniforms } from './atmosphere.js';

const GROUND_VERT = /* glsl */`
varying vec3 vW;
#include <fog_pars_vertex>
void main() {
  vec4 wp = modelMatrix * vec4(position, 1.0);
  vW = wp.xyz;
  vec4 mvPosition = viewMatrix * wp;
  gl_Position = projectionMatrix * mvPosition;
  #include <fog_vertex>
}`;

const GROUND_FRAG = /* glsl */`
uniform sampler2D tDist;
uniform vec4 uGrid;        // x0, z0, sizeX, sizeZ of the distance texture (world)
uniform vec4 uCanal;       // x0, x1, zmin, zmax (strip that stays free everywhere)
uniform float uCut;        // draw only beyond this distance from the road edge
varying vec3 vW;
#include <fog_pars_fragment>
float hash12(vec2 p) { vec3 p3 = fract(vec3(p.xyx) * .1031); p3 += dot(p3, p3.yzx + 33.33); return fract((p3.x + p3.y) * p3.z); }
float vnoise(vec2 p) {
  vec2 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f);
  return mix(mix(hash12(i), hash12(i + vec2(1, 0)), f.x), mix(hash12(i + vec2(0, 1)), hash12(i + vec2(1, 1)), f.x), f.y);
}
void main() {
  vec2 uv = (vW.xz - uGrid.xy) / uGrid.zw;
  float cd = texture2D(tDist, uv).r * 400.0;
  if (uv.x > 0.0 && uv.y > 0.0 && uv.x < 1.0 && uv.y < 1.0 && cd < uCut) discard;
  if (vW.x > uCanal.x - 0.5 && vW.x < uCanal.y + 0.5) discard;
  vec3 V = normalize(-vFogRay);
  vec2 p = vW.xz;
  // street lattice whose pitch doubles with distance (matches the lot quad-tree)
  float far = clamp(length(vFogRay.xz), 0.0, 6000.0);
  float lvl = cd >= 3600.0 ? 3.0 : cd >= 1750.0 ? 2.0 : cd >= 700.0 ? 1.0 : 0.0;
  float pitch = 72.0 * exp2(lvl);
  vec2 q = p / pitch + 0.5;
  vec2 dstr = abs(fract(q) - 0.5) * pitch;                 // metres to the street centre lines
  float sw = 5.0 + 3.0 * lvl;
  float aa = max(fwidth(p.x), fwidth(p.y)) + 0.01;
  float street = 1.0 - smoothstep(sw - aa, sw + aa, min(dstr.x, dstr.y));
  float fade = smoothstep(0.35, 0.10, aa / sw);               // sub-pixel streets average out
  // asphalt: dark, wet, patchy
  float n = vnoise(p * 0.11) * 0.6 + vnoise(p * 0.7) * 0.4;
  vec3 alb = mix(vec3(0.014, 0.015, 0.018), vec3(0.030, 0.030, 0.034), street * 0.8) * (0.7 + 0.6 * n);
  // sodium glow of the street lights along the lattice, fading with distance
  float lampPeriod = 30.0 * exp2(lvl);
  float coord = dstr.x < dstr.y ? p.y : p.x;
  float along = abs(fract(coord / lampPeriod) - 0.5) * lampPeriod;
  float pool = exp(-along * along / 90.0) * street * fade * smoothstep(900.0, 150.0, far);
  vec3 lamp = vec3(1.0, 0.52, 0.20) * pool * 0.32;
  // wet reflection of the haze / sky glow at grazing angles
  float ndv = clamp(V.y, 0.0, 1.0);
  float fres = 0.02 + 0.98 * pow(1.0 - ndv, 5.0);
  vec3 R = vec3(-V.x, V.y, -V.z);
  vec3 refl = kFogColor(normalize(vec3(R.x, 0.02 + R.y * 0.3, R.z))) * 1.6;
  float wet = 0.35 + 0.65 * smoothstep(0.35, 0.8, n);
  vec3 col = alb * 0.8 + lamp + refl * fres * wet * (0.4 + 0.6 * street * fade);
  gl_FragColor = vec4(col, 1.0);
  #include <fog_fragment>
  #include <tonemapping_fragment>
  #include <colorspace_fragment>
}`;

const WATER_FRAG = /* glsl */`
varying vec3 vW;
#include <fog_pars_fragment>
float hash12(vec2 p) { vec3 p3 = fract(vec3(p.xyx) * .1031); p3 += dot(p3, p3.yzx + 33.33); return fract((p3.x + p3.y) * p3.z); }
void main() {
  vec3 V = normalize(-vFogRay);
  float t = uK1.x;
  vec2 p = vW.xz;
  float rip = sin(p.x * 0.31 + t * 0.9) * sin(p.y * 0.17 - t * 0.6) + 0.5 * sin(p.y * 0.53 + p.x * 0.2 + t * 1.3);
  vec3 N = normalize(vec3(rip * 0.03, 1.0, sin(p.y * 0.4 + t) * 0.02));
  float ndv = clamp(dot(N, V), 0.0, 1.0);
  float fres = 0.02 + 0.98 * pow(1.0 - ndv, 5.0);
  vec3 R = reflect(-V, N);
  vec3 refl = kFogColor(normalize(vec3(R.x, abs(R.y) + 0.02, R.z))) * 1.8;
  // reflected city lights: warm/magenta streaks along the canal
  float st = hash12(floor(vec2(p.y / 24.0, p.x / 5.0))) ;
  vec3 lights = (st > 0.86 ? vec3(1.0, 0.45, 0.2) : st > 0.80 ? vec3(0.9, 0.2, 0.6) : vec3(0.0)) * 0.18 * smoothstep(0.7, 0.2, ndv);
  vec3 col = vec3(0.004, 0.010, 0.014) + refl * fres + lights;
  gl_FragColor = vec4(col, 1.0);
  #include <fog_fragment>
  #include <tonemapping_fragment>
  #include <colorspace_fragment>
}`;

export function buildGround(app, track, field) {
  const cn = track.layout.canal, B = track.layout.bounds;
  // distance texture (R8, 0..400 m)
  const { d, w, h, gx0, gz0, cell, bias } = field;
  const data = new Uint8Array(w * h);
  for (let i = 0; i < w * h; i++) data[i] = Math.max(0, Math.min(255, ((d[i] * cell - bias) / 400) * 255));
  const tDist = new THREE.DataTexture(data, w, h, THREE.RedFormat, THREE.UnsignedByteType);
  tDist.magFilter = THREE.LinearFilter; tDist.minFilter = THREE.LinearFilter; tDist.wrapS = tDist.wrapT = THREE.ClampToEdgeWrapping;
  tDist.generateMipmaps = false; tDist.needsUpdate = true;

  const mat = new THREE.ShaderMaterial({
    vertexShader: GROUND_VERT, fragmentShader: GROUND_FRAG, fog: true,
    uniforms: makeFogUniforms({
      tDist: { value: tDist }, uGrid: { value: new THREE.Vector4(gx0, gz0, w * cell, h * cell) },
      uCanal: { value: new THREE.Vector4(cn.x0, cn.x1, B.z0, B.z1) }, uCut: { value: 120 },
    }),
    polygonOffset: true, polygonOffsetFactor: 3, polygonOffsetUnits: 6,
  });
  const R = 7000;
  const ground = new THREE.Mesh(new THREE.PlaneGeometry(2 * R, 2 * R, 1, 1), mat);
  ground.rotation.x = -Math.PI / 2; ground.position.set(0, -0.05, 0); ground.frustumCulled = false; ground.name = 'K-ground';

  // canal continuing beyond the dressed bounds, to the horizon both ways
  const waterMat = new THREE.ShaderMaterial({ vertexShader: GROUND_VERT, fragmentShader: WATER_FRAG, fog: true, uniforms: makeFogUniforms(), polygonOffset: true, polygonOffsetFactor: 2, polygonOffsetUnits: 4 });
  const group = new THREE.Group(); group.name = 'K-canal-extension';
  const cw = cn.x1 - cn.x0;
  for (const [z0, z1] of [[B.z0 - 6500, B.z0], [B.z1, B.z1 + 6500]]) {
    const m = new THREE.Mesh(new THREE.PlaneGeometry(cw, z1 - z0), waterMat);
    m.rotation.x = -Math.PI / 2; m.position.set((cn.x0 + cn.x1) / 2, cn.water, (z0 + z1) / 2); m.frustumCulled = false;
    group.add(m);
  }
  // quay walls (dark concrete) on both banks
  const wallMat = new THREE.ShaderMaterial({
    vertexShader: GROUND_VERT, fog: true, uniforms: makeFogUniforms(), side: THREE.DoubleSide,
    fragmentShader: /* glsl */`varying vec3 vW;
#include <fog_pars_fragment>
void main() { float s = fract(vW.y * 0.5 + vW.z * 0.04); gl_FragColor = vec4(vec3(0.012, 0.013, 0.016) * (0.7 + 0.5 * s), 1.0);
  #include <fog_fragment>
  #include <tonemapping_fragment>
  #include <colorspace_fragment>
}` });
  for (const [z0, z1] of [[B.z0 - 6500, B.z0], [B.z1, B.z1 + 6500]]) for (const x of [cn.x0, cn.x1]) {
    const m = new THREE.Mesh(new THREE.PlaneGeometry(z1 - z0, -0.05 - cn.water), wallMat);
    m.rotation.y = Math.PI / 2; m.position.set(x, (cn.water - 0.05) / 2, (z0 + z1) / 2); m.frustumCulled = false;
    group.add(m);
  }
  return { objects: [ground, group], materials: [mat, waterMat, wallMat] };
}
