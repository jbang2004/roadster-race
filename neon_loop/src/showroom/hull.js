// A signed distance field of the car (its visual hull from three orthographic silhouettes, 5 cm voxels, exact Euclidean distance
// transform). Used by the orbit camera so it never goes through the body, by the hotspots for occlusion, and uploaded as a 3D texture
// for the floor shader (contact-hardening reflections: the blur follows the distance to the reflected surface).
import * as THREE from 'three';

const H = 0.05;
const MIN = new THREE.Vector3(-2.1, 0, -3.3);
const DIM = [84, 52, 132];                // 4.2 x 2.6 x 6.6 m

// squared Euclidean distance transform, 1-D pass (Felzenszwalb & Huttenlocher)
function edt1d(f, n, d, v, z) {
  let k = 0; v[0] = 0; z[0] = -1e20; z[1] = 1e20;
  for (let q = 1; q < n; q++) {
    let s;
    for (;;) { const p = v[k]; s = ((f[q] + q * q) - (f[p] + p * p)) / (2 * q - 2 * p); if (s <= z[k] && k > 0) k--; else break; }
    if (s <= z[k]) { v[0] = q; z[0] = -1e20; z[1] = 1e20; k = 0; continue; }
    k++; v[k] = q; z[k] = s; z[k + 1] = 1e20;
  }
  k = 0;
  for (let q = 0; q < n; q++) { while (z[k + 1] < q) k++; const p = v[k]; d[q] = (q - p) * (q - p) + f[p]; }
}
function edt3(occ, nx, ny, nz, wantInside) {
  const INF = 1e12;
  const g = new Float64Array(nx * ny * nz);
  for (let i = 0; i < g.length; i++) g[i] = (occ[i] ^ (wantInside ? 1 : 0)) ? 0 : INF;
  const m = Math.max(nx, ny, nz), f = new Float64Array(m), d = new Float64Array(m), v = new Int32Array(m), z = new Float64Array(m + 1);
  for (let k = 0; k < nz; k++) for (let j = 0; j < ny; j++) { const o = (k * ny + j) * nx; for (let i = 0; i < nx; i++) f[i] = g[o + i]; edt1d(f, nx, d, v, z); for (let i = 0; i < nx; i++) g[o + i] = d[i]; }
  for (let k = 0; k < nz; k++) for (let i = 0; i < nx; i++) { for (let j = 0; j < ny; j++) f[j] = g[(k * ny + j) * nx + i]; edt1d(f, ny, d, v, z); for (let j = 0; j < ny; j++) g[(k * ny + j) * nx + i] = d[j]; }
  for (let j = 0; j < ny; j++) for (let i = 0; i < nx; i++) { for (let k = 0; k < nz; k++) f[k] = g[(k * ny + j) * nx + i]; edt1d(f, nz, d, v, z); for (let k = 0; k < nz; k++) g[(k * ny + j) * nx + i] = d[k]; }
  return g;
}

