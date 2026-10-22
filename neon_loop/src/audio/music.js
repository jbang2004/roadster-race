// Low-key darksynth bed: A minor, 92 BPM, 8-bar loop. Sequenced with a look-ahead scheduler driven by update().
// Rolling saw bass, slow pad, sparse kick/clap, quiet hats, delayed arpeggio from the second loop on.
import { clamp, ramp, noiseSource } from './util.js';

const mtof = (m) => 440 * Math.pow(2, (m - 69) / 12);
const BPM = 92, STEP = 60 / BPM / 4;
const CHORDS = [  // [bass root, chord notes]
  [33, [57, 60, 64]], [33, [57, 60, 64]], [29, [53, 57, 60]], [29, [53, 57, 60]],
  [36, [55, 60, 64]], [31, [55, 59, 62]], [29, [53, 57, 60]], [28, [52, 56, 59]],
];
const BASS_MASK = '1010101110101101', BASS_OCT = [0, 0, 12, 0, 0, 12, 0, 7, 0, 0, 12, 0, 7, 0, 12, 0];

export function createMusic(A) {
  const { ctx } = A;
  const out = ctx.createGain(); out.gain.value = 0; out.connect(A.buses.music);
  const dly = ctx.createDelay(1.0); dly.delayTime.value = STEP * 3;
  const dlp = ctx.createBiquadFilter(); dlp.type = 'lowpass'; dlp.frequency.value = 2200;
  const fb = ctx.createGain(); fb.gain.value = 0.38;
  dly.connect(dlp); dlp.connect(fb); fb.connect(dly); dlp.connect(out);
  const dsend = ctx.createGain(); dsend.gain.value = 0.55; dsend.connect(dly);

  let nextT = 0, step = 0, enabled = true, started = false, level = 0;

  function voice(type, f, t, dur, peak, atk, dest, filtF0, filtF1, filtT = 0.12, detune = 0) {
    const o = ctx.createOscillator(); o.type = type; o.frequency.value = f; o.detune.value = detune;
    const lp = ctx.createBiquadFilter(); lp.type = 'lowpass'; lp.Q.value = 2.2;
    lp.frequency.setValueAtTime(filtF0, t); lp.frequency.exponentialRampToValueAtTime(Math.max(60, filtF1), t + filtT);
    const g = ctx.createGain(); g.gain.setValueAtTime(0.0001, t); g.gain.linearRampToValueAtTime(peak, t + atk); g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    o.connect(lp); lp.connect(g); g.connect(dest); o.start(t); o.stop(t + dur + 0.05);
    o.onended = () => { try { o.disconnect(); lp.disconnect(); g.disconnect(); } catch { /* done */ } };
  }
  function noise(t, buf, type, f, q, peak, dur, dest) {
    const s = ctx.createBufferSource(); s.buffer = buf; const b = ctx.createBiquadFilter(); b.type = type; b.frequency.value = f; b.Q.value = q;
    const g = ctx.createGain(); g.gain.setValueAtTime(peak, t); g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    s.connect(b); b.connect(g); g.connect(dest); s.start(t, Math.random() * 2); s.stop(t + dur + 0.02);
    s.onended = () => { try { s.disconnect(); b.disconnect(); g.disconnect(); } catch { /* done */ } };
  }
  function kick(t) {
    const o = ctx.createOscillator(); o.type = 'sine'; o.frequency.setValueAtTime(135, t); o.frequency.exponentialRampToValueAtTime(42, t + 0.14);
    const g = ctx.createGain(); g.gain.setValueAtTime(0.0001, t); g.gain.linearRampToValueAtTime(0.55, t + 0.003); g.gain.exponentialRampToValueAtTime(0.0001, t + 0.3);
    o.connect(g); g.connect(out); o.start(t); o.stop(t + 0.35);
    o.onended = () => { try { o.disconnect(); g.disconnect(); } catch { /* done */ } };
  }

  function schedule(s, t) {
    const bar = Math.floor(s / 16) % 8, k = s % 16, loop = Math.floor(s / 128), [root, notes] = CHORDS[bar];
    if (k === 0) for (const n of notes) for (const dt of [-7, 7]) voice('sawtooth', mtof(n), t, STEP * 17, 0.03, 0.9, out, 700, 1500, 1.8, dt);
    if (BASS_MASK[k] === '1') {
      const f = mtof(root + BASS_OCT[k]);
      voice('sawtooth', f, t, STEP * 1.9, 0.20, 0.006, out, 1500, 220, 0.14);
      voice('square', f * 0.5, t, STEP * 1.9, 0.10, 0.006, out, 600, 150, 0.14);
    }
    if (k === 0 || k === 8 || (k === 14 && bar % 2)) kick(t);
    if (k === 4 || k === 12) { noise(t, A.noise.white, 'bandpass', 1700, 0.8, 0.13, 0.16, out); voice('triangle', 190, t, 0.1, 0.06, 0.002, out, 900, 300, 0.08); }
    if (k % 4 === 2) noise(t, A.noise.white, 'highpass', 7500, 0.7, 0.03, 0.035, out);
    if (loop % 2 === 1 && bar >= 2) {
      const arp = [0, 1, 2, 1][k % 4], n = notes[arp] + 12 + (k >= 8 ? 12 * (k % 8 === 7 ? 1 : 0) : 0);
      if (k % 2 === 0 || bar % 2) voice('square', mtof(n), t, STEP * 1.6, 0.045, 0.004, dsend, 2600, 700, 0.1);
    }
  }

  return {
    out,
    setLevel(v, now, tc = 0.8) { level = clamp(v, 0, 1); ramp(out.gain, enabled ? level : 0, now, tc); },
    setEnabled(b, now) { enabled = !!b; ramp(out.gain, enabled ? level : 0, now, 0.6); },
    tick(now) {
      if (!enabled && out.gain.value < 0.0005) { started = false; return; }
      if (!started) { started = true; nextT = now + 0.1; step = 0; }
      while (nextT < now + 0.4) { schedule(step, nextT); nextT += STEP; step++; }
    },
  };
}
