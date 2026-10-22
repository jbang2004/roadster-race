// Physics world: steps all vehicles, detects wall + car-car contacts and resolves them with sequential impulses
// (restitution + Coulomb friction), then a gentle position correction. Pure JS.
//
//  * Walls: vertical planes at |u| = hw + WALL_OFFSET, continuous everywhere (half-spaces → no tunnelling).
//  * Cars: oriented boxes. Points of A (perimeter hull) inside B's box and vice versa → contacts along the axis
//    of least penetration. Sub-stepping (240 Hz) keeps closing speeds of ~100 m/s well below the box size per step.

import { CAR } from './params.js';
import { WALL_PTS } from './vehicle.js';

const MU_WALL = 0.24, MU_CAR = 0.28, E_WALL = 0.16, E_CAR = 0.10;
const MAX_CONTACTS = 256;

class Contact {
  constructor() {
    this.a = null; this.b = null;
    this.nx = 0; this.ny = 0; this.nz = 0;
    this.px = 0; this.py = 0; this.pz = 0;
    this.ra = [0, 0, 0]; this.rb = [0, 0, 0];
    this.depth = 0; this.mu = 0; this.bounce = 0;
    this.jn = 0; this.jt1 = 0; this.jt2 = 0;
    this.t1 = [0, 0, 0]; this.t2 = [0, 0, 0];
    this.kn = 0; this.k1 = 0; this.k2 = 0;
    this.kind = 0;     // 0 wall, 1 car
    this.vn0 = 0;
  }
}

function invInertiaApply(c, rx, ry, rz, out) {
  // out = IinvW * (r)  (vector)
  const W = c.IinvW;
  out[0] = W[0] * rx + W[1] * ry + W[2] * rz;
  out[1] = W[3] * rx + W[4] * ry + W[5] * rz;
  out[2] = W[6] * rx + W[7] * ry + W[8] * rz;
}

export class PhysicsWorld {
  constructor(road) {
    this.road = road;
    this.cars = [];
    this.pool = Array.from({ length: MAX_CONTACTS }, () => new Contact());
    this.n = 0;
    this._pr = {};
    this._t = [0, 0, 0];
    this._t2 = [0, 0, 0];
    this._pt = { x: 0, y: 0, z: 0 };
    this.iterations = 8;
  }

  add(car) {
    this.cars.push(car);
    car.hit = { wallImpulse: 0, carImpulse: 0, wallNx: 0, wallNy: 0, wallNz: 0, wallX: 0, wallY: 0, wallZ: 0,
      carX: 0, carY: 0, carZ: 0, carNx: 0, carNy: 0, carNz: 0, other: null, scrape: 0, scrapeX: 0, scrapeY: 0, scrapeZ: 0,
      scrapeNx: 0, scrapeNy: 0, scrapeNz: 0, maxWallJ: 0, maxCarJ: 0 };
  }
  remove(car) { const i = this.cars.indexOf(car); if (i >= 0) this.cars.splice(i, 1); }

  step(h) {
    const cars = this.cars;
    for (let i = 0; i < cars.length; i++) cars[i].forces(h);
    this.n = 0;
    for (let i = 0; i < cars.length; i++) this._wallContacts(cars[i]);
    this._carContacts();
    if (this.n) this._solve(h);
    for (let i = 0; i < cars.length; i++) cars[i].integrate(h);
    if (this.n) this._correct(h);
  }

  _newContact() { return this.n < MAX_CONTACTS ? this.pool[this.n++] : null; }

  // ---------------------------------------------------------------- wall
  _wallContacts(car) {
    const road = this.road, pr = this._pr, R = car.R;
    // quick reject using the CG projection (car.uProj, hw from the last probe)
    const hwCg = car.pr.hw;
    const lim = hwCg + road.wall;
    if (Math.abs(car.uProj) + 3.0 < lim) return;
    const pt = this._pt;
    for (let k = 0; k < WALL_PTS.length; k++) {
      const c = WALL_PTS[k];
      car.toWorld(c[0], c[1], c[2], pt);
      road.probe(pt.x, pt.z, car.hint, pr);
      const over = Math.abs(pr.u) - (pr.hw + road.wall);
      if (over <= 0) continue;
      const ct = this._newContact(); if (!ct) return;
      const sgn = pr.u > 0 ? -1 : 1;                  // normal points back into the road
      ct.kind = 0; ct.a = car; ct.b = null;
      ct.nx = pr.rx * sgn; ct.ny = 0; ct.nz = pr.rz * sgn;
      ct.px = pt.x; ct.py = pt.y; ct.pz = pt.z;
      ct.depth = over; ct.mu = MU_WALL;
      this._prepare(ct, E_WALL);
    }
  }

