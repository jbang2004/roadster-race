"""
Smoothness of the shell under the phase-3 corrections (CALIB.md phase 3), numpy only:

  python3 tools/blender/smooth_report.py

1. JOINS: every correction is made of pieces (a spline times smoothstep windows, a blend box, a join to the old curve).  At each place where a piece starts, ends or changes,
   the correction d(x) = (new - old) of the line it acts on is differentiated on both sides (finite differences, step H) at two distances E and E/2 from the join.  The difference
   left - right of the slope / 2nd derivative is (step) + (smooth part, proportional to the distance), so the step is 2 D(E/2) - D(E): it stays for a kink or a curvature jump and
   vanishes for a C2 correction however steep.  Lines: L in plan (with the shell's position fields) and in elevation, l3 in plan and elevation, U in plan, the rear arch outline (radial
   offset along the arc).
2. PLANES: the panels that are planes by design (best-fit plane, max distance in mm) now and without the P3 switches.
The baseline (all P3 switches off) is computed by this script in a child process (the switches are read at import).
Output: one 'ROW|key|label|value|limit|ok' line per measure (check.py smooth turns them into a table) after a readable listing.
"""
import json
import os
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
H, E = float(os.environ.get('SMOOTH_H', '0.000125')), float(os.environ.get('SMOOTH_E', '0.0005'))      # finite-difference step, distance from the join (m)
SLOPE_TOL, CURV_TOL = 0.02, 0.05  # deg, 1/m
PLANES = {'corner_tri': 2.5, 'facet': 4.0}            # designed planes: max distance from the best-fit plane (mm); limits = the pre-P3 shell (1.4, 3.6 mm) plus margin
import re
R_ARCH = float(re.search(r'^R_ARCH = ([\d.]+)', open(os.path.join(HERE, 'common.py')).read(), re.M).group(1))     # (common.py itself needs bpy)
OFF = {k: '0' for k in ('QF_P3_L3', 'QF_P3_U', 'QF_P3_HIP', 'QF_P3_FRONT', 'QF_P3_LF', 'QF_P3_ARR', 'QF_P3_TAILX', 'QF_P3_L3Y', 'QF_P3_FRONT_DOOR', 'QF_MID_L3', 'QF_MID_LW')}


def lines_at(xs_by_line):
    """(x, value) samples of the measured lines under the current switches"""
    import shell2 as S
    C = S.C
    out = {}
    for name, xs in xs_by_line.items():
        cn, comp = name.split(':')
        if comp.startswith('d'):                # the rear-end extension (shell2.p3_dxyz) along the line, component dx / dy / dz (0 when QF_P3_TAILX is off)
            c = C[cn]
            xs = np.asarray([x for x in xs if c.x0 <= x <= c.x1], float)
            P = np.asarray(c.at(xs), float) if len(xs) else np.zeros((0, 3))
            k = 'xyz'.index(comp[1])
            out[name] = (list(xs), [float(S.p3_dxyz(p[0], p[1] + S.p3_dy(p[0], p[1], p[2]), p[2])[k]) for p in P])
            continue
        if cn == 'archR':                       # the rear arch outline: x = arc length (m) along the R_ARCH circle, value = radial offset (m)
            out[name] = (list(xs), [float(S.p3_arr(np.degrees(t / R_ARCH))) for t in xs])
            continue
        c = C[cn]
        xs = np.asarray([x for x in xs if c.x0 <= x <= c.x1], float)
        if not len(xs):
            out[name] = ([], [])
            continue
        P = np.asarray(c.at(xs), float)
        if comp == 'plan':
            v = [p[1] + S.p3_dy(p[0], p[1], p[2]) for p in P]
        else:
            v = list(P[:, 2])
        out[name] = (list(xs), [float(t) for t in v])
    return out


