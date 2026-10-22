// 霓虹环线 NEON LOOP — circuit definition (meters, three.js Y-up; X east, -Z north).
// The road is a filleted polyline (straights joined by circular arcs), smoothed so corners get
// transition curves. Direction of travel follows the vertex order. Elevation / width / zone / bank
// are keyed by XZ points that are projected onto the finished centreline.
//
//          N (-Z)
//   G(-520,30)═════ expressway y=14 ══════╗F(620,30)
//   ║ descent           ║(passes over      ║ ramp
//   ║                   ║ the boulevard)   ║
//   ║ tunnel y=-7       ║ boulevard        E(620,-435)… see vertices
//   H═══ market ═══════I  (start/finish)
//
export const LAYOUT = {
  name: '霓虹环线 NEON LOOP',
  ds: 1.0,              // sample spacing (m)
  smoothIters: 120,     // Laplacian passes on the filleted polyline (≈10 m corner transitions)
  vertices: [
    { x: 0, z: 554, r: 30 },     // A  market → boulevard (right)
    { x: 0, z: -380, r: 45 },    // B  T1, end of the 860 m boulevard straight (right)
    { x: 200, z: -380, r: 28 },  // C  chicane (left)
    { x: 245, z: -435, r: 28 },  // D  chicane (right)
    { x: 620, z: -435, r: 55 },  // E  docks corner (right) → ramp
    { x: 620, z: 30, r: 70 },    // F  onto the expressway (right, elevated)
    { x: -520, z: 30, r: 150 },  // G  sweeping expressway left-hander
    { x: -520, z: 600, r: 80 },  // H  left-hander inside the tunnel
    { x: 240, z: 600, r: 22 },   // I  hairpin, part 1 (left)
    { x: 240, z: 554, r: 22 },   // J  hairpin, part 2 (left) → back west to A
  ],
  // Elevation keys (piecewise linear between keys, then box-smoothed over `elevSmooth` m).
  elevSmooth: 60,
  elevation: [
    { x: 0, z: 0, y: 0 },
    { x: 330, z: -435, y: 0 }, { x: 420, z: -435, y: 2.0 }, { x: 510, z: -435, y: 0 }, // canal bridge hump
    { x: 620, z: -300, y: 0 }, { x: 620, z: -80, y: 14 },                              // ramp up
    { x: -520, z: 200, y: 14 }, { x: -520, z: 470, y: -7 },                            // descent into the tunnel
    { x: -300, z: 600, y: -7 }, { x: -150, z: 600, y: 0 },                             // climb out into the market
  ],
  // Zones: each mark starts a zone that lasts until the next mark (cyclic).
  zones: [
    { x: 30, z: 554, zone: 'boulevard', w: 18 },
    { x: 0, z: -320, zone: 'street', w: 13 },
    { x: 300, z: -435, zone: 'docks', w: 13 },
    { x: 620, z: -360, zone: 'ramp', w: 14 },
    { x: 620, z: -90, zone: 'expressway', w: 16 },
    { x: -520, z: 200, zone: 'descent', w: 14 },
    { x: -520, z: 440, zone: 'tunnel', w: 13 },
    { x: -280, z: 600, zone: 'market', w: 12 },
  ],
  widthSmooth: 40,
  // Banking at corner apexes (degrees; + raises the right edge, i.e. use + for left turns).
  bank: [
    { x: 620, z: 30, deg: -3 },
    { x: -520, z: 30, deg: 5 },
  ],
  canal: { x0: 380, x1: 460, water: -4.5, bed: -7 },  // N–S canal across the whole city
  ground: 0,
  bounds: { x0: -950, x1: 1050, z0: -850, z1: 1000 }, // dressed city area (skyline continues beyond)
  start: { x: 0, z: 380 },                             // start/finish line on the boulevard
  laps: 3,
};
