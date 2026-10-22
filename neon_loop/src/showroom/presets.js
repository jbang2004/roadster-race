// Showroom data: studio presets, factory paints, camera presets, hotspots, labels. All numbers are scene units (metres,
// linear HDR radiance). The studio lights are RECTANGULAR EMITTERS: the same rectangles are (a) drawn into the studio cube map
// that becomes the car's image-based light (so the clear coat reflects clean soft boxes), (b) integrated analytically for the
// diffuse light on the cyclorama and the floor, (c) sampled by the shadow bake for the soft area-light shadows on the floor.
//
// Light rect: pos = centre, size = [width, height], aim = point it faces, spin = roll around its normal (deg), L = radiance rgb.
// Car frame: -Z forward (nose), +X right, +Y up. Default camera sits front-left, so "left" lights are at -X.

export const PRESETS = {
  dark: {
    id: 'dark', zh: '深色影棚', en: 'Dark studio',
    floor: { albedo: [0.085, 0.088, 0.096], rough: 0.45, spec: 0.22, reflGain: 0.12, refl: 1.0 },
    wall: { albedo: [0.07, 0.07, 0.076], glow: [0.02, 0.0215, 0.025], glowH: 5.5, k: 0.05 },
    ambient: [0.016, 0.0165, 0.019],
    ceiling: [0.01, 0.01, 0.012],
    // Press-photo lighting (refs p016/p018): one big overhead softbox (slightly toward the nose) lights hood and roof; two high, long, narrow strips lay
    // a thin clean highlight along each shoulder; almost no side fill so the flanks fall off to dark; a floor-only gobo spot in front of the nose makes the
    // pool (it is a flag-shaped light: kS = 0, env = false, so it is not in the car's reflections).
    lights: [
      { name: 'top', glass: false, pos: [0.3, 6.0, -0.9], size: [3.8, 7.5], aim: [0, 0, -0.5], spin: 0, L: [13, 13.1, 13.6], n: 140, beam: 4, kF: 0.04, kW: 0.22, kS: 0.12 },
      // Highlight alignment: for the shoulder shelf (normal ~(-0.5, 0.85, 0)) and the roof rail the mirror ray of every default left-side camera meets the plane y = 5 m at
      // x ~ +1.4 (z follows the camera azimuth: 0 for the side views, +4..+9 for the front 3/4 views). One long narrow strip along z there gives the long clean
      // line on the shoulder for all of them; its mirror twin at x = -1.4 does the same for the right-hand views.
      { name: 'lineL', glass: false, pos: [1.4, 5.3, 1.8], size: [14, 0.35], aim: [-0.3, 0.6, 1.8], spin: 0, L: [26, 26.2, 27.2], n: 56, beam: 3, kF: 0, kW: 0, kS: 0.03 },
      { name: 'lineR', glass: false, pos: [-1.4, 5.3, 1.8], size: [14, 0.35], aim: [0.3, 0.6, 1.8], spin: 0, L: [20, 20.2, 21], n: 56, beam: 3, kF: 0, kW: 0, kS: 0.03 },
      // only the glass sees this one: a very soft, dim overhead box with a gradient (a faint sky on the roof and screen, no hard edge)
      { name: 'glassTop', glassOnly: true, pos: [0, 6.5, 0.5], size: [14, 12], aim: [0, 0, 0.51], spin: 0, L: [1.3, 1.31, 1.36], grad: 0.8, soft: 1.0, n: 8, beam: 0, kF: 0, kW: 0 },
      // two strips lying on the floor beside the car, seen only by the tyres (tyreOnly: not in the body's or the glass's reflections): a thin lit edge on the sidewalls, so the tyre
      // separates from its contact shadow without lighting the doors
      { name: 'tyreL', tyreOnly: true, pos: [-3.2, 0.06, 0.0], size: [9, 0.1], aim: [0, 0.06, 0.0], spin: 0, L: [30, 30.4, 31.5], n: 24, beam: 3, kF: 0, kW: 0 },
      { name: 'tyreR', tyreOnly: true, pos: [3.2, 0.06, 0.0], size: [9, 0.1], aim: [0, 0.06, 0.0], spin: 0, L: [18, 18.2, 18.9], n: 24, beam: 3, kF: 0, kW: 0 },
      // a small soft box low at the side: only a camera looking straight at the flank sees it mirrored there (the soft grey gradient on the doors of the side view); the 3/4 views miss it
      { name: 'sideFill', glass: false, pos: [-4.5, 0.55, 0.3], size: [3.2, 0.5], aim: [0, 0.55, 0.3], spin: 0, L: [0.7, 0.71, 0.74], n: 24, beam: 2, kF: 0, kW: 0, kS: 0.05, kD: 0.1 },
      { name: 'doorFill', glass: false, pos: [-3.3, 1.05, 3.2], size: [3.4, 0.7], aim: [-0.9, 0.6, -0.5], spin: 0, L: [0.95, 0.96, 1.0], n: 24, beam: 2, kF: 0, kW: 0, kS: 0, kD: 0.1 },
      { name: 'doorFillF', glass: false, pos: [-3.3, 1.05, -3.2], size: [3.4, 0.7], aim: [-0.9, 0.6, 0.5], spin: 0, L: [0.95, 0.96, 1.0], n: 24, beam: 2, kF: 0, kW: 0, kS: 0, kD: 0.1 },
      // the floor: one soft pool of light centred on the front half of the car (on the key side), falling away smoothly forward, sideways and to the tail, so the foreground and the
      // far curve of the wall sit in the dark. Floor-only (flag lights: not in the car's reflections). No straight edges anywhere.
      { name: 'pool', env: false, pos: [0.3, 6.5, -1.4], size: [8, 8], aim: [0.3, 0, -1.39], spin: 0, L: [26.0, 26.3, 27.2], n: 200, beam: 0, kF: 1, kW: 0, kS: 0, gobo: { c: [0.2, -0.38], r: [2.5, 2.7], rot: 0, soft: 2.0 } },
      // a weaker, wider pool behind the car (the press photos show a second one to the right of the tail)
      { name: 'spot2', env: false, pos: [-3.0, 5.5, 8.0], size: [3.0, 3.0], aim: [-0.5, 0, 3.6], spin: 0, L: [60, 61, 63], n: 160, beam: 0, kF: 1, kW: 0, kS: 0, gobo: { c: [0.9, 3.4], r: [3.0, 2.2], rot: -20, soft: 0.9 } },
    ],
    carSH: 0.35, diffUp: 0.92, envFloorK: 0.25,
    exposure: 0.85, bloom: { strength: 0.45, threshold: 9 }, vignette: 0.36, tonemap: 'agx',
    camLight: [0.03, 0.03, 0.034],
  },
  light: {
    id: 'light', zh: '浅色影棚', en: 'Light studio',
    // high-key white cyclorama: bright seamless floor and wall, soft overhead and side boxes, soft shadows; the car stays a touch darker than the cyc and keeps its gradient
    floor: { albedo: [0.90, 0.905, 0.915], rough: 0.42, spec: 0.35, reflGain: 0.45, refl: 1.0, tyreAO: 0.55 },
    wall: { albedo: [0.80, 0.80, 0.81], glow: [1.0, 1.0, 1.02], glowH: 8.0, k: 1.0 },
    ambient: [0.66, 0.665, 0.68],
    ceiling: [0.4, 0.4, 0.42],
    lights: [
      { name: 'top', glass: false, pos: [0.2, 6.5, -0.4], size: [9.0, 6.0], aim: [0, 0, -0.2], spin: 0, L: [5.2, 5.2, 5.3], n: 200, beam: 1, kF: 0.85, kW: 0.7, kS: 0.2 },
      { name: 'lineL', glass: false, pos: [1.4, 5.3, 1.8], size: [14, 0.6], aim: [-0.3, 0.6, 1.8], spin: 0, L: [9, 9.1, 9.4], n: 48, beam: 3, kF: 0, kW: 0, kS: 0.05 },
      { name: 'lineR', glass: false, pos: [-1.4, 5.3, 1.8], size: [14, 0.6], aim: [0.3, 0.6, 1.8], spin: 0, L: [7, 7.1, 7.3], n: 48, beam: 3, kF: 0, kW: 0, kS: 0.05 },
      { name: 'glassTop', glassOnly: true, pos: [0, 6.5, 0.5], size: [14, 12], aim: [0, 0, 0.51], spin: 0, L: [1.6, 1.62, 1.65], grad: 0.5, soft: 1.0, n: 8, beam: 0, kF: 0, kW: 0 },
      { name: 'keyL', glass: false, pos: [-6.0, 3.0, -2.6], size: [3.2, 2.6], aim: [0, 0.4, -0.2], spin: 0, L: [2.4, 2.4, 2.45], n: 160, beam: 1.5, kF: 0.7, kW: 0.6 },
      { name: 'keyR', glass: false, pos: [5.6, 3.2, 3.2], size: [3.2, 2.6], aim: [0, 0.4, 0], spin: 0, L: [3.4, 3.4, 3.45], n: 160, beam: 1.5, kF: 0.8, kW: 0.6 },
    ],
    exposure: 1.0, bloom: { strength: 0.5, threshold: 9 }, vignette: 0.08, tonemap: 'agx',
    camLight: [0.06, 0.06, 0.06],
  },
  city: {
    id: 'city', zh: '城市夜景', en: 'City night',
    hdri: 'shanghai_bund',
    floor: { albedo: [0.030, 0.032, 0.040], rough: 0.13, spec: 1.0, refl: 1.0, wet: true },
    wall: { albedo: [0, 0, 0], glow: [0, 0, 0], glowH: 5.0, k: 0 },
    ambient: [0.0, 0.0, 0.0],
    ceiling: [0, 0, 0],
    lights: [
      { name: 'rimL', pos: [-4.6, 2.4, 6.0], size: [0.7, 3.4], aim: [0, 0.6, 0.6], spin: 0, L: [5.0, 7.5, 12.0], n: 48 },
      { name: 'rimR', pos: [4.8, 2.4, 5.6], size: [0.7, 3.4], aim: [0, 0.6, 0.6], spin: 0, L: [12.0, 5.5, 8.0], n: 48 },
      { name: 'keyF', pos: [-5.4, 3.6, -5.0], size: [3.4, 2.0], aim: [0, 0.4, -0.4], spin: 0, L: [3.2, 3.6, 4.4], n: 96 },
    ],
    exposure: 0.7, bloom: { strength: 0.35, threshold: 14 }, vignette: 0.28, tonemap: 'agx',
    camLight: [0.04, 0.045, 0.06],
    hdriIntensity: 0.22, hdriGain: [0.95, 1.0, 1.15], hdriClamp: 60, skyRot: 0.3, fogDist: 42, hazeEl: 0.006, hazeLod: 2.4, hazeK: 0.48, envSkyK: 3.0, skyFold: [0.696, 0.718],
  },
};
export const PRESET_ORDER = ['dark', 'light', 'city'];

