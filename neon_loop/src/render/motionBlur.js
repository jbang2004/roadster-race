// Camera motion blur by depth reprojection. Owner: R.
// Per pixel: world position from depth → previous clip position → screen velocity. The TAA resolve carries the car
// mask in alpha: masked pixels are copied untouched, and masked samples never contribute to a world pixel, so the car
// stays crisp while the road/lights streak past. Foreground samples in front of a background pixel are rejected (soft
// z compare) so close barriers do not smear over the distant city.
import * as THREE from 'three';
import { postMaterial, fsPass, makeRT, POST_GLSL } from './common.js';

const FRAG = /* glsl */`
${POST_GLSL}
uniform sampler2D tColor, tDepth;
uniform mat4 uInvViewProj, uPrevViewProj;
uniform vec2 uNearFar, uTexel;
uniform float uStrength, uMaxLen;
varying vec2 vUv;
#ifndef TAPS
#define TAPS 14
#endif
void main() {
  vec4 c0 = texture(tColor, vUv);
  if (c0.a > 0.5) { gl_FragColor = c0; return; }
  float z = texture(tDepth, vUv).x;
  vec4 wp = uInvViewProj * vec4(vUv * 2.0 - 1.0, z * 2.0 - 1.0, 1.0);
  wp /= wp.w;
  vec4 pc = uPrevViewProj * wp;
  vec2 prevUv = pc.xy / pc.w * 0.5 + 0.5;
  vec2 vel = (vUv - prevUv) * uStrength;
  // aspect-correct length clamp
  float len = length(vel * vec2(uTexel.y / uTexel.x, 1.0));
  if (len > uMaxLen) vel *= uMaxLen / len;
  float px = length(vel / uTexel);
  if (px < 0.75) { gl_FragColor = c0; return; }
  float zc = nl_linearDepth(z, uNearFar);
  float jit = nl_ign(gl_FragCoord.xy) - 0.5;
  vec3 acc = c0.rgb; float ws = 1.0;
  for (int i = 0; i < TAPS; i++) {
    float t = ((float(i) + 0.5 + jit) / float(TAPS) - 0.5);
    vec2 suv = vUv + vel * t;
    if (any(lessThan(suv, vec2(0.0))) || any(greaterThan(suv, vec2(1.0)))) continue;
    vec4 s = texture(tColor, suv);
    float zs = nl_linearDepth(texture(tDepth, suv).x, uNearFar);
    float w = (1.0 - smoothstep(0.35, 0.5, s.a)) * (1.0 - smoothstep(0.02, 0.12, (zc - zs) / max(zc, 0.2)));
    acc += s.rgb * w; ws += w;
  }
  gl_FragColor = vec4(acc / ws, 0.0);
}
`;

export class MotionBlurPass {
  constructor() {
    this.rt = makeRT(1, 1, { name: 'motionBlur' });
    this.mat = postMaterial({
      name: 'motionBlur', fragmentShader: FRAG, defines: { TAPS: 14 },
      uniforms: {
        tColor: { value: null }, tDepth: { value: null },
        uInvViewProj: { value: new THREE.Matrix4() }, uPrevViewProj: { value: new THREE.Matrix4() },
        uNearFar: { value: new THREE.Vector2(0.1, 6000) }, uTexel: { value: new THREE.Vector2() },
        uStrength: { value: 0.5 }, uMaxLen: { value: 0.03 },
      },
    });
  }
  get texture() { return this.rt.texture; }
  setSize(w, h) { this.rt.setSize(w, h); this.mat.uniforms.uTexel.value.set(1 / w, 1 / h); }
  setTaps(n) { n |= 0; if (this.mat.defines.TAPS !== n) { this.mat.defines.TAPS = n; this.mat.needsUpdate = true; } }
  render(renderer, colorTex, depthTex, frame, strength, maxLen) {
    const u = this.mat.uniforms;
    u.tColor.value = colorTex; u.tDepth.value = depthTex;
    u.uInvViewProj.value.copy(frame.viewProj).invert();
    u.uPrevViewProj.value.copy(frame.prevViewProj);
    u.uNearFar.value.set(frame.near, frame.far);
    u.uStrength.value = strength; u.uMaxLen.value = maxLen;
    fsPass(renderer, this.mat, this.rt);
  }
  dispose() { this.rt.dispose(); this.mat.dispose(); }
}
