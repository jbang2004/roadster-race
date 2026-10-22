// Liveries: paint parameters + procedurally drawn decal atlas (race number, sponsor names, stripes).
// Index 0 is the player's liquid-silver / copper-rim car. Colours are sRGB hex here, converted to linear by the materials.
import * as THREE from 'three';

/** Sponsor names are invented. paint: base colour + metal/rough/coat, flake sparkle, pearl (fresnel tint rgb + strength). */
export const LIVERIES = [
  { name: 'Liquid Silver', short: '霓虹', number: '88', plate: 'RDSTR', sponsor: 'NEON LOOP  霓虹环线', style: 'pinstripe',
    paint: { color: 0xc6c9ce, metalness: 0.7, roughness: 0.3, clearcoat: 1, coatRough: 0.03, flake: 0.5, flakeColor: 0xffffff, pearl: null },
    rim: { accent: 0xdc8042 }, accent: 0xdc8042, ink: 0x15161a, numberBg: 0xdc8042, roughnessJitter: 0.0 },
  { name: 'Matte Graphite', short: '石墨', number: '11', sponsor: 'NOVA QUANTUM', style: 'cyanbars',
    paint: { color: 0x25272b, metalness: 0.55, roughness: 0.66, clearcoat: 0.0, coatRough: 0.4, flake: 0.25, flakeColor: 0x9fb7c8, pearl: null },
    rim: { accent: 0x18d8ff }, accent: 0x18d8ff, ink: 0xf2fbff, numberBg: 0x18d8ff, numberInk: 0x061018 },
  { name: 'Pearl White', short: '珍珠', number: '23', sponsor: 'KAZE MOTORS  風', style: 'magentafade',
    paint: { color: 0xe6e6ee, metalness: 0.35, roughness: 0.20, clearcoat: 1, coatRough: 0.03, flake: 0.30, flakeColor: 0xffe8ff, pearl: [0.95, 0.2, 0.62, 0.8] },
    rim: { accent: 0xff2fa8 }, accent: 0xff2fa8, ink: 0x201428, numberBg: 0xff2fa8, numberInk: 0xffffff },
  { name: 'Candy Red', short: '糖红', number: '46', sponsor: 'DRAGONVOLT  龙腾电力', style: 'goldline',
    paint: { color: 0xb0061c, metalness: 0.92, roughness: 0.16, clearcoat: 1, coatRough: 0.025, flake: 0.5, flakeColor: 0xff5a3a, pearl: null },
    rim: { accent: 0xe8b04a }, accent: 0xe8b04a, ink: 0xfff4de, numberBg: 0x1a0508, numberInk: 0xe8b04a },
  { name: 'Midnight Blue', short: '午夜', number: '05', sponsor: 'HEXAGRID', style: 'hexes',
    paint: { color: 0x0b1d6e, metalness: 0.92, roughness: 0.26, clearcoat: 1, coatRough: 0.03, flake: 0.85, flakeColor: 0x9cc4ff, pearl: null },
    rim: { accent: 0xcfe2ff }, accent: 0x6fb2ff, ink: 0xe9f2ff, numberBg: 0xe9f2ff, numberInk: 0x0b1d6e },
  { name: 'Acid Lime', short: '酸绿', number: '69', sponsor: 'ZEPHYR AERO', style: 'blackslash',
    paint: { color: 0xa6e600, metalness: 0.45, roughness: 0.28, clearcoat: 1, coatRough: 0.04, flake: 0.35, flakeColor: 0xeaff9a, pearl: null },
    rim: { accent: 0xa6e600 }, accent: 0x0b0c0e, ink: 0x0b0c0e, numberBg: 0x0b0c0e, numberInk: 0xa6e600 },
  { name: 'Satin Black', short: '缎黑', number: '13', sponsor: 'STELLAR  星河', style: 'orangeswoosh',
    paint: { color: 0x131315, metalness: 0.5, roughness: 0.46, clearcoat: 0.25, coatRough: 0.35, flake: 0.2, flakeColor: 0xffb070, pearl: null },
    rim: { accent: 0xff6a10 }, accent: 0xff6a10, ink: 0xfff0e0, numberBg: 0xff6a10, numberInk: 0x120a04 },
  { name: 'Violet Chrome', short: '紫铬', number: '99', sponsor: 'MIRAI  未来', style: 'prism',
    paint: { color: 0x7a2cff, metalness: 1.0, roughness: 0.055, clearcoat: 1, coatRough: 0.02, flake: 0.12, flakeColor: 0xe6d0ff, pearl: [0.2, 0.9, 1.0, 0.55] },
    rim: { accent: 0xe6d0ff }, accent: 0x18e0ff, ink: 0xf4ecff, numberBg: 0xf4ecff, numberInk: 0x2a0a66 },
];

