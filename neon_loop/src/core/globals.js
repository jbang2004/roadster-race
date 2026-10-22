// Shared uniforms (objects are shared by reference: put G.x straight into your material's uniforms).
// Writers: I = app (time, camera), K = skyline (rain, wet, fog), C/P = headlights.
import * as THREE from 'three';

export const MAX_HEADLIGHTS = 8;
export const G = {
  uTime: { value: 0 },                          // I: seconds of game time
  uCamPos: { value: new THREE.Vector3() },      // I: camera world position (updated before render)
  uRain: { value: 0.3 },                        // K: drizzle 0..1
  uWet: { value: 1.0 },                         // K: surface wetness 0..1
  // Car headlights as data for custom (non three.js-lit) shaders, e.g. W's road. C fills these each frame.
  uHeadCount: { value: 0 },
  uHeadPos: { value: Array.from({ length: MAX_HEADLIGHTS }, () => new THREE.Vector3()) },
  uHeadDir: { value: Array.from({ length: MAX_HEADLIGHTS }, () => new THREE.Vector3(0, 0, -1)) },
  uHeadColor: { value: Array.from({ length: MAX_HEADLIGHTS }, () => new THREE.Vector3()) },   // linear rgb × candela
};

/** GLSL declarations + spot evaluation for the headlight uniforms above. */
export const HEADLIGHT_GLSL = /* glsl */`
#define MAX_HEADLIGHTS ${MAX_HEADLIGHTS}
uniform int uHeadCount;
uniform vec3 uHeadPos[MAX_HEADLIGHTS];
uniform vec3 uHeadDir[MAX_HEADLIGHTS];
uniform vec3 uHeadColor[MAX_HEADLIGHTS];
// Irradiance-like term from all headlights at world point p with normal n. Low-beam pattern: a hot spot within
// ~5° of the axis, falling to a few % at 15° and cut at 20°, so the road right in front of the car (steep angles,
// 3–10 m) is lit softly while the beam reaches 60–90 m. Range 90 m.
vec3 headlightIrradiance(vec3 p, vec3 n) {
  vec3 acc = vec3(0.0);
  for (int i = 0; i < MAX_HEADLIGHTS; i++) {
    if (i >= uHeadCount) break;
    vec3 L = uHeadPos[i] - p; float d2 = max(dot(L, L), 0.25); vec3 l = L * inversesqrt(d2);
    float c = clamp(dot(-l, uHeadDir[i]), -1.0, 1.0);
    float ang = acos(c);
    float beam = exp(-pow(ang / 0.09, 2.0)) + 0.06 * smoothstep(0.35, 0.2, ang);
    float near = mix(0.25, 1.0, smoothstep(2.0, 14.0, sqrt(d2)));
    float range = pow(clamp(1.0 - d2 / 8100.0, 0.0, 1.0), 2.0);
    acc += uHeadColor[i] * beam * near * range * max(dot(n, l), 0.0) / d2;
  }
  return acc;
}`;