def planes():
    import shell2 as S
    pm, _ = S.build_panels(only=None)
    r = {}
    for k in PLANES:
        V = np.array([v[:3] for v in pm[k].verts], float)
        V = V + np.array([S.p3_dxyz(*p) for p in V])          # as exported (the rear-end extension is applied to the built car)
        c = V.mean(0)
        n = np.linalg.svd(V - c, full_matrices=False)[2][-1]
        r[k] = float(1000 * np.abs((V - c) @ n).max())
    return r


def joins():
    """the x stations where a correction piece starts / ends / changes, per line"""
    import shell2 as S
    import design2 as D
    J = {}
    hip = list(S.QF_P3_HIP_W) + [S.QF_P3_HIP_A[0][0], S.QF_P3_HIP_A[-1][0]]
    if S.QF_P3_HIP_FACET != '0':
        b = [float(v) for v in S.QF_P3_HIP_FACET.split(',')]
        hip += [b[0] - S.QF_P3_HIP_FM, b[0], b[1], b[1] + S.QF_P3_HIP_FM]
    front = list(S.QF_P3_FRONT_RISE) + list(S.QF_P3_FRONT_END) + [S.QF_P3_FRONT_A[0][0], S.QF_P3_FRONT_A[-1][0]] + (list(S.QF_P3_FRONT_DX) if S.QF_P3_FRONT_DOOR else [])
    fields = sorted(set(([round(x, 4) for x in hip] if S.QF_P3_HIP else []) + ([round(x, 4) for x in front] if S.QF_P3_FRONT else [])))
    J['L:plan'] = sorted(set(fields + (list(D.QF_MID_LW_X) if D.QF_MID_LW else [])))
    J['l3:plan'] = sorted(set(fields + (list(D.QF_P3_L3Y_X) if D.QF_P3_L3Y else []) + (list(D.QF_NOSE_L3X) if D.QF_NOSE_WIDE else []) + (list(D.QF_MID_L3_X) + [D.QF_MID_L3_END] if D.QF_MID_L3 else [])))
    J['L:elev'] = [D.QF_P3_LF_X1 - D.QF_P3_LF_JOIN, D.QF_P3_LF_X1] + [k[0] for k in D.QF_P3_LF_K] if D.QF_P3_LF else []
    J['l3:elev'] = list(D.QF_P3_L3X) if D.QF_P3_L3 else []
    J['U:plan'] = list(D.QF_P3_UX) if D.QF_P3_U else []
    J['archR:outline'] = [R_ARCH * np.radians(k[0]) for k in S.QF_P3_ARR_K] if S.QF_P3_ARR else []
    if S.QF_P3_TAILX:                           # the rear-end extension: every place along L / the crest / the deck centre where one of its ramps or blends passes a boundary
        e, W = S.QF_P3_TX_E, S.QF_P3_TX_W
        xd0, xd1 = S.QF_P3_TX_XD
        T = S._p3_hip_tables()
        for cn in ('L', 'rail', 'top'):
            c = S.C[cn]
            xs = np.linspace(max(c.x0, xd0 - 0.05), c.x1, 3000)
            P = np.asarray(c.at(xs), float)
            ts = [((p[0] + S.QF_P3_TX_K * (S._p3_zclamp(p[2]) - S.QF_P3_TX_Z0)) - (S.QF_P3_TX_XI1 - W)) / W for p in P]
            td = [(p[0] - xd0) / (xd1 - xd0) for p in P]
            wy = [abs(p[1]) for p in P]
            cross = []
            for t, lev in [(ts, v) for v in (0.0, e, 1 - e, 1.0)] + [(td, v) for v in (0.0, e, 1 - e, 1.0)] + [(wy, v) for v in S.QF_P3_TX_YW]:
                for i in range(len(xs) - 1):
                    if (t[i] - lev) * (t[i + 1] - lev) < 0.0:
                        cross.append(round(float(xs[i] + (lev - t[i]) / (t[i + 1] - t[i]) * (xs[i + 1] - xs[i])), 4))
            for comp in ('dx', 'dy', 'dz'):
                J['%s:%s' % (cn, comp)] = sorted(set(cross))
    return J


