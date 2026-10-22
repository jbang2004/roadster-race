// Downloads CC0 assets from Poly Haven (https://polyhaven.com) into public/assets/ph/.
// Usage: node tools/fetch-assets.mjs   (idempotent; skips files that already exist)
// The asset list below was approved by the user (≈60–100 MB total). Do not add to it without asking.
import fs from 'node:fs';
import path from 'node:path';

const UA = { 'User-Agent': 'neon-loop-dev' };
const OUT = path.resolve('public/assets/ph');

const TEXTURES = {
  asphalt_track: '2k',            // race surface
  asphalt_02: '2k',               // street surface variant
  concrete_pavement: '1k',        // sidewalks
  concrete_slab_wall: '1k',       // barriers, retaining walls
  concrete_panels: '1k',          // building facades
  concrete_tile_facade: '1k',     // tunnel walls
  ribbed_concrete_wall: '1k',     // pillars, expressway underside
  metal_plate: '1k',              // bridge deck, walkways
  corrugated_iron_02: '1k',       // market shacks
  painted_metal_shutter: '1k',    // shop shutters
  dark_brick_wall: '1k',          // older buildings
  rectangular_facade_tiles: '1k', // tower facades
};
const TEX_MAPS = { Diffuse: 'diff', nor_gl: 'nor', arm: 'arm' };
const HDRIS = { shanghai_bund: '2k' };

async function getJSON(url) {
  const r = await fetch(url, { headers: UA });
  if (!r.ok) throw new Error(`${r.status} ${url}`);
  return r.json();
}
async function download(url, dest) {
  if (fs.existsSync(dest) && fs.statSync(dest).size > 0) return 0;
  fs.mkdirSync(path.dirname(dest), { recursive: true });
  for (let attempt = 0; ; attempt++) {
    try {
      const r = await fetch(url, { headers: UA });
      if (!r.ok) throw new Error(`${r.status} ${url}`);
      const buf = Buffer.from(await r.arrayBuffer());
      fs.writeFileSync(dest, buf);
      return buf.length;
    } catch (err) {
      if (attempt >= 4) throw err;
      await new Promise(res => setTimeout(res, 800 * (attempt + 1)));
    }
  }
}

const manifest = { textures: {}, hdris: {} };
let total = 0;
const tasks = [];
for (const [id, res] of Object.entries(TEXTURES)) {
  tasks.push(async () => {
    const files = await getJSON(`https://api.polyhaven.com/files/${id}`);
    manifest.textures[id] = { res, maps: {} };
    for (const [map, short] of Object.entries(TEX_MAPS)) {
      const e = files[map]?.[res]?.jpg;
      if (!e) { console.warn(`missing ${id} ${map} ${res}`); continue; }
      const rel = `textures/${id}/${id}_${short}_${res}.jpg`;
      total += await download(e.url, path.join(OUT, rel));
      manifest.textures[id].maps[short] = rel;
    }
  });
}
for (const [id, res] of Object.entries(HDRIS)) {
  tasks.push(async () => {
    const files = await getJSON(`https://api.polyhaven.com/files/${id}`);
    const e = files.hdri?.[res]?.hdr;
    if (!e) { console.warn(`missing hdri ${id} ${res}`); return; }
    const rel = `hdri/${id}_${res}.hdr`;
    total += await download(e.url, path.join(OUT, rel));
    manifest.hdris[id] = rel;
  });
}
const pool = 4;
await Promise.all(Array.from({ length: pool }, async () => { while (tasks.length) await tasks.shift()(); }));
fs.writeFileSync(path.join(OUT, 'manifest.json'), JSON.stringify(manifest, null, 2));
console.log(`downloaded ${(total / 1e6).toFixed(1)} MB`);
