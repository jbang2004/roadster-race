# 霓虹环线 NEON LOOP — architecture & contracts

A night street race through a rain-soaked cyberpunk megacity. The player drives the **2026 Roadster** replica
(three LOD GLBs `public/assets/car/car_hi.glb` / `car_lod1.glb` / `car_lod2.glb` + `car_meta.json`, built in Blender by
`tools/blender/build_game_car.py`, loaded by `src/car/index.js`: meshopt-compressed, `.raw.glb` fallback, LOD switch by camera distance;
how to build it: `tools/blender/AGENT_GUIDE.md`) against 7 AI cars over 3 laps of a
4.58 km street circuit. (The old `wedge_car.glb` stays in place: the per-area scenes `ui` / `track` / `drive` / `render` / `skyline` still load it.)
three.js **r186**, WebGL2, plain JS ES modules, Vite. Goal: **real racing-game
quality — weight, materials, lighting — and a city with no visible seams.** Look & numbers: `docs/BIBLE.md`.
This file is the authority for paths, ownership and APIs.

## Running & verifying

- Project root: this folder (`neon_loop/`). Shared dev server: `http://127.0.0.1:5180` (already running).
  Do NOT start another server on 5180. If it is down: `npx vite --port 5180 --strictPort --host 127.0.0.1` in the background.
- Scenes: `src/scenes/<name>.js` default-exports `async function (app)`; open `?scene=<name>`. Build content,
  `app.add(system)`, then `await app.ready()` (compiles shaders, removes the loader, sets `window.__ready`).
- **Screenshot harness (real Apple M5 GPU, headless Chrome):**
  `node tools/shot.mjs --scene <name> --out shots/<area>/<file>.png [--w 1600 --h 900] [--wait 2500] [--eval "<js>"] [--eval2 "<js>" --wait2 1000] [--q "k=v&k2=v2"]`
  Then **Read the PNG and look at it.** It prints console errors and `app.stats()` (fps, draw calls, tris). Exit 2 = errors / never ready.
  The harness runs at pixel ratio 1. `?freeze` stops game time. `--eval` runs after ready (e.g. `"__app.setView({pos:[0,3,380],target:[0,1,350]})"`).
- `node tools/trackinfo.mjs` prints circuit stats. `?scene=track` shows the bare circuit (`&view=top` for a map;
  `__viewAt(s, back, up)` puts a chase camera at lap distance s).
- Iterate visually: screenshot → critique honestly against the bible → improve. Several rounds. Check at least: a
  chase-cam view on the boulevard (s≈150), the expressway (s≈2500), the tunnel (s≈3600), the market (s≈4200).
- Use your own `shots/<area>/` folder. Keep screenshots ≤ 1600 px wide.

## Ownership (edit only files you own; create new files only inside your area)

| key | area | owns |
|---|---|---|
| I | integrator (lead) | `index.html`, `src/main.js`, `src/core/**`, `src/track/**`, `src/scenes/full.js`, `src/scenes/track.js`, `tools/shot.mjs`, `tools/trackinfo.mjs`, `tools/fetch-assets.mjs`, `CONTRACTS.md`, `docs/BIBLE.md`, `public/assets/ph/**` |
| R | rendering | `src/render/**`, `src/scenes/render.js`, `src/core/reflect.js` (keep its exported names/signatures) |
| W | trackside world | `src/world/**`, `src/scenes/city.js` |
| K | skyline, sky, atmosphere, weather | `src/skyline/**`, `src/scenes/skyline.js` |
| C | car visuals + vehicle FX | `src/car/**`, `src/fx/**`, `src/scenes/car.js`, `tools/blender/**`, `public/assets/car/**` (keep `wedge_car.glb` as is; add derived files) |
| P | gameplay: physics, AI, race, input, cameras | `src/game/**`, `src/scenes/drive.js` |
| U | UI + audio | `src/ui/**`, `src/audio/**`, `src/scenes/ui.js` |

Need something from another area that doesn't exist yet? Write a small shim inside your own area and list it
under **REQUESTS** in your final report. Never edit someone else's file. No new npm dependencies, no downloads
(the Poly Haven set in `public/assets/ph/` is all there is; ask the lead for more). Generate everything else
procedurally (canvas textures, shaders, geometry, WebAudio synthesis). The original Blender car
(`../wedge_car/wedge_car.blend`, `../wedge_car/build_car.py`) is read-only reference.

Your area scene must only import `src/core/**`, `src/track/**` and your own area (other areas are being written at
the same time and may be broken). The lead integrates everything in `src/scenes/full.js`.

## Conventions

