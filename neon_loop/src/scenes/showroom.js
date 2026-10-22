// SHOWROOM  (?scene=showroom): a close-up viewing mode for the car in a procedural photo studio. Entered from the title menu, Esc / the back button
// returns to the game. A separate scene with its own renderer pipeline (progressive accumulation at rest), so the race is untouched.
//   ?scene=showroom[&studio=dark|light|city][&view=front34|side|...][&paint=pearl|silver|black|red|blue|grey][&samples=96][&bakes=1][&ui=0]
//   hooks (window.__sr): view(id[, instant]) · setStudio(id) · paint(id) · feature(id, on) · photo(on, aperture) · settle() · stats()
import * as THREE from 'three';
import { G } from '../core/globals.js';
import { VIEWS, REF_VIEWS, PRESETS, PAINTS } from '../showroom/presets.js';
import { createShowroomCar } from '../showroom/car.js';
import { buildHull } from '../showroom/hull.js';
import { Studio } from '../showroom/studio.js';
import { ShowroomPipeline } from '../showroom/pipeline.js';
import { OrbitRig } from '../showroom/camera.js';
import { createShowroomUI } from '../showroom/ui.js';

const sleep = (ms) => new Promise(r => setTimeout(r, ms));

export default async function (app) {
  const q = app.q, renderer = app.renderer;
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(30, app.width / app.height, 0.06, 90);
  camera.layers.enableAll();
  G.uRain.value = 0; G.uWet.value = 0;
  app.scene.remove(app.camera);

  // ---- the car, its body SDF, the studio (bake + cube map)
  const GLASS_ABS = 0.9;                      // the press photos show nearly opaque, brown-tinted glass from outside
  const carApi = await createShowroomCar(app, scene);
  carApi.visual.uniforms.car.uGlassAbs.value = GLASS_ABS;
  const hull = buildHull(renderer, scene, carApi.visual);
  const studio = new Studio(app, scene, carApi);
  studio.setHull(hull);
  const startStudio = PRESETS[q.get('studio')] ? q.get('studio') : 'dark';
  await studio.setPreset(startStudio);

  // ---- pipeline + camera
  const pipeline = new ShowroomPipeline(app, { scene, camera, cyclo: studio.mat, params: { samples: +(q.get('samples') ?? 96) } });
  pipeline.cycloMesh = studio.mesh;
  { // starting quality level: phones / small touch screens start one notch lighter; ?q=0|1|2 forces a level; otherwise the governor adapts to the measured frame time
    const mobile = matchMedia('(pointer: coarse)').matches && Math.min(screen.width, screen.height) <= 900;
    pipeline.setLevel(q.has('q') ? +q.get('q') : (mobile ? 1 : 0)); pipeline.locked = q.has('q');
  }
  studio.mat.uniforms.tRefl.value = pipeline.rtRefl.texture;
  const applyLook = (p) => {
    const P = pipeline.params;
    P.exposure = p.exposure; P.bloom.strength = p.bloom.strength; P.bloom.threshold = p.bloom.threshold; P.vignette = p.vignette; P.tonemap = p.tonemap;
    P.contrast = p.contrast ?? 0.16; P.saturation = p.saturation ?? 1.02;
    pipeline.markDirty();
  };
  applyLook(studio.preset);
  if (q.has('exp')) pipeline.params.exposure = +q.get('exp');
  if (q.get('tm')) pipeline.params.tonemap = q.get('tm');
  app.setPipeline(pipeline);

  const rig = new OrbitRig(camera, renderer.domElement, hull);
  rig.autoOn = !app.harness || q.has('autorotate');
  rig.setAspect(app.width / app.height);
  const goView = (id, instant = false) => {
    const v = VIEWS.find(x => x.id === id); if (!v) return;
    if (instant) rig.jumpTo(v.pos, v.target, v.fov, v.margin); else rig.flyTo(v.pos, v.target, v.fov, 1.25, v.margin);
    ui?.setViewActive(id); curView = id;
    glassBase = id === 'cockpit' ? 0.3 : GLASS_ABS;
  };
  let curView = null, ui = null, busy = false, glassBase = GLASS_ABS;

  // ---- actions
  const act = {
    goView: (id) => goView(id),
    async setStudio(id) {
      if (busy || !PRESETS[id] || id === studio.preset.id) return;
      busy = true;
      for (let k = 0; k < 14; k++) { pipeline.fade = Math.min(1, pipeline.fade + 0.1); pipeline.repost(); await sleep(16); }
      pipeline.fade = 1; pipeline.repost(); await sleep(30);
      await studio.setPreset(id);
      applyLook(studio.preset);
      pipeline.markDirty(); await sleep(60);
      for (let k = 0; k < 14; k++) { pipeline.fade = Math.max(0, pipeline.fade - 0.08); pipeline.markDirty(); await sleep(16); }
      pipeline.fade = 0; pipeline.markDirty();
      ui?.setStudioActive(id); busy = false;
    },
    setPaint(id) { carApi.setPaint(id); ui?.setPaintActive(id); pipeline.markDirty(); },
    setFeature(id, on) {
      if (id === 'rotate') { rig.autoOn = on; return; }
      carApi.setFeature(id, on); pipeline.markDirty();
    },
    photo(on) {
      const P = pipeline.params;
      P.samples = on ? 192 : +(q.get('samples') ?? 96);
      P.dof.on = on;
      if (on) { P.dof.aperture = 0.012 + 0.1 * apertureK; P.dof.focus = rig.camera.position.distanceTo(rig.target); }
      pipeline.markDirty();
    },
    setAperture(k) { apertureK = k; pipeline.params.dof.aperture = 0.012 + 0.1 * k * k; pipeline.markDirty(); },
    exit() { leave(); },
  };
  let apertureK = 0.45;
  ui = createShowroomUI(app, { act, camera: rig, hull });
  ui.resize();
  ui.setStudioActive(studio.preset.id); ui.setPaintActive('pearl');
  for (const f of ['drl', 'tail']) ui.setFeatureActive(f, true);
  ui.setFeatureActive('rotate', rig.autoOn); ui.setFeatureActive('hotspots', true);
  if (q.get('ui') === '0') ui.root.style.display = 'none';
  if (PAINTS.some(p => p.id === q.get('paint'))) act.setPaint(q.get('paint'));
  goView(VIEWS.some(v => v.id === q.get('view')) ? q.get('view') : 'front34', true);

  // ---- tap handlers
  rig.onTap = (x, y) => {
    if (ui.photo) {
      const p = rig.pick(x, y); if (!p) return;
      const f = _fwd.set(0, 0, -1).applyQuaternion(camera.quaternion);
      pipeline.params.dof.focus = Math.max(0.3, _d.copy(p).sub(camera.position).dot(f));
      ui.focusRing(x, y); pipeline.markDirty();
    } else if (ui.popOpen) ui.setPop(ui.popOpen);
    else if (ui.cardOpen) ui.closeCard();
  };
  rig.onDoubleTap = (x, y) => {
    if (ui.photo) return;
    const p = rig.pick(x, y);
    if (p && p.y > 0.05) rig.focusOn(p, Math.max(1.0, Math.min(2.4, camera.position.distanceTo(p) * 0.55)));
    else goView('front34');
    curView = null; ui.setViewActive(null);
  };
  rig.onInput = () => { if (curView && !rig.anim) { /* keep the chip lit until the user drags away */ } };

  // ---- keys
  const onKey = (e) => {
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    if (e.code === 'Escape') {
      if (ui.cardOpen) ui.closeCard(); else if (ui.popOpen) ui.setPop(ui.popOpen); else if (ui.photo) ui.setPhoto(false); else leave();
      e.preventDefault(); return;
    }
    if (e.repeat) return;
    if (/^Digit[1-8]$/.test(e.code)) { goView(VIEWS[+e.code.slice(5) - 1].id); return; }
    if (e.code === 'KeyP') { ui.setPhoto(!ui.photo); return; }
    if (e.code === 'Space') { rig.autoOn = !rig.autoOn; ui.setFeatureActive('rotate', rig.autoOn); e.preventDefault(); return; }
    if (e.code === 'KeyR') { goView('front34'); }
  };
  window.addEventListener('keydown', onKey);
  function leave() {
    const u = new URL(location.href);
    u.searchParams.delete('scene'); u.searchParams.delete('studio'); u.searchParams.delete('view'); u.searchParams.delete('paint'); u.searchParams.delete('samples');
    location.href = u.toString();
  }

  // ---- per-frame system
  const U = studio.mat.uniforms;
  app.add({
    update(dt) {
      rig.update(dt);
      const changed = carApi.update(dt);
      if (changed) pipeline.markDirty();
      U.uCam.value.copy(camera.position);
      {                                                  // looking down through the roof the glass closes up (no tan interior patch seen from above); the cabin view keeps it open
        const ga = glassBase + (glassBase > 0.5 ? 0.22 * THREE.MathUtils.smoothstep(rig.pitch, 0.7, 1.3) : 0);
        const gu = carApi.visual.uniforms.car.uGlassAbs; if (Math.abs(gu.value - ga) > 1e-3) { gu.value = ga; pipeline.markDirty(); }
      }
      {                                                  // depth precision follows the distance to the car: far views get a far near-plane, close-ups can still go to 3 cm without cutting the body
        const dh = hull.distance(camera.position), nr = Math.min(Math.max(0.3 * dh, 0.03), 0.5);
        if (Math.abs(nr - camera.near) > 0.04 * camera.near) { camera.near = nr; camera.updateProjectionMatrix(); pipeline.markDirty(); }
      }
      { const far = studio.preset.hdri ? 3000 : 90;      // open night street: the floor runs out to the true horizon (a 90 m far plane would cut it into a visible seam below the skyline)
        if (camera.far !== far) { camera.far = far; camera.updateProjectionMatrix(); pipeline.markDirty(); } }
      if (studio.preset.hdri) {                    // city: the skyline stays behind the car whichever side you look from (the other half of the panorama is a park)
        const x = camera.position.x, z = camera.position.z;
        if (Math.hypot(x, z) > 1.5) skyAz = Math.atan2(x, z);
        const rot = (studio.preset.skyRot ?? 0) + SKY_K * (skyAz - SKY_AZ0);
        if (Math.abs(rot - U.uSkyRot.value) > 1e-4) { U.uSkyRot.value = rot; scene.backgroundRotation.y = rot; studio.setRig(rot - (studio.preset.skyRot ?? 0)); pipeline.markDirty(); }
      }
      _fwd.set(0, 0, -1).applyQuaternion(camera.quaternion); U.uCamFwd.value.set(_fwd.x, 0, _fwd.z).normalize();
      app.camera.position.copy(camera.position);
      ui.update(dt, rig.pointers.size > 0 || rig.idle < 1.5);
    },
    resize(w, h) { camera.aspect = w / h; rig.setAspect(w / h); camera.updateProjectionMatrix(); ui?.resize(); pipeline.markDirty(); },
  });

  // ---- hooks for screenshots / tests
  window.__sr = {
    THREE, app, scene, camera, rig, studio, pipeline, car: carApi, ui, hull,
    view: goView, setStudio: act.setStudio, paint: act.setPaint, feature: (id, on) => { act.setFeature(id, on); ui.setFeatureActive(id, on); },
    photo: (on, k = 0.45) => { ui.setPhoto(on); if (on) act.setAperture(k); },
    focusAt(x, y) { rig.onTap(x, y); },
    quality(l) { pipeline.setLevel(l); pipeline.locked = true; },
    refView(id) { const v = REF_VIEWS[id]; rig.jumpTo(v.pos, v.target, v.fov); curView = null; },
    jump(pos, target, fov) { rig.jumpTo(pos, target, fov); curView = null; },
    settle: async (max = 20000) => { const t0 = performance.now(); await sleep(120); while (!pipeline.converged || rig.anim) { if (performance.now() - t0 > max) return false; await sleep(50); } await sleep(100); return pipeline.n; },
    stats: () => ({ ...app.stats(), calls: pipeline._calls, tris: pipeline._tris, ...pipeline.stats(), bake: { ms: Math.round(studio.bakeMs), samples: studio.bakeSamples } }),
  };
  window.__app = app;

  // ---- compile everything into the HDR target before the first frame
  renderer.setRenderTarget(pipeline.rtScene);
  try { await renderer.compileAsync(scene, camera); } catch (e) { console.warn('compile', e); }
  renderer.setRenderTarget(null);
  pipeline.markDirty();
  await app.ready();
  ui.setLoading(false);
}
const _fwd = new THREE.Vector3(), _d = new THREE.Vector3();
let skyAz = Math.atan2(-5.9, -6.1);
const SKY_AZ0 = Math.atan2(-5.9, -6.1), SKY_K = 1;      // az of the front 3/4 camera the city skyRot was tuned for
