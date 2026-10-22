// Vehicle dynamics: 6-DOF rigid body (CG frame), four raycast suspension corners against the road plane, Pacejka-style
// tyres with combined slip and relaxation, dual-motor AWD EV drivetrain with regen, brakes with ABS and temperature,
// aero. Pure JS (no DOM / WebGL) so it runs in Node. Forces are accumulated in `forces(h)`; collisions are resolved by
// the physics world between `forces` and `integrate` (see world.js).
//
// Frames: car frame x right, y up, z back (forward = -z), origin on the ground between the axles at rest.
// The body state is that of the CG: the rendered pose is the car-frame origin (see `originPose`).

import { CAR, SUSP, TYRE, AERO, DRIVE, BRAKE, STEER, ASSIST, THRUST, GRAV, RHO } from './params.js';
import { Tyre } from './tyre.js';
import { roughness } from './road.js';

const clamp = (x, a, b) => (x < a ? a : x > b ? b : x);
const smooth = (a, b, x) => { const t = clamp((x - a) / (b - a), 0, 1); return t * t * (3 - 2 * t); };

// ---- static derived numbers ------------------------------------------------------------------------------------
const L = CAR.wheelbase;
const aF = CAR.cgZ - CAR.zFront;            // CG to front axle
const aR = CAR.zRear - CAR.cgZ;             // CG to rear axle
const mF = CAR.mass * aR / L * 0.5;         // sprung mass per front corner
const mR = CAR.mass * aF / L * 0.5;
const GEOM = [
  { x: -CAR.halfTrack, z: CAR.zFront, front: true, left: true },
  { x: CAR.halfTrack, z: CAR.zFront, front: true, left: false },
  { x: -CAR.halfTrack, z: CAR.zRear, front: false, left: true },
  { x: CAR.halfTrack, z: CAR.zRear, front: false, left: false },
];

function springForce(x, k0, xRub) {
  let F = k0 * x;
  if (x > xRub) F += k0 * SUSP.rubberRate * (x - xRub);
  return F;
}
function solveStatic(load, k0) {
  // x_s such that spring force = load (rubber not engaged at rest by construction)
  return load / k0;
}

export const RIDE = (() => {
  const kF = mF * (2 * Math.PI * SUSP.freqF) ** 2, kR = mR * (2 * Math.PI * SUSP.freqR) ** 2;
  const xsF = solveStatic(mF * GRAV, kF), xsR = solveStatic(mR * GRAV, kR);
  return { kF, kR, xsF, xsR, cF: 2 * Math.sqrt(kF * mF), cR: 2 * Math.sqrt(kR * mR) };
})();

export const TOP_SPEED_HINT = 92;

const WALL_PTS = (() => {
  const pts = [];
  const hx = CAR.box.hx, hz = CAR.box.hz, y = 0.55;
  for (const z of [-hz, -1.6, -0.8, 0, 0.8, 1.6, hz]) for (const x of [-hx, hx]) pts.push([x, y, z]);
  for (const x of [-0.55, 0, 0.55]) { pts.push([x, y, -hz]); pts.push([x, y, hz]); }
  return pts;
})();
const BELLY_PTS = [
  [-0.95, 0.12, -2.25], [0.95, 0.12, -2.25], [-0.95, 0.12, -0.8], [0.95, 0.12, -0.8],
  [-0.95, 0.12, 0.9], [0.95, 0.12, 0.9], [-0.95, 0.12, 2.25], [0.95, 0.12, 2.25],
  [0, 0.10, -2.3], [0, 0.10, 2.3],
  [-0.85, 1.30, -0.4], [0.85, 1.30, -0.4], [-0.85, 1.30, 1.1], [0.85, 1.30, 1.1],     // roof
];