- Metres, seconds, kg, radians. three.js Y-up. World: X east, −Z north. Ground level y = 0.
- **Car local frame: −Z forward, +X right, +Y up**, origin on the ground plane under the car (between the axles,
  see below). The GLB is authored with −X forward / +Z left: wrap it in a group with `rotation.y = -Math.PI/2`.
- Car dimensions (game frame): body z ∈ [−2.374, 2.375] (front at −z), x ∈ [−1.10, 1.10], y ∈ [0.114, 1.338].
  Wheels (GLB nodes `Wheel_FL`, `Wheel_FR`, `Wheel_RL`, `Wheel_RR`): FL (−0.885, 0.39, −1.487), FR (0.885, 0.39, −1.487),
  RL (−0.885, 0.39, 1.61), RR (0.885, 0.39, 1.61). Tyre radius 0.39 m. Wheelbase 3.097 m, track 1.77 m.
- Wheel order everywhere: `[FL, FR, RL, RR]`.
- Colour: linear HDR scene values, sRGB output. Light/emissive scale: `docs/BIBLE.md §Light scale`. Do not tune your
  area to look right with your own private exposure — the pipeline's exposure is global.

## Core APIs (owner I)

### App (`src/core/app.js`) — `app`
`app.renderer`, `app.scene`, `app.camera` (PerspectiveCamera, layers DEFAULT+MAIN_ONLY), `app.q` (URLSearchParams),
`app.harness`, `app.quality` ('high'|'medium'|'low', from `?q=`), `app.bus`,
`app.time = { t, dt, frame, scale, fixedT, alpha }` (alpha = interpolation factor between the last two fixed steps),
`app.add(sys)` — sys: `{ fixed?(h, t), update?(dt, t), late?(dt, t), resize?(w, h), dispose?() }`; per frame: all `fixed`
at 120 Hz (h = 1/120), then all `update`, then all `late`, then `pipeline.render(dt)`.
`app.setPipeline(p)` — p: `{ render(dt), setSize(w, h, pixelRatio), stats?(), dispose?() }`.
`app.setView({pos, target, fov})` sets the camera and `app.viewLocked = true` (camera rigs must not move the camera
while it is set). `app.renderScale` (pipelines may change it), `app.stats()`, `await app.ready()`.

### Bus (`src/core/bus.js`) — `bus.on(name, fn) → off`, `bus.once`, `bus.emit(name, payload)`. Events: §Events.

### Assets (`src/core/assets.js`)
`loadGLTF(path)`, `loadTexture(path, {srgb, repeat})`, `loadHDR(path)`, `phTextureSet(id) → {map, normalMap, armMap}`
(arm = R AO, G roughness, B metal; textures are shared — `clone()` before changing repeat), `phHDRI('shanghai_bund')`.
Downloaded Poly Haven ids: `asphalt_track` (2k), `asphalt_02` (2k), `concrete_pavement`, `concrete_slab_wall`,
`concrete_panels`, `concrete_tile_facade`, `ribbed_concrete_wall`, `metal_plate`, `corrugated_iron_02`,
`painted_metal_shutter`, `dark_brick_wall`, `rectangular_facade_tiles` (1k). HDRI: `shanghai_bund` (2k, night city).

### Layers (`src/core/layers.js`) — `LAYER = { DEFAULT: 0, MAIN_ONLY: 1, REFLECTION_ONLY: 2, CARS: 3, LATE: 4 }`
`setLayer(obj, layer)`, `lightEverything(light)`. The road surface, decals, rain and other things that must not appear
in the road reflection go on MAIN_ONLY. Car meshes go on CARS. See §Lighting model for how R uses them.

### Lighting model (binding for R, W, K, C)
three.js lights apply to every material in a pass, so the city's thousands of static lights can NOT be real lights.
- **World passes** (R renders camera layers DEFAULT + MAIN_ONLY): the only real three.js lights that reach the world
  are K's global ambient/hemisphere + moon and C's car lights (headlight SpotLights, brake/reverse fill). Everything else
  in the world is lit by **W/K's own static lighting**: emissive surfaces plus light baked/evaluated from `lights.list`
  (vertex-colour bakes, light maps, a city light-grid texture, projected light-pool decals, analytic shader terms —
  the owner's choice). Never put a static lamp in the scene as a real light.
- **Car pass** (R renders camera layer CARS into the same HDR target, depth-tested after the world): sees R's
  **light pool** — the strongest nearby `lights.list` entries turned into real PointLights/SpotLights on layer CARS only,
  faded in/out smoothly — plus the global and car lights. So the cars are correctly lit by the street lamps they pass,
  and nothing is lit twice.
- Global lights (K) and car lights (C) must call `lightEverything(light)` so they reach both passes.
- Custom shaders that don't use three.js lighting (e.g. W's road) get car headlights from `G.uHead*` +
  `HEADLIGHT_GLSL` (`src/core/globals.js`, filled each frame by C), and wet reflections from `RF` + `REFLECT_GLSL`
  (`src/core/reflect.js`, filled by R). Prefer `MeshStandardMaterial`/`MeshPhysicalMaterial` + `onBeforeCompile` over raw
  `ShaderMaterial` so fog, env and car lights keep working; raw shaders must include the fog chunks (K patches them).
