// Racing line (minimum-curvature within the road minus margins) and per-driver speed profiles.
// Pure JS, runs in Node. The profile is a classic forward/backward pass with a friction-ellipse budget using the
// same grip / downforce / power numbers as the physics (see `capability`).

import { GRAV } from './params.js';

const clamp = (x, a, b) => (x < a ? a : x > b ? b : x);

/**
 * Capability model of the car (what the physics delivers on a flat road; measured by test/run.mjs, printed there too).
 * Lateral: a = A0 + A1 v² (m/s², includes downforce). Longitudinal: piecewise-linear tables of the full-throttle acceleration
 * and the full-brake deceleration (drag included). The AI scales all of them by its grip fraction.
 */
export const CAP = {
  latA0: 12.4, latA1: 0.00033,
  accV: [0, 25, 35, 45, 55, 65, 75, 85, 92],
  accA: [12.7, 12.7, 11.3, 9.5, 7.4, 5.3, 3.4, 1.3, 0.0],
  brkV: [0, 20, 35, 55, 75, 95],
  brkA: [13.0, 13.4, 14.2, 14.2, 15.2, 16.4],
};
const tab = (V, A, v) => {
  if (v <= V[0]) return A[0];
  for (let i = 1; i < V.length; i++) if (v < V[i]) return A[i - 1] + (A[i] - A[i - 1]) * (v - V[i - 1]) / (V[i] - V[i - 1]);
  return A[A.length - 1];
};
export function latLimit(v, geff = GRAV) { return CAP.latA0 * geff / GRAV + CAP.latA1 * v * v; }
export function accelLimit(v) { return tab(CAP.accV, CAP.accA, v); }
export function brakeLimit(v) { return tab(CAP.brkV, CAP.brkA, v); }

/**
 * Minimum-curvature line by Gauss-Seidel relaxation of lateral offsets inside [-(hw-margin), hw-margin].
 * Returns { n: Float32Array (offset per sample, + right), x,z: Float32Array of line points, kappa: Float32Array (signed, + left) }
 */
export function buildRacingLine(track, { margin = 1.7, iters = 900, span = 5 } = {}) {
  const N = track.N;
  const n = new Float32Array(N);
  const px = track.px, pz = track.pz, rx = track.rx, rz = track.rz, hw = track.hw;
  const hrx = new Float32Array(N), hrz = new Float32Array(N), lim = new Float32Array(N);
  for (let i = 0; i < N; i++) {
    const rh = Math.hypot(rx[i], rz[i]); hrx[i] = rx[i] / rh; hrz[i] = rz[i] / rh;
    lim[i] = Math.max(0.5, hw[i] - margin);
  }
  const X = new Float32Array(N), Z = new Float32Array(N);
  const place = () => { for (let i = 0; i < N; i++) { X[i] = px[i] + hrx[i] * n[i]; Z[i] = pz[i] + hrz[i] * n[i]; } };
  place();
  for (let it = 0; it < iters; it++) {
    const w = it < iters * 0.2 ? 0.9 : 0.6;
    for (let i = 0; i < N; i++) {
      const a = (i - span + N) % N, b = (i + span) % N;
      const mx = 0.5 * (X[a] + X[b]), mz = 0.5 * (Z[a] + Z[b]);
      const tgt = (mx - px[i]) * hrx[i] + (mz - pz[i]) * hrz[i];
      let v = n[i] + w * (tgt - n[i]);
      v = v > lim[i] ? lim[i] : v < -lim[i] ? -lim[i] : v;
      n[i] = v; X[i] = px[i] + hrx[i] * v; Z[i] = pz[i] + hrz[i] * v;
    }
  }
  // final light smoothing of offsets (removes any residual kinks), keep inside limits
  for (let k = 0; k < 6; k++) {
    const t = new Float32Array(N);
    for (let i = 0; i < N; i++) t[i] = 0.25 * n[(i - 1 + N) % N] + 0.5 * n[i] + 0.25 * n[(i + 1) % N];
    for (let i = 0; i < N; i++) n[i] = clamp(t[i], -lim[i], lim[i]);
  }
  place();
  // signed curvature of the line (Menger, spacing 4 samples), smoothed
  const kap = new Float32Array(N);
  const d = 4;
  for (let i = 0; i < N; i++) {
    const a = (i - d + N) % N, b = (i + d) % N;
    const ax = X[i] - X[a], az = Z[i] - Z[a], bx = X[b] - X[i], bz = Z[b] - Z[i];
    const cross = ax * bz - az * bx;                     // + : turning right in x-z with -z north? sign fixed below
    const la = Math.hypot(ax, az), lb = Math.hypot(bx, bz), lc = Math.hypot(X[b] - X[a], Z[b] - Z[a]);
    // curvature magnitude 2*|cross| / (la lb lc); sign: track.curv is + for left turns. In (x,z) with z south, a left turn
    // (counter-clockwise seen from above) has negative 'cross' (x-z handedness) → left = -cross.
    kap[i] = -2 * cross / (la * lb * lc + 1e-9);
  }
  const ks = new Float32Array(N);
  const h = 3;
  for (let i = 0; i < N; i++) { let a = 0; for (let k = -h; k <= h; k++) a += kap[(i + k + N) % N]; ks[i] = a / (2 * h + 1); }
  return { n, x: X, z: Z, kappa: ks, lim };
}

