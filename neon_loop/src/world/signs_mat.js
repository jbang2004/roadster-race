// Emissive sign material (atlas + flicker), animated advertising screens, and additive glow halos (camera-facing sprites).
import * as THREE from 'three';
import { G } from '../core/globals.js';
import { NOISE_GLSL } from './glsl.js';

export function makeSignMaterial(atlas, gain = 5) {
  const m = new THREE.MeshBasicMaterial({ map: atlas.sign, vertexColors: true, color: new THREE.Color(gain, gain, gain) });
  m.onBeforeCompile = (sh) => {
    sh.uniforms.uTime = G.uTime;
    sh.vertexShader = sh.vertexShader.replace('#include <common>', '#include <common>\nattribute vec2 aFl; varying vec2 vFl;')
      .replace('#include <begin_vertex>', '#include <begin_vertex>\nvFl = aFl;');
    sh.fragmentShader = sh.fragmentShader.replace('#include <common>', '#include <common>\nuniform float uTime; varying vec2 vFl;')
      .replace('#include <map_fragment>', `#include <map_fragment>
      { float ph = vFl.x; float a = vFl.y;
        float r = fract(sin(floor(uTime * 9. + ph * 40.) * 91.17 + ph * 311.) * 43758.5);
        float slow = .85 + .15 * sin(uTime * 1.3 + ph * 20.);
        float off = step(.965, r) * a;
        diffuseColor.rgb *= slow * (1. - .85 * off); }`);
  };
  m.customProgramCacheKey = () => 'world_sign_v1';
  return m;
}

export function makeScreenMaterial(atlas, gain = 2.2) {
  const m = new THREE.MeshBasicMaterial({ map: atlas.screen, vertexColors: true, color: new THREE.Color(gain, gain, gain) });
  m.onBeforeCompile = (sh) => {
    sh.uniforms.uTime = G.uTime;
    sh.vertexShader = sh.vertexShader.replace('#include <common>', '#include <common>\nattribute vec4 aScr; varying vec4 vScr; varying vec2 vSUv;')
      .replace('#include <begin_vertex>', '#include <begin_vertex>\nvScr = aScr; vSUv = uv;');
    sh.fragmentShader = sh.fragmentShader.replace('#include <common>', `#include <common>\nuniform float uTime; varying vec4 vScr; varying vec2 vSUv;\n${NOISE_GLSL}`)
      .replace('#include <map_fragment>', `
      { float g = vScr.x, ph = vScr.y, sp = vScr.z;
        float ft = uTime * sp + ph; float f0 = floor(ft); float bl = smoothstep(.75, 1., fract(ft));
        vec2 uvq = clamp(vSUv, .004, .996);
        vec2 u0 = vec2((mod(f0, 4.) + uvq.x) / 4., (g + uvq.y) / 8.), u1 = vec2((mod(f0 + 1., 4.) + uvq.x) / 4., (g + uvq.y) / 8.);
        vec3 c = mix(texture2D(map, u0).rgb, texture2D(map, u1).rgb, bl);
        // LED pixel grid + gentle scan flicker
        vec2 px = fract(vSUv * vec2(160., 80.)); float grid = smoothstep(.0, .25, px.x) * smoothstep(.0, .25, px.y);
        float scan = .93 + .07 * sin(vSUv.y * 400. - uTime * 8.);
        diffuseColor.rgb *= c * mix(.55, 1., grid) * scan * (.9 + .1 * sin(uTime * 3. + ph)); }`);
  };
  m.customProgramCacheKey = () => 'world_screen_v1';
  return m;
}

/** Radial glow texture for halos. */
export function makeHaloTexture() {
  const c = document.createElement('canvas'); c.width = c.height = 128;
  const x = c.getContext('2d'); const g = x.createRadialGradient(64, 64, 0, 64, 64, 64);
  g.addColorStop(0, 'rgba(255,255,255,1)'); g.addColorStop(0.12, 'rgba(255,255,255,0.55)'); g.addColorStop(0.35, 'rgba(255,255,255,0.14)'); g.addColorStop(0.7, 'rgba(255,255,255,0.03)'); g.addColorStop(1, 'rgba(255,255,255,0)');
  x.fillStyle = g; x.fillRect(0, 0, 128, 128);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t;
}

