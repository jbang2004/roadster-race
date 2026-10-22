"""numpy-only: re-match a straight-down press camera (p013) on the photo features that do not depend on the nose.  Model side: world-space vertices dumped by
`Blender -b --python mask_views.py -- --glb <car.raw.glb> --out <dir> --views p013 --dump-verts verts.npz` (class 0 paint, 1 glass, 2 other).  Photo side: the white body (B/R > 0.72, closed, filled) and the holes
inside it (the bronze glass).  Camera: straight down, px = 900 + f (X - x0) / (H - Z), py = 600 - f (Y - y0) / (H - Z); unknowns (x0, y0, f, H) = shift x / y, focal, height.

  python3 cam_fit.py <verts.npz> [--fit] [--free x0,y0,f,H] [--feat tail,side,glass,seam] [--nose-from X]     (no --fit: just the residual table of the camera in VIEWS['p013'])

Features (all aft of the nose, none of them changed by R1e3):  tail  = rightmost white column per row, rows 450-740;  side = top / bottom edge of the white body per column, columns 500-1500;
glass = top / bottom edge of the glass holes per column (560-1480) and leftmost / rightmost glass column per row (330-870);  seam = the hood / cowl seam (design2 cowl_edge) against the dark line in the photo.
Prints old vs new camera, residual per feature (mean, rms, max in px) and the VIEWS['p013'] tuple of the fit."""
import sys, os
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import imgio
import cam as C

REFS = os.path.abspath(os.path.join(HERE, '..', '..', '..', 'refs', 'press2'))
W, H = 1800, 1200
argv = sys.argv[1:]


def arg(n, d):
    return argv[argv.index(n) + 1] if n in argv else d


def runs(line, gap=8, minlen=1):
    """[(start, end)] of the True runs of a 1-D bool array, gaps shorter than `gap` closed, runs shorter than `minlen` dropped (end inclusive)"""
    d = np.diff(np.r_[0, line.astype(np.int8), 0])
    st, en = np.nonzero(d == 1)[0], np.nonzero(d == -1)[0] - 1
    out = []
    for a, b in zip(st, en):
        if out and a - out[-1][1] - 1 < gap:
            out[-1] = (out[-1][0], b)
        else:
            out.append((a, b))
    return [(a, b) for a, b in out if b - a + 1 >= minlen]


class Photo:
    """photo features by scan lines (no flood fill): white body = B/R > 0.72 and bright; gaps < 8 px (the seam lines) closed; the body edge = the first / last white run of >= 40 px, the glass = the non-white
    runs of >= 40 px between the two body edges"""

    def __init__(self):
        ph = imgio.read(os.path.join(REFS, 'tesla-roadster-2026-013-1.jpg')).astype(float)
        R, G, B = ph[..., 0], ph[..., 1], ph[..., 2]
        self.white = (B / np.maximum(R, 1) > 0.78) & (R + G + B > 255)        # white / sunlit cream and the grey shaded side; the desert has B/R < 0.6, the ground shadow is darker
        self.cols = np.arange(500, 1501, 10)
        top, bot = [], []
        for c in self.cols:
            r = runs(self.white[:, c], 8, 20)
            top.append(r[0][0] if r else np.nan); bot.append(r[-1][1] + 1 if r else np.nan)
        self.top, self.bot = np.array(top, float), np.array(bot, float)
        self.rows = np.arange(450, 741, 10)
        tail = []
        for r_ in self.rows:
            r = runs(self.white[r_, :], 8, 20)
            tail.append(r[-1][1] + 1 if r else np.nan)
        self.tail = np.array(tail, float)
        self.gcols = np.arange(560, 1301, 20)
        gt, gb = [], []
        for c in self.gcols:
            r = runs(self.white[:, c], 8, 20)
            if len(r) < 2:
                gt.append(np.nan); gb.append(np.nan); continue
            lo, hi = r[0][1] + 1, r[-1][0]                       # between the white of the top side and of the bottom side: the glass (and the white ridge between, which is not glass)
            nw = runs(~self.white[lo:hi, c], 3, 15)
            gt.append(lo + nw[0][0] if nw else np.nan); gb.append(lo + nw[-1][1] + 1 if nw else np.nan)
        self.gtop, self.gbot = np.array(gt, float), np.array(gb, float)
        self.grows = np.arange(400, 801, 20)
        gl, gr = [], []
        for r_ in self.grows:
            r = runs(self.white[r_, :], 8, 20)
            if len(r) < 2:
                gl.append(np.nan); gr.append(np.nan); continue
            seg = ~self.white[r_, r[0][1] + 1:r[-1][0]]
            nw = runs(seg, 3, 60)
            gl.append(r[0][1] + 1 + nw[0][0] if nw else np.nan); gr.append(r[0][1] + 1 + nw[-1][1] + 1 if nw else np.nan)
        self.gleft, self.gright = np.array(gl, float), np.array(gr, float)
        self.nrows, self.ncols = np.arange(400, 801, 10), np.arange(170, 341, 10)           # the nose (NOT used by the fit): front edge per row, chamfer = top edge per column
        fe = [runs(self.white[r_, :], 8, 20) for r_ in self.nrows]
        self.nfront = np.array([r[0][0] if r else np.nan for r in fe], float)
        ce = [runs(self.white[:, c], 8, 20) for c in self.ncols]
        self.ncham = np.array([r[0][0] if r else np.nan for r in ce], float)


