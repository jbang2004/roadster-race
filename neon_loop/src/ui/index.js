// UI overlay (DOM/CSS + one canvas for the mini-map). `createUI(app, race) → ui`.
//
// Reads: race.cars[*] (CONTRACTS §Car state), race.phase, race.paused, race.laps, race.camera.setMode.
// Listens: race:phase, race:countdown, race:lap, race:finish, car:collision, camera:mode, ui:pause (from others).
// Emits:   ui:start {laps, difficulty, difficultyIndex, camera}, ui:pause {paused}, ui:restart, ui:quit,
//          ui:volume {volume}, ui:music {on}, ui:mute {muted}, ui:sfx {name}   (audio listens to the last four).
// The UI registers itself with app.add() — nothing to call per frame.
import { bus } from '../core/bus.js';
import { getTrack } from '../track/track.js';
import { buildCSS } from './style.js';
import { createHUD, h } from './hud.js';
import { createTracker } from './tracker.js';
import { createNavInput } from './nav.js';
import { createTitle, createPause, createResults } from './screens.js';
import { CAMERAS, CAMERA_LABELS, DIFFICULTIES, LAP_OPTIONS, clamp, fmtTime, num } from './format.js';

const STORE = 'neonloop.settings.v1';
const SCREENS = ['title', 'countdown', 'hud', 'pause', 'results'];

function loadSettings() {
  const d = { laps: 3, difficulty: 'normal', camera: 'chase', volume: 0.8, music: true };
  try {
    const s = JSON.parse(localStorage.getItem(STORE) || '{}');
    if (LAP_OPTIONS.includes(s.laps)) d.laps = s.laps;
    if (DIFFICULTIES.some(x => x.id === s.difficulty)) d.difficulty = s.difficulty;
    if (CAMERAS.some(x => x.id === s.camera)) d.camera = s.camera;
    if (Number.isFinite(s.volume)) d.volume = clamp(s.volume, 0, 1);
    if (typeof s.music === 'boolean') d.music = s.music;
  } catch { /* storage unavailable */ }
  return d;
}
const saveSettings = (s) => { try { localStorage.setItem(STORE, JSON.stringify(s)); } catch { /* ignore */ } };

