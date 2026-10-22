// Building facade material: procedural window grids (per-room lit pattern, blinds, interior fakery, LED bands, shopfronts) on top of a
// Poly Haven wall set. One shader, styles selected per vertex through `aFac` / `aFac2`.
//   aFac  = (style, seed 0..1, floorHeight m, bayWidth m)
//   aFac2 = (baseY m (floor 0 starts here), litFraction, hue 0..1, podiumHeight m)
// Styles: 0 glass curtain wall, 1 punched concrete, 2 brutalist slits, 3 industrial, 4 tenement, 5 LED tower, 6 shopfront band
import * as THREE from 'three';
import { patchLit } from './litpatch.js';

const FAC_FRAG_PARS = /* glsl */`
uniform sampler2D tWall;
varying vec4 vFac, vFac2;
float fcGlass; float fcRough; float fcMetal; vec2 gW = vec2(.01);
float aaBox(vec2 f, vec2 lo, vec2 hi) {
  vec2 w = max(gW, vec2(1e-4));
  vec2 a = clamp((f - lo) / w + .5, 0., 1.) * clamp((hi - f) / w + .5, 0., 1.);
  return a.x * a.y;
}
vec3 hue2rgb(float h) { return clamp(abs(mod(h * 6. + vec3(0., 4., 2.), 6.) - 3.) - 1., 0., 1.); }
vec3 windowLight(vec2 id, float seed, float hue, float litFrac, float t, out float lit) {
  float h1 = wHash12(id + seed * 37.0), rowH = wHash12(vec2(id.y, seed * 91.0)), colH = wHash12(vec2(id.x, seed * 53.0));
  lit = step(h1, litFrac * (.35 + 1.1 * rowH * (.6 + .8 * colH)));
  float kind = wHash12(id * 1.37 + seed * 11.0);
  vec3 warm = vec3(1.0, .68, .38), cool = vec3(.62, .78, 1.0), tv = vec3(.35, .5, 1.0), pink = vec3(1.0, .35, .7);
  vec3 c = kind < .5 ? warm : kind < .8 ? cool : kind < .93 ? tv * (.7 + .3 * sin(t * 7. + h1 * 40.)) : pink;
  c = mix(c, c * hue2rgb(hue) * 1.4, .25);
  return c * mix(.25, 1.5, wHash12(id * 2.1 + seed) * wHash12(id * 3.7 + seed));
}
// fake room interior in window-local coordinates wf (0..1): ceiling light, back wall gradient, furniture silhouette, curtains
vec3 interiorFx(vec2 wf, vec2 id, float seed, float kindv) {
  float h = wHash12(id * 3.3 + seed * 19.);
  float ceilL = smoothstep(.8, .88, wf.y) * (1. - smoothstep(.95, 1., wf.y)) * step(.2, wf.x) * step(wf.x, .8) * step(.35, h);
  float back = .45 + .55 * (1. - wf.y * .8);
  float desk = step(wf.y, .2 + .12 * fract(h * 7.)) * step(.15 + .2 * fract(h * 3.), wf.x) * step(wf.x, .55 + .4 * fract(h * 5.));
  float curtain = step(.8, fract(h * 11.)) * (smoothstep(.0, .12, wf.x) * (1. - smoothstep(.12, .3, wf.x)) + smoothstep(.7, .88, wf.x) * (1. - smoothstep(.88, 1., wf.x)));
  float blind = step(.7, fract(h * 17.)) * step(.35, wf.y) * (.4 + .6 * step(.5, fract(wf.y * 14.)));
  return vec3(back * (1. - .75 * desk) * (1. - .55 * curtain) * (1. - .5 * blind) + ceilL * 1.6);
}
`;