/**
 * Speed profile (m/s per sample) for a driver using `grip` fraction of the limit (0..1).
 * Uses line curvature, banking, vertical curvature (crests lighten the car), then forward / backward passes.
 */
export function buildSpeedProfile(track, line, grip = 0.95, vTop = 91) {
  const N = track.N;
  const v = new Float32Array(N);
  const kap = line.kappa, X = line.x, Z = line.z;
  const seg = new Float32Array(N);
  for (let i = 0; i < N; i++) { const j = (i + 1) % N; seg[i] = Math.hypot(X[j] - X[i], Z[j] - Z[i]); }
  const g2 = grip * grip;
  const kv = new Float32Array(N);       // vertical curvature (+ dip, - crest)
  for (let i = 0; i < N; i++) {
    const a = (i - 6 + N) % N, b = (i + 6) % N;
    kv[i] = (track.grade[b] - track.grade[a]) / 12;
  }
  const latV = (i, vv) => {
    const k = Math.abs(kap[i]);
    const geff = clamp(GRAV + vv * vv * kv[i], 0.35 * GRAV, 1.5 * GRAV);
    const bankHelp = GRAV * Math.sin(track.bank[i]) * Math.sign(kap[i]);
    return (latLimit(vv, geff) + bankHelp) * g2;
  };
  for (let i = 0; i < N; i++) {
    const k = Math.abs(kap[i]);
    let lo = 3, hi = vTop;
    if (k < 1e-5) { v[i] = vTop; continue; }
    for (let it = 0; it < 22; it++) {                   // v² k = a_lat(v)
      const m = 0.5 * (lo + hi);
      if (m * m * k > latV(i, m)) hi = m; else lo = m;
    }
    v[i] = Math.min(vTop, lo);
  }
  const usage = (i, vv) => {
    const a = vv * vv * Math.abs(kap[i]);
    const cap = latV(i, vv);
    return Math.min(0.999, a / cap);
  };
  // backward pass (braking): v_i <= sqrt(v_{i+1}² + 2 a_brk ds)
  for (let pass = 0; pass < 2; pass++) {
    for (let k = N * 2 - 1; k >= 0; k--) {
      const i = k % N, j = (i + 1) % N;
      const r = usage(j, v[j]);
      const a = brakeLimit(v[j]) * grip * Math.sqrt(1 - r * r) * 0.97;
      const vi = Math.sqrt(v[j] * v[j] + 2 * a * seg[i]);
      if (vi < v[i]) v[i] = vi;
    }
  }
  // forward pass (acceleration)
  for (let pass = 0; pass < 2; pass++) {
    for (let k = 0; k < N * 2; k++) {
      const i = k % N, j = (i + 1) % N;
      const r = usage(i, v[i]);
      const a = accelLimit(v[i]) * grip * Math.sqrt(1 - r * r);
      const vj = Math.sqrt(Math.max(0, v[i] * v[i] + 2 * a * seg[i]));
      if (vj < v[j]) v[j] = vj;
    }
  }
  return v;
}
