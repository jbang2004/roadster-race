// Drive the player car, brake hard at speed and capture the chase view: checks the active wing (airbrake pitch) and
// the light bar under braking. Usage: node tools/wingtest.mjs [out dir]
import { chromium } from 'playwright-core';
import { CHROME, GPU_ARGS } from './chrome.mjs';
import fs from 'node:fs';
const out = process.argv[2] ?? 'shots/wing';
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
const st = () => page.evaluate(() => { const p = __race.player; const w = p.visual.lods[p.visual.lod].wing;
  return { kmh: Math.round(Math.abs(p.speed) * 3.6), wingDeg: w ? +(w.rotation.z * 57.3).toFixed(1) : null, lod: p.visual.lod, fps: __app.stats().fps }; });
await page.evaluate(() => __race.teleport(__race.player, 1000, 0, 55));
await page.keyboard.down('ArrowUp'); await page.waitForTimeout(2500);
console.log('cruise', JSON.stringify(await st()));
await page.screenshot({ path: `${out}/cruise.png` });
await page.keyboard.up('ArrowUp'); await page.keyboard.down('ArrowDown'); await page.waitForTimeout(700);
console.log('braking', JSON.stringify(await st()));
await page.screenshot({ path: `${out}/brake.png` });
await page.keyboard.up('ArrowDown'); await page.waitForTimeout(1500);
console.log('after', JSON.stringify(await st()));
for (const l of [...new Set(logs)].slice(0, 10)) console.log(l);
await browser.close();
