// Drive the player car (autopilot steers), fire the cold-gas thrusters and capture the chase view: plumes, vapour, HUD gas
// gauge, FOV kick, tank drain. Usage: node tools/boosttest.mjs [out dir] [--s 150] [--cam chase] [--v 38]
import { chromium } from 'playwright-core';
import { CHROME, GPU_ARGS } from './chrome.mjs';
import fs from 'node:fs';
const argv = process.argv.slice(2);
const opt = (k, d) => { const i = argv.indexOf('--' + k); return i >= 0 ? argv[i + 1] : d; };
const out = argv[0] && !argv[0].startsWith('--') ? argv[0] : 'shots/boost';
const S0 = +opt('s', 150), cam = opt('cam', 'chase'), V0 = +opt('v', 38);
fs.mkdirSync(out, { recursive: true });
const browser = await chromium.launch({ executablePath: CHROME, headless: true,
  args: [...GPU_ARGS] });
const page = await browser.newPage({ viewport: { width: 1600, height: 900 }, deviceScaleFactor: 1 });
const logs = [];
page.on('pageerror', e => logs.push('[pageerror] ' + e.message));
page.on('console', m => { if (m.type() === 'error') logs.push('[console.error] ' + m.text().slice(0, 200)); });
await page.goto('http://localhost:5180/?scene=full&harness=1&autostart', { waitUntil: 'domcontentloaded' });
await page.waitForFunction(() => window.__ready === true, null, { timeout: 120000, polling: 200 });
await page.waitForFunction(() => window.__race?.phase === 'racing', null, { timeout: 30000, polling: 200 });
// autopilot drives; window.__boost overrides its thruster decision
await page.evaluate((cam) => {
  __race.setAutopilot(true); __race.camera.setMode(cam);
  const ap = __race.player.autopilot, f = ap.update.bind(ap);
  ap.update = (c, ...a) => { f(c, ...a); if (window.__boost != null) c.veh.ctl.boost = window.__boost; };
  window.__boost = false;
}, cam);
const st = () => page.evaluate(() => { const p = __race.player;
  return { kmh: Math.round(Math.abs(p.speed) * 3.6), gas: +p.boost.gas.toFixed(3), jet: +p.boost.level.toFixed(2), fov: +__app.camera.fov.toFixed(1),
    u: +(p.track?.u ?? 0).toFixed(1), fps: __app.stats().fps, calls: __app.stats().calls }; });
await page.evaluate(({ s, v }) => __race.teleport(__race.player, s, 0, v), { s: S0, v: V0 });
await page.waitForTimeout(1600);
console.log('cruise ', JSON.stringify(await st())); await page.screenshot({ path: `${out}/0_cruise.png` });
await page.evaluate(() => { window.__boost = true; });
for (const [ms, name] of [[160, '1_open'], [700, '2_boost'], [1400, '3_boost'], [1600, '4_late']]) {
  await page.waitForTimeout(ms);
  console.log(name.padEnd(7), JSON.stringify(await st())); await page.screenshot({ path: `${out}/${name}.png` });
}
// fixed rig views of the plume (camera locked to the car frame): rear-quarter low and side
for (const [name, cp, look] of [['6_quarter', [2.6, 0.9, 5.6], [0, 0.5, 2.6]], ['7_side', [4.2, 0.7, 3.2], [0, 0.5, 3.2]], ['8_rear', [0, 1.1, 7.5], [0, 0.6, 2.4]]]) {
  await page.evaluate(({ cp, look }) => {
    window.__boost = true; window.__rig = { cp, look };
    if (!__race.sys._late0) { __race.sys._late0 = __race.sys.late; __race.sys.late = (dt) => { __race.sys._late0(dt); const r = window.__rig; if (!r) return;
      const p = __race.player, c = __app.camera, q = p.quaternion; const V = c.position.constructor;
      c.position.copy(new V(...r.cp).applyQuaternion(q).add(p.position)); c.up.set(0, 1, 0); c.lookAt(new V(...r.look).applyQuaternion(q).add(p.position)); c.fov = 50; c.updateProjectionMatrix(); }; }
  }, { cp, look });
  await page.evaluate(() => { __race.player.veh.gas = 1; });
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${out}/${name}.png` });
}
await page.evaluate(() => { window.__rig = null; });
await page.evaluate(() => { window.__boost = false; }); await page.waitForTimeout(250);
console.log('release', JSON.stringify(await st())); await page.screenshot({ path: `${out}/5_release.png` });
await page.waitForTimeout(1500);
console.log('after  ', JSON.stringify(await st()));
for (const l of [...new Set(logs)].slice(0, 10)) console.log(l);
await browser.close();
