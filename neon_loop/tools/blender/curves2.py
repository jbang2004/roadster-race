"""
Fair 3D feature curves for the panel shell (shell2.py).  numpy only (no bpy), so the curves can be plotted / overlaid without Blender.

  Spline1D   C2 cubic spline y(x) through knots (natural or clamped ends)
  BFit1D     least-squares cubic B-spline y(x) with few control points (clamped, uniform knots): fair by construction
  XCurve     a curve parametrised by x:  (y(x), z(x)), made of Spline1D / BFit1D / straight lines;  at(x) -> (x, y, z)
  Poly       polyline / spline in arc-length, for the curves that are not graphs over x
  curvature_report(...)   sign changes of the curvature = wiggles (a fair curve has only the intended inflections)
"""
import math
import numpy as np


class Spline1D:
    """C2 cubic spline through (xs, ys).  bc = 'natural' (zero 2nd derivative at both ends) or 'clamped' (end slopes d0, d1)."""

    def __init__(self, xs, ys, bc='natural', d0=0.0, d1=0.0):
        self.x = np.asarray(xs, float)
        self.y = np.asarray(ys, float)
        n = len(self.x)
        h = np.diff(self.x)
        A = np.zeros((n, n))
        b = np.zeros(n)
        for i in range(1, n - 1):
            A[i, i - 1] = h[i - 1]
            A[i, i] = 2 * (h[i - 1] + h[i])
            A[i, i + 1] = h[i]
            b[i] = 6 * ((self.y[i + 1] - self.y[i]) / h[i] - (self.y[i] - self.y[i - 1]) / h[i - 1])
        if bc == 'clamped':
            A[0, 0] = 2 * h[0]; A[0, 1] = h[0]
            b[0] = 6 * ((self.y[1] - self.y[0]) / h[0] - d0)
            A[-1, -1] = 2 * h[-1]; A[-1, -2] = h[-1]
            b[-1] = 6 * (d1 - (self.y[-1] - self.y[-2]) / h[-1])
        else:
            A[0, 0] = 1.0
            A[-1, -1] = 1.0
        self.M = np.linalg.solve(A, b)

    def _seg(self, x):
        x = np.asarray(x, float)
        i = np.clip(np.searchsorted(self.x, x) - 1, 0, len(self.x) - 2)
        return x, i

    def __call__(self, x):
        x, i = self._seg(x)
        h = self.x[i + 1] - self.x[i]
        a = (self.x[i + 1] - x) / h
        b = (x - self.x[i]) / h
        return (a * self.y[i] + b * self.y[i + 1] + ((a ** 3 - a) * self.M[i] + (b ** 3 - b) * self.M[i + 1]) * h * h / 6.0)

    def d1(self, x):
        x, i = self._seg(x)
        h = self.x[i + 1] - self.x[i]
        a = (self.x[i + 1] - x) / h
        b = (x - self.x[i]) / h
        return ((self.y[i + 1] - self.y[i]) / h - (3 * a * a - 1) / 6.0 * h * self.M[i] + (3 * b * b - 1) / 6.0 * h * self.M[i + 1])

    def d2(self, x):
        x, i = self._seg(x)
        h = self.x[i + 1] - self.x[i]
        a = (self.x[i + 1] - x) / h
        b = (x - self.x[i]) / h
        return a * self.M[i] + b * self.M[i + 1]


def _bs_basis(t, knots, deg, nb):
    """B-spline basis matrix (len(t), nb) by Cox-de Boor (clamped knot vector)."""
    t = np.asarray(t, float)
    B = np.zeros((len(t), len(knots) - 1))
    for i in range(len(knots) - 1):
        B[:, i] = ((t >= knots[i]) & (t < knots[i + 1])).astype(float)
    B[t >= knots[-1], nb - 1] = 1.0
    for d in range(1, deg + 1):
        Bn = np.zeros((len(t), len(knots) - 1 - d))
        for i in range(len(knots) - 1 - d):
            den1 = knots[i + d] - knots[i]
            den2 = knots[i + d + 1] - knots[i + 1]
            term = 0.0
            if den1 > 0:
                term = term + (t - knots[i]) / den1 * B[:, i]
            if den2 > 0:
                term = term + (knots[i + d + 1] - t) / den2 * B[:, i + 1]
            Bn[:, i] = term
        B = Bn
    return B[:, :nb]


