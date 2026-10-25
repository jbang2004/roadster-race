"""
Phase 2: the car's feature lines in 3D from the calibrated photos (numpy only).

  python3 tools/blender/calib/lines.py trace [LINE ...] [--sheets DIR]   snap every (line, photo) of linecfg.CFG onto the photo -> lines/traced.json (+ check sheets)
  python3 tools/blender/calib/lines.py fit [LINE ...] [--sheets DIR]     one 3D curve per line from all its traces -> lines/fit.json (+ reprojection sheets)
  python3 tools/blender/calib/lines.py cv [LINE ...]                      leave-one-photo-out jackknife sigma (the realistic uncertainty) -> fit.json

A line is a graph over one axis (x, y or z: t -> the other two coordinates, cubic B-splines), symmetric: |y| is stored, a trace of the other side is mirrored.
Seeds are the current model's curves (design2.CURVES) or 3D polylines, projected through the calibrated cameras; trace.py moves them onto the photo's edge.
The fit minimises the image distance of every traced point to the projected curve over all photos (Huber), with smoothing, optional 3D anchors (calibrated
landmarks) and a weak pull to the seed so that a direction no photo sees stays put; the posterior sigma per coordinate shows what the photos actually fix.
"""
import sys, os, json, math
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..'))
import design2 as D
from cam import Cam
from trace import snap
from crop import REF, PH
from linecfg import CFG

OUT = os.path.join(HERE, 'lines')
PRIOR = 0.15          # m, per control point: the seed pull (weak)
SIG, HUB = 1.0, 3.0   # px
AX = {'x': 0, 'y': 1, 'z': 2}
LM = json.load(open(os.path.join(HERE, 'result.json')))['landmarks']


class Seed:
    """the seed / model curve of a line as a function of its axis parameter t (|y| side)"""

    def __init__(self, c):
        self.ax = AX[c.get('axis', 'x')]
        s = c['seed']
        if isinstance(s, str):
            cv = D.CURVES[s]
            assert self.ax == 0
            self.f = lambda t: cv.at(t)
            self.model = c.get('model', True)
        else:
            P = np.array(s, float)
            o = np.argsort(P[:, self.ax]); P = P[o]
            self.P = P
            self.f = lambda t: np.stack([np.interp(t, P[:, self.ax], P[:, k]) for k in range(3)], -1)
            self.model = c.get('model', False)

    def at(self, t):
        return self.f(np.asarray(t, float))


def ranges(r):
    return [r] if not isinstance(r[0], (list, tuple)) else list(r)


def mirror(P, sd):
    return P * np.array([1.0, sd, 1.0])


def do_trace(names, sheets=None):
    os.makedirs(OUT, exist_ok=True)
    fn = os.path.join(OUT, 'traced.json')
    T = json.load(open(fn)) if os.path.exists(fn) else {}
    for ln in names:
        c = CFG[ln]; S0 = Seed(c)
        T[ln] = {}
        for ob in c['obs']:
            ph, sd, tr, mode, ch, r = ob[:6]
            opt = ob[6] if len(ob) > 6 else {}
            items, pts, ns, sh = [], [], 0, []
            for t0, t1 in ranges(tr):
                t = np.linspace(t0, t1, 300)
                S = Cam(ph).project(mirror(S0.at(t), sd))
                Q, ok, best, P, N = snap(ph, S, mode, r=r, channel=ch, **opt)
                items.append((S, Q, ok)); pts += np.round(Q[ok], 2).tolist(); ns += len(Q); sh += list(np.hypot(*(Q - P).T)[ok])
            k = '%s:%d' % (ph, sd)
            T[ln][k] = {'pts': pts, 'n_seed': ns, 'shift_px': round(float(np.median(sh)), 2) if sh else -1}
            print('%-8s %-6s side %+d  kept %3d / %3d  median shift %.1f px' % (ln, ph, sd, len(pts), ns, T[ln][k]['shift_px']))
            if sheets:
                draw(ph, items, os.path.join(sheets, 'trace_%s_%s%s.jpg' % (ln, ph, 'L' if sd < 0 else 'R')))
    json.dump(T, open(fn, 'w'))
    return T


