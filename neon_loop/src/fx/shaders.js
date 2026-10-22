// GLSL for the vehicle FX: analytic (stateless) particles. The CPU only writes spawn data into ring buffers; the vertex
// shader evaluates position / size / fade from the particle's age, so a frame costs one buffer upload and three draw calls.
//
//   per-instance attributes:   aP0 = (spawn xyz, spawn time)   aV0 = (initial velocity xyz, life)
//                              aPar = (size0, size1, seed, groundY)   aCol = (rgb albedo / colour, alpha)   aKind (float)
//   kinds (uKind[i] = drag 1/s, gravity m/s² (+ rises), turbulence m, growth 1/s):
//       0 tyre spray mist   1 rooster-tail mist   2 tyre smoke   3 dust / impact puff   4 cold-gas thruster vapour

export const NL = 12;                            // lights used to colour the particles (nearest street lamps + car lights)

const LIGHTS_PARS = /* glsl */`
#define NL ${NL}
uniform vec4 uLPos[NL];                         // xyz position, w range (0 = none)
uniform vec4 uLCol[NL];                         // rgb colour * candela, w spot cos(outer) or -2 for a point light
uniform vec4 uLDir[NL];                         // xyz spot axis, w cos(inner)
uniform vec3 uAmb; uniform float uLK;
vec3 particleLight(vec3 p, float radius) {
  vec3 lit = uAmb;
  for (int i = 0; i < NL; i++) {
    vec3 d = uLPos[i].xyz - p; float d2 = dot(d, d);
    float att = 1.0 / (d2 + radius * radius * 0.8 + 0.4);
    float r = uLPos[i].w;
    float win = r > 0.0 ? pow(clamp(1.0 - d2 / (r * r), 0.0, 1.0), 2.0) : 1.0;
    float spot = 1.0;
    if (uLCol[i].w > -1.0) { spot = smoothstep(uLCol[i].w, uLDir[i].w, dot(-d * inversesqrt(d2 + 1e-5), uLDir[i].xyz)); }
    lit += uLCol[i].rgb * att * win * spot * uLK;
  }
  return min(lit, vec3(1.3));
}`;


// premultiplied-alpha fog (the stock chunk would tint the transparent parts)
const FOG_PM = /* glsl */`
#ifdef USE_FOG
  #ifdef FOG_EXP2
    float fogFactor = 1.0 - exp(-fogDensity * fogDensity * vFogDepth * vFogDepth);
  #else
    float fogFactor = smoothstep(fogNear, fogFar, vFogDepth);
  #endif
  gl_FragColor.rgb = mix(gl_FragColor.rgb, fogColor * gl_FragColor.a, fogFactor);
#endif`;

export const MIST_VERT = /* glsl */`
attribute vec4 aP0; attribute vec4 aV0; attribute vec4 aPar; attribute vec4 aCol; attribute float aKind;
uniform float uTime; uniform vec4 uKind[5];
varying vec2 vUv; varying float vA; varying vec3 vLit; varying vec3 vAlb; varying float vSeed;
#include <fog_pars_vertex>
${LIGHTS_PARS}
void main() {
  float age = uTime - aP0.w; float life = aV0.w;
  if (age < 0.0 || age > life) { gl_Position = vec4(2.0, 2.0, 2.0, 1.0); return; }
  vec4 kp = uKind[int(aKind + 0.5)];
  float k = kp.x; float e = exp(-k * age);
  vec3 g = vec3(0.0, kp.y, 0.0);
  vec3 p = aP0.xyz + (aV0.xyz - g / k) * ((1.0 - e) / k) + g / k * age;
  float seed = aPar.z;
  float tur = kp.z * (1.0 - e);
  p += vec3(sin(seed * 91.7 + age * 1.9), sin(seed * 47.3 + age * 1.4) * 0.5, cos(seed * 63.1 + age * 1.7)) * tur * 0.5;
  float t01 = age / life;
  float size = mix(aPar.x, aPar.y, 1.0 - exp(-age * kp.w));
  p.y = max(p.y, aPar.w + size * 0.42);
  float fade = smoothstep(0.0, 0.09 * life + 0.03, age) * (1.0 - smoothstep(0.35, 1.0, t01));
  float dc = length(cameraPosition - p);
  fade *= smoothstep(0.5, 3.2, dc - size * 0.4);
  vec3 cr = vec3(viewMatrix[0][0], viewMatrix[1][0], viewMatrix[2][0]);
  vec3 cu = vec3(viewMatrix[0][1], viewMatrix[1][1], viewMatrix[2][1]);
  float rot = seed * 6.2831 + age * (0.4 + fract(seed * 7.0));
  float cs = cos(rot), sn = sin(rot);
  vec2 q = position.xy * 2.0;
  vec2 qr = vec2(q.x * cs - q.y * sn, q.x * sn + q.y * cs);
  vec3 wp = p + (cr * qr.x + cu * qr.y) * size * 0.5;
  vUv = q; vA = aCol.a * fade; vAlb = aCol.rgb; vSeed = seed;
  vLit = particleLight(p, size);
  if (aKind > 3.5) vLit += vec3(0.30, 0.38, 0.52) * exp(-age * 5.0);     // thruster vapour: lit by the nozzle sheen as it leaves
  vec4 mvPosition = viewMatrix * vec4(wp, 1.0);
  vec4 worldPosition = vec4(wp, 1.0);
  gl_Position = projectionMatrix * mvPosition;
  #include <fog_vertex>
}`;

