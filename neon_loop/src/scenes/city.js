// W's preview scene: the trackside world with a stand-in atmosphere (fog, HDRI sky, hemisphere + moon), a minimal planar wet-road
// reflection that fills RF (R does this in the game), and bloom. ?scene=city[&s=<metres>][&view=aerial]
// Hooks: __world, __track, __viewAt(s, back, up, ahead, lat, fov), __aerial(s, height, dist, lat), __plane(y|null)
import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { getTrack } from '../track/track.js';
import { phHDRI } from '../core/assets.js';
import { RF } from '../core/reflect.js';
import { G } from '../core/globals.js';
import { LAYER, lightEverything } from '../core/layers.js';
import { buildWorld } from '../world/index.js';

export default async function (app) {
  const T = getTrack();
  window.__track = T;
  const scene = app.scene, renderer = app.renderer, camera = app.camera;
  app.maxPixelRatio = 1;
  camera.layers.enable(LAYER.LATE);

  // ---- stand-in atmosphere ----
  const fogCol = new THREE.Color(0x2a2140);
  scene.fog = new THREE.FogExp2(fogCol, +(app.q.get('fog') ?? 0.0016));
  const hdr = await phHDRI('shanghai_bund');
  const pm = new THREE.PMREMGenerator(renderer);
  scene.environment = pm.fromEquirectangular(hdr).texture;
  scene.environmentIntensity = +(app.q.get('env') ?? 0.22);
  scene.background = hdr; scene.backgroundIntensity = +(app.q.get('bg') ?? 0.07); scene.backgroundBlurriness = 0.02;
  const hemi = lightEverything(new THREE.HemisphereLight(0x5a6a9a, 0x1c1a26, +(app.q.get('amb') ?? 0.7))); scene.add(hemi);
  const moon = lightEverything(new THREE.DirectionalLight(0x8fa6ff, 0.08)); moon.position.set(-300, 500, 200); scene.add(moon);
  // far ground stand-in (K's job in the game)
  // far ground stand-in (K's job in the game: it starts 120 m from the road edge at y = -0.05). Here a plane well below the trench / canal bed.
  const far = new THREE.Mesh(new THREE.PlaneGeometry(9000, 9000), new THREE.MeshBasicMaterial({ color: 0x07070c }));
  far.rotation.x = -Math.PI / 2; far.position.y = -12; scene.add(far);
  G.uWet.value = 1; G.uRain.value = 0.3;

  // ---- world ----
  const world = await buildWorld(app, T);
  window.__world = world;
  app.add(world);

  // ---- minimal planar reflection (fills RF like R will) ----
  let rt = null, planeY = 0, planeOverride = null;
  const vcam = new THREE.PerspectiveCamera();
  const texMat = new THREE.Matrix4(), rot = new THREE.Matrix4();
  const nrm = new THREE.Vector3(0, 1, 0), rp = new THREE.Vector3(), cp = new THREE.Vector3(), tg = new THREE.Vector3(), la = new THREE.Vector3();
  const pr = {};
  function renderReflection() {
    if (!rt) return;
    camera.updateMatrixWorld();
    cp.setFromMatrixPosition(camera.matrixWorld);
    if (planeOverride !== null) planeY = planeOverride;
    else { T.project(cp, -1, pr); planeY = Math.abs(pr.d) < 25 ? pr.y : 0; }
    rp.set(0, planeY, 0);
    const view = rp.clone().sub(cp).reflect(nrm).negate().add(rp);
    rot.extractRotation(camera.matrixWorld);
    la.set(0, 0, -1).applyMatrix4(rot).add(cp);
    tg.copy(rp).sub(la).reflect(nrm).negate().add(rp);
    vcam.position.copy(view);
    vcam.up.set(0, 1, 0).applyMatrix4(rot).reflect(nrm);
    vcam.lookAt(tg);
    vcam.far = camera.far; vcam.near = camera.near; vcam.fov = camera.fov; vcam.aspect = camera.aspect;
    vcam.updateProjectionMatrix(); vcam.updateMatrixWorld(); vcam.matrixWorldInverse.copy(vcam.matrixWorld).invert();
    vcam.layers.set(LAYER.DEFAULT);
    texMat.set(0.5, 0, 0, 0.5, 0, 0.5, 0, 0.5, 0, 0, 0.5, 0.5, 0, 0, 0, 1);
    texMat.multiply(vcam.projectionMatrix).multiply(vcam.matrixWorldInverse);
    { const e = texMat.elements; e[2] = 0; e[6] = 1; e[10] = 0; e[14] = -planeY; }   // RF contract: row 2 carries the mirror plane (n, -n.p)
    RF.uReflectMatrix.value.copy(texMat);
    const rtPrev = renderer.getRenderTarget();
    renderer.setRenderTarget(rt); renderer.clear(); renderer.render(scene, vcam); renderer.setRenderTarget(rtPrev);
    RF.tReflect.value = rt.texture; RF.uReflectOn.value = 1; RF.uReflectLod.value = 5;
  }

  // ---- pipeline: reflection → main (+bloom) ----
  const composer = new EffectComposer(renderer, new THREE.WebGLRenderTarget(4, 4, { type: THREE.HalfFloatType, samples: 4 }));
  composer.addPass(new RenderPass(scene, camera));
  const bloom = new UnrealBloomPass(new THREE.Vector2(256, 256), +(app.q.get('bloom') ?? 0.5), 0.55, 1.0);
  composer.addPass(bloom);
  composer.addPass(new OutputPass());
  app.setPipeline({
    render(dt) {
      if (app.q.has('noref')) { RF.uReflectOn.value = 0; } else renderReflection();
      composer.render(dt);
    },
    setSize(w, h, pixelRatio) {
      composer.setPixelRatio(pixelRatio); composer.setSize(w, h);
      rt?.dispose();
      rt = new THREE.WebGLRenderTarget(Math.max(2, Math.round(w * pixelRatio / 2)), Math.max(2, Math.round(h * pixelRatio / 2)), {
        type: THREE.HalfFloatType, generateMipmaps: true, minFilter: THREE.LinearMipmapLinearFilter, magFilter: THREE.LinearFilter, depthBuffer: true,
      });
      bloom.setSize(w * pixelRatio, h * pixelRatio);
    },
    stats() { return { world: world.meshes.length }; },
  });

  // preview only: thin the fog inside the tunnel / trench (K's height fog does that in the game)
  const fogBase = scene.fog.density, pj = {};
  app.add({ update() { T.project(camera.position, -1, pj); const k = pj.kind; scene.fog.density = fogBase * (k === 3 ? 0.12 : k === 2 ? 0.5 : 1); } });

  // ---- camera hooks ----
  window.__viewAt = (s, back = 9, up = 3.2, ahead = 30, lat = 0, fov = 62) => {
    const f = T.frameAt(s), a = T.frameAt(s + ahead);
    const p = f.pos.clone().addScaledVector(f.t, -back).addScaledVector(f.u, up).addScaledVector(f.r, lat);
    app.setView({ pos: p.toArray(), target: a.pos.clone().addScaledVector(a.u, 1.2).addScaledVector(a.r, lat * 0.5).toArray(), fov });
  };
  window.__aerial = (s, h = 120, dist = 120, lat = 0) => {
    const f = T.frameAt(s);
    const p = f.pos.clone().addScaledVector(f.t, -dist).addScaledVector(f.r, lat); p.y += h;
    app.setView({ pos: p.toArray(), target: f.pos.toArray(), fov: 60 });
  };
  window.__plane = (y) => { planeOverride = y; };
  const sq = app.q.get('s');
  if (app.q.get('view') === 'aerial') window.__aerial(+(sq ?? T.startS));
  else window.__viewAt(+(sq ?? T.startS - 20));
  await app.ready();
}
