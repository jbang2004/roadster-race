# NEON LOOP — art & feel bible

The player should feel they are driving a 1.7-tonne, 1000 kW electric hypercar through a real, lived-in megacity at
2 a.m., an hour after heavy rain. Every frame should survive a screenshot: **no seams, no voids, no floating or
clipping objects, no visible texture tiling, no z-fighting, no LOD popping, no flat-shaded placeholder look.**

## 1. Place & mood

- An Asian coastal megacity around 2080: Hong Kong density + Shinjuku/Mong Kok signage + Shanghai-Lujiazui towers +
  brutalist concrete megastructures. Signs mix Chinese (dominant), Japanese, Korean and English. Invent brand names;
  never use real brands or real people.
- Cinematic references to *study the look of*: Blade Runner 2049 (haze, scale), Ghost in the Shell 1995 (Hong Kong
  canals and signs), Cyberpunk 2077 city at night, Need for Speed 2015 / Underground 2 (wet-road reflections),
  Gran Turismo "Tokyo Expressway" (expressway lighting, sound walls, sign gantries).
- Time: deep night, overcast. The clouds are lit from below by the city (sodium-orange to magenta glow), a faint
  moon disc occasionally visible through a gap. Rain has mostly stopped: light drizzle, mist, puddles, steam.
- Palette: cold blue-teal ambient and wet asphalt; neon accents in **cyan/teal, magenta/pink, violet**; warm accents in
  **sodium amber** (old street lamps, tunnel) and **warm white** (shop interiors). Red only for tail lights, start lights
  and danger signs. Avoid rainbow soup: each district has 2–3 dominant colours.
- Darkness is a tool: large areas of deep shadow between pools of light, but never pure black — the haze always
  carries some light.

## 2. Districts (zones on the track)

| zone | s range (approx) | character |
|---|---|---|
| boulevard | 0→890 | Downtown main avenue, 18 m wide, 4 lanes. Glass megatowers with LED façades, giant holographic and screen billboards (20–60 m tall), the **start/finish gantry** with five red start lamps and a timing board, crowd barriers and grandstand-like terraces, a monorail or skybridge crossing above. The expressway crosses overhead at z = 30 (huge concrete deck, underside lights). |
| street | 890→1251 | Office canyon side street with the chicane. Dense mid-rise, ground-floor shops, vertical blade signs. |
| docks | 1251→1621 (bridge 1323–1419) | Industrial waterfront. The **canal** (x 380–460, water y = −4.5) with a hump bridge, gantry cranes, stacked containers, warehouses with corrugated walls, sodium lamps, moored boats with lights, steam. |
| ramp | 1621→1891 (elevated from 1720) | Ramp climbing to the expressway between retaining walls and then on pillars. |
| expressway | 1891→3226 | Elevated 16 m-wide highway at y = 14: concrete parapets with steel sound walls (partly transparent), overhead sign gantries (Chinese/English direction signs, speed signs), tall twin-head lamps every ~40 m, views over the city on both sides, passes between towers and over the boulevard and the canal. The sweeping R150 left-hander is banked 5°. |
| descent | 3226→3466 (ground 3374–3419, trench 3419–3466) | Expressway descends 7.8 % into an open concrete trench with retaining walls, graffiti, cable trays. |
| tunnel | 3466→3831 | Tiled road tunnel at y = −7 with continuous LED light lines, jet fans, emergency niches, green exit signs, wet floor reflections. Left R80 inside. |
| market | 3831→4584 (trench until 3944) | Climb out into a very dense night market (Kowloon/Mong Kok): 12 m street, signs overhanging the road on both sides, hanging cables, food stalls with steam, plastic awnings, shutters, AC units, tiny shops glowing warm. The hairpin wraps around a block. |

## 3. Light scale (linear HDR, before exposure; pipeline exposure ≈ 1.0)

three.js physical lights, intensity in candela, `decay = 2`.

| source | value |
|---|---|
| Street lamp (sodium or LED), 8–10 m pole | point/spot 350–500 cd, range 30 m; lamp head emissive 20–40 |
| Expressway lamp | 400 cd each head, range 35 m |
| Tunnel LED strip | treat as a point every 6 m: 120 cd, range 14 m; strip emissive 8–12 |
| Neon tube (sign) | emissive 6–20; optional fill light 30–120 cd, range 10–15 m |
| Screen / billboard | emissive 1.5–5 (content colour), large ones may add a 150–400 cd coloured fill |
| Lit office/shop window | emissive 0.6–3, warm 3200 K or cool 5500 K; many windows dark |
| Car headlight (low beam) | nominal 6000 cd; rendered as a level 17° spot with a wide penumbra and linear falloff (150 cd·m, see car/lightpool.js) so the road under the bumper stays dark; range 80 m; lens emissive 40+ |
| Tail light / brake | one continuous bar in the gloss-black band: emissive 3.6 running, +9 braking (brake light guide behind it 25); brake fill 6 cd, 1.1 m behind the tail |
| Night sky near horizon / zenith | 0.03–0.08 / 0.005–0.02 (city glow tints it) |
| Moonlight (directional) | 0.05–0.12 lux-ish (intensity 0.08), cold blue — only for silhouettes |

