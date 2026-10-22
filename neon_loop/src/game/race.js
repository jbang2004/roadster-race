// Race director + simulation core (no DOM, no WebGL): cars, physics world, AI drivers, grid, countdown, lap timing,
// positions, wrong-way, respawn. `createRace` (index.js) wraps this with the app: input, cameras, visuals, events to the UI.
import * as THREE from 'three';
import { Vehicle } from './vehicle.js';
import { PhysicsWorld } from './world.js';
import { Road } from './road.js';
import { buildRacingLine, buildSpeedProfile } from './line.js';
import { Driver } from './ai.js';
import { CAR, DRIVERS, PLAYER_NAME, STEER } from './params.js';

const clamp = (x, a, b) => (x < a ? a : x > b ? b : x);
export const DIFFICULTY_GRIP = [0.90, 1.0, 1.04];     // easy / normal / hard: fraction of the grip limit the AI uses (× driver skill)
const SUB = 2;                                          // physics sub-steps per 120 Hz fixed step → 240 Hz

export function makeCarState(id, name, livery, isPlayer) {
  const wheels = [];
  for (let i = 0; i < 4; i++) wheels.push({ steer: 0, spin: 0, spinRate: 0, compression: 0, suspensionTravel: 0, load: 0, slipRatio: 0, slipAngle: 0, grounded: true, skid: 0, contact: new THREE.Vector3() });
  return {
    id, name, livery, isPlayer, visual: null,
    position: new THREE.Vector3(), quaternion: new THREE.Quaternion(),
    velocity: new THREE.Vector3(), angularVelocity: new THREE.Vector3(), speed: 0, accel: new THREE.Vector3(),
    input: { throttle: 0, brake: 0, steer: 0, handbrake: 0 },
    wheels, motor: { rpm: 0, load: 0, power: 0 }, brakeTemp: 0,
    lights: { head: true, brake: 0, reverse: false },
    boost: { gas: 1, level: 0 },          // cold-gas thrusters: tank 0..1, valve opening 0..1
    race: { lap: 1, lapS: 0, progress: 0, place: id + 1, lapTimes: [], bestLap: 0, lastLap: 0, finished: false, finishTime: 0,
      gapAhead: null, gapBehind: null, gapAheadM: null, gapBehindM: null, started: false, wrongWay: false },
    track: { i: 0, s: 0, u: 0, d: 0, hw: 8 },
    // extras (not in the contract, handy for UI / audio / FX)
    gear: 1, ghost: false, respawning: false, grip: 1, bodyRoll: 0, bodyPitch: 0, gLat: 0, gLong: 0, airborne: false,
    veh: null, driver: null,
    // internal
    _p0: new THREE.Vector3(), _q0: new THREE.Quaternion(), _p1: new THREE.Vector3(), _q1: new THREE.Quaternion(),
    _w0: [0, 0, 0, 0].map(() => ({ spin: 0, trav: 0, comp: 0, steer: 0 })), _w1: [0, 0, 0, 0].map(() => ({ spin: 0, trav: 0, comp: 0, steer: 0 })),
    _prevS: 0, _lapStartT: 0, _flipT: 0, _offT: 0, _slowT: 0, _ghostT: 0, _hitCool: 0, _carCool: 0, _wrongT: 0, _scrape: null,
    _release: 0,
  };
}

export class Race {
  /**
   * o: { laps, aiCount = 7, bus, seed = 1, playerAI = false (drive the player with an AI too — tests / attract mode),
   *      difficulty = 1, catchUp = true }
   */
  constructor(track, o = {}) {
    this.track = track;
    this.bus = o.bus ?? null;
    this.laps = o.laps ?? track.laps ?? 3;
    this.aiCount = o.aiCount ?? 7;
    this.seed = o.seed ?? 1;
    this.playerAI = !!o.playerAI;
    this.catchUpOn = o.catchUp ?? true;
    this.difficulty = o.difficulty ?? 1;
    this.road = new Road(track);
    this.world = new PhysicsWorld(this.road);
    this.line = buildRacingLine(track);
    this.phase = 'grid';
    this.paused = false;
    this.time = 0;                    // race clock (s since GO)
    this.simTime = 0;
    this.cdT = 0; this.cdStep = -1;
    this.cars = [];
    this.results = [];
    this.finishedCount = 0;
    this.stats = { collisions: 0, wallHits: 0, carHits: 0, respawns: 0 };
    this.events = [];                 // pending events for the frame (scrapes etc.)
    this._order = [];
    this._build();
    this.reset();
  }