const hex = (h) => '#' + h.toString(16).padStart(6, '0');
const FONT = '"Arial Black", "Helvetica Neue", Impact, "PingFang SC", "Hiragino Sans GB", "Noto Sans CJK SC", sans-serif';
const FONT_THIN = '"Helvetica Neue", Arial, "PingFang SC", "Hiragino Sans GB", "Noto Sans CJK SC", sans-serif';

/** Run `fn(ctx)` with drawing units = millimetres inside a cell of the atlas that maps to a (sizeU × sizeV) m patch. */
function inCell(ctx, rect, sizeU, sizeV, fn) {
  const [x, y, w, h] = rect;
  ctx.save();
  ctx.beginPath(); ctx.rect(x, y, w, h); ctx.clip();
  ctx.translate(x, y);
  ctx.scale(w / (sizeU * 1000), h / (sizeV * 1000));
  fn(sizeU * 1000, sizeV * 1000);
  ctx.restore();
}

function roundel(ctx, cx, cy, r, bg, ink, text) {
  ctx.fillStyle = hex(bg);
  ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI * 2); ctx.fill();
  ctx.fillStyle = hex(ink);
  ctx.font = `900 ${r * 1.15}px ${FONT}`;
  ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
  ctx.fillText(text, cx, cy + r * 0.06);
}

function sponsorText(ctx, x, y, size, text, col, align = 'left', weight = 800) {
  ctx.fillStyle = hex(col);
  ctx.font = `${weight} ${size}px ${FONT_THIN}`;
  ctx.textAlign = align; ctx.textBaseline = 'middle';
  ctx.fillText(text, x, y);
}

function stripeDoor(ctx, L, W, H) {
  const a = L.accent;
  ctx.save();
  switch (L.style) {
    case 'pinstripe':
      ctx.fillStyle = hex(a); ctx.fillRect(0, H * 0.78, W, 7); ctx.fillRect(0, H * 0.78 + 20, W, 3);
      break;
    case 'cyanbars':
      ctx.fillStyle = hex(a);
      for (let i = 0; i < 3; i++) ctx.fillRect(0, H * 0.70 + i * 40, W * (1 - i * 0.12), 22);
      break;
    case 'magentafade': {
      const g = ctx.createLinearGradient(0, 0, W, 0);
      g.addColorStop(0, hex(a)); g.addColorStop(1, 'rgba(255,47,168,0)');
      ctx.fillStyle = g; ctx.fillRect(0, H * 0.72, W, 70); ctx.fillRect(0, H * 0.72 + 90, W * 0.7, 18);
      break;
    }
    case 'goldline':
      ctx.fillStyle = hex(a); ctx.fillRect(0, H * 0.80, W, 12); ctx.fillRect(0, H * 0.80 + 28, W, 5);
      break;
    case 'hexes':
      ctx.strokeStyle = hex(a); ctx.lineWidth = 6;
      for (let i = 0; i < 9; i++) for (let j = 0; j < 2; j++) {
        const cx = 60 + i * 95 + (j % 2) * 48, cy = H * 0.80 + j * 52, r = 38;
        ctx.globalAlpha = 0.9 - i * 0.08;
        ctx.beginPath();
        for (let k = 0; k < 6; k++) { const an = Math.PI / 6 + k * Math.PI / 3; ctx.lineTo(cx + r * Math.cos(an), cy + r * Math.sin(an)); }
        ctx.closePath(); ctx.stroke();
      }
      break;
    case 'blackslash':
      ctx.fillStyle = hex(a);
      for (let i = 0; i < 6; i++) { ctx.beginPath(); ctx.moveTo(i * 150, H); ctx.lineTo(i * 150 + 70, H); ctx.lineTo(i * 150 + 160, H * 0.62); ctx.lineTo(i * 150 + 90, H * 0.62); ctx.fill(); }
      break;
    case 'orangeswoosh': {
      ctx.fillStyle = hex(a);
      ctx.beginPath(); ctx.moveTo(0, H * 0.92); ctx.bezierCurveTo(W * 0.3, H * 0.62, W * 0.7, H * 0.74, W, H * 0.45); ctx.lineTo(W, H * 0.52);
      ctx.bezierCurveTo(W * 0.7, H * 0.82, W * 0.3, H * 0.70, 0, H * 1.0); ctx.fill();
      break;
    }
    case 'prism': {
      const g = ctx.createLinearGradient(0, 0, W, 0);
      g.addColorStop(0, '#18e0ff'); g.addColorStop(0.5, '#ff5cf0'); g.addColorStop(1, '#ffe85c');
      ctx.fillStyle = g; ctx.fillRect(0, H * 0.82, W, 14); ctx.fillRect(0, H * 0.82 + 30, W * 0.6, 6);
      break;
    }
  }
  ctx.restore();
}