A road surface 8 m from a 400 cd lamp should read about 0.3 linear before exposure. Bloom threshold ≈ 1.0 (soft knee),
so almost every emissive source blooms; keep bloom tight and physically plausible (no fog of glow over everything).

## 4. Materials

- **Wet asphalt** is the hero surface: dark albedo (0.04–0.06), roughness 0.15–0.35 in wheel tracks and puddles,
  0.5–0.7 on dry-ish crown; normal map from Poly Haven asphalt with a second, larger-scale break-up layer so tiling is
  never visible; puddles as low areas (roughness → 0.03, normal flattened) that show sharp reflections; lane paint
  (worn, slightly raised, less wet). Reflections of lamps and neon must be **vertically streaked** on wet road.
- Concrete: Poly Haven concrete sets, triplanar or world-UV mapped (no stretched UVs), rain streaks/darkening near the
  ground, AO at contact.
- Glass towers: dark reflective glass with emissive window grids that vary per floor/room (random lit pattern,
  occasional flicker, blinds, interior depth via parallax/“fake interior” where it helps).
- Metals: painted steel with wear, chrome only on details.
- **Car paint**: clear-coated metallic, base flake sparkle, crisp clear-coat reflections of the dynamic environment;
  the player's livery is liquid silver (as modelled), AI liveries vary (BIBLE §7).

## 5. Weather & atmosphere

- Height fog: dense near the ground in the distance, thin overhead; colour picks up the city glow (desaturated
  violet-blue, warmer near sodium districts). Exponential distance fog so the skyline fades in layers — towers at
  2–5 km are silhouettes with a few lit windows and aircraft lights.
- Light shafts: through mist from lamps and big signs (cheap volumetric cones are fine).
- Drizzle: thin streaks visible near lights, splashes on the road near the camera, droplets on the camera lens when
  stationary (optional, subtle). Spray behind cars at speed is the most important rain effect.
- Steam from vents and market stalls; litter/paper drifting (very few).

## 6. Driving feel (“厚重感”)

- Mass and inertia must be visible and audible: the body pitches under braking (nose dives ~2°), squats on launch,
  rolls in corners (~2–3° at 1.2 g), settles with damped (not bouncy) motion. Kerb/expansion-joint hits are felt.
- Camera: spring-damped chase cam with slight lag, look-ahead into corners, FOV widens with speed (60°→74°), tiny
  high-frequency shake at speed and on rough surfaces, punchy shake on impacts, no nausea.
- Sound: layered EV drive unit (multiple whine harmonics + low inverter hum + gear mesh), tyre roll on wet asphalt
  (hiss/spray), tyre scrub when sliding, wind rush rising with speed², body thumps on bumps, heavy metallic crashes,
  reverb in tunnel and under the expressway.
- Speed sensation: motion blur on the world (not the car), speed streaks of lights, spray.
- Performance: 0–100 km/h ≈ 2.3 s, top speed ≈ 330 km/h, braking 300→80 km/h ≈ 220 m, ~1.5 g peak lateral at speed
  (aero). Keyboard driving must be smooth and controllable (input filtering, speed-sensitive steering, mild assists).

## 7. Grid

8 cars: the player (P1 colour: liquid silver as modelled, copper rims) + 7 AI with distinct liveries, e.g. matte
graphite + cyan accents, pearl white + magenta, deep red candy, midnight blue metallic, acid yellow-green, satin black
+ orange, violet chrome. Each AI driver has a name (invented, mixed Chinese/Japanese/Korean/Western) and a skill level.

## 8. UI

Minimal, cinematic, bilingual (Chinese first, English small caps). Thin type, cyan/white on dark glass, no clutter.
HUD: speed (km/h) large, motor power/regen bar, position `3/8`, lap `2/3`, current/last/best lap times, mini-map
of the circuit with all cars, gap to car ahead/behind. Title screen over a slow cinematic orbit of the car on the grid.
