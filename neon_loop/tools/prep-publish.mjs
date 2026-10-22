// Turns dist/ into publish/: drops files the game never loads and rewrites index.html as page content
// (the artifact host wraps it in its own document skeleton). Prints the file list split into upload batches.
import fs from 'node:fs';
import path from 'node:path';
fs.rmSync('publish', { recursive: true, force: true });
fs.cpSync('dist', 'publish', { recursive: true });
fs.rmSync('publish/assets/car/wedge_car.glb', { force: true });
// the artifact host serves neither .glb nor .hdr: append the build's VITE_BIN_EXT to those files (loaders sniff the bytes)
const BIN = process.env.VITE_BIN_EXT ?? '.wasm';
for (const d of ['publish/assets/car', 'publish/assets/ph/hdri']) for (const f of fs.readdirSync(d)) if (/\.(glb|hdr)$/.test(f)) fs.renameSync(`${d}/${f}`, `${d}/${f}${BIN}`);
const man = JSON.parse(fs.readFileSync('publish/assets/ph/manifest.json', 'utf8'));
for (const k in man.hdris) man.hdris[k] += BIN;
fs.writeFileSync('publish/assets/ph/manifest.json', JSON.stringify(man));
const html = fs.readFileSync('dist/index.html', 'utf8');
const tags = [...html.matchAll(/<(script type="module"[^>]*><\/script>|link rel="modulepreload"[^>]*>)/g)].map(m => '<' + m[1]);
const page = `<title>霓虹环线 NEON LOOP</title>
<style>
  /* single dark look: a full-screen WebGL game */
  :root { --bg: #05060a; --fg: #9fb3c8; color-scheme: dark; }
  html, body { height: 100%; margin: 0; overflow: hidden; background: var(--bg); color: var(--fg); }
  #app { position: fixed; inset: 0; }
  #loader { position: fixed; inset: 0; z-index: 10; display: flex; align-items: center; justify-content: center;
    background: var(--bg); color: var(--fg); font: 500 14px/1.4 ui-monospace, Menlo, monospace; letter-spacing: .3em; }
</style>
<div id="app"></div>
<div id="loader">LOADING · 载入中</div>
${tags.join('\n')}
`;
fs.writeFileSync('publish/index.html', page);
const files = [];
const walk = (d) => { for (const f of fs.readdirSync(d)) { const p = path.join(d, f); if (fs.statSync(p).isDirectory()) walk(p); else if (p !== 'publish/index.html') files.push([path.relative('publish', p), fs.statSync(p).size]); } };
walk('publish');
files.sort((a, b) => a[1] - b[1]);
const batches = [[]]; let sum = 0;
for (const [f, s] of files) { if (sum + s > 55e6 || batches.at(-1).length >= 240) { batches.push([]); sum = 0; } batches.at(-1).push(f); sum += s; }
fs.writeFileSync('publish/.batches.json', JSON.stringify(batches));
console.log(files.length, 'files', (files.reduce((a, f) => a + f[1], 0) / 1e6).toFixed(1), 'MB in', batches.length, 'batches:', batches.map(b => b.length));