const FAC_MAP = /* glsl */`
{
  float style = vFac.x, seed = vFac.y, floorH = vFac.z, bayW = vFac.w;
  float y0 = vFac2.x, litFrac = vFac2.y, hue = vFac2.z, podH = vFac2.w;
  vec2 muv = vMUv; float y = vWPos.y;
  vec3 tint = vColor.rgb * vColor.a;              // vertex tint (alpha = ambient occlusion)
  vec3 wallTex = texture2D(tWall, muv / 3.5).rgb;
  float mv = wNoise(vWPos.xz * .09 + y * .05) * .6 + wNoise(vWPos.xz * .31 - y * .17) * .4;
  vec3 wall = wallTex * tint * mix(.7, 1.25, mv);
  vec3 emit = vec3(0.); float glass = 0.; fcRough = -1.; fcMetal = 0.;
  float vertical = 1. - abs(normalize(vNw).y);
  if (vertical < .5) {  // roofs / floors: plain
    diffuseColor.rgb = wall * .6; fcRough = -1.;
  } else {
    // ---- shopfront band ----
    if (style > 5.5) {
      float bw = max(bayW, 3.);
      float cx = muv.x / bw; vec2 id = vec2(floor(cx), 0.); float fx = fract(cx);
      float fy = y / max(podH, 3.);
      vec2 f = vec2(fx, fy);
      gW = fwidth(vec2(cx, fy));
      float h = wHash12(id + seed * 13.);
      float closed = step(.8, h);
      float inset = .05;
      float winM = aaBox(f, vec2(inset + .02, .06), vec2(1. - inset - .02, .70));
      // 2-3 panes with dark mullions
      float panes = h < .4 ? 2. : 3.;
      float pf = fract((fx - inset) / (1. - 2. * inset) * panes);
      float pfw = gW.x / (1. - 2. * inset) * panes; gW = vec2(pfw, .5); float mull = aaBox(vec2(pf, .5), vec2(.04, 0.), vec2(.96, 1.)); gW = fwidth(vec2(cx, fy));
      float inY = clamp((fy - .06) / .64, 0., 1.);
      vec3 shopC = mix(vec3(1., .68, .36), mix(vec3(.65, .85, 1.), vec3(1., .5, .75), step(.9, wHash12(id + 6. + seed))), step(.55, wHash12(id + 5. + seed)));
      vec3 inside = interiorFx(vec2(clamp((fx - inset) / (1. - 2. * inset), 0., 1.), inY), id, seed, 0.);
      {   // shelves with goods, a ceiling light bar and a counter silhouette
        vec2 gq = vec2((fx - inset) / (1. - 2. * inset) * 9., inY * 6.);
        float shelfLine = smoothstep(.0, .08, fract(gq.y)) * (1. - smoothstep(.86, .96, fract(gq.y)));
        vec3 goods = hue2rgb(wHash12(floor(gq) + id * 3.1 + seed * 7.)) * .55 + .45;
        float hasGoods = step(.35, wHash12(id + 31. + seed)) * step(.3, wHash12(floor(gq) + 5.));
        inside *= mix(vec3(1.), goods * (.55 + .6 * shelfLine), .7 * hasGoods);
        inside *= .6 + .4 * smoothstep(.0, .35, inY);
      }
      emit = shopC * inside * winM * mull * (1. - closed) * mix(.14, .55, wHash12(id + 9.)) * (.55 + .7 * (1. - inY));
      glass = winM * mull * (1. - closed);
      float shut = aaBox(f, vec2(inset, 0.), vec2(1. - inset, .74)) * closed;
      float slats = .55 + .45 * step(.5, fract(y * 7.));
      wall = mix(wall * .75, vec3(.06, .065, .08) * slats, shut);
      emit += vec3(1., .35, .1) * .12 * shut * step(.9, wHash12(id + 2.));
      wall *= mix(1., .3, aaBox(f, vec2(.43, 0.), vec2(.57, .6)) * (1. - closed));
      fcRough = mix(.6, .06, glass);
    } else {
      // ---- floors grid ----
      vec2 c = vec2(muv.x / bayW, (y - y0) / floorH);
      vec2 id = floor(c), f = fract(c);
      vec2 fw = max(fwidth(c), vec2(1e-4)); gW = fw;
      float lit;
      vec3 wl = windowLight(id, seed, hue, litFrac, uTime, lit);
      if (style < .5) {                 // glass curtain wall: 2 panes per bay with thin mullions
        vec2 lo = vec2(.02, .1), hi = vec2(.98, .9);
        float g = aaBox(f, lo, hi);
        vec2 wf = (f - lo) / (hi - lo);
        gW = vec2(fw.x * 2. / (hi.x - lo.x), .5); float pane = aaBox(vec2(fract(wf.x * 2.), .5), vec2(.03, 0.), vec2(.97, 1.)); gW = fw;
        g *= pane;
        vec3 inside = interiorFx(wf, id, seed, 0.);
        emit = lit * g * wl * inside;
        glass = g;
        wall = mix(wall * .25 * vec3(.8, .9, 1.), vec3(.04, .05, .07), g);
        wall += vec3(.05, .06, .08) * (1. - g) * mv;
        fcMetal = (1. - g) * .6; fcRough = mix(.3, .05, g);
        float band = step(abs(id.y - 7. * floor(id.y / 7.)), .5) * aaBox(f, vec2(-1., .02), vec2(2., .1));
        float pulse = .6 + .4 * sin(uTime * 1.7 + id.x * .4 + seed * 20.);
        emit += band * hue2rgb(hue) * (litFrac > .12 ? 2.2 : 0.) * pulse;
      } else if (style < 1.5) {         // punched concrete with balcony slabs
        vec2 lo = vec2(.16, .22), hi = vec2(.84, .86);
        float g = aaBox(f, lo, hi);
        vec2 wf = (f - lo) / (hi - lo);
        gW = vec2(fw.x * 2. / (hi.x - lo.x), .5); float pane = aaBox(vec2(fract(wf.x * 2.), .5), vec2(.04, 0.), vec2(.96, 1.)); gW = fw;
        g *= mix(1., pane, step(.4, wHash12(id + seed * 4.)));
        vec3 inside = interiorFx(wf, id, seed, 1.);
        emit = lit * g * wl * inside; glass = g;
        wall *= 1. - .4 * aaBox(f, vec2(.1, .16), vec2(.9, .92)) * (1. - g);          // reveal
        float slab = aaBox(f, vec2(-1., -.01), vec2(2., .09));
        wall *= 1. - .3 * slab; wall += vec3(.02) * slab;
        fcRough = mix(-1., .08, g);
      } else if (style < 2.5) {         // brutalist slits
        vec2 lo = vec2(.4, .1), hi = vec2(.6, .9);
        float g = aaBox(f, lo, hi);
        vec2 wf = (f - lo) / (hi - lo);
        emit = lit * g * wl * interiorFx(wf, id, seed, 0.) * .8; glass = g; wall *= .8; fcRough = mix(-1., .08, g);
      } else if (style < 3.5) {         // industrial: strip windows high up
        vec2 lo = vec2(.06, .62), hi = vec2(.94, .86);
        float g = aaBox(f, lo, hi) * step(.5, floorH - 2.);
        vec2 wf = (f - lo) / (hi - lo);
        gW = vec2(fw.x * 6. / (hi.x - lo.x), .5); float pane = aaBox(vec2(fract(wf.x * 6.), .5), vec2(.04, 0.), vec2(.96, 1.)); gW = fw;
        g *= pane;
        emit = lit * g * wl * .6; glass = g; fcRough = mix(-1., .12, g);
      } else if (style < 4.5) {         // tenement: small windows with grilles
        vec2 lo = vec2(.2, .3), hi = vec2(.8, .8);
        float g = aaBox(f, lo, hi);
        vec2 wf = (f - lo) / (hi - lo);
        float bars = max(step(.85, fract(wf.x * 5.)), step(.85, fract(wf.y * 3.)));
        vec3 inside = interiorFx(wf, id, seed, 2.);
        emit = lit * g * wl * inside * (1. - .8 * bars * step(.35, wHash12(id + 3.)));
        glass = g * (1. - bars * .6); wall *= 1. - .35 * aaBox(f, vec2(.12, .22), vec2(.88, .88)) * (1. - g);
        // wet stains below windows
        wall *= 1. - .25 * smoothstep(.3, 0., f.y) * step(.5, wHash12(id + 8.)) * aaBox(f, vec2(.2, -.2), vec2(.8, .3));
        fcRough = mix(-1., .1, glass);
      } else {                          // LED tower: animated colour field
        vec2 q = vec2(muv.x * .6, y * .6);
        float t = uTime * .5;
        float wv = sin(q.x * .8 + t * 2. + sin(q.y * .4 + t)) * .5 + .5;
        gW = fwidth(vec2(muv.x, y) * 1.2); float pix = aaBox(fract(vec2(muv.x, y) * 1.2), vec2(.1), vec2(.9));
        vec3 ledc = mix(hue2rgb(hue), hue2rgb(hue + .35), wv);
        emit = ledc * pix * (.25 + .8 * smoothstep(.3, 1., wv)) * (.5 + .5 * step(.3, wHash12(floor(vec2(muv.x * .35 + t, y * .35)))));
        wall = vec3(.02); glass = pix * .5; fcRough = .2;
      }
    }
    diffuseColor.rgb = wall;
  }
  totalEmissiveRadiance += emit;
  fcGlass = glass;
}
`;

