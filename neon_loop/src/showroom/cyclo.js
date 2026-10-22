// The cyclorama: one seamless surface (floor -> quarter-circle sweep -> wall -> ceiling) shaded analytically.
//  * diffuse: the exact irradiance of every rectangular studio light (Lambert / Arvo polygon formula) + the dome term; on the floor it
//    is replaced by the baked lightmap (soft area-light shadows and ambient occlusion of the car, see bake.js);
//  * floor gloss: the lights' rectangles reflected by a rough mirror (Gaussian-blurred rectangle = product of two erf), the blurred planar
//    reflection of the car with contact hardening (blur grows with the distance to what is reflected, found by sphere-tracing the car's
//    SDF), and for the night preset the blurred HDRI;
//  * wall: a faint view-relative halo so the backdrop is never a flat black.
import * as THREE from 'three';

export const MAXL = 12;

export const RECT_GLSL = /* glsl */`
#define MAXL ${MAXL}
uniform int uNL;
uniform vec3 uLC[MAXL]; uniform vec3 uLX[MAXL]; uniform vec3 uLY[MAXL]; uniform vec3 uLN[MAXL]; uniform vec3 uLL[MAXL];
uniform vec3 uLK[MAXL];                    // per light: x = scale on the floor, y = scale on the wall/ceiling, z = scale in the floor's reflection (0 = flag/gobo light, not in the mirror)
const float PI_ = 3.14159265359;
// irradiance on a surface point p with normal n from the emitter i (uniform radiance, emits toward +uLN)
vec3 rectE(vec3 p, vec3 n, int i) {
  vec3 c = uLC[i], x = uLX[i], y = uLY[i];
  if (dot(p - c, uLN[i]) <= 0.0) return vec3(0.0);
  vec3 a = normalize(c - x - y - p), b = normalize(c + x - y - p), cc = normalize(c + x + y - p), d = normalize(c - x + y - p);
  vec3 f = acos(clamp(dot(a, b), -1.0, 1.0)) * normalize(cross(a, b))
         + acos(clamp(dot(b, cc), -1.0, 1.0)) * normalize(cross(b, cc))
         + acos(clamp(dot(cc, d), -1.0, 1.0)) * normalize(cross(cc, d))
         + acos(clamp(dot(d, a), -1.0, 1.0)) * normalize(cross(d, a));
  return uLL[i] * max(0.5 * dot(f, n) * RECT_SIGN, 0.0);
}
float erf_(float x) { float x2 = x * x; float a = 0.147; float t = sqrt(max(1.0 - exp(-x2 * (1.2732395 + a * x2) / (1.0 + a * x2)), 0.0)); return x < 0.0 ? -t : t; }
// the emitter seen in a rough mirror: ray origin p, reflected direction r, angular blur sigma (radians)
vec3 rectSpec(vec3 p, vec3 r, float sigma, int i) {
  float dn = dot(r, uLN[i]);
  if (dn >= -1e-3) return vec3(0.0);
  float t = dot(uLC[i] - p, uLN[i]) / dn;
  if (t <= 0.0) return vec3(0.0);
  vec3 q = p + r * t - uLC[i];
  float hx = length(uLX[i]), hy = length(uLY[i]);
  float qx = dot(q, uLX[i]) / hx, qy = dot(q, uLY[i]) / hy;
  float s = max(t * sigma / max(-dn, 0.2), 0.012);
  float k = 0.70710678 / s;
  float mx = 0.5 * (erf_((hx - qx) * k) + erf_((hx + qx) * k));
  float my = 0.5 * (erf_((hy - qy) * k) + erf_((hy + qy) * k));
  return uLL[i] * mx * my;
}
`;

const VERT = /* glsl */`
varying vec3 vW;
void main() {
  vec4 w = modelMatrix * vec4(position, 1.0);
  vW = w.xyz;
  gl_Position = projectionMatrix * viewMatrix * w;
}`;