  profileFor(skill) { return buildSpeedProfile(this.track, this.line, clamp(skill * DIFFICULTY_GRIP[this.difficulty], 0.5, 0.995)); }

  _build() {
    const player = makeCarState(0, PLAYER_NAME, 0, true);
    this.cars.push(player);
    const n = Math.min(this.aiCount, DRIVERS.length);
    for (let i = 0; i < n; i++) this.cars.push(makeCarState(i + 1, DRIVERS[i].name, i + 1, false));
    this.cars.forEach((c, k) => {
      c.veh = new Vehicle(this.road, k);
      if (!c.isPlayer || this.playerAI) c.veh.assist.stability = 0;     // AI drives accurately; the stability assist is the human's aid
      this.world.add(c.veh);
      if (!c.isPlayer || this.playerAI) {
        const d = c.isPlayer ? { skill: 0.93, aggr: 0.5, cons: 0.98 } : DRIVERS[k - 1];
        c.driver = new Driver(this.track, this.line, this.profileFor(d.skill), { ...d, seed: this.seed * 101 + k * 17 + 3 });
        c.driver.baseSkill = d.skill;
      }
    });
    // an autopilot for the player (cool-down lap after the finish, attract mode)
    player.autopilot = new Driver(this.track, this.line, buildSpeedProfile(this.track, this.line, 0.78), { skill: 0.78, aggr: 0.2, cons: 0.99, seed: 5 });
    this.drivers = this.cars.map(c => c.driver);
  }

  setDifficulty(i) {
    this.difficulty = clamp(i | 0, 0, 2);
    this.cars.forEach((c, k) => {
      if (c.driver && !c.isPlayer) c.driver.prof = this.profileFor(DRIVERS[k - 1].skill);
    });
  }

  emit(name, payload) { this.bus?.emit(name, payload); }

  // ------------------------------------------------------------------ grid / reset / start
  reset() {
    const T = this.track;
    this.phase = 'grid'; this.time = 0; this.cdT = 0; this.cdStep = -1; this.finishedCount = 0; this.paused = false;
    this.results = [];
    // grid order: player 6th (slot 5); AI by driver strength
    const slots = [0, 1, 2, 3, 4, 6, 7];
    this.cars.forEach((c, k) => {
      const slot = k === 0 ? 5 : slots[k - 1] ?? k + 1;
      const g = T.gridSlot(slot);
      c.gridSlot = slot;
      const q = [g.quat.x, g.quat.y, g.quat.z, g.quat.w];
      c.veh.placeAt(g.pos, q, 0);
      c.veh.coolDown(); c.veh.collidable = true; c.veh.gas = 1;
      const ctl = c.veh.ctl; ctl.throttle = 0; ctl.brake = 1; ctl.steer = 0; ctl.handbrake = 0; ctl.reverse = false; ctl.boost = false;
      c.veh.uProj = g.u;
      const r = c.race;
      r.lap = 1; r.lapTimes = []; r.bestLap = 0; r.lastLap = 0; r.finished = false; r.finishTime = 0; r.started = false; r.wrongWay = false;
      r.progress = T.deltaS(T.startS, g.s); r.lapS = T.wrapS(g.s - T.startS);
      r.place = 0; r.gapAhead = r.gapBehind = r.gapAheadM = r.gapBehindM = null;
      c._prevS = g.s; c._lapStartT = 0; c._flipT = c._offT = c._slowT = 0; c._ghostT = 0; c.ghost = false; c.respawning = false; c._scrape = null;
      c.track.i = c.veh.hint; c.track.s = g.s; c.track.u = g.u; c.track.d = 0;
      if (c.driver) { c.driver.mode = 'drive'; c.driver.off = 0; c.driver.passCar = null; c.driver.stuckT = 0; c.driver.speedScale = 1; }
      c.autopilotOn = false;
      c.veh.ctl.brake = 1;
      this._snapshot(c); this._snapshot(c);
    });
    // let the suspension settle one second before anything is released (cars are braked)
    for (let i = 0; i < 60; i++) this._substeps(1 / 120, true);
    this.cars.forEach(c => { this._snapshot(c); this._snapshot(c); this._project(c); });
    this._rank();
    this.emit('race:phase', { phase: 'grid' });
  }

