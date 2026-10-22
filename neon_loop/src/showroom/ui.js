// Showroom UI: back button, bottom toolbar (view / studio / colour / features / photo), popovers, hotspots with info cards, photo mode overlay.
import * as THREE from 'three';
import { buildShowroomCSS } from './style.js';
import { VIEWS, PRESETS, PRESET_ORDER, PAINTS, FEATURES, HOTSPOTS, T } from './presets.js';

const bi = (zh, en, cls = '') => `<span class="bi ${cls}"><span class="zh">${zh}</span><span class="en">${en}</span></span>`;
const STUDIO_BG = {
  dark: 'radial-gradient(120% 90% at 30% 20%, #4a4f58 0%, #1b1d22 46%, #0a0b0d 100%)',
  light: 'radial-gradient(120% 90% at 50% 15%, #ffffff 0%, #e2e4e8 55%, #b9bcc3 100%)',
  city: 'radial-gradient(60% 40% at 25% 70%, #ff9a54 0%, rgba(255,154,84,0) 70%), radial-gradient(60% 40% at 78% 60%, #3ee8ff 0%, rgba(62,232,255,0) 70%), linear-gradient(#101528, #05060c)',
};

export function createShowroomUI(app, ctx) {
  const { act, camera, hull } = ctx;
  const style = document.createElement('style'); style.textContent = buildShowroomCSS(); document.head.append(style);
  const root = document.createElement('div'); root.className = 'sr-ui';
  const touch = matchMedia('(pointer: coarse)').matches;
  root.innerHTML = `
    <div class="sr-top fade">
      <button class="sr-back" data-a="back">${'<span class="ch">‹</span>'}${bi(T.back[0], T.back[1])}</button>
      <div class="sr-title"><b>ROADSTER</b><span>${T.title[0]} · ${T.title[1]}</span></div>
      <div class="sr-name"><span class="zh">霓虹环线</span><span class="en">NEON LOOP · 2026</span></div>
    </div>
    <div class="sr-hot fade"></div>
    <div class="sr-card glass"><button class="x" data-a="card-x">×</button><h3><span class="zh"></span><span class="en"></span></h3><p class="z"></p><p class="e"></p>
      <div class="acts"><button data-a="card-view">${bi('查看', 'VIEW')}</button></div></div>
    <div class="sr-hint fade">${touch ? T.hintTouch[0] : T.hint[0]}<span class="en">${touch ? T.hintTouch[1] : T.hint[1]}</span></div>
    <div class="sr-pop glass" data-pop="views"><div class="hd"><span class="zh">${T.views[0]}</span><span class="en">${T.views[1]}</span></div><div class="sr-grid views"></div></div>
    <div class="sr-pop glass" data-pop="studio"><div class="hd"><span class="zh">${T.studio[0]}</span><span class="en">${T.studio[1]}</span></div><div class="sr-grid studios"></div></div>
    <div class="sr-pop glass" data-pop="paint"><div class="hd"><span class="zh">${T.paint[0]}</span><span class="en">${T.paint[1]}</span></div><div class="sr-swatches"></div></div>
    <div class="sr-pop glass" data-pop="features"><div class="hd"><span class="zh">${T.features[0]}</span><span class="en">${T.features[1]}</span></div><div class="sr-rows"></div></div>
    <div class="sr-bar glass">
      <button class="tab" data-tab="views">${bi(T.views[0], T.views[1])}</button>
      <button class="tab" data-tab="studio">${bi(T.studio[0], T.studio[1])}</button>
      <button class="tab" data-tab="paint">${bi(T.paint[0], T.paint[1])}</button>
      <button class="tab" data-tab="features">${bi(T.features[0], T.features[1])}</button>
      <span class="sep"></span>
      <button class="tab photo" data-a="photo">${bi(T.photo[0], T.photo[1])}</button>
    </div>
    <div class="sr-ph">
      <button class="exit glass" data-a="photo-x">${bi(T.exit[0], T.exit[1])}</button>
      <div class="tip">${bi(T.photoHint[0], T.photoHint[1])}</div>
      <div class="ap glass">${bi(T.aperture[0], T.aperture[1])}<input type="range" min="0" max="100" value="45" step="1" aria-label="aperture"></div>
      <div class="ring"></div>
    </div>
    <div class="sr-load"><div class="zh">${T.loading[0]}</div><div class="en">${T.loading[1]}</div><div class="bar"><i></i></div></div>`;
  document.body.append(root);
  const $ = (s) => root.querySelector(s), $$ = (s) => [...root.querySelectorAll(s)];

  // ---- popover contents
  $('.sr-grid.views').innerHTML = VIEWS.map(v => `<button class="sr-chip" data-view="${v.id}">${bi(v.zh, v.en)}</button>`).join('');
  $('.sr-grid.studios').innerHTML = PRESET_ORDER.map(id => `<button class="sr-chip" data-studio="${id}"><span class="sw" style="background:${STUDIO_BG[id]}"></span>${bi(PRESETS[id].zh, PRESETS[id].en)}</button>`).join('');
  $('.sr-swatches').innerHTML = PAINTS.map(p => `<button class="sr-sw" data-paint="${p.id}"><i style="background:${p.swatch}"></i>${bi(p.zh, p.en)}</button>`).join('');
  const featureRows = [...FEATURES, { id: 'rotate', zh: T.rotate[0], en: T.rotate[1] }, { id: 'hotspots', zh: T.hotspots[0], en: T.hotspots[1] }];
  $('.sr-rows').innerHTML = featureRows.map(f => `<button class="sr-row" data-feat="${f.id}">${bi(f.zh, f.en)}<span class="sw2"></span></button>`).join('');

  // ---- hotspots
  const hotLayer = $('.sr-hot');
  const hs = HOTSPOTS.map(h => {
    const el = document.createElement('button'); el.className = 'sr-hs'; el.dataset.hs = h.id; el.setAttribute('aria-label', h.en); hotLayer.append(el);
    return { h, el, p: new THREE.Vector3(...h.pos), n: new THREE.Vector3(...h.nrm).normalize(), vis: false };
  });
  const card = $('.sr-card'); let cardFor = null;
  let hotspotsOn = true;

  // ---- state
  let openPop = null, photo = false;
  const setPop = (name) => {
    openPop = openPop === name ? null : name;
    $$('.sr-pop').forEach(p => p.classList.toggle('on', p.dataset.pop === openPop));
    $$('.sr-bar .tab[data-tab]').forEach(t => t.classList.toggle('on', t.dataset.tab === openPop));
    if (openPop) closeCard();
    camera.autoBlocked = !!openPop;
  };
  function openCard(id) {
    const x = hs.find(a => a.h.id === id); if (!x) return;
    cardFor = x;
    $('.sr-card h3 .zh').textContent = x.h.zh; $('.sr-card h3 .en').textContent = x.h.en;
    $('.sr-card .z').textContent = x.h.tz; $('.sr-card .e').textContent = x.h.te;
    card.classList.add('on'); hs.forEach(a => a.el.classList.toggle('on', a === x));
    setPop(null); if (openPop) setPop(openPop);
    camera.autoBlocked = true;
    placeCard(true);
  }
  function closeCard() { cardFor = null; card.classList.remove('on'); hs.forEach(a => a.el.classList.remove('on')); camera.autoBlocked = !!openPop; }
  function placeCard(force) {
    if (!cardFor) return;
    if (matchMedia('(max-width: 760px), (max-aspect-ratio: 4/5)').matches) { card.style.left = card.style.top = ''; return; }
    const w = innerWidth, h = innerHeight, pw = card.offsetWidth || 300, ph = card.offsetHeight || 200;
    const q = cardFor.sx, r = cardFor.sy;
    let x = q + 34, y = r - ph / 2;
    if (x + pw > w - 24) x = q - 34 - pw;
    x = Math.max(24, Math.min(w - pw - 24, x)); y = Math.max(86, Math.min(h - ph - 130, y));
    card.style.left = x + 'px'; card.style.top = y + 'px';
  }

  // ---- events
  root.addEventListener('click', (e) => {
    const t = e.target.closest('button'); if (!t) return;
    const a = t.dataset.a;
    if (t.dataset.tab) { setPop(t.dataset.tab); act.sfx?.('select'); return; }
    if (a === 'back') { act.exit(); return; }
    if (a === 'photo') { setPhoto(true); return; }
    if (a === 'photo-x') { setPhoto(false); return; }
    if (a === 'card-x') { closeCard(); return; }
    if (a === 'card-view') { if (cardFor) act.goView(cardFor.h.view); return; }
    if (t.dataset.view) { act.goView(t.dataset.view); closeCard(); return; }
    if (t.dataset.studio) { act.setStudio(t.dataset.studio); return; }
    if (t.dataset.paint) { act.setPaint(t.dataset.paint); return; }
    if (t.dataset.feat) {
      const id = t.dataset.feat; const on = !t.classList.contains('on');
      if (id === 'hotspots') { hotspotsOn = on; hotLayer.style.opacity = on ? 1 : 0; hotLayer.style.pointerEvents = on ? '' : 'none'; if (!on) closeCard(); }
      else act.setFeature(id, on);
      t.classList.toggle('on', on); return;
    }
    if (t.dataset.hs) { if (cardFor && cardFor.h.id === t.dataset.hs) closeCard(); else openCard(t.dataset.hs); return; }
  });
  $('.sr-ph input').addEventListener('input', (e) => act.setAperture(+e.target.value / 100));

  function setPhoto(on) {
    photo = on; root.classList.toggle('photo', on);
    if (on) { closeCard(); if (openPop) setPop(openPop); }
    camera.autoBlocked = on;
    act.photo(on);
    const tip = $('.sr-ph .tip'); tip.style.opacity = 1; clearTimeout(tip._t); tip._t = setTimeout(() => { tip.style.opacity = 0; }, 3800);
  }
  function focusRing(x, y) { const r = $('.sr-ph .ring'); r.style.left = x + 'px'; r.style.top = y + 'px'; r.classList.remove('go'); void r.offsetWidth; r.classList.add('go'); }

  // ---- per frame
  const v3 = new THREE.Vector3(), cp = new THREE.Vector3(), tmp = new THREE.Vector3();
  function updateHotspots() {
    const cam = camera.camera; const w = innerWidth, h = innerHeight;
    cp.copy(cam.position);
    for (const x of hs) {
      let vis = hotspotsOn && !photo;
      if (vis) {
        v3.copy(x.p).project(cam);
        const sx = (v3.x * 0.5 + 0.5) * w, sy = (-v3.y * 0.5 + 0.5) * h;
        x.sx = sx; x.sy = sy;
        const inside = v3.z < 1 && sx > 18 && sx < w - 18 && sy > 70 && sy < h - 90;
        tmp.copy(cp).sub(x.p); const dist = tmp.length(); tmp.divideScalar(dist);
        const facing = tmp.dot(x.n) > 0.12;
        let hidden = false;
        if (inside && facing) {
          // the body SDF is a (conservative) visual hull: it bulges ~5-20 cm past the real surface, so the hotspot itself can sit inside it. Look from the camera to the point and
          // call it hidden only when the hull is entered well before the point (something else is in the way), not just near it.
          const hit = hull.march(cp, tmp.clone().negate(), dist, 0.03);
          hidden = !!hit && hit.distanceTo(cp) < dist - 0.5;
        }
        vis = inside && facing && !hidden && dist > 0.8;          // right up against the paint the marker would only cover what it points at
        const sc = Math.min(1, Math.max(0.5, 0.5 + (dist - 0.8) * 0.3));          // and it shrinks as the camera closes in (1 at ~2.5 m and beyond)
        x.el.style.transform = `translate(${sx.toFixed(1)}px, ${sy.toFixed(1)}px) scale(${sc.toFixed(3)})`;
      }
      x.el.classList.toggle('vis', vis);
      x.el.style.pointerEvents = vis ? 'auto' : 'none';
      if (!vis && cardFor === x) closeCard();
    }
    placeCard();
  }
  let hintT = 0;
  const hint = $('.sr-hint');
  return {
    root, openCard, closeCard, setPhoto, focusRing, setPop,
    get photo() { return photo; }, get popOpen() { return openPop; }, get cardOpen() { return !!cardFor; },
    update(dt, userActive) {
      updateHotspots();
      hintT += dt;
      if (userActive) hintT = Math.max(hintT, 6.5);
      hint.style.opacity = hintT < 6 && !openPop && !cardFor && !photo ? 1 : 0;
    },
    setViewActive(id) { $$('.sr-chip[data-view]').forEach(c => c.classList.toggle('on', c.dataset.view === id)); },
    setStudioActive(id) { $$('.sr-chip[data-studio]').forEach(c => c.classList.toggle('on', c.dataset.studio === id)); },
    setPaintActive(id) { $$('.sr-sw').forEach(c => c.classList.toggle('on', c.dataset.paint === id)); },
    setFeatureActive(id, on) { $$('.sr-row').forEach(c => { if (c.dataset.feat === id) c.classList.toggle('on', on); }); },
    setLoading(on, mode) { $('.sr-load').classList.toggle('off', !on); },
    resize() {
      const w = innerWidth, h = innerHeight;
      const phone = w < 760 || w / h < 0.8;
      root.style.setProperty('--u', phone ? '1' : Math.max(0.78, Math.min(1.7, Math.min(w / 1600, h / 900))).toFixed(3));
    },
    dispose() { root.remove(); style.remove(); },
  };
}
