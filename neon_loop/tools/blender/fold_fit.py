"""numpy-only: the design functions of the R1d2 soft arc (design2.FOLD_K): find the roll turn theta(x), the shoulder-leg bowl B1(x) and the fold position sc(x) so that the apex of the roll stays within
design2.FOLD_BAND of the reading (ARC_K) while (forward of the window tip) the inclined leg leaves U tangent to the door-glass strip, and print them as a FOLD_K literal.  Then evaluate the table.
      python3 fold_fit.py opt           knots (printed)       |       python3 fold_fit.py eval     (error table with the current FOLD_K: 3-D distance of the apex to the reading, theta, B2, radius)"""
import sys, os, math
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import design2 as D
D.build_all()
K = D.CURVES
deg = math.degrees
sstep = D.sstep


_RD = []


def reading_dist(P):
    """3-D distance of the point P to the reading polyline (dense samples of CURVES['arc_reading'])"""
    if not _RD:
        _RD.append(K['arc_reading'].at(np.linspace(0.85, 2.41, 1200)))
    d = np.linalg.norm(_RD[0] - P, axis=1)
    return float(d.min())


def best_sc(x, lo=0.25, hi=0.62):
    """the fold position sc (arclength from L) whose apex is nearest to the reading, for the CURRENT design functions T(x), B1(x): grid search + golden refinement"""
    def err(sc):
        try:
            sol = D.fold_section(x, sc=sc)
        except Exception:
            return 9.0
        if sol['res'] > 1e-7 or sol['S'] < sc + 0.004:
            return 9.0
        return reading_dist(D.fold_apex(sol)[0])
    g = np.linspace(lo, hi, 75)
    e = [err(v) for v in g]
    i = int(np.argmin(e))
    a, b = g[max(i - 1, 0)], g[min(i + 1, len(g) - 1)]
    for _ in range(25):
        c1, c2 = b - 0.618 * (b - a), a + 0.618 * (b - a)
        if err(c1) < err(c2):
            b = c2
        else:
            a = c1
    sc = 0.5 * (a + b)
    return sc, err(sc)


def opt():
    """sc knots: forward knots first (the aft family needs the tip state), then the aft ones"""
    xs_f = [0.874, 0.935, 0.996, 1.057, 1.118, 1.2]
    xs_a = [1.4, 1.7, 2.0, 2.2]
    D.FOLD_K['sc'] = [(0.874, 0.307), (1.2, 0.34), (2.382, 0.53)]
    D._FOLD.clear()
    out = []
    for x in xs_f:
        if x <= D.X_FOLD0 + 1e-9:
            L, U = K['L'].at(x)[1:], K['U'].at(x)[1:]
            out.append((x, round(float(np.hypot(*(U - L))), 4))); continue
        sc, e = best_sc(x)
        out.append((x, round(sc, 4)))
        print('fwd x=%.3f sc %.4f  err %.2f cm' % (x, sc, 100 * e), file=sys.stderr)
    D.FOLD_K['sc'] = out + [(2.382, 0.53)]
    D._FOLD.clear()
    for x in xs_a:
        sc, e = best_sc(x)
        out.append((x, round(sc, 4)))
        print('aft x=%.3f sc %.4f  err %.2f cm' % (x, sc, 100 * e), file=sys.stderr)
        D.FOLD_K['sc'] = sorted(out) + [(2.382, 0.53)]
        D._FOLD.clear()
    print("    sc=%s)" % [tuple(t) for t in sorted(out) + [(2.382, 0.53)]])


def evaluate():
    import shell2 as S
    X = S.XS
    print('  x      th    B1    B2    ell    Rmin(cm) | apex(y,z)            reading(y,z)   same-x d(cm)  3-D d(cm) | sliver end slope / glass | shoulder leg slope at L')
    mx = 0.0
    for x in X[(X >= D.X_FOLD0 - 1e-9) & (X <= 2.381)]:
        sol = D.fold_section(float(x))
        ap = D.fold_apex(sol)[0]
        R = K['arc_reading'].at(x)
        dsame = float(np.hypot(*(ap[1:] - R[1:])))
        d3 = reading_dist(ap)
        mx = max(mx, d3)
        k = np.abs(sol['kap'])
        Rmin = 1.0 / max(k.max(), 1e-9)
        g = deg(D.fold_glass_dir(x)) if x <= 1.2 + 1e-9 else float('nan')
        if abs(x * 1000 % 60) < 21 or x in (1.2,):
            print('%6.3f %5.1f %5.1f %6.1f %6.3f %8.1f | (%.3f, %.3f)   (%.3f, %.3f)   %5.1f      %5.1f   | %5.1f / %5.1f | %5.1f' % (x, deg(sol['th']), deg(sol['B1']), deg(sol['B2']), sol['ell'], 100 * Rmin, ap[1], ap[2], R[1], R[2], 100 * dsame, 100 * d3, deg(sol['phi'][-1]), g, deg(sol['phi'][0])))
    print('max 3-D distance of the apex to the reading: %.1f cm' % (100 * mx))


if __name__ == '__main__':
    {'opt': opt, 'eval': evaluate}[sys.argv[1] if len(sys.argv) > 1 else 'eval']()
