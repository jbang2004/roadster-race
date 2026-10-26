# Shared brief for every body-shell subagent (round 2, local Mac)

Give this file plus one task section of `wip/round2/README.md` (A front, B middle, C rear) to each subagent.

## Setup
Work on a branch / worktree made from `claude/beautiful-johnson-w4eyyd` (5b3f421 or later). Everything runs from `neon_loop/`. The task's half-finished patch from the cloud session is in `wip/round2/<name>.patch` (unverified; `git apply` it only if you want to start from it).

## Project
- A 2026 Tesla Roadster replica for a three.js street-racing game, built procedurally in Blender. Body shell = `tools/blender/design2.py` (named curves: U, L, l3, L5, N, wl, rail, R-1 …) + `shell2.py` (17 panels, position fields such as `p3_dy`; locked by `shell_lock.json`). Detail parts: `regions/front.py`, `side.py`, `rear.py`. Build entry: `tools/blender/build_game_car.py`.
- Read first: `tools/blender/AGENT_GUIDE.md` (commands), `CALIB.md` (joint photo calibration: cameras, 3-D landmarks with σ, phase-2 feature lines in `calib/lines/fit.json`, phase-3 silhouettes; the last sections record round 1), `SPEC.md` §9. Docs are in Chinese.
- Car frame (Blender): x toward the REAR (nose ≈ −2.46, tail ≈ +2.49), y lateral (−y = left), z up, metres.
- Photos: `refs/` (read-only). Cameras in `render_ref_views.py` VIEWS are jointly calibrated (rms 1–3 px): a render from a view is pixel-for-pixel comparable with its photo. Exceptions: p014 weak, p005 hand-matched, p003 misses the nose by 80–100 px. `tools/blender/cam.py` projects 3-D points: `Cam('p018').project(np.array([[x, y, z]]))`.
- Measuring tools: `calib/silhouette.py`, `calib/silmetric.py` (outline in metres), `calib/linecheck.py` (model curves vs traced photo lines, rms px), `calib/model_feat.py`, `check.py smooth|plan|nose|fender|lock|budget|clearance` (`python3 tools/blender/check.py` lists them).

## The user's ruling for this round (highest priority)
"All the old rules are overturned — they were made with inaccurate (uncalibrated) cameras. Reconstruct to match the real car. Panels and lines may be stretched and changed freely. Make sure every face and line of the whole car is smooth: not twisted, not bulging (拱起), consistent with the real car."
So dated rulings in SPEC.md / HISTORY.md are NOT constraints; the calibrated photos and landmarks are. The principle that remains: every face flat or one smooth single curvature; every crease straight and crisp (8 mm fillet); soft transitions only where the photos show them; no twist, bump, dent or S-shaped highlight. Reflection-line (zebra) renders are the proof: on a flat face the bands are uniform / straight, on a curved face they bend monotonically — no hooks, rings, whorls or wiggles.

## Environment
- Blender 5.2 at `/Applications/Blender.app/Contents/MacOS/Blender` (the scripts' default; `$BLENDER` overrides). Python on the host needs numpy; ffmpeg must be installed.
- Iterate cheaply: `tools/blender/fast_preview.py` (bare shell), `build_game_car.py -- --live all --out <dir> --only hi --raw`, renders at `--samples 16 --scale 0.5` with `--reflect h|v`; full resolution (48 samples) only for the final evidence. At most two subagents at a time.
- `render_ref_views.py`: always `--glass-dark`; never `--hide Decals`; front wheels are steered per view automatically (`--steer auto`); p005 needs `--exposure -1.5`.
- Do not write `public/assets/car/` (the coordinator rebuilds them at the end). Outputs under `neon_loop/shots/<your name>/` (gitignored).
- Zoom pairs: `wip/round2/zoom.sh <view> <x> <y> <w> <h> <out.jpg> <renderdir> [scale]` (full-res pixel box; renderdir holds <view>.png; photo | render side by side), or `tools/blender/shots.sh --zoom`.

## Rules
- Every change behind a `QF_*` switch defaulting ON (OFF = the previous shape), with a short comment in the surrounding style (what, which photos / landmarks, numbers). Small exact edits; no one-off scripts committed.
- Locks: build with `--unlock <panels>` while iterating; at the end `--write-lock <exactly the panels you changed>`; `check.py lock` must PASS. Never touch panels outside your zone (README: front x < −0.9, middle −0.9 … 0.8, rear > 0.8; U from x 0.6 belongs to the rear).
- `check.py smooth` all PASS; `check.py budget` PASS; `npm test` PASS; `check.py clearance` positive if you touch anything near the wheels.
- Update CALIB.md (a short section with the numbers) and HISTORY.md (one entry), in Chinese, in the existing style. Commit on your branch.

## Report (your final message)
1. What changed: files, switches (old → new values), panels relocked.
2. Numbers before → after for every item (landmarks, silhouettes, linecheck, check.py outputs).
3. Evidence: paths of full-resolution photo | before | after images for every view used, and zebra h / v before / after.
4. Checks: lock, smooth, budget, npm test (and clearance if relevant).
5. What still does not match, and why (3 lines per item).
6. Branch and commit hash(es).
