// Continuous voices: player EV drive unit, tyres, wind, wall scrape, AI engines (positional).
// Every voice is built once against the shared core `A` and driven by cheap update() calls that only set
// smoothed AudioParam targets (no clicks, NaN-guarded).
import { clamp, smooth, ramp, rampGain, noiseSource, makeWave, safe, cents } from './util.js';

const bp = (ctx, f, q, type = 'bandpass') => { const b = ctx.createBiquadFilter(); b.type = type; b.frequency.value = f; b.Q.value = q; return b; };
const gain = (ctx, v = 0) => { const g = ctx.createGain(); g.gain.value = v; return g; };
const osc = (ctx, type, f, wave) => { const o = ctx.createOscillator(); if (wave) o.setPeriodicWave(wave); else o.type = type; o.frequency.value = f; o.start(); return o; };

// ============================================================================================ drive unit
export function createDriveUnit(A) {
  const { ctx } = A;
  const out = gain(ctx, 0); out.connect(A.buses.engine);
  const soft = makeWave(ctx, [1, 0.32, 0.12, 0.05]), reedy = makeWave(ctx, [1, 0.5, 0.33, 0.25, 0.2, 0.16, 0.12, 0.1]), hollow = makeWave(ctx, [1, 0, 0.3, 0, 0.14, 0, 0.07]);

  const whineLP = bp(ctx, 3000, 0.7, 'lowpass'); whineLP.connect(out);
  const mk = (wave, ratio, k, dest = whineLP) => { const o = osc(ctx, 'sine', 200, wave), g = gain(ctx, 0); o.connect(g); g.connect(dest); return { o, g, ratio, k }; };

  // harmonics 2 & 3 pass through an AM stage ("growl")
  const growl = gain(ctx, 0.8); growl.connect(whineLP);
  const am = osc(ctx, 'sine', 300), amDepth = gain(ctx, 0.2); am.connect(amDepth); amDepth.connect(growl.gain);
  const P = [
    mk(soft, 1, 0.20), mk(hollow, 2, 0.13, growl), mk(soft, 3, 0.09, growl), mk(soft, 4.03, 0.04),
    mk(null, 6.0, 0.024), mk(null, 7.0, 0.038), mk(null, 7.055, 0.032),
  ];
  // low register: rotor tone (reedy saw through its own LP) + sub
  const lowLP = bp(ctx, 520, 0.7, 'lowpass'); lowLP.connect(out);
  const low = osc(ctx, 'sine', 70, reedy), lowG = gain(ctx, 0); low.connect(lowG); lowG.connect(lowLP);
  const sub = osc(ctx, 'sine', 34), subG = gain(ctx, 0); sub.connect(subG); subG.connect(out);
  // inverter: constant hum + PWM chirp
  const hum1 = osc(ctx, 'sine', 94), hum2 = osc(ctx, 'sine', 141), humG = gain(ctx, 0);
  hum1.connect(humG); hum2.connect(humG); humG.connect(out);
  const chirp = osc(ctx, 'triangle', 5200), chirpHP = bp(ctx, 4200, 0.7, 'highpass'), chirpG = gain(ctx, 0);
  chirp.connect(chirpHP); chirpHP.connect(chirpG); chirpG.connect(out);
  // regen whistle (lift-off)
  const rg = osc(ctx, 'sine', 400), rg2 = osc(ctx, 'sine', 800), rgG = gain(ctx, 0);
  rg.connect(rgG); rg2.connect(rgG); rgG.connect(out);

  return {
    out,
    /** st: { rpmN 0..1.1, load 0..1, throttle, power (kW, − = regen), cabin 0..1, duck 0..1 } */
    update(now, st) {
      const r = clamp(st.rpmN, 0, 1.15), load = clamp(st.load, 0, 1);
      const fw = 120 + 1500 * r, fl = 62 + 120 * r;
      const lev = (0.1 + 0.9 * Math.pow(r, 0.55)) * (0.28 + 0.72 * load);
      for (const p of P) { ramp(p.o.frequency, fw * p.ratio, now, 0.03); ramp(p.g.gain, p.k * lev * (p.ratio > 6 ? 0.7 + 0.5 * load : 1), now, 0.05); }
      ramp(am.frequency, fl * 3, now, 0.05); ramp(amDepth.gain, 0.12 + 0.25 * load, now, 0.1);
      ramp(whineLP.frequency, (1300 + 7200 * (0.25 + 0.75 * load) * (0.3 + 0.7 * r)) * (0.78 + 0.22 * st.cabin), now, 0.06);
      ramp(low.frequency, fl, now, 0.04); ramp(lowG.gain, 0.20 * (0.3 + 0.7 * load) * (0.35 + 0.65 * Math.min(1, r * 2)), now, 0.06);
      ramp(sub.frequency, 31 + 38 * r, now, 0.05); ramp(subG.gain, 0.14 * (0.35 + 0.65 * load) * smooth(0.0, 0.08, r), now, 0.08);
      ramp(humG.gain, 0.020 + 0.020 * load, now, 0.1);
      ramp(chirp.frequency, 5000 + 1400 * r, now, 0.05); ramp(chirpG.gain, 0.012 * load * smooth(0.1, 0.5, r), now, 0.08);
      const reg = clamp(-safe(st.power) / 220, 0, 1) * smooth(0.04, 0.3, r);
      ramp(rg.frequency, fw * 0.5, now, 0.04); ramp(rg2.frequency, fw * 1.5, now, 0.04); ramp(rgG.gain, 0.075 * reg, now, 0.08);
      const tot = smooth(-0.001, 0.02, r) * 0.2 + 0.8 * smooth(0, 0.06, r);   // silent when stopped (EV)
      ramp(out.gain, 0.78 * (1 + 0.35 * st.cabin) * (1 - 0.85 * st.duck) * (0.2 + tot * 0.8) * (r > 0.002 ? 1 : 0.35), now, 0.06);
    },
  };
}

