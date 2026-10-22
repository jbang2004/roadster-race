// Procedural advertising atlas (canvas 2D → texture): bilingual neon brand panels used by the giant billboards,
// blimps and holograms. All brands are invented. 4 columns × 4 rows of 512×256 panels = 2048×1024.
import * as THREE from 'three';

const FONT_CJK = '"PingFang SC","Hiragino Sans GB","Heiti SC","Microsoft YaHei","Noto Sans CJK SC","WenQuanYi Micro Hei",sans-serif';
const PANELS = [
  // [bg1, bg2, main text, sub text, accent]
  ['#12002b', '#4a0a6e', '霓虹银行', 'NEON BANK  ·  未来金融', '#ff3ec9'],
  ['#001b2e', '#00506b', '龍宮拉麺', 'RYUGU RAMEN  24H', '#35f3ff'],
  ['#1c0600', '#6b1d00', '天穹航空', 'SKYVAULT AIRWAYS', '#ffb347'],
  ['#0a0030', '#1f1f8f', '新世界', 'NEW WORLD  ·  新世界 ホールディングス', '#8f7bff'],
  ['#14001a', '#62003f', '玫瑰 ROSE', 'ROSE.LABS  合成美学', '#ff5fa8'],
  ['#001a14', '#006b4f', '碧波 AQUA', 'AQUA  ·  CLEAN WATER 清水', '#3dffb5'],
  ['#1a1000', '#5c4300', '金龙 GOLDEN', 'KIN-RYU  金龍  CASINO', '#ffd23d'],
  ['#05001f', '#2b006b', '量子 QUANTUM', 'QUANTUM TRAVEL  量子旅行', '#c46bff'],
  ['#00121f', '#00406b', '电光 DENKO', 'DENKO  電光  ELECTRONICS', '#4db8ff'],
  ['#1f0010', '#6b0033', '赤月 AKATSUKI', '赤月  ·  SAKE & BAR', '#ff4d6d'],
  ['#001f10', '#00693a', '韩流 K-WAVE', '한류  K-WAVE  ENTERTAINMENT', '#7dff4d'],
  ['#0f0025', '#40006b', '夜城 NIGHT CITY', '夜城  ·  24H  ·  眠らない街', '#ff7bf0'],
  ['#1f0f00', '#6b3a00', '福 FORTUNE', '福运  ·  FORTUNE  SUPERMARKET', '#ffa64d'],
  ['#001222', '#005a73', '海洋 OCEANIC', 'OCEANIC  海洋  FREIGHT', '#4dffee'],
  ['#1a0020', '#5e0070', '梦 DREAMS', '夢  ·  DREAMS  VR  体験', '#ee5dff'],
  ['#1f1f1f', '#0a0a0a', 'ARASAKA-X', '警告  ·  WARNING  ·  ZONE', '#ff2d2d'],
];

export const ATLAS = { cols: 4, rows: 4, count: 16 };

export function makeAdAtlas() {
  const W = 2048, H = 1024, pw = W / ATLAS.cols, ph = H / ATLAS.rows;
  const cv = document.createElement('canvas'); cv.width = W; cv.height = H;
  const g = cv.getContext('2d');
  PANELS.forEach(([c1, c2, main, sub, acc], i) => {
    const x = (i % ATLAS.cols) * pw, y = Math.floor(i / ATLAS.cols) * ph;
    g.save(); g.beginPath(); g.rect(x, y, pw, ph); g.clip();
    const gr = g.createLinearGradient(x, y, x + pw, y + ph); gr.addColorStop(0, c1); gr.addColorStop(1, c2);
    g.fillStyle = gr; g.fillRect(x, y, pw, ph);
    // decorative geometry
    g.globalAlpha = 0.28; g.strokeStyle = acc; g.lineWidth = 3;
    for (let k = 0; k < 7; k++) { g.beginPath(); g.moveTo(x + pw * (0.1 + k * 0.14), y + ph); g.lineTo(x + pw * (0.3 + k * 0.14), y); g.stroke(); }
    g.globalAlpha = 1;
    g.strokeStyle = acc; g.lineWidth = 8; g.strokeRect(x + 10, y + 10, pw - 20, ph - 20);
    // main text with neon glow
    g.textAlign = 'center'; g.textBaseline = 'middle';
    let fs = 118; g.font = `900 ${fs}px ${FONT_CJK}`;
    while (g.measureText(main).width > pw - 70 && fs > 40) { fs -= 4; g.font = `900 ${fs}px ${FONT_CJK}`; }
    g.shadowColor = acc; g.shadowBlur = 34; g.fillStyle = '#ffffff';
    g.fillText(main, x + pw / 2, y + ph * 0.42);
    g.shadowBlur = 14; g.fillText(main, x + pw / 2, y + ph * 0.42);
    g.shadowBlur = 0; g.fillStyle = acc;
    let fs2 = 34; g.font = `700 ${fs2}px ${FONT_CJK}`;
    while (g.measureText(sub).width > pw - 60 && fs2 > 16) { fs2 -= 2; g.font = `700 ${fs2}px ${FONT_CJK}`; }
    g.fillText(sub, x + pw / 2, y + ph * 0.80);
    g.fillRect(x + pw * 0.18, y + ph * 0.66, pw * 0.64, 5);
    g.restore();
  });
  const tex = new THREE.CanvasTexture(cv);
  tex.colorSpace = THREE.SRGBColorSpace; tex.anisotropy = 8; tex.generateMipmaps = true; tex.minFilter = THREE.LinearMipmapLinearFilter;
  tex.wrapS = tex.wrapT = THREE.ClampToEdgeWrapping;
  return tex;
}

/** GLSL: sample panel `idx` of the atlas at uv (0..1), slightly inset to avoid bleeding. */
export const ATLAS_GLSL = /* glsl */`
vec3 adPanel(sampler2D atlas, float idx, vec2 uv) {
  float c = mod(idx, 4.0), r = floor(idx / 4.0);
  vec2 q = clamp(uv, 0.004, 0.996);
  return texture2D(atlas, (vec2(c, 3.0 - r) + q) * 0.25).rgb;
}`;
