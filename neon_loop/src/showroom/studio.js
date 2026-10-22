// The studio: cyclorama mesh, the rectangular lights, the light-map bake and the studio cube map (PMREM) the car is lit by.
import * as THREE from 'three';
import { phHDRI } from '../core/assets.js';
import { postMaterial, fsPass, makeRT } from '../render/common.js';
import { PRESETS } from './presets.js';
import { cycloGeometry, createCycloMaterial, lightRects, applyLights } from './cyclo.js';
import { FloorBake } from './bake.js';

const EMIT_VERT = /* glsl */`varying vec2 vUv; void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`;
const EMIT_FRAG = /* glsl */`
uniform vec3 uL; uniform float uGrad; uniform float uSoft; varying vec2 vUv;
void main() {
  vec2 q = abs(vUv * 2.0 - 1.0);
  float e = max(q.x, q.y);
  float edge = 1.0 - 0.22 * smoothstep(0.5, 1.0, e);               // a real soft box is a touch dimmer toward the rim
  float rim = 1.0 - 0.9 * smoothstep(0.985, 0.995, e);              // thin dark frame
  float soft = uSoft > 0.0 ? 1.0 - smoothstep(1.0 - uSoft, 1.0, length(max(q * 1.0, 0.0) * vec2(1.0))) : 1.0;       // optional smooth fall-off to the rim (no visible edge)
  gl_FragColor = vec4(uL * edge * (uSoft > 0.0 ? 1.0 : rim) * soft * (1.0 - uGrad * vUv.y), 1.0);
}`;

// The sky the car's cube map is built from: the HDRI, with the half of the panorama that lies behind the camera (a dark park) folded over the skyline, so the paint
// mirrors city lights from every side (a car on the Bund would, with the river in front of it and the lights all around).
const SKYENV_VERT = /* glsl */`varying vec3 vD; void main() { vD = position; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`;
const SKYENV_FRAG = /* glsl */`
uniform sampler2D tSky; uniform vec3 uGain; uniform float uRot; uniform vec2 uAx; uniform float uFold; varying vec3 vD;
void main() {
  vec3 d = normalize(vD);
  float s = dot(d.xz, uAx);
  if (uFold > 0.5 && s < 0.0) d.xz -= 2.0 * s * uAx;
  float c = cos(uRot), sn = sin(uRot); d = vec3(c * d.x - sn * d.z, d.y, sn * d.x + c * d.z);
  vec2 uv = vec2(atan(d.z, d.x) / 6.2831853 + 0.5, asin(clamp(d.y, -1.0, 1.0)) / 3.14159265 + 0.5);
  gl_FragColor = vec4(textureLod(tSky, uv, 1.0).rgb * uGain, 1.0);
}`;

const SKY_GRADE = /* glsl */`
uniform sampler2D tHDR; uniform vec3 uGain; uniform float uClampV; varying vec2 vUv;
void main() { vec3 c = min(texture(tHDR, vUv).rgb, vec3(uClampV)); gl_FragColor = vec4(c * uGain, 1.0); }`;

