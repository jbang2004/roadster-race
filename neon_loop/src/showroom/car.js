// The showroom car: wraps src/car's createCarVisual (hi LOD forced), drives it with a synthetic car state (wing, lamps, wheels, steering,
// thrusters) and re-tints the existing materials for the factory paints. Nothing here edits the car area's files.
import * as THREE from 'three';
import { loadCarAssets, createCarVisual, LIVERIES } from '../car/index.js';
import { liveryAtlas } from '../car/liveries.js';
import { PAINTS } from './presets.js';
import { RECT_GLSL, MAXL } from './cyclo.js';

const clamp = THREE.MathUtils.clamp;
const lin = (h) => new THREE.Color(h);

export async function createShowroomCar(app, scene) {
  const assets = await loadCarAssets(app);
  const visual = createCarVisual(app, { livery: 0, isPlayer: false, envMap: null, forceLod: 0, poolLights: false });
  scene.add(visual.object);
  const cs = visual.object.getObjectByName('ContactShadow'); if (cs) cs.visible = false;      // the showroom has its own baked contact shadow
  visual.object.traverse(o => { if (o.isMesh) o.frustumCulled = true; });

  // ---- diffuse light: three's PMREM 'irradiance' is a very wide blur, so a big softbox overhead leaks into the vertical flanks and the whole body goes flat white.
  // The paint gets the exact diffuse light instead: the studio's rectangular lights integrated analytically per pixel (Arvo's polygon formula, the same one that
  // lights the cyclorama), plus the rest of the room (floor pool, walls: smooth, so 9 spherical-harmonic coefficients are enough). Hood bright, flanks falling off.
  const shU = { value: Array.from({ length: 9 }, () => new THREE.Vector3()) };
  const v3s = () => ({ value: Array.from({ length: MAXL }, () => new THREE.Vector3()) });
  const archV = Array.from({ length: 4 }, () => new THREE.Vector4(0, -10, 0, 0.39));       // per wheel: hub xyz + tyre radius, read from the model's tyre meshes below
  const lightU = { uArch: { value: archV }, uArchP: { value: new THREE.Vector2(1, 0.12) }, uDiffUp: { value: 0 }, uSHRot: { value: new THREE.Vector2(1, 0) }, uNL: { value: 0 }, uLC: v3s(), uLX: v3s(), uLY: v3s(), uLN: v3s(), uLL: v3s() };
  const IRR_GLSL = RECT_GLSL.replace(/RECT_SIGN/g, '-1.0') + `
uniform vec3 uSH[9]; uniform float uDiffUp; uniform vec2 uSHRot;
vec3 srIrradiance(vec3 n) {
  const float c1 = 0.429043, c2 = 0.511664, c3 = 0.743125, c4 = 0.886227, c5 = 0.247708;
  return max(c1 * uSH[8] * (n.x * n.x - n.y * n.y) + c3 * uSH[6] * n.z * n.z + c4 * uSH[0] - c5 * uSH[6]
       + 2.0 * c1 * (uSH[4] * n.x * n.y + uSH[7] * n.x * n.z + uSH[5] * n.y * n.z) + 2.0 * c2 * (uSH[3] * n.x + uSH[1] * n.y + uSH[2] * n.z), vec3(0.0));
}
// Wheel-arch occlusion. The studio has no light that can reach inside a wheel house (the soft box overhead and the room's SH know nothing of the fender), so the tyre top, the
// visible tread, the arch lip and the well walls would catch it. Per wheel, from its hub (xyz), tyre radius (w) and half width (uArchP.y): a zone above the axle line inside
// the arch cylinder (the tyre: everything facing up; the body: only faces that look at the axle, plus the inboard wall), so lower sidewall, rim and brake stay as lit.
uniform vec4 uArch[4]; uniform vec2 uArchP;
float srArchAO( vec3 P, vec3 N, float tyre ) {
  float occ = 0.0;
  for ( int i = 0; i < 4; i ++ ) {
    vec4 a = uArch[ i ];
    vec3 d = P - a.xyz;
    float sd = a.x < 0.0 ? -1.0 : 1.0;
    float l = d.x * sd;                                   // lateral offset from the hub plane, + = outward
    float rho = max( length( d.yz ), 1e-3 );
    float el = d.y / rho;                                 // sin of the elevation above the axle line
    float R = a.w, hw = uArchP.y;
    vec3 rad = vec3( 0.0, d.y, d.z ) / rho;
    float nOut = N.x * sd;
    float o = 0.0;
    if ( tyre > 0.5 ) {
      float z = smoothstep( -0.12, 0.30, el ) * ( 1.0 - smoothstep( R + 0.05, R + 0.18, rho ) )
              * smoothstep( -hw - 0.12, -hw - 0.02, l ) * ( 1.0 - smoothstep( hw + 0.04, hw + 0.14, l ) );
      o = z * ( 1.0 - 0.06 * smoothstep( 0.6, 0.98, nOut ) );       // only the sidewall face that points straight out keeps a trace of light
    } else {
      float zr = smoothstep( 0.28, 0.36, rho ) * ( 1.0 - smoothstep( R + 0.07, R + 0.22, rho ) ) * smoothstep( -0.25, 0.12, el )
               * smoothstep( -hw - 0.55, -hw - 0.40, l ) * ( 1.0 - smoothstep( hw + 0.05, hw + 0.16, l ) );
      float inward = 1.0 - smoothstep( -0.35, 0.10, dot( N, rad ) );
      float wall = smoothstep( 0.30, 0.80, nOut ) * ( 1.0 - smoothstep( -hw - 0.06, -hw + 0.02, l ) ) * smoothstep( -hw - 0.55, -hw - 0.40, l ) * ( 1.0 - smoothstep( R + 0.12, R + 0.30, rho ) ) * smoothstep( -0.25, 0.12, el );
      o = max( zr * inward, wall );
    }
    occ = max( occ, o );
  }
  return max( 1.0 - occ * uArchP.x, 0.03 );
}`;
  for (const m of visual.materials) {
    if (!m.isMeshStandardMaterial || !m.onBeforeCompile) continue;
    const prev = m.onBeforeCompile;
    m.onBeforeCompile = function (shader, r) {
      prev.call(this, shader, r);
      shader.uniforms.uSH = shU; Object.assign(shader.uniforms, lightU);
      const key = this.customProgramCacheKey?.() ?? '';
      const arch = key.startsWith('car:tyre') ? 1 : /^car:(paint|plain|trim|carbon|nozzle)/.test(key) ? 2 : 0;      // rim, glass, lamps, decals: not occluded
      shader.fragmentShader = shader.fragmentShader
        .replace('#include <common>', '#include <common>\n' + IRR_GLSL)
        .replace('#include <opaque_fragment>', (arch ? `outgoingLight *= srAO;\n` : '') + '#include <opaque_fragment>')
        .replace('#include <lights_fragment_maps>', (arch ? `float srAO = srArchAO( cameraPosition + ( vec4( -vViewPosition, 0.0 ) * viewMatrix ).xyz, inverseTransformDirection( geometryNormal, viewMatrix ), ${arch === 1 ? '1.0' : '0.0'} );\n` : '') + `#include <lights_fragment_maps>
#if defined( RE_IndirectDiffuse ) && defined( USE_ENVMAP )
  {
    vec3 srN = inverseTransformDirection( geometryNormal, viewMatrix );
    vec3 srP = cameraPosition + ( vec4( -vViewPosition, 0.0 ) * viewMatrix ).xyz;
    vec3 srE = srIrradiance( vec3( uSHRot.x * srN.x - uSHRot.y * srN.z, srN.y, uSHRot.y * srN.x + uSHRot.x * srN.z ) );     // the room (sky) may be turned about Y with the camera: look the SH up in its own frame
    for ( int i = 0; i < MAXL; i ++ ) { if ( i >= uNL ) break; srE += rectE( srP, srN, i ); }
    srE *= mix( 1.0, smoothstep( 0.55, 0.97, srN.y ), uDiffUp );           // studio look: the body takes its diffuse light from above, the flanks stay dark
    iblIrradiance = srE * envMapIntensity;
  }
#endif`);
    };
    m.needsUpdate = true;
  }
  const glassMats = visual.materials.filter(m => m.customProgramCacheKey?.().startsWith('car:glass'));
  const tyreMats = visual.materials.filter(m => m.customProgramCacheKey?.().startsWith('car:tyre'));
  // every texture on the car at the sharpest anisotropic filtering (grazing-angle moire on the sills and the plate)
  { const maxA = app.renderer.capabilities.getMaxAnisotropy(), seen = new Set();
    for (const m of visual.materials) for (const k in m) { const t = m[k]; if (t && t.isTexture && !seen.has(t)) { seen.add(t); if (t.anisotropy < maxA) { t.anisotropy = maxA; t.needsUpdate = true; } } } }
  // Coincident shells in the GLB (24-bit depth is confirmed on every target, so this is the model, not precision): the Trim shell lies on the piano-black nose panel and the
  // brake bar lies on the tail bar. Push the shells that must stay behind back by a few depth units (about 0.04 mm at 9 m) instead of pulling the front ones forward:
  // a forward bias on the gloss black / lamps made them cover the tail strip in dashes.
  for (const m of visual.materials) if (m.customProgramCacheKey?.().startsWith('car:trim')) { m.polygonOffset = true; m.polygonOffsetFactor = 4; m.polygonOffsetUnits = 4; }
  for (const rec of visual.lods) { const m = rec.lamps.brake; if (m) { m.polygonOffset = true; m.polygonOffsetFactor = 4; m.polygonOffsetUnits = 4; } }
  for (const m of glassMats) { m.envMapIntensity = 0.8; m.emissive = new THREE.Color(0.019, 0.0142, 0.0108); m.specularColor = new THREE.Color(1.0, 0.92, 0.82); }      // the glass of the press photos shows only a dim reflection
  const setDiffUp = (v) => { lightU.uDiffUp.value = v; };
  const setArchAO = (k) => { lightU.uArchP.value.x = k; };
  // turn the whole environment (sky + rig) about Y by `a`: the cube maps through envMapRotation, the SH through uSHRot (the rectangular lights are moved by the studio)
  const rigMats = [...visual.materials, ...visual.lods.flatMap(rec => rec.blurs ?? [])];
  const setRig = (a) => { lightU.uSHRot.value.set(Math.cos(a), Math.sin(a)); for (const m of rigMats) if (m.envMapRotation) m.envMapRotation.y = a; };
  const setSH = (a) => { for (let i = 0; i < 9; i++) shU.value[i].set(a[3 * i], a[3 * i + 1], a[3 * i + 2]); };
  const setLights = (rects) => {
    const e = rects.filter(r => r.env);
    lightU.uNL.value = e.length;
    e.forEach((r, i) => { lightU.uLC.value[i].copy(r.c); lightU.uLX.value[i].copy(r.ax); lightU.uLY.value[i].copy(r.ay); lightU.uLN.value[i].copy(r.n); lightU.uLL.value[i].copy(r.L).multiplyScalar(r.kD ?? 1); });
  };

  // ---- synthetic car state (what the game's physics would hand to visual.sync)
  const mkWheel = () => ({ steer: 0, spin: 0, spinRate: 0, compression: 0, suspensionTravel: 0, grounded: true });
  const car = {
    position: new THREE.Vector3(), quaternion: new THREE.Quaternion(), speed: 0,
    wheels: [mkWheel(), mkWheel(), mkWheel(), mkWheel()], input: { steer: 0, throttle: 0, brake: 0 },
    lights: { head: true, brake: 0, reverse: false }, brakeTemp: 0, boost: { level: 0, gas: 1 },
  };
  const F = { wing: false, drl: true, tail: true, brake: false, steer: false, spin: false, jets: false, livery: false };
  const S = { drl: 1, tail: 1, brake: 0, steer: 0, steerT: 0, wingTimer: 0, jet: 0, jetPhase: 0, spin: 0, animating: false, t: 0 };
  let paintId = 'pearl';

  // ---- paint
  const paintMats = visual.materials.filter(m => m.customProgramCacheKey?.().startsWith('car:paint'));
  const decalMats = visual.materials.filter(m => m.customProgramCacheKey?.().startsWith('car:decal'));
  const U = visual.uniforms.paint;
  const raceAtlas = decalMats[0]?.map ?? null;
  // factory atlas: the race atlas with the door and hood artwork wiped, so only the rear plate stays
  let factoryAtlas = null;
  if (raceAtlas?.image) {
    const src = raceAtlas.image, c = document.createElement('canvas'); c.width = src.width; c.height = src.height;
    const g = c.getContext('2d'); g.drawImage(src, 0, 0);
    const s = c.width / 2048;
    g.clearRect(0, 0, 1024 * s, 1024 * s); g.clearRect(1024 * s, 0, 1024 * s, 512 * s);
    factoryAtlas = new THREE.CanvasTexture(c);
    factoryAtlas.colorSpace = THREE.SRGBColorSpace; factoryAtlas.flipY = false; factoryAtlas.anisotropy = raceAtlas.anisotropy;
    factoryAtlas.generateMipmaps = true; factoryAtlas.minFilter = THREE.LinearMipmapLinearFilter; factoryAtlas.needsUpdate = true;
  }
  const setDecals = () => {
    for (const m of decalMats) { m.map = F.livery ? raceAtlas : factoryAtlas; m.needsUpdate = true; }
  };

  function applyPaint(spec, accentOverride = null) {
    for (const m of paintMats) {
      m.color.copy(lin(spec.color)); m.metalness = spec.metalness; m.roughness = spec.roughness;
      m.clearcoat = 1; m.clearcoatRoughness = spec.coatRough;
    }
    U.uFlake.value = spec.flake; U.uFlakeColor.value.copy(lin(spec.flakeColor));
    U.uPearl.value.set(...(spec.pearl ?? [0, 0, 0, 0]));
    U.uPaintC.value.copy(lin(spec.wheel ?? 0x6a6d74));                // the wheel's aero panels: gunmetal, not the body colour
    const acc = lin(accentOverride ?? spec.accent);
    U.uAccent.value.copy(acc);
    for (const rec of visual.lods) {
      if (rec.mats.Caliper) rec.mats.Caliper.color.copy(acc);
      if (rec.mats.IntAccent) rec.mats.IntAccent.color.copy(acc);
      for (const b of rec.blurs) b.userData.U.uAcc.value.copy(acc);
    }
  }
  function setPaint(id) {
    paintId = id;
    const spec = PAINTS.find(p => p.id === id) ?? PAINTS[0];
    if (F.livery) { const L = LIVERIES[0]; applyPaint({ ...L.paint, color: L.paint.color, coatRough: L.paint.coatRough, flakeColor: L.paint.flakeColor, accent: L.rim.accent }, L.rim.accent); }
    else applyPaint(spec);
    api.changed = true;
  }
  function setFeature(name, on) {
    F[name] = on;
    if (name === 'livery') { setDecals(); setPaint(paintId); }
    if (name === 'wing') S.wingTimer = 3.2;
    if (name === 'steer' && !on) S.steerT = 0;
    api.changed = true;
  }

  // ---- per-frame
  function update(dt) {
    const t = S.t += dt;
    const kk = (rate) => 1 - Math.exp(-dt * rate);
    let anim = false;
    // wing: sync() stows below 13 m/s and deploys above 22 m/s with its own easing
    const speed = F.wing ? 30 : 0;
    if (S.wingTimer > 0) { S.wingTimer -= dt; anim = true; }
    // lamps
    const targ = { drl: F.drl ? 1 : 0, tail: F.tail ? 1 : 0, brake: F.brake ? 1 : 0 };
    for (const k of ['drl', 'tail', 'brake']) { const d = targ[k] - S[k]; S[k] += d * kk(9); if (Math.abs(targ[k] - S[k]) < 0.004) S[k] = targ[k]; else anim = true; }
    // steering sweeps left-right while on, otherwise eases to straight
    if (F.steer) { S.steerT = 0.36 * Math.sin(t * 0.9); S.steer += (S.steerT - S.steer) * kk(7); anim = true; }
    else { S.steer += (0 - S.steer) * kk(6); if (Math.abs(S.steer) < 4e-4) S.steer = 0; else anim = true; }
    // wheels
    const spinRate = F.spin ? 1.4 : 0;
    S.spin += (spinRate - S.spin) * kk(2.5); if (Math.abs(S.spin) < 1e-3 && !F.spin) S.spin = 0; else anim = true;
    // thrusters: pulses of cold gas while on
    if (F.jets) { S.jetPhase += dt; const p = S.jetPhase % 3.2; const target = p < 0.25 ? p / 0.25 : p < 1.9 ? 1 : p < 2.5 ? 1 - (p - 1.9) / 0.6 : 0; S.jet += (target - S.jet) * kk(14); anim = true; }
    else { S.jet += (0 - S.jet) * kk(10); if (S.jet < 0.004) S.jet = 0; else anim = true; S.jetPhase = 0; }

    car.speed = speed;
    car.lights.head = true; car.lights.brake = S.brake;
    for (let i = 0; i < 4; i++) {
      const w = car.wheels[i];
      w.steer = i < 2 ? S.steer : 0;
      w.spinRate = S.spin; w.spin += S.spin * dt;
    }
    car.input.steer = S.steer / 0.4;
    car.boost.level = S.jet; car.boost.gas = 1;
    visual.sync(car, dt);
    // lamp overrides (sync ties the strips to one headlight state; the showroom switches them individually)
    for (const rec of visual.lods) {
      if (!rec.root.visible) continue;
      const la = rec.lamps;
      la.head.emissiveIntensity = 0;
      la.drl.emissiveIntensity = 12 * S.drl;
      la.side.emissiveIntensity = 1.6 * Math.max(S.drl, S.tail);
      la.tail.emissiveIntensity = (S.tail * 2.2 + S.brake * 6);   // tone mapping bleaches a saturated red above ~2: keep it a deep red line like the press photos
      la.brake.emissiveIntensity = S.brake * 40 + S.tail * 0.25;
      la.reverse.emissiveIntensity = 0;
    }
    S.animating = anim;
    const ch = api.changed; api.changed = false;
    return anim || ch;
  }

  const api = {
    visual, car, assets, F, S, update, setPaint, setFeature, setSH, setDiffUp, setArchAO, arch: { hubs: archV, p: lightU.uArchP }, setRig, setLights, glassMats, tyreMats, get paintId() { return paintId; }, changed: true,
  };
  setDecals(); setPaint('pearl');
  update(0);
  // wheel-arch occlusion data, from the model itself (a rebuilt car just works): every Tyre_* mesh at rest gives its hub (box centre), radius and half width
  { const root = visual.lods[0].root; root.updateMatrixWorld(true);
    const box = new THREE.Box3(), c = new THREE.Vector3(), sz = new THREE.Vector3(); let n = 0, hw = 0;
    root.traverse(o => {
      if (!o.isMesh || !/^Tyre_/.test(o.name) || n >= 4) return;
      box.setFromObject(o); box.getCenter(c); box.getSize(sz);
      archV[n++].set(c.x, c.y, c.z, Math.max(sz.y, sz.z) / 2); hw = Math.max(hw, sz.x / 2);
    });
    if (n) { for (let i = n; i < 4; i++) archV[i].set(0, -10, 0, 0.39); lightU.uArchP.value.y = hw; } }
  return api;
}