def draw(photo, items, out, pad=50, W=1500, extra=()):
    from PIL import Image, ImageDraw
    im = Image.open(REF + PH[photo]).convert('RGB'); d = ImageDraw.Draw(im)
    allp = []
    for S, Q, ok in items:
        if S is not None:
            d.line([tuple(p) for p in S], fill=(60, 120, 255), width=1); allp += list(S)
        for q, k in zip(Q, ok):
            d.ellipse([q[0] - 1.5, q[1] - 1.5, q[0] + 1.5, q[1] + 1.5], fill=(0, 255, 0) if k else (255, 0, 0))
        allp += list(Q)
    for poly, col in extra:
        d.line([tuple(p) for p in poly], fill=col, width=2); allp += list(poly)
    a = np.array(allp); a = a[np.isfinite(a).all(1)]
    x0, y0 = a.min(0) - pad; x1, y1 = a.max(0) + pad
    im = im.crop((int(max(0, x0)), int(max(0, y0)), int(min(im.size[0], x1)), int(min(im.size[1], y1))))
    if im.size[0] > W:
        im = im.resize((W, int(im.size[1] * W / im.size[0])))
    im.save(out, quality=88)


# ------------------------------------------------------------------------------------------------ 3D fit
def basis(t, knots):
    from curves2 import _bs_basis
    kv = np.r_[[knots[0]] * 3, knots, [knots[-1]] * 3]
    return _bs_basis(t, kv, 3, len(kv) - 4)


def dist_to_poly(Q, Pp):
    A = Pp[:-1]; B = Pp[1:]; AB = B - A
    L2 = np.maximum(np.sum(AB * AB, 1), 1e-12)
    t = np.clip(((Q[:, None, :] - A[None]) * AB[None]).sum(-1) / L2[None], 0, 1)
    C = A[None] + t[..., None] * AB[None]
    dd = np.hypot(*(Q[:, None, :] - C).transpose(2, 0, 1))
    j = np.argmin(dd, 1)
    return dd[np.arange(len(Q)), j]


def nearest_seg(Q, Pp):
    A = Pp[:-1]; AB = Pp[1:] - A
    L2 = np.maximum(np.sum(AB * AB, 1), 1e-12)
    t = np.clip(((Q[:, None, :] - A[None]) * AB[None]).sum(-1) / L2[None], 0, 1)
    dd = np.hypot(*(Q[:, None, :] - (A[None] + t[..., None] * AB[None])).transpose(2, 0, 1))
    return np.argmin(dd, 1)


def dist_local(Q, Pp, j0, w=3):
    """distance of Q to the segments j0-w .. j0+w of the polyline Pp (the nearest-segment search done once per iteration: fast Jacobians)"""
    J = np.clip(j0[:, None] + np.arange(-w, w + 1)[None], 0, len(Pp) - 2)
    A = Pp[J]; AB = Pp[J + 1] - A
    L2 = np.maximum(np.sum(AB * AB, -1), 1e-12)
    t = np.clip(((Q[:, None, :] - A) * AB).sum(-1) / L2, 0, 1)
    return np.hypot(*(Q[:, None, :] - (A + t[..., None] * AB)).transpose(2, 0, 1)).min(1)


