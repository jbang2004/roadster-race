// Render layers. See CONTRACTS.md §Lighting model.
//   DEFAULT          world geometry (main pass + road reflection)
//   MAIN_ONLY        drawn in the main pass only (road surface, decals, rain, lens effects)
//   REFLECTION_ONLY  cheap stand-ins drawn only into the wet-road reflection
//   CARS             car meshes; drawn in a separate car pass that also sees the light pool
//   LATE             transparent effects drawn after the cars (spray, smoke, sparks, rain)
export const LAYER = { DEFAULT: 0, MAIN_ONLY: 1, REFLECTION_ONLY: 2, CARS: 3, LATE: 4 };
export function setLayer(obj, layer) { obj.traverse(o => o.layers.set(layer)); }
/** Make a light affect the world passes and the car pass. */
export function lightEverything(light) { light.layers.enable(LAYER.DEFAULT); light.layers.enable(LAYER.MAIN_ONLY); light.layers.enable(LAYER.CARS); return light; }
