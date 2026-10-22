// Formatting helpers + all UI strings (Chinese first, English small caps). Edit CONTROLS to change the help panel.

/** 83.456 → "1:23.456" ; null / NaN → "--:--.---" */
export function fmtTime(t) {
  if (t == null || !Number.isFinite(t) || t < 0) return '--:--.---';
  const ms = Math.round(t * 1000);
  const m = Math.floor(ms / 60000), s = Math.floor((ms % 60000) / 1000), r = ms % 1000;
  return `${m}:${String(s).padStart(2, '0')}.${String(r).padStart(3, '0')}`;
}
/** Same, split so the milliseconds can be styled: ["1:23", ".456"] */
export function fmtTimeParts(t) {
  const s = fmtTime(t); const k = s.indexOf('.');
  return [s.slice(0, k), s.slice(k)];
}
/** +1.24 / −0.85 style gap in seconds. */
export function fmtGap(g, sign = true) {
  if (g == null || !Number.isFinite(g)) return '--.--';
  const a = Math.abs(g);
  const body = a >= 100 ? a.toFixed(0) : a >= 10 ? a.toFixed(1) : a.toFixed(2);
  return (sign ? (g < 0 ? '−' : '+') : '') + body;
}
export const clamp = (v, a, b) => (v < a ? a : v > b ? b : v);
export const lerp = (a, b, t) => a + (b - a) * t;
export const smooth = (a, b, v) => { const t = clamp((v - a) / (b - a), 0, 1); return t * t * (3 - 2 * t); };
export const num = (v, d = 0) => (Number.isFinite(v) ? v : d);

/** Per-livery accent colours for the mini-map / results (index = car.livery; 0 = player, liquid silver). */
export const LIVERY_COLORS = [
  '#dfe9f2', // 0 player — liquid silver
  '#1ee6ff', // 1 graphite + cyan
  '#ff4fd8', // 2 pearl white + magenta
  '#ff3550', // 3 candy red
  '#4d7bff', // 4 midnight blue
  '#c8ff2e', // 5 acid yellow-green
  '#ff8a1f', // 6 satin black + orange
  '#a66bff', // 7 violet chrome
];

export const LAP_OPTIONS = [1, 3, 5];
export const DIFFICULTIES = [
  { id: 'easy', zh: '轻松', en: 'EASY' },
  { id: 'normal', zh: '标准', en: 'NORMAL' },
  { id: 'hard', zh: '残酷', en: 'HARD' },
];
export const CAMERAS = [   // race camera choices on the title screen
  { id: 'chase', zh: '追尾', en: 'CHASE' },
  { id: 'hood', zh: '引擎盖', en: 'HOOD' },
  { id: 'bumper', zh: '保险杠', en: 'BUMPER' },
];
export const CAMERA_LABELS = [...CAMERAS, { id: 'orbit', zh: '环绕', en: 'ORBIT' }];

/** Controls help (keyboard first, then gamepad). Adjust here if the input bindings change. */
export const CONTROLS = {
  keyboard: [
    { keys: ['W', '↑'], zh: '加速', en: 'THROTTLE' },
    { keys: ['S', '↓'], zh: '刹车 / 倒车', en: 'BRAKE / REVERSE' },
    { keys: ['A', 'D', '←', '→'], zh: '转向', en: 'STEER' },
    { keys: ['SPACE'], zh: '手刹', en: 'HANDBRAKE' },
    { keys: ['SHIFT'], zh: '冷气推进', en: 'THRUSTERS' },
    { keys: ['C'], zh: '切换视角', en: 'CAMERA' },
    { keys: ['R'], zh: '复位到赛道', en: 'RESET CAR' },
    { keys: ['ESC', 'P'], zh: '暂停', en: 'PAUSE' },
    { keys: ['M'], zh: '静音', en: 'MUTE' },
  ],
  gamepad: [
    { keys: ['RT'], zh: '加速', en: 'THROTTLE' },
    { keys: ['LT'], zh: '刹车 / 倒车', en: 'BRAKE / REVERSE' },
    { keys: ['L↔'], zh: '转向', en: 'STEER' },
    { keys: ['A'], zh: '手刹', en: 'HANDBRAKE' },
    { keys: ['RB'], zh: '冷气推进', en: 'THRUSTERS' },
    { keys: ['Y'], zh: '切换视角', en: 'CAMERA' },
    { keys: ['START'], zh: '暂停', en: 'PAUSE' },
  ],
};