export class Vehicle {
  constructor(road, id = 0) {
    this.road = road;
    this.id = id;
    this.mass = CAR.mass;
    this.invMass = 1 / CAR.mass;
    this.I = [CAR.inertia.x, CAR.inertia.y, CAR.inertia.z];
    // state (CG)
    this.px = 0; this.py = 0; this.pz = 0;
    this.qx = 0; this.qy = 0; this.qz = 0; this.qw = 1;
    this.vx = 0; this.vy = 0; this.vz = 0;
    this.wx = 0; this.wy = 0; this.wz = 0;
    this.R = new Float64Array(9);            // rotation matrix, columns = right, up, back
    this.IinvW = new Float64Array(9);
    // controls
    this.ctl = { throttle: 0, brake: 0, steer: 0, handbrake: 0, reverse: false, boost: false };
    this.assist = { ...ASSIST };
    this.thr = 0;                             // smoothed throttle
    this.steerAngle = 0;                      // actuator state (rad, + right)
    // road
    this.hint = 0;
    this.pr = {};                             // CG probe
    // wheels
    this.wheels = GEOM.map((g, k) => {
      const front = g.front, ks = front ? RIDE.kF : RIDE.kR, xs = front ? RIDE.xsF : RIDE.xsR;
      return {
        k, front, left: g.left, x: g.x, z: g.z, tyre: new Tyre(front ? TYRE.front : TYRE.rear),
        kSpring: ks, xStatic: xs, cDamp: front ? RIDE.cF : RIDE.cR,
        hy: CAR.wheelR + SUSP.free - xs,      // hardpoint height in the car frame
        ell: SUSP.free - xs, comp: xs, compPrev: xs, travel: 0,
        omega: 0, spin: 0, spinRate: 0, steer: 0,
        alphaF: 0, alpha: 0, kappa: 0, slipS: 0, skid: 0, Fz: 0, N: 0, FzGeo: 0,
        grounded: false, hint: 0, pr: {}, un: 1, hx: 0, hy_w: 0, hz: 0, brakeP: 0,
        cx: 0, cy: 0, cz: 0,                   // contact point (world)
        fxW: 0, fyW: 0, fyChassis: 0, fxChassis: 0,
        tc: 1, abs: 1, brakeT: BRAKE.tAmb, Tdrive: 0, Tbrake: 0,
        nx: 0, ny: 1, nz: 0,
      };
    });
    this.gForceGeo = { fyAxle: [0, 0], fxTot: 0 };
    // outputs / telemetry
    this.speed = 0; this.vLat = 0; this.yawRate = 0;
    this.accW = [0, 0, 0];                    // specific force (world, no gravity)
    this.accelLocal = [0, 0, 0];              // smoothed, car frame
    this.motor = { rpm: 0, load: 0, power: 0 };
    this.brakeTemp = 0;
    this.gas = 1;                             // thruster tank, 0..1
    this.jet = 0;                             // thruster valve opening, 0..1
    this._gasIdle = 9; this._jetLock = false;
    this.airborne = 0;
    this.lastScrapeIntensity = 0;
    this.bellyHit = 0;
    this.noContactTime = 0;
    this.collidable = true;
    this.surfaceGrip = 1;
    this.uProj = 0;
    this.deadTime = 0;
    this._tmp = { x: 0, y: 0, z: 0 };
    this.updateRotation();
  }

  // ---------- pose ----------
  updateRotation() {
    const x = this.qx, y = this.qy, z = this.qz, w = this.qw, R = this.R;
    const xx = x * x, yy = y * y, zz = z * z, xy = x * y, xz = x * z, yz = y * z, wx = w * x, wy = w * y, wz = w * z;
    R[0] = 1 - 2 * (yy + zz); R[1] = 2 * (xy - wz); R[2] = 2 * (xz + wy);
    R[3] = 2 * (xy + wz); R[4] = 1 - 2 * (xx + zz); R[5] = 2 * (yz - wx);
    R[6] = 2 * (xz - wy); R[7] = 2 * (yz + wx); R[8] = 1 - 2 * (xx + yy);
    // inverse inertia in world: R diag(1/I) R^T
    const i0 = 1 / this.I[0], i1 = 1 / this.I[1], i2 = 1 / this.I[2], W = this.IinvW;
    for (let a = 0; a < 3; a++) for (let b = 0; b < 3; b++) {
      W[a * 3 + b] = R[a * 3] * R[b * 3] * i0 + R[a * 3 + 1] * R[b * 3 + 1] * i1 + R[a * 3 + 2] * R[b * 3 + 2] * i2;
    }
  }
  /** world position of a car-frame point */
  toWorld(cx, cy, cz, out) {
    const R = this.R, dx = cx, dy = cy - CAR.cgY, dz = cz - CAR.cgZ;
    out.x = this.px + R[0] * dx + R[1] * dy + R[2] * dz;
    out.y = this.py + R[3] * dx + R[4] * dy + R[5] * dz;
    out.z = this.pz + R[6] * dx + R[7] * dy + R[8] * dz;
    return out;
  }
  /** car-frame origin (render position) */
  originPose(out) { return this.toWorld(0, 0, 0, out); }