export class Studio {
  constructor(app, scene, carApi) {
    this.app = app; this.r = app.renderer; this.scene = scene; this.car = carApi;
    this.mat = createCycloMaterial();
    this.geos = { room: cycloGeometry(10, 3.6, 14, 160), open: cycloGeometry(1500, 0.6, 3, 192) };
    this.mesh = new THREE.Mesh(this.geos.room, this.mat); this.mesh.frustumCulled = false; this.mesh.name = 'Cyclorama';
    scene.add(this.mesh);
    this.envScene = new THREE.Scene();
    this.envMesh = new THREE.Mesh(this.geos.room, this.mat); this.envMesh.frustumCulled = false;
    this.envScene.add(this.envMesh);
    this.emitters = new THREE.Group(); this.envScene.add(this.emitters);
    this.envSkyMat = new THREE.ShaderMaterial({ vertexShader: SKYENV_VERT, fragmentShader: SKYENV_FRAG, side: THREE.BackSide, depthWrite: false, depthTest: false, toneMapped: false,
      uniforms: { tSky: { value: null }, uGain: { value: new THREE.Vector3(1, 1, 1) }, uRot: { value: 0 }, uAx: { value: new THREE.Vector2(0, 1) }, uFold: { value: 0 } } });
    this.envSky = new THREE.Mesh(new THREE.SphereGeometry(50, 48, 24), this.envSkyMat); this.envSky.frustumCulled = false; this.envSky.renderOrder = -10; this.envSky.visible = false;
    this.envScene.add(this.envSky);
    this.pmrem = new THREE.PMREMGenerator(this.r);
    this.envRT = null;
    this.bake = new FloorBake(this.r, app.q.has('bake1k') ? 1024 : 2048, 1024);
    this.preset = null; this.rects = [];
    this.sky = null;                       // { rt, tex } for the night preset
    this.onEnv = null;
    this.ready = false;
    this.bakeScale = +(app.q.get('bakes') ?? 1);
    // the clear coat mirrors the softboxes almost like a mirror: on a desktop GPU the cube is 1024 per face (a 512 cube shows its texels as jagged reflection edges in close-ups)
    this.envSize = +(app.q.get('envsize') ?? ((this.r.capabilities.maxTextureSize >= 8192 && !(window.matchMedia?.('(pointer: coarse)').matches)) ? 1024 : 512));
    this.pending = false;
  }

  setHull(hull) {
    this.hull = hull;
    const U = this.mat.uniforms;
    U.tSdf.value = hull.tex; U.uSdfMin.value.copy(hull.min); U.uSdfMax.value.copy(hull.max);
    U.uSdfInv.value.set(1 / hull.size.x, 1 / hull.size.y, 1 / hull.size.z); U.uSdfOn.value = 1;
  }

  async _loadSky(p) {
    if (this.sky) return this.sky;
    const hdr = await phHDRI(p.hdri);
    const w = 2048, h = 1024;
    const rt = makeRT(w, h, { name: 'nightSky', generateMipmaps: true, minFilter: THREE.LinearMipmapLinearFilter });
    rt.texture.mapping = THREE.EquirectangularReflectionMapping;
    const m = postMaterial({ name: 'skyGrade', fragmentShader: SKY_GRADE, uniforms: { tHDR: { value: hdr }, uGain: { value: new THREE.Vector3(...(p.hdriGain ?? [1, 1, 1])).multiplyScalar(p.hdriIntensity ?? 1) }, uClampV: { value: p.hdriClamp ?? 40 } } });
    fsPass(this.r, m, rt);
    m.dispose();
    this.sky = { rt, tex: rt.texture };
    return this.sky;
  }