def fit(ln, T, it=40, skip=()):
    c = CFG[ln]; S0 = Seed(c)
    ax = S0.ax
    t0, t1 = c['range']
    nk = max(3, int(round((t1 - t0) / c['dk'])) + 1)
    knots = np.linspace(t0, t1, nk)
    ts = np.linspace(t0, t1, 200)
    Bm = basis(ts, knots)
    M0 = S0.at(ts)
    free = [k for k in range(3) if k != ax and not (k == 1 and c.get('center')) and 'xyz'[k] not in c.get('fixed', '')]
    C0 = {k: np.linalg.lstsq(Bm, M0[:, k], rcond=None)[0] for k in free}
    nb = Bm.shape[1]
    obs = []
    for key, v in T[ln].items():
        ph, sd = key.split(':')
        if len(v['pts']) >= 5 and ph not in skip:
            obs.append((ph, int(sd), np.array(v['pts'])))
    cams = {ph: Cam(ph) for ph, _, _ in obs}
    anchors = [(np.array(LM[n]['xyz'], float) if isinstance(n, str) else np.array(n, float), s) for n, s in c.get('anchors', [])]
    smooth = c.get('smooth', 0.01)

    def curve(p):
        P = M0.copy(); P[:, ax] = ts                  # fixed coordinates stay at the seed
        for i, k in enumerate(free):
            P[:, k] = Bm @ p[i * nb:(i + 1) * nb]
        return P

    near = {}

    def res(p):
        P = curve(p)
        r = []
        for i, (ph, sd, Q) in enumerate(obs):
            Pp = cams[ph].project(mirror(P, sd))
            d = (dist_local(Q, Pp, near[i]) if i in near else dist_to_poly(Q, Pp)) / SIG
            r.append(np.where(d < HUB, d, np.sqrt(np.maximum(2 * HUB * d - HUB * HUB, 0))))
        for X, s in anchors:
            r.append(np.atleast_1d(np.min(np.linalg.norm(P - X, axis=1)) / s))
        for i, k in enumerate(free):
            cp = p[i * nb:(i + 1) * nb]
            r.append((cp - C0[k]) / PRIOR)
            r.append(np.diff(cp, 2) / smooth)
        return np.concatenate(r)

    p = np.concatenate([C0[k] for k in free])
    lam = 1e-2
    r = res(p); cost = np.sum(r ** 2)
    for k in range(it):
        P_ = curve(p)
        for i, (ph, sd, Q) in enumerate(obs):
            near[i] = nearest_seg(Q, cams[ph].project(mirror(P_, sd)))
        r = res(p); cost = np.sum(r ** 2)
        J = np.zeros((len(r), len(p)))
        for j in range(len(p)):
            pp = p.copy(); pp[j] += 1e-5
            J[:, j] = (res(pp) - r) / 1e-5
        A = J.T @ J; g = J.T @ r
        acc = False
        while lam < 1e8:
            dp = -np.linalg.solve(A + lam * np.diag(np.diag(A) + 1e-9), g)
            near.clear(); rn = res(p + dp); cn = np.sum(rn ** 2)
            for i, (ph, sd, Q) in enumerate(obs):
                near[i] = nearest_seg(Q, cams[ph].project(mirror(curve(p), sd)))
            if cn < cost:
                p, r, lam, acc = p + dp, rn, lam / 3, True
                break
            lam *= 10
        if not acc or (cost - cn) < 1e-6 * cost:
            break
        cost = cn
    cov = np.linalg.pinv(J.T @ J)
    P = curve(p)
    sig = np.zeros((len(ts), 3))
    for i, k in enumerate(free):
        sl = slice(i * nb, (i + 1) * nb)
        sig[:, k] = np.sqrt(np.einsum('ij,jk,ik->i', Bm, cov[sl, sl], Bm))
    per = {}
    for ph, sd, Q in obs:
        d = dist_to_poly(Q, cams[ph].project(mirror(P, sd)))
        per['%s:%d' % (ph, sd)] = (len(d), round(float(np.sqrt(np.mean(d ** 2))), 2), round(float(d.max()), 2))
    return {'t': ts, 'P': P, 'M': M0, 'sig': sig, 'per': per, 'obs': obs, 'ax': ax, 'model': S0.model}


