// Drivable test scene: the bare circuit with the real game logic (physics, AI, race director, input, cameras) and stand-in car visuals.
//   ?scene=drive[&autostart][&cam=chase|hood|bumper|orbit|tv][&s=<lap m>&u=<m>&speed=<m/s>][&auto=1][&go=1][&hud=0][&laps=3][&line=1]
//   go=1 skips the countdown. auto=1 lets the autopilot drive the player. Hooks: __race, __drive.{jump, cam, auto, go, hud, line, script}
// Keys: W/↑ S/↓ A/D/←/→ Space C R, Enter = start, Esc = pause (this scene has no UI, so it handles pause itself).
import * as THREE from 'three';
import { getTrack, KIND } from '../track/track.js';
import { loadGLTF } from '../core/assets.js';
import { createRace } from '../game/index.js';

const PAINT = [0xdfe9f2, 0x1ee6ff, 0xff4fd8, 0xff3550, 0x4d7bff, 0xc8ff2e, 0xff8a1f, 0xa66bff];

export default async function (app) {
  const T = getTrack();
  const scene = app.scene;
  window.__track = T;
  scene.background = new THREE.Color(0x070a10);
  scene.fog = new THREE.Fog(0x070a10, 250, 2400);
  scene.add(new THREE.HemisphereLight(0x9fb6d8, 0x202226, 2.0));
  const sun = new THREE.DirectionalLight(0xffffff, 1.6); sun.position.set(300, 500, 200); scene.add(sun);

  buildCircuit(scene, T);

  // ---- stand-in car visual
  const gltf = await loadGLTF('assets/car/wedge_car.glb');
  const makeVisual = ({ livery }) => makeStandIn(gltf, PAINT[livery % PAINT.length]);

  const race = createRace(app, T, { makeVisual, laps: +(app.q.get('laps') ?? T.laps), aiCount: +(app.q.get('ai') ?? 7), handleEscape: true,
    camera: app.q.get('cam') ?? 'chase', playerAI: app.q.has('playerai') });
  window.__race = race;
  const core = race.core, player = race.player;

  // ---- debug overlay
  const hud = document.createElement('div');
  hud.style.cssText = 'position:fixed;left:12px;top:10px;font:12px/1.35 ui-monospace,Menlo,monospace;color:#bfe9ff;text-shadow:0 0 4px #000,0 0 2px #000;white-space:pre;pointer-events:none;z-index:5';
  const big = document.createElement('div');
  big.style.cssText = 'position:fixed;right:18px;bottom:14px;font:600 54px/1 ui-monospace,Menlo,monospace;color:#fff;text-shadow:0 0 8px #0af,0 0 3px #000;pointer-events:none;z-index:5;text-align:right';
  const msg = document.createElement('div');
  msg.style.cssText = 'position:fixed;left:50%;top:22%;transform:translateX(-50%);font:700 96px/1 ui-monospace,Menlo,monospace;color:#fff;text-shadow:0 0 16px #0af;pointer-events:none;z-index:5';
  document.body.append(hud, big, msg);
  let hudOn = app.q.get('hud') !== '0';
  const fmt = (t) => { if (!(t > 0)) return '--:--.---'; const m = Math.floor(t / 60); return `${m}:${(t - m * 60).toFixed(3).padStart(6, '0')}`; };
  app.bus.on('race:countdown', ({ n }) => { msg.textContent = n === 0 ? 'GO' : n; setTimeout(() => { if (msg.textContent === (n === 0 ? 'GO' : String(n))) msg.textContent = ''; }, 900); });

  let accT = 0;
  app.add({
    update(dt) {
      accT += dt;
      hud.style.display = big.style.display = hudOn ? '' : 'none';
      if (!hudOn || accT < 0.05) return;
      accT = 0;
      const c = player, r = c.race, v = c.veh;
      const kmh = c.speed * 3.6;
      big.textContent = `${Math.round(Math.abs(kmh))} km/h${c.gear < 0 ? '  R' : ''}`;
      const w = c.wheels;
      hud.textContent =
        `phase ${core.phase}${core.paused ? ' (paused)' : ''}   t ${core.time.toFixed(1)}s   cam ${race.camera.mode}   fov ${race.camera.outputFov.toFixed(0)}\n` +
        `P${r.place}/${core.cars.length}  lap ${r.lap}/${core.laps}  lapS ${r.lapS.toFixed(0)}  last ${fmt(r.lastLap)}  best ${fmt(r.bestLap)}${r.wrongWay ? '  WRONG WAY' : ''}\n` +
        `s ${c.track.s.toFixed(0)} u ${c.track.u.toFixed(1)}  zone ${T.zoneNames[T.zone[c.track.i]]}  d ${c.track.d.toFixed(2)}\n` +
        `thr ${c.input.throttle.toFixed(2)} brk ${c.input.brake.toFixed(2)} str ${c.input.steer.toFixed(2)} hb ${c.input.handbrake.toFixed(0)}  assists tc${v.assist.tc ? '+' : '-'} abs${v.assist.abs ? '+' : '-'}\n` +
        `g lat ${c.gLat.toFixed(2)} long ${c.gLong.toFixed(2)}   motor ${(c.motor.rpm / 1000).toFixed(1)}k rpm ${c.motor.power.toFixed(0)} kW  brakeT ${c.brakeTemp.toFixed(2)}\n` +
        `load ${w.map(x => (x.load / 1000).toFixed(1)).join(' ')} kN   slip(a) ${w.map(x => (x.slipAngle * 57.3).toFixed(1)).join(' ')}°\n` +
        `skid ${w.map(x => x.skid.toFixed(2)).join(' ')}  travel ${w.map(x => (x.suspensionTravel * 100).toFixed(1)).join(' ')} cm\n` +
        `hits ${core.stats.collisions} (wall ${core.stats.wallHits}, car ${core.stats.carHits}) respawns ${core.stats.respawns}\n` +
        core.results.map(x => `${String(x.place).padStart(2)} ${x.name.padEnd(18)} lap ${x.car.race.lap} ${x.car.race.finished ? fmt(x.time) : (x.car.race.progress / 1000).toFixed(2) + 'km'}`).join('\n');
    },
  });

  // ---- harness hooks
  const drive = window.__drive = {
    race, core,
    jump(s, u = 0, speed = 0) { race.teleport(player, s, u, speed); },
    cam(m) { race.camera.setMode(m); },
    auto(on = true, scale = 1) { race.setAutopilot(on, scale); },
    go() { if (core.phase === 'grid') core.start(); core._go?.(); },
    hud(on) { hudOn = on; },
    script(fn) { race.input.script = fn; },
    line(on = true) { showLine(scene, core, T, on); },
    pause(p) { race.paused = p; },
  };

  // ---- keys
  addEventListener('keydown', (e) => {
    if (e.code === 'Enter' && core.phase === 'grid') race.start();
    else if (e.code === 'Enter' && core.phase === 'finished') { core.reset(); core.start(); }
    else if (e.code === 'Escape' || e.code === 'KeyP') { if (!e.repeat) app.bus.emit('ui:pause', { paused: !core.paused }); }
    else if (e.code === 'KeyH') hudOn = !hudOn;
    else if (e.code === 'KeyL') drive.line(!window.__lineOn);
    else if (e.code === 'KeyT') { const a = player.veh.assist; a.tc = !a.tc; }
    else if (e.code === 'KeyB') { const a = player.veh.assist; a.abs = !a.abs; }
  });

  // ---- URL options
  const q = app.q;
  if (q.has('line')) drive.line(true);
  if (q.has('autostart') || q.has('go')) {
    race.start();
    if (q.has('go')) core._go();
  }
  if (q.has('s')) { drive.jump(+q.get('s'), +(q.get('u') ?? 0), +(q.get('speed') ?? 0)); }
  if (q.has('auto')) drive.auto(true, +(q.get('auto') === 'true' ? 1 : q.get('auto')) || 1);
  if (q.has('go') && !q.has('s')) { /* pack stays on the grid and launches */ }
  await app.ready();
}

