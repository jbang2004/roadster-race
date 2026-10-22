// Weather: camera-relative drizzle streaks (world-fixed lattice that wraps around the camera, so speed reads
// correctly), lit by the nearest registered static lights and by the cars' headlights; ground splashes.
// Rain/splashes live on LAYER.LATE (R draws them after the car pass, depth-tested against world and cars) and use a
// blend that leaves the framebuffer alpha (= car mask) untouched.
import * as THREE from 'three';
import { KGLSL, kUniforms } from './atmosphere.js';
import { G, HEADLIGHT_GLSL } from '../core/globals.js';
import { LAYER } from '../core/layers.js';
import { lights } from '../core/lights.js';
import { mulberry32 } from './util.js';

// additive RGB, alpha channel preserved (alpha carries R's car mask in the car pass)
const LATE_ADD = { blending: THREE.CustomBlending, blendEquation: THREE.AddEquation, blendSrc: THREE.OneFactor, blendDst: THREE.OneFactor, blendSrcAlpha: THREE.ZeroFactor, blendDstAlpha: THREE.OneFactor };

const RAIN_VERT = /* glsl */`
attribute vec4 aSeed;
uniform vec3 uBox;
uniform vec3 uFall;
uniform vec3 uCamVel;
uniform float uShutter, uRain, uWidth, uAlpha, uTime, uMaxLen;
uniform vec4 uLP[8];
uniform vec3 uLC[8];
${HEADLIGHT_GLSL}
${KGLSL}
varying float vA;
varying vec3 vCol;
varying float vX;
void main() {
  vec3 base = aSeed.xyz * uBox + uFall * uTime;
  vec3 q = mod(base - cameraPosition, uBox);
  vec3 head = cameraPosition + q - uBox * 0.5;
  vec3 vrel = uFall - uCamVel;
  vec3 axis = -vrel * uShutter;
  float L = length(axis);
  axis *= min(1.0, uMaxLen / max(L, 1e-4));
  L = min(L, uMaxLen);
  vec3 tail = head + axis;
  vec3 toCam = cameraPosition - head;
  float dist = length(toCam);
  vec3 ad = axis / max(L, 1e-4);
  vec3 side = normalize(cross(ad, toCam / max(dist, 1e-3)));
  float px = dist * 0.0011;
  float w = max(uWidth, px);
  vec3 wp = mix(head, tail, position.y) + side * position.x * w;
  vec4 mvPosition = viewMatrix * vec4(wp, 1.0);
  gl_Position = projectionMatrix * mvPosition;
  vec3 e = abs(q / uBox * 2.0 - 1.0);
  float edge = 1.0 - smoothstep(0.75, 1.0, max(max(e.x, e.y), e.z));
  float near = smoothstep(0.35, 1.6, dist);
  float sub = min(1.0, uWidth / px);
  float on = step(aSeed.w, uRain);
  // light picked up by the drop: nearest static lights + car headlights
  vec3 lit = vec3(0.0);
  for (int i = 0; i < 8; i++) { vec3 d = uLP[i].xyz - head; lit += uLC[i] * uLP[i].w / (dot(d, d) + 6.0); }
  for (int i = 0; i < MAX_HEADLIGHTS; i++) {
    if (i >= uHeadCount) break;
    vec3 d = uHeadPos[i] - head; float d2 = max(dot(d, d), 1.0); vec3 l = d * inversesqrt(d2);
    float cone = smoothstep(cos(0.38), cos(0.2), dot(-l, uHeadDir[i]));
    lit += uHeadColor[i] * cone * pow(clamp(1.0 - d2 / 8100.0, 0.0, 1.0), 2.0) / d2;
  }
  vec3 ray = head - cameraPosition;
  vec3 amb = kFogColor(normalize(ray)) * 1.4 + vec3(0.018, 0.022, 0.032);
  vCol = (amb + lit * 0.012) * kFogT(ray);
  vA = uAlpha * on * edge * near * sub * (1.0 - 0.85 * position.y) * (0.6 + 0.8 * aSeed.w);
  vX = position.x * 2.0;
}`;
const RAIN_FRAG = /* glsl */`
varying float vA; varying vec3 vCol; varying float vX;
void main() {
  float a = vA * (1.0 - smoothstep(0.2, 1.0, abs(vX)));
  gl_FragColor = vec4(vCol * a, 1.0);
  #include <tonemapping_fragment>
  #include <colorspace_fragment>
}`;

