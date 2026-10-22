// Player input: keyboard + gamepad → pedals / steering / handbrake with filtering (speed-sensitive steering rate so keyboard
// driving is smooth), automatic brake→reverse when stopped. Produces plain numbers; the vehicle applies the speed-dependent
// steering lock itself (STEER.speedFalloff). Works without a DOM (all browser access is guarded) so it can be unit-tested.

const clamp = (x, a, b) => (x < a ? a : x > b ? b : x);
const lerp = (a, b, t) => a + (b - a) * t;
const dz = (x, d) => { const a = Math.abs(x); return a < d ? 0 : Math.sign(x) * (a - d) / (1 - d); };

export class PlayerInput {
  /**
   * opts.target: EventTarget for key events (default window). opts.onAction(name): 'camera' | 'reset' | 'pause' | 'camera:N'
   */
  constructor(opts = {}) {
    this.keys = new Set();
    this.opts = opts;
    this.onAction = opts.onAction ?? null;
    this.enabled = true;
    this.throttle = 0; this.brake = 0; this.steer = 0; this.handbrake = 0; this.reverse = false; this.boost = false;
    this._steerRaw = 0;
    this._revT = 0; this._fwdT = 0;
    this.pad = null;
    this.usingPad = false;
    this.script = null;              // scripted override: fn(t) → {throttle, brake, steer, handbrake} | null
    this._t = 0;
    const target = opts.target ?? (typeof window !== 'undefined' ? window : null);
    this._target = target;
    this._down = (e) => this._key(e, true);
    this._up = (e) => this._key(e, false);
    this._blur = () => { this.keys.clear(); };
    if (target?.addEventListener) {
      target.addEventListener('keydown', this._down);
      target.addEventListener('keyup', this._up);
      target.addEventListener('blur', this._blur);
    }
  }

  dispose() {
    const t = this._target;
    if (t?.removeEventListener) { t.removeEventListener('keydown', this._down); t.removeEventListener('keyup', this._up); t.removeEventListener('blur', this._blur); }
  }

  _key(e, down) {
    const c = e.code;
    if (down) {
      if (e.repeat) { if (this._isDrive(c)) e.preventDefault?.(); return; }
      this.keys.add(c);
      if (!this.enabled) return;
      if (c === 'KeyC') this.onAction?.('camera');
      else if (c === 'KeyR') this.onAction?.('reset');
      else if (c === 'Escape' && this.opts?.handlePause) this.onAction?.('pause');
      else if (c === 'Digit1') this.onAction?.('camera:chase');
      else if (c === 'Digit2') this.onAction?.('camera:hood');
      else if (c === 'Digit3') this.onAction?.('camera:bumper');
      else if (c === 'Digit4') this.onAction?.('camera:tv');
      if (this._isDrive(c)) e.preventDefault?.();
    } else this.keys.delete(c);
  }
  _isDrive(c) { return c === 'ArrowUp' || c === 'ArrowDown' || c === 'ArrowLeft' || c === 'ArrowRight' || c === 'Space'; }

  _pollPad() {
    if (typeof navigator === 'undefined' || !navigator.getGamepads) return null;
    let pad = null;
    for (const p of navigator.getGamepads()) if (p && p.connected) { pad = p; break; }
    return pad;
  }

