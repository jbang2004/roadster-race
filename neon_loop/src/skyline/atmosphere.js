// Atmosphere: global height fog (patches three's fog ShaderChunks), the sky dome (clouds lit from below by the
// city, moon, light-pollution gradient) and the global hemisphere + moon lights.
//
// How the fog reaches every material without touching them: the fog chunks are replaced, and the extra uniforms
// (uK0..uK7) are added to ShaderLib / UniformsLib.fog as Float32Arrays — three's cloneUniforms copies Vector/Color
// objects but passes typed arrays BY REFERENCE, so every material instance shares the same arrays and we simply
// mutate them once per frame. scene.fog only has to be non-null (it makes three define USE_FOG).
import * as THREE from 'three';
import { G } from '../core/globals.js';
import { lightEverything } from '../core/layers.js';
import { makeNoiseTexture } from './util.js';

// ---------- shared uniform data ----------
export const KU = {
  uK0: new Float32Array(4), uK1: new Float32Array(4), uK2: new Float32Array(4), uK3: new Float32Array(4),
  uK4: new Float32Array(4), uK5: new Float32Array(4), uK6: new Float32Array(4), uK7: new Float32Array(4),
};

/** Tunables (live: change them from the console, e.g. __skyline.params.fog.density = 0.0004). */
export const params = {
  fog: {
    density: 0.0002,         // base exponential distance fog (1/m)
    ground: 0.0003,          // extra density hugging the ground (1/m at y = 0)
    scaleHeight: 60,         // m, e-folding height of the ground layer
    patch: 0.3,              // 0..1 patchiness of the ground mist
    gain: 1.0,               // global multiplier on optical depth
    glow: 1.0,               // global multiplier on the city-glow colour (fog + sky)
  },
  colors: {                  // linear RGB, radiance of the glow at the horizon
    haze: [0.0085, 0.0105, 0.0240],
    sodium: [0.110, 0.042, 0.011],
    magenta: [0.075, 0.012, 0.050],
    cyan: [0.006, 0.034, 0.055],
    zenith: [0.0028, 0.0042, 0.0115],
  },
  sky: {
    cover: 0.46,             // cloud coverage threshold (higher = fewer clouds)
    speed: 1.0,              // cloud drift speed multiplier
    moonGap: 0.85,           // how much the clouds open up around the moon (0..1)
    moonDir: [-0.30, 0.36, -0.88],
    gain: 1.0,               // overall sky brightness
    cloudHeight: 1900,
    cloudBright: 1.0,
  },
  canalX: 420,               // x of the canal centre (mist hangs over it)
  lights: {
    hemiIntensity: 0.9, hemiSky: [0.17, 0.25, 0.46], hemiGround: [0.14, 0.085, 0.06],
    moonIntensity: 0.10, moonColor: [0.62, 0.74, 1.0],
  },
};

// ---------- GLSL ----------
const U_DECL = /* glsl */`
uniform vec4 uK0; // x base density, y ground density, z 1/scaleHeight, w mist 0..1
uniform vec4 uK1; // x time, y patchiness, z glow gain, w fog gain
uniform vec4 uK2; // haze rgb
uniform vec4 uK3; // sodium rgb
uniform vec4 uK4; // magenta rgb
uniform vec4 uK5; // cyan rgb
uniform vec4 uK6; // zenith rgb
uniform vec4 uK7; // xyz moon direction, w canal x
`;