const SPLASH_VERT = /* glsl */`
attribute vec4 aSeed;
uniform vec2 uBox;
uniform float uGroundY, uTime, uRain, uRate;
varying vec2 vQ; varying float vA;
${KGLSL}
float h11(float p) { p = fract(p * .1031); p *= p + 33.33; p *= p + p; return fract(p); }
void main() {
  float ph = uTime * uRate * (0.6 + 0.8 * aSeed.z) + aSeed.w * 37.0;
  float cyc = floor(ph), f = fract(ph);
  vec2 jit = vec2(h11(cyc * 1.7 + aSeed.x * 91.0), h11(cyc * 2.3 + aSeed.y * 57.0));
  vec2 xz = (aSeed.xy + jit * 0.07) * uBox;
  vec2 q = mod(xz - cameraPosition.xz, uBox) - uBox * 0.5;
  vec3 c = vec3(cameraPosition.x + q.x, uGroundY + 0.02, cameraPosition.z + q.y);
  float r = (0.02 + 0.16 * f) * (0.6 + 0.8 * aSeed.z);
  vec3 wp = c + vec3(position.x * r, 0.0, position.y * r);
  vec4 mvPosition = viewMatrix * vec4(wp, 1.0);
  gl_Position = projectionMatrix * mvPosition;
  vQ = position.xy * 2.0;
  float dist = length(q);
  vA = (1.0 - f) * (1.0 - f) * step(aSeed.w, uRain) * (1.0 - smoothstep(14.0, 20.0, dist)) * kFogT(wp - cameraPosition);
}`;
const SPLASH_FRAG = /* glsl */`
varying vec2 vQ; varying float vA;
void main() {
  float r = length(vQ);
  float ring = smoothstep(0.55, 0.85, r) * (1.0 - smoothstep(0.85, 1.0, r));
  float a = ring * vA;
  gl_FragColor = vec4(vec3(0.45, 0.55, 0.75) * a * 0.35, 1.0);
  #include <tonemapping_fragment>
  #include <colorspace_fragment>
}`;

function makeSeedGeometry(n, quadPts, seed, withW = true) {
  const g = new THREE.InstancedBufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(quadPts, 3));
  g.setIndex([0, 1, 2, 0, 2, 3]);
  const rng = mulberry32(seed), a = new Float32Array(n * 4);
  for (let i = 0; i < n; i++) { a[i * 4] = rng(); a[i * 4 + 1] = rng(); a[i * 4 + 2] = rng(); a[i * 4 + 3] = (i + 0.5) / n; }
  g.setAttribute('aSeed', new THREE.InstancedBufferAttribute(a, 4));
  g.instanceCount = n;
  return g;
}