- `G` (`src/core/globals.js`, owner I): `uTime`, `uCamPos` (set by the app every frame), `uRain`, `uWet` (K writes),
  `uHeadCount/uHeadPos/uHeadDir/uHeadColor` (C writes).

### Static lights (`src/core/lights.js`) — `lights.add({pos, color, intensity, range, kind, dir?, angle?, penumbra?, flicker?})`
Register every street lamp / neon fill / tunnel light / sign glow you place. Nothing is drawn by the registry: R's
light pool turns the most important nearby ones into real three.js lights each frame (for cars and anything using
standard materials), and W bakes the full list into road lighting. `lights.nearest(pos, n, filter)`, `lights.list`.

### Track (`src/track/track.js`) — `const track = getTrack()` (singleton, ~90 ms to build)
Samples every `track.ds` = 1 m, `track.N` samples, `track.length` m, closed loop, travel = increasing s.
Per-sample typed arrays: `px py pz` (centreline), `tx ty tz` (tangent), `ux uy uz` (road up, includes bank),
`rx ry rz` (right, includes bank), `hw` (half width of the drivable road, m), `bank`, `curv` (signed horizontal curvature,
+ = left), `grade`, `zone` (index into `track.zoneNames`: boulevard, street, docks, ramp, expressway, descent, tunnel,
market), `kind` (`KIND.GROUND|ELEVATED|TRENCH|TUNNEL|BRIDGE`).
- `track.frameAt(s, out?) → {pos, t, u, r, hw, bank, curv, i, s, zone, kind}`
- `track.pointAt(s, u, out?)` — road surface point at lateral offset u (+ right).
- `track.project(pos, hint = -1, out?) → {i, s, u, y, hw, nx, ny, nz, d, kind}` — with `hint` (sample index from the
  previous call) the search is local and never jumps levels at the crossover; without, nearest road in 3D.
  `y` = road height under pos, `n` = road normal, `d = pos.y − y`.
- `track.field(x, z, out?) → {all, ground, i}` — horizontal distance from the nearest road **edge** (negative = on road),
  clamped to 80 m. `ground` ignores elevated/tunnel road (use it for pillars). Grid 2 m, `track.layout.bounds`.
- `track.gridSlot(k) → {pos, quat, s, u}` (k = 0 pole), `track.quatAt(s)`, `track.startS`, `track.laps`,
  `track.wrapS(s)`, `track.deltaS(a, b)`, `track.layout` (canal, bounds, ground…).
- `WALL_OFFSET` = 0.5: the barrier collision face is at |u| = hw + 0.5 on both sides, everywhere. The asphalt continues
  to it (gutter). Barrier geometry (W) must put its face exactly there.
- Circuit: start/finish at s≈190 on the 890 m **boulevard** (north-bound, x = 0). T1 right (R44) → chicane → **docks**
  street over the canal bridge (x 380–460) → right (R54) → **ramp** up to the **expressway** (y = 14, 16 m wide) which
  passes over the boulevard at z = 30 → sweeping left R150 → **descent** (7.8 %) through an open trench into the
  **tunnel** (y = −7) with a left R80 inside → climb out into the narrow **market** (12 m) → hairpin (R21) → back to the
  boulevard. Run `node tools/trackinfo.mjs` for exact s ranges.

## Area entry points (what the lead's `full.js` will call)

**R** `src/render/index.js`: `export async function createRenderer(app, track) → render`
`render.params` {exposure, bloom:{strength, threshold, radius}, motionBlur, vignette, grain, chroma, …},
`render.setFocus(object3D)` (reflection probe + light pool + reflection plane follow it), `render.probe.texture`
(dynamic cube env for the cars, updated around the focus), `render.fx.shake(a)`, `render.fx.speed(k 0..1)`,
`render.fx.flash(color, seconds)`. R sets `scene.environment` (static, from the HDRI) and installs the pipeline,
runs the world pass, the car pass, the light pool and the wet-road reflection (fills `RF`).

