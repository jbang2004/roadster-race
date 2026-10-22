// Sign placement: shop banners, vertical blade signs, rooftop signs, advertising screens, glow halos. All emissive, atlas-based.
import { mulberry32, hash2, clamp } from './util.js';
import { SIDEWALK } from './params.js';

export function addHalo(ctx, ch, x, y, z, size, r, g, b, lvl = 0) {
  const gg = ctx.geo('halo', ch); gg.lv(lvl); gg.color(r, g, b, 1);
  const i0 = gg.n;
  const cs = [[-1, -1, 0, 0], [1, -1, 1, 0], [1, 1, 1, 1], [-1, 1, 0, 1]];
  for (const [ox, oy, u, v] of cs) { gg.ex('aCorner', size, ox, oy); gg.vert(x, y, z, 0, 0, 1, u, v); }
  gg.quad(i0, i0 + 1, i0 + 2, i0 + 3);
}

const ZPAL = {
  boulevard: ['cyan', 'magenta', 'violet', 'white'], street: ['cyan', 'magenta', 'amber', 'white'], docks: ['amber', 'green', 'cyan', 'red'],
  ramp: ['cyan', 'amber', 'white'], expressway: ['cyan', 'magenta', 'violet'], descent: ['cyan', 'amber'], tunnel: ['green', 'white'],
  market: ['amber', 'red', 'magenta', 'green', 'cyan'],
};

function palTint(palKey, rnd) {
  // vertex tint (multiplies the atlas, which is already coloured): slight brightness variation
  const k = 0.8 + rnd() * 0.45; return [k, k, k];
}

export function signQuad(g, c, right, up, w, h, uv, nrm) {
  const hx = right[0] * w / 2, hz = right[1] * w / 2;
  const p0 = [c[0] - hx, c[1] - h / 2, c[2] - hz], p1 = [c[0] + hx, c[1] - h / 2, c[2] + hz], p2 = [c[0] + hx, c[1] + h / 2, c[2] + hz], p3 = [c[0] - hx, c[1] + h / 2, c[2] - hz];
  g.quadUV(p0, p1, p2, p3, [[uv.u0, uv.v0], [uv.u1, uv.v0], [uv.u1, uv.v1], [uv.u0, uv.v1]]);
}

