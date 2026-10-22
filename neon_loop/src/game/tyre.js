// Pacejka-style tyre: Magic-Formula shaped normalised-slip model with combined slip (friction ellipse), load sensitivity
// of both grip and peak slip angle, and wet-surface grip scaling. Pure functions, no allocation.
//
//   sx = kappa / kappa_pk,  sy = tan(alpha) / tan(alpha_pk)   (alpha_pk grows a little with load)
//   s  = hypot(sx, sy),     f(s) = sin(C atan(B s - E (B s - atan B s)))   normalised so that f(1) = 1 is the peak
//   Fx = mux(Fz) Fz f(s) sx/s,   Fy = muy(Fz) Fz f(s) sy/s
//
// Because the ellipse is built into the slip normalisation, braking while cornering loses lateral grip exactly as a
// real tyre does, and a locked wheel (s large) falls to the sliding level f(inf) = sin(C pi/2).

import { TYRE } from './params.js';

/** Solve B so that the MF curve with shape (C, E) peaks at s = 1 with value 1. */
function solveB(C, E) {
  const target = Math.tan(Math.PI / (2 * C));
  let lo = 0.05, hi = 60;
  for (let k = 0; k < 60; k++) {
    const B = 0.5 * (lo + hi);
    const g = B * (1 - E) + E * Math.atan(B) - target;
    if (g > 0) hi = B; else lo = B;
  }
  return 0.5 * (lo + hi);
}

export class TyreCurve {
  constructor(C, E) {
    this.C = C; this.E = E; this.B = solveB(C, E);
    this.slope = this.B * this.C;           // f'(0)
  }
  f(s) {
    const Bs = this.B * s;
    return Math.sin(this.C * Math.atan(Bs - this.E * (Bs - Math.atan(Bs))));
  }
}

export class Tyre {
  /** p: one of TYRE.front / TYRE.rear */
  constructor(p) {
    this.p = p;
    this.lat = new TyreCurve(p.Clat, p.Elat);
    this.lon = new TyreCurve(p.Clong, p.Elong);
    this.fx = 0; this.fy = 0; this.mu = 1; this.s = 0;
  }
  /** Peak friction coefficients at load Fz. */
  mus(Fz, grip) {
    const p = this.p, r = Fz / TYRE.Fz0;
    const lf = Math.max(0.55, 1 - p.load * (r - 1));
    this.mux = p.mux * lf * grip; this.muy = p.muy * lf * grip;
  }
  /**
   * kappa: longitudinal slip (wheel-minus-ground speed / ref speed), alpha: slip angle in rad (positive = ground-relative
   * lateral velocity of the contact patch is to the LEFT of the wheel, i.e. the tyre force points right).
   * Writes this.fx (along the wheel heading), this.fy (positive = to the right), this.s.
   */
  force(kappa, alpha, Fz, grip = 1) {
    if (Fz <= 1) { this.fx = this.fy = 0; this.s = 0; return; }
    this.mus(Fz, grip);
    const p = this.p, r = Fz / TYRE.Fz0;
    const apk = p.apk * (1 + 0.28 * (r - 1));
    const sx = kappa / p.kpk;
    const sy = Math.tan(alpha) / Math.tan(apk);
    const s = Math.hypot(sx, sy);
    this.s = s;
    if (s < 1e-6) { this.fx = this.fy = 0; return; }
    // blend the two shape curves by direction so pure longitudinal / pure lateral keep their own character
    const wx = (sx * sx) / (s * s);
    const fshape = wx * this.lon.f(s) + (1 - wx) * this.lat.f(s);
    const F = fshape * Fz / s;
    this.fx = this.mux * F * sx;
    this.fy = this.muy * F * sy;
  }
}

export const tyreFront = () => new Tyre(TYRE.front);
export const tyreRear = () => new Tyre(TYRE.rear);