// ============================================================================================ tyres
export function createTyres(A) {
  const { ctx, noise } = A;
  const out = gain(ctx, 1); out.connect(A.buses.tyre);
  const chain = (buf, nodes, g = 0) => {
    const s = noiseSource(ctx, buf); let n = s;
    for (const x of nodes) { n.connect(x); n = x; }
    const G = gain(ctx, g); n.connect(G); G.connect(out); return { G, nodes };
  };
  const roll = chain(noise.pink, [bp(ctx, 1500, 0.6), bp(ctx, 380, 0.7, 'highpass')]);
  const roar = chain(noise.brown, [bp(ctx, 240, 0.7, 'lowpass')]);
  const spray = chain(noise.white, [bp(ctx, 3200, 0.7, 'highpass'), bp(ctx, 6200, 0.45)]);
  const scrub = chain(noise.pink, [bp(ctx, 760, 0.9)]);
  // squeal: band-limited noise + a saw with vibrato, one voice per axle
  const squeal = (f0) => {
    const nS = noiseSource(ctx, noise.white), nB = bp(ctx, f0, 14), nG = gain(ctx, 1.0);
    nS.connect(nB); nB.connect(nG);
    const o = osc(ctx, 'sawtooth', f0), oB = bp(ctx, f0, 6), oG = gain(ctx, 0.5);
    o.connect(oB); oB.connect(oG);
    const lfo = osc(ctx, 'sine', 9), lfoG = gain(ctx, 45); lfo.connect(lfoG); lfoG.connect(o.detune);
    const G = gain(ctx, 0); nG.connect(G); oG.connect(G); G.connect(out);
    return { nB, oB, o, G, lfo };
  };
  const sqF = squeal(1000), sqR = squeal(800);
  return {
    out,
    /** st: { v m/s (abs), wet 0..1, skidF, skidR, slipAng (0..1 lateral), brake } */
    update(now, st) {
      const v = Math.abs(st.v), vN = clamp(v / 90, 0, 1.3), wet = clamp(st.wet, 0, 1);
      rampGain(roll.G.gain, 0.44 * Math.pow(vN, 1.15) * (0.7 + 0.3 * wet) * smooth(0.2, 3, v), now, 0.08);
      ramp(roll.nodes[0].frequency, 750 + 1900 * vN, now, 0.1);
      rampGain(roar.G.gain, 0.30 * vN * smooth(0.3, 4, v), now, 0.1); ramp(roar.nodes[0].frequency, 200 + 200 * vN, now, 0.1);
      rampGain(spray.G.gain, 0.12 * Math.pow(vN, 1.7) * (0.35 + 0.65 * wet) * (1 + 0.6 * st.slipAng), now, 0.1);
      const sk = Math.max(st.skidF, st.skidR);
      rampGain(scrub.G.gain, 0.20 * smooth(0.12, 0.8, sk) * smooth(2, 35, v), now, 0.05);
      const vv = 0.45 + 0.55 * smooth(4, 40, v);
      const q = (s, sk2, base, span) => {
        const f = base + span * sk2 + 360 * vN;
        ramp(s.nB.frequency, f, now, 0.04); ramp(s.oB.frequency, f, now, 0.04); ramp(s.o.frequency, f * 0.5, now, 0.04);
        rampGain(s.G.gain, 0.20 * Math.pow(smooth(0.3, 0.95, sk2), 1.3) * vv, now, 0.035);
      };
      q(sqF, st.skidF, 900, 420); q(sqR, st.skidR, 720, 340);
    },
  };
}

