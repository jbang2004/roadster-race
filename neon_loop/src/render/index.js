// R — rendering. createRenderer(app, track) → render.   See CONTRACTS.md §Area entry points and src/render/pipeline.js.
//
//   render.params          live numbers: exposure, tonemap ('agx'|'aces'), bloom{strength,threshold,knee,radius,levels},
//                          streak{strength,threshold,length}, motionBlur, mbMaxLen, vignette, grain, chroma, sharpen,
//                          grade{teal,magenta,contrast,saturation}, aa ('taa'|'fxaa'), taa*, reflection{enabled},
//                          probe{enabled}, adaptive, targetFps, debug ('none'|'bloom'|'mask'|'streak')
//   render.setFocus(obj)   the car/object the reflection plane, car probe and light pool follow
//   render.setCars(objs)   optional: car roots for exact per-car TAA reprojection + light-pool interest (else auto-detected)
//   render.probe.texture   PMREM cube environment around the focus, for car materials (envMap)
//   render.fx.shake(a) / .speed(k 0..1) / .flash(color, seconds)
//   render.stats()         fps-independent numbers (also merged into app.stats())
//   render.sceneTexture / render.depthTexture   HDR colour (alpha = car mask) and depth of the last frame's scene target
//   LAYER_LATE (= 4)       layer for transparent effects that must draw after the cars (spray, smoke, sparks)
import * as THREE from 'three';
import { Pipeline, LAYER_LATE, MASK_WORLD, MASK_CARS } from './pipeline.js';

export { LAYER_LATE, MASK_WORLD, MASK_CARS };

export async function createRenderer(app, track) {
  const r = app.renderer;
  r.toneMapping = THREE.NoToneMapping;            // the pipeline tone-maps in its composite pass
  r.shadowMap.enabled = false;
  const pipe = new Pipeline(app, track);
  await pipe.init();
  app.setPipeline(pipe);

  const render = {
    pipeline: pipe,
    params: pipe.params,
    fx: pipe.fx,
    setFocus: (o) => pipe.setFocus(o),
    setCars: (l) => pipe.setCars(l),
    probe: { get texture() { return pipe.probe.texture; } },
    lightPool: pipe.pool,
    reflection: pipe.refl,
    stats: () => pipe.stats(),
    benchmark: (n) => pipe.benchmark(n),
    get sceneTexture() { return pipe.rtScene.texture; },
    get depthTexture() { return pipe.rtScene.depthTexture; },
    get plane() { return pipe.plane; },
    dispose: () => { pipe.dispose(); },
  };
  window.__render = render;
  return render;
}