class Model:
    """model points (vertices + 4 mm edge samples) of class paint / glass; a probe = the extreme of one image coordinate over the points whose other coordinate is within `half` px of a bin position;
    the candidate points of every bin are cut out once (at the camera q0: those within `pad` px of the extreme) so the fit evaluates a few hundred points per bin"""

    def __init__(self, npz, q0):
        z = np.load(npz)
        self.cls = {'paint': z['v'][z['c'] == 0], 'glass': z['v'][z['c'] == 1]}
        self.q0, self.probes = np.asarray(q0, float), {}

    @staticmethod
    def proj(P, q):
        x0, y0, f, Hc = q
        zc = Hc - P[:, 2]
        return np.stack([900 + f * (P[:, 0] - x0) / zc, 600 - f * (P[:, 1] - y0) / zc], -1)

    def probe(self, name, cls, key, pos, which, half, pad=18.0, sel=None):
        P = self.cls[cls]
        px = self.proj(P, self.q0)
        if sel is not None:
            m = sel(px)
            P, px = P[m], px[m]
        o = np.argsort(px[:, key]); ks = px[o, key]
        subs = []
        for p in pos:
            i0, i1 = np.searchsorted(ks, p - half - 6), np.searchsorted(ks, p + half + 6)
            idx = o[i0:i1]
            if len(idx) == 0:
                subs.append(np.zeros((0, 3))); continue
            ex = px[idx, 1 - key].min() if which == 'min' else px[idx, 1 - key].max()
            keep = np.abs(px[idx, 1 - key] - ex) < pad
            subs.append(P[idx[keep]])
        self.probes[name] = (subs, np.asarray(pos, float), key, which, half)

    def edge(self, name, q):
        subs, pos, key, which, half = self.probes[name]
        out = np.full(len(pos), np.nan)
        for i, (S, p) in enumerate(zip(subs, pos)):
            if len(S) == 0:
                continue
            a = self.proj(S, q)
            s = np.abs(a[:, key] - p) < half
            if s.any():
                out[i] = a[s, 1 - key].min() if which == 'min' else a[s, 1 - key].max()
        return out


