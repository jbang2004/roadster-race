// R's test scene: the whole real circuit as a small wet-night test city (road with the reference wet-road shader that calls
// roadReflection(), parapets, lamps registered in `lights`, neon, towers with lit windows, a tunnel, trench walls, sky)
// and the wedge car (+2 AI copies) driving along the track under the render pipeline.
//   ?scene=render[&s=<metres>][&v=<m/s>][&mirror][&q=high|medium|low][&aa=fxaa][&cam=back,up,ahead,side][&nocars]
//   hooks: __rt.place(s) · __rt.setSpeed(v) · __rt.cam({back,up,ahead,side,fov,lag}) · __rt.mirror(bool) · __rt.freeze(bool)
//          __render (pipeline params), __app, __track, __cars
import * as THREE from 'three';
import { getTrack, KIND } from '../track/track.js';
import { loadGLTF, phTextureSet } from '../core/assets.js';
import { lights } from '../core/lights.js';
import { LAYER, setLayer, lightEverything } from '../core/layers.js';
import { RF, REFLECT_GLSL } from '../core/reflect.js';
import { G, HEADLIGHT_GLSL } from '../core/globals.js';
import { createRenderer } from '../render/index.js';

function rng(seed) { let a = seed >>> 0; return () => { a = (a + 0x6D2B79F5) >>> 0; let t = a; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }

const NOISE_GLSL = /* glsl */`
float h21(vec2 p) { vec3 p3 = fract(vec3(p.xyx) * 0.1031); p3 += dot(p3, p3.yzx + 33.33); return fract((p3.x + p3.y) * p3.z); }
float vn(vec2 p) { vec2 i = floor(p), f = fract(p); vec2 u = f * f * (3.0 - 2.0 * f);
  return mix(mix(h21(i), h21(i + vec2(1, 0)), u.x), mix(h21(i + vec2(0, 1)), h21(i + vec2(1, 1)), u.x), u.y); }
float fbm(vec2 p) { float s = 0.0, a = 0.5; for (int i = 0; i < 4; i++) { s += a * vn(p); p = mat2(1.6, 1.2, -1.2, 1.6) * p + 3.7; a *= 0.5; } return s / 0.9375; }
`;

// ---------------------------------------------------------------------------------------------------------------------
// the reference wet-road shader (what W's road must do with RF / REFLECT_GLSL)
function makeRoadMaterial(tex) {
  const uniforms = {
    ...THREE.UniformsUtils.clone(THREE.UniformsLib.fog),
    tDiff: { value: tex.map }, tNor: { value: tex.normalMap }, tArm: { value: tex.armMap },
    tReflect: RF.tReflect, uReflectMatrix: RF.uReflectMatrix, uReflectOn: RF.uReflectOn, uReflectLod: RF.uReflectLod,
    uHeadCount: G.uHeadCount, uHeadPos: G.uHeadPos, uHeadDir: G.uHeadDir, uHeadColor: G.uHeadColor,
    uWet: G.uWet, uTime: G.uTime,
    uLampPos: { value: Array.from({ length: 16 }, () => new THREE.Vector3()) },
    uLampCol: { value: Array.from({ length: 16 }, () => new THREE.Vector3()) },
    uLampRange: { value: new Array(16).fill(1) },
    uMirror: { value: 0 }, uRough: { value: -1 }, uStreak: { value: -1 },
  };
  return new THREE.ShaderMaterial({
    uniforms, fog: true,
    vertexShader: /* glsl */`
      attribute vec3 aRoad;           // lateral offset u, arc length s, half width
      varying vec3 vWP, vN, vRoad;
      #include <fog_pars_vertex>
      void main() {
        vec4 wp = modelMatrix * vec4(position, 1.0);
        vWP = wp.xyz; vN = normalize(mat3(modelMatrix) * normal); vRoad = aRoad;
        vec4 mvPosition = viewMatrix * wp;
        gl_Position = projectionMatrix * mvPosition;
        #include <fog_vertex>
      }`,
    fragmentShader: /* glsl */`
      uniform sampler2D tDiff, tNor, tArm;
      uniform vec3 uLampPos[16]; uniform vec3 uLampCol[16]; uniform float uLampRange[16];
      uniform float uWet, uMirror, uTime, uRough, uStreak;
      varying vec3 vWP, vN, vRoad;
      ${NOISE_GLSL}
      ${HEADLIGHT_GLSL}
      ${REFLECT_GLSL}
      #include <fog_pars_fragment>
      void main() {
        vec3 N0 = normalize(vN);
        vec3 V = normalize(cameraPosition - vWP);
        float dist = length(cameraPosition - vWP);
        vec2 w1 = vWP.xz * 0.30, w2 = vWP.xz * 0.047 + 0.31;
        // fade the fine normal detail with distance (anti-shimmer)
        float detail = 1.0 - smoothstep(25.0, 90.0, dist);
        vec3 n1 = texture(tNor, w1).xyz * 2.0 - 1.0, n2 = texture(tNor, w2).xyz * 2.0 - 1.0;
        vec3 T = normalize(cross(N0, vec3(0.0, 0.0, 1.0))); vec3 B = cross(N0, T);
        vec2 nxy = (n1.xy * 0.9 * detail + n2.xy * 0.6);
        vec3 N = normalize(N0 + (T * nxy.x + B * nxy.y) * 0.55);
        vec3 arm = texture(tArm, w1).rgb;
        vec3 albedo = texture(tDiff, w1).rgb * mix(texture(tDiff, w2).rgb, vec3(1.0), 0.4) * 0.16;
        // puddles and wheel tracks
        float pud = smoothstep(0.60, 0.68, fbm(vWP.xz * 0.045) * 0.6 + fbm(vWP.xz * 0.21) * 0.4);
        float u = vRoad.x, hw = vRoad.z;
        float lanes = max(floor(hw * 2.0 / 3.7 + 0.5), 1.0);
        float q = fract(u / (hw * 2.0 / lanes) + 0.5) - 0.5;
        float track = exp(-pow((abs(q) - 0.2) / 0.075, 2.0));
        float rough = mix(0.45 + 0.3 * arm.g, 0.05, clamp(pud + track * 0.6, 0.0, 1.0));
        // lane paint
        float au = abs(u);
        float edgeL = smoothstep(0.12, 0.08, abs(au - (hw - 0.45)));
        float dash = step(0.35, fract(vRoad.y / 12.0)) * smoothstep(0.1, 0.07, abs(u)) * step(0.5, lanes);
        float lanesDash = 0.0;
        for (int k = 1; k < 4; k++) { float lu = u - (float(k) - lanes * 0.5) * (hw * 2.0 / lanes); lanesDash = max(lanesDash, step(0.35, fract(vRoad.y / 9.0)) * smoothstep(0.1, 0.07, abs(lu)) * step(float(k), lanes - 0.5)); }
        float paint = clamp(edgeL + max(dash, lanesDash), 0.0, 1.0) * (0.55 + 0.45 * vn(vWP.xz * 3.1)) * (1.0 - pud * 0.6);
        albedo = mix(albedo, vec3(0.5, 0.5, 0.46), paint);
        rough = mix(rough, 0.7, paint);
        if (uRough >= 0.0) rough = uRough;
        // light
        vec3 diff = vec3(0.05, 0.07, 0.11);                                  // sky ambient
        for (int i = 0; i < 16; i++) {
          vec3 L = uLampPos[i] - vWP; float d2 = max(dot(L, L), 0.5); vec3 l = L * inversesqrt(d2);
          float q2 = d2 / (uLampRange[i] * uLampRange[i]); float win = pow(clamp(1.0 - q2 * q2, 0.0, 1.0), 2.0);
          diff += uLampCol[i] * win * max(dot(N0, l), 0.0) / d2;
        }
        diff += headlightIrradiance(vWP, N);
        vec3 col = albedo * diff;
        // wet reflection
        float ndv = clamp(dot(N, V), 0.0, 1.0);
        float F0 = 0.04;
        float F = F0 + (max(1.0 - rough, F0) - F0) * pow(1.0 - ndv, 5.0);
        float wet = clamp(uWet, 0.0, 1.0);
        float ro = mix(rough, 0.0, uMirror);
        vec3 refl = roadReflection(vWP, N, ro, uStreak >= 0.0 ? uStreak : mix(0.95 - 0.8 * pud, 0.0, uMirror));
        col += refl * F * wet * (1.0 - paint * 0.85) * mix(1.0, 3.0, uMirror);
        gl_FragColor = vec4(col, 1.0);
        #include <fog_fragment>
      }`,
  });
}

// ---------------------------------------------------------------------------------------------------------------------
class Batcher {
  // collects instances per (kind, chunk) and builds InstancedMeshes
  constructor() { this.sets = new Map(); }
  add(kind, chunk, matrix, color) {
    const key = kind + '|' + chunk;
    let s = this.sets.get(key); if (!s) this.sets.set(key, s = { kind, mats: [], cols: [] });
    s.mats.push(matrix.clone()); s.cols.push(color ? color.clone() : null);
  }
  build(parent, spec) {
    let calls = 0;
    for (const s of this.sets.values()) {
      const sp = spec[s.kind]; if (!sp) continue;
      const im = new THREE.InstancedMesh(sp.geo, sp.mat, s.mats.length);
      s.mats.forEach((m, i) => { im.setMatrixAt(i, m); if (s.cols[i]) im.setColorAt(i, s.cols[i]); });
      im.instanceMatrix.needsUpdate = true; if (im.instanceColor) im.instanceColor.needsUpdate = true;
      im.computeBoundingSphere();
      im.matrixAutoUpdate = false;
      if (sp.layer !== undefined) im.layers.set(sp.layer);
      parent.add(im); calls++;
    }
    return calls;
  }
}

function ribbon(T, profile, { side = 1, filter = null, y0 = 0, step = 1 } = {}) {
  // profile: [[lateral from road edge outward (m), height (m)], ...] polyline; produces flat-shaded quads along s
  const pos = [], idx = [], nor = [];
  const N = T.N;
  const segs = profile.length - 1;
  let base = 0;
  const v = new THREE.Vector3();
  let run = [];
  const flush = () => {
    if (run.length < 2) { run = []; return; }
    for (let k = 0; k < segs; k++) {
      const b0 = base;
      for (const i of run) {
        for (const pidx of [k, k + 1]) {
          const [lat, hh] = profile[pidx];
          const hw = T.hw[i] + 0.5;
          const o = side * (hw + lat);
          pos.push(T.px[i] + T.rx[i] * o + T.ux[i] * 0, T.py[i] + T.ry[i] * o + hh + y0, T.pz[i] + T.rz[i] * o);
          nor.push(0, 1, 0);
        }
      }
      for (let j = 0; j < run.length - 1; j++) {
        const a = b0 + j * 2;
        idx.push(a, a + 1, a + 2, a + 1, a + 3, a + 2);
      }
      base += run.length * 2;
    }
    run = [];
  };
  for (let i = 0; i <= N; i += step) {
    const k = i % N;
    if (filter && !filter(k)) { flush(); continue; }
    run.push(k);
  }
  flush();
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  g.setIndex(idx);
  g.computeVertexNormals();
  return g;
}

export default async function (app) {
  const T = getTrack();
  window.__track = T;
  const scene = app.scene;
  const R = rng(1234);
  const q = app.q;

  scene.background = new THREE.Color(0x02030a);
  scene.fog = new THREE.FogExp2(0x0b0a1c, 0.0028);

  // ---- global lights (reach every pass)
  const hemi = lightEverything(new THREE.HemisphereLight(0x4d6aa8, 0x1a1420, 0.42)); scene.add(hemi);
  const moon = lightEverything(new THREE.DirectionalLight(0x7a9cff, 0.12)); moon.position.set(-300, 500, 200); scene.add(moon);

  const render = await createRenderer(app, T);
  window.__rt = {};

  // ---- sky
  const sky = new THREE.Mesh(new THREE.SphereGeometry(5200, 32, 20), new THREE.ShaderMaterial({
    side: THREE.BackSide, depthWrite: false, fog: false,
    uniforms: { uTime: G.uTime },
    vertexShader: 'varying vec3 vDir; void main(){ vDir = position; gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0); }',
    fragmentShader: `varying vec3 vDir; uniform float uTime; ${NOISE_GLSL}
      void main(){ vec3 d = normalize(vDir); float h = d.y;
        vec3 hor = vec3(0.075, 0.034, 0.062), mid = vec3(0.02, 0.018, 0.04), zen = vec3(0.003, 0.005, 0.014);
        vec3 c = mix(hor, mid, smoothstep(0.0, 0.25, h)); c = mix(c, zen, smoothstep(0.2, 0.9, h));
        vec2 p = d.xz / (abs(h) + 0.25) * 1.3 + vec2(uTime * 0.004, 0.0);
        float cl = smoothstep(0.35, 0.8, fbm(p * 1.6));
        vec3 glow = mix(vec3(0.5, 0.18, 0.08), vec3(0.45, 0.08, 0.35), fbm(d.xz * 3.0 + 4.0));
        c += cl * glow * 0.09 * (1.0 - smoothstep(0.05, 0.55, h)) + cl * vec3(0.02, 0.018, 0.04);
        if (h < 0.0) c = hor * 0.6;
        gl_FragColor = vec4(c, 1.0); }`,
  }));
  sky.renderOrder = -1000; sky.frustumCulled = false; scene.add(sky);

  // ---- ground
  const B = T.layout.bounds;
  const ground = new THREE.Mesh(new THREE.PlaneGeometry(B.x1 - B.x0 + 2000, B.z1 - B.z0 + 2000),
    new THREE.MeshStandardMaterial({ color: 0x0c0e12, roughness: 0.95, metalness: 0 }));
  ground.rotation.x = -Math.PI / 2; ground.position.set((B.x0 + B.x1) / 2, -0.06, (B.z0 + B.z1) / 2); scene.add(ground);

  // ---- road (MAIN_ONLY: never in the reflection)
  const tex = await phTextureSet('asphalt_track');
  const roadMat = makeRoadMaterial(tex);
  {
    const N = T.N, pos = [], nor = [], aR = [], idx = [];
    for (let i = 0; i <= N; i++) {
      const k = i % N, hw = T.hw[k] + 0.5;
      for (const side of [-1, 1]) {
        pos.push(T.px[k] + T.rx[k] * hw * side, T.py[k] + T.ry[k] * hw * side, T.pz[k] + T.rz[k] * hw * side);
        nor.push(T.ux[k], T.uy[k], T.uz[k]);
        aR.push(side * hw, i, T.hw[k]);
      }
      if (i < N) { const a = i * 2; idx.push(a, a + 1, a + 2, a + 1, a + 3, a + 2); }
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
    g.setAttribute('normal', new THREE.Float32BufferAttribute(nor, 3));
    g.setAttribute('aRoad', new THREE.Float32BufferAttribute(aR, 3));
    g.setIndex(idx);
    const road = new THREE.Mesh(g, roadMat); road.layers.set(LAYER.MAIN_ONLY); road.frustumCulled = false; scene.add(road);
  }

  // ---- parapets (+ glowing rail strips), trench walls, tunnel shell
  const concrete = new THREE.MeshStandardMaterial({ color: 0x3b3e44, roughness: 0.85, side: THREE.DoubleSide });
  const notTunnel = (i) => T.kind[i] !== KIND.TUNNEL && T.kind[i] !== KIND.TRENCH;
  for (const side of [-1, 1]) {
    scene.add(new THREE.Mesh(ribbon(T, [[0, 0], [0, 0.95], [0.4, 0.95], [0.4, 0]], { side, filter: notTunnel }), concrete));
    const strip = new THREE.Mesh(ribbon(T, [[-0.02, 0.55], [-0.02, 0.68]], { side, filter: (i) => notTunnel(i) }),
      new THREE.MeshBasicMaterial({ color: (side < 0 ? new THREE.Color(0xff2a9d) : new THREE.Color(0x19e6ff)).multiplyScalar(2.2), side: THREE.DoubleSide }));
    scene.add(strip);
    scene.add(new THREE.Mesh(ribbon(T, [[0.0, 0], [0.0, 6.5], [0.5, 6.5]], { side, filter: (i) => T.kind[i] === KIND.TRENCH }),
      new THREE.MeshStandardMaterial({ color: 0x2b2e33, roughness: 0.9, side: THREE.DoubleSide })));
  }
  const tunnelF = (i) => T.kind[i] === KIND.TUNNEL;
  const tunnelShell = new THREE.Mesh(
    ribbon(T, [[0.0, 0], [0.0, 5.0], [-0.9, 5.9], [-2.4, 6.2]], { side: 1, filter: tunnelF }), // right half
    new THREE.MeshStandardMaterial({ color: 0x4a5560, roughness: 0.55, metalness: 0.1, side: THREE.DoubleSide }));
  scene.add(tunnelShell);
  const tunnelShellL = new THREE.Mesh(
    ribbon(T, [[0.0, 0], [0.0, 5.0], [-0.9, 5.9], [-2.4, 6.2]], { side: -1, filter: tunnelF }),
    tunnelShell.material);
  scene.add(tunnelShellL);
  scene.add(new THREE.Mesh(ceilingStrip(T, tunnelF, 6.2, 5.0), new THREE.MeshStandardMaterial({ color: 0x3a434c, roughness: 0.6, side: THREE.DoubleSide })));
  const led = new THREE.MeshBasicMaterial({ color: new THREE.Color(0xcfe8ff).multiplyScalar(7), side: THREE.DoubleSide });
  scene.add(new THREE.Mesh(ceilingLine(T, tunnelF, 6.17, -3.0), led));
  scene.add(new THREE.Mesh(ceilingLine(T, tunnelF, 6.17, 3.0), led));
  scene.add(new THREE.Mesh(ceilingLine(T, tunnelF, 3.4, -6.4, true), new THREE.MeshBasicMaterial({ color: new THREE.Color(0x35f0c0).multiplyScalar(2.2), side: THREE.DoubleSide })));

  // ---- batched props: lamps, neon, towers
  const batch = new Batcher();
  const m4 = new THREE.Matrix4(), qq = new THREE.Quaternion(), sc = new THREE.Vector3(), pp = new THREE.Vector3(), up = new THREE.Vector3(0, 1, 0);
  const chunkOf = (s) => Math.floor(s / 260);
  const zoneName = (i) => T.zoneNames[T.zone[i]];
  const lampCol = (i) => {
    const z = zoneName(i);
    if (z === 'docks' || z === 'expressway' || z === 'descent' || z === 'ramp') return new THREE.Color(1.0, 0.62, 0.28);   // sodium
    if (z === 'market') return new THREE.Color(1.0, 0.78, 0.5);
    return new THREE.Color(0.78, 0.9, 1.0);                                                                                  // cool LED
  };
  let nLamps = 0;
  for (let s = 12; s < T.length; s += 36) {
    const i = Math.floor(s) % T.N;
    if (T.kind[i] === KIND.TUNNEL) continue;
    const side = (Math.floor(s / 36) % 2) ? 1 : -1;
    const hw = T.hw[i] + 0.5 + (T.kind[i] === KIND.ELEVATED ? 0.2 : 2.6);
    const base = new THREE.Vector3(T.px[i] + T.rx[i] * hw * side, T.py[i] + T.ry[i] * hw * side, T.pz[i] + T.rz[i] * hw * side);
    const tall = T.kind[i] === KIND.ELEVATED ? 9.5 : 8.5;
    // pole
    m4.compose(pp.copy(base).setY(base.y + tall / 2), qq.identity(), sc.set(0.16, tall, 0.16)); batch.add('pole', chunkOf(s), m4);
    // arm towards the road + head
    const arm = new THREE.Vector3(-T.rx[i] * side, 0, -T.rz[i] * side).normalize();
    const headPos = base.clone().addScaledVector(arm, 1.9).setY(base.y + tall);
    qq.setFromUnitVectors(new THREE.Vector3(1, 0, 0), arm);
    m4.compose(pp.copy(base).addScaledVector(arm, 0.95).setY(base.y + tall), qq, sc.set(1.9, 0.12, 0.12)); batch.add('pole', chunkOf(s), m4);
    const col = lampCol(i);
    m4.compose(headPos.clone().setY(headPos.y - 0.12), qq, sc.set(0.95, 0.1, 0.36)); batch.add('head', chunkOf(s), m4, col.clone().multiplyScalar(26));
    lights.add({ pos: headPos.clone().setY(headPos.y - 0.3), color: col, intensity: 420, range: 32, kind: 'street', dir: [0, -1, 0], angle: 1.15, penumbra: 0.7 });
    nLamps++;
  }
  // tunnel lights: a point every 6 m
  {
    let nT = 0;
    for (let s = 0; s < T.length; s += 6) {
      const i = Math.floor(s) % T.N; if (T.kind[i] !== KIND.TUNNEL) continue;
      lights.add({ pos: [T.px[i] + T.ux[i] * 5.6, T.py[i] + T.uy[i] * 5.6, T.pz[i] + T.uz[i] * 5.6], color: new THREE.Color(0.78, 0.9, 1.0), intensity: 120, range: 14, kind: 'tunnel' });
      nT++;
    }
  }
  // towers + neon signs
  const palette = [0x19e6ff, 0xff2a9d, 0x8a5cff, 0xffa31a, 0x35f0c0, 0xff4d6d].map(c => new THREE.Color(c));
  let nTowers = 0, nNeon = 0;
  const field = {};
  for (let s = 0; s < T.length; s += 15) {
    const i = Math.floor(s) % T.N;
    for (const side of [-1, 1]) {
      const off = T.hw[i] + 0.5 + 9 + R() * 26;
      const x = T.px[i] + T.rx[i] * off * side, z = T.pz[i] + T.rz[i] * off * side;
      const w = 12 + R() * 20, d = 12 + R() * 20;
      T.field(x, z, field);
      if (field.all < w * 0.5 + 6 || field.ground < w * 0.5 + 6) continue;
      const hgt = (T.kind[i] === KIND.ELEVATED ? 30 : 18) + Math.pow(R(), 1.8) * 120;
      const yaw = Math.atan2(T.tx[i], -T.tz[i]);
      qq.setFromAxisAngle(up, -yaw);
      const gy = -0.06;
      m4.compose(pp.set(x, gy + hgt / 2, z), qq, sc.set(w, hgt, d)); batch.add('tower', chunkOf(s), m4);
      nTowers++;
      if (R() < 0.7) {
        // sign on the facade that faces the road
        const face = new THREE.Vector3(-T.rx[i] * side, 0, -T.rz[i] * side).normalize();
        const sw = 3 + R() * 7, sh = 1 + R() * 5, y = 5 + R() * Math.min(hgt - 6, 30);
        const sp = new THREE.Vector3(x, gy + y, z).addScaledVector(face, d * 0.5 + 0.2);
        const c = palette[Math.floor(R() * palette.length)].clone();
        qq.setFromUnitVectors(new THREE.Vector3(0, 0, 1), face);
        m4.compose(sp, qq, sc.set(sw, sh, 0.25)); batch.add('neon', chunkOf(s), m4, c.clone().multiplyScalar(5 + R() * 9));
        if (R() < 0.55) lights.add({ pos: sp.clone().addScaledVector(face, 1.2), color: c, intensity: 60 + R() * 90, range: 14, kind: 'neon' });
        nNeon++;
      }
    }
  }
  const towerMat = makeTowerMaterial();
  const calls = batch.build(scene, {
    pole: { geo: new THREE.BoxGeometry(1, 1, 1), mat: new THREE.MeshStandardMaterial({ color: 0x25272c, roughness: 0.6, metalness: 0.5 }) },
    head: { geo: new THREE.BoxGeometry(1, 1, 1), mat: new THREE.MeshBasicMaterial({ color: 0xffffff }) },
    neon: { geo: new THREE.BoxGeometry(1, 1, 1), mat: new THREE.MeshBasicMaterial({ color: 0xffffff }) },
    tower: { geo: new THREE.BoxGeometry(1, 1, 1), mat: towerMat },
  });

  // ---- the cars
  const gltf = await loadGLTF('assets/car/wedge_car.glb');
  const cars = [];
  const mkCar = (paint) => {
    const root = new THREE.Group(), wrap = new THREE.Group();
    const m = gltf.scene.clone(true);
    m.traverse(o => { if (o.isMesh) { o.material = o.material.clone(); o.material.envMap = render.probe.texture; o.material.envMapIntensity = 1.0; if (paint && o.material.name === 'Paint_LiquidSilver') o.material.color.set(paint); } });
    wrap.rotation.y = -Math.PI / 2; wrap.add(m); root.add(wrap);
    setLayer(root, LAYER.CARS);
    const heads = [];
    for (const sx of [-0.7, 0.7]) {
      const sp = lightEverything(new THREE.SpotLight(0xdfeaff, 6000, 80, 0.44, 0.6, 2));
      sp.position.set(sx, 0.62, -2.2); sp.target.position.set(sx * 0.6, 0.15, -30);
      root.add(sp); root.add(sp.target); heads.push(sp);
    }
    scene.add(root);
    return { root, heads, wheels: ['Wheel_FL', 'Wheel_FR', 'Wheel_RL', 'Wheel_RR'].map(n => m.getObjectByName(n)) };
  };
  const withCars = !q.has('nocars');
  if (withCars) {
    cars.push({ ...mkCar(null), s: +(q.get('s') ?? 250), u: -1.8, v: +(q.get('v') ?? 0), isPlayer: true });
    cars.push({ ...mkCar(0xc01856), s: +(q.get('s') ?? 250) + 38, u: 2.8, v: 0, ai: true });
    cars.push({ ...mkCar(0x1f6fe0), s: +(q.get('s') ?? 250) + 16, u: 3.4, v: 0, ai: true });
  }
  const player = cars[0];
  if (player) render.setFocus(player.root);
  window.__cars = cars;

  // ---- LATE-layer test: translucent 'spray' sheets that must draw after the cars (in front of / behind them correctly)
  const sprayMat = new THREE.MeshBasicMaterial({ color: 0xbfd8ff, transparent: true, opacity: 0.3, depthWrite: false, side: THREE.DoubleSide });
  const spray = new THREE.Group();
  if (player) {
    for (const [x, y, z, w] of [[0, 0.8, 2.9, 2.2], [-1.6, 0.6, 0.5, 1.2], [1.6, 0.6, -1.4, 1.2]]) {
      const q = new THREE.Mesh(new THREE.PlaneGeometry(w, 1.4), sprayMat); q.position.set(x, y, z); spray.add(q);
    }
    spray.traverse(o => o.layers.set(4)); spray.visible = false; player.root.add(spray);
  }
  window.__spray = spray;

  // ---- driving + chase camera
  const camCfg = { back: 8.2, up: 2.35, ahead: 12, side: 0, fov: 62, lag: 0.0 };
  if (q.get('cam')) { const [b, u, a, s] = q.get('cam').split(',').map(Number); Object.assign(camCfg, { back: b, up: u, ahead: a, side: s ?? 0 }); }
  const fr = {}, tmpQ = new THREE.Quaternion();
  const camPos = new THREE.Vector3(), camTgt = new THREE.Vector3(), camVel = new THREE.Vector3();
  let frozen = false, camInit = false;
  const place = (c) => {
    T.frameAt(c.s, fr);
    c.root.position.copy(fr.pos).addScaledVector(fr.r, c.u);
    T.quatAt(c.s, tmpQ); c.root.quaternion.copy(tmpQ);
  };
  const lampQuery = new THREE.Vector3();
  const updateHeads = () => {
    let n = 0;
    for (const c of cars) {
      for (const sp of c.heads) {
        if (n >= 8) break;
        sp.getWorldPosition(G.uHeadPos.value[n]);
        G.uHeadDir.value[n].set(0, 0.0, -1).transformDirection(c.root.matrixWorld);
        G.uHeadColor.value[n].set(0.87, 0.92, 1.0).multiplyScalar(6000);
        n++;
      }
    }
    G.uHeadCount.value = n;
  };
  const updateLampUniforms = (p) => {
    const L = lights.nearest(p, 16, (l) => l.kind === 'street' || l.kind === 'tunnel' || l.kind === 'neon', 70);
    const U = roadMat.uniforms;
    for (let i = 0; i < 16; i++) {
      const l = L[i];
      if (l) { U.uLampPos.value[i].copy(l.pos); U.uLampCol.value[i].set(l.color.r, l.color.g, l.color.b).multiplyScalar(l.intensity); U.uLampRange.value[i] = l.range; }
      else { U.uLampPos.value[i].set(0, -9999, 0); U.uLampCol.value[i].set(0, 0, 0); U.uLampRange.value[i] = 1; }
    }
  };
  const sys = {
    update(dt) {
      if (!frozen) for (const c of cars) {
        if (c.ai) c.v = c.fixedV ?? player.v * (c.u > 3 ? 0.93 : 1.08);
        c.s = T.wrapS(c.s + c.v * dt);
      }
      for (const c of cars) {
        place(c);
        const sp = c.v * dt / 0.39;
        for (const w of c.wheels) if (w) w.rotation.z -= sp;      // wheel nodes spin about their local axle
      }
      if (player) {
        render.fx.speed(player.v / 85);
        updateHeads(); updateLampUniforms(player.root.position);
        sky.position.copy(app.camera.position);
      }
    },
    late(dt) {
      sky.position.copy(app.camera.position);
      if (!player || app.viewLocked) return;
      const p = player.root;
      T.frameAt(player.s - camCfg.back, fr);
      const want = fr.pos.clone().addScaledVector(fr.r, player.u + camCfg.side).addScaledVector(fr.u, camCfg.up);
      T.frameAt(player.s + camCfg.ahead, fr);
      const tgt = fr.pos.clone().addScaledVector(fr.r, player.u * 0.6).addScaledVector(fr.u, 1.0);
      if (!camInit || camCfg.lag <= 0) { camPos.copy(want); camTgt.copy(tgt); camInit = true; }
      else { const k = 1 - Math.exp(-dt / camCfg.lag); camPos.lerp(want, k); camTgt.lerp(tgt, k); }
      app.camera.position.copy(camPos); app.camera.lookAt(camTgt);
      if (Math.abs(app.camera.fov - camCfg.fov) > 0.01) { app.camera.fov = camCfg.fov; app.camera.updateProjectionMatrix(); }
    },
  };
  app.add(sys);
  cars.forEach(place);
  scene.updateMatrixWorld(true);
  if (player) { sys.update(0); sys.late(0); }

  Object.assign(window.__rt, {
    place(s, v) { if (player) { const d = s - player.s; for (const c of cars) c.s = T.wrapS(c.s + d); if (v !== undefined) player.v = v; camInit = false; } },
    setSpeed(v) { if (player) player.v = v; },
    cam(o) { Object.assign(camCfg, o); camInit = false; },
    mirror(b) { roadMat.uniforms.uMirror.value = b ? 1 : 0; },
    rough(r, st = -1) { roadMat.uniforms.uRough.value = r; roadMat.uniforms.uStreak.value = st; },
    freeze(b) { frozen = b; },
    spray(b) { spray.visible = b; },
    roadMat, cars, camCfg, calls,
  });
  if (q.has('mirror')) window.__rt.mirror(true);
  if (player) player.v = +(q.get('v') ?? 0);
  console.log(`[render-scene] ${nLamps} lamps, ${nTowers} towers, ${nNeon} neon, ${lights.list.length} registered lights, ${calls} batched draws`);
  await app.ready();
}

// ceiling pieces for the tunnel -----------------------------------------------------------------------------------------
function ceilingStrip(T, filter, height, halfWidth) {
  return ceilingLine(T, filter, height, 0, false, halfWidth);
}
function ceilingLine(T, filter, height, lateral, wall = false, halfWidth = 0.17) {
  const pos = [], idx = []; let base = 0, run = [];
  const flush = () => {
    if (run.length > 1) {
      for (const i of run) for (const sgn of [-1, 1]) {
        const o = lateral + sgn * halfWidth;
        if (!wall) pos.push(T.px[i] + T.rx[i] * o, T.py[i] + T.ry[i] * o + height, T.pz[i] + T.rz[i] * o);
        else { const side = Math.sign(lateral); pos.push(T.px[i] + T.rx[i] * (T.hw[i] + 0.45) * side, T.py[i] + T.ry[i] * (T.hw[i] + 0.45) * side + height + sgn * 0.12, T.pz[i] + T.rz[i] * (T.hw[i] + 0.45) * side); }
      }
      for (let j = 0; j < run.length - 1; j++) { const a = base + j * 2; idx.push(a, a + 1, a + 2, a + 1, a + 3, a + 2); }
      base += run.length * 2;
    }
    run = [];
  };
  for (let i = 0; i <= T.N; i++) { const k = i % T.N; if (!filter(k)) { flush(); continue; } run.push(k); }
  flush();
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3)); g.setIndex(idx); g.computeVertexNormals();
  return g;
}