const FRAG = /* glsl */`
precision highp float;
precision highp sampler3D;
${RECT_GLSL}
uniform vec3 uCam, uCamFwd;
uniform vec3 uAmb;
uniform vec3 uFloorAlb, uWallAlb, uGlow;
uniform vec3 uRoomSpec;
uniform float uRough, uSpec, uReflGain, uReflOn, uGlowH, uWallK;
uniform float uRf, uRc, uH;               // floor radius, sweep radius, wall height
uniform sampler2D tLight; uniform vec4 uLightRect; uniform float uUseLight;
uniform sampler2D tRefl; uniform mat4 uReflVP; uniform vec2 uReflPx; uniform float uReflK;      // planar reflection, its (unjittered) view-projection, texel size, texels per radian
uniform sampler3D tSdf; uniform vec3 uSdfMin, uSdfMax, uSdfInv; uniform float uSdfOn;
uniform sampler2D tSky; uniform float uSkyOn; uniform vec3 uSkyGain; uniform float uSkyMips; uniform float uSkyRot;
uniform float uEnvFloorK; uniform float uFrame; uniform float uEnvPass; uniform float uWet; uniform float uReflQ;
uniform float uFogDist; uniform float uHazeLod; uniform float uHazeEl; uniform float uHazeK;
uniform vec2 uTyre[4]; uniform float uTyreAO;        // contact occlusion under the tyres (the LOD meshes the SDF and the bake see are tyre-less, the bake only has the borrowed hi-LOD tyres)
varying vec3 vW;

float ign(vec2 p) { return fract(52.9829189 * fract(dot(p, vec2(0.06711056, 0.00583715)))); }
float marchHull(vec3 ro, vec3 rd) {
  if (uSdfOn < 0.5) return -1.0;
  float t = 0.03;
  for (int i = 0; i < 18; i++) {
    vec3 q = ro + rd * t;
    vec3 uvw = (q - uSdfMin) * uSdfInv;
    if (any(lessThan(uvw, vec3(0.0))) || any(greaterThan(uvw, vec3(1.0)))) {
      vec3 dd = max(max(uSdfMin - q, q - uSdfMax), vec3(0.0));
      t += max(length(dd), 0.06);
    } else {
      float d = texture(tSdf, uvw).r;
      if (d < 0.025) return t;
      t += max(d * 0.9, 0.02);
    }
    if (t > 14.0) break;
  }
  return -1.0;
}
vec2 eqUv(vec3 d) { return vec2(atan(d.z, d.x) / (2.0 * PI_) + 0.5, asin(clamp(d.y, -1.0, 1.0)) / PI_ + 0.5); }
vec3 sky(vec3 d, float lod) { float c = cos(uSkyRot), s = sin(uSkyRot); d = vec3(c * d.x - s * d.z, d.y, s * d.x + c * d.z); return textureLod(tSky, eqUv(d), lod).rgb * uSkyGain; }

void main() {
  vec3 p = vW;
  float r = length(p.xz);
  // analytic inward normal of the sweep
  vec3 n = vec3(0.0, 1.0, 0.0);
  float fl = 1.0;                              // 1 on the floor, 0 on the wall
  if (r > uRf && p.y < uRc) {
    vec2 d = vec2(r - uRf, p.y - uRc); float l = max(length(d), 1e-4);
    vec2 nn = -d / l; vec2 dirXZ = p.xz / max(r, 1e-4);
    n = vec3(dirXZ.x * nn.x, nn.y, dirXZ.y * nn.x);
    fl = clamp(nn.y, 0.0, 1.0);
  } else if (r > uRf) { n = vec3(-p.x, 0.0, -p.z) / max(r, 1e-4); fl = 0.0; }
  if (p.y > uH - 0.02) { n = vec3(0.0, -1.0, 0.0); fl = 0.0; }
  if (uFogDist > 0.0 && fl < 0.5) discard;       // open (night-city) mode: just the floor disc, the HDRI sky is the backdrop
  vec3 V = normalize(uCam - p);
  float nv = max(dot(n, V), 0.0);

  // ---- diffuse light
  vec3 E = vec3(0.0);
  vec2 luv = (p.xz - uLightRect.xy) / uLightRect.z + 0.5;
  bool inMap = uUseLight > 0.5 && all(greaterThan(luv, vec2(0.002))) && all(lessThan(luv, vec2(0.998)));
  if (inMap) E = texture(tLight, luv).rgb;
  else {
    float fk = smoothstep(0.0, 0.8, fl);
    for (int i = 0; i < MAXL; i++) { if (i >= uNL) break; E += rectE(p, n, i) * mix(uLK[i].y, uLK[i].x, fk); }
    E += PI_ * uAmb * (0.55 + 0.45 * n.y);
  }
  E *= mix(uWallK, 1.0, smoothstep(0.0, 0.8, fl));
  if (uEnvPass > 0.5) E *= mix(1.0, uEnvFloorK, smoothstep(0.0, 0.5, fl));      // what the car reflects of the floor (the pool the camera sees is not what the body mirrors)
  vec3 alb = mix(uWallAlb, uFloorAlb, smoothstep(0.0, 0.5, fl));
  vec3 col = alb / PI_ * E;

  // wall halo: where the camera looks along the floor, a soft lift low on the wall (so the backdrop has depth)
  if (fl < 0.99 && uEnvPass < 0.5) {
    vec2 dirW = normalize(p.xz + 1e-4);
    float az = dot(dirW, normalize(uCamFwd.xz + 1e-4));
    float h = clamp(p.y / uGlowH, 0.0, 4.0);
    float prof = exp(-h * h * 0.8) * (0.45 + 0.55 * smoothstep(-0.6, 1.0, az));
    col += uGlow * prof * (1.0 - fl);
  }

  // ---- floor gloss
  if (fl > 0.01 && uSpec > 0.0) {
    vec3 rv = reflect(-V, n);
    float rough = uRough;
    float alpha = rough * rough;
    float sigma = 1.25 * alpha + 0.004;
    float F0 = 0.04;
    float fr = F0 + (max(1.0 - rough, F0) - F0) * pow(1.0 - nv, 5.0);
    vec3 spec = uRoomSpec;
    for (int i = 0; i < MAXL; i++) { if (i >= uNL) break; if (uLK[i].z > 0.0) spec += rectSpec(p + n * 0.002, rv, sigma, i) * uLK[i].z; }
    vec3 refl = vec3(0.0); float ra = 0.0;
    if (uSkyOn > 0.5) { spec += min(sky(rv, clamp(log2(1.0 + rough * rough * 120.0), 0.0, uSkyMips)), vec3(2.2)); }       // blurred street lamps would otherwise smear into a white band across the wet floor
    if (uReflOn > 0.5 && uReflQ > 0.5 && uEnvPass < 0.5) {
      float t = marchHull(p + n * 0.003, rv);
      vec4 rc = uReflVP * vec4(p, 1.0);
      vec2 ruv = rc.xy / rc.w * 0.5 + 0.5;
      float wrad = (t > 0.0 ? t : 3.0) * sigma;                         // blur radius in metres at the reflected surface
      float dQ = length(uCam - p) + max(t, 0.0);
      float pxRad = wrad / max(dQ, 0.1) * uReflK;                       // the same radius in reflection texels
      float lod = clamp(log2(max(pxRad, 1.0)), 0.0, 6.0);
      float rot = ign(gl_FragCoord.xy + uFrame * 17.0) * 6.2831853;
      vec4 acc = vec4(0.0);
      const int NT = 9;
      for (int i = 0; i < NT; i++) {
        float fi = (float(i) + 0.5) / float(NT);
        float ang = float(i) * 2.399963 + rot; float rr = sqrt(fi);
        vec2 off = vec2(cos(ang), sin(ang)) * rr * pxRad * uReflPx;
        acc += textureLod(tRefl, ruv + off, max(lod - 1.5, 0.0));
      }
      acc /= float(NT);
      refl = acc.rgb; ra = acc.a;
    }
    col += fr * (uSpec * spec * (1.0 - ra) + uReflGain * refl) * fl;
  }

  if (fl > 0.5 && uTyreAO > 0.0) {
    float ao = 1.0;
    for (int i = 0; i < 4; i++) { vec2 d = (p.xz - uTyre[i]) / vec2(0.27, 0.40); ao = min(ao, 1.0 - uTyreAO * exp(-dot(d, d) * 1.7)); }
    col *= ao;
  }

  // sky / horizon fog for the night preset
  if (uFogDist > 0.0) {
    float dist = length(p.xz - uCam.xz);                                   // along the ground: looking straight down there is no haze
    float k = 1.0 - exp(-(dist * dist) / (uFogDist * uFogDist));            // nothing near, everything at the horizon
    col = mix(col, sky(normalize(vec3(p.x - uCam.x, uHazeEl * dist, p.z - uCam.z)), uHazeLod) * uHazeK, k * k);       // the floor runs out into the skyline's own base row (same azimuth, a little blurred): no seam at the horizon
  }
  gl_FragColor = vec4(col, 1.0);
}`;

