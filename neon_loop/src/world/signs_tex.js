// Procedural sign atlases (canvas): neon shop banners, vertical blade signs, and advertising screen frames.
// Invented brands in Chinese / Japanese / Korean / English. Built once at load.
import * as THREE from 'three';
import { mulberry32 } from './util.js';

const FONT = '"PingFang SC","Hiragino Sans GB","Hiragino Sans","Microsoft YaHei","Noto Sans CJK SC","Apple SD Gothic Neo","Noto Sans KR","Helvetica Neue",Arial,sans-serif';

// hue palettes: [core, glow, accent]
export const PAL = {
  cyan: ['#d8fbff', '#20e8ff', '#0aa0ff'], magenta: ['#ffe0f4', '#ff2bd0', '#ff4a9a'], violet: ['#efe0ff', '#9a4dff', '#6b6bff'],
  amber: ['#fff2d0', '#ffa020', '#ff7a10'], green: ['#e0ffe6', '#30ff7a', '#10d0a0'], red: ['#ffe0d8', '#ff3a20', '#ff1a50'], white: ['#ffffff', '#c8dcff', '#8fb0ff'],
};
export const PAL_KEYS = Object.keys(PAL);

const CN = ['霓虹拉面', '夜光酒吧', '龙华茶餐厅', '万象电器', '星海药房', '深夜食堂', '金鹤旅馆', '极速网咖', '云端酒店', '风暴电竞', '澄海海鲜', '福隆当铺', '新纪元科技', '幻彩KTV', '七号便利店', '灵犀按摩', '赤焰火锅', '蓝鲸水族', '光年书店', '银河洗衣', '豪运麻将', '龙门客栈', '零度冰室', '义体维修', '记忆修复', '数码当铺', '天际银行', '北斗诊所', '凤凰烧腊', '夜航通信'];
const JP = ['ラーメン', '居酒屋 さくら', 'パチンコ', 'カラオケ', '二十四時間', 'ゲームセンター', 'ネオン寿司', '焼肉', 'サイバー薬局', '電脳堂', 'スナック 月', 'たこ焼き'];
const KR = ['치킨', '노래방', '편의점', '포차', '약국', '24시 찜질방', '네온 호프', '사이버 PC방'];
const EN = ['NEXUS', 'HYPERION', 'VOID LOUNGE', 'OMEGA BAR', '24H', 'HOTEL', 'TAXI', 'NOODLE', 'CYBER-MED', 'ARCADE', 'NEON', 'KAIJU BURGER', 'BLUE LOTUS', 'DRAGON BYTE', 'ORBITAL BANK', 'SYNTH CAFE'];
const CN_SUB = ['NEON NOODLE', 'NIGHT GLOW BAR', 'LONGHUA CAFE', 'VANGUARD ELECTRIC', 'STARSEA PHARMACY', 'MIDNIGHT DINER', 'GOLDEN CRANE', 'SPEED NET', 'CLOUD HOTEL', 'STORM ESPORTS', 'SEAFOOD', 'PAWN', 'NEO-ERA TECH', 'KTV', 'MART 7', 'MASSAGE', 'HOTPOT', 'AQUARIUM', 'BOOKS', 'LAUNDRY', 'MAHJONG', 'INN', 'ICE ROOM', 'CYBERNETICS', 'MEMORY REPAIR', 'DIGITAL PAWN', 'SKY BANK', 'NORTH STAR CLINIC', 'ROAST', 'NIGHT COMMS'];

function fit(ctx, text, maxW, maxH, weight = 700) {
  let size = maxH;
  for (; size > 8; size -= 2) { ctx.font = `${weight} ${size}px ${FONT}`; if (ctx.measureText(text).width <= maxW) break; }
  return size;
}

function neonText(ctx, text, x, y, size, pal, weight = 700) {
  ctx.font = `${weight} ${size}px ${FONT}`; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
  ctx.lineJoin = 'round';
  ctx.save();
  ctx.shadowColor = pal[1]; ctx.shadowBlur = size * 0.35; ctx.strokeStyle = pal[1]; ctx.lineWidth = Math.max(2, size * 0.09); ctx.globalAlpha = 0.9;
  ctx.strokeText(text, x, y);
  ctx.shadowBlur = size * 0.12; ctx.fillStyle = pal[0]; ctx.globalAlpha = 1; ctx.fillText(text, x, y);
  ctx.restore();
}

