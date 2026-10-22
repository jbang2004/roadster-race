// Test scenarios for the vehicle model: straight-line metrics, braking, skidpad, step steer, body motion.
// They run on an infinite flat road (FlatRoad) so there are no walls and no track curvature to interfere.
import { Vehicle } from '../vehicle.js';
import { STEER, CAR } from '../params.js';

export class FlatRoad {
  constructor() { this.N = 1000; this.length = 1000; this.ds = 1; }
  seed() { return 0; }
  probe(x, z, hint, o) {
    o.i = 0; o.t = 0; o.s = -z; o.u = x; o.hw = 1e6; o.y = 0; o.nx = 0; o.ny = 1; o.nz = 0; o.rx = 1; o.rz = 0;
    o.tx = 0; o.ty = 0; o.tz = -1; o.kind = 0; o.curv = 0; o.bank = 0; return o;
  }
}

const H = 1 / 240;
const G = 9.81;
const flat = new FlatRoad();

export function newCar(speed = 0, settle = 0.8) {
  const v = new Vehicle(flat);
  v.placeAt({ x: 0, y: 0, z: 0 }, [0, 0, 0, 1], speed);
  v.coolDown();
  // settle the suspension / aero load while holding the speed with a trivial cruise controller
  for (let i = 0; i < settle * 240; i++) {
    v.ctl.throttle = Math.max(0, Math.min(1, (speed - v.speed) * 0.5 + 0.3 * (speed > 5 ? 1 : 0)));
    v.forces(H); v.integrate(H);
  }
  v.ctl.throttle = 0;
  v.px = 0; v.pz = 0;                                     // restart the odometer, keep the settled load state
  return v;
}

const dist = (v, p) => Math.hypot(v.px - p.x, v.pz - p.z);

/** Full-throttle run from standstill. */
export function accelRun(maxT = 40) {
  const v = newCar(0);
  v.ctl.throttle = 1;
  const out = { t100: 0, t200: 0, t300: 0, d400: 0, vTop: 0, peakG: 0, pitchSquat: 0, tTop: 0 };
  let t = 0, d = 0, px = v.px, pz = v.pz, topT = 0;
  const x0 = v.px, z0 = v.pz;
  for (let i = 0; i < maxT * 240; i++) {
    v.forces(H); v.integrate(H); t += H;
    const kmh = v.speed * 3.6;
    if (!out.t100 && kmh >= 100) out.t100 = t;
    if (!out.t200 && kmh >= 200) out.t200 = t;
    if (!out.t300 && kmh >= 300) out.t300 = t;
    if (!out.d400 && Math.hypot(v.px - x0, v.pz - z0) >= 400) out.d400 = t;
    out.peakG = Math.max(out.peakG, -v.accelLocal[2] / G);
    if (t < 3) out.pitchSquat = Math.max(out.pitchSquat, -pitchDeg(v));
    if (kmh > out.vTop + 0.05) { out.vTop = kmh; out.tTop = t; }
  }
  out.vTop = v.speed * 3.6;
  return out;
}

/** body pitch in degrees, + = nose DOWN (front corners compressed more than the rear) */
export function pitchDeg(v) {
  const w = v.wheels;
  const front = (w[0].travel + w[1].travel) / 2, rear = (w[2].travel + w[3].travel) / 2;
  return Math.atan2(front - rear, CAR.wheelbase) * 180 / Math.PI;
}
export function rollDeg(v) {
  const w = v.wheels;
  const left = (w[0].travel + w[2].travel) / 2, right = (w[1].travel + w[3].travel) / 2;
  return Math.atan2(left - right, 2 * CAR.halfTrack) * 180 / Math.PI;    // left compressed more → rolled to the right
}

/** Full-brake stop from v0 km/h to v1 km/h; returns distance (m), time, peak decel (g), pitch (deg). */
export function brakeRun(v0, v1 = 0) {
  const v = newCar(v0 / 3.6);
  v.ctl.brake = 1;
  let t = 0, d = 0, peak = 0, pitch = 0, px = v.px, pz = v.pz, lockMax = 0, tempMax = 0;
  for (let i = 0; i < 20 * 240; i++) {
    v.forces(H); v.integrate(H); t += H;
    d += Math.hypot(v.px - px, v.pz - pz); px = v.px; pz = v.pz;
    peak = Math.max(peak, v.accelLocal[2] / G);
    pitch = Math.max(pitch, pitchDeg(v));
    for (const w of v.wheels) if (v.speed > 5) lockMax = Math.max(lockMax, -w.kappa);
    tempMax = Math.max(tempMax, v.brakeTemp);
    if (v.speed * 3.6 <= v1 + 0.05) break;
  }
  return { dist: d, time: t, peakG: peak, pitchDeg: pitch, maxSlip: lockMax, brakeTemp: tempMax };
}