export const MIST_FRAG = /* glsl */`
varying vec2 vUv; varying float vA; varying vec3 vLit; varying vec3 vAlb; varying float vSeed;
#include <fog_pars_fragment>
float h21(vec2 p) { p = fract(p * vec2(123.34, 456.21)); p += dot(p, p + 45.32); return fract(p.x * p.y); }
float vn(vec2 p) { vec2 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f);
  return mix(mix(h21(i), h21(i + vec2(1, 0)), f.x), mix(h21(i + vec2(0, 1)), h21(i + vec2(1, 1)), f.x), f.y); }
void main() {
  float r = length(vUv);
  if (r > 1.0 || vA <= 0.002) discard;
  float soft = exp(-r * r * 3.2) * smoothstep(1.0, 0.7, r);
  vec2 w = vUv * 1.6 + vSeed * 13.1;
  float n = vn(w) * 0.55 + vn(w * 2.3 + 7.7) * 0.3 + vn(w * 5.1 + 3.3) * 0.15;
  float a = soft * (0.18 + 1.35 * n * n) * vA;
  gl_FragColor = vec4(vLit * vAlb * a, a * 0.55);
  ${FOG_PM}
}`;

// streaks: water droplets, debris chips (SPARK define: emissive additive sparks with a ground bounce)
export const STREAK_VERT = /* glsl */`
attribute vec4 aP0; attribute vec4 aV0; attribute vec4 aPar; attribute vec4 aCol; attribute float aKind;
uniform float uTime; uniform float uStreak;
varying vec2 vUv; varying float vA; varying vec3 vLit; varying vec3 vAlb; varying float vSeed; varying float vKind;
#include <fog_pars_vertex>
${LIGHTS_PARS}
const float GRAV = 9.81;
vec3 posAt(float a, float gy) {
  float drag = 0.35;
  float e = exp(-drag * a);
  vec3 g = vec3(0.0, -GRAV, 0.0);
  vec3 v0 = aV0.xyz;
  vec3 p = aP0.xyz + (v0 - g / drag) * ((1.0 - e) / drag) + g / drag * a;
  #ifdef SPARK
  // one bounce on the ground, losing most of the energy
  float vy = v0.y; float h = aP0.y - gy;
  float disc = vy * vy + 2.0 * GRAV * max(h, 0.0);
  float th = (vy + sqrt(disc)) / GRAV;
  if (a > th) {
    float b = a - th;
    vec3 ph = aP0.xyz + v0 * th; ph.y = gy;
    float vyh = -(vy - GRAV * th) * 0.32;
    p = ph + vec3(v0.x, 0.0, v0.z) * 0.55 * b; p.y = gy + vyh * b - 0.5 * GRAV * b * b;
    p.y = max(p.y, gy + 0.004);
  }
  #else
  p.y = max(p.y, gy + 0.004);
  #endif
  return p;
}
void main() {
  float age = uTime - aP0.w; float life = aV0.w;
  if (age < 0.0 || age > life) { gl_Position = vec4(2.0, 2.0, 2.0, 1.0); return; }
  float gy = aPar.w;
  vec3 head = posAt(age, gy);
  vec3 tail = posAt(max(age - uStreak, 0.0), gy);
  vec3 dir = head - tail; float len = length(dir);
  vec3 axis = len > 1e-4 ? dir / len : vec3(0.0, 1.0, 0.0);
  vec3 toCam = normalize(cameraPosition - head);
  vec3 side = cross(axis, toCam); float sl = length(side);
  side = sl > 1e-4 ? side / sl : vec3(1.0, 0.0, 0.0);
  float width = aPar.x;
  float lmin = width * 1.4;
  if (len < lmin) { tail = head - axis * lmin; }
  float t01 = age / life;
  vec3 p = mix(tail, head, position.y + 0.5) + side * position.x * width * 2.0;
  vUv = vec2(position.x * 2.0, position.y * 2.0);
  float fade = (1.0 - smoothstep(0.6, 1.0, t01)) * smoothstep(0.0, 0.03, age);
  #ifndef SPARK
  fade *= smoothstep(gy, gy + 0.05, head.y + 0.02);
  #endif
  vA = aCol.a * fade; vAlb = aCol.rgb; vSeed = aPar.z; vKind = aKind;
  #ifdef SPARK
  vLit = vec3(1.0);
  #else
  vLit = particleLight(head, 0.3);
  #endif
  vec4 mvPosition = viewMatrix * vec4(p, 1.0);
  vec4 worldPosition = vec4(p, 1.0);
  gl_Position = projectionMatrix * mvPosition;
  #include <fog_vertex>
}`;

export const STREAK_FRAG = /* glsl */`
varying vec2 vUv; varying float vA; varying vec3 vLit; varying vec3 vAlb; varying float vSeed; varying float vKind;
#include <fog_pars_fragment>
void main() {
  if (vA <= 0.003) discard;
  float across = 1.0 - smoothstep(0.35, 1.0, abs(vUv.x));
  float along = smoothstep(-1.0, -0.2, vUv.y) * (1.0 - smoothstep(0.85, 1.0, vUv.y) * 0.6);
  #ifdef SPARK
    float core = smoothstep(0.0, 1.0, across) * along;
    float flick = 0.75 + 0.25 * sin(vSeed * 50.0 + gl_FragCoord.x * 0.0);
    vec3 col = vAlb * (0.35 + 0.65 * smoothstep(-1.0, 1.0, vUv.y));
    gl_FragColor = vec4(col * core * vA * flick, core * vA);
  #else
    float chip = step(vKind, 0.5);          // kind 0 = droplet, 1 = debris chip
    float shape = mix(across * along, step(abs(vUv.x), 0.8) * step(abs(vUv.y), 0.9), 1.0 - chip);
    float a = shape * vA;
    gl_FragColor = vec4(vLit * vAlb * a, a * mix(0.85, 0.12, chip));
    ${FOG_PM}
  #endif
}`;
