// Shared GLSL snippets for the world materials.
export const NOISE_GLSL = /* glsl */`
float wHash12(vec2 p){ vec3 p3 = fract(vec3(p.xyx) * .1031); p3 += dot(p3, p3.yzx + 33.33); return fract((p3.x + p3.y) * p3.z); }
vec2 wHash22(vec2 p){ vec3 p3 = fract(vec3(p.xyx) * vec3(.1031, .1030, .0973)); p3 += dot(p3, p3.yzx + 33.33); return fract((p3.xx + p3.yz) * p3.zy); }
float wNoise(vec2 p){ vec2 i = floor(p), f = fract(p); f = f*f*(3.0-2.0*f);
  return mix(mix(wHash12(i), wHash12(i+vec2(1,0)), f.x), mix(wHash12(i+vec2(0,1)), wHash12(i+vec2(1,1)), f.x), f.y); }
float wFbm(vec2 p){ float a = .5, s = 0.; for (int i = 0; i < 4; i++) { s += a * wNoise(p); p = p * 2.03 + vec2(17.1, 9.2); a *= .5; } return s; }
mat2 wRot(float a){ float c = cos(a), s = sin(a); return mat2(c, -s, s, c); }
`;

// Baked static light (attribute aLit, irradiance) + car headlights (G.uHead*) as extra direct light for custom materials.
export const LIT_VERT_PARS = /* glsl */`
attribute vec3 aLit;
varying vec3 vLit;
varying vec3 vWPos;
varying vec3 vNw;
`;
export const LIT_VERT_MAIN = /* glsl */`
vLit = aLit;
vWPos = (modelMatrix * vec4(position, 1.0)).xyz;
vNw = normalize(mat3(modelMatrix) * normal);
`;
export const LIT_FRAG_PARS = /* glsl */`
varying vec3 vLit;
varying vec3 vWPos;
varying vec3 vNw;
uniform float uHeadK;
uniform float uBakeK;
uniform float uTime, uWet, uRain;
`;
// Adds baked light + headlights. Needs: material, geometryPosition/Normal/ViewDir (lights_fragment_begin has run).
export const HEADLIGHTS_FRAG = /* glsl */`
{
  for (int i = 0; i < MAX_HEADLIGHTS; i++) {
    if (i >= uHeadCount) break;
    vec3 lp = (viewMatrix * vec4(uHeadPos[i], 1.0)).xyz;
    vec3 ld = normalize(mat3(viewMatrix) * uHeadDir[i]);
    vec3 Lv = lp - geometryPosition; float d2 = max(dot(Lv, Lv), 0.25); vec3 l = Lv * inversesqrt(d2);
    float cone = smoothstep(cos(0.30), cos(0.09), dot(-l, ld));        // same cone as the near cars' spots (car/lightpool.js)
    float rng = pow(clamp(1.0 - d2 / 8100.0, 0.0, 1.0), 2.0);
    float farK = smoothstep(30.0, 60.0, distance(uHeadPos[i], cameraPosition));   // the nearest cars have real world-pass spot lights (C's light pool): don't light twice
    float k = cone * rng * farK;
    if (k <= 0.0) continue;                                       // out of the beam / range: skip the BRDF
    IncidentLight dl; dl.direction = l;
    dl.color = uHeadColor[i] * (k * 0.025 * inversesqrt(d2) * uHeadK);  // decay 1, as the near cars' spots (car/lightpool.js)
    RE_Direct(dl, geometryPosition, geometryNormal, geometryViewDir, geometryClearcoatNormal, material, reflectedLight);
  }
}
`;
export const BAKE_FRAG = /* glsl */`
vec3 bkE = vLit * uBakeK; bkE /= 1.0 + max(bkE - 4.0, vec3(0.0)) * 0.35;      // soft knee: surfaces right next to a lamp must not clip to white
reflectedLight.directDiffuse += bkE * RECIPROCAL_PI * material.diffuseColor;
`;
