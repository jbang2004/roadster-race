// tools/shot.mjs with the car assets served from a local build folder instead of public/assets/car (nothing is written to public/).
//   node shots/lipfix/shot_route.mjs --car <dir> --scene car --out a.png [--eval ...] [--wait ms] [--w --h] [--q ...]
import { chromium } from 'playwright-core';
import { CHROME, GPU_ARGS } from './chrome.mjs';
import fs from 'node:fs';
import path from 'node:path';

const args = Object.fromEntries(process.argv.slice(2).reduce((acc, a, i, arr) => {
  if (a.startsWith('--')) acc.push([a.slice(2), arr[i + 1] && !arr[i + 1].startsWith('--') ? arr[i + 1] : 'true']);
  return acc;
}, []));
const W = +(args.w ?? 1600), H = +(args.h ?? 900);
const url = `http://localhost:${args.port ?? 5180}/?scene=${args.scene ?? 'car'}&harness=1${args.q ? '&' + args.q : ''}`;
const browser = await chromium.launch({
  executablePath: CHROME, headless: true,
  args: [...GPU_ARGS],
});
const page = await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
const logs = [];
if (args.car) {
  const dir = path.resolve(args.car);
  await page.route(/\/assets\/car\/(car_[a-z0-9_]+(\.raw)?\.(glb|json))(\?.*)?$/, (route, req) => {
    const name = new URL(req.url()).pathname.split('/').pop();
    const f = path.join(dir, name);
    if (!fs.existsSync(f)) { logs.push(`[route] missing ${name}, passing through`); return route.continue(); }
    logs.push(`[route] ${name}`);
    route.fulfill({ status: 200, body: fs.readFileSync(f), contentType: name.endsWith('.json') ? 'application/json' : 'model/gltf-binary' });
  });
}
page.on('console', m => { if (['error', 'warning'].includes(m.type())) logs.push(`[console.${m.type()}] ${m.text()}`); });
page.on('pageerror', e => logs.push(`[pageerror] ${e.message}`));
await page.goto(url, { waitUntil: 'domcontentloaded' });
await page.waitForFunction(() => window.__ready === true, null, { timeout: 60000, polling: 100 });
if (args.eval) { const r = await page.evaluate(args.eval); if (r !== undefined) logs.push(`[eval] ${JSON.stringify(r)}`); }
await page.waitForTimeout(+(args.wait ?? 2500));
fs.mkdirSync(path.dirname(path.resolve(args.out)), { recursive: true });
await page.screenshot({ path: args.out });
console.log(`[harness] ${url} -> ${args.out}`);
for (const l of logs) console.log(l);
await browser.close();
