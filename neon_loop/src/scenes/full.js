// The game: integrates every area (CONTRACTS §Area entry points). Areas that are missing or fail to load are
// skipped with a console error so the rest still runs.
import { getTrack } from '../track/track.js';
import { bus } from '../core/bus.js';
import { LAYER } from '../core/layers.js';

const MODS = import.meta.glob(['../skyline/index.js', '../render/index.js', '../world/index.js', '../car/index.js',
  '../fx/index.js', '../game/index.js', '../ui/index.js', '../audio/index.js']);

async function area(path) {
  const load = MODS[path];
  if (!load) { console.error(`[full] ${path} does not exist yet`); return null; }
  try { return await load(); } catch (e) { console.error(`[full] ${path} failed to load`, e); return null; }
}
async function attempt(label, fn) {
  try { return await fn(); } catch (e) { console.error(`[full] ${label} failed`, e); return null; }
}

export default async function (app) {
  const track = getTrack();
  const [skyM, renderM, worldM, carM, fxM, gameM, uiM, audioM] = await Promise.all(
    ['../skyline/index.js', '../render/index.js', '../world/index.js', '../car/index.js', '../fx/index.js',
      '../game/index.js', '../ui/index.js', '../audio/index.js'].map(area));

  await attempt('installAtmosphere', () => skyM?.installAtmosphere(app));
  const render = await attempt('createRenderer', () => renderM?.createRenderer(app, track));
  const [world, skyline] = await Promise.all([
    attempt('buildWorld', () => worldM?.buildWorld(app, track)),
    attempt('buildSkyline', () => skyM?.buildSkyline(app, track)),
    attempt('loadCarAssets', () => carM?.loadCarAssets(app)),
  ]);
  if (world) app.add(world);
  // ground-level and below-road surfaces add nothing to the wet-road reflection: keep them out of that pass
  world?.root?.traverse(o => { if (o.isMesh && /^(gnd|pave|water)/.test(o.name)) o.layers.set(LAYER.MAIN_ONLY); });
  if (skyline) app.add(skyline);

  const makeVisual = (opts) => {
    if (!carM) return null;
    const v = carM.createCarVisual(app, { ...opts, envMap: render?.probe?.texture ?? null });
    app.scene.add(v.object);
    return v;
  };
  const laps = +(app.q.get('laps') ?? track.laps);
  const race = gameM ? gameM.createRace(app, track, { makeVisual, laps, aiCount: 7 }) : null;
  window.__race = race;
  if (race && render) {
    render.setFocus(race.cars[0].visual?.object ?? race.cars[0]);
    render.setCars?.(race.cars.map(c => c.visual?.object).filter(Boolean));
    app.add({ update: () => render.fx.speed(Math.min(1, Math.abs(race.cars[0].speed ?? 0) / 90)) });
  }
  if (race && !app.q.has('autostart')) race.camera.setMode('orbit');   // title screen: cinematic orbit of the grid

  const fx = await attempt('createVehicleFx', () => fxM?.createVehicleFx(app));
  if (fx && race) app.add({ update: (dt) => fx.update(dt, race.cars) });
  if (fx?.tune) Object.assign(fx.tune, { smoke: 0.2, sprayA: 0.6, tailA: 0.7, drops: 0.7 });   // wet road: little smoke, lighter mist
  Object.assign(window, { __fx: fx, __world: world, __skyline: skyline });

  const ui = race ? await attempt('createUI', () => uiM?.createUI(app, race)) : null;
  const audio = race ? await attempt('createAudio', () => audioM?.createAudio(app, race)) : null;
  window.__ui = ui; window.__audio = audio;

  bus.on('race:countdown', ({ n, lamps }) => world?.setStartLights?.(lamps ?? (n > 0 ? 6 - n : -1)));
  bus.on('ui:start', (o) => race?.start?.(o));
  const unlock = () => { audio?.unlock?.(); };
  window.addEventListener('pointerdown', unlock, { once: true });
  window.addEventListener('keydown', unlock, { once: true });

  // ?autostart skips the title screen (harness / quick testing)
  if (app.q.has('autostart')) bus.emit('ui:start', { laps });
  await app.ready();
}