/**
 * Steady skidpad on a circle of radius R: speed ramps until the car cannot hold the circle. Returns peak lateral g and roll.
 * Uses a path-following steering controller (feed-forward + radial error), so it measures grip, not driver skill.
 */
export function skidpad(R, { ramp = 1.0, v0 = 10, maxT = 120 } = {}) {
  const v = new Vehicle(flat);
  v.placeAt({ x: 0, y: 0, z: 0 }, [0, 0, 0, 1], v0);
  const cx = R, cz = 0;
  let vt = v0, best = 0, bestV = 0, bestRoll = 0, t = 0, usGrad = 0, bestSteer = 0;
  for (let i = 0; i < maxT * 240; i++) {
    t += H; vt += ramp * H;
    const sp = v.speed;
    v.ctl.throttle = sp < vt ? Math.min(1, (vt - sp) * 0.8 + 0.12) : 0; v.ctl.brake = 0;
    const dx = v.px - cx, dz = v.pz - cz, r = Math.hypot(dx, dz), e = r - R;
    const tx = -dz / r, tz = dx / r;
    const fx = -v.R[2], fz = -v.R[8];
    const herr = Math.atan2(fx * tz - fz * tx, fx * tx + fz * tz);
    const ay = sp * sp / R;
    const steerRad = CAR.wheelbase / R + 0.0035 * ay + 0.02 * e + 0.6 * herr;
    v.ctl.steer = Math.max(-1, Math.min(1, steerRad / STEER.speedFalloff(Math.max(sp, 0))));
    v.forces(H); v.integrate(H);
    const lat = Math.abs(v.accelLocal[0]) / G;
    if (Math.abs(e) < 1.5 && lat > best) { best = lat; bestV = sp; bestRoll = rollDeg(v); bestSteer = Math.abs(v.steerAngle); }
    if (Math.abs(e) > 6 || sp < 3) break;
  }
  return { latG: best, kmh: bestV * 3.6, rollDeg: bestRoll, steerDeg: bestSteer * 57.3, end: t, steerKin: Math.atan(CAR.wheelbase / R) * 57.3 };
}

/**
 * Step steer at speed v (km/h): hold throttle to keep speed, apply a steering step of `steerFrac` of the available lock,
 * record yaw-rate response. Returns steady yaw rate, overshoot ratio, rise time, peak body slip (deg), peak lat g.
 */
export function stepSteer(kmh, steerFrac = 0.35, { dir = 1 } = {}) {
  const v = newCar(kmh / 3.6, 0.5);
  const target = kmh / 3.6;
  let t = 0, peakYaw = 0, tPeak = 0, yawEnd = 0, slipMax = 0, latMax = 0, rise = 0, t0 = 1.0;
  const rec = [];
  for (let i = 0; i < 7 * 240; i++) {
    t += H;
    v.ctl.throttle = v.speed < target ? Math.min(1, (target - v.speed) * 0.3 + 0.2) : 0.05; v.ctl.brake = 0;
    v.ctl.steer = t > t0 ? steerFrac * dir : 0;
    v.forces(H); v.integrate(H);
    const yaw = -v.wy * dir;
    if (t > t0) { rec.push(yaw); if (yaw > peakYaw) { peakYaw = yaw; tPeak = t - t0; } }
    const slip = Math.atan2(v.vLat, Math.max(1, Math.abs(v.speed))) * 57.3;
    slipMax = Math.max(slipMax, Math.abs(slip));
    latMax = Math.max(latMax, Math.abs(v.accelLocal[0]) / G);
  }
  yawEnd = rec.slice(-120).reduce((a, b) => a + b, 0) / 120;
  const t90 = rec.findIndex(y => y >= 0.9 * yawEnd) / 240;
  return { yawSteady: yawEnd, overshoot: peakYaw / Math.max(yawEnd, 1e-6), rise90: t90, slipDeg: slipMax, latG: latMax, endSpeedKmh: v.speed * 3.6 };
}

