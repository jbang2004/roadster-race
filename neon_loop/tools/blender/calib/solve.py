"""
Joint calibration of the press-photo cameras (numpy only): python3 tools/blender/calib/solve.py [--quiet]

Reads picks.json (hand-read points, px + sigma), rims/<photo>.json (rim-edge points from wheel.py / saverim.py), rings/<photo>.json (nozzle-ring centres from ring.py)
and init_views.json (start cameras: the pre-calibration VIEWS of the matched photos, rough starts for the new ones), solves bundle.py's Problem and writes
result.json: every camera as a VIEWS tuple (render_ref_views.py / cam.py format) with its uncertainty and residuals, the landmark 3D points, wheel rims, axle heights,
front-wheel steer per photo, and the residuals of the old cameras.  See CALIB.md.

Gauge: front / rear axle x = -1.487 / 1.61 (the model's wheel centres; fixes origin and scale), tyre ground contacts at z = 0, landmark pairs mirror-symmetric about y = 0.
"""
import json, glob, os, sys
from collections import Counter
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from bundle import Problem, CamModel, base, triangulate

EXCL = ['p005']                       # p005 shares only the hood-corner flap (FT*) with p013, whose heights it cannot fix: not calibrated (kept as before)
DROPLM = {'FT1', 'FT2', 'FT3'}
STRAIGHT = ['p018', 'p011', 'p001']   # front wheels straight in these photos (prior 0 +- 2 deg); steered ~18-23 deg in p016 / p017 / p003 (the rim ellipses show it)
RIM_GROUPS = {'p011': '11', 'p012': '11'}      # the desert shoot (p011 / p012) has its own rim radius / face offset
GROUND = {     # tyre ground contacts (u, v, sigma, (x, sign(y), 0)); |y| = rim face + 4 cm (bundle.py)
    'p018': {'GF_L': [476.6, 769.5, 3.0, [-1.487, -1.0, 0.0]], 'GR_L': [1353.1, 767.0, 3.0, [1.61, -1.0, 0.0]]},
    'p001': {'GF_L': [454.4, 862.0, 3.0, [-1.487, -1.0, 0.0]], 'GR_L': [1325.8, 857.0, 3.0, [1.61, -1.0, 0.0]]},
    'p012': {'GR_L': [316.0, 980.0, 3.0, [1.61, -1.0, 0.0]], 'GR_R': [1478.5, 977.0, 3.0, [1.61, 1.0, 0.0]]},
    'r81': {'GR_L': [697.0, 943.0, 3.0, [1.61, -1.0, 0.0]]}}
HORIZON = {'p012': [(60, 843.0, 4.0), (1740, 843.0, 4.0)]}      # the lake bed's far edge (without it p012's height / pitch is free: the tail is nearly a plane)
PRIOR_LOC, PRIOR_F, PRIOR_STEER = 0.6, 0.15, 2.0                  # mild priors on the matched cameras (m, relative focal) and on the straight front wheels (deg)


def load():
    picks = json.load(open(os.path.join(HERE, 'picks.json')))
    rims = {os.path.basename(f)[:-5]: json.load(open(f)) for f in glob.glob(os.path.join(HERE, 'rims', '*.json'))}
    rings = {os.path.basename(f)[:-5]: json.load(open(f)) for f in glob.glob(os.path.join(HERE, 'rings', '*.json'))}
    for d in (picks, rims, rings):
        for e in EXCL:
            d.pop(e, None)
    for ph in picks:
        picks[ph] = {k: v for k, v in picks[ph].items() if base(k) not in DROPLM}
    cnt = Counter()                    # a landmark seen in one photo carries no information
    for d in list(picks.values()) + list(rings.values()):
        for b in {base(k) for k in d}:
            cnt[b] += 1
    for ph in picks:
        picks[ph] = {k: v for k, v in picks[ph].items() if cnt[base(k)] > 1}
    iv = json.load(open(os.path.join(HERE, 'init_views.json')))
    tup = lambda v: (tuple(v[0]), tuple(v[1]), v[2], tuple(v[3]), tuple(v[4])) + tuple(v[5:])
    used = set(picks) | set(rims) | set(rings)
    matched = {k: tup(v) for k, v in iv['matched'].items() if k in used}
    new = {k: tup(v) for k, v in iv['new'].items() if k in used}
    pr = Problem(picks, rims, rings, {**matched, **new}, {}, RIM_GROUPS, ground={k: v for k, v in GROUND.items() if k in used},
                 horizon={k: v for k, v in HORIZON.items() if k in used})
    return pr, matched, new