  start(o = {}) {
    if (o.laps) this.laps = o.laps;
    if (o.difficultyIndex != null && o.difficultyIndex !== this.difficulty) this.setDifficulty(o.difficultyIndex);
    if (this.phase !== 'grid') this.reset();
    this.phase = 'countdown'; this.cdT = 0; this.cdStep = -1;
    this.emit('race:phase', { phase: 'countdown' });
  }

  // ------------------------------------------------------------------ main step (120 Hz)
  fixed(h) {
    if (this.paused) return;
    this.simTime += h;
    // phases
    if (this.phase === 'countdown') {
      this.cdT += h;
      const step = Math.min(3, Math.floor(this.cdT));
      if (step !== this.cdStep) {
        this.cdStep = step;
        const n = 3 - step;
        this.emit('race:countdown', { n, lamps: n === 0 ? -1 : 6 - n });
        if (n === 0) this._go();
      }
    } else if (this.phase === 'racing' || this.phase === 'finished') this.time += h;

    // controllers
    const racing = this.phase === 'racing' || this.phase === 'finished';
    for (let k = 0; k < this.cars.length; k++) {
      const c = this.cars[k];
      if (c.driver && !c.driver.disabled && (!c.isPlayer || this.playerAI || c.autopilotOn)) {
        if (c.race.started && c._release > 0) { c._release -= h; c.veh.ctl.throttle = 0; c.veh.ctl.brake = 1; continue; }
        c.driver.update(c, this.cars, h, this.time);
      } else if (c.isPlayer && c.autopilotOn) {
        c.autopilot.update(c, this.cars, h, this.time);
      } else if (!racing && c.isPlayer) {
        const ctl = c.veh.ctl; ctl.throttle = 0; ctl.brake = 1; ctl.steer = 0; ctl.handbrake = 0; ctl.reverse = false;
      }
    }
    // catch-up (tiny and invisible): AIs far from the human player lean ±3 % on their target speed
    if (this.catchUpOn && !this.playerAI && racing) {
      const p = this.cars[0].race.progress;
      for (let k = 1; k < this.cars.length; k++) {
        const c = this.cars[k]; if (!c.driver) continue;
        const gap = p - c.race.progress;
        c.driver.catchUp = clamp((Math.abs(gap) - 45) / 140, 0, 1) * Math.sign(gap);
      }
    } else for (let k = 1; k < this.cars.length; k++) if (this.cars[k].driver) this.cars[k].driver.catchUp = 0;

    for (let k = 0; k < this.cars.length; k++) this._snapshotPrev(this.cars[k]);
    this._substeps(h, false);
    for (let k = 0; k < this.cars.length; k++) {
      const c = this.cars[k];
      this._project(c);
      this._progress(c, h);
      this._health(c, h);
      this._events(c, h);
      this._snapshotCurr(c);
    }
    this._rank();
  }

  _go() {
    this.phase = 'racing'; this.time = 0;
    this.cars.forEach((c, k) => {
      c.race.started = true; c._lapStartT = 0;
      if (c.driver) { c.driver.laneU = c.track.u; c.driver.laneS = c.track.s; c.driver.off = 0; }
      c._release = c.isPlayer ? 0 : 0.10 + 0.22 * ((k * 37) % 11) / 11;
      if (c.isPlayer && !this.playerAI) { c.veh.ctl.brake = 0; }
    });
    this.emit('race:phase', { phase: 'racing' });
  }

  _substeps(h, quiet) {
    const hs = h / SUB;
    for (let i = 0; i < SUB; i++) this.world.step(hs);
  }

