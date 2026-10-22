// K — skyline, sky, atmosphere, weather. Entry points: installAtmosphere(app), buildSkyline(app, track).
//
//   installAtmosphere(app)          call FIRST (before any material compiles). Patches three's fog ShaderChunks (height + distance
//                                   fog whose colour follows the city glow; no per-material setup needed), keeps scene.fog as a
//                                   non-null placeholder (never set it to null), adds the sky dome (renders at infinity, also
//                                   visible in reflection / probe passes) and the global hemisphere + moon lights (lightEverything).
//   buildSkyline(app, track)        → skyline { params, atmosphere, root, roadDistance(x,z), timing, counts, update, setWeather,
//                                   dispose }. Everything beyond the near band: far ground (y = -0.05, only >= 120 m from the road
//                                   edge), ~5 km of instanced towers (one façade material), landmarks, rails/trains, cable bridge,
//                                   billboards + holograms, flying traffic, searchlights, blimps, rain / splashes (LAYER.LATE).
//   skyline.setWeather({rain, mist}) 0..1 each; writes G.uRain / G.uWet. skyline.params.fog / colors / sky / lights are live-tunable.
import * as THREE from 'three';
import { installAtmosphere, getAtmosphere, params as atmoParams } from './atmosphere.js';
import { G } from '../core/globals.js';
import { buildRoadField, planLots } from './city.js';
import { createFacadeMaterial, InstanceSet, buildInstancedMeshes, emitLot, createBeaconMesh } from './towers.js';
import { buildGround } from './ground.js';
import { createWeather } from './weather.js';
import { createTraffic, createSearchlights, createBlimps } from './traffic.js';
import { makeAdAtlas } from './ads.js';
import { reservedRects, emitLandmarks, emitRails, createTrains, createCableBridge } from './mega.js';
import { makeBoxGeometry } from './facade.js';
import { createBillboards } from './billboards.js';
import { createHolograms } from './hologram.js';
import { lights } from '../core/lights.js';

export { installAtmosphere };

export async function buildSkyline(app, track) {
  const atmo = getAtmosphere() ?? installAtmosphere(app);
  const scene = app.scene;
  const root = new THREE.Group(); root.name = 'K-skyline'; scene.add(root);
  const parts = [];
  const timing = {};
  const T0 = performance.now();
  const lap = (k) => { timing[k] = Math.round(performance.now() - T0); };

  const field = buildRoadField(track); lap('field');
  const cn = track.layout.canal, B = track.layout.bounds;

  // far ground
  const ground = buildGround(app, track, field);
  for (const o of ground.objects) root.add(o);
  lap('ground');

  // towers
  const facade = createFacadeMaterial();
  const lots = planLots(track, field, cn, B, reservedRects(B));
  const set = new InstanceSet(), beacons = [], screens = [];
  for (const lot of lots) emitLot(lot, set, beacons, screens);
  const landmarks = emitLandmarks(set, beacons, screens);
  emitRails(set, beacons);
  const bridge = createCableBridge(set, beacons, cn, B);
  const towers = buildInstancedMeshes(set, facade, 'K-towers');
  for (const m of towers) root.add(m);
  root.add(bridge.lines);
  const trains = createTrains(facade, makeBoxGeometry); root.add(trains.mesh); parts.push(trains);
  const beaconMesh = createBeaconMesh(beacons);
  root.add(beaconMesh);
  lap('towers');

  // flying traffic, searchlights, blimps
  const adTex = makeAdAtlas();
  const boards = createBillboards(screens, adTex); root.add(boards.group);
  for (const sc of screens) {          // the biggest screens near the track act as coloured fill lights for W / R
    if (sc.w * sc.h > 3000 && field.dist(sc.x, sc.z) < 520) lights.add({ pos: [sc.x + sc.nx * 12, sc.y + sc.h * 0.5, sc.z + sc.nz * 12], color: [0.6, 0.5, 1.0], intensity: 380, range: 260, kind: 'sign' });
  }
  const holo = createHolograms(); root.add(holo.group); parts.push(holo);
  const traffic = createTraffic(app, lots); root.add(traffic.group); parts.push(traffic);
  const search = createSearchlights(lots); root.add(search.group);
  const blimps = createBlimps(adTex, lots); root.add(blimps.group); parts.push(blimps);
  lap('traffic');

  // weather
  const weather = createWeather(app, track, atmo);
  root.add(weather.group); parts.push(weather);
  lap('weather');

  const skyline = {
    params: atmoParams,
    atmosphere: atmo,
    root,
    roadDistance: field.dist,
    timing,
    counts: { lots: lots.length, instances: set.count, beacons: beacons.length / 7, craft: traffic.craftCount, screens: screens.length, lanes: traffic.lanes.length, searchlights: search.picks.length },
    update(dt, t) { for (const p of parts) p.update?.(dt, t); },
    setWeather({ rain, mist } = {}) {
      if (rain !== undefined) atmo.weather.rain = rain;
      if (mist !== undefined) atmo.weather.mist = mist;
      G.uRain.value = atmo.weather.rain;
      G.uWet.value = Math.min(1, 0.7 + 0.3 * atmo.weather.rain + 0.15 * atmo.weather.mist);
    },
    dispose() { root.removeFromParent(); for (const p of parts) p.dispose?.(); },
  };
  skyline.setWeather({});
  return skyline;
}
