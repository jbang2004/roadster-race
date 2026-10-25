# bundle.py: joint calibration of all press-photo cameras (numpy only).
# Unknowns: per photo loc (3) + rotation (3, about the VIEWS / initial orientation) + focal (log px); landmark 3D points (x, |y|, z: _L/_R pairs share one point,
# mirror-symmetric about y = 0); wheel rims as 3D circles (axle x fixed = the gauge: front -1.487, rear 1.61; axle z, rim |y| and radius free);
# tyre ground contacts at z = 0 fix the height gauge.  Observations: picked points (px, sigma), rim-edge points (Sampson distance to the projected circle),
# nozzle-ring centres.  Robust (Huber) Levenberg-Marquardt, numerical Jacobian.
import json, os, sys, math, glob
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import cam as CAM

HERE = os.path.dirname(os.path.abspath(__file__))
X_AXLE = {'F': -1.487, 'R': 1.61}
SIG_RIM = 0.7
SIG_RIM_PH = {'p003': 3.0}        # p003: the rim's rear third is hidden behind the fender (partial-ellipse fit rms 3.4 px)
HUBER = 2.5


def skew(w):
    return np.array([[0, -w[2], w[1]], [w[2], 0, -w[0]], [-w[1], w[0], 0]])


def rodrigues(w):
    th = np.linalg.norm(w)
    if th < 1e-12:
        return np.eye(3) + skew(w)
    K = skew(w / th)
    return np.eye(3) + math.sin(th) * K + (1 - math.cos(th)) * K @ K


class CamModel:
    def __init__(self, name, view):
        CAM.VIEWS[name] = view
        c = CAM.Cam(name)
        self.name, self.w, self.h, self.cx, self.cy = name, c.w, c.h, c.cx, c.cy
        self.R0 = np.array([c.right, -c.up, c.d])
        self.p0 = np.r_[c.loc, 0.0, 0.0, 0.0, math.log(c.f)]
        self.view = view

    def unpack(self, p):
        return p[:3], rodrigues(p[3:6]) @ self.R0, math.exp(p[6])

    def project(self, p, X):
        loc, R, f = self.unpack(p)
        v = (np.atleast_2d(X) - loc) @ R.T
        return np.stack([self.cx + f * v[:, 0] / v[:, 2], self.cy + f * v[:, 1] / v[:, 2]], -1)

    def circle_conic(self, p, c, r, steer=0.0):
        """image conic of the circle (centre c, radius r) in the plane y = c[1] (wheel axis along y), turned by steer (rad) about z"""
        loc, R, f = self.unpack(p)
        K = np.array([[f, 0, self.cx], [0, f, self.cy], [0, 0, 1.0]])
        ex = np.array([math.cos(steer), math.sin(steer), 0.0])
        H = K @ np.stack([R @ (r * ex), R @ np.array([0, 0, r]), R @ (c - loc)], 1)
        Hi = np.linalg.inv(H)
        return Hi.T @ np.diag([1.0, 1.0, -1.0]) @ Hi

    def to_view(self, p):
        """back to a VIEWS tuple: loc, tgt (10 m ahead), lens mm, (w, h), shift, roll"""
        loc, R, f = self.unpack(p)
        d, right, up = R[2], R[0], -R[1]
        if abs(d[2]) > 0.999999:        # cam.py straight-down branch
            u0 = np.array([0.0, 1.0, 0.0]); r0 = np.cross(d, u0)
        else:
            r0 = np.cross(d, np.array([0, 0, 1.0])); r0 /= np.linalg.norm(r0); u0 = np.cross(r0, d)
        roll = math.degrees(math.atan2(right @ u0, right @ r0))
        sx = (self.w / 2 - self.cx) / self.w; sy = (self.cy - self.h / 2) / self.w
        return (tuple(np.round(loc, 5)), tuple(np.round(loc + 10 * d, 6)), round(f * 36 / self.w, 4), (self.w, self.h), (round(sx, 4), round(sy, 4)), round(roll, 4))


def side(nm):
    return -1.0 if nm.endswith('_L') else (1.0 if nm.endswith('_R') else 0.0)


def base(nm):
    return nm[:-2] if nm[-2:] in ('_L', '_R') else nm


