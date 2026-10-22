"""numpy-only (no bpy): R1d2 report of the soft arc (design2.fold_section = the cross-sections the shoulder / rear_shoulder rows are sampled from).

  python3 fold_report.py [out.png]

prints per station: net turn T across the arc (deg), the roll's turn theta, the barrel B2, the roll length ell (cm), its minimum radius (cm), the arc path error against the reading (3-D distance of the roll's centre to the
reading ARC_K, cm), the angle between the sliver's end tangent and the door-glass strip at U (G1, deg) and the slope of the shoulder leg at L;
plot (1500 x 1500): 3 x 3 cross-sections (y outboard to the LEFT, the car centre line to the right, z up; 1 m = 900 px) at x = .894 .956 1.057 1.2 1.5 1.8 2.0 2.2 2.35: white = the fold's section L -> upper end,
red dots = the roll's two ends, orange dot = the roll's centre (the arc), cyan cross = the reading, blue line = the door-glass strip U -> wl (forward of the tip), dim grey = the 5 cm grid."""
import sys, os, math
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import design2 as D
import imgio
from fold_fit import reading_dist

D.build_all()
K = D.CURVES
deg = math.degrees


def table():
    import shell2 as S
    X = S.XS
    print('  x      T(deg) theta  B2    ell(cm)  Rmin(cm) | path error (cm) | end slope / glass strip (deg), G1 gap | shoulder leg slope at L (deg)')
    mx = 0.0
    rows = []
    for x in X[(X >= D.X_FOLD0 - 1e-9) & (X <= 2.381)]:
        sol = D.fold_section(float(x))
        ap = D.fold_apex(sol)[0]
        d3 = reading_dist(ap)
        mx = max(mx, d3)
        Rmin = 1.0 / max(np.abs(sol['kap']).max(), 1e-9)
        g = deg(D.fold_glass_dir(float(x))) if x <= D.X_TIP + 1e-9 else float('nan')
        gap = deg(sol['phi'][-1]) - g if x <= D.X_TIP + 1e-9 else float('nan')
        rows.append((float(x), deg(sol['T']), deg(sol['th']), deg(sol['B2']), 100 * sol['ell'], 100 * Rmin, 100 * d3, deg(sol['phi'][-1]), g, gap, deg(sol['phi'][0])))
    for r in rows:
        if abs(r[0] * 1000 % 60) < 21 or abs(r[0] - 1.2) < 1e-6 or abs(r[0] - 2.381) < 0.02:
            print('%6.3f %6.1f %6.1f %6.1f %7.1f %9.1f | %8.1f        | %6.1f / %6.1f   %+5.2f | %6.1f' % r)
    print('max path error %.1f cm;  stations with path error <= 3 cm: %d of %d' % (100 * 0 + max(r[6] for r in rows), sum(r[6] <= 3.0 for r in rows), len(rows)))
    big = [r for r in rows if r[5] < 5.0]
    print('roll radius < 5 cm at %d stations (x %.3f .. %.3f); min %.1f cm' % (len(big), min(r[0] for r in big), max(r[0] for r in big), min(r[5] for r in rows)) if big else 'roll radius >= 5 cm everywhere')
    return rows


def line(img, p, q, col):
    n = int(max(abs(q[0] - p[0]), abs(q[1] - p[1]))) + 1
    xs, ys = np.linspace(p[0], q[0], n).round().astype(int), np.linspace(p[1], q[1], n).round().astype(int)
    ok = (xs >= 0) & (xs < img.shape[1]) & (ys >= 0) & (ys < img.shape[0])
    img[ys[ok], xs[ok]] = col


def dot(img, p, col, r=4):
    x, y = int(round(p[0])), int(round(p[1]))
    img[max(y - r, 0):y + r + 1, max(x - r, 0):x + r + 1] = col


def plot(out):
    st = [0.894, 0.956, 1.057, 1.2, 1.5, 1.8, 2.0, 2.2, 2.35]
    W = 500
    img = np.full((3 * W, 3 * W, 3), 24, np.uint8)
    sc = 900.0
    for n, x in enumerate(st):
        cx0, cy0 = (n % 3) * W, (n // 3) * W
        sol = D.fold_section(float(x))
        a = sol['a']
        P = np.c_[sol['y'] + a[0], sol['z'] + a[1]]
        ctr = P.mean(0)
        to = lambda y, z: (cx0 + W / 2 - (y - ctr[0]) * sc, cy0 + W / 2 - (z - ctr[1]) * sc)           # outboard on the left
        for g in np.arange(-0.4, 0.41, 0.05):
            line(img, to(ctr[0] + g, ctr[1] - 0.4), to(ctr[0] + g, ctr[1] + 0.4), (46, 46, 46))
            line(img, to(ctr[0] - 0.4, ctr[1] + g), to(ctr[0] + 0.4, ctr[1] + g), (46, 46, 46))
        for i in range(len(P) - 1):
            line(img, to(*P[i]), to(*P[i + 1]), (240, 240, 240))
        if x <= D.X_TIP + 1e-9:
            U, wl = K['U'].at(x), K['wl'].at(x)
            line(img, to(U[1], U[2]), to(wl[1], wl[2]), (80, 140, 255))
        for sv, col in ((sol['sc'] - 0.5 * sol['ell'], (255, 60, 60)), (sol['sc'] + 0.5 * sol['ell'], (255, 60, 60)), (sol['sc'], (255, 160, 0))):
            p = D.fold_points(sol, np.array([sv]))[0]
            dot(img, to(p[1], p[2]), col)
        r = K['arc_reading'].at(x)
        c = to(r[1], r[2])
        line(img, (c[0] - 7, c[1]), (c[0] + 7, c[1]), (60, 220, 255)); line(img, (c[0], c[1] - 7), (c[0], c[1] + 7), (60, 220, 255))
        line(img, (cx0, cy0), (cx0 + W - 1, cy0), (90, 90, 90)); line(img, (cx0, cy0), (cx0, cy0 + W - 1), (90, 90, 90))
    imgio.write(out, img)
    print('plot ->', out)


if __name__ == '__main__':
    table()
    plot(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, '..', '..', 'shots', 'full_rework', 'r1d2', 'fold_sections.png'))