def table(pr, x):
    per, rows = pr.report(x)
    out = {}
    for ph in pr.cn:
        a = np.array(per.get(ph, []))
        d = np.hypot(a[:, 0], a[:, 1])
        out[ph] = (len(d), float(np.sqrt(np.mean(d ** 2))), float(d.max()))
    return out, rows


def main(quiet=False):
    pr, matched, new = load()
    for n in matched:
        i = pr.ci[n].start
        pr.priors['loc_' + n] = (slice(i, i + 3), pr.cams[n].p0[:3], PRIOR_LOC)
        pr.priors['f_' + n] = (i + 6, pr.cams[n].p0[6], PRIOR_F)
    obl = {}
    for o in pr.obs:
        if o[1] == 'pt':
            obl.setdefault(base(o[2]), []).append((o[0], o[2], o[3][0]))
    L0 = triangulate(matched, obl)
    x = pr.x0({b: L0.get(b, np.array([0.0, 0.5, 0.8])) for b in pr.lm})
    # 1. the old cameras frozen: resect the new photos, then fit landmarks / rims to the old cameras (-> how consistent the old set is)
    frz = [pr.ci[n] for n in matched]
    x = pr.solve(x, it=40, verbose=False, freeze=frz + list(pr.li.values()) + [pr.zi['F'], pr.zi['R']] + list(pr.ri.values()))
    x = pr.solve(x, it=40, verbose=False, freeze=frz)
    before, _ = table(pr, x)
    # 2. everything free
    for ph, i in pr.si.items():
        if ph in STRAIGHT:
            pr.priors['steer_' + ph] = (i, 0.0, np.radians(PRIOR_STEER))
    x = pr.solve(x, it=150, verbose=not quiet)
    after, rows = table(pr, x)
    r = pr.residuals(x)
    s2 = np.sum(r ** 2) / max(1, len(r) - pr.n)
    sd = np.sqrt(np.maximum(np.diag(np.linalg.pinv(pr.J.T @ pr.J) * s2), 0))
    res = {'sigma0': round(float(np.sqrt(s2)), 3), 'excluded': EXCL, 'cameras': {}, 'landmarks': {}, 'rims': {}, 'axle_z': {}, 'steer_deg': {}, 'observations': []}
    for n in pr.cn:
        s = sd[pr.ci[n]]
        res['cameras'][n] = {'view': list(pr.cams[n].to_view(x[pr.ci[n]])), 'n': after[n][0], 'rms_px': round(after[n][1], 2), 'max_px': round(after[n][2], 2),
                             'old_rms_px': round(before[n][1], 2) if n in matched else None, 'old_max_px': round(before[n][2], 2) if n in matched else None,
                             'sd_loc_m': [round(float(t), 3) for t in s[:3]], 'sd_rot_deg': [round(float(np.degrees(t)), 3) for t in s[3:6]], 'sd_f_pct': round(float(100 * s[6]), 2)}
    for b in pr.lm:
        res['landmarks'][b] = {'xyz': [round(float(t), 4) for t in x[pr.li[b]]], 'sd_mm': [round(float(1000 * t), 1) for t in sd[pr.li[b]]]}
    for g in pr.rimg:
        res['rims'][g] = {'abs_y': round(float(x[pr.ri[g]][0]), 4), 'r': round(float(x[pr.ri[g]][1]), 4), 'sd_mm': [round(float(1000 * t), 1) for t in sd[pr.ri[g]]]}
    res['axle_z'] = {k: round(float(x[i]), 4) for k, i in pr.zi.items()}
    res['steer_deg'] = {k: round(float(np.degrees(x[i])), 2) for k, i in pr.si.items()}
    res['observations'] = [[r_[0], r_[1]] + [round(float(v), 2) for v in r_[2:]] for r_ in rows]
    json.dump(res, open(os.path.join(HERE, 'result.json'), 'w'), indent=1, default=lambda o: o.tolist() if hasattr(o, 'tolist') else float(o))
    print('sigma0 %.3f' % res['sigma0'])
    print('%-7s %4s  %13s  %13s   %s' % ('photo', 'n', 'rms / max px', 'old cam', 'lens mm, loc'))
    for n in pr.cn:
        c = res['cameras'][n]
        old = '%5.1f / %5.1f' % (c['old_rms_px'], c['old_max_px']) if c['old_rms_px'] is not None else '      new    '
        print('%-7s %4d  %5.2f / %5.2f  %s   %6.1f  %s' % (n, c['n'], c['rms_px'], c['max_px'], old, c['view'][2], np.round(c['view'][0], 2)))
    return res


if __name__ == '__main__':
    main('--quiet' in sys.argv)
