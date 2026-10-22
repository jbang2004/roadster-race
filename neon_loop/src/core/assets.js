// Cached asset loading. All paths are relative to public/ (served at the site root, base './').
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { HDRLoader } from 'three/addons/loaders/HDRLoader.js';

const cache = new Map();
const once = (key, fn) => { if (!cache.has(key)) cache.set(key, fn()); return cache.get(key); };
let maxAniso = 8;
export function setMaxAnisotropy(n) { maxAniso = n; }
export const url = (p) => `./${p.replace(/^\.?\//, '')}`;

export const loadGLTF = (p) => once('gltf:' + p, () => new GLTFLoader().loadAsync(url(p)));

/** opts: { srgb=false, repeat=[1,1], aniso=true } — returns a THREE.Texture (shared; clone() to change repeat). */
export const loadTexture = (p, opts = {}) => once(`tex:${p}:${!!opts.srgb}`, async () => {
  const t = await new THREE.TextureLoader().loadAsync(url(p));
  t.colorSpace = opts.srgb ? THREE.SRGBColorSpace : THREE.NoColorSpace;
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.anisotropy = opts.aniso === false ? 1 : maxAniso;
  if (opts.repeat) t.repeat.set(opts.repeat[0], opts.repeat[1]);
  return t;
});

export const loadHDR = (p) => once('hdr:' + p, async () => {
  const t = await new HDRLoader().loadAsync(url(p));
  t.mapping = THREE.EquirectangularReflectionMapping;
  return t;
});

const manifest = () => once('ph:manifest', () => fetch(url('assets/ph/manifest.json')).then(r => r.json()));

/**
 * Poly Haven texture set by id (see public/assets/ph/manifest.json):
 * → { map (sRGB), normalMap, armMap (R=AO, G=roughness, B=metalness — use as aoMap+roughnessMap+metalnessMap) }
 * Textures are shared between callers: clone() before changing repeat/offset.
 */
export const phTextureSet = (id) => once('phset:' + id, async () => {
  const m = (await manifest()).textures[id];
  if (!m) throw new Error(`Poly Haven texture set "${id}" is not downloaded`);
  const base = 'assets/ph/';
  const [map, normalMap, armMap] = await Promise.all([
    loadTexture(base + m.maps.diff, { srgb: true }),
    loadTexture(base + m.maps.nor),
    loadTexture(base + m.maps.arm),
  ]);
  return { map, normalMap, armMap };
});

export const phHDRI = async (id) => loadHDR('assets/ph/' + (await manifest()).hdris[id]);
export const listPH = async () => manifest();