// Factory paints: only existing material parameters change (colour, metalness, base roughness, flake, pearl); the clear coat stays
// a real clear coat (clearcoat 1, coatRough ~0.03) so the reflections stay physically right.
export const PAINTS = [
  { id: 'pearl', zh: '珍珠白', en: 'Pearl White', swatch: '#ecebea', color: 0xdedee4, metalness: 0.32, roughness: 0.22, coatRough: 0.03, flake: 0.02, flakeColor: 0xfff4ff, pearl: [0.95, 0.88, 0.80, 0.55], accent: 0xb8bcc4 },
  { id: 'silver', zh: '冰川银', en: 'Glacier Silver', swatch: '#b9bdc4', color: 0xbcc0c7, metalness: 0.78, roughness: 0.28, coatRough: 0.03, flake: 0.04, flakeColor: 0xffffff, pearl: null, accent: 0xc9ccd2 },
  { id: 'black', zh: '曜石黑', en: 'Obsidian Black', swatch: '#101113', color: 0x0b0c0f, metalness: 0.55, roughness: 0.22, coatRough: 0.025, flake: 0.025, flakeColor: 0xaab4c8, pearl: null, accent: 0x9aa0aa },
  { id: 'red', zh: '烈焰红', en: 'Flame Red', swatch: '#b3101f', color: 0xa40a1a, metalness: 0.82, roughness: 0.20, coatRough: 0.025, flake: 0.03, flakeColor: 0xff6a4a, pearl: null, accent: 0xd8d8dc },
  { id: 'blue', zh: '深海蓝', en: 'Deep Sea Blue', swatch: '#102a78', color: 0x0c2470, metalness: 0.85, roughness: 0.24, coatRough: 0.03, flake: 0.04, flakeColor: 0x9cc4ff, pearl: null, accent: 0xd8d8dc },
  { id: 'grey', zh: '纳多灰', en: 'Nardo Grey', swatch: '#73767b', color: 0x70747a, metalness: 0.12, roughness: 0.34, coatRough: 0.04, flake: 0.01, flakeColor: 0xffffff, pearl: null, accent: 0xb0b4ba },
];