// ------------------------------------------------------------------------------------------------------------------
function buildCircuit(scene, T) {
  const N = T.N, pos = [], col = [], idx = [];
  const kc = { [KIND.GROUND]: 0x3a3d44, [KIND.ELEVATED]: 0x4a5a78, [KIND.TRENCH]: 0x6a4a3a, [KIND.TUNNEL]: 0x7a3a5a, [KIND.BRIDGE]: 0x3a6a5a };
  const c = new THREE.Color();
  for (let i = 0; i <= N; i++) {
    const k = i % N, hw = T.hw[k] + 0.5;
    for (const side of [-1, 1]) {
      pos.push(T.px[k] + T.rx[k] * hw * side, T.py[k] + T.ry[k] * hw * side + 0.01, T.pz[k] + T.rz[k] * hw * side);
      c.set(kc[T.kind[k]]); if (Math.floor(k / 10) % 2) c.multiplyScalar(0.8); col.push(c.r, c.g, c.b);
    }
    if (i < N) { const a = i * 2; idx.push(a, a + 2, a + 1, a + 1, a + 2, a + 3); }
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  g.setAttribute('color', new THREE.Float32BufferAttribute(col, 3));
  g.setIndex(idx); g.computeVertexNormals();
  scene.add(new THREE.Mesh(g, new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.55, metalness: 0.1, side: THREE.DoubleSide })));

  // centre dashes
  const dash = [], di = [];
  for (let s = 0, n = 0; s < T.length - 6; s += 12) {
    for (const [a, b] of [[s, s + 5]]) {
      const p0 = T.frameAt(a), p1 = T.frameAt(b);
      const w = 0.12;
      const base = dash.length / 3;
      for (const [p, side] of [[p0, -1], [p0, 1], [p1, -1], [p1, 1]]) dash.push(p.pos.x + p.r.x * w * side + p.u.x * 0.03, p.pos.y + p.r.y * w * side + p.u.y * 0.03, p.pos.z + p.r.z * w * side + p.u.z * 0.03);
      di.push(base, base + 2, base + 1, base + 1, base + 2, base + 3);
    }
  }
  const dg = new THREE.BufferGeometry(); dg.setAttribute('position', new THREE.Float32BufferAttribute(dash, 3)); dg.setIndex(di);
  scene.add(new THREE.Mesh(dg, new THREE.MeshBasicMaterial({ color: 0xcfe8ff, side: THREE.DoubleSide })));

  // walls at hw + 0.5, 1.1 m tall, with a glow strip on top
  for (const side of [-1, 1]) {
    const wp = [], wi = [];
    for (let i = 0; i <= N; i++) {
      const k = i % N, o = (T.hw[k] + 0.5) * side;
      const x = T.px[k] + T.rx[k] * o, y = T.py[k] + T.ry[k] * o, z = T.pz[k] + T.rz[k] * o;
      wp.push(x, y, z, x, y + 1.1, z);
      if (i < N) { const a = i * 2; wi.push(a, a + 2, a + 1, a + 1, a + 2, a + 3); }
    }
    const wg = new THREE.BufferGeometry(); wg.setAttribute('position', new THREE.Float32BufferAttribute(wp, 3)); wg.setIndex(wi); wg.computeVertexNormals();
    scene.add(new THREE.Mesh(wg, new THREE.MeshStandardMaterial({ color: side < 0 ? 0x802040 : 0x1f6a80, emissive: side < 0 ? 0x601030 : 0x10506a, emissiveIntensity: 0.8, side: THREE.DoubleSide })));
  }
  // ground + canal
  const B = T.layout.bounds, cn = T.layout.canal;
  const ground = new THREE.Mesh(new THREE.PlaneGeometry(B.x1 - B.x0, B.z1 - B.z0), new THREE.MeshStandardMaterial({ color: 0x15171c, roughness: 1 }));
  ground.rotation.x = -Math.PI / 2; ground.position.set((B.x0 + B.x1) / 2, -0.05, (B.z0 + B.z1) / 2); scene.add(ground);
  const canal = new THREE.Mesh(new THREE.PlaneGeometry(cn.x1 - cn.x0, B.z1 - B.z0), new THREE.MeshStandardMaterial({ color: 0x0a2a40, roughness: 0.2 }));
  canal.rotation.x = -Math.PI / 2; canal.position.set((cn.x0 + cn.x1) / 2, -0.02, (B.z0 + B.z1) / 2); scene.add(canal);
  // start / finish line + gantry posts
  const sf = T.frameAt(T.startS);
  const line = new THREE.Mesh(new THREE.PlaneGeometry(sf.hw * 2, 1.2), new THREE.MeshBasicMaterial({ color: 0xffffff }));
  line.position.copy(sf.pos).addScaledVector(sf.u, 0.04); line.quaternion.copy(T.quatAt(T.startS)); line.rotateX(-Math.PI / 2); scene.add(line);
  for (const side of [-1, 1]) {
    const post = new THREE.Mesh(new THREE.BoxGeometry(0.6, 7, 0.6), new THREE.MeshStandardMaterial({ color: 0xb0b8c8, emissive: 0x303848 }));
    post.position.copy(sf.pos).addScaledVector(sf.r, side * (sf.hw + 1.4)); post.position.y += 3.5; scene.add(post);
  }
  const bar = new THREE.Mesh(new THREE.BoxGeometry(sf.hw * 2 + 3, 0.7, 0.6), new THREE.MeshStandardMaterial({ color: 0xffffff, emissive: 0x335577 }));
  bar.position.copy(sf.pos); bar.position.y += 7; bar.quaternion.copy(T.quatAt(T.startS)); scene.add(bar);
  // a few tall markers every 250 m so speed and position read in screenshots
  const mk = new THREE.MeshStandardMaterial({ color: 0x40e0ff, emissive: 0x108090 });
  for (let s = 0; s < T.length; s += 250) {
    const f = T.frameAt(s);
    const m = new THREE.Mesh(new THREE.BoxGeometry(0.5, 6 + (s % 500 ? 0 : 3), 0.5), mk);
    m.position.copy(f.pos).addScaledVector(f.r, f.hw + 2.2); m.position.y += 3; scene.add(m);
  }
}