  // ------------------------------------------------------------------ per-car bookkeeping
  _project(c) {
    const v = c.veh, pr = v.pr, tr = c.track;
    tr.i = pr.i; tr.s = pr.s; tr.u = pr.u; tr.hw = pr.hw;
    const R = v.R;
    const oy = v.py - R[4] * CAR.cgY - R[5] * CAR.cgZ;           // origin height
    tr.d = oy - pr.y;
  }

  _progress(c, h) {
    const T = this.track, r = c.race, tr = c.track;
    const ds = T.deltaS(c._prevS, tr.s);
    c._prevS = tr.s;
    const prev = r.progress;
    r.progress += ds;
    r.lapS = T.wrapS(tr.s - T.startS);
    if (r.finished) return;
    const L = T.length;
    const racing = this.phase === 'racing' || this.phase === 'finished';
    // lap line crossings (upward)
    const kPrev = Math.floor(prev / L), kNow = Math.floor(r.progress / L);
    if (racing && kNow > kPrev && kNow >= 1) {
      const k = kNow;                                              // k laps completed
      const frac = (k * L - prev) / Math.max(1e-6, r.progress - prev);
      const tCross = this.time - h + frac * h;
      const lapTime = tCross - c._lapStartT;
      c._lapStartT = tCross;
      r.lapTimes.push(lapTime); r.lastLap = lapTime;
      if (r.bestLap <= 0 || lapTime < r.bestLap) r.bestLap = lapTime;
      if (k >= this.laps) {
        r.finished = true; r.finishTime = tCross; r.lap = this.laps;
        this.finishedCount++;
        r.place = this.finishedCount;
        this.emit('race:lap', { car: c, lap: k, time: lapTime, best: r.bestLap });
        this.emit('race:finish', { car: c, place: r.place, time: tCross });
        if (c.isPlayer && !this.playerAI) { c.autopilotOn = true; c.autopilot.speedScale = 0.62; }
        if (c.driver) c.driver.speedScale = 0.62;
        if (c.isPlayer && this.phase === 'racing') { this.phase = 'finished'; this.emit('race:phase', { phase: 'finished' }); }
        if (this.phase !== 'finished' && this.cars[0].race.finished) { this.phase = 'finished'; }
        if (this.finishedCount === this.cars.length) this.emit('race:results', { results: this._results() });
      } else {
        r.lap = k + 1;
        this.emit('race:lap', { car: c, lap: k, time: lapTime, best: r.bestLap });
      }
    } else if (kNow < kPrev && !r.finished) {
      // crossed the line backwards: nothing to count
    }
    r.lap = Math.max(1, Math.min(this.laps, Math.floor(r.progress / L) + 1));
    // wrong way: moving against the road direction
    const v = c.veh;
    const T_i = tr.i;
    const vt = v.vx * T.tx[T_i] + v.vz * T.tz[T_i];
    if (vt < -4) c._wrongT += h; else c._wrongT = Math.max(0, c._wrongT - 2 * h);
    r.wrongWay = c._wrongT > 1.0;
  }

  _health(c, h) {
    const v = c.veh, T = this.track, tr = c.track;
    const racing = this.phase === 'racing' || this.phase === 'finished';
    if (c._ghostT > 0) {
      c._ghostT -= h;
      if (c._ghostT <= 0 && this._clearOfOthers(c, 6.5)) { c.ghost = false; c.respawning = false; v.collidable = true; c._ghostT = 0; }
      else if (c._ghostT <= 0) c._ghostT = 0.2;
    }
    if (!racing) return;
    // upside down / on its side
    if (v.R[4] < 0.25) c._flipT += h; else c._flipT = Math.max(0, c._flipT - h);
    // off the road (should not happen: walls are continuous) or fell below it
    if (Math.abs(tr.u) > tr.hw + 4 || tr.d < -2.5) c._offT += h; else c._offT = 0;
    // stationary while trying to move
    const ctl = v.ctl;
    const trying = c.isPlayer && !c.autopilotOn ? (ctl.throttle > 0.3 || (ctl.reverse && ctl.throttle > 0.3)) : (c.driver?.mode === 'reverse' || ctl.throttle > 0.3);
    if (Math.abs(v.speed) < 1.2 && trying && this.time > 2) c._slowT += h; else c._slowT = Math.max(0, c._slowT - h * 2);
    if (c._flipT > 3 || c._offT > 1.0 || c._slowT > (c.isPlayer ? 3.5 : 3.2)) this.respawn(c);
  }