class BFit1D:
    """least-squares clamped cubic B-spline with ncp control points on [x0, x1] fitted to samples (xs, ys); the end values are interpolated exactly.
    Few control points = a fair curve; the residual to the traced samples is reported by .resid."""

    def __init__(self, xs, ys, ncp, w=None, exact_ends=True):
        xs = np.asarray(xs, float)
        ys = np.asarray(ys, float)
        self.x0, self.x1 = float(xs[0]), float(xs[-1])
        deg = 3
        ncp = max(ncp, deg + 1)
        inner = np.linspace(0, 1, ncp - deg + 1)[1:-1]
        self.knots = np.concatenate([[0] * (deg + 1), inner, [1] * (deg + 1)])
        self.deg, self.ncp = deg, ncp
        t = (xs - self.x0) / (self.x1 - self.x0)
        B = _bs_basis(t, self.knots, deg, ncp)
        W = np.ones(len(xs)) if w is None else np.asarray(w, float)
        if exact_ends:
            W = W.copy(); W[0] *= 1e4; W[-1] *= 1e4
        sw = np.sqrt(W)
        self.c = np.linalg.lstsq(B * sw[:, None], ys * sw, rcond=None)[0]
        self.resid = float(np.max(np.abs(B @ self.c - ys)))

    def _t(self, x):
        return np.clip((np.asarray(x, float) - self.x0) / (self.x1 - self.x0), 0, 1 - 1e-12)

    def __call__(self, x):
        t = self._t(x)
        return _bs_basis(np.atleast_1d(t), self.knots, self.deg, self.ncp) @ self.c if np.ndim(x) else float((_bs_basis(np.array([t]), self.knots, self.deg, self.ncp) @ self.c)[0])

    def d1(self, x, e=1e-4):
        return (self(np.asarray(x) + e) - self(np.asarray(x) - e)) / (2 * e)

    def d2(self, x, e=2e-3):
        x = np.asarray(x, float)
        return (self(x + e) - 2 * self(x) + self(x - e)) / (e * e)


class Line1D:
    def __init__(self, x0, y0, x1, y1):
        self.x0, self.y0, self.x1, self.y1 = x0, y0, x1, y1

    def __call__(self, x):
        return self.y0 + (np.asarray(x, float) - self.x0) * (self.y1 - self.y0) / (self.x1 - self.x0)

    def d1(self, x):
        return np.full_like(np.asarray(x, float), (self.y1 - self.y0) / (self.x1 - self.x0))

    def d2(self, x):
        return np.zeros_like(np.asarray(x, float))


class XCurve:
    """3D curve that is a graph over x:  x -> (x, y(x), z(x)).  fy, fz are Spline1D / BFit1D / Line1D objects."""

    def __init__(self, x0, x1, fy, fz, name=''):
        self.x0, self.x1, self.fy, self.fz, self.name = x0, x1, fy, fz, name

    def at(self, x):
        x = np.asarray(x, float)
        return np.stack([x, self.fy(x), self.fz(x)], -1)

    def tan(self, x):
        x = np.asarray(x, float)
        return np.stack([np.ones_like(x), self.fy.d1(x), self.fz.d1(x)], -1)

    def __call__(self, x):
        return self.at(x)


def line3(a, b, name=''):
    """straight 3D segment a -> b (x must increase)"""
    return XCurve(a[0], b[0], Line1D(a[0], a[1], b[0], b[1]), Line1D(a[0], a[2], b[0], b[2]), name)


def spline3(knots, name='', bc='natural', slope0=None, slope1=None):
    """interpolating C2 spline through (x, y, z) knots (use few, well spaced knots)"""
    k = np.asarray(knots, float)
    if bc == 'clamped':
        fy = Spline1D(k[:, 0], k[:, 1], 'clamped', slope0[0], slope1[0])
        fz = Spline1D(k[:, 0], k[:, 2], 'clamped', slope0[1], slope1[1])
    else:
        fy = Spline1D(k[:, 0], k[:, 1]); fz = Spline1D(k[:, 0], k[:, 2])
    return XCurve(k[0, 0], k[-1, 0], fy, fz, name)