// Camera presets. pos/target are in the car frame (the car stands at the origin, facing -Z); fov = vertical degrees.
export const VIEWS = [
  { id: 'front34', zh: '前 3/4', en: 'Front ¾', pos: [-5.9, 1.45, -6.1], target: [0, 0.55, -0.2], fov: 30 },
  { id: 'side', zh: '正侧', en: 'Side', pos: [-10.2, 0.85, 0.0], target: [0, 0.62, 0.0], fov: 24 },
  { id: 'rear34', zh: '后 3/4', en: 'Rear ¾', pos: [5.6, 1.5, 6.4], target: [0, 0.6, 0.3], fov: 30 },
  { id: 'rear', zh: '正后', en: 'Rear', pos: [0, 1.05, 9.4], target: [0, 0.68, 0.4], fov: 26 },
  { id: 'top', zh: '俯视', en: 'Top', pos: [0.01, 12.2, 0.4], target: [0, 0.4, 0.0], fov: 30 },
  { id: 'wheel', zh: '轮毂特写', en: 'Wheel', pos: [-2.55, 0.55, -3.25], target: [-0.9, 0.4, -1.49], fov: 30 },
  { id: 'lamp', zh: '灯带特写', en: 'Light bar', pos: [-1.5, 0.7, -4.4], target: [0, 0.52, -2.3], fov: 32 },
  { id: 'cockpit', zh: '座舱', en: 'Cabin', pos: [-1.55, 1.7, -0.3], target: [-0.25, 0.8, -0.55], fov: 42 },
];

