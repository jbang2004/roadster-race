// Serves publish/ under a sub-path with an artifact-like skeleton and a strict CSP (no wasm, no eval, no query
// string), then loads the title screen, presses Enter and checks the race starts. Screens go to shots/P/.
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { chromium } from 'playwright-core';
import { CHROME, GPU_ARGS } from './chrome.mjs';

const ROOT = 'publish', PORT = 5190;
const TYPES = { '.js': 'text/javascript', '.json': 'application/json', '.jpg': 'image/jpeg', '.glb': 'model/gltf-binary', '.wasm': 'application/wasm', '.html': 'text/html' };
const CSP = "default-src 'none'; script-src 'self' https://cdnjs.cloudflare.com; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; " +
  "img-src 'self' data: blob:; media-src 'self' data: blob:; connect-src 'self' data: blob:; font-src https://fonts.gstatic.com data:; worker-src 'self' blob:";
const server = http.createServer((req, res) => {
  let p = decodeURIComponent(req.url.split('?')[0]).replace(/^\/x\//, '');
  if (!p || p === '/x') p = 'index.html';
  const f = path.join(ROOT, p);
  if (!f.startsWith(ROOT) || !fs.existsSync(f)) { console.log('404', p); res.writeHead(404); return res.end(); }
  let body = fs.readFileSync(f);
  if (p === 'index.html') body = `<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><style>:root{color-scheme:light}body{margin:0;font:14px system-ui}</style></head><body>${body}</body></html>`;
  res.writeHead(200, { 'content-type': TYPES[path.extname(f)] ?? 'application/octet-stream', 'content-security-policy': CSP });
  res.end(body);
}).listen(PORT);

const browser = await chromium.launch({ executablePath: CHROME, headless: true,
  args: [...GPU_ARGS, '--autoplay-policy=no-user-gesture-required'] });
const page = await browser.newPage({ viewport: { width: 1600, height: 900 }, deviceScaleFactor: 1 });
const logs = [], fails = [];
page.on('console', m => { if (['error', 'warning'].includes(m.type())) logs.push(`[${m.type()}] ${m.text().slice(0, 240)}`); });
page.on('pageerror', e => logs.push(`[pageerror] ${e.message}`));
page.on('requestfailed', r => fails.push(r.url()));
page.on('response', r => { if (r.status() >= 400) fails.push(r.status() + ' ' + r.url()); });
const t0 = Date.now();
await page.goto(`http://127.0.0.1:${PORT}/x/`, { waitUntil: 'domcontentloaded' });
await page.waitForFunction(() => window.__ready === true, null, { timeout: 180000, polling: 250 });
console.log('ready in', ((Date.now() - t0) / 1000).toFixed(1), 's');
fs.mkdirSync('shots/P', { recursive: true });
await page.waitForTimeout(2500);
await page.screenshot({ path: 'shots/P/title.png' });
const glb = await page.evaluate(() => performance.getEntriesByType('resource').filter(e => /\.(glb|hdr)/.test(e.name)).map(e => e.name.split('/').pop()));
console.log('glb loaded:', glb.join(', '));
await page.keyboard.press('Enter');
await page.waitForTimeout(600);
await page.keyboard.press('Enter');
await page.waitForFunction(() => window.__race?.phase === 'racing', null, { timeout: 30000, polling: 200 }).catch(() => console.log('phase', 'not racing'));
await page.keyboard.down('ArrowUp');
await page.waitForTimeout(6000);
await page.screenshot({ path: 'shots/P/race.png' });
await page.keyboard.up('ArrowUp');
console.log(JSON.stringify(await page.evaluate(() => ({ phase: __race.phase, kmh: Math.round(Math.abs(__race.player.speed) * 3.6), fps: __app.stats().fps }))));
for (const l of [...new Set(logs)].slice(0, 25)) console.log(l);
for (const f of [...new Set(fails)].slice(0, 25)) console.log('FAIL', f);
await browser.close(); server.close();