  /** change the studio. Bakes synchronously (the caller fades the screen out around it). */
  async setPreset(id) {
    const p = PRESETS[id]; if (!p) return;
    this.preset = p;
    const U = this.mat.uniforms;
    this.rects = lightRects(p); this.rects0 = lightRects(p); this.rigAng = 0; this.car.setRig?.(0);
    applyLights(this.mat, this.rects);
    this.car.setLights?.(this.rects); this.car.setDiffUp?.(p.diffUp ?? 0); this.car.setArchAO?.(p.archAO ?? 1);
    U.uFloorAlb.value.set(...p.floor.albedo); U.uWallAlb.value.set(...p.wall.albedo); U.uGlow.value.set(...p.wall.glow); U.uGlowH.value = p.wall.glowH;
    U.uAmb.value.set(...p.ambient); U.uRoomSpec.value.set(...(p.camLight ?? [0, 0, 0]));
    U.uTyreAO.value = p.floor.tyreAO ?? 0.6; U.uEnvFloorK.value = p.envFloorK ?? 1;
    { const hi = this.car.visual.lods?.[0]?.root, v = new THREE.Vector3(); hi?.updateMatrixWorld(true);
      ['FL', 'FR', 'RL', 'RR'].forEach((w, i) => { const h = hi?.getObjectByName('Wheel_' + w); if (h) { h.getWorldPosition(v); U.uTyre.value[i].set(v.x, v.z); } }); }
    U.uRough.value = p.floor.rough; U.uSpec.value = p.floor.spec; U.uReflGain.value = p.floor.reflGain ?? p.floor.spec; U.uWallK.value = p.wall.k ?? 0.2;
    const open = !!p.hdri;
    this.mesh.geometry = this.envMesh.geometry = open ? this.geos.open : this.geos.room;
    U.uRf.value = open ? 1500 : 10; U.uRc.value = open ? 0.6 : 3.6; U.uH.value = open ? 3 : 14;
    U.uReflOn.value = p.floor.refl > 0 ? 1 : 0;
    if (open) {
      const sky = await this._loadSky(p);
      U.tSky.value = sky.tex; U.uSkyOn.value = 1; U.uFogDist.value = p.fogDist ?? 120; U.uHazeEl.value = p.hazeEl ?? 0.004; U.uHazeLod.value = p.hazeLod ?? 1.5; U.uHazeK.value = p.hazeK ?? 1;
      this.scene.background = sky.tex; this.scene.backgroundIntensity = 1; this.scene.backgroundBlurriness = 0.0;
      this.envScene.background = null; this.envSky.visible = true;
      { const E = this.envSkyMat.uniforms, f = p.skyFold ? new THREE.Vector2(...p.skyFold).normalize() : null; E.tSky.value = sky.tex; E.uRot.value = p.skyRot ?? 0; E.uFold.value = f ? 1 : 0; if (f) E.uAx.value.copy(f); }
      this.scene.backgroundRotation.y = p.skyRot ?? 0; U.uSkyRot.value = p.skyRot ?? 0;
    } else {
      U.uSkyOn.value = 0; U.uFogDist.value = 0; this.scene.background = null; this.envScene.background = null; this.envSky.visible = false;
    }
    // emitters for the cube map
    for (const c of [...this.emitters.children]) { this.emitters.remove(c); c.geometry.dispose(); c.material.dispose(); }
    for (const r of this.rects) {
      if (!r.env && !r.glassOnly && !r.tyreOnly) continue;                                // flag / gobo lights only light the floor, they are not in the car's reflections
      const m = new THREE.Mesh(new THREE.PlaneGeometry(r.w, r.h), new THREE.ShaderMaterial({ uniforms: { uL: { value: r.L.clone() }, uGrad: { value: r.grad ?? 0 }, uSoft: { value: r.soft ?? 0 } }, vertexShader: EMIT_VERT, fragmentShader: EMIT_FRAG, toneMapped: false, side: THREE.DoubleSide }));
      m.matrixAutoUpdate = false;
      m.matrix.makeBasis(r.ax.clone().normalize(), r.ay.clone().normalize(), r.n.clone()).setPosition(r.c);
      m.matrixWorldNeedsUpdate = true; m.frustumCulled = false; m.userData.noGlass = r.glass === false; m.userData.glassOnly = !!r.glassOnly; m.userData.tyreOnly = !!r.tyreOnly; m.visible = !r.glassOnly && !r.tyreOnly;
      this.emitters.add(m);
    }
    // 1) env without the car's shadow (so the cube exists), 2) bake with LOD 2, 3) env again with the baked floor
    U.uUseLight.value = 0;
    this._buildEnv();
    this.runBake();
    this._buildEnv();
    this.ready = true;
  }