/** The profile of the tub: floor to radius rf, quarter-circle sweep of radius rc, wall to height h, flat ceiling. */
export function cycloGeometry(rf, rc, h, segs = 128) {
  const pts = [new THREE.Vector2(0, 0)];
  pts.push(new THREE.Vector2(rf * 0.5, 0), new THREE.Vector2(rf, 0));
  const N = 24;
  for (let i = 1; i <= N; i++) { const a = (i / N) * Math.PI / 2; pts.push(new THREE.Vector2(rf + rc * Math.sin(a), rc - rc * Math.cos(a))); }
  pts.push(new THREE.Vector2(rf + rc, h * 0.5), new THREE.Vector2(rf + rc, h), new THREE.Vector2((rf + rc) * 0.5, h), new THREE.Vector2(0, h));
  return new THREE.LatheGeometry(pts, segs);
}

export function createCycloMaterial() {
  const z3 = () => ({ value: new THREE.Vector3() });
  const arr = () => ({ value: Array.from({ length: MAXL }, () => new THREE.Vector3()) });
  const U = {
    uNL: { value: 0 }, uLC: arr(), uLX: arr(), uLY: arr(), uLN: arr(), uLL: arr(), uLK: arr(),
    uCam: z3(), uCamFwd: { value: new THREE.Vector3(0, 0, -1) }, uAmb: z3(), uFloorAlb: z3(), uWallAlb: z3(), uGlow: z3(), uRoomSpec: z3(),
    uRough: { value: 0.35 }, uSpec: { value: 1 }, uReflGain: { value: 1 }, uReflOn: { value: 0 }, uGlowH: { value: 5 }, uWallK: { value: 0.2 },
    uRf: { value: 10 }, uRc: { value: 3.5 }, uH: { value: 14 },
    tLight: { value: null }, uLightRect: { value: new THREE.Vector4(0, 0, 28, 0) }, uUseLight: { value: 0 },
    tRefl: { value: null }, uReflVP: { value: new THREE.Matrix4() }, uReflPx: { value: new THREE.Vector2(1 / 512, 1 / 512) }, uReflK: { value: 400 },
    tSdf: { value: null }, uSdfMin: z3(), uSdfMax: z3(), uSdfInv: z3(), uSdfOn: { value: 0 },
    tSky: { value: null }, uSkyRot: { value: 0 }, uSkyOn: { value: 0 }, uSkyGain: { value: new THREE.Vector3(1, 1, 1) }, uSkyMips: { value: 6 },
    uTyre: { value: [new THREE.Vector2(-0.885, -1.487), new THREE.Vector2(0.885, -1.487), new THREE.Vector2(-0.885, 1.61), new THREE.Vector2(0.885, 1.61)] }, uTyreAO: { value: 0.6 },
    uReflQ: { value: 1 }, uFrame: { value: 0 }, uEnvPass: { value: 0 }, uEnvFloorK: { value: 1 }, uWet: { value: 0 }, uFogDist: { value: 0 }, uHazeLod: { value: 1.5 }, uHazeEl: { value: 0.004 }, uHazeK: { value: 1 },
  };
  const m = new THREE.ShaderMaterial({
    uniforms: U, vertexShader: VERT, fragmentShader: FRAG.replace(/RECT_SIGN/g, '-1.0'),
    side: THREE.DoubleSide, toneMapped: false, depthWrite: true,
  });
  m.glslVersion = null;
  return m;
}

