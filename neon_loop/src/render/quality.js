// Quality presets (app.quality = 'high' | 'medium' | 'low'). Owner: R.
// Light-pool sizes and the reflection MSAA sample count are fixed for the lifetime of the renderer (changing them
// recompiles shaders); everything else can be switched live through render.setQuality().
export const QUALITY = {
  high: {
    sceneScale: 1.0, minScale: 0.7, aa: 'taa', maxScenePx: 2.2e6, maxReflPx: 0.6e6,
    reflScale: 0.5, reflSamples: 0, reflEvery: 1, reflFar: 1200,
    probeSize: 128, probeFaces: 1, probeEvery: 2, probeFar: 300,
    points: 8, spots: 3,
    bloomLevels: 6, streaks: true, mbTaps: 14,
  },
  medium: {
    sceneScale: 0.85, minScale: 0.6, aa: 'taa', maxScenePx: 1.6e6, maxReflPx: 0.4e6,
    reflScale: 0.4, reflSamples: 0, reflEvery: 1, reflFar: 3000,
    probeSize: 64, probeFaces: 1, probeEvery: 2,
    points: 8, spots: 2,
    bloomLevels: 5, streaks: true, mbTaps: 8,
  },
  low: {
    sceneScale: 0.7, minScale: 0.5, aa: 'fxaa', maxScenePx: 1.0e6, maxReflPx: 0.25e6,
    reflScale: 0.3, reflSamples: 0, reflEvery: 2, reflFar: 1500,
    probeSize: 64, probeFaces: 1, probeEvery: 3,
    points: 4, spots: 0,
    bloomLevels: 5, streaks: false, mbTaps: 0,
  },
};