def fit3(samples, ncp, name='', ncp_z=None, w=None):
    """least-squares B-spline fit of (x, y, z) samples with ncp control points per coordinate"""
    k = np.asarray(samples, float)
    fy = BFit1D(k[:, 0], k[:, 1], ncp, w)
    fz = BFit1D(k[:, 0], k[:, 2], ncp_z or ncp, w)
    c = XCurve(k[0, 0], k[-1, 0], fy, fz, name)
    c.resid = (fy.resid, fz.resid)
    return c


class _Herm1D:
    """cubic Hermite y(x) on [x0, x1] from end values and end slopes (a G1 blend between two curves)"""

    def __init__(self, x0, y0, d0, x1, y1, d1_):
        self.x0, self.x1, self.y0, self.d0, self.y1, self.d1_ = x0, x1, y0, d0, y1, d1_

    def __call__(self, x):
        x = np.asarray(x, float)
        h = self.x1 - self.x0
        s = (x - self.x0) / h
        return ((2 * s ** 3 - 3 * s ** 2 + 1) * self.y0 + (s ** 3 - 2 * s ** 2 + s) * h * self.d0 + (-2 * s ** 3 + 3 * s ** 2) * self.y1 + (s ** 3 - s ** 2) * h * self.d1_)

    def d1(self, x):
        x = np.asarray(x, float)
        h = self.x1 - self.x0
        s = (x - self.x0) / h
        return ((6 * s ** 2 - 6 * s) * self.y0 / h + (3 * s ** 2 - 4 * s + 1) * self.d0 + (-6 * s ** 2 + 6 * s) * self.y1 / h + (3 * s ** 2 - 2 * s) * self.d1_)

    def d2(self, x):
        x = np.asarray(x, float)
        h = self.x1 - self.x0
        s = (x - self.x0) / h
        return ((12 * s - 6) * self.y0 / h ** 2 + (6 * s - 4) * self.d0 / h + (-12 * s + 6) * self.y1 / h ** 2 + (6 * s - 2) * self.d1_ / h)


def herm3(c0, x0, c1, x1, name=''):
    """G1 blend between curve c0 (at x0) and curve c1 (at x1): positions and tangents of both are matched"""
    p0, p1 = c0.at(x0), c1.at(x1)
    t0, t1 = c0.tan(x0), c1.tan(x1)
    return XCurve(x0, x1, _Herm1D(x0, p0[1], t0[1], x1, p1[1], t1[1]), _Herm1D(x0, p0[2], t0[2], x1, p1[2], t1[2]), name)


class SubCurve:
    """a piece of a curve restricted to [x0, x1]"""

    def __init__(self, c, x0, x1, name=''):
        self.c, self.x0, self.x1, self.name = c, x0, x1, name

    def at(self, x):
        return self.c.at(x)

    def tan(self, x):
        return self.c.tan(x)

    @property
    def fy(self):
        return self.c.fy

    @property
    def fz(self):
        return self.c.fz


def curvature_report(c, n=400, name=None):
    """curvature of the side-view (x, z) and plan (x, y) projections: (sign changes of kappa = inflections, max |kappa| in 1/m, max |jump| between neighbours)"""
    xs = np.linspace(c.x0, c.x1, n)
    out = {}
    for lab, f in (('z', c.fz), ('y', c.fy)):
        v = np.asarray(f(xs), float)
        d1 = np.gradient(v, xs)
        d2 = np.gradient(d1, xs)
        k = (d2 / (1 + d1 * d1) ** 1.5)[4:-4]
        sg = np.sign(k[np.abs(k) > 0.05])
        infl = int(np.sum(sg[1:] != sg[:-1])) if len(sg) > 1 else 0
        out[lab] = (infl, float(np.max(np.abs(k))), float(np.max(np.abs(np.diff(k)))))
    return out
