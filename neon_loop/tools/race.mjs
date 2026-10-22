// Full race in the browser with the player on autopilot: node tools/race.mjs [laps=1] [outDir]
// Logs collisions/respawns/finishes, takes a few TV-cam shots during the race and the results screen at the end.
import { chromium } from 'playwright-core';
import { CHROME, GPU_ARGS } from './chrome.mjs';
import fs from 'node:fs';
const laps = +(process.argv[2] ?? 1), out = process.argv[3] ?? 'shots/I/race'; fs.mkdirSync(out, { recursive: true });
const b = await chromium.launch({ executablePath: CHROME, headless: true,
  args: [...GPU_ARGS, '--autoplay-policy=no-user-gesture-required'] });
const p = await b.newPage({ viewport: { width: 1600, height: 900 } });
const logs = []; p.on('console', m => { if (['error', 'warning'].includes(m.type())) logs.push(m.text().slice(0, 200)); }); p.on('pageerror', e => logs.push('PAGEERROR ' + e.message));
await p.goto(`http://localhost:5180/?scene=full&harness=1&autostart&laps=${laps}`);
await p.waitForFunction(() => window.__ready === true, null, { timeout: 120000 });
await p.evaluate(() => { __race.setAutopilot(true); window.__ev = []; const B = __app.bus;
  B.on('car:collision', e => { if (e.impulse > 3000) __ev.push(['col', e.kind, e.car?.name, Math.round(e.impulse), Math.round(e.car?.track?.s ?? 0)]); });
  B.on('car:respawn', e => __ev.push(['respawn', e.car?.name, Math.round(e.car?.track?.s ?? 0)]));
  B.on('race:lap', e => __ev.push(['lap', e.car?.name, e.lap, +(+e.time).toFixed(2)]));
  B.on('race:finish', e => __ev.push(['finish', e.car?.name, e.place, +(+e.time).toFixed(1)])); });
const t0 = Date.now(); let shot = 0;
while (true) {
  await p.waitForTimeout(5000);
  const st = await p.evaluate(() => ({ phase: __race.phase, done: __race.cars.filter(c => c.race.finished).length, fps: __app.stats().fps, pl: Math.round(__race.player.track.s) }));
  if (shot < 4 && (Date.now() - t0) > 20000 * (shot + 1)) { await p.evaluate(() => __race.camera.setMode('tv')); await p.waitForTimeout(1500); await p.screenshot({ path: `${out}/tv${shot}.png` }); await p.evaluate(() => __race.camera.setMode('chase')); shot++; }
  if (st.done === 8 || (Date.now() - t0) > laps * 200000) { console.log('state', JSON.stringify(st)); break; }
}
await p.waitForTimeout(4500);
await p.screenshot({ path: `${out}/results.png` });
console.log(JSON.stringify(await p.evaluate(() => ({ ev: __ev, res: (__race.results ?? []).map(r => JSON.stringify(r).slice(0, 120)) })), null, 0).slice(0, 4000));
for (const l of [...new Set(logs)].slice(0, 15)) console.log('LOG', l);
await b.close();
