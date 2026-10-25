# wheel.py: outer edge of the light wheel disc (rim face) along rays from a rough centre, robust ellipse fit; writes an overlay to check.
#   python3 wheel.py PHOTO cx cy rmin rmax [out.png [a,b,phi,band]]   (a,b,phi,band: search band around an approximate ellipse instead of [rmin, rmax]; env DROP = min edge contrast)
import sys, numpy as np
from PIL import Image, ImageDraw
from crop import REF, PH


def lum(photo):
    a = np.asarray(Image.open(REF + PH[photo]).convert('RGB'), float)
    return a @ np.array([0.299, 0.587, 0.114])


def bil(L, x, y):
    x0 = np.clip(np.floor(x).astype(int), 0, L.shape[1] - 2); y0 = np.clip(np.floor(y).astype(int), 0, L.shape[0] - 2)
    fx, fy = x - x0, y - y0
    return (L[y0, x0] * (1 - fx) * (1 - fy) + L[y0, x0 + 1] * fx * (1 - fy) + L[y0 + 1, x0] * (1 - fx) * fy + L[y0 + 1, x0 + 1] * fx * fy)


def fit_conic(P):
    x, y = P[:, 0], P[:, 1]
    A = np.stack([x * x, x * y, y * y, x, y, np.ones_like(x)], 1)
    _, _, vt = np.linalg.svd(A)
    return vt[-1]


def conic_params(c):
    a, b, cc, d, e, f = c
    M = np.array([[a, b / 2], [b / 2, cc]])
    ctr = np.linalg.solve(2 * M, [-d, -e])
    k = ctr @ M @ ctr - f
    w, v = np.linalg.eigh(M / k)
    return ctr, 1 / np.sqrt(np.abs(w)), v


def conic_dist(c, P):
    ctr, ax, v = conic_params(c)
    q = (P - ctr) @ v
    # approx geometric distance: radial scaling
    rr = np.sqrt((q[:, 0] / ax[0]) ** 2 + (q[:, 1] / ax[1]) ** 2)
    return (rr - 1) * np.hypot(q[:, 0], q[:, 1]) / np.maximum(rr, 1e-9)


def edges(L, cx, cy, rmin, rmax, n=180, drop=25, ell=None):
    drop = float(__import__("os").environ.get("DROP", drop))
    """ell = (a, b, phi_deg, band): search r in [1-band, 1+band] x the radius of an approximate ellipse instead of [rmin, rmax]"""
    out = []
    for t in np.linspace(0, 2 * np.pi, n, endpoint=False):
        if ell:
            a, b, ph, bd = ell
            re = 1 / np.sqrt((np.cos(t - np.radians(ph)) / a) ** 2 + (np.sin(t - np.radians(ph)) / b) ** 2)
            r = np.arange(re * (1 - bd), re * (1 + bd), 0.25)
        else:
            r = np.arange(rmin, rmax, 0.25)
        v = bil(L, cx + r * np.cos(t), cy + r * np.sin(t))
        g = np.convolve(v, [-1, -1, -1, -1, 0, 1, 1, 1, 1], 'same') / 4      # (convolve flips the kernel) >0 where light inside, dark outside
        i = np.argmax(g[4:-4]) + 4
        if g[i] > drop:
            out.append((cx + r[i] * np.cos(t), cy + r[i] * np.sin(t), g[i]))
    return np.array(out)


def robust(P, it=6, tol=1.5):
    keep = np.ones(len(P), bool)
    for k in range(it):
        c = fit_conic(P[keep])
        d = np.abs(conic_dist(c, P))
        s = max(tol, 2.5 * np.median(d[keep]))
        keep = d < s
    return c, keep, d


if __name__ == '__main__':
    ph = sys.argv[1]; cx, cy, rmin, rmax = map(float, sys.argv[2:6])
    ell = tuple(map(float, sys.argv[7].split(','))) if len(sys.argv) > 7 else None      # a,b,phi,band
    L = lum(ph)
    E = edges(L, cx, cy, rmin, rmax, ell=ell)
    c, keep, d = robust(E[:, :2])
    ctr, ax, v = conic_params(c)
    print('%s edges %d kept %d  centre (%.2f, %.2f)  axes %.2f %.2f  rms %.2f px' % (ph, len(E), keep.sum(), ctr[0], ctr[1], ax[0], ax[1], np.sqrt(np.mean(d[keep] ** 2))))
    if len(sys.argv) > 6:
        im = Image.open(REF + PH[ph]).convert('RGB')
        hw = (max(ell[:2]) * (1 + ell[3]) if ell else rmax) * 1.1
        x0, y0 = int(cx - hw), int(cy - hw)
        cr = im.crop((x0, y0, int(cx + hw), int(cy + hw)))
        m = 600 / cr.size[0]; cr = cr.resize((600, int(cr.size[1] * m)))
        dr = ImageDraw.Draw(cr)
        for (x, y, g), k in zip(E, keep):
            X, Y = (x - x0) * m, (y - y0) * m
            dr.ellipse([X - 2, Y - 2, X + 2, Y + 2], fill=(0, 255, 0) if k else (255, 0, 0))
        tt = np.linspace(0, 2 * np.pi, 200)
        pts = ctr + (np.stack([ax[0] * np.cos(tt), ax[1] * np.sin(tt)], 1) @ v.T)
        dr.line([((p[0] - x0) * m, (p[1] - y0) * m) for p in pts], fill=(255, 0, 255), width=1)
        X, Y = (ctr[0] - x0) * m, (ctr[1] - y0) * m; dr.line([(X - 8, Y), (X + 8, Y)], fill=(255, 0, 255)); dr.line([(X, Y - 8), (X, Y + 8)], fill=(255, 0, 255))
        cr.save(sys.argv[6])
