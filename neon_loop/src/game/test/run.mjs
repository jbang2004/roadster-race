// `npm test` — headless checks of the gameplay layer (physics, collisions, AI, race director). Pure Node, no browser.
//   node src/game/test/run.mjs [--quick] [--race-only] [--laps N]
// Prints measured numbers next to their targets (docs/BIBLE.md §6) and exits 1 on a failed hard check.
import * as THREE from 'three';
import { getTrack, WALL_OFFSET } from '../../track/track.js';
import { Race } from '../race.js';
import { Road } from '../road.js';
import { Vehicle, WALL_PTS } from '../vehicle.js';
import { PhysicsWorld } from '../world.js';
import { PlayerInput } from '../input.js';
import { Driver } from '../ai.js';
import { buildSpeedProfile } from '../line.js';
import { bus } from '../../core/bus.js';
import * as L from './lib.mjs';

const args = process.argv.slice(2);
const QUICK = args.includes('--quick');
const RACE_ONLY = args.includes('--race-only');
const LAPS = +(args[args.indexOf('--laps') + 1] || 3) || 3;
let failures = 0, warnings = 0;
const rows = [];
const fmt = (x, d = 2) => (typeof x === 'number' ? x.toFixed(d) : String(x));
function metric(name, value, unit, target, tol, { hard = false } = {}) {
  // target: number | [lo, hi] | null
  let ok = true, tgt = '';
  if (Array.isArray(target)) { ok = value >= target[0] && value <= target[1]; tgt = `${target[0]}..${target[1]}`; }
  else if (typeof target === 'number') { ok = Math.abs(value - target) <= tol; tgt = `${target} ±${tol}`; }
  rows.push([ok ? 'ok ' : (hard ? 'FAIL' : 'warn'), name, `${fmt(value, 2)} ${unit}`, tgt ? `target ${tgt}` : '']);
  if (!ok) { if (hard) failures++; else warnings++; }
  return ok;
}
function check(name, cond, detail = '', { hard = true } = {}) {
  rows.push([cond ? 'ok ' : (hard ? 'FAIL' : 'warn'), name, detail, '']);
  if (!cond) { if (hard) failures++; else warnings++; }
  return cond;
}
const section = (s) => rows.push(['', `--- ${s}`, '', '']);
const t0 = Date.now();
const T = getTrack();

