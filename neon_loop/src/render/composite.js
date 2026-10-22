// COMPOSITE + FINAL. Owner: R.
// composite: edge chromatic aberration (grows with speed) → + bloom + streaks → exposure + flash → tone map (AgX or
// ACES fitted) → teal/magenta split-tone grade → contrast/saturation → vignette → sRGB, luma in alpha.
// final: FXAA 3.11 (low quality only) or a light unsharp mask, then film grain + dither, straight to the canvas.
import * as THREE from 'three';
import { postMaterial, POST_GLSL } from './common.js';

const COMPOSITE_FRAG = /* glsl */`
${POST_GLSL}
uniform sampler2D tScene, tBloom, tStreak;
uniform float uBloom, uStreak, uExposure, uCA, uVig, uTeal, uMagenta, uContrast, uSat, uAspect;
uniform vec3 uStreakTint;
uniform vec4 uFlash;
uniform int uDebug;
varying vec2 vUv;

const mat3 LIN709_TO_2020 = mat3(vec3(0.6274, 0.0691, 0.0164), vec3(0.3293, 0.9195, 0.0880), vec3(0.0433, 0.0113, 0.8956));
const mat3 LIN2020_TO_709 = mat3(vec3(1.6605, -0.1246, -0.0182), vec3(-0.5876, 1.1329, -0.1006), vec3(-0.0728, -0.0083, 1.1187));
vec3 agxContrast(vec3 x) {
  vec3 x2 = x * x, x4 = x2 * x2;
  return 15.5 * x4 * x2 - 40.14 * x4 * x + 31.96 * x4 - 6.868 * x2 * x + 0.4298 * x2 + 0.1191 * x - 0.00232;
}
vec3 agx(vec3 c) {
  const mat3 inset = mat3(vec3(0.856627153315983, 0.137318972929847, 0.11189821299995), vec3(0.0951212405381588, 0.761241990602591, 0.0767994186031903), vec3(0.0482516061458583, 0.101439036467562, 0.811302368396859));
  const mat3 outset = mat3(vec3(1.1271005818144368, -0.1413297634984383, -0.14132976349843826), vec3(-0.11060664309660323, 1.157823702216272, -0.11060664309660294), vec3(-0.016493938717834573, -0.016493938717834257, 1.2519364065950405));
  c = inset * (LIN709_TO_2020 * c);
  c = max(c, 1e-10);
  c = clamp((log2(c) + 12.47393) / 16.500, 0.0, 1.0);
  c = agxContrast(c);
  c = outset * c;
  c = pow(max(vec3(0.0), c), vec3(2.2));
  return clamp(LIN2020_TO_709 * c, 0.0, 1.0);
}
vec3 rrtOdt(vec3 v) { vec3 a = v * (v + 0.0245786) - 0.000090537; vec3 b = v * (0.983729 * v + 0.4329510) + 0.238081; return a / b; }
vec3 aces(vec3 c) {
  const mat3 m1 = mat3(0.59719, 0.07600, 0.02840, 0.35458, 0.90834, 0.13383, 0.04823, 0.01566, 0.83777);
  const mat3 m2 = mat3(1.60475, -0.10208, -0.00327, -0.53108, 1.10813, -0.07276, -0.07367, -0.00605, 1.07602);
  return clamp(m2 * rrtOdt(m1 * c), 0.0, 1.0);
}

void main() {
  vec2 uv = vUv;
  vec2 cc = uv - 0.5;
  vec2 ccs = cc * vec2(uAspect, 1.0);
  float r2 = dot(ccs, ccs);
  vec2 ca = cc * r2 * uCA;
  vec3 col = vec3(texture(tScene, uv - ca).r, texture(tScene, uv).g, texture(tScene, uv + ca).b);
  vec3 bloom = texture(tBloom, uv).rgb;
  col += bloom * uBloom;
  col += texture(tStreak, uv).rgb * uStreakTint * uStreak;
  col *= uExposure;
  col += uFlash.rgb * uFlash.a;
  col = max(col, vec3(0.0));

#if TONEMAP == 1
  vec3 m = aces(col);
#else
  vec3 m = agx(col);
#endif
  float l = dot(m, NL_LUMA709);
  // split-tone: teal in the shadows, magenta in the highlights, a breath of lift so the haze never goes pure black
  float sh = 1.0 - smoothstep(0.0, 0.38, l), hi = smoothstep(0.3, 0.95, l);
  m *= mix(vec3(1.0), vec3(0.80, 1.0, 1.09), uTeal * sh);
  m *= mix(vec3(1.0), vec3(1.07, 0.96, 1.08), uMagenta * hi);
  m += vec3(0.0035, 0.0095, 0.0135) * uTeal * (1.0 - smoothstep(0.0, 0.12, l));
  m = mix(vec3(dot(m, NL_LUMA709)), m, uSat);
  m = clamp(m, 0.0, 1.0);
  m = mix(m, m * m * (3.0 - 2.0 * m), uContrast);
  float vig = smoothstep(0.30, 1.15, length(ccs * vec2(0.95, 1.18)));
  m *= 1.0 - uVig * vig * vig;

  if (uDebug == 1) m = clamp(bloom * uBloom * uExposure * 3.0, 0.0, 1.0);
  else if (uDebug == 2) m = clamp(texture(tScene, uv).aaa, 0.0, 1.0);
  else if (uDebug == 3) m = clamp(texture(tStreak, uv).rgb * 0.5, 0.0, 1.0);
  vec3 s = nl_toSRGB(m);
  gl_FragColor = vec4(s, dot(s, vec3(0.299, 0.587, 0.114)));
}
`;