def do_fit(names, sheets=None):
    T = json.load(open(os.path.join(OUT, 'traced.json')))
    fn = os.path.join(OUT, 'fit.json')
    F = json.load(open(fn)) if os.path.exists(fn) else {}
    for ln in names:
        if ln not in T:
            print('no traces for', ln); continue
        R = fit(ln, T)
        P, M, S = R['P'], R['M'], R['sig']
        print('\n%s  (%s)' % (ln, CFG[ln]['doc']))
        for k, (n, rms, mx) in R['per'].items():
            print('   %-9s n %3d  rms %.2f px  max %.2f px' % (k, n, rms, mx))
        lab = 'xyz'
        print('   ' + '  '.join(('%s_fit  ' % a) + (('%s_mod  d%s(cm) ' % (a, a)) if R['model'] else '') + 's%s(cm)' % a for a in lab))
        for tv in np.linspace(R['t'][0], R['t'][-1], 9):
            i = np.argmin(np.abs(R['t'] - tv))
            row = []
            for k in range(3):
                row.append('%7.3f ' % P[i, k] + (('%7.3f %+6.1f ' % (M[i, k], 100 * (P[i, k] - M[i, k]))) if R['model'] else '') + '%5.1f' % (100 * S[i, k]))
            print('   ' + ' | '.join(row))
        F[ln] = {'doc': CFG[ln]['doc'], 'axis': 'xyz'[R['ax']], 'fixed': CFG[ln].get('fixed', ''), 'pts': np.round(P, 4).tolist(), 'sig': np.round(S, 4).tolist(),
                 'model': np.round(M, 4).tolist() if R['model'] else None, 'per_photo': R['per']}
        if sheets:
            for ph, sd, Q in R['obs']:
                cm = Cam(ph)
                draw(ph, [(None, Q, np.ones(len(Q), bool))], os.path.join(sheets, 'fit_%s_%s%s.jpg' % (ln, ph, 'L' if sd < 0 else 'R')),
                     extra=[(cm.project(mirror(M, sd)), (60, 120, 255)), (cm.project(mirror(P, sd)), (255, 60, 200))])
    json.dump(F, open(fn, 'w'))


def do_cv(names):
    """leave-one-photo-out (both sides of a photo together) jackknife: a realistic sigma of every coordinate along the curve -> fit.json 'sig_cv', 'cv_max'"""
    T = json.load(open(os.path.join(OUT, 'traced.json')))
    fn = os.path.join(OUT, 'fit.json')
    F = json.load(open(fn))
    for ln in names:
        full = fit(ln, T)
        phs = sorted({ph for ph, _, _ in full['obs']})
        reps = [fit(ln, T, skip={ph})['P'] for ph in phs]
        R = np.array(reps); n = len(R)
        jk = np.sqrt((n - 1) / n * np.sum((R - R.mean(0)) ** 2, 0))
        dev = np.abs(R - full['P'][None])
        worst = [phs[int(i)] for i in np.argmax(dev.max(1), 0)]
        F[ln]['sig_cv'] = np.round(jk, 4).tolist()
        F[ln]['cv_max'] = {'xyz'[k]: [round(float(dev[:, :, k].max()), 4), worst[k]] for k in range(3)}
        print('%-9s photos %d  jackknife sigma (cm) median / max:  x %.1f / %.1f  y %.1f / %.1f  z %.1f / %.1f   largest leave-one-out shift: %s'
              % (ln, n, 100 * np.median(jk[:, 0]), 100 * jk[:, 0].max(), 100 * np.median(jk[:, 1]), 100 * jk[:, 1].max(), 100 * np.median(jk[:, 2]), 100 * jk[:, 2].max(),
                 ', '.join('%s %.1f cm (%s)' % (k, 100 * v[0], v[1]) for k, v in F[ln]['cv_max'].items() if v[0] > 0.005)))
    json.dump(F, open(fn, 'w'))


if __name__ == '__main__':
    a = sys.argv[1:]
    sheets = a[a.index('--sheets') + 1] if '--sheets' in a else None
    if sheets:
        os.makedirs(sheets, exist_ok=True)
    names = [n for n in a[1:] if not n.startswith('--') and n != sheets] or list(CFG)
    if a[0] == 'trace':
        do_trace(names, sheets)
    elif a[0] == 'fit':
        do_fit(names, sheets)
    elif a[0] == 'cv':
        do_cv(names)