/** Additive camera-facing sprites. Per vertex: position = sprite centre, aCorner = (size, ox, oy); colour = tint (rgb) * intensity. */
export function makeHaloMaterial(tex) {
  const m = new THREE.MeshBasicMaterial({ map: tex, vertexColors: true, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, fog: true });
  m.onBeforeCompile = (sh) => {
    sh.vertexShader = sh.vertexShader.replace('#include <common>', '#include <common>\nattribute vec3 aCorner;')
      .replace('#include <project_vertex>', `
        vec4 mvPosition = vec4(transformed, 1.0);
        mvPosition = modelViewMatrix * mvPosition;
        mvPosition.xy += aCorner.yz * aCorner.x;
        gl_Position = projectionMatrix * mvPosition;`);
  };
  m.customProgramCacheKey = () => 'world_halo_v1';
  return m;
}

/** Soft cloud puff for steam / mist sprites (alpha = density). */
export function makeSteamTexture() {
  const S = 128, c = document.createElement('canvas'); c.width = c.height = S;
  const x = c.getContext('2d');
  let seed = 12345; const r = () => { seed = (seed * 1664525 + 1013904223) >>> 0; return seed / 4294967296; };
  x.clearRect(0, 0, S, S);
  for (let k = 0; k < 46; k++) {
    const a = r() * Math.PI * 2, d = Math.sqrt(r()) * 34, px = 64 + Math.cos(a) * d, py = 64 + Math.sin(a) * d, rad = 14 + r() * 22;
    const g = x.createRadialGradient(px, py, 0, px, py, rad);
    g.addColorStop(0, 'rgba(255,255,255,0.20)'); g.addColorStop(0.6, 'rgba(255,255,255,0.07)'); g.addColorStop(1, 'rgba(255,255,255,0)');
    x.fillStyle = g; x.fillRect(0, 0, S, S);
  }
  // fade to zero at the sprite border
  const m = x.createRadialGradient(64, 64, 20, 64, 64, 64);
  m.addColorStop(0, 'rgba(0,0,0,1)'); m.addColorStop(1, 'rgba(0,0,0,0)');
  x.globalCompositeOperation = 'destination-in'; x.fillStyle = m; x.fillRect(0, 0, S, S);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t;
}

/**
 * Rising, expanding steam puffs (camera-facing quads). Per vertex: position = vent, aCorner = (size, ox, oy), aSt = (phase, speed, riseHeight),
 * aLit = baked irradiance at the vent (tints the steam with the lamps / neon around it). Drawn on LAYER.LATE.
 */
export function makeSteamMaterial(tex) {
  const m = new THREE.MeshBasicMaterial({ map: tex, vertexColors: true, transparent: true, depthWrite: false, fog: true });
  m.onBeforeCompile = (sh) => {
    sh.uniforms.uTime = G.uTime;
    sh.vertexShader = sh.vertexShader
      .replace('#include <common>', '#include <common>\nattribute vec3 aCorner; attribute vec3 aSt; attribute vec3 aLit; uniform float uTime; varying float vStA; varying vec3 vStL;')
      .replace('#include <project_vertex>', `
        float stT = fract(uTime * aSt.y + aSt.x);
        vec3 stP = transformed; stP.y += stT * aSt.z; stP.xz += vec2(sin(stT * 5.0 + aSt.x * 40.0), cos(stT * 4.0 + aSt.x * 23.0)) * stT * 0.5;
        vec4 mvPosition = modelViewMatrix * vec4(stP, 1.0);
        mvPosition.xy += aCorner.yz * aCorner.x * (0.35 + 1.6 * stT);
        gl_Position = projectionMatrix * mvPosition;
        vStA = (1.0 - stT) * (1.0 - stT) * smoothstep(0.0, 0.12, stT);
        vStL = aLit;`);
    sh.fragmentShader = sh.fragmentShader
      .replace('#include <common>', '#include <common>\nvarying float vStA; varying vec3 vStL;')
      .replace('#include <map_fragment>', `
        float stD = texture2D(map, vMapUv).a;
        diffuseColor = vec4(clamp(vec3(.8, .86, 1.) * (.05 + vStL * .22), 0., 1.2), stD * vStA * .85);`);
  };
  m.customProgramCacheKey = () => 'world_steam_v1';
  return m;
}