export function createCompositeMaterial(tonemap = 0) {
  return postMaterial({
    name: 'composite', fragmentShader: COMPOSITE_FRAG, defines: { TONEMAP: tonemap },
    uniforms: {
      tScene: { value: null }, tBloom: { value: null }, tStreak: { value: null },
      uBloom: { value: 0.1 }, uStreak: { value: 0 }, uExposure: { value: 1 }, uCA: { value: 0.004 }, uVig: { value: 0.35 },
      uTeal: { value: 0.5 }, uMagenta: { value: 0.35 }, uContrast: { value: 0.25 }, uSat: { value: 1.05 }, uAspect: { value: 16 / 9 },
      uStreakTint: { value: new THREE.Vector3(0.45, 0.7, 1.0) },
      uFlash: { value: new THREE.Vector4() }, uDebug: { value: 0 },
    },
  });
}

const FINAL_FRAG = /* glsl */`
${POST_GLSL}
uniform sampler2D tLDR;
uniform vec2 uTexel;
uniform float uSharpen, uGrain, uFrame, uFade;
varying vec2 vUv;

#define L(o) textureLodOffset(tLDR, uv, 0.0, o).a
float lumaAt(vec2 p) { return textureLod(tLDR, p, 0.0).a; }

void main() {
  vec2 uv = vUv;
  vec4 M = textureLod(tLDR, uv, 0.0);
  float lumaM = M.a;
  float lumaS = L(ivec2(0, 1)), lumaE = L(ivec2(1, 0)), lumaN = L(ivec2(0, -1)), lumaW = L(ivec2(-1, 0));
  float rangeMax = max(max(lumaN, lumaW), max(lumaE, max(lumaS, lumaM)));
  float rangeMin = min(min(lumaN, lumaW), min(lumaE, min(lumaS, lumaM)));
  float range = rangeMax - rangeMin;
  vec3 rgb;
#if FXAA
  if (range < max(0.0312, rangeMax * 0.125)) {
#else
  if (true) {
#endif
    vec3 avg = (textureLodOffset(tLDR, uv, 0.0, ivec2(0, 1)).rgb + textureLodOffset(tLDR, uv, 0.0, ivec2(1, 0)).rgb
              + textureLodOffset(tLDR, uv, 0.0, ivec2(0, -1)).rgb + textureLodOffset(tLDR, uv, 0.0, ivec2(-1, 0)).rgb) * 0.25;
    rgb = M.rgb + (M.rgb - avg) * uSharpen;
  } else {
    float lumaNW = L(ivec2(-1, -1)), lumaSE = L(ivec2(1, 1)), lumaNE = L(ivec2(1, -1)), lumaSW = L(ivec2(-1, 1));
    float lumaNS = lumaN + lumaS, lumaWE = lumaW + lumaE;
    float subpixRcpRange = 1.0 / range;
    float subpixNSWE = lumaNS + lumaWE;
    float edgeHorz1 = -2.0 * lumaM + lumaNS, edgeVert1 = -2.0 * lumaM + lumaWE;
    float lumaNESE = lumaNE + lumaSE, lumaNWNE = lumaNW + lumaNE;
    float edgeHorz2 = -2.0 * lumaE + lumaNESE, edgeVert2 = -2.0 * lumaN + lumaNWNE;
    float lumaNWSW = lumaNW + lumaSW, lumaSWSE = lumaSW + lumaSE;
    float edgeHorz4 = abs(edgeHorz1) * 2.0 + abs(edgeHorz2), edgeVert4 = abs(edgeVert1) * 2.0 + abs(edgeVert2);
    float edgeHorz3 = -2.0 * lumaW + lumaNWSW, edgeVert3 = -2.0 * lumaS + lumaSWSE;
    float edgeHorz = abs(edgeHorz3) + edgeHorz4, edgeVert = abs(edgeVert3) + edgeVert4;
    float subpixNWSWNESE = lumaNWSW + lumaNESE;
    float lengthSign = uTexel.x;
    bool horzSpan = edgeHorz >= edgeVert;
    float subpixA = subpixNSWE * 2.0 + subpixNWSWNESE;
    if (!horzSpan) { lumaN = lumaW; lumaS = lumaE; } else lengthSign = uTexel.y;
    float subpixB = subpixA * (1.0 / 12.0) - lumaM;
    float gradientN = lumaN - lumaM, gradientS = lumaS - lumaM;
    float lumaNN = lumaN + lumaM, lumaSS = lumaS + lumaM;
    bool pairN = abs(gradientN) >= abs(gradientS);
    float gradient = max(abs(gradientN), abs(gradientS));
    if (pairN) lengthSign = -lengthSign;
    float subpixC = clamp(abs(subpixB) * subpixRcpRange, 0.0, 1.0);
    vec2 posB = uv;
    vec2 offNP = horzSpan ? vec2(uTexel.x, 0.0) : vec2(0.0, uTexel.y);
    if (!horzSpan) posB.x += lengthSign * 0.5; else posB.y += lengthSign * 0.5;
    vec2 posN = posB - offNP, posP = posB + offNP;
    float subpixD = -2.0 * subpixC + 3.0;
    float lumaEndN = lumaAt(posN), lumaEndP = lumaAt(posP);
    float subpixE = subpixC * subpixC;
    if (!pairN) lumaNN = lumaSS;
    float gradientScaled = gradient * 0.25;
    float lumaMM = lumaM - lumaNN * 0.5;
    float subpixF = subpixD * subpixE;
    bool lumaMLTZero = lumaMM < 0.0;
    lumaEndN -= lumaNN * 0.5; lumaEndP -= lumaNN * 0.5;
    bool doneN = abs(lumaEndN) >= gradientScaled, doneP = abs(lumaEndP) >= gradientScaled;
    if (!doneN) posN -= offNP;
    if (!doneP) posP += offNP;
    const float STEPS[8] = float[8](1.0, 1.5, 1.5, 1.5, 2.0, 2.0, 4.0, 4.0);
    for (int i = 0; i < 8; i++) {
      if (doneN && doneP) break;
      if (!doneN) lumaEndN = lumaAt(posN) - lumaNN * 0.5;
      if (!doneP) lumaEndP = lumaAt(posP) - lumaNN * 0.5;
      doneN = abs(lumaEndN) >= gradientScaled; doneP = abs(lumaEndP) >= gradientScaled;
      if (!doneN) posN -= offNP * STEPS[i];
      if (!doneP) posP += offNP * STEPS[i];
    }
    float dstN = horzSpan ? uv.x - posN.x : uv.y - posN.y;
    float dstP = horzSpan ? posP.x - uv.x : posP.y - uv.y;
    bool goodSpanN = (lumaEndN < 0.0) != lumaMLTZero, goodSpanP = (lumaEndP < 0.0) != lumaMLTZero;
    float spanLengthRcp = 1.0 / (dstP + dstN);
    bool directionN = dstN < dstP;
    float dst = min(dstN, dstP);
    bool goodSpan = directionN ? goodSpanN : goodSpanP;
    float subpixG = subpixF * subpixF;
    float pixelOffset = dst * -spanLengthRcp + 0.5;
    float subpixH = subpixG * 0.75;
    float pixelOffsetSubpix = max(goodSpan ? pixelOffset : 0.0, subpixH);
    vec2 posM = uv;
    if (!horzSpan) posM.x += pixelOffsetSubpix * lengthSign; else posM.y += pixelOffsetSubpix * lengthSign;
    rgb = textureLod(tLDR, posM, 0.0).rgb;
  }
  // film grain (stronger in the shadows) + dither, after AA
  vec2 fc = gl_FragCoord.xy;
  float fr = mod(uFrame, 1024.0);
  float l = dot(rgb, vec3(0.299, 0.587, 0.114));
  float g = nl_hash12(fc + fract(fr * 0.618034) * 311.0) + nl_hash12(fc.yx * 1.7 + fr * 0.37) - 1.0;
  rgb += g * uGrain * (1.0 - 0.55 * clamp(l * 1.6, 0.0, 1.0));
  rgb += (nl_hash12(fc.yx * 1.3 + fr * 0.713) - 0.5) / 255.0;
  rgb *= 1.0 - uFade;
  gl_FragColor = vec4(clamp(rgb, 0.0, 1.0), 1.0);
}
`;

export function createFinalMaterial(fxaa = true) {
  return postMaterial({
    name: 'final', fragmentShader: FINAL_FRAG, defines: { FXAA: fxaa ? 1 : 0 },
    uniforms: {
      tLDR: { value: null }, uTexel: { value: new THREE.Vector2() }, uSharpen: { value: 0.3 }, uGrain: { value: 0.03 },
      uFrame: { value: 0 }, uFade: { value: 0 },
    },
  });
}
