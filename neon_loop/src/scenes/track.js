// Debug scene: the bare circuit (road ribbon coloured by kind, wall lines, ground, canal) + the car for scale.
// ?scene=track[&s=<metres>][&view=top]   Hooks: __track, __viewAt(s, back, up)
import * as THREE from 'three';
import { getTrack, KIND } from '../track/track.js';
import { loadGLTF } from '../core/assets.js';

export default async function (app) {
  const T = getTrack();
  window.__track = T;
  const scene = app.scene;
  scene.background = new THREE.Color(0x0b0d12);
  scene.add(new THREE.HemisphereLight(0x9fb6d8, 0x202226, 2.2));
  const sun = new THREE.DirectionalLight(0xffffff, 1.5); sun.position.set(300, 500, 200); scene.add(sun);

  // road ribbon
  const N = T.N, pos = [], col = [], idx = [];
  const kc = { [KIND.GROUND]: 0x3a3d44, [KIND.ELEVATED]: 0x4a5a78, [KIND.TRENCH]: 0x6a4a3a, [KIND.TUNNEL]: 0x7a3a5a, [KIND.BRIDGE]: 0x3a6a5a };
  const c = new THREE.Color();
  for (let i = 0; i <= N; i++) {
    const k = i % N, hw = T.hw[k];
    for (const side of [-1, 1]) {
      pos.push(T.px[k] + T.rx[k] * hw * side, T.py[k] + T.ry[k] * hw * side + 0.02, T.pz[k] + T.rz[k] * hw * side);
      c.set(kc[T.kind[k]]); if (Math.floor(k / 10) % 2) c.multiplyScalar(0.85); col.push(c.r, c.g, c.b);
    }
    if (i < N) { const a = i * 2; idx.push(a, a + 2, a + 1, a + 1, a + 2, a + 3); }
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  g.setAttribute('color', new THREE.Float32BufferAttribute(col, 3));
  g.setIndex(idx); g.computeVertexNormals();
  scene.add(new THREE.Mesh(g, new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.8, side: THREE.DoubleSide })));

  // walls (thin vertical strips at hw + 0.5)
  for (const side of [-1, 1]) {
    const wp = [], wi = [];
    for (let i = 0; i <= N; i++) {
      const k = i % N, o = (T.hw[k] + 0.5) * side;
      const x = T.px[k] + T.rx[k] * o, y = T.py[k] + T.ry[k] * o, z = T.pz[k] + T.rz[k] * o;
      wp.push(x, y, z, x, y + 0.9, z);
      if (i < N) { const a = i * 2; wi.push(a, a + 2, a + 1, a + 1, a + 2, a + 3); }
    }
    const wg = new THREE.BufferGeometry(); wg.setAttribute('position', new THREE.Float32BufferAttribute(wp, 3)); wg.setIndex(wi); wg.computeVertexNormals();
    scene.add(new THREE.Mesh(wg, new THREE.MeshStandardMaterial({ color: side < 0 ? 0xc04060 : 0x40a0c0, emissive: side < 0 ? 0x301018 : 0x102830, side: THREE.DoubleSide })));
  }
  // ground + canal
  const B = T.layout.bounds, cn = T.layout.canal;
  const ground = new THREE.Mesh(new THREE.PlaneGeometry(B.x1 - B.x0, B.z1 - B.z0), new THREE.MeshStandardMaterial({ color: 0x15171c, roughness: 1 }));
  ground.rotation.x = -Math.PI / 2; ground.position.set((B.x0 + B.x1) / 2, -0.05, (B.z0 + B.z1) / 2); scene.add(ground);
  const canal = new THREE.Mesh(new THREE.PlaneGeometry(cn.x1 - cn.x0, B.z1 - B.z0), new THREE.MeshStandardMaterial({ color: 0x0a2a40, roughness: 0.2 }));
  canal.rotation.x = -Math.PI / 2; canal.position.set((cn.x0 + cn.x1) / 2, 0.0, (B.z0 + B.z1) / 2); scene.add(canal);
  // start line
  const sf = T.frameAt(T.startS);
  const line = new THREE.Mesh(new THREE.PlaneGeometry(sf.hw * 2, 1.2), new THREE.MeshBasicMaterial({ color: 0xffffff }));
  line.position.copy(sf.pos).y += 0.04; line.quaternion.copy(T.quatAt(T.startS)); line.rotateX(-Math.PI / 2); scene.add(line);

  // cars on the grid
  const gltf = await loadGLTF('assets/car/wedge_car.glb');
  for (let k = 0; k < 8; k++) {
    const slot = T.gridSlot(k);
    const car = new THREE.Group(); const m = gltf.scene.clone(); m.rotation.y = -Math.PI / 2; car.add(m);
    car.position.copy(slot.pos); car.quaternion.copy(slot.quat); scene.add(car);
  }

  window.__viewAt = (s, back = 9, up = 3.2, ahead = 30) => {
    const f = T.frameAt(s), a = T.frameAt(s + ahead);
    const p = f.pos.clone().addScaledVector(f.t, -back).addScaledVector(f.u, up);
    app.setView({ pos: p.toArray(), target: a.pos.clone().addScaledVector(a.u, 1).toArray(), fov: 62 });
  };
  if (app.q.get('view') === 'top') {
    app.camera.near = 200; app.camera.far = 8000; app.setView({ pos: [50, 2600, 80], target: [50, 0, 79.9], fov: 45 });
  } else window.__viewAt(+(app.q.get('s') ?? T.startS - 30));
  await app.ready();
}