export function createWeather(app, track, atmo) {
  const group = new THREE.Group(); group.name = 'K-weather';
  const lpArr = Array.from({ length: 8 }, () => new THREE.Vector4()), lcArr = Array.from({ length: 8 }, () => new THREE.Vector3());
  const camVel = new THREE.Vector3(), prevCam = new THREE.Vector3(), camInit = { v: false };
  const shared = () => ({
    uTime: { value: 0 }, uRain: { value: 0.3 }, uLP: { value: lpArr }, uLC: { value: lcArr }, uCamVel: { value: camVel },
    uHeadCount: G.uHeadCount, uHeadPos: G.uHeadPos, uHeadDir: G.uHeadDir, uHeadColor: G.uHeadColor,
    ...kUniforms(),
  });
  const layers = [];
  const addRain = (n, box, width, alpha, shutter, maxLen, seed, name) => {
    const g = makeSeedGeometry(n, [-0.5, 0, 0, 0.5, 0, 0, 0.5, 1, 0, -0.5, 1, 0], seed);
    const u = shared();
    Object.assign(u, { uBox: { value: new THREE.Vector3(...box) }, uFall: { value: new THREE.Vector3(0.6, -9.0, 0.3) }, uShutter: { value: shutter },
      uWidth: { value: width }, uAlpha: { value: alpha }, uMaxLen: { value: maxLen } });
    const m = new THREE.ShaderMaterial({ vertexShader: RAIN_VERT, fragmentShader: RAIN_FRAG, uniforms: u, transparent: true, depthWrite: false, ...LATE_ADD, fog: false });
    const mesh = new THREE.Mesh(g, m); mesh.frustumCulled = false; mesh.name = name; mesh.layers.set(LAYER.LATE); mesh.renderOrder = 20;
    group.add(mesh); layers.push(m); return mesh;
  };
  addRain(5200, [30, 20, 30], 0.010, 0.55, 1 / 45, 3.5, 3, 'K-rain-near');
  addRain(4200, [160, 60, 160], 0.020, 0.30, 1 / 45, 6.0, 5, 'K-rain-far');

  // ground splashes
  const sg = makeSeedGeometry(1400, [-0.5, -0.5, 0, 0.5, -0.5, 0, 0.5, 0.5, 0, -0.5, 0.5, 0], 9);
  const su = shared(); Object.assign(su, { uBox: { value: new THREE.Vector2(40, 40) }, uGroundY: { value: 0 }, uRate: { value: 2.4 } });
  const splashMat = new THREE.ShaderMaterial({ vertexShader: SPLASH_VERT, fragmentShader: SPLASH_FRAG, uniforms: su, transparent: true, depthWrite: false, ...LATE_ADD, fog: false, side: THREE.DoubleSide });
  const splash = new THREE.Mesh(sg, splashMat); splash.frustumCulled = false; splash.name = 'K-splash'; splash.layers.set(LAYER.LATE); splash.renderOrder = 19;
  group.add(splash); layers.push(splashMat);

  const proj = {}; let groundY = 0, lightTimer = 0;
  const cam = app.camera.position;
  return {
    group, enabled: true,
    update(dt, t) {
      if (!camInit.v) { prevCam.copy(cam); camInit.v = true; }
      if (dt > 1e-5) { const k = 1 - Math.exp(-dt * 12); camVel.x += ((cam.x - prevCam.x) / dt - camVel.x) * k; camVel.y += ((cam.y - prevCam.y) / dt - camVel.y) * k; camVel.z += ((cam.z - prevCam.z) / dt - camVel.z) * k; }
      if (camVel.lengthSq() > 160000) camVel.setLength(400);   // teleports
      prevCam.copy(cam);
      const rain = atmo.weather.rain;
      for (const m of layers) { m.uniforms.uTime.value = t; m.uniforms.uRain.value = rain; }
      group.visible = rain > 0.01;
      // static lights near the camera for rain pickup (10 Hz, few allocations)
      lightTimer -= dt;
      if (lightTimer <= 0 && group.visible) {
        lightTimer = 0.1;
        const near = lights.nearest(cam, 8, null, 70);
        for (let i = 0; i < 8; i++) {
          const l = near[i];
          if (l) { lpArr[i].set(l.pos.x, l.pos.y, l.pos.z, l.intensity); lcArr[i].set(l.color.r, l.color.g, l.color.b); } else lpArr[i].set(0, 0, 0, 0);
        }
        track.project(cam, -1, proj); groundY += (Math.min(proj.y, cam.y - 0.8) - groundY) * 0.5;
        splashMat.uniforms.uGroundY.value = groundY;
      }
    },
  };
}