  // ---------------------------------------------------------------- car vs car
  _carContacts() {
    const cars = this.cars, n = cars.length;
    for (let i = 0; i < n; i++) {
      const A = cars[i]; if (!A.collidable) continue;
      for (let j = i + 1; j < n; j++) {
        const B = cars[j]; if (!B.collidable) continue;
        const dx = B.px - A.px, dz = B.pz - A.pz;
        if (dx * dx + dz * dz > 36) continue;          // 6 m between CGs
        if (Math.abs(B.py - A.py) > 2.5) continue;
        this._pairContacts(A, B);
        this._pairContacts(B, A, true);
      }
    }
  }

  /** points of P inside the box of Q. flip: contacts are reported with normal pointing from the first (Q... see below) */
  _pairContacts(P, Q, flip = false) {
    const pt = this._pt, R = Q.R, box = CAR.box;
    const oy = box.cy - CAR.cgY, oz = CAR.cgZ;     // box centre relative to Q's CG: y offset, z offset (centre z = 0 in car frame)
    for (let k = 0; k < WALL_PTS.length; k++) {
      const c = WALL_PTS[k];
      P.toWorld(c[0], c[1], c[2], pt);
      const dx = pt.x - Q.px, dy = pt.y - Q.py, dz = pt.z - Q.pz;
      const lx = dx * R[0] + dy * R[3] + dz * R[6];
      const ly = dx * R[1] + dy * R[4] + dz * R[7] - oy;
      const lz = dx * R[2] + dy * R[5] + dz * R[8] + oz;
      const ex = box.hx - Math.abs(lx), ey = (box.hy - Math.abs(ly)) * 3, ez = box.hz - Math.abs(lz);
      if (ex <= 0 || ey <= 0 || ez <= 0) continue;
      // axis of least penetration
      let ax = 0, depth = ex;
      if (ez < depth) { ax = 2; depth = ez; }
      if (ey < depth) { ax = 1; depth = ey; }
      let nlx = 0, nly = 0, nlz = 0;
      if (ax === 0) nlx = lx > 0 ? 1 : -1; else if (ax === 1) nly = ly > 0 ? 1 : -1; else nlz = lz > 0 ? 1 : -1;
      // local normal (pointing out of Q towards P) → world
      let nx = R[0] * nlx + R[1] * nly + R[2] * nlz;
      let ny = R[3] * nlx + R[4] * nly + R[5] * nlz;
      let nz = R[6] * nlx + R[7] * nly + R[8] * nlz;
      const ct = this._newContact(); if (!ct) return;
      ct.kind = 1;
      // contact normal convention: points from b to a. Here a = P, b = Q.
      ct.a = P; ct.b = Q;
      ct.nx = nx; ct.ny = ny; ct.nz = nz;
      ct.px = pt.x; ct.py = pt.y; ct.pz = pt.z;
      ct.depth = ax === 1 ? depth / 3 : depth; ct.mu = MU_CAR;
      this._prepare(ct, E_CAR);
    }
  }

  // ---------------------------------------------------------------- solver
  _prepare(ct, e) {
    const A = ct.a, B = ct.b, t = this._t;
    ct.ra[0] = ct.px - A.px; ct.ra[1] = ct.py - A.py; ct.ra[2] = ct.pz - A.pz;
    if (B) { ct.rb[0] = ct.px - B.px; ct.rb[1] = ct.py - B.py; ct.rb[2] = ct.pz - B.pz; }
    // relative velocity of A wrt B at the contact
    let vx = A.vx + A.wy * ct.ra[2] - A.wz * ct.ra[1];
    let vy = A.vy + A.wz * ct.ra[0] - A.wx * ct.ra[2];
    let vz = A.vz + A.wx * ct.ra[1] - A.wy * ct.ra[0];
    if (B) {
      vx -= B.vx + B.wy * ct.rb[2] - B.wz * ct.rb[1];
      vy -= B.vy + B.wz * ct.rb[0] - B.wx * ct.rb[2];
      vz -= B.vz + B.wx * ct.rb[1] - B.wy * ct.rb[0];
    }
    const vn = vx * ct.nx + vy * ct.ny + vz * ct.nz;
    ct.vn0 = vn;
    ct.bounce = vn < -2.0 ? -e * vn : 0;
    // tangents
    let tx = vx - vn * ct.nx, ty = vy - vn * ct.ny, tz = vz - vn * ct.nz;
    let tl = Math.hypot(tx, ty, tz);
    if (tl < 1e-4) {
      // any perpendicular
      if (Math.abs(ct.nx) < 0.9) { tx = 0; ty = -ct.nz; tz = ct.ny; } else { tx = ct.nz; ty = 0; tz = -ct.nx; }
      tl = Math.hypot(tx, ty, tz);
    }
    tx /= tl; ty /= tl; tz /= tl;
    ct.t1[0] = tx; ct.t1[1] = ty; ct.t1[2] = tz;
    ct.t2[0] = ct.ny * tz - ct.nz * ty; ct.t2[1] = ct.nz * tx - ct.nx * tz; ct.t2[2] = ct.nx * ty - ct.ny * tx;
    ct.kn = this._effMass(ct, ct.nx, ct.ny, ct.nz);
    ct.k1 = this._effMass(ct, tx, ty, tz);
    ct.k2 = this._effMass(ct, ct.t2[0], ct.t2[1], ct.t2[2]);
    ct.jn = ct.jt1 = ct.jt2 = 0;
  }

