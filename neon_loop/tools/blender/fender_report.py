"""numpy-only: the front fender's three faces (fender3 round) measured on the DESIGN curves (no build needed):
    python3 fender_report.py [--json out.json] [--design <dir>]

  U profile   side view z(x) of the crest U: the slope dz/dx must fall monotonically (concave); p016 projection: the signed curvature of U must not change sign (the photo's line 2 is one gentle parabola)
  rows        the fender top is a ruled surface, row k joins L5[k] with U[k]: height difference U - L5 and the tilt of the row (deg, + = rising outward) at U's x = -2.0 / -1.8 / -1.6 and the minimum over the rows
  p016        the coordinator's readings of the photo lines 1-4 (L5 / U / L / wheel arch circle) against the model: perpendicular distance in px
  p018        the crest U projected through the p018 camera against the photo's top edge (first bright run from the top, lum > 110), columns of x -2.40 ... -1.55: residual in px (+ = photo lower)
"""
import sys, os, json, math
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
_design = os.path.abspath(sys.argv[sys.argv.index('--design') + 1]) if '--design' in sys.argv else HERE         # --design <dir>: design2.py / shell2.py of an older state (the BEFORE numbers: ../backup/pre_fender3/blender)
sys.path.insert(0, HERE)
sys.path.insert(0, _design)
import design2 as D, shell2 as S, cam as C, imgio

REFS = os.path.abspath(os.path.join(HERE, '..', '..', '..', 'refs', 'press2'))
LINES16 = {                                  # coordinator's reading of p016 (1800 x 1200 px)
    '1 L5 (hood edge)': [(715, 688), (738, 654), (757, 623), (780, 592), (822, 552)],
    '2 U (crest)': [(730, 680), (770, 652), (810, 628), (850, 604), (890, 580), (930, 562), (970, 540), (1010, 530), (1060, 527)],
    '3 L (mid / low)': [(718, 690), (770, 676), (850, 662), (930, 644), (970, 630), (995, 626)],
    '4 wheel arch': [(972, 780), (984, 673), (999, 627), (1026, 592), (1065, 575), (1103, 588), (1130, 627)],
}


def _dist_poly(p, Q):
    best = 1e9
    for a, b in zip(Q[:-1], Q[1:]):
        ab = b - a
        t = np.clip(((p - a) @ ab) / (ab @ ab + 1e-12), 0, 1)
        best = min(best, float(np.linalg.norm(p - (a + t * ab))))
    return best


def profile(rep):
    U = D.CURVES['U']
    xs = np.linspace(D.N[0] + 0.01, -1.0, 400)
    P = U.at(xs)
    dz = np.gradient(P[:, 2], xs)
    d2 = np.gradient(dz, xs)
    bad = xs[3:-3][d2[3:-3] > 0.02]
    sel_ = xs <= -1.43
    rise = float(np.max(np.maximum.accumulate(dz[sel_][::-1])[::-1] - dz[sel_]) ) if sel_.any() else 0.0        # the largest fall-then-rise of the slope aft of a given point (in dz/dx)
    rise = float(max(0.0, np.max(dz[sel_][1:] - np.minimum.accumulate(dz[sel_])[:-1])))
    print('  largest rise of the slope after a fall (x <= -1.43): %.3f (a z error of %.1f mm at most)' % (rise, rise * 0.1 * 1e3 / 2))
    rep['u_side_slope_rise'] = rise
    print('U side view  z slope dz/dx at x -2.4 / -2.2 / -2.0 / -1.8 / -1.6 / -1.43: ' + ' '.join('%.3f' % dz[int(np.argmin(abs(xs - x)))] for x in (-2.4, -2.2, -2.0, -1.8, -1.6, -1.43)))
    print('  slope rises (d2z > 0.02 1/m) at x: %s' % (('%.2f..%.2f' % (bad.min(), bad.max())) if len(bad) else 'nowhere (monotone, concave)'))
    rep['u_side_slope_rise_x'] = [float(bad.min()), float(bad.max())] if len(bad) else None
    cm = C.Cam('p016')
    Q = cm.project(P * [1, -1, 1])
    dq = np.gradient(Q, axis=0)
    d2q = np.gradient(dq, axis=0)
    k = (dq[:, 0] * d2q[:, 1] - dq[:, 1] * d2q[:, 0]) / (np.hypot(dq[:, 0], dq[:, 1]) ** 3 + 1e-12)
    sl = dq[:, 1] / dq[:, 0]
    sel = (xs >= D.N[0] + 0.05) & (xs <= -1.3)
    ks = k[sel]
    ign = np.abs(ks) < 4e-4                                              # numerically straight: not a sign
    sg = np.sign(ks[~ign])
    ch = int(np.sum(np.diff(sg) != 0))
    print('U in p016    image slope at x -2.4 / -2.2 / -2.0 / -1.8 / -1.6 / -1.43: ' + ' '.join('%.2f' % sl[int(np.argmin(abs(xs - x)))] for x in (-2.4, -2.2, -2.0, -1.8, -1.6, -1.43)) + '   (photo: -0.7 ... 0, slowing)')
    print('  curvature sign changes N..x -1.3: %d   (target 0)' % ch)
    rep['u_p016_curv_sign_changes'] = ch
    rep['u_p016_slope_peak'] = float(np.abs(sl[sel]).max())