  /** Place the car sitting at rest with its car-frame origin at `pos`, orientation q = [x,y,z,w], and a forward speed. */
  placeAt(pos, q, speed = 0, vel = null) {
    this.qx = q[0]; this.qy = q[1]; this.qz = q[2]; this.qw = q[3];
    this.updateRotation();
    const R = this.R, dx = 0, dy = CAR.cgY, dz = CAR.cgZ;
    this.px = pos.x + R[0] * dx + R[1] * dy + R[2] * dz;
    this.py = pos.y + R[3] * dx + R[4] * dy + R[5] * dz;
    this.pz = pos.z + R[6] * dx + R[7] * dy + R[8] * dz;
    // forward = -back axis
    this.vx = -R[2] * speed; this.vy = -R[5] * speed; this.vz = -R[8] * speed;
    if (vel) { this.vx = vel.x; this.vy = vel.y; this.vz = vel.z; }
    this.wx = this.wy = this.wz = 0;
    this.speed = speed; this.vLat = 0; this.jet = 0;
    this.hint = this.road.seed(this.px, this.py, this.pz);
    for (const w of this.wheels) {
      w.comp = w.compPrev = w.xStatic; w.ell = SUSP.free - w.xStatic; w.travel = 0; w.hint = this.hint;
      w.alphaF = 0; w.omega = speed / CAR.wheelR; w.fyChassis = w.fxChassis = 0; w.tc = w.abs = 1; w.FzGeo = 0;
      w.grounded = true;
    }
    this.thr = 0; this.steerAngle = 0;
    this.gForceGeo.fyAxle[0] = this.gForceGeo.fyAxle[1] = 0; this.gForceGeo.fxTot = 0;
    this.deadTime = 0; this.airborne = 0; this.noContactTime = 0;
    this.accW[0] = this.accW[1] = this.accW[2] = 0;
    this.accelLocal[0] = this.accelLocal[1] = this.accelLocal[2] = 0;
  }

  // ---------- helpers ----------
  /** speed of the CG along the car's forward axis, and lateral (right) component */
  bodyVel() {
    const R = this.R;
    const vf = -(this.vx * R[2] + this.vy * R[5] + this.vz * R[8]);
    const vr = this.vx * R[0] + this.vy * R[3] + this.vz * R[6];
    this.speed = vf; this.vLat = vr;
    return vf;
  }

