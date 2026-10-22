// Wet-road planar reflection contract. OWNER: R (rendering). Exported names and signatures are stable (W's road /
// puddle / water shaders use them); R improves the internals.
//
// R renders the scene mirrored about the road plane under the focus into RF.tReflect (linear HDR, half resolution,
// mip chain = roughness blur) and sets RF.uReflectMatrix so that  uReflectMatrix * vec4(worldPos, 1)  gives projective
// texture coordinates (xyw, like THREE.Reflector's textureMatrix). Row 2 (the unused z output) carries the mirror plane:
//   c.z = signed height of worldPos above the plane (m);  (m[0][2], m[1][2], m[2][2]) = plane normal.
// RF.uReflectOn = 1 when valid.  Uniform names/types are fixed: put RF.* straight into your material's uniforms.
import * as THREE from 'three';

export const RF = {
  tReflect: { value: null },
  uReflectMatrix: { value: new THREE.Matrix4() },
  uReflectOn: { value: 0 },
  uReflectLod: { value: 5 },          // highest usable blur level (mip index)
};

/** GLSL: vec3 roadReflection(vec3 worldPos, vec3 n, float roughness, float streak)
 *  worldPos = the surface point (on the road), n = perturbed surface normal (world), roughness 0..1,
 *  streak 0..1 = vertical smear of light reflections (wet asphalt ≈ 0.6–1, puddles ≈ 0.1).
 *  Returns linear HDR radiance to be weighted by Fresnel and wetness by the caller. Returns 0 when RF is off, when the
 *  point is far from the mirror plane (other road level) and near the edges of the reflection image. */
export const REFLECT_GLSL = /* glsl */`
uniform sampler2D tReflect;
uniform mat4 uReflectMatrix;
uniform float uReflectOn;
uniform float uReflectLod;
vec3 roadReflection(vec3 worldPos, vec3 n, float roughness, float streak) {
  if (uReflectOn < 0.5) return vec3(0.0);
  vec3 N0 = vec3(uReflectMatrix[0][2], uReflectMatrix[1][2], uReflectMatrix[2][2]);
  float h = dot(N0, worldPos) + uReflectMatrix[3][2];
  float fade = 1.0 - smoothstep(3.0, 8.0, abs(h));
  if (fade <= 0.0) return vec3(0.0);
  vec3 pp = worldPos - N0 * clamp(h, -2.5, 2.5);                  // foot of the point on the mirror plane
  vec4 c0 = uReflectMatrix * vec4(pp, 1.0);
  if (c0.w <= 0.05) return vec3(0.0);
  vec3 dn = n - N0 * dot(n, N0);                                    // tangential normal perturbation (ripples, normal map)
  float dnl = length(dn);
  vec4 c = uReflectMatrix * vec4(pp + dn * (0.035 * c0.w), 1.0);    // constant angular distortion at any distance
  vec2 uv = c.xy / max(c.w, 0.05);
  float rough = clamp(roughness, 0.0, 1.0);
  vec2 ts = vec2(textureSize(tReflect, 0));
  // vertical streak: lamps and neon smear along the view direction on wet asphalt
  float len = streak * (0.010 + 0.16 * rough * rough + 0.05 * rough);        // uv units (image height)
  float lodIso = clamp(rough * uReflectLod * 1.25 + dnl * 4.0, 0.0, uReflectLod);
  float step_ = len / 5.0;
  float lodStreak = log2(max(step_ * ts.y, 1.0));
  float lod = clamp(max(lodIso, lodStreak * 0.85), 0.0, uReflectLod);
  vec3 acc = vec3(0.0); float ws = 0.0;
  for (int k = -5; k <= 5; k++) {
    float fk = float(k);
    float w = exp(-fk * fk * 0.07);
    vec2 o = vec2(0.0, fk * step_);
    acc += textureLod(tReflect, clamp(uv + o, vec2(0.002), vec2(0.998)), lod).rgb * w; ws += w;
  }
  vec2 e = smoothstep(vec2(0.0), vec2(0.035), uv) * (1.0 - smoothstep(vec2(0.965), vec2(1.0), uv));
  return acc / ws * fade * e.x * e.y;
}`;
