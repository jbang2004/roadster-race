// Lap tour of the full game: one page load, autopilot on, teleport the player to each lap distance and screenshot.
// Usage: node tools/tour.mjs [--s 150,1000,...] [--out shots/I/tour] [--w 1600 --h 900] [--speed 45] [--settle 1800]
//        [--q "extra=1"] [--cam chase] [--eval "<js run once after start>"]
import { chromium } from 'playwright-core';
import { CHROME, GPU_ARGS } from './chrome.mjs';
import fs from 'node:fs';

const args = Object.fromEntries(process.argv.slice(2).reduce((acc, a, i, arr) => {
  if (a.startsWith('--')) acc.push([a.slice(2), arr[i + 1] && !arr[i + 1].startsWith('--') ? arr[i + 1] : 'true']);
  return acc;
}, []));
const W = +(args.w ?? 1600), H = +(args.h ?? 900);
const out = args.out ?? 'shots/I/tour';
const S = (args.s ?? '150,560,1000,1180,1370,1700,1950,2500,3050,3330,3450,3600,3800,3950,4150,4360,4500').split(',').map(Number);
const speed = +(args.speed ?? 45), settle = +(args.settle ?? 1800);
fs.mkdirSync(out, { recursive: true });

const browser = await chromium.launch({
  executablePath: CHROME, headless: true,
  args: [...GPU_ARGS, '--autoplay-policy=no-user-gesture-required'],
});
const page = await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
const logs = [];
page.on('console', m => { if (['error', 'warning'].includes(m.type())) logs.push(`[console.${m.type()}] ${m.text().slice(0, 300)}`); });
page.on('pageerror', e => logs.push(`[pageerror] ${e.message}`));
await page.goto(`http://localhost:5180/?scene=full&harness=1&autostart${args.q ? '&' + args.q : ''}`, { waitUntil: 'domcontentloaded' });
await page.waitForFunction(() => window.__ready === true, null, { timeout: 120000, polling: 200 });
await page.waitForFunction(() => window.__race?.phase === 'racing', null, { timeout: 30000, polling: 200 });
await page.evaluate(({ cam }) => { __race.setAutopilot(true); if (cam) __race.camera.setMode(cam); }, { cam: args.cam ?? null });
if (args.eval) await page.evaluate(args.eval);
for (const s of S) {
  await page.evaluate(({ s, speed }) => __race.teleport(__race.player, s, 0, speed), { s: s - speed * settle / 1000 * 0.9, speed });
  await page.waitForTimeout(settle);
  const f = `${out}/s${String(s).padStart(4, '0')}.png`;
  await page.screenshot({ path: f });
  const st = await page.evaluate(() => { const a = __app.stats(); const p = __race.player; const c = __app.camera.position, q = p.position; return { fps: a.fps, calls: a.calls, tris: a.tris, s: Math.round(p.track?.s ?? 0), u: +(p.track?.u ?? 0).toFixed(1), kmh: Math.round(Math.abs(p.speed) * 3.6),
    cam: __race.camera.mode, camD: +c.distanceTo(q).toFixed(1), camY: +(c.y - q.y).toFixed(1), lod: p.visual?.lod, vis: p.visual?.object?.visible }; });
  console.log(f, JSON.stringify(st));
}
for (const l of [...new Set(logs)].slice(0, 30)) console.log(l);
await browser.close();
