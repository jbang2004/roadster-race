// Headlight tuning: same view of car 1 on the grid with the world-pass headlight spots varied.
import { chromium } from 'playwright-core';
import { CHROME, GPU_ARGS } from './chrome.mjs';
const out = process.argv[2];
const browser = await chromium.launch({ executablePath: CHROME, headless: true, args: [...GPU_ARGS] });
const page = await browser.newPage({ viewport: { width: 1600, height: 900 }, deviceScaleFactor: 1 });
await page.goto('http://localhost:5180/?scene=full&harness=1', { waitUntil: 'domcontentloaded' });
await page.waitForFunction(() => window.__ready === true, null, { timeout: 120000, polling: 200 });
await page.waitForTimeout(1500);
await page.evaluate(() => {
  const cv = document.querySelector('canvas');
  for (const e of document.querySelectorAll('body *')) if (e !== cv && !e.contains(cv)) e.style.visibility = 'hidden';
  const o = __race.cars[1].visual.object; o.updateMatrixWorld(); const V = o.position.constructor;
  const p = new V(-3.4, 1.15, -4.4).applyMatrix4(o.matrixWorld), t = new V(0, 0.55, 0).applyMatrix4(o.matrixWorld);
  __app.setView({ pos: [p.x, p.y, p.z], target: [t.x, t.y, t.z], fov: 40 });
  const spots = []; __app.scene.getObjectByName('CarLightPool').traverse(l => { if (l.isSpotLight && !l.layers.test({ mask: 1 << 3 })) spots.push(l); });
  window.__hv = null;
  __app.add({ late: () => { if (!__hv) return; for (const l of spots) { l.intensity *= __hv.k; l.angle = __hv.angle; l.penumbra = __hv.pen; if (__hv.up != null) { l.target.position.y = l.position.y + __hv.up; } } } });
});
const V = [['a_now', null], ['b_off', { k: 0, angle: 0.35, pen: 0.37 }], ['c_150_narrow', { k: 150 / 240, angle: 0.30, pen: 0.7, up: 0 }], ['d_100_narrow', { k: 100 / 240, angle: 0.30, pen: 0.7, up: 0 }]];
for (const [name, hv] of V) {
  await page.evaluate((hv) => { window.__hv = hv; }, hv);
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${out}/${name}.png` });
}
await browser.close();