/** Renders the car's silhouette from the three axes and builds the SDF.  `visual`: the car visual, `scene`: the scene it lives in. */
export function buildHull(renderer, scene, visual) {
  const [nx, ny, nz] = DIM;
  const lodWas = visual.lod;
  visual.forceLod(2);
  const RES = 0.025;
  const views = {
    top: { w: Math.round(4.2 / RES), h: Math.round(6.6 / RES), cam: new THREE.OrthographicCamera(-2.1, 2.1, 3.3, -3.3, 0.1, 30) },
    side: { w: Math.round(6.6 / RES), h: Math.round(2.6 / RES), cam: new THREE.OrthographicCamera(-3.3, 3.3, 2.6, 0, 0.1, 30) },
    front: { w: Math.round(4.2 / RES), h: Math.round(2.6 / RES), cam: new THREE.OrthographicCamera(-2.1, 2.1, 2.6, 0, 0.1, 30) },
  };
  views.top.cam.position.set(0, 10, 0); views.top.cam.up.set(0, 0, -1); views.top.cam.lookAt(0, 0, 0);
  views.side.cam.position.set(-10, 0, 0); views.side.cam.up.set(0, 1, 0); views.side.cam.lookAt(0, 0, 0);
  views.front.cam.position.set(0, 0, -10); views.front.cam.up.set(0, 1, 0); views.front.cam.lookAt(0, 0, 0);
  // the side/front cameras' frustum bottom is y = 0: ortho top/bottom are relative to the camera centre (y = 0)
  const mat = new THREE.MeshBasicMaterial({ color: 0xffffff, side: THREE.DoubleSide });
  const old = { om: scene.overrideMaterial, bg: scene.background, rt: renderer.getRenderTarget(), ac: renderer.autoClear };
  const cc = new THREE.Color(); renderer.getClearColor(cc); const ca = renderer.getClearAlpha();
  scene.overrideMaterial = mat; scene.background = null;
  renderer.setClearColor(0x000000, 1); renderer.autoClear = true;
  const read = {};
  for (const [k, v] of Object.entries(views)) {
    const rt = new THREE.WebGLRenderTarget(v.w, v.h, { type: THREE.UnsignedByteType, depthBuffer: true });
    v.cam.layers.set(3);
    v.cam.updateProjectionMatrix(); v.cam.updateMatrixWorld(true);
    renderer.setRenderTarget(rt);
    renderer.render(scene, v.cam);
    const buf = new Uint8Array(v.w * v.h * 4);
    renderer.readRenderTargetPixels(rt, 0, 0, v.w, v.h, buf);
    rt.dispose();
    read[k] = { buf, w: v.w, h: v.h };
  }
  scene.overrideMaterial = old.om; scene.background = old.bg; renderer.setRenderTarget(old.rt); renderer.autoClear = old.ac; renderer.setClearColor(cc, ca);
  visual.forceLod(lodWas < 0 ? 0 : lodWas);
  mat.dispose();

  // silhouette lookups (pixel row 0 is the bottom of the image)
  const T = read.top, S = read.side, F = read.front;
  const on = (r, i, j) => i >= 0 && j >= 0 && i < r.w && j < r.h && r.buf[(j * r.w + i) * 4] > 127;
  const occ = new Uint8Array(nx * ny * nz);
  // 3x3 dilation of each silhouette by one pixel makes the hull a touch conservative
  const dil = (r, i, j) => { for (let a = -1; a <= 1; a++) for (let b = -1; b <= 1; b++) if (on(r, i + a, j + b)) return true; return false; };
  for (let k = 0; k < nz; k++) {
    const z = MIN.z + (k + 0.5) * H;
    const ti_j = Math.floor(((3.3 - z) / 6.6) * T.h - 0 - 0.0);          // top: row from bottom, bottom = +z
    const si = Math.floor(((z + 3.3) / 6.6) * S.w);                      // side: right = +z
    for (let j = 0; j < ny; j++) {
      const y = MIN.y + (j + 0.5) * H;
      const sj = Math.floor((y / 2.6) * S.h), fj = Math.floor((y / 2.6) * F.h);
      if (!dil(S, si, sj)) continue;
      for (let i = 0; i < nx; i++) {
        const x = MIN.x + (i + 0.5) * H;
        const ti = Math.floor(((x + 2.1) / 4.2) * T.w);
        const fi = Math.floor(((2.1 - x) / 4.2) * F.w);                  // front: right = -x
        if (dil(T, ti, ti_j) && dil(F, fi, fj)) occ[(k * ny + j) * nx + i] = 1;
      }
    }
  }
  const dOut = edt3(occ, nx, ny, nz, false), dIn = edt3(occ, nx, ny, nz, true);
  const sdf = new Float32Array(nx * ny * nz);
  for (let i = 0; i < sdf.length; i++) sdf[i] = (Math.sqrt(dOut[i]) - Math.sqrt(dIn[i]) + (occ[i] ? -0.5 : 0.5)) * H * (occ[i] ? 1 : 1);
  // exact sign convention: occupied voxel centres have d <= 0, free ones > 0 (half a voxel offset to the surface)
  for (let i = 0; i < sdf.length; i++) sdf[i] = occ[i] ? -(Math.sqrt(dIn[i]) - 0.5) * H : (Math.sqrt(dOut[i]) - 0.5) * H;

  const half = new Uint16Array(sdf.length);
  for (let i = 0; i < sdf.length; i++) half[i] = THREE.DataUtils.toHalfFloat(sdf[i]);
  const tex = new THREE.Data3DTexture(half, nx, ny, nz);
  tex.format = THREE.RedFormat; tex.type = THREE.HalfFloatType; tex.minFilter = tex.magFilter = THREE.LinearFilter;
  tex.wrapS = tex.wrapT = tex.wrapR = THREE.ClampToEdgeWrapping; tex.unpackAlignment = 1; tex.needsUpdate = true;

  const max = new THREE.Vector3(MIN.x + nx * H, MIN.y + ny * H, MIN.z + nz * H);
  const idx = (i, j, k) => (k * ny + j) * nx + i;
  const out = {
    sdf, tex, min: MIN.clone(), max, size: new THREE.Vector3(nx * H, ny * H, nz * H),
    /** trilinear signed distance (m); outside the grid: distance to the grid box + the clamped edge value */
    distance(p) {
      const q = p;
      const gx = (q.x - MIN.x) / H - 0.5, gy = (q.y - MIN.y) / H - 0.5, gz = (q.z - MIN.z) / H - 0.5;
      const bx = Math.max(MIN.x - q.x, 0, q.x - max.x), by = Math.max(MIN.y - q.y, 0, q.y - max.y), bz = Math.max(MIN.z - q.z, 0, q.z - max.z);
      const out2 = Math.hypot(bx, by, bz);
      const cx = Math.min(Math.max(gx, 0), nx - 1), cy = Math.min(Math.max(gy, 0), ny - 1), cz = Math.min(Math.max(gz, 0), nz - 1);
      const i0 = Math.min(Math.floor(cx), nx - 2), j0 = Math.min(Math.floor(cy), ny - 2), k0 = Math.min(Math.floor(cz), nz - 2);
      const fx = cx - i0, fy = cy - j0, fz = cz - k0;
      const a = (di, dj, dk) => sdf[idx(i0 + di, j0 + dj, k0 + dk)];
      const c00 = a(0, 0, 0) * (1 - fx) + a(1, 0, 0) * fx, c10 = a(0, 1, 0) * (1 - fx) + a(1, 1, 0) * fx;
      const c01 = a(0, 0, 1) * (1 - fx) + a(1, 0, 1) * fx, c11 = a(0, 1, 1) * (1 - fx) + a(1, 1, 1) * fx;
      const v = (c00 * (1 - fy) + c10 * fy) * (1 - fz) + (c01 * (1 - fy) + c11 * fy) * fz;
      return v + out2;
    },
    gradient(p, o = new THREE.Vector3()) {
      const e = 0.04, v = new THREE.Vector3();
      const f = (x, y, z) => out.distance(v.set(x, y, z));
      return o.set(f(p.x + e, p.y, p.z) - f(p.x - e, p.y, p.z), f(p.x, p.y + e, p.z) - f(p.x, p.y - e, p.z), f(p.x, p.y, p.z + e) - f(p.x, p.y, p.z - e)).normalize();
    },
    /** first point along the ray (origin, unit dir) with distance < eps, or null; maxT in metres */
    march(ro, rd, maxT = 20, eps = 0.02, out3 = new THREE.Vector3()) {
      const q = new THREE.Vector3();
      let t = 0;
      for (let i = 0; i < 120 && t < maxT; i++) {
        q.copy(ro).addScaledVector(rd, t);
        const d = out.distance(q);
        if (d < eps) return out3.copy(q);
        t += Math.max(d * 0.9, 0.01);
      }
      return null;
    },
  };
  return out;
}