  /**
   * dt seconds, vFwd = forward speed of the car (m/s, signed). Fills this.throttle/brake/steer/handbrake/reverse.
   */
  update(dt, vFwd) {
    this._t += dt;
    if (this.script) {
      const s = this.script(this._t);
      if (s) {
        this.throttle = s.throttle ?? 0; this.brake = s.brake ?? 0; this.steer = s.steer ?? 0; this.handbrake = s.handbrake ?? 0;
        this.reverse = !!s.reverse; this.boost = !!s.boost;
        return;
      }
    }
    const k = this.keys;
    let fwd = (k.has('KeyW') || k.has('ArrowUp')) ? 1 : 0;
    let back = (k.has('KeyS') || k.has('ArrowDown')) ? 1 : 0;
    let steerT = ((k.has('KeyD') || k.has('ArrowRight')) ? 1 : 0) - ((k.has('KeyA') || k.has('ArrowLeft')) ? 1 : 0);
    let hb = k.has('Space') ? 1 : 0;
    let boost = k.has('ShiftLeft') || k.has('ShiftRight');      // cold-gas thrusters
    let analog = false;
    const pad = this._pollPad();
    if (pad) {
      const rt = pad.buttons[7]?.value ?? 0, lt = pad.buttons[6]?.value ?? 0;
      const sx = dz(pad.axes[0] ?? 0, 0.11);
      const a = pad.buttons[0]?.pressed ? 1 : 0;
      const active = rt > 0.03 || lt > 0.03 || Math.abs(sx) > 0.02 || a;
      if (active) {
        this.usingPad = true;
        fwd = Math.max(fwd, dz(rt, 0.03)); back = Math.max(back, dz(lt, 0.03));
        if (Math.abs(sx) > 0.02 || steerT === 0) { steerT = Math.sign(sx) * Math.pow(Math.abs(sx), 1.3); analog = Math.abs(sx) > 0.02; }
        hb = Math.max(hb, a);
      }
      boost = boost || !!pad.buttons[5]?.pressed;                // RB
      // action buttons (edge)
      const b = (i) => !!pad.buttons[i]?.pressed;
      this._padPrev ??= {};
      const edge = (i, name) => { const on = b(i); if (on && !this._padPrev[i] && this.enabled) this.onAction?.(name); this._padPrev[i] = on; };
      edge(3, 'camera'); edge(2, 'reset'); edge(8, 'reset');
    }

    // ---- direction logic: brake → reverse when (nearly) stopped
    const stopped = Math.abs(vFwd) < 1.1;
    let throttleT = 0, brakeT = 0, rev = this.reverse;
    if (!rev) {
      throttleT = fwd; brakeT = back;
      if (back > 0.1 && fwd < 0.05 && stopped) { this._revT += dt; if (this._revT > 0.22) rev = true; } else this._revT = 0;
    } else {
      throttleT = back; brakeT = fwd;
      if (fwd > 0.1 && back < 0.05 && stopped) { this._fwdT += dt; if (this._fwdT > 0.12) rev = false; } else this._fwdT = 0;
      if (vFwd > 3 && back < 0.05) rev = false;
    }
    if (rev !== this.reverse) { this.reverse = rev; this._revT = this._fwdT = 0; }
    if (brakeT > 0.3) throttleT = 0;

    // ---- pedal ramps (keyboard is binary; analog goes through nearly untouched)
    const rate = (cur, tgt, up, down) => cur + clamp(tgt - cur, -down * dt, up * dt);
    this.throttle = rate(this.throttle, throttleT, analog || this.usingPad ? 30 : 5.5, 12);
    this.brake = rate(this.brake, brakeT, analog || this.usingPad ? 30 : 7, 14);
    this.handbrake = hb;
    this.boost = boost;

    // ---- steering: speed-sensitive rate limits give smooth keyboard control
    const sf = clamp(Math.abs(vFwd) / 70, 0, 1);
    const cur = this.steer;
    let rt;
    if (analog) rt = lerp(9, 6, sf);
    else if (steerT === 0 || Math.sign(steerT) !== Math.sign(cur) && cur !== 0) rt = lerp(6.5, 3.4, sf);   // centering / reversing direction
    else rt = lerp(3.4, 0.95, Math.sqrt(sf));
    this.steer = cur + clamp(steerT - cur, -rt * dt, rt * dt);
  }

  /** Make the pedals/steer neutral (pause, phase change). */
  neutral() { this.throttle = this.brake = this.steer = this.handbrake = 0; this.reverse = false; this.boost = false; }
}
