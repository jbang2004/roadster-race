// Mini-map: the whole circuit, north-up (the loop is nearly square, so the full shape fits a small tile and
// every car's position reads at a glance). The static road art is rendered once into an offscreen canvas;
// per frame we only blit it and draw ≤ 8 markers.
import { LIVERY_COLORS } from './format.js';

const ZONE_COLORS = {
  boulevard: '#3ee8ff', street: '#62c4ff', docks: '#4de6c4', ramp: '#8f95ff',
  expressway: '#c690ff', descent: '#ff7ad9', tunnel: '#ffb340', market: '#ff9a4a',
};

export function createMinimap(track) {
  const canvas = document.createElement('canvas');
  const ctx = canvas.getContext('2d');
  const base = document.createElement('canvas');
  const bctx = base.getContext('2d');

  // world → map transform (north = −Z up)
  let x0 = Infinity, x1 = -Infinity, z0 = Infinity, z1 = -Infinity;
  for (let i = 0; i < track.N; i += 4) {
    x0 = Math.min(x0, track.px[i]); x1 = Math.max(x1, track.px[i]);
    z0 = Math.min(z0, track.pz[i]); z1 = Math.max(z1, track.pz[i]);
  }
  const cx = (x0 + x1) / 2, cz = (z0 + z1) / 2, span = Math.max(x1 - x0, z1 - z0);
  let W = 232, H = 232, K = 1, dpr = 1;
  const tx = (x) => (x - cx) * K + W / 2, ty = (z) => (z - cz) * K + H / 2;

  const startF = track.frameAt(track.startS);
  const STEP = 5;
  // segments sorted by height so bridges/expressway draw over the ground level
  const segs = [];
  for (let i = 0; i < track.N; i += STEP) {
    const j = (i + STEP) % track.N;
    segs.push({ i, j, y: (track.py[i] + track.py[j]) / 2, zone: track.zoneNames[track.zone[i]], kind: track.kind[i] });
  }
  segs.sort((a, b) => a.y - b.y);

  function drawBase() {
    base.width = canvas.width; base.height = canvas.height;
    bctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    bctx.clearRect(0, 0, W, H);
    // faint grid
    bctx.strokeStyle = 'rgba(120,210,255,0.045)'; bctx.lineWidth = 1;
    bctx.beginPath();
    for (let g = 1; g < 6; g++) { const p = Math.round((g * W) / 6) + .5; bctx.moveTo(p, 0); bctx.lineTo(p, H); bctx.moveTo(0, p); bctx.lineTo(W, p); }
    bctx.stroke();
    bctx.lineCap = 'round'; bctx.lineJoin = 'round';
    const w = W / 232; // line scale
    const pass = (width, styleFn, filter) => {
      for (const s of segs) {
        if (filter && !filter(s)) continue;
        bctx.strokeStyle = styleFn(s); bctx.lineWidth = width;
        bctx.beginPath();
        bctx.moveTo(tx(track.px[s.i]), ty(track.pz[s.i]));
        bctx.lineTo(tx(track.px[s.j]), ty(track.pz[s.j]));
        bctx.stroke();
      }
    };
    // Per-height layers: casing + core, low to high, so crossings read as over/under.
    const levels = [[-99, 1], [1, 6], [6, 99]];
    for (const [lo, hi] of levels) {
      const f = (s) => s.y >= lo && s.y < hi;
      pass(7.2 * w, () => 'rgba(3,8,14,0.92)', f);
      pass(5.2 * w, (s) => hexA(ZONE_COLORS[s.zone] ?? '#3ee8ff', 0.14), f);
      pass(2.3 * w, (s) => hexA(ZONE_COLORS[s.zone] ?? '#3ee8ff', s.kind === 3 ? 0.42 : 0.9), f);
    }
    // start / finish line
    const rx = startF.r.x, rz = startF.r.z, hw = 11 * w;
    const sx = tx(startF.pos.x), sy = ty(startF.pos.z), nx = rx / Math.hypot(rx, rz), nz = rz / Math.hypot(rx, rz);
    bctx.strokeStyle = '#fff'; bctx.lineWidth = 2 * w; bctx.lineCap = 'butt';
    bctx.beginPath(); bctx.moveTo(sx - nx * hw * 0.5, sy - nz * hw * 0.5); bctx.lineTo(sx + nx * hw * 0.5, sy + nz * hw * 0.5); bctx.stroke();
    bctx.shadowColor = '#fff'; bctx.shadowBlur = 6 * w; bctx.stroke(); bctx.shadowBlur = 0;
  }

  function resize(cssW, cssH, ratio = Math.min(window.devicePixelRatio || 1, 2)) {
    W = Math.max(16, cssW); H = Math.max(16, cssH); dpr = ratio;
    canvas.width = Math.round(W * dpr); canvas.height = Math.round(H * dpr);
    K = (Math.min(W, H) * 0.86) / span;
    drawBase();
  }

  const fwd = { x: 0, z: 0 };
  function heading(q) {   // rotate (0,0,−1) by quaternion → horizontal heading
    const { x, y, z, w } = q;
    fwd.x = -2 * (x * z + w * y); fwd.z = -(1 - 2 * (x * x + y * y));
    return Math.atan2(fwd.z, fwd.x);
  }

  /** cars: race.cars; player = cars[0]; pulse 0..1 animates the player halo. */
  function draw(cars, player, t) {
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, W, H);
    ctx.drawImage(base, 0, 0, W, H);
    const w = W / 232, pPlace = player?.race?.place ?? 1;
    // AI first, player last (on top)
    for (let k = cars.length - 1; k >= 0; k--) {
      const c = cars[k]; if (!c || c === player || !c.position) continue;
      const x = tx(c.position.x), y = ty(c.position.z);
      const col = LIVERY_COLORS[c.livery ?? k] ?? '#fff';
      const adj = Math.abs((c.race?.place ?? 0) - pPlace) === 1;
      ctx.fillStyle = 'rgba(3,8,14,.9)'; ctx.beginPath(); ctx.arc(x, y, 5.4 * w, 0, 6.2832); ctx.fill();
      ctx.fillStyle = col; ctx.beginPath(); ctx.arc(x, y, 3.7 * w, 0, 6.2832); ctx.fill();
      if (adj) { ctx.strokeStyle = 'rgba(255,255,255,.9)'; ctx.lineWidth = 1.1 * w; ctx.beginPath(); ctx.arc(x, y, 7.4 * w, 0, 6.2832); ctx.stroke(); }
    }
    if (player?.position) {
      const x = tx(player.position.x), y = ty(player.position.z), a = player.quaternion ? heading(player.quaternion) : -Math.PI / 2;
      const pulse = 0.5 + 0.5 * Math.sin(t * 4.2);
      ctx.fillStyle = `rgba(62,232,255,${0.10 + 0.10 * pulse})`; ctx.beginPath(); ctx.arc(x, y, (11 + 4 * pulse) * w, 0, 6.2832); ctx.fill();
      ctx.save(); ctx.translate(x, y); ctx.rotate(a);
      ctx.shadowColor = '#3ee8ff'; ctx.shadowBlur = 8 * w;
      ctx.fillStyle = '#eafcff'; ctx.strokeStyle = 'rgba(3,8,14,.95)'; ctx.lineWidth = 1.6 * w; ctx.lineJoin = 'round';
      ctx.beginPath(); ctx.moveTo(8.5 * w, 0); ctx.lineTo(-5.6 * w, 5.2 * w); ctx.lineTo(-2.8 * w, 0); ctx.lineTo(-5.6 * w, -5.2 * w); ctx.closePath();
      ctx.stroke(); ctx.fill();
      ctx.restore();
    }
  }
  resize(232, 232, 1);
  return { canvas, resize, draw };
}

function hexA(hex, a) {
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${n >> 16},${(n >> 8) & 255},${n & 255},${a})`;
}