/** Lift-off oversteer check: turn at ay ≈ target (g) at speed, then lift. Returns peak yaw-rate excess (rad/s) and final stability. */
export function liftOff(kmh, R) {
  const v = newCar(kmh / 3.6, 0.3);
  v.placeAt({ x: 0, y: 0, z: 0 }, [0, 0, 0, 1], kmh / 3.6);
  const cx = R, cz = 0, target = kmh / 3.6;
  let t = 0, maxSlip = 0, maxYaw = 0, spun = false;
  for (let i = 0; i < 8 * 240; i++) {
    t += H;
    const sp = v.speed;
    v.ctl.throttle = t < 3 ? Math.min(1, (target - sp) * 0.5 + 0.15) : 0; v.ctl.brake = t > 6 ? 0.3 : 0;
    const dx = v.px - cx, dz = v.pz - cz, r = Math.hypot(dx, dz), e = r - R;
    const tx = -dz / r, tz = dx / r, fx = -v.R[2], fz = -v.R[8];
    const herr = Math.atan2(fx * tz - fz * tx, fx * tx + fz * tz);
    const steerRad = CAR.wheelbase / R + 0.0035 * sp * sp / R + (t < 3 ? 0.02 * e + 0.6 * herr : 0);
    v.ctl.steer = Math.max(-1, Math.min(1, steerRad / STEER.speedFalloff(Math.max(sp, 0))));
    v.forces(H); v.integrate(H);
    const slip = Math.abs(Math.atan2(v.vLat, Math.max(1, Math.abs(v.speed))) * 57.3);
    if (t > 3) maxSlip = Math.max(maxSlip, slip);
    maxYaw = Math.max(maxYaw, Math.abs(v.wy));
    if (slip > 70) spun = true;
  }
  return { maxSlipDeg: maxSlip, spun, maxYaw };
}

/** Roll angle of the sprung mass at a given steady lateral g (uses skidpad with a speed cap). */
export function rollAt(R, kmh) {
  const v = new Vehicle(flat);
  v.placeAt({ x: 0, y: 0, z: 0 }, [0, 0, 0, 1], kmh / 3.6);
  const cx = R, cz = 0; const target = kmh / 3.6;
  let roll = 0, lat = 0;
  for (let i = 0; i < 25 * 240; i++) {
    const sp = v.speed;
    v.ctl.throttle = Math.max(0, Math.min(1, (target - sp) * 0.6 + 0.12)); v.ctl.brake = 0;
    const dx = v.px - cx, dz = v.pz - cz, r = Math.hypot(dx, dz), e = r - R;
    const tx = -dz / r, tz = dx / r, fx = -v.R[2], fz = -v.R[8];
    const herr = Math.atan2(fx * tz - fz * tx, fx * tx + fz * tz);
    const steerRad = CAR.wheelbase / R + 0.0035 * sp * sp / R + 0.02 * e + 0.6 * herr;
    v.ctl.steer = Math.max(-1, Math.min(1, steerRad / STEER.speedFalloff(Math.max(sp, 0))));
    v.forces(H); v.integrate(H);
    if (i > 12 * 240) { roll = rollDeg(v); lat = Math.abs(v.accelLocal[0]) / G; }
  }
  return { rollDeg: Math.abs(roll), latG: lat };
}

/** Cold-gas thrusters: 100→200 km/h at full throttle with and without the boost held, how long a full tank lasts and how
 *  long it takes to refill. */
export function boostRun() {
  const run = (boost) => {
    const v = newCar(100 / 3.6); v.ctl.throttle = 1; v.ctl.boost = boost;
    let t = 0;
    while (v.speed * 3.6 < 200 && t < 20) { v.forces(H); v.integrate(H); t += H; }
    return t;
  };
  const tPlain = run(false), tBoost = run(true);
  const v = newCar(30); v.ctl.throttle = 0.4; v.ctl.boost = true;
  let t = 0, tEmpty = 0, tFull = 0;
  while (t < 10 && !tEmpty) { v.forces(H); v.integrate(H); t += H; if (v.gas <= 0) tEmpty = t; }
  v.ctl.boost = false; v.ctl.throttle = 0; t = 0;
  while (t < 40 && !tFull) { v.forces(H); v.integrate(H); t += H; if (v.gas >= 1) tFull = t; }
  return { tPlain, tBoost, tEmpty, tFull };
}