  _clearOfOthers(c, d) {
    const d2 = d * d;
    for (const o of this.cars) {
      if (o === c) continue;
      const dx = o.veh.px - c.veh.px, dz = o.veh.pz - c.veh.pz;
      if (dx * dx + dz * dz < d2 && Math.abs(o.veh.py - c.veh.py) < 4) return false;
    }
    return true;
  }

  /** Put a car back on the road behind its current position at a free, safe lateral spot. */
  respawn(c, back = 5, speed = null) {
    const T = this.track, v = c.veh;
    const s0 = T.wrapS(c.track.s - back);
    let placed = false, pos = null, q = null, sFinal = s0;
    for (let attempt = 0; attempt < 10 && !placed; attempt++) {
      const s = T.wrapS(s0 - attempt * 8);
      const f = T.frameAt(s);
      const ln = this.line.n[Math.floor(s / T.ds) % T.N] ?? 0;
      const lim = Math.max(0.5, f.hw - 3.0);
      const cands = [clamp(ln, -lim, lim), 0, lim * 0.6, -lim * 0.6, lim, -lim];
      for (const u of cands) {
        const p = T.pointAt(s, u);
        let ok = true;
        for (const o of this.cars) {
          if (o === c) continue;
          const dx = o.veh.px - p.x, dz = o.veh.pz - p.z;
          if (dx * dx + dz * dz < 8.5 * 8.5 && Math.abs(o.veh.py - p.y) < 4) { ok = false; break; }
        }
        if (ok) { placed = true; pos = p; q = T.quatAt(s); sFinal = s; break; }
      }
    }
    if (!placed) { sFinal = T.wrapS(s0 - 40); pos = T.pointAt(sFinal, 0); q = T.quatAt(sFinal); }
    const sp = speed ?? (c.isPlayer ? 0 : Math.min(18, (c.driver ? c.driver.profAt(sFinal) * 0.35 : 0)));
    v.placeAt(pos, [q.x, q.y, q.z, q.w], sp);
    v.hint = this.road.seed(v.px, v.py, v.pz);
    const ctl = v.ctl; ctl.throttle = 0; ctl.brake = 0; ctl.steer = 0; ctl.handbrake = 0; ctl.reverse = false;
    c._prevS = sFinal;
    c.race.progress += T.deltaS(c.track.s, sFinal);
    c._flipT = c._offT = c._slowT = 0; c._wrongT = 0;
    c._ghostT = 2.0; c.ghost = true; c.respawning = true; v.collidable = false;
    if (c.driver) { c.driver.mode = 'drive'; c.driver.off = 0; c.driver.passCar = null; c.driver.stuckT = 0; }
    this._snapshot(c); this._snapshot(c);
    this.stats.respawns++;
    this.emit('car:respawn', { car: c, s: sFinal });
  }

  /** Place a car exactly at lap distance s / lateral offset u with a forward speed (debug / harness / cinematics). */
  teleport(c, s, u = 0, speed = 0) {
    const T = this.track, v = c.veh;
    const pos = T.pointAt(s, u), q = T.quatAt(s);
    v.placeAt(pos, [q.x, q.y, q.z, q.w], speed);
    v.hint = this.road.seed(v.px, v.py, v.pz);
    const ctl = v.ctl; ctl.throttle = 0; ctl.brake = 0; ctl.steer = 0; ctl.handbrake = 0; ctl.reverse = false;
    c.race.progress = Math.max(0, Math.floor(c.race.progress / T.length)) * T.length + T.wrapS(s - T.startS); c._prevS = T.wrapS(s);
    c._flipT = c._offT = c._slowT = 0; c._wrongT = 0;
    if (c.driver) { c.driver.mode = 'drive'; c.driver.off = 0; c.driver.passCar = null; c.driver.stuckT = 0; }
    for (let i = 0; i < 4; i++) v.wheels[i].omega = speed / CAR.wheelR;
    this._snapshot(c);
    this._substeps(1 / 120, true);
    this._project(c); this._snapshot(c);
  }