  // ---------- force computation (one sub-step) ----------
  forces(h) {
    const R = this.R, ctl = this.ctl, W = this.wheels, road = this.road, pr = this.pr;
    const m = this.mass, g = GRAV;
    const rgx = R[0], rgy = R[3], rgz = R[6];      // right
    const ux = R[1], uy = R[4], uz = R[7];         // up
    const fx_ = -R[2], fy_ = -R[5], fz_ = -R[8];   // forward
    this.prevSpeed = this.speed;
    const vf = this.bodyVel();
    const vabs = Math.hypot(this.vx, this.vy, this.vz);

    // chassis road probe (plane for belly contacts)
    road.probe(this.px, this.pz, this.hint, pr);
    this.hint = pr.i; this.uProj = pr.u;

    // accumulators
    let Fx = 0, Fy = -m * g, Fz = 0, Tx = 0, Ty = 0, Tz = 0;
    let Sx = 0, Sy = 0, Sz = 0;                      // specific-force accumulator (no gravity)
    const cgx = this.px, cgy = this.py, cgz = this.pz;
    const addF = (fx, fy, fz, ax, ay, az) => {       // force at world point a
      Fx += fx; Fy += fy; Fz += fz; Sx += fx; Sy += fy; Sz += fz;
      const rx = ax - cgx, ry = ay - cgy, rz = az - cgz;
      Tx += ry * fz - rz * fy; Ty += rz * fx - rx * fz; Tz += rx * fy - ry * fx;
    };

    // ---- steering actuator
    const vsteer = Math.max(Math.abs(vf), 0);
    const maxAng = STEER.speedFalloff(vsteer);
    let target = clamp(ctl.steer, -1, 1) * maxAng;
    // ---- stability assist (ESC-lite): trims the steering when the car yaws more than the driver's request / the grip allow,
    // and counter-steers a sliding rear. Understeer is left alone (more lock cannot help). Off with the handbrake.
    this.escActive = 0;
    const stab = this.assist.stability;
    if (stab > 0 && vf > 7 && ctl.handbrake < 0.2 && !ctl.reverse) {
      const rYaw = -(R[1] * this.wx + R[4] * this.wy + R[7] * this.wz);              // + = turning right
      const kinGain = vf / (L + 0.0040 * vf * vf);
      const aMax = 12.5 + 0.0003 * vf * vf;
      const rLim = aMax / vf;
      const rRef = clamp(kinGain * target, -rLim, rLim);
      const err = rYaw - rRef;
      const ref = Math.abs(rRef) > 0.02 ? Math.sign(rRef) : Math.sign(rYaw);
      const over = err * ref;                                                         // > 0 : rotating more than requested
      let corr = 0;
      if (over > 0.10) corr = -clamp((err - 0.10 * ref) * 0.14, -0.4 * maxAng - 0.015, 0.4 * maxAng + 0.015) * stab;
      // sliding rear: body slip beyond ~8° with the yaw rate going the same way → steer towards the velocity direction
      const beta = Math.atan2(this.vLat, Math.max(vf, 3));
      const bAbs = Math.abs(beta);
      if (bAbs > 0.14 && Math.sign(rYaw) === Math.sign(-beta)) corr += Math.sign(beta) * clamp((bAbs - 0.14) * 1.1, 0, 0.55 * maxAng) * stab * (1 - Math.abs(ctl.steer) * 0.4);
      target = clamp(target + corr, -STEER.maxLock, STEER.maxLock);
      this.escActive = Math.min(1, Math.abs(corr) / (0.3 * maxAng + 0.01));
      // power-on oversteer: trim torque when the body slip is large
      this.escThr = 1 - 0.75 * stab * smooth(0.15, 0.32, Math.abs(beta));
    } else this.escThr = 1;
    const dmax = STEER.rate * h * (1 + 1.5 * (1 - smooth(0, 30, vsteer)));
    this.steerAngle += clamp(target - this.steerAngle, -dmax, dmax);
    // Ackermann
    const dl = this.steerAngle;
    let dFL = dl, dFR = dl;
    if (Math.abs(dl) > 1e-4) {
      const tn = Math.tan(dl), ht = CAR.halfTrack;
      const inner = Math.atan(L * tn / (L - ht * Math.abs(tn))), outer = Math.atan(L * tn / (L + ht * Math.abs(tn)));
      if (dl > 0) { dFR = inner; dFL = outer; } else { dFL = inner; dFR = outer; }
    }
    W[0].steer = dFL; W[1].steer = dFR; W[2].steer = 0; W[3].steer = 0;

    // ---- suspension geometry: compression for each wheel
    for (let k = 0; k < 4; k++) {
      const w = W[k];
      // hardpoint world
      const dx = w.x, dy = w.hy - CAR.cgY, dz = w.z - CAR.cgZ;
      const hx = cgx + R[0] * dx + R[1] * dy + R[2] * dz;
      const hy = cgy + R[3] * dx + R[4] * dy + R[5] * dz;
      const hz = cgz + R[6] * dx + R[7] * dy + R[8] * dz;
      const ex = hx - ux * w.ell, ez = hz - uz * w.ell;
      const p2 = road.probe(ex, ez, w.hint, w.pr);
      w.hint = p2.i;
      const yRoad = p2.y + roughness(p2.s, p2.u, p2.kind);
      const nx = p2.nx, ny = p2.ny, nz = p2.nz;
      // (H - P) . n  with P = (ex, yRoad, ez)
      const dn = (hx - ex) * nx + (hy - yRoad) * ny + (hz - ez) * nz;
      const un = ux * nx + uy * ny + uz * nz;
      w.nx = nx; w.ny = ny; w.nz = nz; w.un = un;
      w.hx = hx; w.hy_w = hy; w.hz = hz;
      if (un > 0.35) {
        const ell = (dn - CAR.wheelR) / un;
        w.ell = clamp(ell, SUSP.free - SUSP.travelMax - 0.08, SUSP.free);
        const x = SUSP.free - ell;
        w.comp = x > 0 ? x : 0;
        w.grounded = x > 0;
      } else { w.ell = SUSP.free; w.comp = 0; w.grounded = false; }
    }

    // ---- suspension forces + tyre loads
    const arbF = SUSP.arbF * (W[0].comp - W[1].comp), arbR = SUSP.arbR * (W[2].comp - W[3].comp);
    const gg = this.gForceGeo;
    const geoRollF = gg.fyAxle[0] * SUSP.appH / (2 * CAR.halfTrack), geoRollR = gg.fyAxle[1] * SUSP.appH / (2 * CAR.halfTrack);
    const geoPitch = gg.fxTot * SUSP.appH / L;
    let grounded = 0;
    for (let k = 0; k < 4; k++) {
      const w = W[k];
      if (!w.grounded) { w.N = 0; w.Fz = 0; w.travel = 0; w.compPrev = w.comp; w.spinLoss = 0; continue; }
      grounded++;
      const xs = w.xStatic, x = w.comp;
      let Fk = springForce(x, w.kSpring, xs + SUSP.rubberAt);
      if (x > SUSP.travelMax) Fk += 1.2e6 * (x - SUSP.travelMax);
      let v = (x - w.compPrev) / h;
      v = clamp(v, -6, 6);
      const zeta = v > 0 ? SUSP.zetaBump : SUSP.zetaReb;
      const c = zeta * w.cDamp, vk = SUSP.kneeV;
      const av = Math.abs(v);
      const Fd = Math.sign(v) * c * (Math.min(av, vk) + SUSP.postKnee * Math.max(0, av - vk));
      let arb = w.front ? arbF : arbR;
      if (!w.left) arb = -arb;
      let Fs = Fk + Fd + arb;
      if (Fs < 0) Fs = 0;
      w.compPrev = x;
      w.travel = x - xs;
      const N = Fs / Math.max(0.5, w.un);
      w.N = N;
      // geometric load transfer (acts on tyre grip only)
      let geo = (w.front ? geoRollF : geoRollR) * (w.left ? 1 : -1);
      geo += (w.front ? -1 : 1) * geoPitch * 0.5;
      w.FzGeo += (geo - w.FzGeo) * Math.min(1, h * 60);
      w.Fz = Math.max(0.12 * N, N + w.FzGeo);
    }
    this.airborne = grounded === 0 ? this.airborne + h : 0;

    // ---- aero
    const vdx = this.vx, vdy = this.vy, vdz = this.vz;
    const q2 = 0.5 * RHO;
    const vfwd = vf, vside = this.vLat;
    const dragK = q2 * AERO.CdA * vabs;
    {
      const ax = this.px + R[1] * (AERO.dragY - CAR.cgY), ay = this.py + R[4] * (AERO.dragY - CAR.cgY), az = this.pz + R[7] * (AERO.dragY - CAR.cgY);
      addF(-dragK * vdx, -dragK * vdy, -dragK * vdz, ax, ay, az);
    }
    {
      // downforce ~ forward speed², along -up, split front / rear axle
      const vdf = vfwd > 0 ? vfwd : 0;
      const DF = q2 * AERO.ClA * vdf * vdf * (1 - 0.35 * Math.min(1, Math.abs(vside) / (Math.abs(vfwd) + 6)));
      for (const [frac, zz] of [[AERO.balanceF, CAR.zFront + 0.35], [1 - AERO.balanceF, CAR.zRear - 0.25]]) {
        const dx = 0, dy = 0.30 - CAR.cgY, dz = zz - CAR.cgZ;
        const ax = this.px + R[0] * dx + R[1] * dy + R[2] * dz, ay = this.py + R[3] * dx + R[4] * dy + R[5] * dz, az = this.pz + R[6] * dx + R[7] * dy + R[8] * dz;
        const f = DF * frac;
        addF(-ux * f, -uy * f, -uz * f, ax, ay, az);
      }
      // side force behind the CG (weathervane): opposes lateral velocity
      const fs = -q2 * AERO.CyA * Math.abs(vside) * vside;
      const dz = AERO.pressureZ;
      const ax = this.px + R[2] * dz, ay = this.py + R[5] * dz, az = this.pz + R[8] * dz;
      addF(rgx * fs, rgy * fs, rgz * fs, ax, ay, az);
    }

    // ---- cold-gas thrusters: push along the car's forward axis at the nozzles while the valve is open; fade near top speed
    if (this.gas <= 0) this._jetLock = true;
    if (this._jetLock && (!ctl.boost || this.gas > THRUST.relock)) this._jetLock = false;
    const jetWant = ctl.boost && !this._jetLock && !ctl.reverse ? 1 : 0;
    this.jet += (jetWant - this.jet) * Math.min(1, h * (jetWant ? THRUST.open : THRUST.close));
    if (this.jet > 0.002) {
      const F = THRUST.force * this.jet * (1 - smooth(THRUST.vFade[0], THRUST.vFade[1], vf));
      const dy = THRUST.y - CAR.cgY, dz = THRUST.z - CAR.cgZ;
      addF(fx_ * F, fy_ * F, fz_ * F, this.px + R[1] * dy + R[2] * dz, this.py + R[4] * dy + R[5] * dz, this.pz + R[7] * dy + R[8] * dz);
    }
    if (jetWant) { this.gas = Math.max(0, this.gas - h * this.jet / THRUST.duration); this._gasIdle = 0; }
    else if ((this._gasIdle += h) > THRUST.refillDelay) this.gas = Math.min(1, this.gas + h / THRUST.refill);

    // ---- powertrain & tyres
    this._powertrain(h, vf);
    let fyAxle0 = 0, fyAxle1 = 0, fxTot = 0;
    for (let k = 0; k < 4; k++) {
      const w = W[k];
      if (!w.grounded || w.un <= 0.35) {
        // airborne wheel: spin freely, brakes still bite
        this._spinFree(w, h);
        w.slipS = 0; w.skid = 0; w.kappa = 0; w.alpha = 0; w.fxChassis = w.fyChassis = 0;
        continue;
      }
      // wheel centre and contact patch
      const ell = w.ell;
      const wcx = w.hx - ux * ell, wcy = w.hy_w - uy * ell, wcz = w.hz - uz * ell;
      const cx = wcx - w.nx * CAR.wheelR, cy = wcy - w.ny * CAR.wheelR, cz = wcz - w.nz * CAR.wheelR;
      w.cx = cx; w.cy = cy; w.cz = cz;
      // wheel heading (steered chassis forward) projected on the road plane
      const cs = Math.cos(w.steer), sn = Math.sin(w.steer);
      let hx = fx_ * cs + rgx * sn, hy = fy_ * cs + rgy * sn, hz = fz_ * cs + rgz * sn;
      const hn = hx * w.nx + hy * w.ny + hz * w.nz;
      hx -= w.nx * hn; hy -= w.ny * hn; hz -= w.nz * hn;
      const hl = Math.hypot(hx, hy, hz) || 1; hx /= hl; hy /= hl; hz /= hl;
      // right = heading x normal
      const lx = hy * w.nz - hz * w.ny, ly = hz * w.nx - hx * w.nz, lz = hx * w.ny - hy * w.nx;
      // contact velocity
      const rx = cx - cgx, ry = cy - cgy, rz = cz - cgz;
      const cvx = this.vx + this.wy * rz - this.wz * ry;
      const cvy = this.vy + this.wz * rx - this.wx * rz;
      const cvz = this.vz + this.wx * ry - this.wy * rx;
      const vlong = cvx * hx + cvy * hy + cvz * hz;
      const vlat = cvx * lx + cvy * ly + cvz * lz;
      const den = Math.sqrt(vlong * vlong + TYRE.vReg * TYRE.vReg);
      const alphaRaw = Math.atan2(-vlat, den);
      const sigma = w.tyre.p.sigma;
      const kr = 1 - Math.exp(-h * (Math.abs(vlong) + 1.5) / sigma);
      w.alphaF += (alphaRaw - w.alphaF) * kr;
      const grip = this.surfaceGrip * TYRE.wetGrip;
      const Fzg = w.Fz;
      const R_ = CAR.wheelR, I = CAR.wheelInertia;
      const tyre = w.tyre;
      const kap0 = (w.omega * R_ - vlong) / den;
      tyre.force(kap0, w.alphaF, Fzg, grip);
      let fxT = tyre.fx, fyT = tyre.fy;
      const s0 = tyre.s;
      const dK = 0.01;
      tyre.force(kap0 + dK, w.alphaF, Fzg, grip);
      const dFdK = (tyre.fx - fxT) / dK;
      const dFdw = Math.max(0, dFdK * R_ / den);
      // wheel torques: drive (set by powertrain), rolling resistance, brake (locks at zero)
      const Troll = TYRE.crr * Fzg * R_ * Math.tanh(w.omega / 1.5);
      const Tnet = w.Tdrive - Troll;
      const dOmega = h * (Tnet - R_ * fxT) / (I + h * R_ * dFdw);
      let om = w.omega + dOmega;
      const dwb = h * w.Tbrake / I;
      if (dwb > 0) { if (Math.abs(om) <= dwb) om = 0; else om -= Math.sign(om) * dwb; }
      const fxUsed = clamp(fxT + dFdw * (om - w.omega), -1.3 * tyre.mux * Fzg, 1.3 * tyre.mux * Fzg);
      w.spinRate = om; w.omega = om;
      w.spin += om * h;
      w.kappa = (om * R_ - vlong) / den;
      w.alpha = w.alphaF;
      w.slipS = s0;
      w.skid = smooth(0.85, 2.2, Math.max(s0, Math.abs(w.kappa) / 0.2)) * (Fzg > 200 ? 1 : 0);
      w.fxW = fxUsed; w.fyW = fyT;
      // force on the chassis, applied at the (raised) patch
      const FxW = hx * fxUsed + lx * fyT + w.nx * w.N;
      const FyW = hy * fxUsed + ly * fyT + w.ny * w.N;
      const FzW = hz * fxUsed + lz * fyT + w.nz * w.N;
      const ah = SUSP.appH;
      addF(FxW, FyW, FzW, cx + w.nx * ah, cy + w.ny * ah, cz + w.nz * ah);
      // for geometric transfer: chassis-frame lateral / longitudinal tyre force
      w.fyChassis = fxUsed * (hx * rgx + hy * rgy + hz * rgz) + fyT * (lx * rgx + ly * rgy + lz * rgz);
      w.fxChassis = fxUsed * (hx * fx_ + hy * fy_ + hz * fz_) + fyT * (lx * fx_ + ly * fy_ + lz * fz_);
      if (w.front) fyAxle0 += w.fyChassis; else fyAxle1 += w.fyChassis;
      fxTot += w.fxChassis;
      w.brakeP = Math.abs(w.Tbrake * om);
    }
    gg.fyAxle[0] += (fyAxle0 - gg.fyAxle[0]) * Math.min(1, h * 60);
    gg.fyAxle[1] += (fyAxle1 - gg.fyAxle[1]) * Math.min(1, h * 60);
    gg.fxTot += (fxTot - gg.fxTot) * Math.min(1, h * 60);
    this._brakeThermal(h, vabs);

    // ---- body contact with the road (belly / roof / sliding on its side)
    this.bellyHit = 0;
    if (true) {
      const y0 = pr.y + roughness(pr.s, pr.u, pr.kind);
      const nx = pr.nx, ny = pr.ny, nz = pr.nz;
      for (let k = 0; k < BELLY_PTS.length; k++) {
        const bp = BELLY_PTS[k];
        const dx = bp[0], dy = bp[1] - CAR.cgY, dz = bp[2] - CAR.cgZ;
        const wx_ = R[0] * dx + R[1] * dy + R[2] * dz, wy_ = R[3] * dx + R[4] * dy + R[5] * dz, wz_ = R[6] * dx + R[7] * dy + R[8] * dz;
        const ax = cgx + wx_, ay = cgy + wy_, az = cgz + wz_;
        // plane through (cg.x, y0, cg.z) with normal n
        const d = (cgx - ax) * nx + (y0 - ay) * ny + (cgz - az) * nz;
        if (d <= 0) continue;
        const pvx = this.vx + this.wy * wz_ - this.wz * wy_;
        const pvy = this.vy + this.wz * wx_ - this.wx * wz_;
        const pvz = this.vz + this.wx * wy_ - this.wy * wx_;
        const vn = pvx * nx + pvy * ny + pvz * nz;
        let Fn = 650e3 * d - 14e3 * vn * (vn < 0 ? 1 : 0.3);
        if (Fn < 0) Fn = 0;
        let tvx = pvx - vn * nx, tvy = pvy - vn * ny, tvz = pvz - vn * nz;
        const tv = Math.hypot(tvx, tvy, tvz);
        const fr = 0.55 * Fn * (tv > 1e-3 ? 1 / Math.max(tv, 0.6) : 0);
        addF(nx * Fn - tvx * fr, ny * Fn - tvy * fr, nz * Fn - tvz * fr, ax, ay, az);
        this.bellyHit = Math.max(this.bellyHit, Math.min(1, d * 40) * clamp(tv / 15, 0.1, 1));
        this.bellyX = ax; this.bellyY = ay; this.bellyZ = az;
      }
    }

    // ---- integrate velocities
    this.vx += Fx / m * h; this.vy += Fy / m * h; this.vz += Fz / m * h;
    // angular: body frame
    let wbx = R[0] * this.wx + R[3] * this.wy + R[6] * this.wz;
    let wby = R[1] * this.wx + R[4] * this.wy + R[7] * this.wz;
    let wbz = R[2] * this.wx + R[5] * this.wy + R[8] * this.wz;
    const tbx = R[0] * Tx + R[3] * Ty + R[6] * Tz, tby = R[1] * Tx + R[4] * Ty + R[7] * Tz, tbz = R[2] * Tx + R[5] * Ty + R[8] * Tz;
    const I0 = this.I[0], I1 = this.I[1], I2 = this.I[2];
    wbx += (tbx - (I2 - I1) * wby * wbz) / I0 * h;
    wby += (tby - (I0 - I2) * wbz * wbx) / I1 * h;
    wbz += (tbz - (I1 - I0) * wbx * wby) / I2 * h;
    this.wx = R[0] * wbx + R[1] * wby + R[2] * wbz;
    this.wy = R[3] * wbx + R[4] * wby + R[5] * wbz;
    this.wz = R[6] * wbx + R[7] * wby + R[8] * wbz;
    this.accW[0] = Sx / m; this.accW[1] = Sy / m; this.accW[2] = Sz / m;
    this.yawRate = this.wy;
  }