def build_probes(mod, ph, feats):
    if 'tail' in feats:
        mod.probe('tail', 'paint', 1, ph.rows, 'max', 2.0, sel=lambda px: px[:, 0] > 1500)
    if 'side' in feats:
        mod.probe('top', 'paint', 0, ph.cols, 'min', 3.0)
        if 'bot' in feats:
            mod.probe('bot', 'paint', 0, ph.cols, 'max', 3.0)
    if 'nose' in feats:
        mod.probe('nfront', 'paint', 1, ph.nrows, 'min', 2.0)
        mod.probe('ncham', 'paint', 0, ph.ncols, 'min', 3.0)
    if 'glass' in feats:
        mod.probe('gtop', 'glass', 0, ph.gcols, 'min', 4.0)
        if 'gbot' in feats:
            mod.probe('gbot', 'glass', 0, ph.gcols, 'max', 4.0)
        mod.probe('gleft', 'glass', 1, ph.grows, 'min', 3.0)
        mod.probe('gright', 'glass', 1, ph.grows, 'max', 3.0)


def residuals(mod, ph, q, feats):
    res = {}
    refs = {'nfront': ph.nfront, 'ncham': ph.ncham, 'tail': ph.tail, 'top': ph.top, 'bot': ph.bot, 'gtop': ph.gtop, 'gbot': ph.gbot, 'gleft': ph.gleft, 'gright': ph.gright}
    for k in mod.probes:
        if k in refs:
            res[k] = refs[k] - mod.edge(k, q)
    return res


def flat(res, clip=25.0):
    r = np.concatenate([v for k, v in res.items() if not k.startswith('n')])
    ok = np.isfinite(r) & (np.abs(r) < clip)
    return r, ok


def table(label, res):
    print('  %-9s' % label, end='')
    for k, v in res.items():
        v = v[np.isfinite(v) & (np.abs(v) < 25)]
        print('  %s %+5.1f/%4.1f/%4.1f' % (k, v.mean() if len(v) else 0, np.sqrt((v ** 2).mean()) if len(v) else 0, np.abs(v).max() if len(v) else 0), end='')
    print()