// ============================================================================================ wind
export function createWind(A) {
  const { ctx, noise } = A;
  const out = gain(ctx, 1); out.connect(A.buses.wind);
  const side = (buf, pan) => {
    const s = noiseSource(ctx, buf), lp = bp(ctx, 600, 0.5, 'lowpass'), G = gain(ctx, 0), p = ctx.createStereoPanner(); p.pan.value = pan;
    s.connect(lp); lp.connect(G); G.connect(p); p.connect(out); return { lp, G };
  };
  const L = side(noise.pink, -0.55), R = side(noise.pink, 0.55);
  const whS = noiseSource(ctx, noise.white), whB = bp(ctx, 2200, 9), whG = gain(ctx, 0); whS.connect(whB); whB.connect(whG); whG.connect(out);
  const bfS = noiseSource(ctx, noise.brown), bfL = bp(ctx, 110, 0.6, 'lowpass'), bfG = gain(ctx, 0); bfS.connect(bfL); bfL.connect(bfG); bfG.connect(out);
  const flut = osc(ctx, 'sine', 0.37), flutD = gain(ctx, 0.0); flut.connect(flutD); flutD.connect(L.G.gain); flutD.connect(R.G.gain);
  return {
    out,
    update(now, st) {
      const vN = clamp(Math.abs(st.v) / 90, 0, 1.35);
      const g = 0.84 * vN * vN * (1 + 0.5 * st.cabin);
      rampGain(L.G.gain, g, now, 0.12); rampGain(R.G.gain, g, now, 0.12);
      const f = 300 + 4800 * Math.pow(vN, 1.3); ramp(L.lp.frequency, f, now, 0.1); ramp(R.lp.frequency, f * 0.93, now, 0.1);
      ramp(whB.frequency, 1800 + 2400 * vN, now, 0.1); rampGain(whG.gain, 0.05 * Math.pow(vN, 3) * (1 + st.cabin), now, 0.15);
      rampGain(bfG.gain, 0.35 * vN * vN, now, 0.15);
      ramp(flutD.gain, 0.05 * vN * g, now, 0.2);
    },
  };
}

