// Keyboard playtest of the real game flow: title → Enter → countdown → drive with arrow keys. Screens + telemetry.
import { chromium } from 'playwright-core';
import { CHROME, GPU_ARGS } from './chrome.mjs';
import fs from 'node:fs';
const out = process.argv[2] ?? 'shots/I/play'; fs.mkdirSync(out, { recursive: true });
const b = await chromium.launch({ executablePath: CHROME, headless: true,
  args: [...GPU_ARGS, '--autoplay-policy=no-user-gesture-required'] });
const p = await b.newPage({ viewport: { width: 1600, height: 900 } });
const logs = []; p.on('console', m => { if (['error', 'warning'].includes(m.type())) logs.push(m.text().slice(0, 200)); }); p.on('pageerror', e => logs.push('PAGEERROR ' + e.message));
await p.goto('http://localhost:5180/?scene=full&harness=1');
await p.waitForFunction(() => window.__ready === true, null, { timeout: 120000 });
const tel = async (tag) => { const t = await p.evaluate(() => { const c = __race.player; return { phase: __race.phase, kmh: Math.round(c.speed * 3.6), s: Math.round(c.track.s), u: +c.track.u.toFixed(1), place: c.race.place, lap: c.race.lap, in: c.input, audio: __audio?.ctx?.state ?? __audio?.state ?? null }; }); console.log(tag, JSON.stringify(t)); };
await p.waitForTimeout(1500); await p.screenshot({ path: `${out}/0_title.png` }); await tel('title');
await p.keyboard.press('Enter'); await p.waitForTimeout(1200); await tel('after enter'); await p.screenshot({ path: `${out}/1_countdown.png` });
await p.waitForFunction(() => __race.phase === 'racing', null, { timeout: 15000 });
await p.keyboard.down('ArrowUp'); await p.waitForTimeout(3000); await tel('3s throttle'); await p.screenshot({ path: `${out}/2_launch.png` });
await p.waitForTimeout(6000); await tel('9s throttle');
await p.keyboard.down('ArrowDown'); await p.keyboard.up('ArrowUp'); await p.waitForTimeout(1500); await tel('braking'); await p.screenshot({ path: `${out}/3_brake.png` });
await p.keyboard.up('ArrowDown'); await p.keyboard.down('ArrowUp'); await p.keyboard.down('ArrowRight'); await p.waitForTimeout(1200); await tel('turn right'); await p.screenshot({ path: `${out}/4_turn.png` });
await p.keyboard.up('ArrowRight'); await p.waitForTimeout(2500); await tel('after turn'); await p.screenshot({ path: `${out}/5_after.png` });
await p.keyboard.up('ArrowUp'); await p.keyboard.press('Escape'); await p.waitForTimeout(800); await tel('paused?'); await p.screenshot({ path: `${out}/6_pause.png` });
for (const l of [...new Set(logs)].slice(0, 20)) console.log('LOG', l);
await b.close();
