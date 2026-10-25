// Vehicle parameters for the NEON LOOP wedge EV (SI units, car frame: x right, y up, z back; forward = -z).
// Everything physical lives here so the physics, the AI speed profile and the tests agree on the same numbers.

export const GRAV = 9.81;
export const RHO = 1.2;

const deg = (d) => d * Math.PI / 180;

export const CAR = {
  mass: 1700,                 // kg incl. driver
  wheelbase: 3.097,
  zFront: -1.487, zRear: 1.61,
  // 2026-10-25 (the calibrated press photos, tools/blender/CALIB.md): the wheels stand 9.4 cm further out (half track 0.885 -> 0.979) and the
  // front wheel is smaller than the rear (tyre radius 0.353 / 0.39 = hub height); the visual car (car_meta.json hubs / tyreRadius) has the same numbers
  halfTrack: 0.979,
  wheelR: 0.39,               // rear tyre radius, and the reference radius of the wheel dynamics (drive, brakes, inertia are tuned at it; vehicle.js)
  wheelRF: 0.353,             // front tyre radius (geometry and spin only)
  frontWeight: 0.45,          // static front weight fraction
  cgY: 0.45,                  // centre of gravity height above ground at rest
  // principal moments about the CG in the car frame (x = pitch axis, y = yaw axis, z = roll axis), kg m²
  inertia: { x: 3300, y: 3150, z: 880 },
  // collision hull (car frame)
  box: { hx: 1.10, hy: 0.62, hz: 2.375, cy: 0.73 },
  // wheel inertia incl. reflected rotor, kg m²
  wheelInertia: 3.2,
};
CAR.cgZ = CAR.zFront + CAR.wheelbase * (1 - CAR.frontWeight);   // CG z in the car frame (front axle + 55 % of wheelbase)

export const SUSP = {
  free: 0.30,                 // fully extended hub-to-wheel-centre length (droop limit), m
  travelMax: 0.205,           // maximum compression (bump-stop contact), m
  // ride frequencies (Hz) of the sprung corner masses give the linear spring rates
  freqF: 1.38, freqR: 1.46,
  rubberAt: 0.060,            // bump rubber engages this far beyond static compression
  rubberRate: 4.0,            // × linear rate
  // dampers: critical-damping fractions (digressive above kneeV)
  zetaBump: 0.30, zetaReb: 0.62, kneeV: 0.14, postKnee: 0.42,
  arbF: 12500, arbR: 8000,    // anti-roll bar rates N/m of left-right compression difference
  // geometric (non-elastic) load transfer heights: forces act on the chassis at these heights above the road
  appH: 0.09,
};

export const TYRE = {
  Fz0: 4200,
  // front 285/30 R20-ish, rear 335/30 R21-ish
  front: { mux: 1.33, muy: 1.38, kpk: 0.115, apk: 0.145, Clat: 1.38, Elat: -0.7, Clong: 1.55, Elong: -0.6, sigma: 0.32, load: 0.13 },
  rear:  { mux: 1.39, muy: 1.47, kpk: 0.115, apk: 0.150, Clat: 1.38, Elat: -0.7, Clong: 1.55, Elong: -0.6, sigma: 0.34, load: 0.13 },
  crr: 0.011,                 // rolling resistance coefficient
  vReg: 2.0,                  // slip-velocity regularisation (m/s) – keeps standstill / parking well behaved
  wetGrip: 1.0,               // overall surface grip multiplier (wet asphalt is already baked into mu)
};

// cold-gas thrusters (the Roadster's SpaceX package): compressed air from carbon pressure vessels through the four gold
// nozzles in the diffuser. One tank lasts `duration` s of full thrust and refills after `refillDelay` s off the button.
export const THRUST = {
  force: 9500,                // N at full valve (≈ 0.57 g on the 1700 kg car)
  y: 0.536, z: 2.37,          // nozzle exits, car frame
  vFade: [84, 104],           // m/s: thrust fades out between these forward speeds (≈ 300 → 375 km/h)
  duration: 4.0, refill: 16, refillDelay: 0.9,
  open: 16, close: 9,         // valve slew, 1/s
  relock: 0.25,               // an emptied tank needs this much gas (or a fresh press) before it fires again
};