export const KFOG_FUNCS = /* glsl */`
float kLobe(vec2 h, vec2 d, float k) { return exp(k * (dot(h, d) - 1.0)); }
// Radiance of the light-polluted horizon for horizontal direction h (unit xz). North (-z) = downtown.
// w fades the district lobes out for near-vertical rays (no pie-slice artefact looking straight up/down).
vec3 kHorizonW(vec2 h, float w) {
  vec3 c = uK2.xyz;
  vec3 l = uK3.xyz * (0.90 * kLobe(h, vec2(0.60, -0.80), 4.5) + 0.75 * kLobe(h, vec2(-0.85, 0.52), 4.0) + 0.45 * kLobe(h, vec2(0.10, 0.99), 3.5));
  l += uK4.xyz * (1.00 * kLobe(h, vec2(0.00, -1.00), 3.5) + 0.80 * kLobe(h, vec2(0.96, 0.28), 4.5) + 0.55 * kLobe(h, vec2(-0.60, -0.80), 6.0));
  l += uK5.xyz * (0.90 * kLobe(h, vec2(-0.45, -0.89), 6.0) + 0.60 * kLobe(h, vec2(0.70, 0.71), 5.0));
  vec3 avg = (uK3.xyz + uK4.xyz + uK5.xyz) * 0.22;
  return (c + mix(avg, l, w)) * uK1.z;
}
vec3 kHorizon(vec2 h) { return kHorizonW(h, 1.0); }
// Colour of the haze seen along direction rd: warm glow low and toward lit districts, cooler overhead.
vec3 kFogColor(vec3 rd) {
  float hl = length(rd.xz);
  vec2 h = rd.xz / max(hl, 1e-4);
  vec3 hz = kHorizonW(h, smoothstep(0.02, 0.45, hl));
  float e = max(rd.y, 0.0);
  return mix(hz, uK6.xyz + hz * 0.10, 1.0 - exp(-e * 3.2));
}
// Optical depth along ray (fragment - camera, world metres): uniform distance fog + ground-hugging height fog.
float kFogTau(vec3 ray) {
  float dist = length(ray);
  float b = uK0.z;
  float cy = max(cameraPosition.y, 0.0);
  float k = clamp(b * ray.y, -12.0, 12.0);
  float f = abs(k) < 1e-3 ? 1.0 - 0.5 * k : (1.0 - exp(-k)) / k;
  float mist = uK0.w;
  vec2 wp = ray.xz + cameraPosition.xz;
  float t = uK1.x;
  float pt = 1.0 + uK1.y * (sin(wp.x * 0.0107 + t * 0.045) * sin(wp.y * 0.0131 - t * 0.037) + 0.6 * sin((wp.x + wp.y) * 0.0231 + t * 0.081));
  pt = max(pt, 0.25);
  float cm = (wp.x - uK7.w) / 110.0;
  pt *= 1.0 + 1.5 * exp(-cm * cm);                        // mist hangs over the canal
  float tauG = uK0.y * (1.0 + 2.2 * mist) * pt * exp(-b * cy) * f * dist;
  return (uK0.x * (1.0 + 0.9 * mist) * dist + tauG) * uK1.w;
}
float kFogT(vec3 ray) { return exp(-kFogTau(ray)); }
vec3 kFogApply(vec3 col, vec3 ray) {
  float d = length(ray) + 1e-4;
  float f = 1.0 - exp(-kFogTau(ray));
  return mix(col, kFogColor(ray / d), f);
}
`;

const FOG_PARS_FRAG_ORIG = THREE.ShaderChunk.fog_pars_fragment;
const FOG_VERT_ORIG = THREE.ShaderChunk.fog_vertex;
const FOG_PARS_VERT_ORIG = THREE.ShaderChunk.fog_pars_vertex;
let patched = false;

function patchFog() {
  if (patched) return; patched = true;
  const C = THREE.ShaderChunk;
  C.fog_pars_vertex = /* glsl */`
#ifdef USE_FOG
	varying float vFogDepth;
	varying vec3 vFogRay;
#endif
`;
  C.fog_vertex = /* glsl */`
#ifdef USE_FOG
	vFogDepth = - mvPosition.z;
	vFogRay = transpose( mat3( viewMatrix ) ) * mvPosition.xyz;
#endif
`;
  C.fog_pars_fragment = /* glsl */`
#ifdef USE_FOG
	uniform vec3 fogColor;
	varying float vFogDepth;
	varying vec3 vFogRay;
	#ifdef FOG_EXP2
		uniform float fogDensity;
	#else
		uniform float fogNear;
		uniform float fogFar;
	#endif
	${U_DECL}
	${KFOG_FUNCS}
#endif
`;
  C.fog_fragment = /* glsl */`
#ifdef USE_FOG
	gl_FragColor.rgb = kFogApply( gl_FragColor.rgb, vFogRay );
#endif
`;
  // add the shared uniforms to every built-in shader and to UniformsLib.fog (for ShaderMaterials that merge it)
  const add = (u) => { for (const k in KU) u[k] = { value: KU[k] }; };
  add(THREE.UniformsLib.fog);
  for (const id in THREE.ShaderLib) {
    const sl = THREE.ShaderLib[id];
    if (sl.fragmentShader && sl.fragmentShader.includes('fog_pars_fragment') && sl.uniforms) add(sl.uniforms);
  }
}
export function restoreFogChunks() {   // debugging helper
  const C = THREE.ShaderChunk; C.fog_pars_fragment = FOG_PARS_FRAG_ORIG; C.fog_vertex = FOG_VERT_ORIG; C.fog_pars_vertex = FOG_PARS_VERT_ORIG;
}

