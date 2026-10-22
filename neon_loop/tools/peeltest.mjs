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
  const c = __race.cars[3], o = c.visual.object; o.updateMatrixWorld(); const V = o.position.constructor;
  const p = new V(3.4, 1.15, -4.4).applyMatrix4(o.matrixWorld), t = new V(0, 0.55, 0).applyMatrix4(o.matrixWorld);
  __app.setView({ pos: [p.x, p.y, p.z], target: [t.x, t.y, t.z], fov: 40 });
  const orig = c.visual.sync.bind(c.visual);
  window.__mode = { peel: true, bead: true, flake: true };
  const U = c.visual.uniforms; const peel0 = U.paint.uPeel.value, flake0 = U.paint.uFlake.value;
  c.visual.sync = (...a) => { const r = orig(...a); if (!__mode.bead) U.car.uBead.value = 0; U.paint.uPeel.value = __mode.peel ? peel0 : 0; U.paint.uFlake.value = __mode.flake ? flake0 : 0; return r; };
  window.__info = { peel0, flake0, bead: U.car.uBead.value };
});
console.log(JSON.stringify(await page.evaluate(() => __info)));
for (const [name, m] of [['a_default', {}], ['b_nopeel', { peel: false }], ['c_nobead', { bead: false }], ['d_none', { peel: false, bead: false, flake: false }]]) {
  await page.evaluate((m) => Object.assign(__mode, { peel: true, bead: true, flake: true }, m), m);
  await page.waitForTimeout(600);
  await page.screenshot({ path: `${out}/${name}.png`, clip: { x: 380, y: 260, width: 1100, height: 450 } });
}
await browser.close();