function drawDoor(ctx, L, rect, sizeU, sizeV) {
  inCell(ctx, rect, sizeU, sizeV, (W, H) => {
    stripeDoor(ctx, L, W, H);
    roundel(ctx, W * 0.46, H * 0.40, H * 0.30, L.numberBg ?? L.accent, L.numberInk ?? L.ink, L.number);
    sponsorText(ctx, W * 0.08, H * 0.12, H * 0.115, L.sponsor, L.style === 'blackslash' || L.paint.color === 0xe6e6ee ? L.ink : L.ink, 'left');
    sponsorText(ctx, W * 0.97, H * 0.93, H * 0.075, '霓虹环线 · NEON LOOP', L.ink, 'right', 600);
  });
}

function drawHood(ctx, L, rect, sizeU, sizeV) {
  inCell(ctx, rect, sizeU, sizeV, (W, H) => {
    ctx.save();
    ctx.fillStyle = hex(L.accent);
    switch (L.style) {
      case 'pinstripe':
        ctx.fillRect(W * 0.47, 0, 6, H); ctx.fillRect(W * 0.53, 0, 6, H); break;
      case 'cyanbars':
        for (let i = -2; i <= 2; i++) ctx.fillRect(W * 0.5 + i * 60 - 18, 0, 26, H); break;
      case 'magentafade': {
        const g = ctx.createLinearGradient(0, 0, 0, H); g.addColorStop(0, 'rgba(255,47,168,0.9)'); g.addColorStop(1, 'rgba(255,47,168,0)');
        ctx.fillStyle = g; ctx.fillRect(W * 0.40, 0, W * 0.2, H); break;
      }
      case 'goldline':
        ctx.fillRect(W * 0.46, 0, 12, H); ctx.fillRect(W * 0.54, 0, 12, H); break;
      case 'hexes':
        ctx.strokeStyle = hex(L.accent); ctx.lineWidth = 7;
        for (let i = 0; i < 6; i++) { const cx = W * 0.5 + (i - 2.5) * 100, cy = H * 0.5 + (i % 2) * 40 - 20, r = 42; ctx.beginPath();
          for (let k = 0; k < 6; k++) { const an = Math.PI / 6 + k * Math.PI / 3; ctx.lineTo(cx + r * Math.cos(an), cy + r * Math.sin(an)); } ctx.closePath(); ctx.stroke(); }
        break;
      case 'blackslash':
        for (let i = 0; i < 5; i++) { ctx.beginPath(); ctx.moveTo(W * 0.3 + i * 110, H); ctx.lineTo(W * 0.3 + i * 110 + 50, H); ctx.lineTo(W * 0.3 + i * 110 + 110, 0); ctx.lineTo(W * 0.3 + i * 110 + 60, 0); ctx.fill(); }
        break;
      case 'orangeswoosh':
        ctx.beginPath(); ctx.moveTo(W * 0.1, H); ctx.bezierCurveTo(W * 0.4, H * 0.2, W * 0.6, H * 0.8, W * 0.9, 0); ctx.lineTo(W * 0.94, 0);
        ctx.bezierCurveTo(W * 0.64, H * 0.9, W * 0.4, H * 0.3, W * 0.14, H); ctx.fill();
        break;
      case 'prism': {
        const g = ctx.createLinearGradient(0, 0, W, 0); g.addColorStop(0, '#18e0ff'); g.addColorStop(0.5, '#ff5cf0'); g.addColorStop(1, '#ffe85c');
        ctx.fillStyle = g; ctx.fillRect(W * 0.47, 0, 10, H); ctx.fillRect(W * 0.53, 0, 10, H); break;
      }
    }
    ctx.restore();
    // small number on the hood, upright for a viewer in front of the car
    sponsorText(ctx, W * 0.5, H * 0.52, H * 0.34, L.number, L.ink, 'center', 900);
  });
}