// =================================================================================================== vehicle
if (!RACE_ONLY) {
  section('straight line (flat road)');
  const a = L.accelRun(QUICK ? 30 : 60);
  metric('0-100 km/h', a.t100, 's', 2.3, 0.25);
  metric('0-200 km/h', a.t200, 's', [4.2, 6.2], 0);
  metric('0-300 km/h', a.t300, 's', [9, 15], 0);
  metric('top speed (after ' + (QUICK ? 30 : 60) + ' s)', a.vTop, 'km/h', QUICK ? [315, 345] : [322, 340], 0);
  metric('launch acceleration (peak)', a.peakG, 'g', [1.1, 1.6], 0);
  metric('launch squat (nose up)', a.pitchSquat, 'deg', [0.8, 3], 0);
  const b1 = L.brakeRun(100, 0), b2 = L.brakeRun(200, 0), b3 = L.brakeRun(300, 80);
  metric('braking 100-0', b1.dist, 'm', [26, 36], 0);
  metric('braking 200-0', b2.dist, 'm', [95, 125], 0);
  metric('braking 300-80', b3.dist, 'm', 220, 25);
  metric('nose dive at 1.5 g braking', b3.pitchDeg, 'deg', 2, 1.0);
  metric('brake slip under ABS (peak)', b2.maxSlip, '', [0.08, 0.25], 0);
  metric('brake disc temperature after 300-80', b3.brakeTemp, '(0..1)', [0.05, 0.9], 0);

  section('cornering (flat skidpad, path-following controller)');
  const s50 = L.skidpad(50), s150 = L.skidpad(150);
  const s450 = L.skidpad(450, { ramp: 1.5, maxT: QUICK ? 60 : 120 });
  metric('skidpad R50 lateral', s50.latG, 'g', [1.15, 1.45], 0);
  metric('skidpad R150 lateral', s150.latG, 'g', [1.2, 1.55], 0);
  metric('lateral at speed (R450)', s450.latG, 'g @' + fmt(s450.kmh, 0) + ' km/h', 1.5, 0.15);
  metric('roll at skidpad limit', s50.rollDeg, 'deg', [1.8, 3.5], 0);
  const r12 = L.rollAt(100, 3.6 * Math.sqrt(1.2 * 9.81 * 100));
  metric('roll at 1.2 g', r12.rollDeg, 'deg @' + fmt(r12.latG, 2) + ' g', [1.8, 3.5], 0);

  section('cold-gas thrusters');
  const bo = L.boostRun();
  metric('100-200 km/h, thrusters held', bo.tBoost, 's @' + fmt(bo.tPlain, 2) + ' s without', [bo.tPlain * 0.55, bo.tPlain - 0.4], 0, { hard: true });
  metric('full tank lasts', bo.tEmpty, 's', 4.0, 0.25, { hard: true });
  metric('empty tank refills in', bo.tFull, 's', 16.9, 1.0);

  section('stability');
  const st1 = L.stepSteer(100, 0.6), st2 = L.stepSteer(250, 0.5);
  metric('step steer 100 km/h: yaw overshoot', st1.overshoot, '×', [1.0, 1.4], 0);
  metric('step steer 100 km/h: rise time', st1.rise90, 's', [0.08, 0.4], 0);
  metric('step steer 250 km/h: yaw overshoot', st2.overshoot, '×', [1.0, 1.7], 0);
  const lo = L.liftOff(200, 200);
  check('lift-off in a fast corner does not spin', !lo.spun && lo.maxSlipDeg < 20, `max slip ${fmt(lo.maxSlipDeg, 1)}°`);
  const lo2 = L.liftOff(120, 60);
  check('lift-off + braking in a medium corner does not spin', !lo2.spun && lo2.maxSlipDeg < 20, `max slip ${fmt(lo2.maxSlipDeg, 1)}°`);

  // ============================================================================================ collisions
  section('walls & collisions (real circuit)');
  const road = new Road(T);
  function wallRun(s, u, speed, angleDeg, secs, label) {
    const w = new PhysicsWorld(road);
    const v = new Vehicle(road, 0);
    w.add(v);
    const p = T.pointAt(s, u), q = T.quatAt(s);
    const yaw = new THREE.Quaternion().setFromAxisAngle(T.frameAt(s).u, -angleDeg * Math.PI / 180);
    q.premultiply(yaw);
    v.placeAt(p, [q.x, q.y, q.z, q.w], speed);
    v.hint = road.seed(v.px, v.py, v.pz);
    const pr = {}, pt = { x: 0, y: 0, z: 0 };
    let maxPen = 0, maxU = 0, impMax = 0, scrapes = 0, left = 0;
    for (let i = 0; i < secs * 240; i++) {
      w.step(1 / 240);
      for (const c of WALL_PTS) {
        v.toWorld(c[0], c[1], c[2], pt);
        road.probe(pt.x, pt.z, v.hint, pr);
        maxPen = Math.max(maxPen, Math.abs(pr.u) - (pr.hw + WALL_OFFSET));
      }
      maxU = Math.max(maxU, Math.abs(v.pr.u) - v.pr.hw);
      impMax = Math.max(impMax, v.hit.maxWallJ); if (v.hit.scrape > 0.05) scrapes++;
      v.hit.wallImpulse = v.hit.carImpulse = v.hit.maxWallJ = v.hit.maxCarJ = v.hit.scrape = 0;
      if (Math.abs(v.pr.u) > v.pr.hw + 1.5) left++;
    }
    check(`${label}: wall holds (max corner penetration)`, maxPen < 0.3 && left === 0, `${fmt(maxPen, 3)} m, final speed ${fmt(v.speed, 1)} m/s, hit impulse ${fmt(impMax, 0)} N·s, scrape steps ${scrapes}`);
    return { maxPen, v };
  }
  wallRun(300, 0, 90, 12, 4, 'boulevard 90 m/s @12°');
  wallRun(300, -6, 60, 35, 3, 'boulevard 60 m/s @35°');
  wallRun(2500, 0, 85, 8, 4, 'expressway 85 m/s @8°');
  wallRun(3600, 0, 40, 25, 3, 'tunnel 40 m/s @25°');
  wallRun(4350, 0, 45, 0, 3, 'market hairpin straight on');
  wallRun(1000, 0, 80, 70, 3, 'street 80 m/s @70° (head on)');

  function carRun(label, vA, vB, gap, lat, secs = 2.5) {
    const w = new PhysicsWorld(road);
    const A = new Vehicle(road, 0), B = new Vehicle(road, 1);
    w.add(A); w.add(B);
    const s0 = 400;
    const place = (v, s, u, speed, flip) => {
      const p = T.pointAt(s, u), q = T.quatAt(s);
      if (flip) q.premultiply(new THREE.Quaternion().setFromAxisAngle(T.frameAt(s).u, Math.PI));
      v.placeAt(p, [q.x, q.y, q.z, q.w], speed); v.hint = road.seed(v.px, v.py, v.pz);
    };
    place(A, s0, 0, vA, false);
    place(B, s0 + gap, lat, Math.abs(vB), vB < 0);
    const tan = new THREE.Vector3(); let crossed = false, minD = 1e9, maxPenetration = 0;
    const sgn0 = Math.sign(gap);
    for (let i = 0; i < secs * 240; i++) {
      w.step(1 / 240);
      const f = T.frameAt(s0); tan.copy(f.t);
      const d = (B.px - A.px) * tan.x + (B.pz - A.pz) * tan.z;
      if (Math.sign(d) !== sgn0 && Math.abs(lat) < 1.5) crossed = true;
      minD = Math.min(minD, Math.hypot(B.px - A.px, B.pz - A.pz));
      for (const v of [A, B]) { v.hit.wallImpulse = v.hit.carImpulse = v.hit.maxWallJ = v.hit.maxCarJ = v.hit.scrape = 0; }
    }
    check(`${label}: no tunnelling`, !crossed, `closest centres ${fmt(minD, 2)} m, final speeds ${fmt(A.speed, 1)} / ${fmt(B.speed, 1)} m/s`);
    return { A, B };
  }
  carRun('rear-end 60 → 0 m/s', 60, 0, 40, 0.2);
  carRun('head-on 60 vs 60 m/s', 60, -60, 120, 0.3);
  carRun('side swipe 50 m/s, 1.6 m overlap', 52, 50, 3, 1.9);
  carRun('rear-end 90 → 10 m/s', 90, 10, 60, 0.0, 2.0);
}