  /** advance pose by h */
  integrate(h) {
    this.px += this.vx * h; this.py += this.vy * h; this.pz += this.vz * h;
    const hx = 0.5 * h * this.wx, hy = 0.5 * h * this.wy, hz = 0.5 * h * this.wz;
    const qx = this.qx, qy = this.qy, qz = this.qz, qw = this.qw;
    this.qx += hx * qw + hy * qz - hz * qy;
    this.qy += hy * qw + hz * qx - hx * qz;
    this.qz += hz * qw + hx * qy - hy * qx;
    this.qw += -hx * qx - hy * qy - hz * qz;
    const n = 1 / Math.hypot(this.qx, this.qy, this.qz, this.qw);
    this.qx *= n; this.qy *= n; this.qz *= n; this.qw *= n;
    this.updateRotation();
    // smoothed local acceleration
    const R = this.R, a = this.accW, k = Math.min(1, h / 0.09);
    const lx = R[0] * a[0] + R[3] * a[1] + R[6] * a[2];
    const ly = R[1] * a[0] + R[4] * a[1] + R[7] * a[2];
    const lz = R[2] * a[0] + R[5] * a[1] + R[8] * a[2];
    this.accelLocal[0] += (lx - this.accelLocal[0]) * k;
    this.accelLocal[1] += (ly - this.accelLocal[1]) * k;
    this.accelLocal[2] += (lz - this.accelLocal[2]) * k;
  }