  // ------------------------------------------------------------------ events
  _events(c, h) {
    const hit = c.veh.hit;
    c._hitCool -= h; c._carCool -= h;
    if (hit.wallImpulse > 2200 && c._hitCool <= 0) {
      c._hitCool = 0.22;
      this.stats.collisions++; this.stats.wallHits++;
      this.emit('car:collision', { car: c, other: null, pos: new THREE.Vector3(hit.wallX, hit.wallY, hit.wallZ),
        normal: new THREE.Vector3(hit.wallNx, hit.wallNy, hit.wallNz), impulse: hit.wallImpulse, kind: 'wall' });
    }
    if (hit.carImpulse > 1500 && c._carCool <= 0) {
      c._carCool = 0.22;
      // each pair is reported once, for the lower id
      if (!hit.other || hit.other.id > c.veh.id) {
        this.stats.collisions++; this.stats.carHits++;
        const other = this.cars.find(o => o.veh === hit.other) ?? null;
        this.emit('car:collision', { car: c, other, pos: new THREE.Vector3(hit.carX, hit.carY, hit.carZ),
          normal: new THREE.Vector3(hit.carNx, hit.carNy, hit.carNz), impulse: hit.carImpulse, kind: 'car' });
      }
    }
    // scrape (wall or belly): keep the strongest this render frame; flushed once per frame by flushScrapes()
    let inten = hit.scrape, px = hit.scrapeX, py = hit.scrapeY, pz = hit.scrapeZ, nx = hit.scrapeNx, ny = hit.scrapeNy, nz = hit.scrapeNz;
    if (c.veh.bellyHit > 0.12 && Math.abs(c.veh.speed) > 6) {
      const b = Math.min(1, c.veh.bellyHit * Math.min(1, Math.abs(c.veh.speed) / 40));
      if (b > inten) { inten = b; px = c.veh.bellyX; py = c.veh.bellyY; pz = c.veh.bellyZ; nx = 0; ny = 1; nz = 0; }
    }
    if (inten > 0.04) {
      if (!c._scrape || inten > c._scrape.intensity) c._scrape = { intensity: inten, px, py, pz, nx, ny, nz };
    }
    hit.wallImpulse = hit.carImpulse = hit.maxWallJ = hit.maxCarJ = hit.scrape = 0; hit.other = null;
  }

  /** Called once per render frame: at most one car:scrape per car. */
  flushScrapes() {
    for (const c of this.cars) {
      const s = c._scrape; if (!s) continue;
      c._scrape = null;
      this.emit('car:scrape', { car: c, pos: new THREE.Vector3(s.px, s.py, s.pz), normal: new THREE.Vector3(s.nx, s.ny, s.nz), intensity: clamp(s.intensity, 0, 1) });
    }
  }

  // ------------------------------------------------------------------ ranking
  _rank() {
    const cars = this.cars;
    const ord = this._order; ord.length = 0;
    for (const c of cars) ord.push(c);
    ord.sort((a, b) => {
      const fa = a.race.finished, fb = b.race.finished;
      if (fa && fb) return a.race.finishTime - b.race.finishTime;
      if (fa) return -1; if (fb) return 1;
      return b.race.progress - a.race.progress;
    });
    for (let i = 0; i < ord.length; i++) {
      const c = ord[i], r = c.race;
      r.place = i + 1;
      const ahead = ord[i - 1], behind = ord[i + 1];
      const sp = Math.max(Math.abs(c.veh.speed), 20);
      r.gapAheadM = ahead ? Math.max(0, ahead.race.progress - r.progress) : null;
      r.gapAhead = ahead ? (ahead.race.finished && r.finished ? r.finishTime - ahead.race.finishTime : r.gapAheadM / sp) : null;
      if (behind) {
        const spB = Math.max(Math.abs(behind.veh.speed), 20);
        r.gapBehindM = Math.max(0, r.progress - behind.race.progress);
        r.gapBehind = behind.race.finished && r.finished ? behind.race.finishTime - r.finishTime : r.gapBehindM / spB;
      } else { r.gapBehind = null; r.gapBehindM = null; }
    }
    this.results = this._results();
  }