// =================================================================================================== race
section(`8-car race, ${LAPS} laps, all AI (player slot AI-driven)`);
function runRace(seed, laps = LAPS, maxSim = 600) {
  const race = new Race(T, { bus: null, laps, playerAI: true, seed });
  const ev = { collisions: [], respawns: [], laps: [], finish: [], scrapes: 0 };
  race.bus = { emit(name, p) {
    if (name === 'car:collision') ev.collisions.push(p);
    else if (name === 'car:respawn') ev.respawns.push(p);
    else if (name === 'race:lap') ev.laps.push(p);
    else if (name === 'race:finish') ev.finish.push(p);
  } };
  race.start();
  const H = 1 / 120;
  let maxOff = 0, minSpeedRacing = 1e9, stuckTime = 0, steps = 0;
  const t1 = performance.now();
  while (race.time < maxSim && race.finishedCount < race.cars.length) {
    race.fixed(H); steps++;
    if (race.phase === 'countdown' || race.phase === 'grid') continue;
    for (const c of race.cars) {
      if (c.race.finished) continue;
      const over = Math.abs(c.track.u) - c.track.hw - WALL_OFFSET;
      if (over > maxOff) maxOff = over;
    }
  }
  const wall = performance.now() - t1;
  return { race, ev, maxOff, wall, steps };
}
const R1 = runRace(1);
{
  const { race, ev, maxOff, wall, steps } = R1;
  check('countdown 3-2-1-GO then racing', race.phase === 'finished' || race.phase === 'racing', `phase ${race.phase}`);
  check('every car finishes', race.cars.every(c => c.race.finished), race.cars.map(c => c.race.finished ? '✓' : '✗').join(' '));
  check('no AI respawn (nobody stuck or flipped)', ev.respawns.length === 0, `${ev.respawns.length} respawn(s)`);
  check('no car leaves the road (max distance beyond wall face)', maxOff < 0.35, `${fmt(maxOff, 3)} m`);
  const lt = race.cars.map(c => c.race.lapTimes);
  const best = Math.min(...lt.flat());
  metric('fastest lap', best, 's', [85, 125], 0);
  const finT = race.cars.map(c => c.race.finishTime).sort((a, b) => a - b);
  metric('race duration (winner)', finT[0], 's', [LAPS * 85, LAPS * 125], 0);
  metric('spread winner → last', finT[finT.length - 1] - finT[0], 's', [0, 40], 0);
  const wallHits = ev.collisions.filter(c => c.kind === 'wall').length, carHits = ev.collisions.filter(c => c.kind === 'car').length;
  metric('collisions (heavy)', ev.collisions.length, `(wall ${wallHits}, car ${carHits})`, [0, 24], 0);
  const worst = ev.collisions.reduce((m, c) => Math.max(m, c.impulse), 0);
  metric('worst impact impulse', worst, 'N·s', [0, 30000], 0);
  rows.push(['info', 'sim speed', `${fmt(race.simTime / (wall / 1000), 0)}× real time for 8 cars (${fmt(wall / steps * 1000, 0)} µs per 120 Hz step)`, '']);
  for (const c of [...race.cars].sort((a, b) => a.race.place - b.race.place)) {
    rows.push(['info', `P${c.race.place} ${c.name}`, `${fmt(c.race.finishTime, 1)} s  laps ${c.race.lapTimes.map(x => fmt(x, 1)).join(' / ')}  best ${fmt(c.race.bestLap, 1)}`, '']);
  }
}
if (!RACE_ONLY && !QUICK) {
  const R2 = runRace(1);
  const same = R1.race.cars.every((c, i) => Math.abs(c.race.finishTime - R2.race.cars[i].race.finishTime) < 1e-6);
  check('deterministic (same seed → same race)', same, '');
  const R3 = runRace(2, 2);
  check('second seed: every car finishes without respawn', R3.race.cars.every(c => c.race.finished) && R3.ev.respawns.length === 0, `${R3.ev.collisions.length} collisions`);
}