if __name__ == '__main__':
    ph = Photo()
    feats = arg('--feat', 'tail,side,glass').split(',')
    v = C.VIEWS['p013']
    q0 = np.array([v[0][0], v[0][1], v[2] / 36.0 * 1800, v[0][2]])
    mod = Model(argv[0], q0)
    build_probes(mod, ph, feats)
    free = [s for s in arg('--free', 'x0,y0,f,H').split(',') if s]
    names = ['x0', 'y0', 'f', 'H']
    idx = [names.index(s) for s in free]
    print('features', feats, ' columns: mean / rms / max |residual| in px (photo - model; + = the photo is further right / lower)')
    table('VIEWS', residuals(mod, ph, q0, feats))
    if '--cam' in argv:                                           # --cam x0,y0,f,H : residual table of another camera (e.g. the new VIEWS entry: f = lens / 36 * 1800)
        qc = np.array([float(t) for t in arg('--cam', '').split(',')])
        table('--cam', residuals(mod, ph, qc, feats))
    if '--corner' in argv:                                        # the photo's nose outline through the camera (--cam, else VIEWS): chamfer = top edge per column at z .52, front edge = first white column per row at z .57
        qc = np.array([float(t) for t in arg('--cam', '').split(',')]) if '--cam' in argv else q0

        def world(col, row, z):
            return qc[0] + (col - 900) * (qc[3] - z) / qc[2], qc[1] - (row - 600) * (qc[3] - z) / qc[2]
        pts = []
        for c in range(150, 620, 12):
            r = runs(ph.white[:, c], 8, 20)
            if r:
                z = 0.52
                for _ in range(4):                                            # the outline is the lower edge L: z follows L (0.513 at the nose, 0.642 at x -1.9, <= 0.70)
                    x, y = world(c, r[0][0], z)
                    z = float(np.clip(0.513 + 0.2283 * (x + 2.465), 0.513, 0.70))
                pts.append((round(float(x), 3), round(float(y), 3)))
        print('chamfer outline (x, y) m, z along L:', pts)
        fr = []
        for r_ in range(430, 771, 20):
            rr = runs(ph.white[r_, :], 8, 20)
            if rr:
                fr.append(tuple(round(float(v), 3) for v in world(rr[0][0], r_, 0.566)))
        print('front edge (x, y) m at z .566:', fr)
    q = q0.copy()
    if '--fit' in argv:
        sc = np.array([0.01, 0.01, 50.0, 0.5])
        r0, ok0 = flat(residuals(mod, ph, q0, feats))                 # the outlier set is fixed at the start camera (so the profile over H is smooth)
        keep = ok0.copy()

        def solve(qs, idx):
            q = qs.copy()
            for it in range(60):
                r, _ = flat(residuals(mod, ph, q, feats))
                J = np.zeros((len(r), len(idx)))
                for j, i in enumerate(idx):
                    dq = np.zeros(4); dq[i] = sc[i]
                    rj, _ = flat(residuals(mod, ph, q + dq, feats))
                    J[:, j] = (rj - r) / sc[i]
                ok = keep & np.isfinite(r) & np.isfinite(J).all(1)
                A, b = J[ok], -r[ok]
                step = np.linalg.solve(A.T @ A + 1e-3 * np.eye(len(idx)), A.T @ b)
                q[idx] += step
                if np.abs(step / sc[idx]).max() < 1e-3:
                    break
            r, _ = flat(residuals(mod, ph, q, feats))
            ok = keep & np.isfinite(r)
            return q, np.sqrt((r[ok] ** 2).mean()), A, ok.sum(), r[ok]
        print('start camera: rms %.2f px (%d residuals)' % (np.sqrt((r0[keep] ** 2).mean()), keep.sum()))
        q, rms, A, n, rr = solve(q0, idx)
        cov = np.linalg.inv(A.T @ A) * np.var(rr)
        print('fit, free %s: x0 %.4f y0 %.4f f %.1f (lens %.1f mm) H %.2f m   rms %.2f px   1 sigma (white noise, optimistic): %s' % (','.join(free), q[0], q[1], q[2], q[2] * 36 / 1800, q[3], rms, np.sqrt(np.diag(cov)).round(3)))
        table('fit', residuals(mod, ph, q, feats))
        print('profile over the camera height (x0, y0, f refitted):  H  rms  f  x0  y0')
        for Hc in [float(h) for h in arg("--profile", "10,15,20,25,30,40,60").split(",")]:
            qp, rp, _, _, _ = solve(np.array([q0[0], q0[1], q0[2] * Hc / q0[3], Hc]), [i for i in idx if i != 3])
            ex = ''
            if 'nose' in feats:
                rs = residuals(mod, ph, qp, feats)
                sc_ = qp[2] / (qp[3] - 0.57)
                ex = '   nose (not fitted): front edge %+5.1f px = %+5.1f cm, chamfer top edge %+5.1f px = %+5.1f cm  (photo - model, z .57)' % (np.nanmean(rs['nfront']), 100 * np.nanmean(rs['nfront']) / sc_, np.nanmean(rs['ncham']), 100 * np.nanmean(rs['ncham']) / sc_)
            print('   H %5.1f  rms %.2f  f %.0f (lens %.1f mm)  x0 %.4f  y0 %.4f%s' % (Hc, rp, qp[2], qp[2] * 36 / 1800, qp[0], qp[1], ex))
            print("      VIEWS['p013'] = ((%.4f, %.4f, %.3f), (%.4f, %.4f, 0.0), %.3f, (1800, 1200), (0.0, 0.0))" % (qp[0], qp[1], qp[3], qp[0], qp[1], qp[2] * 36.0 / 1800))
        print("VIEWS['p013'] = ((%.4f, %.4f, %.3f), (%.4f, %.4f, 0.0), %.3f, (1800, 1200), (0.0, 0.0))" % (q[0], q[1], q[3], q[0], q[1], q[2] * 36.0 / 1800))