class Problem:
    def __init__(self, picks, rims, rings, views, fixed_pts, rim_groups, priors=None, ground=None, horizon=None):
        self.cams = {n: CamModel(n, v) for n, v in views.items()}
        self.obs = []        # (cam, kind, key, data)
        for ph, d in picks.items():
            for nm, (u, v, s) in d.items():
                self.obs.append((ph, 'pt', nm, (np.array([u, v]), s)))
        for ph, d in rings.items():
            for nm, (u, v, a, b) in d.items():
                self.obs.append((ph, 'pt', nm, (np.array([u, v]), 1.0)))
        for ph, d in rims.items():
            for nm, pts in d.items():
                pts = np.array(pts)
                sel = pts[np.linspace(0, len(pts) - 1, min(30, len(pts))).astype(int)]
                axle = nm[3]
                grp = rim_groups.get(ph, '')
                self.obs.append((ph, 'rim', nm, (sel, axle, 'RIM' + axle + grp, side(nm))))
        for ph, d in (ground or {}).items():
            for nm, (u, v, s, X) in d.items():
                self.obs.append((ph, 'fix', nm, (np.array([u, v]), s, np.array(X, float))))
        for ph, lst in (horizon or {}).items():
            for i, (u, v, s) in enumerate(lst):
                self.obs.append((ph, 'hz', 'HZ%d' % i, (u, v, s)))
        self.priors = priors or {}
        # parameter layout
        self.lm = sorted({base(o[2]) for o in self.obs if o[1] == 'pt'})
        self.rimg = sorted({o[3][2] for o in self.obs if o[1] == 'rim'})
        self.cn = sorted(self.cams)
        idx = 0; self.ci = {}
        for n in self.cn:
            self.ci[n] = slice(idx, idx + 7); idx += 7
        self.li = {}
        for n in self.lm:
            self.li[n] = slice(idx, idx + 3); idx += 3
        self.zi = {'F': idx, 'R': idx + 1}; idx += 2
        self.ri = {}
        for g in self.rimg:
            self.ri[g] = slice(idx, idx + 2); idx += 2
        self.si = {}
        for o in self.obs:
            if o[1] == 'rim' and o[3][1] == 'F' and o[0] not in self.si:
                self.si[o[0]] = idx; idx += 1
        self.n = idx

    def x0(self, L0, z0=(0.39, 0.39), rim0=(0.95, 0.30)):
        x = np.zeros(self.n)
        for n in self.cn:
            x[self.ci[n]] = self.cams[n].p0
        for n in self.lm:
            x[self.li[n]] = L0[n]
        x[self.zi['F']], x[self.zi['R']] = z0
        for g in self.rimg:
            x[self.ri[g]] = rim0
        return x

    def point(self, x, nm):
        p = x[self.li[base(nm)]]
        return np.array([p[0], side(nm) * p[1] if side(nm) else p[1], p[2]])

    def residuals(self, x, per_obs=False):
        res, tags = [], []
        for o in self.obs:
            ph, kind, nm, d = o
            cp = x[self.ci[ph]]
            cm = self.cams[ph]
            if kind == 'pt':
                e = (cm.project(cp, self.point(x, nm))[0] - d[0]) / d[1]
                res.append(e); tags.append((ph, nm, 2))
            elif kind == 'hz':            # horizon: v of the vanishing line of the ground plane at column u
                loc, R, f = cm.unpack(cp)
                K = np.array([[f, 0, cm.cx], [0, f, cm.cy], [0, 0, 1.0]])
                l = np.linalg.inv(K).T @ (R @ np.array([0, 0, 1.0]))
                u, vo, s = d
                e = np.array([(-(l[0] * u + l[2]) / l[1] - vo) / s])
                res.append(e); tags.append((ph, nm, 1))
            elif kind == 'fix':
                X = d[2].copy()
                g = 'RIM' + nm[1]
                if g in self.ri and X[2] == 0.0:          # tyre ground contact: the outer sidewall bottom, 4 cm outside the rim face
                    X[1] = np.sign(X[1]) * (x[self.ri[g]][0] + 0.04)
                e = (cm.project(cp, X)[0] - d[0]) / d[1]
                res.append(e); tags.append((ph, nm, 2))
            else:
                pts, axle, g, sd = d
                s, r = x[self.ri[g]]
                st = x[self.si[ph]] if axle == 'F' else 0.0
                KP = 0.80
                c = np.array([X_AXLE[axle] - math.sin(st) * sd * (s - KP), sd * (KP + math.cos(st) * (s - KP)), x[self.zi[axle]]])
                Q = cm.circle_conic(cp, c, r, st)
                P = np.c_[pts, np.ones(len(pts))]
                qp = P @ Q
                alg = np.sum(qp * P, 1)
                grad = 2 * np.hypot(qp[:, 0], qp[:, 1])
                e = alg / grad / SIG_RIM_PH.get(ph, SIG_RIM)
                res.append(e); tags.append((ph, nm, len(e)))
        for k, (ii, mu, sg) in self.priors.items():
            res.append(np.atleast_1d((x[ii] - mu) / sg)); tags.append(('prior', k, np.size(mu)))
        r = np.concatenate(res)
        return (r, tags) if per_obs else r

    def solve(self, x, it=60, verbose=True, freeze=()):
        lam = 1e-3
        free = np.ones(self.n, bool)
        for sl in freeze:
            free[sl] = False
        r = self.residuals(x)
        npri = sum(np.size(v[1]) for v in self.priors.values())
        robust = np.ones(len(r), bool)
        if npri:
            robust[-npri:] = False          # priors are never down-weighted
        def cost(r):
            a = np.abs(r)
            return np.sum(np.where((a < HUBER) | ~robust, 0.5 * r * r, HUBER * a - 0.5 * HUBER ** 2))
        c = cost(r)
        for k in range(it):
            a = np.abs(r); w = np.where((a < HUBER) | ~robust, 1.0, HUBER / np.maximum(a, 1e-12))
            J = np.zeros((len(r), self.n))
            for j in np.nonzero(free)[0]:
                h = 1e-6 * max(1.0, abs(x[j]))
                xp = x.copy(); xp[j] += h
                J[:, j] = (self.residuals(xp) - r) / h
            Jw = J * np.sqrt(w)[:, None]; rw = r * np.sqrt(w)
            A = Jw.T @ Jw; g = Jw.T @ rw
            ok = False
            for t in range(12):
                Ad = A + lam * np.diag(np.diag(A) + 1e-9)
                Ad[~free, :] = 0; Ad[:, ~free] = 0; Ad[~free, ~free] = 1
                dx = -np.linalg.solve(Ad, np.where(free, g, 0))
                xn = x + dx
                rn = self.residuals(xn); cn = cost(rn)
                if cn < c:
                    ok = True; break
                lam *= 10
            if not ok:
                break
            rel = (c - cn) / c
            x, r, c = xn, rn, cn
            lam = max(lam / 5, 1e-9)
            if verbose:
                print('it %2d cost %.2f  lam %.1e' % (k, c, lam))
            if rel < 1e-7:
                break
        self.J = J
        return x

    def report(self, x, file=None):
        r, tags = self.residuals(x, per_obs=True)
        i = 0; per = {}
        rows = []
        for ph, nm, n in tags:
            e = r[i:i + n]; i += n
            if ph == 'prior':
                continue
            if n == 1:
                o = next(o for o in self.obs if o[0] == ph and o[2] == nm)
                per.setdefault(ph, []).append(np.array([e[0] * o[3][2], 0.0])); rows.append((ph, nm, 0.0, e[0] * o[3][2], abs(e[0] * o[3][2])))
                continue
            if n == 2:
                o = next(o for o in self.obs if o[0] == ph and o[2] == nm)
                s = o[3][1]
                px = e * s
                per.setdefault(ph, []).append(px)
                rows.append((ph, nm, px[0], px[1], np.hypot(*px)))
            else:
                px = e * SIG_RIM_PH.get(ph, SIG_RIM)
                per.setdefault(ph, []).extend([np.array([v, 0.0]) for v in px])
                rows.append((ph, nm, np.sqrt(np.mean(px ** 2)), np.max(np.abs(px)), len(px)))
        return per, rows


def triangulate(views, obs_by_lm):
    """linear triangulation of (x, |y|, z) from point observations in cameras with known views"""
    out = {}
    for b, lst in obs_by_lm.items():
        A, B = [], []
        for ph, nm, uv in lst:
            if ph not in views:
                continue
            c = CamModel('_t', views[ph])
            loc, R, f = c.unpack(c.p0)
            K = np.array([[f, 0, c.cx], [0, f, c.cy], [0, 0, 1.0]])
            M = K @ np.c_[R, -R @ loc]
            sg = side(nm) or 1.0
            for row, val in ((0, uv[0]), (1, uv[1])):
                e = val * M[2] - M[row]
                A.append([e[0], sg * e[1], e[2]]); B.append(-e[3])
        if len(A) >= 4:
            out[b] = np.linalg.lstsq(np.array(A), np.array(B), rcond=None)[0]
    return out