// =================================================================================================== keyboard player, respawn, rules
if (!RACE_ONLY) {
  section('keyboard-style player (bang-bang keys through the input filter) vs the pack');
  function keyboardRace(pace, esc, aiCount, seconds) {
    const race = new Race(T, { bus: null, laps: 3, aiCount });
    const player = race.cars[0]; player.veh.assist.stability = esc;
    const bot = new Driver(T, race.line, buildSpeedProfile(T, race.line, pace), { skill: pace, aggr: 0.3, cons: 1, seed: 3 });
    const input = new PlayerInput({ target: null });
    let hits = 0, wall = 0, resp = 0, maxSlip = 0;
    race.bus = { emit(name, p) { if (name === 'car:collision' && p.car === player) { hits++; if (p.kind === 'wall') wall++; } else if (name === 'car:respawn' && p.car === player) resp++; } };
    race.start();
    const H = 1 / 120;
    while (race.time < seconds) {
      if (race.phase === 'racing' && !player.race.finished) {
        const ctl = player.veh.ctl;
        bot.update(player, race.cars, H, race.time);
        const k = input.keys; k.clear();
        const st = ctl.steer, cur = input.steer;
        if (st > cur + 0.10) k.add('KeyD'); else if (st < cur - 0.10) k.add('KeyA');
        if (ctl.throttle > 0.3) k.add('KeyW');
        if (ctl.brake > 0.2) k.add('KeyS');
        input.update(H, player.veh.speed);
        ctl.throttle = input.throttle; ctl.brake = input.brake; ctl.steer = input.steer; ctl.handbrake = input.handbrake; ctl.reverse = input.reverse;
        maxSlip = Math.max(maxSlip, Math.abs(Math.atan2(player.veh.vLat, Math.max(5, player.veh.speed))));
      }
      race.fixed(H);
    }
    return { race, player, hits, wall, resp, maxSlip };
  }
  const kb = keyboardRace(0.9, 0.6, 0, QUICK ? 120 : 210);
  check('keyboard bot at 90 % pace laps cleanly', kb.hits === 0 && kb.resp === 0, `${fmt(kb.player.race.lapTimes[0] ?? 0, 1)} s lap, ${kb.hits} hits, max body slip ${fmt(kb.maxSlip * 57.3, 1)}°`);
  const kb2 = keyboardRace(1.0, 0.6, 0, QUICK ? 120 : 210);
  check('keyboard bot at the limit (stability assist on) stays on the road', kb2.resp === 0 && kb2.wall <= 3, `${kb2.wall} wall hits, max body slip ${fmt(kb2.maxSlip * 57.3, 1)}°`);
  if (!QUICK) {
    const kb3 = keyboardRace(0.9, 0.6, 7, 160);
    check('keyboard bot in traffic: no respawn', kb3.resp === 0, `${kb3.hits} hits, place ${kb3.player.race.place}/8`);
  }

  section('director rules');
  {
    const race = new Race(T, { bus: null, laps: 2, playerAI: true });
    const log = [];
    race.bus = { emit(n, p) { log.push([n, p]); } };
    check('starts on the grid, player 6th', race.phase === 'grid' && race.cars[0].gridSlot === 5 && race.cars[0].race.place === 6, `slot ${race.cars[0].gridSlot} place ${race.cars[0].race.place}`);
    race.start();
    for (let i = 0; i < 120 * 3.2; i++) race.fixed(1 / 120);
    const cd = log.filter(l => l[0] === 'race:countdown').map(l => l[1].n);
    check('countdown events 3,2,1,0', cd.join() === '3,2,1,0', cd.join(','));
    check('phase → racing at GO', race.phase === 'racing');
    // flip the player upside down → automatic respawn
    const p = race.cars[0];
    race.cars[0].driver.disabled = true;
    const q = new THREE.Quaternion(p.veh.qx, p.veh.qy, p.veh.qz, p.veh.qw).premultiply(new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 0, -1), Math.PI));
    p.veh.qx = q.x; p.veh.qy = q.y; p.veh.qz = q.z; p.veh.qw = q.w; p.veh.updateRotation(); p.veh.vx = p.veh.vy = p.veh.vz = 0; p.veh.py += 0.6;
    let respawnedAt = -1;
    for (let i = 0; i < 120 * 8 && respawnedAt < 0; i++) { race.fixed(1 / 120); if (log.some(l => l[0] === 'car:respawn' && l[1].car === p)) respawnedAt = race.time; }
    check('upside-down car respawns within ~3.5 s', respawnedAt > 0 && respawnedAt - race.time > -8, `respawn at t=${fmt(respawnedAt, 1)}`);
    for (let i = 0; i < 120; i++) race.fixed(1 / 120);
    check('respawned car is upright, on the road, ghosted', p.veh.R[4] > 0.9 && Math.abs(p.track.u) < p.track.hw && p.ghost, `up ${fmt(p.veh.R[4], 2)} u ${fmt(p.track.u, 1)}`);
    // wrong-way detection
    race.cars[1].driver.disabled = true;
    const c1 = race.cars[1];
    race.teleport(c1, 600, 0, 20);
    const q1 = new THREE.Quaternion(c1.veh.qx, c1.veh.qy, c1.veh.qz, c1.veh.qw).premultiply(new THREE.Quaternion().setFromAxisAngle(T.frameAt(600).u, Math.PI));
    c1.veh.placeAt(T.pointAt(600, 0), [q1.x, q1.y, q1.z, q1.w], 20); c1.veh.hint = race.road.seed(c1.veh.px, c1.veh.py, c1.veh.pz);
    for (let i = 0; i < 120 * 2; i++) { c1.veh.ctl.throttle = 0.2; c1.veh.ctl.brake = 0; race.fixed(1 / 120); }
    check('wrong-way detected', c1.race.wrongWay, `speed ${fmt(c1.veh.speed, 1)} m/s`);
    // lap timing: teleport just before the line
    const c2 = race.cars[2];
    c2.driver.disabled = true;
    const lapsBefore = c2.race.lapTimes.length;
    race.teleport(c2, T.startS - 25, 0, 50);
    for (let i = 0; i < 120 * 1.5; i++) { c2.veh.ctl.throttle = 0.5; c2.veh.ctl.brake = 0; race.fixed(1 / 120); }
    check('crossing the line completes a lap', c2.race.lapTimes.length === lapsBefore + 1 && c2.race.lap === 2, `laps ${c2.race.lapTimes.length}, lap ${c2.race.lap}`);
  }
}

// =================================================================================================== report
const w = [0, 0, 0];
for (const r of rows) { w[1] = Math.max(w[1], r[1].length); w[2] = Math.max(w[2], r[2].length); }
console.log('');
for (const r of rows) {
  if (r[0] === '') { console.log(`\n${r[1]}`); continue; }
  console.log(`  ${r[0].padEnd(4)} ${r[1].padEnd(w[1])}  ${r[2].padEnd(Math.min(w[2], 46))}  ${r[3]}`);
}
console.log(`\n${failures ? 'FAILED' : 'PASSED'}: ${failures} hard failure(s), ${warnings} warning(s) in ${((Date.now() - t0) / 1000).toFixed(1)} s`);
process.exit(failures ? 1 : 0);