  // ---------- drivetrain ----------
  _spinFree(w, h) {
    const I = CAR.wheelInertia;
    let om = w.omega + h * (w.Tdrive) / I;
    const dwb = h * w.Tbrake / I;
    if (dwb > 0) { if (Math.abs(om) <= dwb) om = 0; else om -= Math.sign(om) * dwb; }
    w.omega = om; w.spinRate = om; w.spin += om * h; w.brakeP = Math.abs(w.Tbrake * om);
  }

  _powertrain(h, vf) {
    const W = this.wheels, ctl = this.ctl, D = DRIVE;
    // throttle smoothing (fast attack, quick release) – avoids torque steps
    const thrT = clamp(ctl.throttle, 0, 1);
    this.thr += (thrT - this.thr) * Math.min(1, h * (thrT > this.thr ? 22 : 40));
    const thr = this.thr * (this.escThr ?? 1);
    const reverse = ctl.reverse;
    const dir = reverse ? -1 : 1;
    const brakeP = clamp(ctl.brake, 0, 1);
    const hb = clamp(ctl.handbrake, 0, 1);
    const assistTC = this.assist.tc, assistABS = this.assist.abs;
    const G = D.gear, eta = D.eta;
    const aero = Math.abs(vf);
    const vSign = vf >= 0 ? 1 : -1;
    let totP = 0, totLoad = 0, rpmSum = 0;
    for (let ax = 0; ax < 2; ax++) {
      const a = ax === 0 ? W[0] : W[2], b = ax === 0 ? W[1] : W[3];
      const mt = ax === 0 ? D.front : D.rear;
      const om = 0.5 * (a.omega + b.omega);
      const omM = Math.abs(om) * G;
      const rpm = omM * 30 / Math.PI;
      rpmSum += rpm;
      // available motor torque: constant torque, then constant power, soft limiter near max rpm
      const taper = 1 - smooth(D.taperRpm, D.maxRpm, rpm);
      const Tav = Math.min(mt.T, mt.P / Math.max(omM, 1)) * taper;
      let Tm = 0;
      if (thr > 0.001) Tm = thr * Tav * (reverse ? D.reverseTorque * (1 - smooth(D.reverseMaxSpeed - 4, D.reverseMaxSpeed, -vf)) : 1);
      let Twheel = dir * Tm * G * eta;                    // axle wheel torque (signed, + = forward)
      // regen on lift and on the brake pedal
      const spdFade = smooth(0.6, 3.5, aero);
      let regen = 0;
      if (thr < 0.02 && brakeP < 0.01 && hb < 0.01) regen = D.regenLift * mt.T * G * eta * spdFade * (1 - thr / 0.02);
      const Tb = (ax === 0 ? BRAKE.front : BRAKE.rear) * 2 * brakeP * (BRAKE.hiScale + (1 - BRAKE.hiScale) * (1 - smooth(BRAKE.hiV0, BRAKE.hiV1, aero)));
      let fricAxle = 0;
      if (brakeP > 0.005) {
        const regenCap = Math.min(D.regenBrakeMax * mt.T, D.regenPower / Math.max(omM, 1)) * G * eta * spdFade;
        const r = Math.min(Tb, regenCap);
        regen = Math.max(regen, r);
        fricAxle = Tb - r;
      }
      Twheel -= regen * vSign;
      const lsd = clamp(D.lsdK * (b.omega - a.omega), -D.lsdMax, D.lsdMax);   // right faster → torque to the left
      const fade = 1 - 0.3 * smooth(BRAKE.tFadeStart, BRAKE.tFadeEnd, 0.5 * (a.brakeT + b.brakeT));
      for (let s = 0; s < 2; s++) {
        const w = s === 0 ? a : b;
        const kap = w.kappa;
        let tcf = 1, absf = 1;
        if (assistTC) tcf = 1 - smooth(0.13, 0.26, kap * dir);
        if (assistABS && aero > 2.5) absf = 1 - smooth(0.11, 0.22, -kap * vSign);
        w.tc += (tcf - w.tc) * Math.min(1, h * 80);
        w.abs += (absf - w.abs) * Math.min(1, h * 90);
        let T = Twheel * 0.5 + (s === 0 ? lsd : -lsd);
        T *= (T * dir > 0) ? w.tc : w.abs;                // drive torque ← TC, regen torque ← ABS
        w.Tdrive = T;
        let fr = fricAxle * 0.5 * fade * w.abs;
        if (ax === 1 && hb > 0) fr = Math.max(fr, BRAKE.handbrake * hb);
        w.Tbrake = fr;
      }
      totP += Twheel * om / (Twheel * om > 0 ? eta : 1 / eta);
      totLoad += Math.abs(Twheel) / (G * eta * mt.T);
    }
    this.motor.rpm = rpmSum * 0.5;
    this.motor.load = clamp(totLoad * 0.5, 0, 1);
    this.motor.power = totP / 1000;
  }

  _brakeThermal(h, vabs) {
    let mx = 0;
    for (const w of this.wheels) {
      const cool = BRAKE.cool0 + BRAKE.coolV * vabs;      // W/K
      w.brakeT += ((w.brakeP || 0) - cool * (w.brakeT - BRAKE.tAmb)) / BRAKE.mass * h;
      if (w.brakeT < BRAKE.tAmb) w.brakeT = BRAKE.tAmb;
      if (w.brakeT > mx) mx = w.brakeT;
    }
    this.brakeTemp = clamp((mx - 80) / 820, 0, 1);
  }

  /** Reset thermal state etc. */
  coolDown() { for (const w of this.wheels) w.brakeT = BRAKE.tAmb; }
}

export { WALL_PTS, BELLY_PTS };