export function makeFacade(tex, { set, key, scale = 3.5 }) {
  const s = tex[set];
  const m = new THREE.MeshStandardMaterial({
    vertexColors: true, roughness: 0.9, metalness: 0.0,
    normalMap: (() => { const c = s.normalMap.clone(); c.repeat.set(1 / scale, 1 / scale); c.needsUpdate = true; return c; })(),
    roughnessMap: (() => { const c = s.armMap.clone(); c.repeat.set(1 / scale, 1 / scale); c.needsUpdate = true; return c; })(),
  });
  patchLit(m, {
    key: 'facade_' + key,
    uniforms: { tWall: { value: s.map } },
    vertPars: 'attribute vec4 aFac, aFac2; varying vec4 vFac, vFac2;',
    vertMain: 'vFac = aFac; vFac2 = aFac2;',
    fragPars: FAC_FRAG_PARS,
    repl: {
      color_fragment: '',
      map_fragment: FAC_MAP,
      roughnessmap_fragment: '#include <roughnessmap_fragment>\nif (fcRough >= 0.0) roughnessFactor = fcRough;',
      metalnessmap_fragment: 'float metalnessFactor = fcMetal;',
      normal_fragment_maps: '#include <normal_fragment_maps>\nnormal = normalize(mix(normal, nonPerturbedNormal, fcGlass));',
    },
  });
  return m;
}
