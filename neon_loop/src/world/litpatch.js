// Lit-material patching: baked static light (aLit), car headlights and shared uniforms.
import { G, HEADLIGHT_GLSL } from '../core/globals.js';
import { NOISE_GLSL, LIT_VERT_PARS, LIT_VERT_MAIN, LIT_FRAG_PARS, HEADLIGHTS_FRAG, BAKE_FRAG } from './glsl.js';

export const SHARED_UNIFORMS = () => ({
  uHeadK: { value: 1 }, uBakeK: { value: 1 },
  uHeadCount: G.uHeadCount, uHeadPos: G.uHeadPos, uHeadDir: G.uHeadDir, uHeadColor: G.uHeadColor,
  uWet: G.uWet, uRain: G.uRain, uTime: G.uTime,
});

/** Patch a MeshStandardMaterial with baked light + headlights (+ optional extra GLSL). */
export function patchLit(m, { key, vertPars = '', vertMain = '', fragPars = '', repl = {}, uniforms = {}, noBake = false } = {}) {
  const U = Object.assign(SHARED_UNIFORMS(), uniforms);
  m.userData.uniforms = U;
  m.onBeforeCompile = (sh) => {
    Object.assign(sh.uniforms, U);
    sh.vertexShader = sh.vertexShader
      .replace('#include <common>', `#include <common>\n${LIT_VERT_PARS}\nvarying vec2 vMUv;\n${vertPars}`)
      .replace('#include <begin_vertex>', `#include <begin_vertex>\n${LIT_VERT_MAIN}\nvMUv = uv;\n${vertMain}`);
    let f = sh.fragmentShader.replace('#include <common>', `#include <common>\n${LIT_FRAG_PARS}\nvarying vec2 vMUv;\n${HEADLIGHT_GLSL}\n${NOISE_GLSL}\n${fragPars}`);
    for (const [chunk, code] of Object.entries(repl)) f = f.replace(`#include <${chunk}>`, () => code);
    f = f.replace('#include <lights_fragment_end>', () => `${noBake ? '' : BAKE_FRAG}\n${HEADLIGHTS_FRAG}\n#include <lights_fragment_end>`);
    sh.fragmentShader = f;
  };
  m.customProgramCacheKey = () => 'world_lit_' + key;
  return m;
}