function frameRect(ctx, x, y, w, h, pal, r = 10) {
  ctx.save();
  ctx.fillStyle = '#05060a'; roundRect(ctx, x, y, w, h, r); ctx.fill();
  ctx.shadowColor = pal[1]; ctx.shadowBlur = 10; ctx.strokeStyle = pal[2]; ctx.lineWidth = 3;
  roundRect(ctx, x + 5, y + 5, w - 10, h - 10, r - 2); ctx.stroke();
  ctx.restore();
}
function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath(); ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r); ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath();
}

/**
 * Returns { sign: CanvasTexture, signs: [{ kind:'h'|'v', u0,v0,u1,v1, pal, text }], screen: CanvasTexture, screens: n }.
 * Sign atlas 2048²: top half 4×8 horizontal cells (512×128), bottom half 16×2 vertical cells (128×512).
 */
export function makeSignAtlases() {
  const rnd = mulberry32(8812);
  const W = 2048, cv = document.createElement('canvas'); cv.width = cv.height = W;
  const ctx = cv.getContext('2d');
  ctx.fillStyle = '#000'; ctx.fillRect(0, 0, W, W);
  const signs = [];
  const all = [...CN.map((t, i) => ['cn', t, CN_SUB[i]]), ...JP.map(t => ['jp', t]), ...KR.map(t => ['kr', t]), ...EN.map(t => ['en', t])];
  const pick = () => all[Math.floor(rnd() * all.length)];
  // horizontal cells
  let n = 0;
  for (let r = 0; r < 8; r++) for (let c = 0; c < 4; c++, n++) {
    const x = c * 512, y = r * 128, palK = PAL_KEYS[n % PAL_KEYS.length], pal = PAL[palK];
    const [lang, text, sub] = pick();
    frameRect(ctx, x, y, 512, 128, pal);
    const two = sub && rnd() < .55;
    const size = fit(ctx, text, 440, two ? 64 : 84);
    neonText(ctx, text, x + 256, y + (two ? 50 : 64), size, pal);
    if (two) { const s2 = fit(ctx, sub, 400, 26, 500); neonText(ctx, sub, x + 256, y + 100, s2, [pal[0], pal[2], pal[2]], 500); }
    if (rnd() < .3) { ctx.fillStyle = pal[1]; ctx.globalAlpha = .8; ctx.fillRect(x + 22, y + 22, 8, 8); ctx.fillRect(x + 482, y + 98, 8, 8); ctx.globalAlpha = 1; }
    signs.push({ kind: 'h', u0: x / W, v0: 1 - (y + 128) / W, u1: (x + 512) / W, v1: 1 - y / W, pal: palK, text, lang });
  }
  // vertical cells (bottom half)
  n = 0;
  for (let r = 0; r < 2; r++) for (let c = 0; c < 16; c++, n++) {
    const x = c * 128, y = 1024 + r * 512, palK = PAL_KEYS[(n + 2) % PAL_KEYS.length], pal = PAL[palK];
    let [lang, text] = pick();
    const chars = [...text.replace(/\s+/g, '')].slice(0, 6);
    frameRect(ctx, x, y, 128, 512, pal);
    const size = Math.min(84, Math.floor(440 / chars.length));
    chars.forEach((ch, k) => neonText(ctx, ch, x + 64, y + 40 + (k + .5) * (432 / chars.length), size, pal));
    signs.push({ kind: 'v', u0: x / W, v0: 1 - (y + 512) / W, u1: (x + 128) / W, v1: 1 - y / W, pal: palK, text, lang });
  }
  const sign = new THREE.CanvasTexture(cv);
  sign.colorSpace = THREE.SRGBColorSpace; sign.anisotropy = 8; sign.generateMipmaps = true; sign.minFilter = THREE.LinearMipmapLinearFilter; sign.needsUpdate = true;

  // ---- screens: 8 groups (rows of 256 px) × 4 frames (512×256) ----
  const sv = document.createElement('canvas'); sv.width = 2048; sv.height = 2048;
  const sc = sv.getContext('2d');
  sc.fillStyle = '#000'; sc.fillRect(0, 0, 2048, 2048);
  const BRANDS = [['NEURAL-SYNC', '神经同步'], ['SKYLINE AIR', '天际航空'], ['AURORA', '极光能源'], ['NOVA CORP', '新星集团'], ['KAIJU', '怪兽饮料'], ['ORBITAL', '轨道银行'], ['HYPER-X', '超感游戏'], ['LOTUS', '莲花香氛']];
  const pals = ['cyan', 'magenta', 'violet', 'amber', 'cyan', 'magenta', 'green', 'violet'];
  for (let g = 0; g < 8; g++) {
    const pal = PAL[pals[g]], [en, cn] = BRANDS[g];
    for (let f = 0; f < 4; f++) {
      const x = f * 512, y = g * 256;
      sc.save(); sc.beginPath(); sc.rect(x, y, 512, 256); sc.clip();
      const grad = sc.createLinearGradient(x, y, x + 512, y + 256);
      const base = [['#07131f', '#0b3050'], ['#12081c', '#40104a'], ['#0b1a14', '#0d4a3a'], ['#1a0f08', '#503010']][f % 4];
      grad.addColorStop(0, base[0]); grad.addColorStop(1, base[1]); sc.fillStyle = grad; sc.fillRect(x, y, 512, 256);
      sc.globalAlpha = .9; sc.strokeStyle = pal[1]; sc.lineWidth = 3;
      for (let k = 0; k < 7; k++) { sc.beginPath(); const yy = y + 30 + k * 30 + f * 6; sc.moveTo(x, yy); sc.bezierCurveTo(x + 150, yy - 40 - f * 10, x + 350, yy + 50, x + 512, yy - 20); sc.stroke(); }
      sc.globalAlpha = 1;
      if (f === 0) { neonText(sc, en, x + 256, y + 96, fit(sc, en, 440, 90), pal); neonText(sc, cn, x + 256, y + 190, fit(sc, cn, 420, 62), [pal[0], pal[2], pal[2]], 600); }
      else if (f === 1) { for (let k = 0; k < 6; k++) { sc.fillStyle = pal[k % 3]; sc.globalAlpha = .75; sc.beginPath(); sc.arc(x + 90 + k * 66, y + 128 + Math.sin(k * 1.7) * 55, 22 + k * 5, 0, 6.3); sc.fill(); } sc.globalAlpha = 1; neonText(sc, cn, x + 256, y + 214, fit(sc, cn, 420, 44), pal); }
      else if (f === 2) { neonText(sc, '24H', x + 140, y + 128, 96, pal); neonText(sc, '-50%', x + 360, y + 128, 96, [pal[0], pal[1], pal[2]]); }
      else { sc.fillStyle = pal[1]; sc.globalAlpha = .85; sc.fillRect(x, y, 512, 256); sc.globalAlpha = 1; neonText(sc, en, x + 256, y + 128, fit(sc, en, 460, 110), ['#ffffff', '#ffffff', '#ffffff']); }
      sc.restore();
    }
  }
  const screen = new THREE.CanvasTexture(sv);
  screen.colorSpace = THREE.SRGBColorSpace; screen.anisotropy = 8; screen.generateMipmaps = true; screen.minFilter = THREE.LinearMipmapLinearFilter; screen.needsUpdate = true;
  return { sign, signs, screen, screens: 8 };
}

