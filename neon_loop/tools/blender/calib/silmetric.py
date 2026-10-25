"""
Silhouette offsets (silhouette.py, sil.json) in metres, as profiles:

  python3 tools/blender/calib/silmetric.py SILDIR

  plan    p013: half width |y| of the outline vs x (model and photo), unprojected at the height of L (the widest crease) at that x
  side    p018: height of the top outline vs x, unprojected on the centre plane y = 0 (the crown)
  rear    r81 / p012 / p019: half width of the outline vs z, unprojected on the plane x = 1.65 (the rear haunch)
"""
import sys, os, json
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..'))
from cam import Cam
import design2 as D

S = json.load(open(os.path.join(sys.argv[1], 'sil.json')))


def pts(v):
    a = np.array([[np.nan if q is None else q for q in p] for p in S[v]['pts']], float)
    a = a[np.isfinite(a[:, 4])]
    return a


def unproj_plane(cm, u, v, n, d):
    """ray of pixel (u, v) hits the plane n . X = d"""
    o, r = cm.ray(u, v)
    t = (d - n @ o) / (r @ n)
    return o + t * r


def plan():
    cm = Cam('p013'); a = pts('p013')
    L = D.CURVES['L']
    rows = []
    for u, v, nx, ny, off, con in a:
        out = []
        for uu, vv in ((u, v), (u + nx * off, v + ny * off)):
            X = cm.unproject(uu, vv, 'z', 0.85)
            x = float(np.clip(X[0], L.x0, L.x1)); z = float(L.at(x)[2])
            X = cm.unproject(uu, vv, 'z', z)
            out.append(X)
        rows.append((out[0][0], abs(out[0][1]), abs(out[1][1]), np.sign(out[0][1])))
    r = np.array(rows)
    print('p013 plan outline: half width |y| (m), model vs photo, per 0.2 m of x (both sides averaged)')
    for x0 in np.arange(-2.6, 2.6, 0.2):
        s = r[(r[:, 0] >= x0) & (r[:, 0] < x0 + 0.2) & (np.abs(r[:, 0]) < 3)]
        if len(s) < 2:
            continue
        print('  x %+5.1f..%+5.1f  n %3d  model %.3f  photo %.3f  d %+5.1f cm   (L %.3f, R %+5.1f / %+5.1f cm)' % (
            x0, x0 + 0.2, len(s), np.median(s[:, 1]), np.median(s[:, 2]), 100 * np.median(s[:, 2] - s[:, 1]), np.median(s[:, 1]),
            100 * np.median((s[:, 2] - s[:, 1])[s[:, 3] < 0]) if (s[:, 3] < 0).any() else np.nan, 100 * np.median((s[:, 2] - s[:, 1])[s[:, 3] > 0]) if (s[:, 3] > 0).any() else np.nan))
    return r


def side(v='p018'):
    cm = Cam(v); a = pts(v)
    a = a[a[:, 3] < -0.5]                  # outline samples whose outward normal points up: the top line
    r = []
    for u, vv, nx, ny, off, con in a:
        P0 = unproj_plane(cm, u, vv, np.array([0, 1.0, 0]), 0.0); P1 = unproj_plane(cm, u + nx * off, vv + ny * off, np.array([0, 1.0, 0]), 0.0)
        r.append((P0[0], P0[2], P1[2]))
    r = np.array(r)
    print('%s top outline: height (m) on the centre plane, model vs photo' % v)
    for x0 in np.arange(-2.6, 2.6, 0.2):
        s = r[(r[:, 0] >= x0) & (r[:, 0] < x0 + 0.2)]
        if len(s) < 2:
            continue
        print('  x %+5.1f..%+5.1f  n %3d  model %.3f  photo %.3f  d %+5.1f cm' % (x0, x0 + 0.2, len(s), np.median(s[:, 1]), np.median(s[:, 2]), 100 * np.median(s[:, 2] - s[:, 1])))
    return r


def rear(v):
    cm = Cam(v); a = pts(v)
    a = a[np.abs(a[:, 2]) > 0.7]           # side outline samples (normal mostly horizontal)
    r = []
    for u, vv, nx, ny, off, con in a:
        P0 = unproj_plane(cm, u, vv, np.array([1.0, 0, 0]), 1.65); P1 = unproj_plane(cm, u + nx * off, vv + ny * off, np.array([1.0, 0, 0]), 1.65)
        r.append((P0[2], abs(P0[1]), abs(P1[1]), np.sign(P0[1])))
    r = np.array(r)
    print('%s side outline: half width (m) at x 1.65, model vs photo' % v)
    for z0 in np.arange(0.0, 1.4, 0.1):
        s = r[(r[:, 0] >= z0) & (r[:, 0] < z0 + 0.1)]
        if len(s) < 2:
            continue
        print('  z %.1f..%.1f  n %3d  model %.3f  photo %.3f  d %+5.1f cm' % (z0, z0 + 0.1, len(s), np.median(s[:, 1]), np.median(s[:, 2]), 100 * np.median(s[:, 2] - s[:, 1])))


if __name__ == '__main__':
    plan(); side('p018')
    for v in ('r81', 'p012', 'p019'):
        if v in S:
            rear(v)
