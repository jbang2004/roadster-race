// App: renderer, scene, camera, the frame loop (fixed 120 Hz step + variable update) and harness hooks.
// See CONTRACTS.md §App.
import * as THREE from 'three';
import { LAYER } from './layers.js';
import { bus } from './bus.js';
import { setMaxAnisotropy } from './assets.js';
import { G } from './globals.js';

export class App {
  constructor(container) {
    this.q = new URLSearchParams(location.search);
    this.harness = this.q.has('harness');
    this.quality = this.q.get('q') ?? 'high';            // 'high' | 'medium' | 'low'
    this.bus = bus;

    const renderer = this.renderer = new THREE.WebGLRenderer({
      antialias: false, powerPreference: 'high-performance', stencil: false, preserveDrawingBuffer: this.harness,
    });
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;    // pipelines usually switch this off and tone-map themselves
    renderer.toneMappingExposure = 1;
    renderer.shadowMap.enabled = false;                    // render area decides
    this.maxPixelRatio = this._pixelRatio();
    this.renderScale = 1;                                  // pipelines may lower this (adaptive resolution)
    renderer.setPixelRatio(this.maxPixelRatio);
    container.appendChild(renderer.domElement);
    renderer.domElement.style.display = 'block';
    setMaxAnisotropy(Math.min(16, renderer.capabilities.getMaxAnisotropy()));

    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(62, 1, 0.1, 6000);
    this.camera.layers.enable(LAYER.MAIN_ONLY);
    this.scene.add(this.camera);                           // so camera-attached objects render

    this.systems = [];
    this.pipeline = null;
    this.fixedHz = 120;
    this.time = { t: 0, dt: 0, frame: 0, scale: this.q.has('freeze') ? 0 : 1, fixedT: 0, alpha: 0 };
    this._acc = 0;
    this._fps = 60;
    this._last = performance.now();

    window.addEventListener('resize', () => this.resize());
    this.resize();
    window.__app = this;
  }

  /** Register a system: { update?(dt,t), fixed?(h,t), late?(dt,t), resize?(w,h), dispose?() }. Returns it. */
  add(sys) { this.systems.push(sys); if (sys.resize) sys.resize(this.width, this.height); return sys; }
  remove(sys) { const i = this.systems.indexOf(sys); if (i >= 0) this.systems.splice(i, 1); sys.dispose?.(); }

  /** Install a render pipeline: { render(dt), setSize(w, h, pixelRatio), dispose?() }. */
  setPipeline(p) {
    this.pipeline?.dispose?.();
    this.pipeline = p;
    p?.setSize(this.width, this.height, this.maxPixelRatio * this.renderScale);
  }

  /** Device pixel ratio, capped so the canvas never exceeds ~3.7 MP (2560×1440); the pipeline upsamples from there. */
  _pixelRatio() {
    if (this.harness) return 1;
    const px = window.innerWidth * window.innerHeight;
    return Math.max(0.5, Math.min(window.devicePixelRatio, 2, Math.sqrt(3.7e6 / Math.max(px, 1))));
  }

  resize() {
    this.width = window.innerWidth; this.height = window.innerHeight;
    this.maxPixelRatio = this._pixelRatio();
    this.renderer.setPixelRatio(this.maxPixelRatio);
    this.renderer.setSize(this.width, this.height);
    this.camera.aspect = this.width / this.height;
    this.camera.updateProjectionMatrix();
    this.pipeline?.setSize(this.width, this.height, this.maxPixelRatio * this.renderScale);
    for (const s of this.systems) s.resize?.(this.width, this.height);
    bus.emit('resize', { w: this.width, h: this.height });
  }

  setView({ pos, target, fov }) {
    if (pos) this.camera.position.set(...pos);
    if (fov) { this.camera.fov = fov; this.camera.updateProjectionMatrix(); }
    if (target) this.camera.lookAt(...target);
    this.viewLocked = true;   // camera systems should leave the camera alone while this is set
  }

  start() {
    const loop = () => { this._raf = requestAnimationFrame(loop); this.frame(); };
    loop();
  }

  frame() {
    const now = performance.now();
    let real = Math.min((now - this._last) / 1000, 0.1);
    this._last = now;
    this._fps += ((real > 0 ? 1 / real : 60) - this._fps) * 0.05;
    const T = this.time;
    const dt = real * T.scale;
    T.dt = dt; T.t += dt; T.frame++;
    // fixed step
    const h = 1 / this.fixedHz;
    this._acc += dt;
    let steps = 0;
    while (this._acc >= h && steps < 10) {
      for (const s of this.systems) s.fixed?.(h, T.fixedT);
      T.fixedT += h; this._acc -= h; steps++;
    }
    if (steps === 10) this._acc = 0;
    T.alpha = this._acc / h;                 // interpolation factor between the last two fixed states
    for (const s of this.systems) s.update?.(dt, T.t);
    for (const s of this.systems) s.late?.(dt, T.t);
    G.uTime.value = T.t;
    G.uCamPos.value.copy(this.camera.position);
    if (this.pipeline) this.pipeline.render(dt);
    else this.renderer.render(this.scene, this.camera);
  }

  /** Compile shaders, render a couple of frames, remove the loader and signal the harness. */
  async ready() {
    try { await this.renderer.compileAsync(this.scene, this.camera); } catch (e) { console.warn('compileAsync', e); }
    this.frame(); this.frame();
    document.getElementById('loader')?.remove();
    await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
    window.__ready = true;
    bus.emit('ready');
  }

  stats() {
    const i = this.renderer.info;
    return { fps: Math.round(this._fps), calls: i.render.calls, tris: i.render.triangles, geo: i.memory.geometries, tex: i.memory.textures,
      w: this.width, h: this.height, pr: this.renderer.getPixelRatio(), ...(this.pipeline?.stats?.() ?? {}) };
  }
}