  _effMass(ct, dx, dy, dz) {
    const A = ct.a, B = ct.b, tmp = this._t2;
    let k = A.invMass;
    let cx = ct.ra[1] * dz - ct.ra[2] * dy, cy = ct.ra[2] * dx - ct.ra[0] * dz, cz = ct.ra[0] * dy - ct.ra[1] * dx;
    invInertiaApply(A, cx, cy, cz, tmp);
    // (I^-1 (r x d)) x r . d
    let ux = tmp[1] * ct.ra[2] - tmp[2] * ct.ra[1], uy = tmp[2] * ct.ra[0] - tmp[0] * ct.ra[2], uz = tmp[0] * ct.ra[1] - tmp[1] * ct.ra[0];
    k += ux * dx + uy * dy + uz * dz;
    if (B) {
      k += B.invMass;
      cx = ct.rb[1] * dz - ct.rb[2] * dy; cy = ct.rb[2] * dx - ct.rb[0] * dz; cz = ct.rb[0] * dy - ct.rb[1] * dx;
      invInertiaApply(B, cx, cy, cz, tmp);
      ux = tmp[1] * ct.rb[2] - tmp[2] * ct.rb[1]; uy = tmp[2] * ct.rb[0] - tmp[0] * ct.rb[2]; uz = tmp[0] * ct.rb[1] - tmp[1] * ct.rb[0];
      k += ux * dx + uy * dy + uz * dz;
    }
    return 1 / k;
  }

  _apply(ct, jx, jy, jz, sign) {
    // apply impulse J to A (sign=+1) and -J to B
    const A = ct.a, B = ct.b, tmp = this._t2;
    A.vx += jx * A.invMass; A.vy += jy * A.invMass; A.vz += jz * A.invMass;
    let cx = ct.ra[1] * jz - ct.ra[2] * jy, cy = ct.ra[2] * jx - ct.ra[0] * jz, cz = ct.ra[0] * jy - ct.ra[1] * jx;
    invInertiaApply(A, cx, cy, cz, tmp);
    A.wx += tmp[0]; A.wy += tmp[1]; A.wz += tmp[2];
    if (B) {
      B.vx -= jx * B.invMass; B.vy -= jy * B.invMass; B.vz -= jz * B.invMass;
      cx = ct.rb[1] * jz - ct.rb[2] * jy; cy = ct.rb[2] * jx - ct.rb[0] * jz; cz = ct.rb[0] * jy - ct.rb[1] * jx;
      invInertiaApply(B, cx, cy, cz, tmp);
      B.wx -= tmp[0]; B.wy -= tmp[1]; B.wz -= tmp[2];
    }
  }

  _relVel(ct, out) {
    const A = ct.a, B = ct.b;
    out[0] = A.vx + A.wy * ct.ra[2] - A.wz * ct.ra[1];
    out[1] = A.vy + A.wz * ct.ra[0] - A.wx * ct.ra[2];
    out[2] = A.vz + A.wx * ct.ra[1] - A.wy * ct.ra[0];
    if (B) {
      out[0] -= B.vx + B.wy * ct.rb[2] - B.wz * ct.rb[1];
      out[1] -= B.vy + B.wz * ct.rb[0] - B.wx * ct.rb[2];
      out[2] -= B.vz + B.wx * ct.rb[1] - B.wy * ct.rb[0];
    }
  }

