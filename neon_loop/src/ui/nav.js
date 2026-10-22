// Menu focus model + keyboard / gamepad navigation. One Menu is "active" at a time and receives input.
// Menus emit sound requests on the bus ('ui:sfx' {name}) so audio stays decoupled.
import { bus } from '../core/bus.js';

export class Menu {
  /**
   * items: [{ id, el, kind:'action'|'choice'|'slider', disabled? }]
   * h: { onActivate(item), onAdjust(item, dir), onBack(), axis: 'v'|'h' }
   */
  constructor(items, h = {}) {
    this.items = items; this.h = h; this.axis = h.axis ?? 'v'; this.i = 0;
    items.forEach((it, k) => {
      it.el.addEventListener('mouseenter', () => { if (this.active && this.i !== k) this.focus(k); });
      it.el.addEventListener('click', (e) => {
        if (!this.active) return;
        const ar = e.target.closest?.('.ar');
        this.focus(k, true);
        if (ar) { this.adjust(+ar.dataset.d || 1); return; }
        if (it.kind === 'slider') { const r = it.el.querySelector('.segs')?.getBoundingClientRect(); if (r && e.clientX >= r.left && e.clientX <= r.right) { it.setFromFraction?.((e.clientX - r.left) / r.width); } return; }
        if (it.kind === 'choice') this.adjust(1); else this.activate();
      });
    });
    this.active = false;
    this.focus(0, true);
  }
  focus(k, silent = false) {
    const n = this.items.length; k = ((k % n) + n) % n;
    this.items[this.i]?.el.classList.remove('f');
    this.i = k; this.items[k].el.classList.add('f');
    if (!silent) bus.emit('ui:sfx', { name: 'move' });
  }
  move(d) {
    const n = this.items.length; let k = this.i;
    for (let t = 0; t < n; t++) { k = (k + d + n) % n; if (!this.items[k].disabled) break; }
    this.focus(k);
  }
  get item() { return this.items[this.i]; }
  activate() { const it = this.item; if (it && !it.disabled) { bus.emit('ui:sfx', { name: 'select' }); this.h.onActivate?.(it); } }
  adjust(d) { const it = this.item; if (it && (it.kind === 'choice' || it.kind === 'slider')) { this.h.onAdjust?.(it, d); bus.emit('ui:sfx', { name: 'adjust', dir: d }); } }
  back() { if (this.h.onBack) { bus.emit('ui:sfx', { name: 'back' }); this.h.onBack(); } }
  setActive(a) { this.active = a; if (a) this.focus(this.i, true); }
  /** dir: 'up'|'down'|'left'|'right'|'ok'|'back' */
  press(dir) {
    const v = this.axis === 'v';
    if (dir === 'up') v ? this.move(-1) : null;
    else if (dir === 'down') v ? this.move(1) : null;
    else if (dir === 'left') v ? this.adjust(-1) : this.move(-1);
    else if (dir === 'right') v ? this.adjust(1) : this.move(1);
    else if (dir === 'ok') this.activate();
    else if (dir === 'back') this.back();
  }
}

const KEYMAP = {
  ArrowUp: 'up', ArrowDown: 'down', ArrowLeft: 'left', ArrowRight: 'right',
  KeyW: 'up', KeyS: 'down', KeyA: 'left', KeyD: 'right',
  Enter: 'ok', NumpadEnter: 'ok', Space: 'ok', Escape: 'back', Backspace: 'back',
};

/** Routes keyboard + gamepad to `get()` (the active Menu or null). `onGlobal(code, e)` sees every key first. */
export function createNavInput(get, onGlobal) {
  const down = (e) => {
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    if (onGlobal?.(e.code, e)) return;
    const m = get(); if (!m) return;
    const d = KEYMAP[e.code]; if (!d) return;
    e.preventDefault(); m.press(d);
  };
  window.addEventListener('keydown', down);

  // gamepad: edge-triggered buttons, stick with repeat
  let prev = [], hold = 0, holdDir = null, repeat = 0;
  const BTN = { 12: 'up', 13: 'down', 14: 'left', 15: 'right', 0: 'ok', 1: 'back' };
  function poll(dt) {
    const pads = navigator.getGamepads ? navigator.getGamepads() : [];
    let pad = null; for (const p of pads) if (p && p.connected) { pad = p; break; }
    if (!pad) { prev.length = 0; return false; }
    const m = get(); let anyStart = false;
    // buttons
    for (const k in BTN) {
      const on = !!pad.buttons[k]?.pressed, was = !!prev[k];
      if (on && !was && m) m.press(BTN[k]);
    }
    const start = !!pad.buttons[9]?.pressed; if (start && !prev[9]) anyStart = true;
    // stick
    const ax = pad.axes[0] ?? 0, ay = pad.axes[1] ?? 0; let dir = null;
    if (Math.abs(ay) > Math.abs(ax)) { if (ay < -0.6) dir = 'up'; else if (ay > 0.6) dir = 'down'; }
    else if (ax < -0.6) dir = 'left'; else if (ax > 0.6) dir = 'right';
    if (dir !== holdDir) { holdDir = dir; hold = 0; repeat = 0; if (dir && m) m.press(dir); }
    else if (dir) { hold += dt; if (hold > 0.38) { repeat += dt; if (repeat > 0.13) { repeat = 0; m?.press(dir); } } }
    for (let k = 0; k < pad.buttons.length; k++) prev[k] = !!pad.buttons[k].pressed;
    return anyStart;
  }
  return { poll, dispose() { window.removeEventListener('keydown', down); } };
}