/** Fill the light uniforms from a preset's rect list. Returns the world-space rect records (for the bake and the env cube). */
export function lightRects(preset) {
  const out = [];
  const tgt = new THREE.Vector3(), c = new THREE.Vector3(), n = new THREE.Vector3(), ax = new THREE.Vector3(), ay = new THREE.Vector3(), ref = new THREE.Vector3();
  for (const l of preset.lights.slice(0, MAXL)) {
    c.fromArray(l.pos); tgt.fromArray(l.aim);
    n.subVectors(tgt, c).normalize();
    ref.set(0, 1, 0); if (Math.abs(n.y) > 0.92) ref.set(0, 0, -1);
    ax.crossVectors(ref, n).normalize();              // x axis: horizontal (or along -Z for ceiling boxes)
    ay.crossVectors(n, ax).normalize();               // y axis completes the frame: ax x ay = n  (see rectE: CCW seen from the front)
    if (l.spin) { const q = new THREE.Quaternion().setFromAxisAngle(n, THREE.MathUtils.degToRad(l.spin)); ax.applyQuaternion(q); ay.applyQuaternion(q); }
    out.push({
      name: l.name, c: c.clone(), n: n.clone(), ax: ax.clone().multiplyScalar(l.size[0] / 2), ay: ay.clone().multiplyScalar(l.size[1] / 2),
      L: new THREE.Vector3(...l.L), w: l.size[0], h: l.size[1], count: l.n ?? 64, beam: l.beam ?? 0,
      glass: l.glass, glassOnly: !!l.glassOnly, tyreOnly: !!l.tyreOnly, grad: l.grad ?? 0, soft: l.soft ?? 0, gobo: l.gobo ?? null, band: l.band ?? null, env: l.env !== false && !l.glassOnly && !l.tyreOnly, kF: l.kF ?? 1, kW: l.kW ?? 1, kD: l.kD ?? 1, kS: l.kS ?? ((l.env === false || l.glassOnly || l.tyreOnly) ? 0 : 1),
    });
  }
  return out;
}

export function applyLights(mat, rects) {
  const U = mat.uniforms;
  U.uNL.value = rects.length;
  rects.forEach((r, i) => { U.uLC.value[i].copy(r.c); U.uLX.value[i].copy(r.ax); U.uLY.value[i].copy(r.ay); U.uLN.value[i].copy(r.n); U.uLL.value[i].copy(r.L); U.uLK.value[i].set(r.kF, r.kW, r.kS); });
}