  /** Turn the studio rig about Y (night city: the skyline follows the camera, so the sky, its reflections on the paint and the neon rects turn with it). The cube maps are baked once. */
  setRig(a) {
    if (!this.rects0 || Math.abs(a - this.rigAng) < 1e-5) return;
    this.rigAng = a;
    const q = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), a);
    this.rects.forEach((r, i) => { const b = this.rects0[i]; r.c.copy(b.c).applyQuaternion(q); r.n.copy(b.n).applyQuaternion(q); r.ax.copy(b.ax).applyQuaternion(q); r.ay.copy(b.ay).applyQuaternion(q); });
    applyLights(this.mat, this.rects); this.car.setLights?.(this.rects); this.car.setRig?.(a);
  }

  runBake() {
    const v = this.car.visual;
    const lod = v.lod; v.forceLod(2);
    const U = this.mat.uniforms;
    // LOD2 has no tyres: borrow the hi-LOD tyre meshes (same geometry, world matrices of the hubs) as occluders for the bake only
    const tyres = [];
    const hi = v.lods?.[0]?.root; hi?.updateMatrixWorld(true);
    hi?.traverse(o => {
      if (!o.isMesh || !(/^Tyre_/.test(o.name) || /^Tyre_/.test(o.parent?.name ?? ''))) return;
      const m = new THREE.Mesh(o.geometry, new THREE.MeshBasicMaterial());
      m.matrixAutoUpdate = false; m.matrix.copy(o.matrixWorld); m.matrixWorld.copy(o.matrixWorld); m.layers.set(3); m.frustumCulled = false;
      this.scene.add(m); tyres.push(m);
    });
    this.bake.start(this.rects, this.preset.ambient, 192, this.bakeScale);
    const t0 = performance.now();
    while (!this.bake.finished) this.bake.step(this.scene, 50);
    for (const m of tyres) { this.scene.remove(m); m.material.dispose(); }
    this.bakeMs = performance.now() - t0;
    this.bakeSamples = this.bake.samples.length;
    v.forceLod(lod < 0 ? 0 : lod);
    U.tLight.value = this.bake.texture; U.uUseLight.value = 1;
    U.uLightRect.value.set(0, 0, this.bake.extent, 0);
  }

  _buildEnv() {
    const U = this.mat.uniforms;
    const camSave = U.uCam.value.clone();
    U.uCam.value.set(0, 0.8, 0); U.uEnvPass.value = 1; U.uCamFwd.value.set(0, 0, -1);
    this.envSkyMat.uniforms.uGain.value.setScalar(this.preset?.envSkyK ?? 1);       // the paint sees the skyline hotter than the backdrop shows it (a night-city backdrop is dim; the clear coat only mirrors 4 % of it)
    const next = this.pmrem.fromScene(this.envScene, 0, 0.1, 100, { size: this.envSize, position: new THREE.Vector3(0, 0.8, 0) });
    U.uEnvPass.value = 0; U.uCam.value.copy(camSave);
    const old = this.envRT; this.envRT = next;
    this.car.visual.setEnvMap(next.texture);
    old?.dispose();
    // the glass sees the studio without the strip lights (photographers flag them off the glass: no snaking white lines across the windscreen)
    const hide = this.emitters.children.filter(m => m.userData.noGlass), only = this.emitters.children.filter(m => m.userData.glassOnly);
    if (hide.length || only.length) {
      hide.forEach(m => { m.visible = false; }); only.forEach(m => { m.visible = true; });
      U.uCam.value.set(0, 0.8, 0); U.uEnvPass.value = 1;
      const g = this.pmrem.fromScene(this.envScene, 0, 0.1, 100, { size: 256, position: new THREE.Vector3(0, 0.8, 0) });
      U.uEnvPass.value = 0; U.uCam.value.copy(camSave);
      hide.forEach(m => { m.visible = true; }); only.forEach(m => { m.visible = false; });
      for (const m of this.car.glassMats ?? []) m.envMap = g.texture;
      this.envGlassRT?.dispose(); this.envGlassRT = g;
    }
    // the tyres (only) see two extra strips lying on the floor beside the car: a thin lit edge along the sidewall without lighting the doors
    const tyreOnly = this.emitters.children.filter(m => m.userData.tyreOnly);
    if (tyreOnly.length) {
      tyreOnly.forEach(m => { m.visible = true; });
      U.uCam.value.set(0, 0.8, 0); U.uEnvPass.value = 1;
      const g = this.pmrem.fromScene(this.envScene, 0, 0.1, 100, { size: 256, position: new THREE.Vector3(0, 0.8, 0) });
      U.uEnvPass.value = 0; U.uCam.value.copy(camSave);
      tyreOnly.forEach(m => { m.visible = false; });
      for (const m of this.car.tyreMats ?? []) m.envMap = g.texture;
      this.envTyreRT?.dispose(); this.envTyreRT = g;
    } else for (const m of this.car.tyreMats ?? []) m.envMap = next.texture;
    this.envSkyMat.uniforms.uGain.value.setScalar(this.preset?.envSkyDiff ?? 1);
    this._projectSH();
    this.onEnv?.(next);
  }

  /** Spherical-harmonic (order 2) projection of the studio radiance seen from the car: the exact diffuse light for the paint (see car.js). */
  _projectSH() {
    const N = 96, r = this.r, U = this.mat.uniforms;
    if (!this.shRT) { this.shRT = new THREE.WebGLRenderTarget(N, N, { type: THREE.HalfFloatType, depthBuffer: true, samples: 4 }); this.shCam = new THREE.PerspectiveCamera(90, 1, 0.1, 400); this.shBuf = new Uint16Array(N * N * 4); }
    const cam = this.shCam, buf = this.shBuf, camSave = U.uCam.value.clone(), old = r.getRenderTarget(), cc = new THREE.Color(), ca = r.getClearAlpha(); r.getClearColor(cc);
    U.uCam.value.set(0, 0.8, 0); U.uEnvPass.value = 1; U.uCamFwd.value.set(0, 0, -1);
    this.emitters.visible = false;                         // the lights are integrated analytically in the paint shader; only the room goes into the SH
    const faces = [[1, 0, 0, 0, 1, 0], [-1, 0, 0, 0, 1, 0], [0, 1, 0, 0, 0, -1], [0, -1, 0, 0, 0, 1], [0, 0, 1, 0, 1, 0], [0, 0, -1, 0, 1, 0]];
    const sh = new Float64Array(27), fwd = new THREE.Vector3(), up = new THREE.Vector3(), right = new THREE.Vector3(), d = new THREE.Vector3();
    const half = THREE.DataUtils.fromHalfFloat;
    for (const f of faces) {
      fwd.set(f[0], f[1], f[2]); up.set(f[3], f[4], f[5]); right.crossVectors(fwd, up);
      cam.position.set(0, 0.8, 0); cam.up.copy(up); cam.lookAt(fwd.x, 0.8 + fwd.y, fwd.z); cam.updateMatrixWorld(true);
      r.setRenderTarget(this.shRT); r.setClearColor(0x000000, 1); r.clear(true, true, false); r.render(this.envScene, cam);
      r.readRenderTargetPixels(this.shRT, 0, 0, N, N, buf);
      for (let j = 0; j < N; j++) for (let i = 0; i < N; i++) {
        const x = (i + 0.5) / N * 2 - 1, y = (j + 0.5) / N * 2 - 1, l2 = 1 + x * x + y * y;
        const dw = (2 / N) * (2 / N) / (l2 * Math.sqrt(l2));
        d.set(fwd.x + right.x * x + up.x * y, fwd.y + right.y * x + up.y * y, fwd.z + right.z * x + up.z * y).normalize();
        const o = (j * N + i) * 4, R = half(buf[o]), G = half(buf[o + 1]), B = half(buf[o + 2]);
        const bas = [0.282095, 0.488603 * d.y, 0.488603 * d.z, 0.488603 * d.x, 1.092548 * d.x * d.y, 1.092548 * d.y * d.z, 0.315392 * (3 * d.z * d.z - 1), 1.092548 * d.x * d.z, 0.546274 * (d.x * d.x - d.y * d.y)];
        for (let k = 0; k < 9; k++) { const w = bas[k] * dw; sh[3 * k] += R * w; sh[3 * k + 1] += G * w; sh[3 * k + 2] += B * w; }
      }
    }
    this.emitters.visible = true; r.setRenderTarget(old); r.setClearColor(cc, ca); U.uEnvPass.value = 0; U.uCam.value.copy(camSave);
    this.sh = Array.from(sh);
    this.car.setSH?.(this.sh.map(v => v * (this.preset?.carSH ?? 1)));       // preset.carSH: how much room (floor / wall) light the body picks up
  }

  dispose() { this.envRT?.dispose(); this.envGlassRT?.dispose(); this.shRT?.dispose(); this.pmrem.dispose(); this.bake.dispose(); this.mat.dispose(); }
}
