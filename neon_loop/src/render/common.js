// Shared plumbing for the render area's passes. Owner: R.
//   fsPass(renderer, mat, rt, level?)  — one fullscreen triangle with `mat` into `rt` (null = canvas)
//   postMaterial({...})                — ShaderMaterial preset for post passes (no depth, no blending, GLSL ES 3.00)
//   makeRT(w, h, opts)                 — HalfFloat RGBA linear render target
//   POST_GLSL                          — helpers shared by the pass shaders
//   halton(i, base)                    — TAA jitter sequence
import * as THREE from 'three';

const triGeo = new THREE.BufferGeometry();
triGeo.setAttribute('position', new THREE.Float32BufferAttribute([-1, -1, 0, 3, -1, 0, -1, 3, 0], 3));
triGeo.setAttribute('uv', new THREE.Float32BufferAttribute([0, 0, 2, 0, 0, 2], 2));
const fsCam = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
const fsScene = new THREE.Scene();
const fsMesh = new THREE.Mesh(triGeo);
fsMesh.frustumCulled = false;
fsMesh.matrixAutoUpdate = false;
fsScene.add(fsMesh);
fsScene.matrixWorldAutoUpdate = false;

export const FS_VERT = /* glsl */`
varying vec2 vUv;
void main() { vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }
`;

/** Render `material` over the full target (null = canvas). Leaves autoClear/viewport state as three keeps them. */
export function fsPass(renderer, material, rt, level = 0) {
  fsMesh.material = material;
  renderer.setRenderTarget(rt, 0, level);
  const ac = renderer.autoClear;
  renderer.autoClear = false;
  renderer.render(fsScene, fsCam);
  renderer.autoClear = ac;
}

export function postMaterial({ uniforms = {}, fragmentShader, defines = {}, vertexShader = FS_VERT, name = 'post', ...rest }) {
  return new THREE.ShaderMaterial({
    name, uniforms, defines, vertexShader, fragmentShader,
    depthTest: false, depthWrite: false, blending: THREE.NoBlending, toneMapped: false, ...rest,
  });
}

export function makeRT(w, h, { type = THREE.HalfFloatType, format = THREE.RGBAFormat, filter = THREE.LinearFilter, name = '', ...rest } = {}) {
  const rt = new THREE.WebGLRenderTarget(Math.max(1, w), Math.max(1, h), {
    type, format, minFilter: filter, magFilter: filter, depthBuffer: false, stencilBuffer: false, generateMipmaps: false, ...rest,
  });
  rt.texture.name = name;
  return rt;
}

export function halton(i, base) {
  let f = 1, r = 0;
  while (i > 0) { f /= base; r += f * (i % base); i = Math.floor(i / base); }
  return r;
}

export const POST_GLSL = /* glsl */`
#ifndef NL_COMMON
#define NL_COMMON
const vec3 NL_LUMA709 = vec3(0.2126, 0.7152, 0.0722);
float nl_ign(vec2 p) { return fract(52.9829189 * fract(dot(p, vec2(0.06711056, 0.00583715)))); }
float nl_hash12(vec2 p) { vec3 p3 = fract(vec3(p.xyx) * 0.1031); p3 += dot(p3, p3.yzx + 33.33); return fract((p3.x + p3.y) * p3.z); }
float nl_linearDepth(float z, vec2 nf) { float zn = z * 2.0 - 1.0; return 2.0 * nf.x * nf.y / (nf.y + nf.x - zn * (nf.y - nf.x)); }
vec3 nl_toSRGB(vec3 c) { c = clamp(c, 0.0, 1.0); return mix(c * 12.92, 1.055 * pow(c, vec3(1.0 / 2.4)) - 0.055, step(0.0031308, c)); }
vec3 nl_toYCoCg(vec3 c) { return vec3(dot(c, vec3(0.25, 0.5, 0.25)), dot(c, vec3(0.5, 0.0, -0.5)), dot(c, vec3(-0.25, 0.5, -0.25))); }
vec3 nl_fromYCoCg(vec3 c) { return vec3(c.x + c.y - c.z, c.x + c.z, c.x - c.y - c.z); }
#endif
`;