  _results() {
    return this._order.map((c, i) => ({ place: i + 1, car: c, name: c.name, finished: c.race.finished, time: c.race.finished ? c.race.finishTime : null,
      bestLap: c.race.bestLap > 0 ? c.race.bestLap : null, laps: c.race.lapTimes.length }));
  }

  // ------------------------------------------------------------------ snapshots for render interpolation
  _snapshotPrev(c) {
    c._p0.copy(c._p1); c._q0.copy(c._q1);
    for (let i = 0; i < 4; i++) { const a = c._w0[i], b = c._w1[i]; a.spin = b.spin; a.trav = b.trav; a.comp = b.comp; a.steer = b.steer; }
  }
  _snapshotCurr(c) {
    const v = c.veh, R = v.R;
    const ox = v.px - (R[1] * CAR.cgY + R[2] * CAR.cgZ), oy = v.py - (R[4] * CAR.cgY + R[5] * CAR.cgZ), oz = v.pz - (R[7] * CAR.cgY + R[8] * CAR.cgZ);
    c._p1.set(ox, oy, oz); c._q1.set(v.qx, v.qy, v.qz, v.qw);
    for (let i = 0; i < 4; i++) { const w = v.wheels[i], b = c._w1[i]; b.spin = w.spin; b.trav = w.travel; b.comp = w.comp; b.steer = w.steer; }
  }
  _snapshot(c) { this._snapshotPrev(c); this._snapshotCurr(c); this._snapshotPrev(c); this._snapshotCurr(c); }

  /** Fill the public (contract) state of every car, interpolated with alpha (0..1) between the last two fixed steps. */
  sync(alpha) {
    for (const c of this.cars) this.syncCar(c, alpha);
  }
  syncCar(c, alpha) {
    const v = c.veh, a = clamp(alpha, 0, 1);
    c.position.lerpVectors(c._p0, c._p1, a);
    c.quaternion.slerpQuaternions(c._q0, c._q1, a);
    c.velocity.set(v.vx, v.vy, v.vz);
    c.angularVelocity.set(v.wx, v.wy, v.wz);
    c.speed = v.speed;
    c.accel.set(v.accelLocal[0], v.accelLocal[1], v.accelLocal[2]);
    const ctl = v.ctl;
    c.input.throttle = ctl.throttle; c.input.brake = ctl.brake; c.input.steer = ctl.steer; c.input.handbrake = ctl.handbrake;
    c.input.boost = !!ctl.boost;
    c.boost.gas = v.gas; c.boost.level = v.jet;
    c.gear = ctl.reverse ? -1 : 1;
    for (let i = 0; i < 4; i++) {
      const w = v.wheels[i], o = c.wheels[i], p0 = c._w0[i], p1 = c._w1[i];
      o.steer = p0.steer + (p1.steer - p0.steer) * a;
      o.spin = p0.spin + (p1.spin - p0.spin) * a;
      o.spinRate = w.spinRate;
      o.compression = p0.comp + (p1.comp - p0.comp) * a;
      o.suspensionTravel = p0.trav + (p1.trav - p0.trav) * a;
      o.load = w.N; o.slipRatio = w.kappa; o.slipAngle = w.alpha; o.grounded = w.grounded; o.skid = w.skid;
      o.contact.set(w.cx, w.cy, w.cz);
    }
    c.motor.rpm = v.motor.rpm; c.motor.load = v.motor.load; c.motor.power = v.motor.power;
    c.brakeTemp = v.brakeTemp;
    const aFwd = -v.accelLocal[2];
    c.lights.brake = Math.max(ctl.brake, clamp((-aFwd - 1.6) / 4, 0, 1) * (v.speed > 2 ? 1 : 0));
    c.lights.reverse = !!ctl.reverse && Math.abs(v.speed) < 20;
    c.lights.head = true;
    c.gLat = v.accelLocal[0] / 9.81; c.gLong = aFwd / 9.81;
    c.airborne = v.airborne > 0.1;
    c.grip = v.surfaceGrip;
  }
}
