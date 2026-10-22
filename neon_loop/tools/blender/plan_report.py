"""numpy-only (no bpy): R1e2 plan report of the nose edge curves L (lower edge of the wall / the nose chamfer) and U (the crest) from the nose corner N to the straight side:
curvature table (signed plan curvature k = y'' / (1 + y'^2)^1.5, 1/m, convex = negative), inflection count, monotone-curvature check, the G2 join (value / slope / curvature of the new fit and of the old curve at the join),
residual of L's plan against the photo outline points (design2.PHOTO_CORNER), and a plot (no text: layout stated below).

    python3 plan_report.py [out.png]

Plot (1500 x 900 px): left = the plan (x right = aft, y up = outboard; 1 m = 800 px; bright red = L, dim red = the R1e L, blue = U, white dots = photo outline points, grey grid every 0.1 m, the vertical white line = the join X_JL);
right = geometric curvature -k(x) (convex = positive) of L (red), the R1e L (dim red) and U (blue) against x, 0 .. 3 1/m (grid every 0.5, bright every 1), x = N .. N + 0.9 m, the white vertical = X_JL."""
import sys, os
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import design2 as D
import imgio

D.build_all()
K = D.CURVES
xN, XJ = float(D.N[0]), D.X_JL


def kappa(f, xs):
    d1 = np.gradient(np.asarray(f(xs), float), xs)
    d2 = np.gradient(d1, xs)
    return d2 / (1 + d1 * d1) ** 1.5


def kap5(f, x):
    """geometric curvature at x from 5 samples 2.5 mm apart (x pushed inside the curve's start)"""
    x = max(float(x), xN + 6e-3)
    return float(kappa(f, x + 2.5e-3 * np.arange(-2, 3))[2])


def report(name, c, x_hi, join_x):
    xs = np.linspace(xN, x_hi, 800)
    k = kappa(c.fy, xs)
    kk = k[4:-4]
    sg = np.sign(kk[np.abs(kk) > 0.02])
    infl = int(np.sum(sg[1:] != sg[:-1])) if len(sg) > 1 else 0
    a = np.abs(kk)
    pk = int(np.argmax(a))
    d = np.diff(a)
    rises_after_peak = float(d[pk:].max()) if pk < len(d) else 0.0
    falls_before_peak = float(d[:pk].min()) if pk > 0 else 0.0
    print(f'--- {name}: plan y(x) from N (x {xN:.3f}) to x {x_hi:.2f}; modified up to x {join_x:.3f}')
    print('    inflections (sign changes of the curvature, |k| > 0.02):', infl, '   curvature: at N %.2f 1/m, PEAK %.2f 1/m (R %.0f mm) at x %.3f, at the join %.2f 1/m' % (a[0], a[pk], 1000 / a[pk], xs[4 + pk], kap5(c.fy, join_x) * -1))
    print('    one peak: largest fall before the peak %.4f, largest rise after it %.4f (1/m per 1.2 mm sample; a dip would show as a fall before / a rise after)' % (falls_before_peak, rises_after_peak))
    for x in np.arange(xN, x_hi + 1e-9, 0.05):
        kx = kap5(c.fy, x)
        print('    x %+6.3f  y %.4f  y\' %+6.3f  k %+7.3f 1/m  R %7.0f mm' % (x, float(c.fy(x)), float((c.fy(x + 1e-4) - c.fy(x - 1e-4)) / 2e-4), kx, 1000 / max(abs(kx), 1e-9)))
    return xs, k


def join_check(new, old, xj, label):
    e = 1e-3
    a = (float(new.fy(xj - e)), float((new.fy(xj - e + 1e-4) - new.fy(xj - e - 1e-4)) / 2e-4), kap5(new.fy, xj - 8e-3))
    b = (float(old.fy(xj + e)), float((old.fy(xj + e + 1e-4) - old.fy(xj + e - 1e-4)) / 2e-4), kap5(old.fy, xj + 8e-3))
    print(f'    {label} join x {xj}: value  new {a[0]:.5f} old {b[0]:.5f}   slope  {a[1]:+.4f} / {b[1]:+.4f}   curvature  {a[2]:+.3f} / {b[2]:+.3f} 1/m')


def line(img, p, q, col):
    n = int(max(abs(q[0] - p[0]), abs(q[1] - p[1]))) + 1
    xs, ys = np.linspace(p[0], q[0], n).round().astype(int), np.linspace(p[1], q[1], n).round().astype(int)
    ok = (xs >= 0) & (xs < img.shape[1]) & (ys >= 0) & (ys < img.shape[0])
    img[ys[ok], xs[ok]] = col


