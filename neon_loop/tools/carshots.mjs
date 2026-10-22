// Car beauty/inspection shots in the real game scene: title screen (cars parked on the grid), UI hidden, camera placed
// in each car's local frame (+X right, +Y up, −Z forward).  Usage: node tools/carshots.mjs [out dir]
import { chromium } from 'playwright-core';
import { CHROME, GPU_ARGS } from './chrome.mjs';
import fs from 'node:fs';
const out = process.argv[2] ?? 'shots/cars';
fs.mkdirSync(out, { recursive: true });
const browser = await chromium.launch({ executablePath: CHROME, headless: true,
  args: [...GPU_ARGS] });
const page = await browser.newPage({ viewport: { width: 1600, height: 900 }, deviceScaleFactor: 1 });
page.on('pageerror', e => console.log('[pageerror]', e.message));
await page.goto('http://localhost:5180/?scene=full&harness=1', { waitUntil: 'domcontentloaded' });
await page.waitForFunction(() => window.__ready === true, null, { timeout: 120000, polling: 200 });
await page.waitForTimeout(1500);
await page.evaluate((lod) => {
  const cv = document.querySelector('canvas');
  for (const e of document.querySelectorAll('body *')) if (e !== cv && !e.contains(cv)) e.style.visibility = 'hidden';
  if (lod >= 0) for (const c of __race.cars) c.visual.forceLod(lod);     // LOD=1|2 env: inspect the far LODs up close
  window.__shoot = (i, off, look = [0, 0.55, 0], fov = 40) => {
    const o = __race.cars[i].visual.object; o.updateMatrixWorld();
    const V = o.position.constructor;
    const p = new V(...off).applyMatrix4(o.matrixWorld), t = new V(...look).applyMatrix4(o.matrixWorld);
    __app.setView({ pos: [p.x, p.y, p.z], target: [t.x, t.y, t.z], fov });
    return { lod: __race.cars[i].visual.lod, livery: __race.cars[i].visual.livery?.name ?? __race.cars[i].name };
  };
}, +(process.env.LOD ?? -1));
const SHOTS = [
  ['p_front34', 0, [3.4, 1.15, -4.4]],
  ['p_side', 0, [-7.5, 0.75, 0.1], [0, 0.5, 0.1], 32],
  ['p_rear34', 0, [-3.6, 1.3, 4.6]],
  ['p_rear', 0, [0.3, 1.0, 5.2], [0, 0.55, 1.8], 40],
  ['p_nose_low', 0, [0.6, 0.45, -5.2], [0, 0.45, 0], 38],
  ['p_wheel', 0, [-2.7, 0.6, -0.9], [-0.9, 0.38, -1.49], 34],
  ['p_chase', 0, [0, 1.75, 5.6], [0, 0.9, -2], 62],
  ['p_rear_high', 0, [0, 3.6, 6.4], [0, 0.45, 1.0], 36],
  ['p_rear_low', 0, [0, 0.6, 5.2], [0, 0.6, 0], 34],
  ['p_diff', 0, [0.95, 0.5, 3.7], [0, 0.42, 2.3], 30],
  ['p_wing_side', 0, [-4.6, 1.35, 2.7], [0, 0.95, 1.7], 30],
  ['p_rear_q', 0, [-2.6, 0.75, 5.6], [0, 0.55, 0.6], 34],
  ['p_wheel_face', 0, [-2.25, 0.42, -1.47], [-0.9, 0.39, -1.487], 30],
  ['ai1_front34', 1, [-3.4, 1.15, -4.4]],
  ['ai3_front34', 3, [3.4, 1.15, -4.4]],
  ['ai5_rear34', 5, [3.6, 1.3, 4.6]],
];
const ONLY = process.env.SHOTS ? new Set(process.env.SHOTS.split(',')) : null;
for (const [name, i, off, look, fov] of SHOTS) {
  if (ONLY && !ONLY.has(name)) continue;
  const info = await page.evaluate(([i, off, look, fov]) => __shoot(i, off, look, fov), [i, off, look, fov]);
  await page.waitForTimeout(700);
  await page.screenshot({ path: `${out}/${name}.png` });
  console.log(name, JSON.stringify(info));
}
await browser.close();