/** Tiny seamless textures: chain-link fence alpha, graffiti tags atlas. */
export function makeFenceTexture() {
  const c = document.createElement('canvas'); c.width = c.height = 64;
  const x = c.getContext('2d'); x.clearRect(0, 0, 64, 64);
  x.strokeStyle = '#fff'; x.lineWidth = 3;
  x.beginPath(); x.moveTo(0, 0); x.lineTo(64, 64); x.moveTo(64, 0); x.lineTo(0, 64); x.moveTo(-32, 32); x.lineTo(32, 96); x.moveTo(32, -32); x.lineTo(96, 32); x.moveTo(-32, 32); x.lineTo(32, -32); x.moveTo(32, 96); x.lineTo(96, 32); x.stroke();
  const t = new THREE.CanvasTexture(c); t.wrapS = t.wrapT = THREE.RepeatWrapping; t.colorSpace = THREE.NoColorSpace; t.anisotropy = 4;
  return t;
}

/** Highway / tunnel road-sign atlas (2048×1024, 4×4 cells of 512×256) + the start-gantry timing board texture. */
export function makeRoadSignAtlas() {
  const cv = document.createElement('canvas'); cv.width = 2048; cv.height = 1024;
  const x = cv.getContext('2d'); x.fillStyle = '#103020'; x.fillRect(0, 0, 2048, 1024);
  const cells = [];
  const green = (c, r, big, small, arrow) => {
    const X = c * 512, Y = r * 256;
    x.fillStyle = '#0b6a3a'; x.fillRect(X, Y, 512, 256);
    x.strokeStyle = '#ffffff'; x.lineWidth = 6; x.strokeRect(X + 8, Y + 8, 496, 240);
    x.fillStyle = '#fff'; x.textAlign = 'center'; x.textBaseline = 'middle';
    x.font = `700 ${fit(x, big, 360, 84)}px ${FONT}`; x.fillText(big, X + (arrow ? 230 : 256), Y + 90);
    x.font = `600 ${fit(x, small, 440, 44, 600)}px ${FONT}`; x.fillText(small, X + 256, Y + 182);
    if (arrow === 'up') { x.beginPath(); x.moveTo(X + 450, Y + 40); x.lineTo(X + 490, Y + 100); x.lineTo(X + 465, Y + 100); x.lineTo(X + 465, Y + 150); x.lineTo(X + 435, Y + 150); x.lineTo(X + 435, Y + 100); x.lineTo(X + 410, Y + 100); x.closePath(); x.fill(); }
    if (arrow === 'right') { x.beginPath(); x.moveTo(X + 490, Y + 95); x.lineTo(X + 440, Y + 55); x.lineTo(X + 440, Y + 80); x.lineTo(X + 390, Y + 80); x.lineTo(X + 390, Y + 110); x.lineTo(X + 440, Y + 110); x.lineTo(X + 440, Y + 135); x.closePath(); x.fill(); }
    cells.push({ c, r });
  };
  green(0, 0, '市中心', 'CITY CENTRE  5 km', 'up');
  green(1, 0, '隧道', 'TUNNEL  2 km', 'up');
  green(2, 0, '港区', 'DOCKS  出口 14', 'right');
  green(3, 0, '霓虹环线', 'NEON LOOP  ring road', 'up');
  const blue = (c, r, big, small) => {
    const X = c * 512, Y = r * 256; x.fillStyle = '#0a3c8c'; x.fillRect(X, Y, 512, 256); x.strokeStyle = '#fff'; x.lineWidth = 6; x.strokeRect(X + 8, Y + 8, 496, 240);
    x.fillStyle = '#fff'; x.textAlign = 'center'; x.textBaseline = 'middle'; x.font = `700 ${fit(x, big, 440, 90)}px ${FONT}`; x.fillText(big, X + 256, Y + 98); x.font = `600 ${fit(x, small, 440, 44, 600)}px ${FONT}`; x.fillText(small, X + 256, Y + 190); cells.push({ c, r });
  };
  blue(0, 1, '夜市', 'NIGHT MARKET'); blue(1, 1, '市场', 'MARKET  P'); blue(2, 1, '限高 5.5m', 'HEIGHT LIMIT'); blue(3, 1, '出口', 'EXIT  ONLY');
  const speed = (c, r, v) => {
    const X = c * 512, Y = r * 256; x.fillStyle = '#e8e8ea'; x.fillRect(X, Y, 512, 256);
    x.beginPath(); x.arc(X + 256, Y + 128, 112, 0, 6.3); x.fillStyle = '#d01818'; x.fill(); x.beginPath(); x.arc(X + 256, Y + 128, 84, 0, 6.3); x.fillStyle = '#fff'; x.fill();
    x.fillStyle = '#111'; x.font = `800 ${v.length > 2 ? 78 : 96}px ${FONT}`; x.textAlign = 'center'; x.textBaseline = 'middle'; x.fillText(v, X + 256, Y + 134); cells.push({ c, r });
  };
  speed(0, 2, '80'); speed(1, 2, '100'); speed(2, 2, '60'); speed(3, 2, '50');
  // tunnel exit pictogram (green running man) and emergency / telephone signs
  const ex = (c, r, label) => {
    const X = c * 512, Y = r * 256; x.fillStyle = '#0a8a48'; x.fillRect(X, Y, 512, 256); x.strokeStyle = '#fff'; x.lineWidth = 6; x.strokeRect(X + 8, Y + 8, 496, 240);
    x.fillStyle = '#fff'; x.beginPath(); x.arc(X + 150, Y + 70, 22, 0, 6.3); x.fill(); x.lineWidth = 16; x.lineCap = 'round'; x.strokeStyle = '#fff';
    x.beginPath(); x.moveTo(X + 150, Y + 100); x.lineTo(X + 170, Y + 160); x.moveTo(X + 160, Y + 120); x.lineTo(X + 120, Y + 140); x.moveTo(X + 160, Y + 120); x.lineTo(X + 205, Y + 112); x.moveTo(X + 170, Y + 160); x.lineTo(X + 130, Y + 215); x.moveTo(X + 170, Y + 160); x.lineTo(X + 205, Y + 210); x.stroke();
    x.font = `700 ${fit(x, label[0], 220, 70)}px ${FONT}`; x.textAlign = 'center'; x.fillText(label[0], X + 360, Y + 100); x.font = `600 36px ${FONT}`; x.fillText(label[1], X + 360, Y + 175); cells.push({ c, r });
  };
  ex(0, 3, ['出口', 'EXIT 120 m']); ex(1, 3, ['紧急', 'EMERGENCY']); ex(2, 3, ['出口', 'EXIT →']); ex(3, 3, ['电话', 'SOS']);
  const t = new THREE.CanvasTexture(cv); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 8; t.generateMipmaps = true; t.minFilter = THREE.LinearMipmapLinearFilter;
  const uv = (c, r) => ({ u0: c / 4, u1: (c + 1) / 4, v0: 1 - (r + 1) / 4, v1: 1 - r / 4 });
  return { tex: t, uv };
}

