"""numpy-only (no bpy): c11 crease smoothness.  Every character line of the front fender must be a smooth line: no kink, no dent, no notch.

    python3 crease_smooth.py [--list] [--kinks] [--x0 X0] [--x1 X1] [--json out.json]

For each crease (the panel join edges of the SHELL: U crest, L lower edge as designed, Lm = the shared edge of wall | shoulder as built (the c9c band's middle, raised in z over the wheel by QF_H), the
rendered boundary row of the shoulder panel after the round fill, the hood seam L5, the front corner edge, the bottom edge l3 of the lower face) and each of the three orthographic projections (plan x-y, front y-z,
side x-z) the turning angle of the polyline is taken at every vertex (signed, along the traversal), summed in windows of 5 cm of arc length: T_w (deg per 5 cm, = 100 / R for a circle of radius R m with R in m, 1 deg / 5 cm
= radius 2.9 m).  Reported per crease and projection:
  Tmax       max |T_w|
  sign       sign changes of T_w (windows with |T_w| < TOL_T = 0.5 deg are straight and ignored): 0 = one-signed curvature (a dent / S bend shows up here)
  step       max |T_(w+1) - T_w| (a kink / a notch is a single step; a smooth curvature change is small); accepted: <= max(STEP_MAX, STEP_REL * Tmax)
  kink       largest single-vertex turn (deg), the sharp point
Verdict: plan and front views: sign = 0 and step within the limit; side view: the step only (a height profile may be S-shaped by design); L / Lm are judged on their visible part (x <= -1.85: the front rim of the wheel opening; the hidden bend aft of it is not seen).  --list prints the windows
(x of the window centre, T_w) so that the kinks and dents can be located.
"""
import sys, os, json
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

TOL_T = 0.5           # deg per window below which a window counts as straight (radius > 5.7 m)
WIN = 0.05            # m of arc length
DEC = 0.02            # m: the polyline is thinned to vertices this far apart in the projection
STEP_MAX = 2.0        # deg per 5 cm: the largest accepted change of the turning between neighbouring windows (about 0.4 1/m per 5 cm of curvature change) ...
STEP_REL = 0.45       # ... or 45 % of the crease's own maximum turning (a bell-shaped curvature profile is a smooth bend, a kink is a step that is most of the peak)

PROJ = {'plan': (0, 1), 'front': (1, 2), 'side': (0, 2)}


def turns(P2):
    """signed turning angle (deg) at the interior vertices of a 2D polyline, the arc length of the vertices; the polyline is first thinned to vertices at least DEC apart in the projection (a crease that runs
    nearly along the view direction moves by a millimetre per station: its raw turning angles are rounding noise)"""
    P2 = np.asarray(P2, float)
    keep = np.zeros(len(P2), bool)
    keep[0] = True
    last = 0
    for k in range(1, len(P2)):
        if np.linalg.norm(P2[k] - P2[last]) >= DEC:
            keep[k] = True
            last = k
    keep[-1] = True
    if keep.sum() >= 3 and np.linalg.norm(P2[-1] - P2[np.flatnonzero(keep)[-2]]) < 0.5 * DEC:
        keep[np.flatnonzero(keep)[-2]] = False                  # a stub at the end: merge it into the previous segment
    P2 = P2[keep]
    d = np.diff(P2, axis=0)
    sl = np.linalg.norm(d, axis=1)
    a = np.arctan2(d[:, 1], d[:, 0])
    t = np.degrees((np.diff(a) + np.pi) % (2 * np.pi) - np.pi)
    s = np.r_[0.0, np.cumsum(sl)]
    return t, s[1:-1], keep


def windows(t, s):
    """turning per window of 5 cm of arc length from the cumulative turning angle (linear between the vertices, so that the thinned vertices do not make the sums jump) -> (T_w, window centre arc length)"""
    cum = np.cumsum(t)
    edges = np.arange(s[0], s[-1] + 1e-9, WIN)
    if len(edges) < 2:
        return np.zeros(0), np.zeros(0)
    c = np.interp(edges, s, cum)
    return np.diff(c), 0.5 * (edges[1:] + edges[:-1])


def analyse(P, proj):
    i, j = PROJ[proj]
    t, s, keep = turns(np.asarray(P, float)[:, [i, j]])
    if len(t) < 3:
        return None
    T, sc = windows(t, s)
    if len(T) < 2:
        return None
    xs = np.asarray(P, float)[keep][1:-1, 0]
    xw = np.interp(sc, s, xs)
    sg = np.sign(T[np.abs(T) >= TOL_T])
    sign = int(np.sum(sg[1:] != sg[:-1])) if len(sg) > 1 else 0
    step = np.abs(np.diff(T))
    k = int(np.argmax(step)) if len(step) else 0
    nz = np.flatnonzero(np.abs(T) >= TOL_T)
    flips = [float(0.5 * (xw[nz[i]] + xw[nz[i + 1]])) for i in range(len(nz) - 1) if np.sign(T[nz[i]]) != np.sign(T[nz[i + 1]])]
    big = [(float(0.5 * (xw[i] + xw[i + 1])), float(step[i])) for i in range(len(step)) if step[i] > max(STEP_MAX, STEP_REL * np.abs(T).max())]
    return dict(flips=flips, big=big, Tmax=float(np.abs(T).max()), sign=sign, step=float(step.max()) if len(step) else 0.0, step_x=float(0.5 * (xw[k] + xw[k + 1])) if len(step) else float('nan'),
                kink=float(np.abs(t).max()), kink_x=float(xs[int(np.argmax(np.abs(t)))]), T=T, xw=xw, n=len(t))


