// Shared WebAudio helpers: NaN-safe parameter ramps, seamless noise loops, procedural reverb impulse responses.
export const clamp = (v, a, b) => (v < a ? a : v > b ? b : v);
export const lerp = (a, b, t) => a + (b - a) * t;
export const smooth = (a, b, v) => { const t = clamp((v - a) / (b - a), 0, 1); return t * t * (3 - 2 * t); };
export const safe = (v, d = 0) => (Number.isFinite(v) ? v : d);
export const rand = (a, b) => a + Math.random() * (b - a);
export const cents = (ratio) => 1200 * Math.log2(ratio);

/** Smoothly move an AudioParam to v (never clicks, never NaN). tc = time constant in seconds. */
export function ramp(param, v, now, tc = 0.05) {
  v = Number.isFinite(v) ? v : param.value;
  param.setTargetAtTime(v, now, tc);
}
/** Like ramp, but snaps to exactly 0 when the target is 0 and the value is inaudible (lets silent chains idle). */
export function rampGain(param, v, now, tc = 0.05) {
  v = Number.isFinite(v) ? Math.max(0, v) : 0;
  if (v === 0 && param.value < 0.00015) { param.setValueAtTime(0, now); return; }
  param.setTargetAtTime(v, now, tc);
}

/** Seamless looped noise: 'white' | 'pink' | 'brown'. Peak-normalised to ~0.9. */
export function makeNoise(ctx, type = 'white', seconds = 4) {
  const sr = ctx.sampleRate, n = Math.floor(seconds * sr), X = Math.floor(sr * 0.12), total = n + X;
  const raw = new Float32Array(total);
  if (type === 'white') { for (let i = 0; i < total; i++) raw[i] = Math.random() * 2 - 1; }
  else if (type === 'pink') {
    let b0 = 0, b1 = 0, b2 = 0, b3 = 0, b4 = 0, b5 = 0, b6 = 0;
    for (let i = 0; i < total; i++) {
      const w = Math.random() * 2 - 1;
      b0 = 0.99886 * b0 + w * 0.0555179; b1 = 0.99332 * b1 + w * 0.0750759; b2 = 0.969 * b2 + w * 0.153852;
      b3 = 0.8665 * b3 + w * 0.3104856; b4 = 0.55 * b4 + w * 0.5329522; b5 = -0.7616 * b5 - w * 0.016898;
      raw[i] = (b0 + b1 + b2 + b3 + b4 + b5 + b6 + w * 0.5362) * 0.11; b6 = w * 0.115926;
    }
  } else {
    let y = 0;
    for (let i = 0; i < total; i++) { y = y * 0.985 + (Math.random() * 2 - 1) * 0.1; raw[i] = y; }
  }
  const buf = ctx.createBuffer(1, n, sr), d = buf.getChannelData(0);
  for (let i = 0; i < n; i++) d[i] = raw[i];
  for (let i = 0; i < X; i++) {            // equal-power crossfade of the tail into the head → no loop click
    const th = (i / X) * Math.PI / 2;
    d[i] = raw[i] * Math.sin(th) + raw[n + i] * Math.cos(th);
  }
  let pk = 0; for (let i = 0; i < n; i++) pk = Math.max(pk, Math.abs(d[i]));
  const g = 0.9 / (pk || 1); for (let i = 0; i < n; i++) d[i] *= g;
  return buf;
}

/** Looping noise source starting at a random offset. */
export function noiseSource(ctx, buffer) {
  const s = ctx.createBufferSource(); s.buffer = buffer; s.loop = true;
  s.start(0, Math.random() * buffer.duration);
  return s;
}

/**
 * Procedural stereo impulse response.
 * o: { dur (s, −60 dB time), pre (s), lpHi, lpLo (Hz: tail brightness start → end), early: [[t, gain], …], flutter: [period, gain] | null, level }
 */
export function makeIR(ctx, o) {
  const sr = ctx.sampleRate, n = Math.floor((o.dur + (o.pre ?? 0)) * sr), buf = ctx.createBuffer(2, n, sr);
  const tau = o.dur / 6.9, pre = Math.floor((o.pre ?? 0) * sr);
  for (let ch = 0; ch < 2; ch++) {
    const d = buf.getChannelData(ch); let lp = 0;
    for (let i = pre; i < n; i++) {
      const t = (i - pre) / sr, env = Math.exp(-t / tau);
      const fc = o.lpLo + (o.lpHi - o.lpLo) * Math.exp(-t / (o.dur * 0.3));
      const a = 1 - Math.exp(-2 * Math.PI * fc / sr);
      lp += a * ((Math.random() * 2 - 1) - lp);
      const ramp = Math.min(1, t / 0.012);           // soft onset
      d[i] = lp * env * ramp;
    }
    for (const [t, g] of (o.early ?? [])) {          // discrete early reflections, decorrelated per channel
      const k = pre + Math.floor((t * (ch ? 1.07 : 0.95)) * sr);
      if (k < n - 3) { d[k] += g * (ch ? -1 : 1); d[k + 1] += g * 0.5; d[k + 2] += g * 0.2; }
    }
    if (o.flutter) {
      const [per, g] = o.flutter;
      for (let m = 1; m * per < o.dur * 0.8; m++) { const k = pre + Math.floor(m * per * (ch ? 1.03 : 1) * sr); if (k < n - 3) d[k] += g * Math.pow(0.82, m) * (ch ? 0.8 : 1); }
    }
  }
  // normalise energy so wet levels are comparable between IRs
  let e = 0; for (let ch = 0; ch < 2; ch++) { const d = buf.getChannelData(ch); for (let i = 0; i < n; i++) e += d[i] * d[i]; }
  const g = (o.level ?? 1) / Math.sqrt(e / 2 || 1) * 0.35;
  for (let ch = 0; ch < 2; ch++) { const d = buf.getChannelData(ch); for (let i = 0; i < n; i++) d[i] *= g; }
  return buf;
}

export function softClipCurve(k = 1.4, n = 2048) {
  const c = new Float32Array(n), norm = Math.tanh(k);
  for (let i = 0; i < n; i++) { const x = (i / (n - 1)) * 2 - 1; c[i] = Math.tanh(k * x) / norm; }
  return c;
}

/** Simple periodic waves (real/imag harmonic amplitudes). */
export function makeWave(ctx, amps) {
  const real = new Float32Array(amps.length + 1), imag = new Float32Array(amps.length + 1);
  for (let i = 0; i < amps.length; i++) imag[i + 1] = amps[i];
  return ctx.createPeriodicWave(real, imag);
}