def poly(img, P, col):
    for a, b in zip(P[:-1], P[1:]):
        line(img, a, b, col)


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, '..', '..', 'shots', 'full_rework', 'r1e2', 'plan_curvature.png')
    L, U = K['L'], K['U']
    xs_L, kL = report('L (lower edge; the corner chamfer)', L, -1.40, XJ)
    xjU = D.NOSE_FIT['xjU']
    xs_U, kU = report('U (crest)', U, -1.80, xjU)
    print('--- G2 joins (new curve at the join vs the old curve)')
    join_check(L, K['L_old'], XJ, 'L')
    join_check(U, K['U_old'], xjU, 'U')
    if '--fine' in sys.argv:          # --fine x0,x1: curvature -k (1/m) of U, U_old, L, L_old every 10 mm
        a, b = [float(v) for v in sys.argv[sys.argv.index('--fine') + 1].split(',')]
        print('--- fine: x, -k of U / U_old / L / L_old (1/m)')
        for x in np.arange(a, b + 1e-9, 0.01):
            print('    x %+6.3f   U %6.3f  U_old %6.3f   L %6.3f  L_old %6.3f' % (x, -kap5(U.fy, x), -kap5(K['U_old'].fy, x), -kap5(L.fy, x), -kap5(K['L_old'].fy, x)))
    P = np.array(D.photo_corner(xN, float(D.N[1])), float)
    e = np.array([abs(float(L.fy(x)) - y) for x, y in P if xN < x < XJ])
    ed = np.array([float(np.min(np.hypot(P[:, 0] - x, P[:, 1] - float(L.fy(x))))) for x in np.linspace(xN, XJ, 200)])
    print('--- L plan vs the photo outline points (p013, %d points): mean |dy| %.1f mm, max %.1f mm (vertical); mean distance model-curve -> outline points %.1f mm, max %.1f mm' % (len(e), 1000 * e.mean(), 1000 * e.max(), 1000 * ed.mean(), 1000 * ed.max()))
    print('    old R1e L plan vs the same points: mean |dy| %.1f mm' % (1000 * np.mean([abs(float(K['L_old'].fy(x)) - y) for x, y in P if xN < x < XJ])))
    # ---- plot
    W, H = 1500, 900
    img = np.full((H, W, 3), 24, np.uint8)
    sx = 800.0
    to = lambda x, y: (60 + (x - xN) * sx, 860 - (y - 0.64) * sx)
    for t in np.arange(0, 0.81, 0.1):
        line(img, to(xN + t, 0.64), to(xN + t, 1.14), (60, 60, 60))
    for yv in np.arange(0.64, 1.15, 0.1):
        line(img, to(xN, yv), to(xN + 0.8, yv), (60, 60, 60))
    xs = np.linspace(xN, xN + 0.8, 300)
    poly(img, [to(x, float(L.fy(x))) for x in xs], (240, 60, 60))
    poly(img, [to(x, float(U.fy(x))) for x in xs], (80, 140, 255))
    poly(img, [to(x, float(K['L_old'].fy(max(x, K['L_old'].x0)))) for x in xs], (120, 70, 70))
    poly(img, [to(x, float(K['U_old'].fy(max(x, K['U_old'].x0)))) for x in xs], (60, 80, 130))
    for x, y in P:
        px, py = to(x, y)
        img[int(py) - 2:int(py) + 3, int(px) - 2:int(px) + 3] = 255
    line(img, to(XJ, 0.64), to(XJ, 1.14), (255, 255, 255))
    gx0, gx1, gy0, gy1 = 760, 1440, 80, 840                    # curvature plot frame: -k (convex = positive) 0 .. 3 1/m
    ky = lambda v: gy1 - v / 3.0 * (gy1 - gy0)
    kx = lambda x: gx0 + (x - xN) / 0.9 * (gx1 - gx0)
    for v in np.arange(0, 3.01, 0.5):
        line(img, (gx0, ky(v)), (gx1, ky(v)), (90, 90, 90) if v == int(v) else (50, 50, 50))
    for t in np.arange(0, 0.91, 0.1):
        line(img, (kx(xN + t), gy0), (kx(xN + t), gy1), (50, 50, 50))
    line(img, (kx(XJ), gy0), (kx(XJ), gy1), (255, 255, 255))
    xo = np.linspace(xN + 0.01, xN + 0.9, 400)
    poly(img, [(kx(x), ky(-kap5(K['L_old'].fy, x))) for x in xo], (120, 70, 70))
    poly(img, [(kx(x), ky(-kap5(K['U_old'].fy, x))) for x in xo], (60, 80, 130))
    poly(img, [(kx(x), ky(-kap5(L.fy, x))) for x in xo], (240, 60, 60))
    poly(img, [(kx(x), ky(-kap5(U.fy, x))) for x in xo], (80, 140, 255))
    imgio.write(out, img)
    print('plot ->', out)


if __name__ == '__main__':
    main()