function makeTowerMaterial() {
  const m = new THREE.MeshStandardMaterial({ color: 0x14161c, roughness: 0.45, metalness: 0.25 });
  m.onBeforeCompile = (sh) => {
    sh.vertexShader = sh.vertexShader
      .replace('#include <common>', '#include <common>\nvarying vec3 vWPt; varying vec3 vWNt;')
      .replace('#include <project_vertex>', `#include <project_vertex>
        { mat4 im = modelMatrix * instanceMatrix; vWPt = (im * vec4(transformed, 1.0)).xyz; vWNt = normalize(mat3(im) * objectNormal); }`);
    sh.fragmentShader = sh.fragmentShader
      .replace('#include <common>', `#include <common>\nvarying vec3 vWPt; varying vec3 vWNt;\n${NOISE_GLSL}`)
      .replace('#include <emissivemap_fragment>', `#include <emissivemap_fragment>
        {
          vec3 an = abs(vWNt);
          float hu = an.x > an.z ? vWPt.z : vWPt.x;
          vec2 cell = floor(vec2(hu / 1.9, vWPt.y / 3.6));
          float face = an.x > an.z ? sign(vWNt.x) * 17.0 : sign(vWNt.z) * 31.0;
          float rnd = h21(cell + face + floor(vWPt.x * 0.01) * 7.0);
          vec2 f = fract(vec2(hu / 1.9, vWPt.y / 3.6));
          float win = step(0.16, f.x) * step(f.x, 0.84) * step(0.2, f.y) * step(f.y, 0.8) * step(an.y, 0.5);
          float lit = step(0.58, rnd) * (0.4 + 0.6 * h21(cell * 1.7 + 3.0));
          float warm = step(0.5, h21(cell * 0.37 + 9.0));
          vec3 wc = mix(vec3(0.55, 0.78, 1.0), vec3(1.0, 0.72, 0.4), warm);
          // floors fade out at the very bottom/top, plus a few bright LED bands
          float band = step(0.965, h21(vec2(floor(vWPt.y / 3.6), face + floor(hu / 40.0))));
          totalEmissiveRadiance += win * lit * wc * (0.5 + 2.4 * h21(cell + 11.0)) + band * vec3(0.2, 0.7, 1.0) * 1.5 * step(an.y, 0.5);
        }`);
  };
  return m;
}
