// Ambience: city hum, drizzle, tunnel jet-fan drone, occasional distant sirens and PA announcements.
import { clamp, rand, ramp, rampGain, noiseSource } from './util.js';

const gain = (ctx, v = 0) => { const g = ctx.createGain(); g.gain.value = v; return g; };
const filt = (ctx, type, f, q = 0.7) => { const b = ctx.createBiquadFilter(); b.type = type; b.frequency.value = f; b.Q.value = q; return b; };
const osc = (ctx, type, f) => { const o = ctx.createOscillator(); o.type = type; o.frequency.value = f; o.start(); return o; };

const VOWELS = [[800, 1200, 2500], [300, 2300, 3000], [350, 800, 2400], [500, 1800, 2500], [500, 900, 2400]];

export function createAmbience(A) {
  const { ctx, noise } = A;
  const out = gain(ctx, 1); out.connect(A.buses.amb);

  // city bed
  const cityG = gain(ctx, 0); cityG.connect(out);
  const hs = noiseSource(ctx, noise.brown), hl = filt(ctx, 'lowpass', 230, 0.6), hg = gain(ctx, 0.17); hs.connect(hl); hl.connect(hg); hg.connect(cityG);
  const ts = noiseSource(ctx, noise.pink), tb = filt(ctx, 'bandpass', 520, 0.5), tg = gain(ctx, 0.032); ts.connect(tb); tb.connect(tg); tg.connect(cityG);
  const t1 = osc(ctx, 'sine', 100.2), t2 = osc(ctx, 'sine', 120.6), tt = gain(ctx, 0.0045); t1.connect(tt); t2.connect(tt); tt.connect(cityG);
  const sl = osc(ctx, 'sine', 0.07), slD = gain(ctx, 0.02); sl.connect(slD); slD.connect(hg.gain);   // slow breathing of the bed

  // drizzle
  const rainG = gain(ctx, 0); rainG.connect(out);
  const rs = noiseSource(ctx, noise.white), rh = filt(ctx, 'highpass', 2600, 0.6), rl = filt(ctx, 'lowpass', 9500, 0.5); rs.connect(rh); rh.connect(rl); rl.connect(rainG);
  const rs2 = noiseSource(ctx, noise.pink), rb = filt(ctx, 'bandpass', 900, 0.6), rg2 = gain(ctx, 0.35); rs2.connect(rb); rb.connect(rg2); rg2.connect(rainG);

  // tunnel jet-fan drone
  const fanG = gain(ctx, 0); fanG.connect(out);
  const fs = noiseSource(ctx, noise.brown), fl = filt(ctx, 'lowpass', 150, 0.7), fg = gain(ctx, 0.5); fs.connect(fl); fl.connect(fg); fg.connect(fanG);
  const f1 = osc(ctx, 'sine', 51.5), f2 = osc(ctx, 'sine', 64), fo = gain(ctx, 0.12); f1.connect(fo); f2.connect(fo); fo.connect(fanG);
  const fan = osc(ctx, 'sine', 0.42), fanD = gain(ctx, 0.25); fan.connect(fanD); fanD.connect(fg.gain);

  let sirenT = rand(14, 35), paT = rand(25, 60), dropT = 0;

  function spawnSiren(now, listenerPos) {
    const nodes = [], dur = rand(9, 14), dir = rand(0, Math.PI * 2), R = rand(190, 300);
    const o = ctx.createOscillator(); o.type = 'sawtooth';
    const lo = rand(620, 720), hi = lo * 1.38, per = rand(0.55, 0.75), n = Math.floor(dur / per);
    o.frequency.setValueAtTime(lo, now);
    for (let i = 1; i <= n; i++) o.frequency.setTargetAtTime(i % 2 ? hi : lo, now + i * per, 0.03);
    o.detune.setValueAtTime(40, now); o.detune.linearRampToValueAtTime(-70, now + dur);
    const l1 = filt(ctx, 'lowpass', 1500, 0.6), b1 = filt(ctx, 'bandpass', 950, 0.5), g = gain(ctx, 0);
    g.gain.setValueAtTime(0, now); g.gain.linearRampToValueAtTime(0.06, now + dur * 0.3); g.gain.linearRampToValueAtTime(0.06, now + dur * 0.55); g.gain.linearRampToValueAtTime(0, now + dur);
    const p = ctx.createPanner(); p.panningModel = 'equalpower'; p.distanceModel = 'inverse'; p.refDistance = 20; p.rolloffFactor = 1.1; p.maxDistance = 600;
    const cx = listenerPos.x + Math.cos(dir) * R, cz = listenerPos.z + Math.sin(dir) * R, sx = -Math.sin(dir) * 160;
    p.positionX.setValueAtTime(cx - sx, now); p.positionX.linearRampToValueAtTime(cx + sx, now + dur);
    p.positionZ.setValueAtTime(cz, now); p.positionY.value = listenerPos.y + 25;
    o.connect(l1); l1.connect(b1); b1.connect(g); g.connect(p); p.connect(out);
    o.start(now); o.stop(now + dur + 0.1); nodes.push(o, l1, b1, g, p);
    setTimeout(() => nodes.forEach(x => { try { x.disconnect(); } catch { /* done */ } }), (dur + 0.6) * 1000);
  }

  function spawnAnnouncement(now, listenerPos) {
    const nodes = [], syl = Math.round(rand(14, 22));
    const dir = rand(0, Math.PI * 2), R = rand(90, 160);
    const p = ctx.createPanner(); p.panningModel = 'equalpower'; p.distanceModel = 'inverse'; p.refDistance = 12; p.rolloffFactor = 1.0;
    p.positionX.value = listenerPos.x + Math.cos(dir) * R; p.positionZ.value = listenerPos.z + Math.sin(dir) * R; p.positionY.value = listenerPos.y + 14;
    const tel1 = filt(ctx, 'highpass', 420, 0.7), tel2 = filt(ctx, 'lowpass', 3300, 0.7), master = gain(ctx, 1);
    tel1.connect(tel2); tel2.connect(master); master.connect(p); p.connect(out);
    // chime
    for (const [f, dt] of [[659.3, 0], [523.3, 0.42]]) {
      const c = ctx.createOscillator(); c.type = 'sine'; c.frequency.value = f; const cg = gain(ctx, 0);
      cg.gain.setValueAtTime(0, now + dt); cg.gain.linearRampToValueAtTime(0.05, now + dt + 0.01); cg.gain.exponentialRampToValueAtTime(0.0008, now + dt + 1.2);
      c.connect(cg); cg.connect(tel1); c.start(now + dt); c.stop(now + dt + 1.3); nodes.push(c, cg);
    }
    // voice: glottal saw → 3 formants, re-tuned per syllable
    const src = ctx.createOscillator(); src.type = 'sawtooth'; src.frequency.value = 118;
    const fm = [0, 1, 2].map(i => { const b = filt(ctx, 'bandpass', 800, 7); const g = gain(ctx, [1, 0.55, 0.3][i]); b.connect(g); g.connect(tel1); return b; });
    const vg = gain(ctx, 0); src.connect(vg); fm.forEach(b => vg.connect(b));
    let t = now + 1.1; const base = rand(105, 135);
    vg.gain.setValueAtTime(0, t);
    for (let i = 0; i < syl; i++) {
      const v = VOWELS[(Math.random() * VOWELS.length) | 0], d = rand(0.1, 0.2);
      fm.forEach((b, k) => b.frequency.setTargetAtTime(v[k] * rand(0.92, 1.08), t, 0.02));
      src.frequency.setTargetAtTime(base * (1 + 0.12 * Math.sin(i * 0.7) + rand(-0.04, 0.04)) * (i % 6 === 5 ? 0.88 : 1), t, 0.03);
      vg.gain.setTargetAtTime(0.5, t, 0.012); vg.gain.setTargetAtTime(0.05, t + d * 0.7, 0.02);
      t += d + (i % 6 === 5 ? rand(0.25, 0.4) : 0.015);
    }
    vg.gain.setTargetAtTime(0, t, 0.03);
    src.start(now + 1); src.stop(t + 0.3); nodes.push(src, vg, tel1, tel2, master, p, ...fm);
    setTimeout(() => nodes.forEach(x => { try { x.disconnect(); } catch { /* done */ } }), (t - now + 1) * 1000);
  }

  function droplet(now) {
    const o = ctx.createOscillator(); o.type = 'sine'; o.frequency.value = rand(2200, 6500);
    const g = gain(ctx, 0), pn = ctx.createStereoPanner(); pn.pan.value = rand(-0.9, 0.9);
    g.gain.setValueAtTime(0, now); g.gain.linearRampToValueAtTime(rand(0.004, 0.012), now + 0.001); g.gain.exponentialRampToValueAtTime(0.0002, now + 0.012);
    o.connect(g); g.connect(pn); pn.connect(out); o.start(now); o.stop(now + 0.02);
    o.onended = () => { try { o.disconnect(); g.disconnect(); pn.disconnect(); } catch { /* done */ } };
  }

  return {
    out,
    /** st: { rain 0..1, city (level), tunnel 0..1, under 0..1, paused, listener:{x,y,z}, dt } */
    update(now, st) {
      rampGain(cityG.gain, 0.8 * st.city, now, 0.4);
      ramp(hl.frequency, 230 - 80 * st.tunnel, now, 0.5);
      const rainK = clamp(st.rain, 0, 1) * (1 - 0.92 * st.tunnel) * (1 - 0.35 * st.under);
      rampGain(rainG.gain, 0.07 * rainK, now, 0.5);
      rampGain(fanG.gain, 0.5 * st.tunnel, now, 0.5);
      if (!st.dt) return;
      dropT -= st.dt; if (dropT <= 0 && rainK > 0.03) { droplet(now + Math.random() * 0.03); dropT = rand(0.03, 0.25) / (0.3 + rainK); }
      if (st.under > 0.4 && rainK > 0.02 && Math.random() < st.dt * 3) droplet(now);       // drips under the deck
      sirenT -= st.dt; paT -= st.dt;
      if (sirenT <= 0) { sirenT = rand(35, 80); if (st.tunnel < 0.5) spawnSiren(now, st.listener); }
      if (paT <= 0) { paT = rand(45, 100); if (st.tunnel < 0.5) spawnAnnouncement(now, st.listener); }
    },
    trigger(kind, now, pos) { if (kind === 'siren') spawnSiren(now, pos); else if (kind === 'pa') spawnAnnouncement(now, pos); },
  };
}
