// 霓虹环线 NEON LOOP — trackside world (owner W). `buildWorld(app, track) → world`.
import * as THREE from 'three';
import { lights } from '../core/lights.js';
import { LAYER } from '../core/layers.js';
import { Ctx } from './ctx.js';
import { loadWorldTextures, createDefs } from './materials.js';
import { LightGrid, bakeGeo } from './bake.js';
import { buildRoad } from './road.js';
import { buildBarriers } from './barriers.js';
import { buildGround, buildSidewalks } from './ground.js';
import { buildLamps, buildTunnel, buildUndersideLights, buildPosts } from './lamps.js';
import { buildCity } from './buildings.js';
import { makeSignAtlases, makeRoadSignAtlas, makeBoardTexture, makeGrafAtlas } from './signs_tex.js';
import { buildTrench } from './trench.js';
import { buildStartGantry, buildGrandstands, buildAdBoards, buildSkybridge, buildGantries, buildTunnelSigns } from './landmarks.js';
import { buildSigns, signQuad } from './signs.js';
import { buildQuays, buildDockSigns } from './docks.js';
import { buildMarket } from './market.js';
import { CANAL } from './params.js';
import { buildDeck, buildPiers, buildBridges, buildPortals, buildCanal, buildWater } from './structures.js';

export async function buildWorld(app, track) {
  const t0 = performance.now();
  const tex = await loadWorldTextures();
  const atlas = makeSignAtlases();
  const rs = makeRoadSignAtlas(), boardTex = makeBoardTexture();
  const graf = makeGrafAtlas();
  const defs = createDefs(tex, atlas, rs, boardTex, graf);
  const ctx = new Ctx(app, track, defs);
  const T = track;
  const lap = (name, fn) => { const t = performance.now(); fn(); if (app.q.has('wtime')) console.log(`[world] ${name} ${(performance.now() - t).toFixed(0)} ms`); };

  lap('road', () => buildRoad(ctx));
  lap('barriers', () => buildBarriers(ctx));
  lap('ground', () => buildGround(ctx));
  lap('sidewalks', () => buildSidewalks(ctx));
  lap('deck', () => buildDeck(ctx));
  lap('piers', () => buildPiers(ctx));
  lap('bridges', () => buildBridges(ctx));
  lap('portals', () => buildPortals(ctx));
  lap('canal', () => { buildCanal(ctx); buildWater(ctx); });
  lap('city', () => buildCity(ctx));
  lap('signs', () => buildSigns(ctx, atlas));
  lap('docks', () => { buildQuays(ctx); buildDockSigns(ctx, atlas, signQuad); });
  lap('market', () => buildMarket(ctx));
  lap('trench', () => buildTrench(ctx, graf));
  const root = new THREE.Group(); root.name = 'world';
  let start = null;
  lap('landmarks', () => {
    start = buildStartGantry(ctx, boardTex, root, defs);
    buildGrandstands(ctx); buildAdBoards(ctx, atlas); buildSkybridge(ctx); buildGantries(ctx, rs); buildTunnelSigns(ctx, rs);
  });
  lap('lamps', () => { buildLamps(ctx); buildTunnel(ctx); buildUndersideLights(ctx); buildPosts(ctx); });

  // ---- finalize: bake lights, create meshes ----
  const meshes = [];
  lap('bake+meshes', () => {
    const grid = new LightGrid(lights.list);
    for (const g of ctx.buckets.values()) {
      if (g.empty) continue;
      const d = defs[g.key];
      const geo = g.toGeometry();
      if (d.bake) geo.setAttribute('aLit', new THREE.BufferAttribute(bakeGeo(g, grid), 3));
      const mesh = new THREE.Mesh(geo, d.mat);
      mesh.layers.set(d.layer); mesh.matrixAutoUpdate = false; mesh.updateMatrix();
      mesh.name = `${g.key}|${g.chunk}`;
      root.add(mesh); meshes.push(mesh);
    }
  });
  app.scene.add(root);

  // road uniforms: start line + grid slots
  const ru = defs.road.mat.userData.uniforms;
  ru.uStartS.value = T.startS;
  for (let k = 0; k < 8; k++) { const s = T.gridSlot(k); ru.uSlot.value[k].set(s.s, s.u); }

  // water glints: the 8 canal-side lights nearest to the camera feed the water shader (no per-frame allocation)
  const wU = defs.water.mat.userData.uniforms;
  const wl = ctx.lightMeta.filter(l => l.lvl === 0 && l.pos.x > CANAL.x0 - 80 && l.pos.x < CANAL.x1 + 80 && l.intensity * l.color.g > 25);
  const NW = wl.length, wd = new Float32Array(8), wi = new Int32Array(8);
  const cam = app.camera;
  function updateWater() {
    const cp = cam.position;
    if (cp.x < CANAL.x0 - 110 || cp.x > CANAL.x1 + 110) { if (wU.uWL.value[0].w !== 0) for (let k = 0; k < 8; k++) wU.uWL.value[k].w = 0; return; }
    let n = 0;
    for (let j = 0; j < NW; j++) {
      const l = wl[j], dx = l.pos.x - cp.x, dy = l.pos.y - cp.y, dz = l.pos.z - cp.z, d2 = dx * dx + dy * dy + dz * dz;
      if (d2 > 90 * 90) continue;
      if (n === 8 && d2 >= wd[7]) continue;
      let k = n < 8 ? n++ : 7;
      while (k > 0 && wd[k - 1] > d2) { wd[k] = wd[k - 1]; wi[k] = wi[k - 1]; k--; }
      wd[k] = d2; wi[k] = j;
    }
    for (let k = 0; k < 8; k++) {
      if (k < n) { const l = wl[wi[k]]; wU.uWL.value[k].set(l.pos.x, l.pos.y, l.pos.z, Math.min(l.range || 40, 60)); const g = 0.0045 * Math.min(l.intensity, 900); wU.uWC.value[k].set(l.color.r * g, l.color.g * g, l.color.b * g); }
      else wU.uWL.value[k].w = 0;
    }
  }
  const world = {
    root, ctx, defs, meshes,
    update(dt, t) { updateWater(); },
    setStartLights(n) {
      if (!start) return;
      start.lamps.forEach((l, k) => { const on = k < n; l.disc.material = n === -1 ? start.matGo : on ? start.matOn : start.matOff; l.halo.visible = on || n === -1; l.halo.material = defs.halo.mat; });
    },
    dispose() {
      app.scene.remove(root);
      root.traverse((o) => { if (o.geometry) o.geometry.dispose(); });
      const texKeys = ['map', 'normalMap', 'roughnessMap', 'metalnessMap', 'aoMap', 'emissiveMap'];
      for (const d of Object.values(defs)) { for (const k of texKeys) d.mat[k]?.dispose(); d.mat.dispose(); }
      if (start) for (const m of [start.matOn, start.matOff, start.matGo]) m?.dispose?.();
      for (const t of [atlas.sign, atlas.screen, rs.tex, boardTex, graf.tex]) t?.dispose?.();
      // the light registry has no remove(): silence and unlist our lights
      const mine = new Set(ctx.lightMeta);
      for (const l of ctx.lightMeta) l.intensity = 0;
      for (let k = lights.list.length - 1; k >= 0; k--) if (mine.has(lights.list[k])) lights.list.splice(k, 1);
    },
  };
  if (app.q.has('wtime')) console.log(`[world] built in ${(performance.now() - t0).toFixed(0)} ms, ${meshes.length} meshes, ${lights.list.length} lights`);
  return world;
}
