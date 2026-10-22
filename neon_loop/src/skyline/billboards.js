// Giant LED screens mounted on tower faces (instanced quads sampling the ad atlas, animated) + their light halos.
import * as THREE from 'three';
import { makeFogUniforms, kUniforms, KGLSL } from './atmosphere.js';
import { ATLAS_GLSL } from './ads.js';

const SCREEN_VERT = /* glsl */`
attribute vec4 aPos;     // centre xyz, panel index
attribute vec4 aOri;     // normal.x, normal.z, width, height
attribute vec4 aMisc;    // brightness, phase, mode, halo
varying vec2 vUv; varying vec4 vMisc; varying vec2 vWH;
#include <fog_pars_vertex>
void main() {
  vec3 n = vec3(aOri.x, 0.0, aOri.y);
  vec3 right = vec3(n.z, 0.0, -n.x);
  vec3 wp = aPos.xyz + right * position.x * aOri.z + vec3(0.0, 1.0, 0.0) * position.y * aOri.w + n * 0.45;
  vec4 mvPosition = viewMatrix * vec4(wp, 1.0);
  gl_Position = projectionMatrix * mvPosition;
  vUv = position.xy + 0.5;
  vMisc = vec4(aMisc.x, aMisc.y, aMisc.z, aPos.w);
  vWH = aOri.zw;
  #include <fog_vertex>
}`;
const SCREEN_FRAG = /* glsl */`
uniform sampler2D tAds;
varying vec2 vUv; varying vec4 vMisc; varying vec2 vWH;
#include <fog_pars_fragment>
${ATLAS_GLSL}
float hash12(vec2 p) { vec3 p3 = fract(vec3(p.xyx) * .1031); p3 += dot(p3, p3.yzx + 33.33); return fract((p3.x + p3.y) * p3.z); }
void main() {
  float t = uK1.x + vMisc.y * 50.0;
  float cycle = 9.0;
  float k = floor(t / cycle);
  float f = fract(t / cycle);
  float p0 = mod(vMisc.w + k * 5.0, 16.0), p1 = mod(vMisc.w + (k + 1.0) * 5.0, 16.0);
  vec2 uv = vUv;
  // landscape panels use the 2:1 atlas cell directly; tall panels show the cell's centre column scaled
  float asp = vWH.x / vWH.y;
  if (asp < 1.9) uv.x = 0.5 + (vUv.x - 0.5) * (asp / 2.0);
  float glitch = step(0.992, hash12(vec2(floor(t * 11.0), vMisc.w))) * (hash12(vec2(floor(uv.y * 40.0), floor(t * 11.0))) - 0.5) * 0.12;
  vec3 a = adPanel(tAds, p0, uv + vec2(glitch, 0.0));
  vec3 b = adPanel(tAds, p1, uv + vec2(glitch, 0.0));
  vec3 col = mix(a, b, smoothstep(0.88, 1.0, f));
  // LED pixel grid + scanline
  vec2 px = vUv * vWH / 0.9;
  vec2 g = abs(fract(px) - 0.5);
  float mask = mix(1.0, smoothstep(0.52, 0.30, max(g.x, g.y)), clamp(1.0 - fwidth(px.x) * 1.5, 0.0, 1.0));
  float scan = 0.9 + 0.1 * sin(vUv.y * vWH.y * 1.7 - t * 6.0);
  float flick = 0.94 + 0.06 * sin(t * 37.0 + vMisc.y * 9.0);
  col = col * col * 2.2;                       // sRGB-ish → linear-ish, punchy
  gl_FragColor = vec4(col * vMisc.x * mask * scan * flick, 1.0);
  #include <fog_fragment>
  #include <tonemapping_fragment>
  #include <colorspace_fragment>
}`;
const HALO_VERT = /* glsl */`
attribute vec4 aPos; attribute vec4 aOri; attribute vec4 aMisc;
varying vec2 vQ; varying vec3 vRay; varying vec3 vTint; varying float vI;
${KGLSL}
void main() {
  vec3 n = vec3(aOri.x, 0.0, aOri.y);
  vec3 right = vec3(n.z, 0.0, -n.x);
  float sx = aOri.z * 1.9 + 14.0, sy = aOri.w * 1.9 + 14.0;
  vec3 wp = aPos.xyz + right * position.x * sx + vec3(0.0, 1.0, 0.0) * position.y * sy + n * 6.0;
  gl_Position = projectionMatrix * viewMatrix * vec4(wp, 1.0);
  vQ = position.xy * 2.0; vRay = wp - cameraPosition;
  float h = fract(aPos.w * 0.137 + 0.1);
  vTint = h < 0.25 ? vec3(1.0, 0.25, 0.7) : h < 0.5 ? vec3(0.2, 0.8, 1.0) : h < 0.75 ? vec3(0.6, 0.4, 1.0) : vec3(1.0, 0.6, 0.25);
  vI = aMisc.w;
}`;
const HALO_FRAG = /* glsl */`
varying vec2 vQ; varying vec3 vRay; varying vec3 vTint; varying float vI;
${KGLSL}
void main() {
  vec2 a = abs(vQ);
  float g = exp(-pow(a.x, 3.0) * 2.5) * exp(-pow(a.y, 3.0) * 2.5);
  float fall = smoothstep(1.0, 0.45, max(a.x, a.y));
  gl_FragColor = vec4(vTint * g * fall * vI * 0.10 * kFogT(vRay), 1.0);
  #include <tonemapping_fragment>
  #include <colorspace_fragment>
}`;

/** screens: array of {x,y,z, nx,nz, w,h, panel, bright, phase} */
export function createBillboards(screens, adTex) {
  const n = screens.length;
  const pos = new Float32Array(n * 4), ori = new Float32Array(n * 4), misc = new Float32Array(n * 4);
  screens.forEach((s, i) => {
    pos.set([s.x, s.y, s.z, s.panel], i * 4); ori.set([s.nx, s.nz, s.w, s.h], i * 4);
    misc.set([s.bright ?? 2.0, s.phase ?? i * 0.37, 0, Math.min(1, (s.w * s.h) / 4000) * 1.0 + 0.25], i * 4);
  });
  const quad = [-0.5, 0, 0, 0.5, 0, 0, 0.5, 1, 0, -0.5, 1, 0];
  const mk = () => {
    const g = new THREE.InstancedBufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(quad, 3)); g.setIndex([0, 1, 2, 0, 2, 3]);
    g.setAttribute('aPos', new THREE.InstancedBufferAttribute(pos, 4)); g.setAttribute('aOri', new THREE.InstancedBufferAttribute(ori, 4)); g.setAttribute('aMisc', new THREE.InstancedBufferAttribute(misc, 4));
    g.instanceCount = n; return g;
  };
  const screenMat = new THREE.ShaderMaterial({ vertexShader: SCREEN_VERT, fragmentShader: SCREEN_FRAG, fog: true, uniforms: makeFogUniforms({ tAds: { value: adTex } }), side: THREE.DoubleSide });
  const screensMesh = new THREE.Mesh(mk(), screenMat); screensMesh.frustumCulled = false; screensMesh.name = 'K-screens';
  const halos = new THREE.Mesh(mk(), new THREE.ShaderMaterial({ vertexShader: HALO_VERT, fragmentShader: HALO_FRAG, uniforms: kUniforms(), transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, fog: false, side: THREE.DoubleSide }));
  halos.frustumCulled = false; halos.renderOrder = 8; halos.name = 'K-screen-halos';
  const group = new THREE.Group(); group.name = 'K-billboards'; group.add(screensMesh, halos);
  return { group, count: n };
}