export const AERO = {
  CdA: 1.75, ClA: 1.40,       // m²
  balanceF: 0.42,             // fraction of downforce on the front axle
  CyA: 3.2,                   // side force area (weathervane stability)
  pressureZ: 0.45,            // centre of side-force pressure behind the CG, m
  dragY: 0.55,                // height where drag acts
};

export const DRIVE = {
  motors: 2,
  gear: 8.0,                  // single reduction
  eta: 0.93,
  front: { T: 720, P: 455e3 },   // Nm, W – front motor
  rear: { T: 900, P: 545e3 },    // rear motor (total 1000 kW)
  maxRpm: 19200,
  taperRpm: 17600,            // torque tapers to zero between taperRpm and maxRpm (soft top-speed limiter)
  rearBias: 0.56,             // static torque share of the rear motor
  regenLift: 0.10,            // fraction of peak torque applied as regen on lift
  regenBrakeMax: 0.62,        // max regen fraction of peak torque under braking
  regenPower: 330e3,          // W per motor
  lsdK: 140, lsdMax: 380,     // Nm/(rad/s), Nm  — e-diff
  reverseTorque: 0.35, reverseMaxSpeed: 14,
};

export const BRAKE = {
  front: 4300, rear: 2550,    // Nm per wheel at full pedal (low speed)
  hiScale: 0.54, hiV0: 22, hiV1: 62,   // brake-by-wire cap: scale of the torque at high speed (full below hiV0 m/s)
  handbrake: 3600,            // Nm per rear wheel
  mass: 4300,                 // thermal mass per disc, J/K
  cool0: 15, coolV: 1.4,      // cooling conductance W/K: base + per m/s
  tAmb: 60, tFadeStart: 650, tFadeEnd: 1000,
};

// Steering lock (rad at the wheel) as a function of speed: full stick ≈ 1.25 × the angle at which the front axle reaches ~97 % of its
// peak lateral force, so a keyboard / stick at full deflection is "just past the limit" (understeer) rather than a spin.
const LOCK_V = [0, 8, 12.5, 16.7, 22.2, 27.8, 41.7, 55.6, 69.4, 83.3, 100];
const LOCK_A = [0.55, 0.50, 0.28, 0.215, 0.145, 0.108, 0.068, 0.049, 0.043, 0.044, 0.047];
export const STEER = {
  maxLock: 0.55,
  speedFalloff(v) {
    if (v <= 0) return LOCK_A[0];
    for (let i = 1; i < LOCK_V.length; i++) if (v < LOCK_V[i]) { const t = (v - LOCK_V[i - 1]) / (LOCK_V[i] - LOCK_V[i - 1]); return LOCK_A[i - 1] + (LOCK_A[i] - LOCK_A[i - 1]) * t; }
    return LOCK_A[LOCK_A.length - 1];
  },
  rate: 4.2,                  // rad/s actuator limit
};

export const ASSIST = { tc: true, abs: true, stability: 0.6 };

// Driver roster (BIBLE §7). livery index = LIVERIES order (0 = player). skill 0..1 = fraction of the grip limit used.
export const DRIVERS = [
  { name: '林夜 LIN YE',        skill: 0.985, aggr: 0.70, cons: 0.97 },
  { name: '佐藤凛 RIN SATO',     skill: 0.975, aggr: 0.55, cons: 0.98 },
  { name: '朴俊豪 PARK JUNHO',   skill: 0.965, aggr: 0.80, cons: 0.93 },
  { name: 'KAI MERCER',          skill: 0.955, aggr: 0.65, cons: 0.95 },
  { name: '赵晓 ZHAO XIAO',      skill: 0.945, aggr: 0.45, cons: 0.97 },
  { name: 'MAYA OKOYE',          skill: 0.935, aggr: 0.60, cons: 0.92 },
  { name: '森隼人 HAYATO MORI',  skill: 0.920, aggr: 0.35, cons: 0.96 },
];

export const PLAYER_NAME = 'YOU 玩家';

export { deg };