/** Uniforms object to give to a custom ShaderMaterial that does NOT use `fog: true` but wants K's functions. */
export function kUniforms() { const u = {}; for (const k in KU) u[k] = { value: KU[k] }; return u; }
/** Uniforms for a ShaderMaterial with `fog: true` (three's fog uniforms + K's shared arrays) plus your own. */
export function makeFogUniforms(extra = {}) {
  return { ...THREE.UniformsUtils.clone(THREE.UniformsLib.fog), ...kUniforms(), ...extra };
}
/** GLSL block (uniform declarations + functions) for materials that don't go through fog_pars_fragment. */
export const KGLSL = U_DECL + KFOG_FUNCS;

// ---------- sky dome ----------
const SKY_VERT = /* glsl */`
varying vec3 vDir;
void main() {
  vDir = position;
  vec4 p = projectionMatrix * vec4(mat3(viewMatrix) * position, 1.0);
  gl_Position = p.xyww;
}`;

const SKY_FRAG = /* glsl */`
uniform sampler2D tNoise;
uniform vec4 uS0;   // x cover, y speed, z moonGap, w gain
uniform vec4 uS1;   // x cloud brightness, y cloud height
uniform vec3 uSkyTime;
varying vec3 vDir;
${U_DECL}
${KFOG_FUNCS}

float hash12(vec2 p) { vec3 p3 = fract(vec3(p.xyx) * .1031); p3 += dot(p3, p3.yzx + 33.33); return fract((p3.x + p3.y) * p3.z); }

vec3 kSky(vec3 rd) {
  float t = uK1.x * uS0.y;
  float e = rd.y;
  vec2 h = normalize(rd.xz + vec2(1e-5));
  vec3 hz = kFogColor(rd);
  vec3 moonDir = normalize(uK7.xyz);
  float mc = dot(rd, moonDir);
  float ang = acos(clamp(mc, -1.0, 1.0));

  // --- clear sky: dark violet-blue with the light-pollution gradient hugging the horizon
  vec3 clearSky = uK6.xyz * 1.4 + hz * (0.55 * exp(-max(e, 0.0) * 5.5) + 0.06);
  vec3 moonCol = vec3(0.72, 0.86, 1.15);
  float disc = smoothstep(0.999900, 0.999945, mc);
  float halo = exp(-ang * ang * 9000.0) * 0.22 + exp(-ang * 14.0) * 0.016;
  clearSky += moonCol * (disc * 3.0 + halo);

  // --- clouds on a ceiling plane, perspective-correct
  float eps = 0.035;
  float k = uS1.y / (max(e, 0.0) + eps);
  vec2 p = rd.xz * k * 0.00011;
  vec2 wind = vec2(0.0022, 0.0009) * t;
  vec2 pw = p + wind;
  vec4 n0 = texture2D(tNoise, pw * 0.5 + vec2(0.21, 0.67));
  pw += (n0.gb - 0.5) * 0.05;                                     // domain warp: wispy, torn edges
  vec4 n1 = texture2D(tNoise, pw);
  vec4 n2 = texture2D(tNoise, pw * 2.3 + wind * 0.6 + vec2(0.37, 0.71));
  vec4 n3 = texture2D(tNoise, pw * 5.3 + wind * 1.1 + vec2(0.11, 0.53));
  float dens = n1.r * 0.60 + n2.g * 0.28 + n3.b * 0.08 + n3.a * 0.04;
  // keep a window of clearer sky around the moon (slowly breathing)
  float gapAmt = uS0.z * (0.55 + 0.45 * sin(uK1.x * 0.021));
  dens -= gapAmt * 0.60 * smoothstep(0.42, 0.0, ang);
  float cover = uS0.x;
  float cl = smoothstep(cover - 0.13, cover + 0.12, dens);
  float thick = smoothstep(cover - 0.05, cover + 0.45, dens);
  // pseudo self-shadowing: density gradient along the radial direction (towards the city below the camera)
  vec2 q = pw - normalize(rd.xz + vec2(1e-5)) * 0.018;
  float d2 = texture2D(tNoise, q).r * 0.60 + texture2D(tNoise, q * 2.3 + wind * 0.6 + vec2(0.37, 0.71)).g * 0.28 + n3.b * 0.08 + n3.a * 0.04;
  float rim = clamp((d2 - dens) * 5.0, -1.0, 1.0);

  // light arriving from below: sodium orange low, magenta higher, brighter over lit districts
  float lumH = dot(hz, vec3(0.3, 0.55, 0.15));
  vec3 under = mix(vec3(1.0, 0.50, 0.22), vec3(0.78, 0.30, 0.55), smoothstep(0.02, 0.65, e));
  under = mix(under, under * 0.6 + normalize(hz + 1e-4) * 0.6, 0.35);
  float glow = (lumH * 4.2 + 0.012) * uS1.x;
  float lightT = 1.0 - 0.80 * thick;
  float detail = 0.86 + 0.30 * n3.b;
  vec3 cloudCol = under * glow * lightT * detail * (1.0 + 0.45 * rim);
  cloudCol += uK6.xyz * 2.0;
  // moonlight scattered by the cloud around the moon
  cloudCol += moonCol * (exp(-ang * ang * 22.0) * 0.30 + exp(-ang * 2.6) * 0.012) * (0.25 + 0.75 * (1.0 - thick));

  float horizonFade = smoothstep(0.0, 0.14, e);
  vec3 col = mix(clearSky, cloudCol, cl);
  col = mix(hz, col, horizonFade);
  if (e < 0.0) col = hz * (1.0 + e * 0.3);
  col *= uS0.w;
  col *= 1.0 + (hash12(gl_FragCoord.xy) - 0.5) * 0.04;      // de-banding dither
  return col;
}

void main() {
  gl_FragColor = vec4(kSky(normalize(vDir)), 1.0);
  #include <tonemapping_fragment>
  #include <colorspace_fragment>
}`;