def rows(rep):
    """height of the crest U over the hood edge L5 at the same x (the hood is flat across the car at each x, so this is the lean of the top face): dz and the angle atan(dz / dy)"""
    U = D.CURVES['U']
    N_, W_ = np.array(D.N, float), np.array(D.W, float)
    yl5 = lambda x: N_[1] + (W_[1] - N_[1]) * (x - N_[0]) / (W_[0] - N_[0])
    zl5 = lambda x: N_[2] + (W_[2] - N_[2]) * (x - N_[0]) / (W_[0] - N_[0]) + float(D.hood_sag((x - N_[0]) / (W_[0] - N_[0])))      # (L5's own bow: QF_L5_FIT / QF_HOOD_SAG)
    out = {}
    print('top face lean  U - inner edge at the same x  (inner edge = L5, aft of its end W (x %.3f) the cowl diagonal W -> A_OUT)' % W_[0])
    A_ = np.array(D.A_OUT, float)

    def inner(x):                    # the inner edge of the top face at x: L5 up to the cowl corner W, aft of it the cowl diagonal W -> A_OUT (the glass's lower edge)
        if x <= W_[0] + 1e-9:
            return yl5(x), zl5(x)
        t = (x - W_[0]) / (A_[0] - W_[0])
        return W_[1] + t * (A_[1] - W_[1]), W_[2] + t * (A_[2] - W_[2])
    for x in (-2.0, -1.8, -1.625, -1.5):
        u = U.at(x)
        yi, zi = inner(x)
        dz, dy = float(u[2] - zi), float(u[1] - yi)
        print('  x %.3f   dz %+6.1f mm   dy %.3f   lean %+5.2f deg' % (x, dz * 1e3, dy, math.degrees(math.atan2(dz, dy))))
        out['%.3f' % x] = dict(dz_mm=dz * 1e3, lean=math.degrees(math.atan2(dz, dy)))
    xs = np.linspace(-2.3, A_[0], 120)
    u = U.at(xs)
    dz = u[:, 2] - np.array([inner(x)[1] for x in xs])
    print('  min over x -2.3 .. %.3f: dz %+6.1f mm at x %.2f' % (A_[0], dz.min() * 1e3, xs[int(np.argmin(dz))]))
    out['min_dz_mm'] = float(dz.min() * 1e3)
    rep['lean'] = out


def p016(rep):
    cm = C.Cam('p016')
    U, L = D.CURVES['U'], D.CURVES['L']
    n = D.NOSE['curves']
    mod = {'1 L5 (hood edge)': cm.project(np.asarray(n['L5']) * [1, -1, 1]),
           '2 U (crest)': cm.project(U.at(np.linspace(D.N[0], -1.0, 300)) * [1, -1, 1]),
           '3 L (mid / low)': cm.project(L.at(np.linspace(D.N[0], -1.3, 300)) * [1, -1, 1])}
    th = np.linspace(0, 2 * np.pi, 2000)
    mod['4 wheel arch'] = cm.project(np.stack([-1.487 + D.R_ARCH * np.sin(th), np.full_like(th, -1.0), 0.39 + D.R_ARCH * np.cos(th)], 1)) if hasattr(D, 'R_ARCH') else cm.project(np.stack([-1.487 + 0.415 * np.sin(th), np.full_like(th, -1.0), 0.39 + 0.415 * np.cos(th)], 1))
    print('p016 residual of the photo lines (perpendicular px)')
    out = {}
    for name, pts in LINES16.items():
        d = [_dist_poly(np.array(p, float), mod[name]) for p in pts]
        print('  %-18s %s   mean %5.1f  max %5.1f' % (name, ' '.join('%4.0f' % v for v in d), np.mean(d), np.max(d)))
        out[name] = dict(mean=float(np.mean(d)), max=float(np.max(d)))
    rep['p016'] = out


def p018(rep):
    cm = C.Cam('p018')
    lum = imgio.read(os.path.join(REFS, 'tesla-roadster-2026-018.jpg')).astype(float).mean(-1)
    U = D.CURVES['U']
    xs = np.linspace(-2.40, -1.55, 400)
    Q = cm.project(U.at(xs) * [1, -1, 1])
    d, dc = [], []
    for c in range(int(Q[0, 0]) + 3, int(Q[-1, 0]) - 2, 4):
        col = lum[:, c]
        ok = np.where((col[:-2] > 110) & (col[1:-1] > 110) & (col[2:] > 110))[0]
        ok = ok[ok > 300]
        if not len(ok):
            continue
        mrow = float(np.interp(c, Q[:, 0], Q[:, 1]))
        d.append(int(ok[0]) - mrow)
        dc.append(float(np.interp(c, Q[:, 0], xs)))
    d = np.array(d)
    if os.environ.get('P18_LIST'):
        print('  p018 per-column (x: d px):', ' '.join('%.2f:%+.0f' % (a_, b_) for a_, b_ in list(zip(dc, d))[::3]))
    print('p018 crest U against the photo top edge (cols %d..%d): mean %+5.1f px  mean|d| %5.1f  max|d| %5.1f px   (+: photo lower = the model crest is higher than the photo)' % (Q[0, 0], Q[-1, 0], d.mean(), np.abs(d).mean(), np.abs(d).max()))
    rep['p018'] = dict(mean=float(d.mean()), mean_abs=float(np.abs(d).mean()), max_abs=float(np.abs(d).max()))


if __name__ == '__main__':
    rep = {}
    profile(rep)
    rows(rep)
    p016(rep)
    p018(rep)
    if '--json' in sys.argv:
        json.dump(rep, open(sys.argv[sys.argv.index('--json') + 1], 'w'), indent=1)