**W** `src/world/index.js`: `export async function buildWorld(app, track) → world` with `world.update(dt, t)`,
`world.setStartLights(n)` (n = 0..5 red lamps lit, −1 = all off/green), `world.dispose()`.
Owns everything within ~150 m of the road (track.field(x,z).all < 150), the road surface, barriers, sidewalks,
near buildings, expressway structure, trench/tunnel, bridge, the canal (whole length inside bounds), street props.

**K** `src/skyline/index.js`: `export function installAtmosphere(app)` (called first, before any material compiles:
global height-fog shader chunk patch + sky) and `export async function buildSkyline(app, track) → skyline` with
`skyline.update(dt, t)`, `skyline.setWeather({rain, mist})`. Owns everything beyond ~140 m from the road, ground
beyond it (y = −0.05, must leave the canal strip and the near band to W), the sky, clouds, moon, fog, rain,
flying traffic, far megastructures.

**C** `src/car/index.js`: `export async function loadCarAssets(app)`; `export function createCarVisual(app, {livery, isPlayer, envMap})
→ visual` with `visual.object` (Object3D on layer CARS; caller adds it to the scene; LOD switching is internal),
`visual.sync(car, dt)` (reads §Car state: pose, wheels, lights, brake; also writes this car's slot of `G.uHead*`),
`visual.setEnvMap(tex)`, `visual.dispose()`; `export const LIVERIES` (8 entries, index 0 = player).
`envMap` will be `render.probe.texture` in the game.
`src/fx/index.js`: `export function createVehicleFx(app) → fx` with `fx.update(dt, cars)` (spray, mist, tyre smoke from
car state) and listeners for `car:collision` / `car:scrape` (sparks, debris).

**P** `src/game/index.js`: `export function createRace(app, track, {makeVisual, laps, aiCount}) → race` with `race.cars`
(§Car state, `race.cars[0]` = player), `race.phase` ('grid'|'countdown'|'racing'|'finished'), `race.start()`
(countdown → racing), `race.reset()`, `race.camera` (chase/hood/bumper/orbit modes, `race.camera.setMode(m)`),
`race.paused`. Physics must be pure JS (no DOM, no WebGL) so `src/game/test/run.mjs` runs in Node.

**U** `src/ui/index.js`: `export function createUI(app, race) → ui` (title, HUD, countdown, pause, results).
`src/audio/index.js`: `export function createAudio(app, race) → audio` (`audio.unlock()` on first user gesture,
`audio.setVolume(v)`, `audio.mute(b)`).

## Car state (owner P; read by C, U, audio, R)

```
car = {
  id, name, livery (index into LIVERIES), isPlayer, visual,
  position: Vector3, quaternion: Quaternion          // render pose, already interpolated with app.time.alpha
  velocity: Vector3 (m/s, world), angularVelocity: Vector3, speed (m/s along car forward, signed),
  accel: Vector3 (m/s², car local, smoothed)        // for camera/body feel
  input: { throttle 0..1, brake 0..1, steer -1..1 (+ = right), handbrake 0..1 },
  wheels: [ { steer (rad, + = right), spin (rad, accumulated), spinRate (rad/s), compression (m, + = compressed),
              suspensionTravel (m, + = wheel moved up), load (N), slipRatio, slipAngle, grounded, skid 0..1,
              contact: Vector3 (world) } ×4 ],         // [FL, FR, RL, RR]
  motor: { rpm, load 0..1, power (kW, − = regen) }, brakeTemp 0..1,
  lights: { head: bool, brake 0..1, reverse: bool },
  race: { lap (1-based), lapS (0..length), progress (total m), place (1..8), lapTimes [], bestLap, lastLap,
          finished, finishTime, gapAhead, gapBehind },
  track: { i, s, u, d }                             // last projection
}
```

## Events (bus)

`race:phase {phase}` · `race:countdown {n}` (3, 2, 1, then 0 = GO) · `race:lap {car, lap, time, best}` ·
`race:finish {car, place, time}` · `car:collision {car, other|null, pos, normal, impulse, kind:'wall'|'car'}` (impulse in N·s) ·
`car:scrape {car, pos, normal, intensity 0..1}` (at most once per frame per car while grinding a wall) ·
`camera:mode {mode}` · `ui:start {laps}` · `ui:pause {paused}` · `ui:restart` · `ui:quit`.

## Budgets (M5, 1920×1080 render, high quality)

60 fps. Whole scene ≤ 1500 draw calls, ≤ 8 M triangles visible. Rough split: R post ≤ 5 ms; W ≤ 600 calls; K ≤ 300 calls;
cars ≤ 8 × 40 calls (C provides LODs: AI cars beyond ~40 m use a ≤ 60 k-tri LOD). Instancing and merged geometry
everywhere; no per-frame allocations in hot loops. Textures ≤ 2k; build procedural textures once at load.