export function createUI(app, race, opts = {}) {
  const track = getTrack();
  const settings = loadSettings();
  const root = h('div', 'nl-ui');
  const style = document.createElement('style'); style.textContent = buildCSS();
  document.head.append(style);
  document.body.append(root);

  let screen = 'title', muted = false, resultsAt = -1, lastPhase = race.phase, lastRacePaused = !!race.paused, startedLaps = settings.laps;
  let applyCam = false;

  const getLaps = () => (Number.isFinite(race.laps) ? race.laps : Number.isFinite(race.totalLaps) ? race.totalLaps : startedLaps ?? track.laps);
  const hud = createHUD(root, track);
  const vig = h('div', 'nl-vig'); root.prepend(vig);
  const tracker = createTracker({ race, track, bus, hud, getLaps });
  const S = tracker.S;

  // ---- countdown ----
  const count = h('div', 'nl-count');
  const cd = h('div', 'cd', `<div class="ring"></div><div class="d num">3</div><div class="sub zh">准备</div>`);
  count.append(cd); root.append(count);
  const cdD = cd.querySelector('.d'), cdSub = cd.querySelector('.sub');
  function showCount(n, hold = false) {
    const go = n <= 0;
    cdD.textContent = go ? 'GO' : String(n); cdSub.textContent = go ? '出发' : n === 3 ? '准备 GET READY' : n === 2 ? '就位 SET' : '预备 READY';
    cd.classList.remove('tick', 'hold'); cd.classList.toggle('go', go);
    void cd.offsetWidth; cd.classList.add(hold ? 'hold' : 'tick');
  }

  // ---- screens ----
  const title = createTitle(root, {
    settings,
    onChange(id) {
      saveSettings(settings);
      if (id === 'volume') bus.emit('ui:volume', { volume: settings.volume });
      if (id === 'music') bus.emit('ui:music', { on: settings.music });
    },
    onStart: startRace,
    onShowroom() { const u = new URL(location.href); u.searchParams.set('scene', 'showroom'); location.href = u.toString(); },
  });
  const pause = createPause(root, {
    onResume: () => setPaused(false),
    onRestart() { setPaused(false); doRestart(); },
    onQuit() { setPaused(false); doQuit(); },
  });
  const results = createResults(root, { onRestart: doRestart, onQuit: doQuit });
  const menus = { title: title.menu, pause: pause.menu, results: results.menu };
  const screenEls = { title: title.el, pause: pause.el, results: results.el };

  function activeMenu() { return menus[screen] ?? null; }
  function setScreen(name) {
    if (!SCREENS.includes(name)) return;
    screen = name;
    for (const k in screenEls) screenEls[k].classList.toggle('on', k === name);
    if (name !== 'hud' && menus[name]) menus[name].focus(0, true);
    for (const k in menus) menus[k].setActive(k === name);
    hud.setVisible(name === 'countdown' || name === 'hud' || name === 'pause', name === 'pause');
    vig.classList.toggle('on', name === 'countdown' || name === 'hud');
    if (name !== 'countdown') cd.classList.remove('tick', 'hold');
    if (name === 'hud' || name === 'countdown' || name === 'pause') requestAnimationFrame(() => hud.resize());
    root.dataset.screen = name;
  }

  // ---- flow ----
  function startRace() {
    startedLaps = settings.laps;
    const di = Math.max(0, DIFFICULTIES.findIndex(d => d.id === settings.difficulty));
    resultsAt = -1; tracker.reset(); results.resetSig();
    setScreen('countdown');
    bus.emit('ui:start', { laps: settings.laps, difficulty: settings.difficulty, difficultyIndex: di, camera: settings.camera });
    applyCam = true; applyCamera();
    bus.emit('ui:sfx', { name: 'start' });
  }
  function applyCamera() { try { race.camera?.setMode?.(settings.camera); } catch { /* camera not ready */ } }
  function doRestart() {
    resultsAt = -1; tracker.reset(); results.resetSig();
    setScreen('countdown');
    bus.emit('ui:restart');
  }
  function doQuit() { resultsAt = -1; tracker.reset(); setScreen('title'); bus.emit('ui:quit'); }
  function setPaused(p, emit = true) {
    p = !!p;
    if (p) {
      if (screen !== 'hud') return;
      const rc = race.cars?.[0]?.race ?? {};
      pause.setInfo({ lap: Math.min(rc.lap ?? 1, getLaps()), laps: getLaps(), place: rc.place ?? 1, total: S.total, best: rc.bestLap > 0 ? rc.bestLap : null });
      setScreen('pause');
    } else if (screen === 'pause') setScreen('hud');
    else return;
    if (emit) { bus.emit('ui:pause', { paused: p }); bus.emit('ui:sfx', { name: p ? 'back' : 'select' }); }
  }

  // ---- results rows ----
  function buildRows() {
    const cars = [...(race.cars ?? [])].sort((a, b) => num(a.race?.place, 99) - num(b.race?.place, 99));
    let fl = Infinity; for (const c of cars) { const b = c.race?.bestLap; if (b > 0 && b < fl) fl = b; }
    const lead = cars[0]?.race?.finished ? cars[0].race.finishTime : null;
    return cars.map((c) => {
      const r = c.race ?? {}, total = r.finished ? r.finishTime : null;
      return { place: r.place, name: c.name ?? `P${r.place}`, livery: c.livery ?? 0, isMe: !!c.isPlayer, total, best: r.bestLap > 0 && Number.isFinite(r.bestLap) ? r.bestLap : null,
        gap: total != null && lead != null ? total - lead : null, fastest: r.bestLap > 0 && r.bestLap === fl };
    });
  }
  const showResults = () => { results.render(buildRows()); setScreen('results'); };

  // ---- global keys ----
  const nav = createNavInput(activeMenu, (code, e) => {
    if (e.repeat && code !== 'KeyP' && code !== 'Escape') return false;
    if (code === 'KeyM' && !e.repeat) { muted = !muted; bus.emit('ui:mute', { muted }); hud.toast('声音', 'SOUND', muted ? '静音 MUTED' : '开启 ON'); return true; }
    if ((code === 'Escape' || code === 'KeyP') && !e.repeat) {
      if (screen === 'hud') { setPaused(true); e.preventDefault(); return true; }
      if (screen === 'pause' && code === 'KeyP') { setPaused(false); e.preventDefault(); return true; }
    }
    return false;
  });

  // ---- bus ----
  const offs = [
    bus.on('race:countdown', ({ n }) => { if (screen === 'title' || screen === 'results') setScreen('countdown'); if (n === 3 && applyCam) { applyCamera(); applyCam = false; } showCount(n); }),
    bus.on('race:phase', ({ phase }) => {
      if (phase === 'countdown' && (screen === 'title' || screen === 'results')) setScreen('countdown');
      if (phase === 'racing' && (screen === 'countdown' || screen === 'title')) setScreen('hud');
      if (phase === 'grid' || phase === 'countdown') { resultsAt = -1; if (phase === 'countdown') { tracker.reset(); results.resetSig(); } }
    }),
    bus.on('race:finish', ({ car, place, time }) => {
      if (!car?.isPlayer) return;
      hud.notify({ kind: 'fin', en: 'Finish', zh: '冲线', sub: `第 ${place} 名 · ${fmtTime(time)}`, ms: 3000, prio: 5 });
      resultsAt = S.time + 3.2;
    }),
    bus.on('car:collision', ({ car, impulse }) => { if (car?.isPlayer) hud.hit(clamp(num(impulse) / 30000, 0.15, 0.7)); }),
    bus.on('camera:mode', ({ mode }) => { const c = CAMERA_LABELS.find(x => x.id === mode); if (c && (screen === 'hud' || screen === 'countdown')) hud.toast('视角', 'CAMERA', `${c.zh} ${c.en}`); }),
    bus.on('ui:pause', ({ paused }) => { if (paused !== (screen === 'pause')) setPaused(paused, false); }),
  ];

  // auto-pause when the window loses focus mid-race
  const onBlur = () => { if (screen === 'hud') setPaused(true); };
  window.addEventListener('blur', onBlur);

  // ---- layout scale ----
  function resize(w = innerWidth, hgt = innerHeight) {
    const u = clamp(Math.min(w / 1600, hgt / 900), 0.55, 2.4);
    root.style.setProperty('--u', u.toFixed(4));
    hud.resize();
  }

  // ---- per-frame ----
  const sys = {
    update(dt) {
      const start = nav.poll(dt);
      if (start && screen === 'hud') setPaused(true); else if (start && screen === 'pause') setPaused(false);
      // follow race state we did not cause
      if (race.phase !== lastPhase) { lastPhase = race.phase; if (race.phase === 'racing' && screen === 'countdown') setScreen('hud'); }
      if (!!race.paused !== lastRacePaused) { lastRacePaused = !!race.paused; if (lastRacePaused !== (screen === 'pause')) setPaused(lastRacePaused, false); }
      if (screen === 'title') { tracker.update(dt); return; }
      tracker.update(dt);
      if (screen === 'countdown' || screen === 'hud' || screen === 'pause') hud.update(dt, S);
      if (race.phase === 'finished' && resultsAt < 0 && screen === 'hud') resultsAt = S.time + 2.4;
      if (resultsAt >= 0 && S.time >= resultsAt && (screen === 'hud' || screen === 'pause')) { resultsAt = -1; if (screen === 'pause') setPaused(false, true); showResults(); }
      if (screen === 'results') results.render(buildRows());
    },
    resize,
  };
  app.add(sys);
  resize();
  setScreen('title');

  const ui = {
    root, hud, settings, tracker,
    get screen() { return screen; },
    get muted() { return muted; },
    /** Force a screen (harness / lead): 'title' | 'hud' | 'countdown' (arg = 3|2|1|0, held) | 'pause' | 'results' */
    show(name, arg) {
      if (name === 'countdown') { setScreen('countdown'); showCount(arg ?? 3, true); }
      else if (name === 'results') { showResults(); }
      else if (name === 'pause') { setScreen('hud'); setPaused(true, false); }
      else setScreen(name);
      return screen;
    },
    startRace, setPaused, notify: (n) => hud.notify(n),
    /** Called by the lead if the camera mode is changed outside the UI. */
    applySettings() { bus.emit('ui:volume', { volume: settings.volume }); bus.emit('ui:music', { on: settings.music }); },
    dispose() { offs.forEach(o => o()); nav.dispose(); window.removeEventListener('blur', onBlur); tracker.dispose(); root.remove(); style.remove(); app.remove(sys); },
  };
  window.__nlUI = ui;
  setTimeout(() => ui.applySettings(), 0);   // let audio pick up the stored volume / music flag
  return ui;
}