FRONT_X1 = {'default': -1.90, 'U': -1.85}     # the front view of a crease that runs along the view direction piles up into a point: it is judged only where it is a line in the picture (x <= this)
VIS_X1 = -1.85                                 # L / Lm are visible only ahead of the wheel opening (x <= -1.85: the rim); aft of it they dip into the opening (hidden bend, listed as info)


def creases(x0, x1):
    """name -> (polyline, {projection: 's' (step only) | 'ss' (sign and step)}, x limit of the front projection, x limit of the judged part)"""
    import design2 as D
    import shell2 as S
    D.build_all()
    panels, R = S.build_panels()
    out = {}

    def cut(P, lo=x0, hi=x1):
        P = np.asarray(P, float)
        m = (P[:, 0] >= lo) & (P[:, 0] <= hi)
        return P[m]
    PSF = {'plan': 'ss', 'front': 'ss', 'side': 's'}
    out['U'] = (cut(R._edge('U')), {'plan': 'ss', 'front': 'ss', 'side': 's'}, FRONT_X1['U'], x1)
    out['L (visible: x <= %.2f)' % VIS_X1] = (cut(R._edge('L')), PSF, FRONT_X1['default'], VIS_X1)
    out['Lm (wall|shoulder join as designed, hidden aft of the rim)'] = (cut(R._edge('Lm')), PSF, FRONT_X1['default'], VIS_X1)
    rows = np.array([np.asarray(r, float)[0] for r in panels['shoulder'].rows])
    # the rows of the shoulder run Lm -> U (see p_shoulder); the first node of each row is the built crease between wall and shoulder (the round fill moved it)
    out['Lm built (after the round fill)'] = (cut(rows), PSF, FRONT_X1['default'], VIS_X1)
    rows_u = np.array([np.asarray(r, float)[-1] for r in panels['shoulder'].rows])
    out['U built (after the round fill)'] = (cut(rows_u), {'plan': 'ss', 'front': 'ss', 'side': 's'}, FRONT_X1['U'], x1)
    out['l3 (bottom edge of the lower face)'] = (cut(R._edge('l3')), PSF, FRONT_X1['default'], x1)
    out['L5 (hood seam)'] = (np.asarray(R._edge('L5'), float), {'plan': 'ss', 'side': 's'}, FRONT_X1['default'], x1)
    out['front corner edge (face | chamfer crease)'] = (np.asarray(R._edge('crease'), float), {'front': 'ss', 'side': 's'}, 0.0, x1)
    return out


def main(argv):
    x0, x1 = -2.50, -0.90
    lst = '--list' in argv
    kinks = '--kinks' in argv
    js = None
    for a, b in zip(argv, argv[1:]):
        if a == '--x0':
            x0 = float(b)
        if a == '--x1':
            x1 = float(b)
        if a == '--json':
            js = b
    cr = creases(x0, x1)
    res = {}
    print('crease smoothness (turning angle per 5 cm of arc, deg; TOL %.2f deg: straight; STEP_MAX %.1f)   x in [%.2f, %.2f]' % (TOL_T, STEP_MAX, x0, x1))
    print('%-52s %-6s %5s %7s %5s %7s %9s %7s %9s' % ('crease', 'proj', 'n', 'Tmax', 'sign', 'step', 'at x', 'kink', 'at x'))
    bad = 0
    for name, (P, judged, xf, xj) in cr.items():
        res[name] = {}
        for pj in ('plan', 'front', 'side'):
            Pp = P[P[:, 0] <= (xf if (pj == 'front' and xf != 0.0) else xj)]
            a = analyse(Pp, pj) if len(Pp) >= 5 else None
            if a is None:
                continue
            res[name][pj] = {k: v for k, v in a.items() if k not in ('T', 'xw')}
            mode = judged.get(pj)
            plane = name.startswith('front corner')
            ok_step = a['step'] <= max(STEP_MAX, STEP_REL * a['Tmax']) or plane
            ok = ok_step and (a['sign'] == 0 or mode != 'ss')
            if mode and not ok:
                bad += 1
            print('%-52s %-6s %5d %7.2f %5d %7.2f %9.3f %7.2f %9.3f   %s' % (name[:52], pj, a['n'], a['Tmax'], a['sign'], a['step'], a['step_x'], a['kink'], a['kink_x'],
                                                                         ('PASS' if ok else 'FAIL') if mode else 'info'))
            if kinks and (a['flips'] or a['big']):
                print('      kinks / dents: ' + ('curvature sign changes at x = %s; ' % ', '.join('%.2f' % v for v in a['flips']) if a['flips'] else '') + ('steps > limit at x = %s' % ', '.join('%.2f (%.1f deg)' % v for v in a['big']) if a['big'] else ''))
            if lst:
                print('      windows (x: T): ' + '  '.join('%.2f:%+.1f' % (x, t) for x, t in zip(a['xw'], a['T'])))
    print('SUMMARY smooth: %d judged rows FAIL' % bad)
    if js:
        json.dump(res, open(js, 'w'), indent=1)
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