// Camera solved from the press photos (tools/blender/render_ref_views.py, Blender frame -> car frame: x = by, y = bz, z = bx); 36 mm sensor, 3:2.
// Only for side-by-side checks against refs/press2 (window.__sr.refView).
const vfov = (lens, ar = 1.5) => 2 * Math.atan(Math.tan(Math.atan(18 / lens)) / ar) * 180 / Math.PI;
export const REF_VIEWS = {
  p016: { pos: [-4.773, 1.059, -8.130], target: [-0.488, 0.706, -1.383], fov: vfov(65.26) },
  p018: { pos: [-10.0, 0.61, 0.0], target: [0.0, 0.61, 0.0], fov: vfov(51.2) },
  p017: { pos: [-6.044, 0.973, 6.665], target: [-0.452, 0.609, 0.956], fov: vfov(55.59) },
};

export const FEATURES = [
  { id: 'wing', zh: '主动尾翼', en: 'Active wing' },
  { id: 'drl', zh: '日行灯带', en: 'Daytime strip' },
  { id: 'tail', zh: '尾灯带', en: 'Tail strip' },
  { id: 'brake', zh: '刹车灯', en: 'Brake light' },
  { id: 'steer', zh: '前轮转向', en: 'Steering' },
  { id: 'spin', zh: '车轮慢转', en: 'Wheels turning' },
  { id: 'jets', zh: '冷气推进器', en: 'Cold-gas thrusters' },
  { id: 'livery', zh: '比赛涂装', en: 'Race livery' },
];