// ============================================================================================ cold-gas thrusters
// Compressed air through four nozzles: a hard high hiss (jet noise peaks high for small nozzles), a broadband low roar of
// the mixing wake, turbulence flutter, and a valve "tock + pssh" when the valves crack open. The hiss pitch sags as the
// tank pressure falls; from inside the cabin the rear blast is muffled.
export function createThruster(A) {
  const { ctx, noise } = A;
  const out = gain(ctx, 1), tone = bp(ctx, 9000, 0.5, 'lowpass'); tone.connect(out); out.connect(A.buses.engine);
  const hS = noiseSource(ctx, noise.white), hH = bp(ctx, 1800, 0.7, 'highpass'), hB = bp(ctx, 4200, 1.1), hG = gain(ctx, 0);
  hS.connect(hH); hH.connect(hB); hB.connect(hG); hG.connect(tone);
  const rS = noiseSource(ctx, noise.pink), rL = bp(ctx, 420, 0.6, 'lowpass'), rG = gain(ctx, 0);
  rS.connect(rL); rL.connect(rG); rG.connect(tone);
  const fl = osc(ctx, 'triangle', 31), flG = gain(ctx, 0); fl.connect(flG); flG.connect(hG.gain);
  // valve transient: a short noise burst and a low knock, enveloped per event
  const pS = noiseSource(ctx, noise.white), pB = bp(ctx, 2600, 0.9), pG = gain(ctx, 0); pS.connect(pB); pB.connect(pG); pG.connect(tone);
  const kO = osc(ctx, 'sine', 95), kG = gain(ctx, 0); kO.connect(kG); kG.connect(tone);
  let prev = 0;
  return {
    out,
    update(now, st) {
      const L = clamp(st.level, 0, 1), P = clamp(st.gas, 0, 1), c = st.cabin;
      if (L > 0.08 && prev <= 0.08) {
        pG.gain.cancelScheduledValues(now); pG.gain.setValueAtTime(0.55, now); pG.gain.setTargetAtTime(0, now + 0.01, 0.05);
        kG.gain.cancelScheduledValues(now); kG.gain.setValueAtTime(0.5, now); kG.gain.setTargetAtTime(0, now + 0.005, 0.03);
      } else if (L < 0.3 && prev >= 0.3) {   // valves shut: a softer exhale
        pG.gain.cancelScheduledValues(now); pG.gain.setValueAtTime(0.18, now); pG.gain.setTargetAtTime(0, now + 0.02, 0.12);
      }
      prev = L;
      const press = 0.55 + 0.45 * Math.sqrt(P);
      rampGain(hG.gain, 0.42 * L * press, now, 0.03);
      ramp(hB.frequency, 2600 + 2400 * P, now, 0.08);
      rampGain(rG.gain, 0.75 * L * (0.7 + 0.3 * P), now, 0.04);
      ramp(flG.gain, 0.08 * L, now, 0.05);
      ramp(tone.frequency, 9000 - 7400 * c, now, 0.1);
    },
  };
}

// ============================================================================================ scrape (wall grinding)
export function createScrape(A, positional = false) {
  const { ctx, noise } = A;
  const G = gain(ctx, 0);
  let panner = null;
  if (positional) {
    panner = ctx.createPanner(); panner.panningModel = 'equalpower'; panner.distanceModel = 'inverse';
    panner.refDistance = 6; panner.maxDistance = 250; panner.rolloffFactor = 1.4;
    G.connect(panner); panner.connect(A.buses.impact);
  } else G.connect(A.buses.impact);
  const nS = noiseSource(ctx, noise.white), nB = bp(ctx, 1900, 1.3), nH = bp(ctx, 500, 0.7, 'highpass'); nS.connect(nB); nB.connect(nH);
  const nG = gain(ctx, 0.9); nH.connect(nG); nG.connect(G);
  const o = osc(ctx, 'sawtooth', 150), oL = bp(ctx, 1400, 0.7, 'lowpass'), oG = gain(ctx, 0.28); o.connect(oL); oL.connect(oG); oG.connect(G);
  const jit = osc(ctx, 'square', 23), jitG = gain(ctx, 0.25); jit.connect(jitG); jitG.connect(nG.gain);
  return {
    G, panner,
    update(now, intensity, speedN, pos) {
      const k = clamp(intensity, 0, 1);
      rampGain(G.gain, 0.34 * k, now, 0.04);
      ramp(o.frequency, 110 + 160 * speedN, now, 0.05); ramp(nB.frequency, 1200 + 1800 * k, now, 0.05);
      if (panner && pos) { ramp(panner.positionX, pos.x, now, 0.03); ramp(panner.positionY, pos.y, now, 0.03); ramp(panner.positionZ, pos.z, now, 0.03); }
    },
  };
}