OFFS = sorted(set(round(sg * (e + k * H), 6) for sg in (-1, 1) for e in (E, E / 2) for k in (-1, 0, 1)))


def samples(J):
    return {k: [xj + o for xj in sorted(set(v)) for o in OFFS] for k, v in J.items()}


def steps(f, xj):
    """(slope step in rad, curvature step in 1/m) of f at xj; f(x) evaluates the sampled correction"""
    def d1(x):
        return (f(x + H) - f(x - H)) / (2 * H)

    def d2(x):
        return (f(x + H) - 2 * f(x) + f(x - H)) / H ** 2
    D1 = lambda e: d1(xj + e) - d1(xj - e)
    D2 = lambda e: d2(xj + e) - d2(xj - e)
    return abs(2 * D1(E / 2) - D1(E)), abs(2 * D2(E / 2) - D2(E))


def main():
    if '--child' in sys.argv:                       # baseline: the same samples with the P3 switches off
        S = json.loads(sys.argv[sys.argv.index('--child') + 1])
        print('CHILD' + json.dumps({'lines': lines_at(S), 'planes': {} if '--no-planes' in sys.argv else planes()}))
        return
    J = joins()
    S = samples(J)
    now = lines_at(S)
    env = dict(os.environ, **OFF)
    p = subprocess.run([sys.executable, os.path.abspath(__file__), '--child', json.dumps(S)] + (['--no-planes'] if '--no-planes' in sys.argv else []), capture_output=True, text=True, env=env, cwd=HERE)
    base = json.loads([l for l in p.stdout.splitlines() if l.startswith('CHILD')][0][5:])
    rows = []
    print('JOINS: correction d = new - old along each line, steps at every piece boundary (finite differences, %.1f mm step, %.0f / %.0f mm from the join)' % (H * 1e3, E * 1e3, E * 5e2))
    for name, xs in J.items():
        if not xs:
            continue
        va = dict(zip((round(x, 6) for x in now[name][0]), now[name][1]))
        vb = dict(zip((round(x, 6) for x in base['lines'][name][0]), base['lines'][name][1]))
        for xj in sorted(set(xs)):
            if any(round(xj + o, 6) not in va or round(xj + o, 6) not in vb for o in OFFS):
                continue                                # the line ends here: nothing on one side
            f = lambda x: va[round(x, 6)] - vb[round(x, 6)]
            s1, s2 = steps(f, xj)
            ds, dk = np.degrees(s1), s2
            print('  %-8s x %+6.3f   d %+7.2f mm   slope step %.4f deg   curvature step %.4f 1/m' % (name, xj, 1000 * f(xj + E), ds, dk))
            rows.append(('smooth:%s@%.3f slope' % (name, xj), '%s x %+.3f slope step (deg)' % (name, xj), '%.3f' % ds, SLOPE_TOL, ds <= SLOPE_TOL))
            rows.append(('smooth:%s@%.3f curv' % (name, xj), '%s x %+.3f curvature step (1/m)' % (name, xj), '%.3f' % dk, CURV_TOL, dk <= CURV_TOL))
    if '--no-planes' in sys.argv:
        pl = None
    else:
        pl = planes()
    print('PLANES: max distance from the best-fit plane (mm), now / without P3')
    for k, lim in (PLANES.items() if pl else ()):
        print('  %-12s %6.2f / %6.2f' % (k, pl[k], base['planes'][k]))
        rows.append(('smooth:plane %s' % k, '%s planarity (mm; %.2f without P3)' % (k, base['planes'][k]), '%.2f' % pl[k], lim, pl[k] <= lim))
    for r in rows:
        print('ROW|%s|%s|%s|%s|%d' % (r[0], r[1], r[2], r[3], int(r[4])))


if __name__ == '__main__':
    main()