// Hotspots (car frame). Text describes features only: no performance figures that were not published.
export const HOTSPOTS = [
  { id: 'wheel', pos: [-0.9, 0.5, -1.49], nrm: [-1, 0, 0], view: 'wheel', zh: '轮毂与刹车', en: 'Wheels & brakes',
    tz: '六辐轮毂配宽大的辐间开口，制动盘与卡钳透过辐条清晰可见。', te: 'Six-spoke wheels with wide openings: the brake discs and calipers show through between the spokes.' },
  { id: 'lamp', pos: [0, 0.58, -2.36], nrm: [0, 0, -1], view: 'lamp', zh: '贯穿式灯带', en: 'Full-width light bar',
    tz: '一条贯穿车头的细长灯带取代了传统大灯，日行灯与车头线条融为一体。', te: 'A single slim light bar runs across the nose in place of conventional headlamps, drawn into the line of the front end.' },
  { id: 'jets', pos: [0, 0.62, 2.42], nrm: [0, 0, 1], view: 'rear', zh: '冷气推进器', en: 'Cold-gas thrusters',
    tz: '尾部扩散器内嵌一排喷口。演示时可看到压缩气体喷出的气流。', te: 'A row of nozzles sits inside the rear diffuser. In the demo you can watch the compressed-gas plumes.' },
  { id: 'wing', pos: [0, 1.12, 2.15], nrm: [0, 1, 0.2], view: 'rear34', zh: '主动尾翼', en: 'Active wing',
    tz: '尾翼平时收起，与车尾盖板齐平；需要时展开。可在“功能”里演示。', te: 'The wing sits flush with the rear deck when stowed and rises when needed. Try it under Features.' },
  { id: 'roof', pos: [0, 1.30, -0.35], nrm: [0, 1, 0], view: 'top', zh: '玻璃车顶', en: 'Glass roof',
    tz: '整块玻璃车顶让座舱通透明亮。', te: 'A glass roof opens up the cabin.' },
];

export const T = {
  back: ['返回', 'BACK'], title: ['展厅', 'SHOWROOM'],
  views: ['机位', 'VIEW'], studio: ['环境', 'STUDIO'], paint: ['颜色', 'COLOUR'], features: ['功能', 'FEATURES'], photo: ['拍照', 'PHOTO'],
  photoHint: ['点击画面对焦', 'TAP TO FOCUS'], aperture: ['光圈', 'APERTURE'], exit: ['退出', 'EXIT'],
  hint: ['拖动旋转 · 滚轮缩放 · 右键平移', 'DRAG TO ORBIT · SCROLL TO ZOOM · RIGHT-DRAG TO PAN'],
  hintTouch: ['单指旋转 · 双指缩放与平移', 'ONE FINGER ORBIT · TWO FINGERS ZOOM & PAN'],
  loading: ['正在布置影棚', 'SETTING UP THE STUDIO'],
  hotspots: ['热点', 'HOTSPOTS'], rotate: ['自动转台', 'TURNTABLE'], on: ['开', 'ON'], off: ['关', 'OFF'],
};