export function buildSigns(ctx, atlas) {
  const rnd = mulberry32(555);
  const S = atlas.signs;
  const Hs = S.filter(s => s.kind === 'h'), Vs = S.filter(s => s.kind === 'v');
  const byPal = (arr, pals) => { const a = arr.filter(s => pals.includes(s.pal)); return a.length ? a : arr; };
  let nSigns = 0;
  for (const b of ctx.buildings) {
    if (b.row > 0 || b.dist > 100 || b.yard) continue;
    const pals = ZPAL[b.zone] ?? ZPAL.street;
    const Hz = byPal(Hs, pals), Vz = byPal(Vs, pals);
    const ch = b.ch, ex = b.ex, nrm = [-b.ez[0], -b.ez[1]];
    const right = [nrm[1], -nrm[0]];                           // horizontal 'right' for a viewer in front of the facade looking at it
    const frontC = [b.cx + nrm[0] * b.d / 2, b.cz + nrm[1] * b.d / 2];
    const T0 = b.tiers[0];
    const market = b.zone === 'market', street = b.zone === 'street', blvd = b.zone === 'boulevard';
    const gsign = ctx.geo('sign', ch), ghouse = ctx.geo('steel', ch);
    ghouse.lv(0); ghouse.color(.1, .11, .13, 1);
    // ---- banners above the shopfront band ----
    if (b.podH > 0 && b.dist < 60) {
      const nB = Math.max(1, Math.floor(b.w / 6.5));
      for (let k = 0; k < nB; k++) {
        const off = (k + .5 - nB / 2) * (b.w / nB);
        const sw = clamp(b.w / nB - 0.7, 2.6, market ? 4.2 : 6.5), sh = sw / 4;
        const d = Hz[Math.floor(rnd() * Hz.length)];
        const yc = Math.min(b.podH - 0.35 - sh / 2, b.podH * 0.9) ;
        const c = [frontC[0] + ex[0] * off + nrm[0] * 0.2, yc, frontC[1] + ex[1] * off + nrm[1] * 0.2];
        const t = palTint(d.pal, rnd);
        gsign.color(t[0], t[1], t[2], 1); gsign.ex('aFl', rnd() * 6, rnd() < .25 ? 1 : 0);
        signQuad(gsign, c, right, 0, sw, sh, d, nrm);
        ghouse.box(c[0] - nrm[0] * 0.15, c[1], c[2] - nrm[1] * 0.15, sw + 0.15, sh + 0.15, 0.22, Math.atan2(-right[1], right[0]));
        nSigns++;
        if (rnd() < (market ? .35 : .2)) {
          const col = { cyan: [.3, .9, 1], magenta: [1, .25, .8], violet: [.6, .35, 1], amber: [1, .6, .2], green: [.3, 1, .5], red: [1, .25, .15], white: [.8, .9, 1] }[d.pal];
          ctx.light({ pos: [c[0] + nrm[0] * 1.2, Math.max(2.5, yc - 1), c[2] + nrm[1] * 1.2], color: col, intensity: 70, range: 11, kind: 'neon' }, 0);
        }
      }
    }
    // ---- blade signs ----
    if ((market || street || b.zone === 'docks') && b.dist < 50) {
      const nBl = market ? (rnd() < .8 ? 1 : 2) : (rnd() < .5 ? 1 : 0);
      for (let k = 0; k < nBl; k++) {
        const off = (rnd() - .5) * (b.w - 1.2);
        const bw = market ? 1.1 : 0.95, bh = bw * (3.4 + rnd() * 1.2), proj = market ? rr(rnd, 1.6, 3.4) : rr(rnd, .9, 1.6);
        const d = Vz[Math.floor(rnd() * Vz.length)];
        const yc = Math.max(b.podH + 0.8, 3.2) + bh / 2 + rnd() * (market ? 4 : 6);
        const cc = [frontC[0] + ex[0] * off + nrm[0] * (0.1 + proj / 2), yc, frontC[1] + ex[1] * off + nrm[1] * (0.1 + proj / 2)];
        // two faces: normals +ex and -ex (the board spans along the facade normal)
        for (const sgn of [1, -1]) {
          const n2 = [ex[0] * sgn, ex[1] * sgn], r2 = [n2[1], -n2[0]];
          const c2 = [cc[0] + n2[0] * 0.07, yc, cc[2] + n2[1] * 0.07];
          const t = palTint(d.pal, rnd);
          gsign.color(t[0], t[1], t[2], 1); gsign.ex('aFl', rnd() * 6, rnd() < .2 ? 1 : 0);
          signQuad(gsign, c2, r2, 0, proj, bh, d, n2);
        }
        ghouse.box(cc[0], yc, cc[2], proj + 0.1, bh + 0.1, 0.12, Math.atan2(-nrm[1], nrm[0]));
        nSigns++;
        if (rnd() < .5) {
          const col = { cyan: [.3, .9, 1], magenta: [1, .25, .8], violet: [.6, .35, 1], amber: [1, .6, .2], green: [.3, 1, .5], red: [1, .25, .15], white: [.8, .9, 1] }[d.pal];
          ctx.light({ pos: [cc[0] + nrm[0] * 0.6, yc, cc[2] + nrm[1] * 0.6], color: col, intensity: 90, range: 13, kind: 'neon' }, 0);
          addHalo(ctx, ch, cc[0], yc, cc[2], 2.6, col[0] * .5, col[1] * .5, col[2] * .5);
        }
      }
    }
    // ---- rooftop signs on tall buildings of the boulevard / street / expressway ----
    if (b.h > 35 && (blvd || street || b.zone === 'expressway') && b.dist < 90 && rnd() < .55) {
      const d = Hz[Math.floor(rnd() * Hz.length)];
      const sw = clamp(b.w * 0.55, 8, 16), sh = sw / 4;
      const yc = b.tiers[b.tiers.length - 1].yt + 2.2 + sh / 2, T_ = b.tiers[b.tiers.length - 1];
      const c = [b.cx + b.ez[0] * T_.off + nrm[0] * (T_.d / 2 - 1.2), yc, b.cz + b.ez[1] * T_.off + nrm[1] * (T_.d / 2 - 1.2)];
      gsign.color(1, 1, 1, 1); gsign.ex('aFl', rnd() * 6, 1);
      signQuad(gsign, c, right, 0, sw, sh, d, nrm);
      ghouse.box(c[0] - nrm[0] * 0.2, c[1], c[2] - nrm[1] * 0.2, sw + 0.3, sh + 0.3, 0.3, Math.atan2(-right[1], right[0]));
      ghouse.box(c[0] - nrm[0] * 0.2, c[1] - sh / 2 - 1.1, c[2] - nrm[1] * 0.2, 0.3, 2.2, 0.3, 0);
      const col = { cyan: [.3, .9, 1], magenta: [1, .25, .8], violet: [.6, .35, 1], amber: [1, .6, .2], green: [.3, 1, .5], red: [1, .25, .15], white: [.8, .9, 1] }[d.pal];
      ctx.light({ pos: [c[0] + nrm[0] * 3, yc, c[2] + nrm[1] * 3], color: col, intensity: 220, range: 28, kind: 'sign' }, 0);
      addHalo(ctx, ch, c[0] + nrm[0] * .5, yc, c[2] + nrm[1] * .5, sw * .9, col[0] * .25, col[1] * .25, col[2] * .25);
      nSigns++;
    }
    // ---- advertising screens on the facade (boulevard + some expressway-side towers) ----
    if (b.h > 40 && (blvd || b.zone === 'expressway' || b.zone === 'street') && b.dist < 100 && b.w > 20 && rnd() < (blvd ? .55 : .3)) {
      const sw = clamp(b.w * (.55 + rnd() * .3), 12, 28), sh = sw / 2;
      const yb = Math.max(b.podH, 6) + 4 + rnd() * 18;
      if (yb + sh < b.h - 3) {
        const off = (rnd() - .5) * (b.w - sw - 2);
        const c = [frontC[0] + ex[0] * off + nrm[0] * 0.35, yb + sh / 2, frontC[1] + ex[1] * off + nrm[1] * 0.35];
        const gs = ctx.geo('screen', ch);
        const grp = Math.floor(rnd() * atlas.screens);
        gs.color(1, 1, 1, 1); gs.ex('aScr', grp, rnd() * 5, .18 + rnd() * .15, 0);
        const hx = right[0] * sw / 2, hz = right[1] * sw / 2;
        gs.quadUV([c[0] - hx, c[1] - sh / 2, c[2] - hz], [c[0] + hx, c[1] - sh / 2, c[2] + hz], [c[0] + hx, c[1] + sh / 2, c[2] + hz], [c[0] - hx, c[1] + sh / 2, c[2] - hz], [[0, 0], [1, 0], [1, 1], [0, 1]]);
        // dark frame
        ghouse.box(c[0] - nrm[0] * 0.3, c[1], c[2] - nrm[1] * 0.3, sw + 1.0, sh + 1.0, 0.5, Math.atan2(-right[1], right[0]));
        const col = [[.3, .8, 1], [1, .3, .8], [.7, .4, 1], [1, .65, .3]][grp % 4];
        ctx.light({ pos: [c[0] + nrm[0] * 6, c[1] - sh * .3, c[2] + nrm[1] * 6], color: col, intensity: 300, range: 34, kind: 'sign' }, 0);
        addHalo(ctx, ch, c[0] + nrm[0] * 1.5, c[1], c[2] + nrm[1] * 1.5, sw * .75, col[0] * .18, col[1] * .18, col[2] * .18);
        nSigns++;
      }
    }
  }
  ctx.stats.signs = nSigns;
}
const rr = (rnd, a, b) => a + (b - a) * rnd();
