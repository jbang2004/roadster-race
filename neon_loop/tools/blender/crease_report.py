"""numpy-only: dihedral angle (degrees) along every shared boundary between two panels of the shell (shell2.build_panels + assemble): per panel pair min / mean / max and the straightness of the join (max distance of its vertices from their best-fit line, mm; right half),
and whether bevel_creases would fillet it (> 3 degrees and not a SMOOTH_PAIR).      python3 crease_report.py [panelA,panelB,...|-] [x0 x1]   (only pairs touching these panels; x0 x1: window of the straightness column)"""
import sys, os, math, numpy as np
SIGNED = '--signed' in sys.argv          # apillar: also the SIGNED dihedral (+ convex ridge, - concave valley): min / max and how many edges are ridge / valley
if SIGNED:
    sys.argv.remove('--signed')
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import shell2 as S
panels, R = S.build_panels()
V, F, M, PID, names = S.assemble(panels)
only = set(sys.argv[1].split(',')) if len(sys.argv) > 1 and sys.argv[1] != '-' else None
XWIN = (float(sys.argv[2]), float(sys.argv[3])) if len(sys.argv) > 3 else None      # optional x window for the straightness column (e.g. the straight rear stretch of l3: 1.95 2.38)


def normal(f):
    p = V[list(f)]
    n = np.cross(p[1] - p[0], p[2] - p[0]) if len(f) == 3 else np.cross(p[2] - p[0], p[3] - p[1])
    return n / (np.linalg.norm(n) + 1e-30)


edges = {}
for i, f in enumerate(F):
    for a, b in zip(f, f[1:] + f[:1]):
        edges.setdefault((min(a, b), max(a, b)), []).append(i)
pairs = {}
signs = {}
pverts = {}
for (a, b), fs in edges.items():
    if len(fs) != 2:
        continue
    pa, pb = PID[fs[0]], PID[fs[1]]
    if pa == pb:
        continue
    ang = math.degrees(math.acos(max(-1, min(1, float(normal(F[fs[0]]) @ normal(F[fs[1]]))))))
    n0 = normal(F[fs[0]]) * (1 if names[pa] <= names[pb] else -1)               # (outward normals: the face normals are oriented by shell2.orient)
    c1 = V[list(F[fs[1]])].mean(0) - 0.5 * (V[a] + V[b])
    convex = float(normal(F[fs[0]]) @ c1) < 0
    if SIGNED:
        signs.setdefault(tuple(sorted((names[pa], names[pb]))), []).append(ang if convex else -ang)
    pairs.setdefault(tuple(sorted((names[pa], names[pb]))), []).append(ang)
    pverts.setdefault(tuple(sorted((names[pa], names[pb]))), set()).update((a, b))


def straight_mm(ids):
    """largest distance (mm) of the join's vertices (right half, y >= 0) from their best-fit straight line (PCA)"""
    P = V[sorted(ids)]
    P = P[P[:, 1] >= -1e-9]
    if XWIN:
        P = P[(P[:, 0] >= XWIN[0]) & (P[:, 0] <= XWIN[1])]
    if len(P) < 3:
        return float('nan'), float('nan')
    c = P.mean(0)
    u = np.linalg.svd(P - c, full_matrices=False)[2][0]
    d = (P - c) - np.outer((P - c) @ u, u)
    a, b = np.polyfit(P[:, 0], P[:, 2], 1)                                  # the side view (x, z): the line a photo from the side sees
    return float(np.linalg.norm(d, axis=1).max()) * 1000.0, float(np.abs(P[:, 2] - (a * P[:, 0] + b)).max()) * 1000.0
for k, v in sorted(pairs.items()):
    if only and not (set(k) & only):
        continue
    v = np.array(v)
    sm = frozenset(k) in S.SMOOTH_PAIRS
    extra = ''
    if SIGNED:
        sg = np.array(signs[k])
        extra = '   signed (+ ridge / - valley): min %+6.2f  mean %+6.2f  max %+6.2f   ridge %d valley %d' % (sg.min(), sg.mean(), sg.max(), int((sg > 0.05).sum()), int((sg < -0.05).sum()))
    print('%-32s edges %4d   min %5.2f  mean %5.2f  max %6.2f  straight %6.2f mm (side view %6.2f mm)  %s' % ('/'.join(k), len(v), v.min(), v.mean(), v.max(), *straight_mm(pverts[k]), 'smooth pair' if sm else ('FILLET' if v.max() > 3.0 else 'no fillet (< 3 deg)')) + extra)