// Rear plate (under the light band, as on the press shots): brushed aluminium with a pressed rim and pressed letters in the
// same metal (lit from above: bright upper edges, soft shadow below).
function drawPlate(ctx, L, rect, sizeU, sizeV) {
  inCell(ctx, rect, sizeU, sizeV, (W, H) => {
    const r = H * 0.09;
    const g = ctx.createLinearGradient(0, 0, 0, H); g.addColorStop(0, '#e2e5e9'); g.addColorStop(0.55, '#c9cdd3'); g.addColorStop(1, '#b4b9c0');
    ctx.fillStyle = g;
    ctx.beginPath(); ctx.roundRect(2, 2, W - 4, H - 4, r); ctx.fill();
    ctx.save(); ctx.clip();
    for (let y = 0; y < H; y += 2) { ctx.fillStyle = `rgba(255,255,255,${0.035 + 0.035 * Math.sin(y * 1.7)})`; ctx.fillRect(0, y, W, 1); }
    ctx.restore();
    const emboss = (draw) => {
      ctx.save(); ctx.translate(H * 0.006, H * 0.03); ctx.globalAlpha = 0.8; draw('#454a52'); ctx.restore();   // shadow
      ctx.save(); ctx.translate(0, -H * 0.016); ctx.globalAlpha = 0.95; draw('#f8f9fb'); ctx.restore();     // lit edge
      draw('#c2c7ce');
    };
    const inset = H * 0.07;
    emboss((c) => { ctx.strokeStyle = c; ctx.lineWidth = H * 0.035; ctx.beginPath(); ctx.roundRect(inset, inset, W - 2 * inset, H - 2 * inset, r * 0.7); ctx.stroke(); });
    ctx.font = `600 ${H * 0.52}px ${FONT_THIN}`;
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    const txt = L.plate ?? `NL·${L.number}`;
    emboss((c) => { ctx.fillStyle = c; ctx.fillText(txt, W * 0.5, H * 0.55, W * 0.8); });
  });
}

const atlasCache = new Map();

/** Canvas texture atlas for livery `i` using the cell layout from car_meta.json (decals). */
export function liveryAtlas(i, meta, maxAniso = 8, scale = 1) {
  const key = i + ':' + scale;
  if (atlasCache.has(key)) return atlasCache.get(key);
  const L = LIVERIES[i % LIVERIES.length];
  const [AW, AH] = meta.atlas;
  const cv = document.createElement('canvas');
  cv.width = AW * scale; cv.height = AH * scale;
  const ctx = cv.getContext('2d');
  ctx.scale(scale, scale);
  ctx.clearRect(0, 0, AW, AH);
  const D = meta.decals;
  const size = (d, a, b) => [Math.abs(d[a][1] - d[a][0]), Math.abs(d[b][1] - d[b][0])];
  for (const k of ['doorL', 'doorR']) {
    const d = D[k]; const [su, sv] = size(d, 'x', 'z');
    drawDoor(ctx, L, d.uv, su, sv);
  }
  { const d = D.hood; const [su, sv] = size(d, 'y', 'x'); drawHood(ctx, L, d.uv, su, sv); }
  if (D.plate) { const d = D.plate; const [su, sv] = size(d, 'y', 'z'); drawPlate(ctx, L, d.uv, su, sv); }
  const tex = new THREE.CanvasTexture(cv);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.flipY = false;                       // uv comes from the glTF (v down), same as the canvas
  tex.anisotropy = maxAniso;
  tex.generateMipmaps = true;
  tex.minFilter = THREE.LinearMipmapLinearFilter;
  tex.needsUpdate = true;
  atlasCache.set(key, tex);
  return tex;
}
