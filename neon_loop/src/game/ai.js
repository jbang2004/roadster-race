// AI drivers. Each one drives the SAME physics as the player through throttle / brake / steer:
//  * racing line = minimum-curvature path (line.js) + a speed profile built for the driver's grip fraction,
//  * look-ahead pursuit steering with understeer feed-forward and yaw-rate damping,
//  * car avoidance: clean overtakes with a lateral offset, following when there is no room, keeping clear of cars alongside,
//  * recovery (reverse + turn) after spins / contact; the race director respawns anything stuck for good.
// No teleporting and no grip cheating; the only help is an optional, invisible catch-up of <= 3 % in target speed.

import { CAR, STEER, GRAV } from './params.js';
import { brakeLimit } from './line.js';

const clamp = (x, a, b) => (x < a ? a : x > b ? b : x);
const TWO_PI = Math.PI * 2;
const L = CAR.wheelbase;

function mulberry(seed) {
  let a = seed >>> 0;
  return () => { a = (a + 0x6D2B79F5) >>> 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
}

export class Driver {
  constructor(track, line, profile, opts) {
    this.track = track; this.line = line; this.prof = profile;
    this.skill = opts.skill; this.aggr = opts.aggr; this.cons = opts.cons;
    this.rand = mulberry(opts.seed ?? 1);
    this.ph = [this.rand() * TWO_PI, this.rand() * TWO_PI, this.rand() * TWO_PI];
    this.off = 0;                 // current lateral offset from the racing line (m)
    this.offTarget = 0;
    this.passSide = 0; this.passCar = null; this.passT = 0;
    this.mode = 'drive'; this.modeT = 0;
    this.stuckT = 0;
    this.laneU = null; this.laneS = 0;
    this.catchUp = 0;             // -1..1 set by the director
    this.speedScale = 1;          // external scaling (e.g. cool-down lap)
    this.enabled = true;
    this.dbg = {};
    this.tgtX = 0; this.tgtZ = 0;
  }

  profAt(s) {
    const T = this.track, f = T.wrapS(s) / T.ds, i = Math.floor(f) % T.N, j = (i + 1) % T.N, a = f - Math.floor(f);
    return this.prof[i] * (1 - a) + this.prof[j] * a;
  }
  lineAt(s) {
    const T = this.track, f = T.wrapS(s) / T.ds, i = Math.floor(f) % T.N, j = (i + 1) % T.N, a = f - Math.floor(f);
    return this.line.n[i] * (1 - a) + this.line.n[j] * a;
  }

  /**
   * car: race car (car.veh physics, car.track {i,s,u}); others: all cars; time: race seconds.
   * Writes veh.ctl. Returns nothing.
   */
  update(car, others, h, time) {
    const veh = car.veh, T = this.track, ctl = veh.ctl, R = veh.R;
    const v = veh.speed;
    const tr = car.track;
    const s = tr.s, hw = tr.hw ?? 8;
    const fx = -R[2], fz = -R[8];
    const fh = Math.hypot(fx, fz) || 1;
    // heading relative to the road tangent
    const i0 = tr.i;
    const tx = T.tx[i0], tz = T.tz[i0], th = Math.hypot(tx, tz) || 1;
    // signed angle from the road direction to the car heading (+ = car turned to the right of the road)
    const crossRC = (tx / th) * (fz / fh) - (tz / th) * (fx / fh);
    const dotRC = (fx * tx + fz * tz) / (fh * th);
    const rel = Math.atan2(crossRC, dotRC);                 // positive: car heading rotated to the right of the road direction

    // ------------------------------------------------ recovery logic
    this.modeT += h;
    if (this.mode === 'drive') {
      if ((Math.abs(rel) > 1.9 && v < 18) || (Math.abs(v) < 1.2 && this.stuckT > 1.4)) { this.mode = 'reverse'; this.modeT = 0; }
    } else {
      if ((Math.abs(rel) < 0.9 && Math.abs(v) < 8) || this.modeT > 3.2) { this.mode = 'drive'; this.modeT = 0; this.stuckT = 0; }
    }
    if (Math.abs(v) < 1.2 && car.race.started) this.stuckT += h; else this.stuckT = Math.max(0, this.stuckT - h * 2);
    car.stuckT = this.stuckT;

    if (this.mode === 'reverse') {
      ctl.reverse = true; ctl.throttle = v > -6 ? 0.7 : 0; ctl.brake = 0; ctl.handbrake = 0; ctl.boost = false;
      // reversing with steer δ>0 turns the car's heading to the left of its current direction
      const want = clamp(rel * 1.2, -1, 1);
      ctl.steer = want;
      if (v > 1.5) { ctl.reverse = false; ctl.throttle = 0; ctl.brake = 0.6; }   // still rolling forward → brake first
      return;
    }
    ctl.reverse = false;

    // ------------------------------------------------ neighbours
    const myU = tr.u;
    let front = null, frontDs = 1e9;
    let pushOff = 0;
    for (let k = 0; k < others.length; k++) {
      const o = others[k];
      if (o === car || !o.track || o.respawning) continue;
      const ds = T.deltaS(s, o.track.s);
      const du = o.track.u - myU;
      const adu = Math.abs(du);
      if (ds > 0 && ds < 90 && adu < 3.1 && ds < frontDs) { front = o; frontDs = ds; }
      if (Math.abs(ds) < 6.2 && adu < 3.3) {
        // someone alongside: leave room (never squeeze)
        pushOff += (du > 0 ? -1 : 1) * (3.3 - adu) * (0.9 - 0.25 * (Math.abs(ds) / 6.2));
      }
    }

    // ------------------------------------------------ speed target
    const lookS = Math.max(2.5, v * 0.16);
    let vProf = this.profAt(s + lookS);
    const wob = 1 + (1 - this.cons) * 0.55 * (Math.sin(time * 0.37 + this.ph[0]) * 0.6 + Math.sin(time * 0.91 + this.ph[1]) * 0.4);
    let vT = vProf * wob * this.speedScale * (1 + 0.03 * this.catchUp);
    // when away from the line towards the inside of a corner the real radius is smaller
    const lk = this.line.kappa[i0];
    if (lk !== 0 && this.off * lk < 0) {                  // offset is toward the centre of the turn (n is + right, kappa is + left)
      const k2 = Math.abs(lk) / Math.max(0.35, 1 - Math.abs(lk) * Math.abs(this.off));
      vT *= Math.sqrt(Math.abs(lk) / k2);
    }
    vT *= 1 - 0.012 * Math.min(Math.abs(this.off), 6);

    // ------------------------------------------------ overtaking / following
    let vCap = 1e9;
    let wantOff = 0;
    const gapBumper = front ? frontDs - CAR.box.hz * 2 : 1e9;
    if (this.passCar) {
      const ds = T.deltaS(s, this.passCar.track.s);
      this.passT += h;
      if (ds < -8.5 || this.passT > 9 || this.passCar.respawning) { this.passCar = null; this.passSide = 0; }
    }
    if (front) {
      const vf = front.veh.speed;
      const closing = v - vf;
      const wantPass = (vT > vf + 1.2 && closing > -0.5) || (gapBumper < 6 && closing > 1.0);
      const lanesFree = this.laneU == null || s - this.laneS > 740;          // nobody overtakes on the grid straight
      if (!this.passCar && wantPass && lanesFree && v > 14 && gapBumper < 22 + Math.max(0, closing) * (1.1 + 0.6 * this.aggr)) {
        // choose a side with room
        const u0 = front.track.u;
        const room = (side) => {
          const edge = side < 0 ? -hw + 1.5 : hw - 1.5;
          const space = side < 0 ? (u0 - 1.15) - edge : edge - (u0 + 1.15);
          // another car already in that lane next to the target?
          let blocked = false;
          for (let k = 0; k < others.length; k++) {
            const o = others[k]; if (o === car || o === front || !o.track) continue;
            const ds = T.deltaS(s, o.track.s);
            if (ds > -8 && ds < frontDs + 8 && Math.abs(o.track.u - (u0 + side * 2.6)) < 2.3) blocked = true;
          }
          return blocked ? -1 : space;
        };
        const rl = room(-1), rr = room(1);
        if (Math.max(rl, rr) > 2.1) {
          // prefer the side that suits the next corner: keep a slight bias to the side we are already on
          const pick = (rl > 2.1 && rr > 2.1) ? (rl + (myU < front.track.u ? 0.8 : 0) > rr + (myU >= front.track.u ? 0.8 : 0) ? -1 : 1) : (rl > rr ? -1 : 1);
          this.passSide = pick; this.passCar = front; this.passT = 0;
        }
      }
      if (this.passCar === front) {
        const uT = front.track.u + this.passSide * (2.45 + 0.35 * (1 - this.aggr));
        wantOff = clamp(uT, -hw + 1.5, hw - 1.5) - this.lineAt(s + Math.max(6, v * 0.25));
      } else {
        // no room / not allowed to pass: follow with a time gap
        const gapWant = 6 + v * 0.10;
        vCap = vf + clamp((gapBumper - gapWant) * 0.3, -6, 10);
      }
      // never run into the back of anyone: we must be able to shed the closing speed at ~3.5 m/s² before the gap is gone
      if (!this.passCar || Math.abs(front.track.u - myU) < 2.3) {
        const gmin = (3.2 + 0.055 * Math.max(v, 0)) * (1.12 - 0.3 * this.aggr);
        const ac = front.veh.speed - (front.veh.prevSpeed ?? front.veh.speed) < -0.05 ? 2.6 : 3.4;       // lead car braking → more margin
        const vSafe = gapBumper >= gmin ? vf + Math.sqrt(2 * ac * (gapBumper - gmin)) : vf - 3 * (gmin - gapBumper);
        vCap = Math.min(vCap, vSafe);
      }
    }
    if (!front && this.passCar) {
      // keep the passing offset until we're clear of the car
      const u0 = this.passCar.track.u;
      wantOff = clamp(u0 + this.passSide * 2.45, -hw + 1.5, hw - 1.5) - this.lineAt(s + Math.max(6, v * 0.25));
    }
    // starting lane: stay in the grid column until the pack has spread out, then blend onto the line
    if (this.laneU != null) {
      const ds = s - this.laneS;
      const w = 1 - clamp((ds - 740) / 320, 0, 1);       // hold the grid column to the first corner, then merge onto the line
      if (ds > 1080 || ds < -50) this.laneU = null;
      else if (!this.passCar) wantOff += (this.laneU - this.lineAt(s + Math.max(6, v * 0.25))) * w * w * (3 - 2 * w);
    }
    // ease the offset
    wantOff += pushOff * 0.85;
    {
      const room = this.lineAt(s + 8);
      wantOff = clamp(wantOff, -(hw - 1.5) - room, (hw - 1.5) - room);     // keep line+offset inside the road
    }
    const rate = (this.passCar ? 2.2 : 1.4) * h;
    this.off += clamp(wantOff - this.off, -rate, rate);
    vT = Math.min(vT, vCap);

    // ------------------------------------------------ steering: pure pursuit at a look-ahead point
    const Ld = clamp(5 + 0.30 * Math.max(v, 0), 6.5, 36);
    const sT = s + Ld;
    const f = T.wrapS(sT) / T.ds, ia = Math.floor(f) % T.N, ib = (ia + 1) % T.N, aa = f - Math.floor(f);
    const nT = clamp(this.lineAt(sT) + this.off, -(T.hw[ia] - 1.45), T.hw[ia] - 1.45);
    const rx = T.rx[ia] * (1 - aa) + T.rx[ib] * aa, rz = T.rz[ia] * (1 - aa) + T.rz[ib] * aa, rh = Math.hypot(rx, rz);
    const tgx = T.px[ia] * (1 - aa) + T.px[ib] * aa + rx / rh * nT;
    const tgz = T.pz[ia] * (1 - aa) + T.pz[ib] * aa + rz / rh * nT;
    this.tgtX = tgx; this.tgtZ = tgz;
    const dx = tgx - veh.px, dz = tgz - veh.pz;
    const dl = Math.hypot(dx, dz) || 1;
    const cr = (fx / fh) * (dz / dl) - (fz / fh) * (dx / dl);       // + : target is to the right
    const dt_ = (fx / fh) * (dx / dl) + (fz / fh) * (dz / dl);
    const eta = Math.atan2(cr, dt_);
    let delta = Math.atan2(2 * L * Math.sin(eta), dl);
    const kap = Math.tan(delta) / L;
    // understeer feed-forward (rad per m/s² of lateral accel) + yaw-rate damping
    const ay = v * v * kap;
    delta += 0.0031 * ay;
    const yawRight = -veh.wy;
    delta += 0.07 * clamp((v * kap - yawRight), -0.6, 0.6) * clamp(v / 20, 0, 1);
    const maxAng = STEER.speedFalloff(Math.max(v, 0));
    ctl.steer = clamp(delta / maxAng, -1, 1);

    // ------------------------------------------------ longitudinal
    let thr = 0, brk = 0;
    const verr = vT - v;
    if (verr > 0) thr = clamp(verr * 0.55 + 0.04, 0, 1);
    else brk = clamp(-verr * 0.25 - 0.015, 0, 1);
    // braking safety: look ahead on the profile (what decel is needed to meet it?)
    let aNeed = 0;
    for (let d = 18; d <= 260; d += 14 + d * 0.18) {
      const vp = this.profAt(s + d) * this.speedScale * 1.0;
      if (vp < v) aNeed = Math.max(aNeed, (v * v - vp * vp) / (2 * d));
    }
    const cap = brakeLimit(v) * 0.95;
    if (aNeed > 0.55 * cap) { brk = Math.max(brk, clamp((aNeed - 0.45 * cap) / (0.55 * cap), 0, 1)); thr = 0; }
    if (brk > 0.02) thr = 0;
    if (!car.race.started) { thr = 0; brk = 1; }
    ctl.throttle = thr; ctl.brake = brk; ctl.handbrake = 0;
    // cold-gas thrusters on a long clear straight: fire with a fullish tank (aggressive drivers sooner), hold while it lasts
    const straight = car.race.started && thr > 0.95 && Math.abs(ctl.steer) < 0.1 && aNeed < 0.2 * cap && vT - v > 5 && v > 22;
    ctl.boost = straight && (veh.jet > 0.05 ? veh.gas > 0.02 : veh.gas > 0.5 + 0.4 * (1 - this.aggr));
    this.dbg.vT = vT; this.dbg.eta = eta; this.dbg.off = this.off;
  }
}

/** Seeded driver set: returns Driver instances sharing one racing line, each with its own speed profile. */
export function makeDrivers(track, line, buildProfile, roster, seed = 7) {
  return roster.map((d, i) => new Driver(track, line, buildProfile(d.skill), { ...d, seed: seed * 101 + i * 17 + 3 }));
}