// ---------- install ----------
let atmosphere = null;

/** Called first (before any material compiles). Idempotent: returns the same atmosphere on repeat calls. */
export function installAtmosphere(app) {
  if (atmosphere) return atmosphere;
  patchFog();
  const scene = app.scene;
  // a non-null fog makes three define USE_FOG; the values are ignored by the patched chunks (kept as a fallback tint)
  scene.fog = new THREE.FogExp2(0x1b1624, 0.00025);
  scene.background = null;

  const noise = makeNoiseTexture(512, 11);
  const skyMat = new THREE.ShaderMaterial({
    vertexShader: SKY_VERT, fragmentShader: SKY_FRAG,
    uniforms: { tNoise: { value: noise }, uS0: { value: new THREE.Vector4() }, uS1: { value: new THREE.Vector4() }, uSkyTime: { value: new THREE.Vector3() }, ...kUniforms() },
    depthTest: false, depthWrite: false, side: THREE.DoubleSide, fog: false,
  });
  const dome = new THREE.Mesh(new THREE.SphereGeometry(1, 48, 24), skyMat);
  dome.frustumCulled = false; dome.renderOrder = -1000; dome.name = 'K-sky';
  scene.add(dome);

  const hemi = lightEverything(new THREE.HemisphereLight(0x2a40a0, 0x241810, 1)); hemi.name = 'K-hemi';
  const moon = lightEverything(new THREE.DirectionalLight(0x9fbcff, 0.1)); moon.name = 'K-moon';
  moon.target.position.set(0, 0, 0);
  scene.add(hemi, moon, moon.target);

  const weather = { rain: 0.3, mist: 0.4 };
  const tmpDir = new THREE.Vector3();

  const syncUniforms = (t) => {
    const f = params.fog, c = params.colors, s = params.sky, L = params.lights;
    KU.uK0[0] = f.density; KU.uK0[1] = f.ground; KU.uK0[2] = 1 / f.scaleHeight; KU.uK0[3] = weather.mist;
    KU.uK1[0] = t; KU.uK1[1] = f.patch; KU.uK1[2] = f.glow; KU.uK1[3] = f.gain * (1 + 0.25 * weather.rain);
    KU.uK2.set(c.haze); KU.uK3.set(c.sodium); KU.uK4.set(c.magenta); KU.uK5.set(c.cyan); KU.uK6.set(c.zenith);
    tmpDir.set(s.moonDir[0], s.moonDir[1], s.moonDir[2]).normalize();
    KU.uK7[0] = tmpDir.x; KU.uK7[1] = tmpDir.y; KU.uK7[2] = tmpDir.z; KU.uK7[3] = params.canalX;
    skyMat.uniforms.uS0.value.set(s.cover, s.speed, s.moonGap, s.gain);
    skyMat.uniforms.uS1.value.set(s.cloudBright, s.cloudHeight, 0, 0);
    hemi.color.setRGB(L.hemiSky[0], L.hemiSky[1], L.hemiSky[2]); hemi.groundColor.setRGB(L.hemiGround[0], L.hemiGround[1], L.hemiGround[2]); hemi.intensity = L.hemiIntensity;
    moon.color.setRGB(L.moonColor[0], L.moonColor[1], L.moonColor[2]); moon.intensity = L.moonIntensity;
    moon.position.copy(tmpDir).multiplyScalar(500);
  };
  syncUniforms(0);

  atmosphere = {
    params, weather, dome, hemi, moon, noise, KU,
    syncUniforms,
    update(dt, t) { syncUniforms(t); },
  };
  // runs even if the skyline itself fails to build
  app.add({ update: (dt, t) => atmosphere.update(dt, t) });
  return atmosphere;
}
export const getAtmosphere = () => atmosphere;