export function makeBoardTexture() {
  const cv = document.createElement('canvas'); cv.width = 1536; cv.height = 384;
  const x = cv.getContext('2d'); x.fillStyle = '#04060a'; x.fillRect(0, 0, 1536, 384);
  // chequered flag blocks
  for (let r = 0; r < 6; r++) for (let c = 0; c < 8; c++) { x.fillStyle = (r + c) & 1 ? '#f4f4f4' : '#101010'; x.fillRect(24 + c * 32, 64 + r * 42, 32, 42); x.fillRect(1536 - 24 - 256 + c * 32, 64 + r * 42, 32, 42); }
  const pal = PAL.cyan;
  neonText(x, '霓虹环线', 768, 130, 150, pal); neonText(x, 'NEON LOOP  ·  START / FINISH  起点 终点', 768, 250, 58, PAL.magenta, 600);
  x.fillStyle = '#10ff90'; for (let k = 0; k < 24; k++) x.fillRect(330 + k * 36, 320, 24, 10);
  x.strokeStyle = pal[2]; x.lineWidth = 6; x.strokeRect(6, 6, 1524, 372);
  const t = new THREE.CanvasTexture(cv); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 8; return t;
}

/** Spray-paint tags atlas (2048×512, 4×2 cells of 512×256, alpha). */
export function makeGrafAtlas() {
  const cv = document.createElement('canvas'); cv.width = 2048; cv.height = 512;
  const x = cv.getContext('2d'); x.clearRect(0, 0, 2048, 512);
  const rnd = mulberry32(31337);
  const words = ['NEON', 'KAI', 'ZERO', '夜行', '霓虹', 'LOOP', '404', 'RAIN'];
  const cols = [['#ff2bd0', '#2af', '#fff'], ['#ffe03a', '#f33', '#111'], ['#30ff9a', '#a0f', '#fff'], ['#2ae8ff', '#f4a', '#111']];
  for (let n = 0; n < 8; n++) {
    const cx = (n % 4) * 512, cy = Math.floor(n / 4) * 256, c = cols[Math.floor(rnd() * cols.length)];
    x.save(); x.translate(cx + 256, cy + 128); x.rotate((rnd() - .5) * .25); x.textAlign = 'center'; x.textBaseline = 'middle'; x.lineJoin = 'round';
    const size = words[n].length > 3 ? 120 : 170; x.font = `900 ${size}px Impact, "PingFang SC", "Hiragino Sans GB", sans-serif`;
    x.shadowColor = c[0]; x.shadowBlur = 12; x.lineWidth = 26; x.strokeStyle = c[2] === '#111' ? '#111' : c[1]; x.strokeText(words[n], 0, 0);
    x.shadowBlur = 0; x.lineWidth = 12; x.strokeStyle = c[1]; x.strokeText(words[n], 0, 0);
    x.fillStyle = c[0]; x.fillText(words[n], 0, 0);
    x.restore();
    // drips
    for (let k = 0; k < 9; k++) { const dx = cx + 70 + rnd() * 370, dy = cy + 150 + rnd() * 20, len = 20 + rnd() * 60; x.fillStyle = c[0]; x.fillRect(dx, dy, 4, len); x.beginPath(); x.arc(dx + 2, dy + len, 4, 0, 6.3); x.fill(); }
    // a few scribbles / stars
    x.strokeStyle = c[1]; x.lineWidth = 5; x.beginPath(); x.moveTo(cx + 30, cy + 220); x.bezierCurveTo(cx + 150, cy + 190, cx + 300, cy + 250, cx + 480, cy + 215); x.stroke();
  }
  const t = new THREE.CanvasTexture(cv); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 8; t.generateMipmaps = true; t.minFilter = THREE.LinearMipmapLinearFilter;
  return { tex: t, cells: 8, uv: (n) => ({ u0: (n % 4) / 4, u1: (n % 4 + 1) / 4, v0: 1 - (Math.floor(n / 4) + 1) / 2, v1: 1 - Math.floor(n / 4) / 2 }) };
}
