// Race-state watcher: derives the race clock, current lap time, who is ahead / behind, and raises HUD
// notifications (position change, lap, best lap, final lap, wrong way). Reads only the documented car/race state.
import * as THREE from 'three';
import { fmtTime, num } from './format.js';

const _f = new THREE.Vector3();

export function createTracker({ race, track, bus, hud, getLaps }) {
  const S = {
    player: null, cars: [], total: 8, laps: 3, racing: false, raceTime: 0, curLap: 0, time: 0,
    carAhead: null, carBehind: null, wrongWay: false, boost: 0,
  };
  let placeCand = 0, placeSince = 0, placeShown = 0, lastNoteT = -9, lapSeen = 0, wrongT = 0, rightT = 0, finished = false;

  function reset() {
    S.raceTime = 0; S.curLap = 0; placeCand = placeShown = 0; lapSeen = 0; wrongT = 0; rightT = 0; S.wrongWay = false; finished = false;
    hud.resetNotes();
  }

  const offs = [
    bus.on('race:phase', ({ phase }) => { if (phase === 'grid' || phase === 'countdown') reset(); }),
    bus.on('race:lap', ({ car, lap, time, best }) => {
      if (!car?.isPlayer) return;
      const laps = getLaps();
      const bl = car.race?.bestLap;
      const isBest = best === true || (typeof best === 'number' ? time <= best + 1e-3 : (bl > 0 && time <= bl + 1e-3));
      lap = car.race?.lapTimes?.length || lap;  // number of completed laps (robust to either lap numbering)
      if (lap >= laps) return;                  // the finish is handled by the results screen
      if (isBest && lap > 1) hud.notify({ kind: 'rec', en: 'New best lap', zh: '最快圈速', sub: fmtTime(time), ms: 3400, prio: 3 });
      else hud.notify({ kind: '', en: `Lap ${lap} complete`, zh: `第 ${lap} 圈完成`, sub: fmtTime(time), ms: 2800, prio: 2 });
      if (lap + 1 === laps && laps > 1) hud.notify({ kind: 'fin', en: 'Final lap', zh: '最后一圈', ms: 3000, prio: 2 });
    }),
  ];

  function update(dt) {
    const cars = race.cars ?? [];
    const p = cars[0] ?? null;
    S.player = p; S.cars = cars; S.total = cars.length || 8; S.laps = getLaps(); S.time += dt;
    S.racing = race.phase === 'racing';
    if (!p) return S;
    S.boost = Math.min(1, Math.max(0, +p.boost?.level || 0)) * 0.35;    // edge glow while the thrusters fire
    const rc = p.race ?? {};
    // race clock (prefer the race's own if it publishes one)
    const own = race.time ?? race.raceTime ?? race.clock;
    if (Number.isFinite(own)) S.raceTime = own;
    else if (S.racing && !race.paused && !rc.finished) S.raceTime += dt;
    // current lap
    let done = 0; const lt = rc.lapTimes;
    if (Array.isArray(lt) && lt.length >= (rc.lap ?? 1) - 1) { for (let i = 0; i < (rc.lap ?? 1) - 1; i++) done += num(lt[i]); } else done = S._lapStart ?? 0;
    S.curLap = rc.finished ? (rc.lapTimes?.[rc.lapTimes.length - 1] ?? 0) : Math.max(0, S.raceTime - done);
    if (race.phase === 'grid' || race.phase === 'countdown') S.curLap = 0;

    // ahead / behind
    const place = rc.place ?? 1;
    let a = null, b = null;
    for (const c of cars) { const cp = c.race?.place; if (cp === place - 1) a = c; else if (cp === place + 1) b = c; }
    S.carAhead = a; S.carBehind = b;

    // position-change notes (debounced; ignored in the opening seconds)
    if (S.racing) {
      if (place !== placeCand) { placeCand = place; placeSince = S.time; }
      if (placeShown === 0) placeShown = place;
      if (place !== placeShown && S.time - placeSince > 0.55 && S.raceTime > 3 && S.time - lastNoteT > 1.2) {
        const up = place < placeShown;
        const other = up ? cars.find(c => c.race?.place === place + 1) : cars.find(c => c.race?.place === place - 1);
        hud.notify({ kind: up ? 'up' : 'dn', en: up ? 'Position gained' : 'Position lost', zh: `${up ? '▲' : '▼'}  第 ${place} 名`,
          sub: other ? (up ? `超越 ${other.name ?? ''}` : `被 ${other.name ?? ''} 超越`) : '', ms: 2400, prio: 2 });
        bus.emit('ui:sfx', { name: up ? 'place-up' : 'place-down' });
        placeShown = place; lastNoteT = S.time;
      } else if (place !== placeShown && S.raceTime <= 3) placeShown = place;
    }

    // wrong way: moving against the road tangent while not facing along it
    if (S.racing && p.velocity && p.quaternion && p.track) {
      const i = Math.max(0, Math.min(track.N - 1, p.track.i | 0));
      const vt = p.velocity.x * track.tx[i] + p.velocity.z * track.tz[i];
      _f.set(0, 0, -1).applyQuaternion(p.quaternion);
      const facing = _f.x * track.tx[i] + _f.z * track.tz[i];
      if (vt < -4 && facing < 0.3) { wrongT += dt; rightT = 0; } else { rightT += dt; wrongT = Math.max(0, wrongT - dt * 2); }
      if (!S.wrongWay && wrongT > 0.9) S.wrongWay = true;
      else if (S.wrongWay && rightT > 0.6) { S.wrongWay = false; wrongT = 0; }
    } else if (!S.racing) { S.wrongWay = false; wrongT = 0; }
    return S;
  }
  return { S, update, reset, dispose() { offs.forEach(o => o()); } };
}