function showLine(scene, core, T, on) {
  window.__lineOn = on;
  if (window.__lineMesh) { window.__lineMesh.visible = on; if (on) return; else return; }
  if (!on) return;
  const line = core.line, drv = core.cars[1]?.driver;
  const pts = [], cols = [];
  const c = new THREE.Color();
  for (let i = 0; i < T.N; i++) {
    const hw = line.n[i];
    const k = i;
    pts.push(line.x[i], T.py[k] + T.ry[k] * hw + 0.12, line.z[i]);
    const v = drv ? drv.prof[i] : 60;
    c.setHSL(0.66 - 0.66 * Math.min(1, v / 85), 1, 0.5); cols.push(c.r, c.g, c.b);
  }
  const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.Float32BufferAttribute(pts, 3)); g.setAttribute('color', new THREE.Float32BufferAttribute(cols, 3));
  const m = new THREE.LineLoop(g, new THREE.LineBasicMaterial({ vertexColors: true }));
  scene.add(m); window.__lineMesh = m;
}

// ------------------------------------------------------------------------------------------------------------------
function makeStandIn(gltf, paint) {
  const root = new THREE.Group();
  const model = gltf.scene.clone(true);
  model.rotation.y = -Math.PI / 2;
  root.add(model);
  const mats = new Map();
  model.traverse((o) => {
    if (!o.isMesh) return;
    o.frustumCulled = false;
    const m = o.material;
    if (m && m.name === 'Paint_LiquidSilver' && paint !== PAINT[0]) {
      if (!mats.has(m)) { const n = m.clone(); n.color = new THREE.Color(paint); n.metalness = 0.6; n.roughness = 0.35; mats.set(m, n); }
      o.material = mats.get(m);
    }
  });
  const names = ['Wheel_FL', 'Wheel_FR', 'Wheel_RL', 'Wheel_RR'];
  const wheels = names.map((n) => { const o = model.getObjectByName(n); return o ? { o, p: o.position.clone(), q: o.quaternion.clone() } : null; });
  const qs = new THREE.Quaternion(), qr = new THREE.Quaternion(), Y = new THREE.Vector3(0, 1, 0), Z = new THREE.Vector3(0, 0, 1);
  return {
    object: root,
    sync(car) {
      root.position.copy(car.position);
      root.quaternion.copy(car.quaternion);
      for (let i = 0; i < 4; i++) {
        const w = wheels[i]; if (!w) continue;
        const cw = car.wheels[i];
        w.o.position.set(w.p.x, w.p.y + cw.suspensionTravel, w.p.z);
        qs.setFromAxisAngle(Y, -cw.steer);
        qr.setFromAxisAngle(Z, cw.spin);
        w.o.quaternion.copy(qs).multiply(w.q).multiply(qr);
      }
    },
    dispose() { root.removeFromParent(); },
  };
}