  _solve(h) {
    const n = this.n, P = this.pool, v = this._t;
    for (let it = 0; it < this.iterations; it++) {
      for (let c = 0; c < n; c++) {
        const ct = P[c];
        // normal
        this._relVel(ct, v);
        const vn = v[0] * ct.nx + v[1] * ct.ny + v[2] * ct.nz;
        let dj = -(vn - ct.bounce) * ct.kn;
        const old = ct.jn;
        ct.jn = Math.max(0, old + dj); dj = ct.jn - old;
        if (dj !== 0) this._apply(ct, ct.nx * dj, ct.ny * dj, ct.nz * dj);
        // friction
        const maxF = ct.mu * ct.jn;
        this._relVel(ct, v);
        let vt = v[0] * ct.t1[0] + v[1] * ct.t1[1] + v[2] * ct.t1[2];
        let d1 = -vt * ct.k1, o1 = ct.jt1;
        ct.jt1 = Math.max(-maxF, Math.min(maxF, o1 + d1)); d1 = ct.jt1 - o1;
        if (d1 !== 0) this._apply(ct, ct.t1[0] * d1, ct.t1[1] * d1, ct.t1[2] * d1);
        vt = v[0] * ct.t2[0] + v[1] * ct.t2[1] + v[2] * ct.t2[2];
        let d2 = -vt * ct.k2, o2 = ct.jt2;
        ct.jt2 = Math.max(-maxF, Math.min(maxF, o2 + d2)); d2 = ct.jt2 - o2;
        if (d2 !== 0) this._apply(ct, ct.t2[0] * d2, ct.t2[1] * d2, ct.t2[2] * d2);
      }
    }
    // bookkeeping for events
    const cars = this.cars;
    for (let k = 0; k < cars.length; k++) { cars[k]._wj = 0; cars[k]._wjMax = 0; }
    for (let c = 0; c < n; c++) {
      const ct = P[c], A = ct.a, B = ct.b;
      if (ct.kind === 0) {
        const hit = A.hit;
        hit.wallImpulse += ct.jn;
        A._wj += ct.jn;
        if (ct.jn > hit.maxWallJ) {
          hit.maxWallJ = ct.jn;
          hit.wallX = ct.px; hit.wallY = ct.py; hit.wallZ = ct.pz; hit.wallNx = ct.nx; hit.wallNy = ct.ny; hit.wallNz = ct.nz;
        }
        if (ct.jn > A._wjMax) {
          A._wjMax = ct.jn;
          hit.scrapeX = ct.px; hit.scrapeY = ct.py; hit.scrapeZ = ct.pz; hit.scrapeNx = ct.nx; hit.scrapeNy = ct.ny; hit.scrapeNz = ct.nz;
        }
      } else {
        for (const car of [A, B]) {
          const hit = car.hit;
          hit.carImpulse += ct.jn;
          if (ct.jn > hit.maxCarJ) {
            hit.maxCarJ = ct.jn; hit.other = car === A ? B : A;
            hit.carX = ct.px; hit.carY = ct.py; hit.carZ = ct.pz;
            const s = car === A ? 1 : -1;
            hit.carNx = ct.nx * s; hit.carNy = ct.ny * s; hit.carNz = ct.nz * s;
          }
        }
      }
    }
    // scraping = sliding along the wall under load: intensity from the contact force (all wall points) and the sliding speed
    for (let k = 0; k < cars.length; k++) {
      const A = cars[k];
      if (A._wj <= 0) continue;
      const force = A._wj / h;                                                   // N, sum over contact points this sub-step
      const inten = Math.sqrt(Math.min(1, force / 8000)) * Math.min(1, Math.hypot(A.vx, A.vz) / 40);
      if (inten > A.hit.scrape) A.hit.scrape = inten;
    }
  }

  _correct(h) {
    const n = this.n, P = this.pool, v = this._t;
    for (let c = 0; c < n; c++) {
      const ct = P[c], A = ct.a, B = ct.b;
      this._relVel(ct, v);
      const vn = v[0] * ct.nx + v[1] * ct.ny + v[2] * ct.nz;
      const rem = ct.depth - Math.max(vn, 0) * h - 0.004;
      if (rem <= 0) continue;
      const k = 0.55 * rem;
      if (!B) {
        A.px += ct.nx * k; A.py += ct.ny * k * 0; A.pz += ct.nz * k;
      } else {
        A.px += ct.nx * k * 0.5; A.py += ct.ny * k * 0.1; A.pz += ct.nz * k * 0.5;
        B.px -= ct.nx * k * 0.5; B.py -= ct.ny * k * 0.1; B.pz -= ct.nz * k * 0.5;
      }
    }
  }
}