// ============================================================================================ AI cars
const SPEED_OF_SOUND = 343;
export function createAiVoice(A) {
  const { ctx, noise } = A;
  const panner = ctx.createPanner(); panner.panningModel = 'equalpower'; panner.distanceModel = 'inverse';
  panner.refDistance = 9; panner.maxDistance = 320; panner.rolloffFactor = 1.55;
  const G = gain(ctx, 0); G.connect(panner); panner.connect(A.buses.ai);
  const lp = bp(ctx, 2200, 0.6, 'lowpass'); lp.connect(G);
  const mk = (type, g) => { const o = osc(ctx, type, 200), og = gain(ctx, g); o.connect(og); og.connect(lp); return o; };
  const o1 = mk('triangle', 0.5), o2 = mk('sawtooth', 0.14), o3 = mk('sine', 0.4), o4 = mk('sine', 0.18);
  const tS = noiseSource(ctx, noise.pink), tB = bp(ctx, 1300, 0.7), tG = gain(ctx, 0); tS.connect(tB); tB.connect(tG); tG.connect(panner);
  const wS = noiseSource(ctx, noise.white), wB = bp(ctx, 900, 0.9), wG = gain(ctx, 0); wS.connect(wB); wB.connect(wG); wG.connect(panner);   // pass-by whoosh
  let ratio = 1, active = true;
  return {
    panner, G,
    /** dist = distance to the listener (m), closing = closing speed (m/s, + = approaching), pos = car world position */
    update(now, car, rpmN, dist, closing, pos, load) {
      if (dist > 230) {
        if (active) { rampGain(G.gain, 0, now, 0.1); rampGain(tG.gain, 0, now, 0.1); rampGain(wG.gain, 0, now, 0.1); active = false; }
        return;
      }
      active = true;
      const dop = clamp(SPEED_OF_SOUND / (SPEED_OF_SOUND - clamp(closing, -80, 80)), 0.82, 1.22);
      ratio += (dop - ratio) * 0.25;
      const r = clamp(rpmN, 0, 1.1), fw = 110 + 1050 * r, det = cents(ratio);
      ramp(o1.frequency, fw, now, 0.06); ramp(o2.frequency, fw * 2, now, 0.06); ramp(o3.frequency, fw * 0.5, now, 0.06); ramp(o4.frequency, fw * 3.01, now, 0.06);
      for (const o of [o1, o2, o3, o4]) ramp(o.detune, det, now, 0.05);
      const ld = clamp(load, 0, 1), lev = (0.12 + 0.88 * Math.pow(r, 0.5)) * (0.3 + 0.7 * ld);
      rampGain(G.gain, 0.34 * lev * smooth(0.002, 0.05, r), now, 0.08);
      ramp(lp.frequency, 1200 + 3800 * r * (0.4 + 0.6 * ld), now, 0.1);
      const vN = clamp(Math.abs(car.speed) / 90, 0, 1.2);
      rampGain(tG.gain, 0.20 * Math.pow(vN, 1.2), now, 0.1); ramp(tB.frequency, 900 + 1400 * vN, now, 0.1);
      const whoosh = smooth(26, 3, dist) * clamp(Math.abs(closing) / 55, 0, 1);
      rampGain(wG.gain, 0.5 * whoosh, now, 0.05); ramp(wB.frequency, 700 + 900 * whoosh, now, 0.05);
      if (pos) { ramp(panner.positionX, pos.x, now, 0.03); ramp(panner.positionY, pos.y, now, 0.03); ramp(panner.positionZ, pos.z, now, 0.03); }
    },
  };
}
