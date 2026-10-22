// 霓虹环线 NEON LOOP — gameplay entry: vehicle physics, AI, race director, input and cameras.
//
//   const race = createRace(app, track, { makeVisual, laps, aiCount });
//
//  * race.cars[0] is the player (CONTRACTS §Car state), race.cars[1..] the AI.
//  * makeVisual({ livery, isPlayer, car, name }) → visual { object, sync(car, dt), dispose() } | null  — called once per car;
//    createRace adds visual.object to app.scene if the factory did not, and calls visual.sync(car, dt) every frame.
//  * race.phase 'grid' | 'countdown' | 'racing' | 'finished'; race.start({laps, difficultyIndex}); race.reset(); race.paused.
//  * Events: race:phase, race:countdown {n, lamps}, race:lap, race:finish, race:results, car:collision, car:scrape, car:respawn, camera:mode.
//  * Listens: ui:pause {paused} (the UI owns Esc / P), ui:restart (reset + new countdown), ui:quit (back to the grid).
//  * race.camera: CameraRig (setMode('chase'|'hood'|'bumper'|'orbit'|'tv'), cycle(), setTarget(car)).
import { Race } from './race.js';
import { PlayerInput } from './input.js';
import { CameraRig } from './camera.js';
import { getTrack } from '../track/track.js';
import { ASSIST } from './params.js';

export { Race } from './race.js';
export { CameraRig } from './camera.js';
export { PlayerInput } from './input.js';

export function createRace(app, track = getTrack(), opts = {}) {
  const bus = app.bus;
  const core = new Race(track, { bus, laps: opts.laps ?? track.laps, aiCount: opts.aiCount ?? 7, seed: opts.seed ?? 1, playerAI: !!opts.playerAI,
    difficulty: opts.difficultyIndex ?? 1, catchUp: opts.catchUp ?? true });
  const player = core.cars[0];
  const camera = new CameraRig(app, core, track, core.road);
  const input = new PlayerInput({ onAction: (a) => action(a), handlePause: !!opts.handleEscape });
  player.veh.assist.tc = ASSIST.tc; player.veh.assist.abs = ASSIST.abs; player.veh.assist.stability = ASSIST.stability;

  const action = (a) => {
    if (a === 'camera') camera.cycle();
    else if (a.startsWith('camera:')) camera.setMode(a.slice(7));
    else if (a === 'reset') { if (core.phase === 'racing' && !core.paused) core.respawn(player, 3); }
    else if (a === 'pause') bus?.emit('ui:pause', { paused: !core.paused });
  };

  const race = {
    core, cars: core.cars, player, camera, input, track,
    get phase() { return core.phase; },
    get paused() { return core.paused; },
    set paused(v) { core.paused = !!v; if (v) input.neutral(); },
    get laps() { return core.laps; },
    set laps(n) { core.laps = n; },
    get time() { return core.time; },
    get raceTime() { return core.time; },
    get results() { return core.results; },
    get stats() { return core.stats; },
    get assists() { return player.veh.assist; },
    start(o) { core.start(o ?? {}); },
    reset() { core.reset(); camera.snap(); },
    respawn(car = player, back = 3) { core.respawn(car, back); },
    teleport(car, s, u, speed) { core.teleport(car, s, u, speed); camera.snap(); },
    setAutopilot(on, speedScale = 1) { player.autopilotOn = !!on; player.autopilot.speedScale = speedScale; },
    setDifficulty(i) { core.setDifficulty(i); },
    dispose() { offs.forEach(o => o()); camera.dispose(); input.dispose(); app.remove(sys); for (const c of core.cars) { c.visual?.object?.removeFromParent?.(); c.visual?.dispose?.(); } },
  };

  // ---- visuals
  if (opts.makeVisual) {
    for (const c of core.cars) {
      let v = null;
      try { v = opts.makeVisual({ livery: c.livery, isPlayer: c.isPlayer, car: c, name: c.name }); } catch (e) { console.error('[game] makeVisual failed', e); }
      if (v) {
        c.visual = v;
        if (v.object && !v.object.parent && app.scene) app.scene.add(v.object);
      }
    }
  }

  // ---- events from the UI
  const offs = [];
  if (bus) {
    offs.push(bus.on('ui:pause', ({ paused }) => { race.paused = paused; }));
    offs.push(bus.on('ui:restart', () => { core.reset(); core.start(); camera.snap(); }));
    offs.push(bus.on('ui:quit', () => { core.reset(); camera.snap(); camera.setMode('orbit'); }));
  }

  // ---- frame loop
  const sys = {
    fixed(h) {
      if (core.paused) return;
      if (core.phase === 'racing' && !player.race.finished && !player.autopilotOn && !core.playerAI) {
        input.update(h, player.veh.speed);
        const ctl = player.veh.ctl;
        ctl.throttle = input.throttle; ctl.brake = input.brake; ctl.steer = input.steer; ctl.handbrake = input.handbrake; ctl.reverse = input.reverse;
        ctl.boost = input.boost;
      } else if (!player.autopilotOn && !core.playerAI) player.veh.ctl.boost = false;
      core.fixed(h);
    },
    update(dt) {
      core.sync(app.time.alpha);
      core.flushScrapes();
      for (const c of core.cars) c.visual?.sync?.(c, dt);
    },
    late(dt) { camera.update(dt); },
  };
  app.add(sys);
  race.sys = sys;
  core.sync(1);
  camera.setMode(opts.camera ?? 'chase', true);
  camera.snap();
  return race;
}
