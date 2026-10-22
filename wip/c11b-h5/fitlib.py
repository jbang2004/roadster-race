"""c11: small numeric helpers for the crease fits (numpy only): non-negative least squares, a CONCAVE smooth curve fit (y'' = -sum a_k bump_k <= 0, analytic) and the pool-adjacent-violators isotonic fit."""
import numpy as np


def nnls(A, b, maxit=3000, tol=1e-12):
    """Lawson-Hanson active-set non-negative least squares"""
    m, n = A.shape
    P = np.zeros(n, bool)
    x = np.zeros(n)
    w = A.T @ (b - A @ x)
    it = 0
    while (~P).any() and w[~P].max() > tol and it < maxit:
        it += 1
        j = np.where(~P)[0][np.argmax(w[~P])]
        P[j] = True
        while True:
            s = np.zeros(n)
            s[P] = np.linalg.lstsq(A[:, P], b, rcond=None)[0]
            if s[P].min() > 0:
                x = s
                break
            idx = P & (s <= 0)
            a = np.min(x[idx] / (x[idx] - s[idx] + 1e-30))
            x = x + a * (s - x)
            P &= (x > tol)
        w = A.T @ (b - A @ x)
    return x


def _bump2(x, c, hw):
    """slope integral and height integral of the raised-cosine bump 0.5 (1 + cos(pi t)), t = (x - c) / hw, |t| < 1"""
    t = np.clip((np.asarray(x, float) - c) / hw, -1.0, 1.0)
    s = hw * 0.5 * ((t + 1.0) + np.sin(np.pi * t) / np.pi)
    Y = hw * hw * 0.5 * ((t + 1.0) ** 2 / 2.0 - (np.cos(np.pi * t) + 1.0) / np.pi ** 2)
    tt = (np.asarray(x, float) - c) / hw
    Y = np.where(tt > 1.0, hw * hw + hw * (np.asarray(x, float) - c - hw), Y)
    s = np.where(tt > 1.0, hw, s)
    return s, Y


def concave_curve(xg, yt, w, y0, x_end, y_end, s_end, centers, hw, lam=0.0, wend=1e4, s_free=True):
    """y(x) = y0 + S (x - x0) - sum_k a_k Y_k(x), a_k >= 0 (so y'' <= 0 everywhere, smooth), fitted to the targets yt (weights w) on the grid xg with y(x_end) = y_end, y'(x_end) = s_end (weight wend)
    and a penalty lam on the variation of neighbouring a_k.  Returns (function of x, info)."""
    x0 = xg[0]
    K = len(centers)
    cols = []
    for c in centers:
        cols.append(_bump2(xg, c, hw)[1])
    B = np.array(cols).T
    dx = xg - x0
    M = np.hstack([dx[:, None], -dx[:, None], -B])
    rows = [np.sqrt(w)[:, None] * M]
    rhs = [np.sqrt(w) * (yt - y0)]
    be = np.array([_bump2(x_end, c, hw)[1] for c in centers])
    se = np.array([_bump2(x_end, c, hw)[0] for c in centers])
    rows.append(wend * np.concatenate([[x_end - x0, -(x_end - x0)], -be])[None, :])
    rhs.append(np.array([wend * (y_end - y0)]))
    rows.append(wend * np.concatenate([[1.0, -1.0], -se])[None, :])
    rhs.append(np.array([wend * s_end]))
    if lam > 0:
        Dm = np.zeros((K - 1, K + 2))
        for j in range(K - 1):
            Dm[j, 2 + j] = -np.sqrt(lam)
            Dm[j, 3 + j] = np.sqrt(lam)
        rows.append(Dm)
        rhs.append(np.zeros(K - 1))
    z = nnls(np.vstack(rows), np.concatenate(rhs))
    S = z[0] - z[1]
    a = z[2:]

    def f(x):
        x = np.asarray(x, float)
        out = y0 + S * (x - x0)
        for c, ak in zip(centers, a):
            if ak > 0:
                out = out - ak * _bump2(x, c, hw)[1]
        return out

    def kappa(x):                       # -y''
        x = np.asarray(x, float)
        out = np.zeros_like(x)
        for c, ak in zip(centers, a):
            t = (x - c) / hw
            out = out + ak * np.where(np.abs(t) < 1, 0.5 * (1 + np.cos(np.pi * t)), 0.0)
        return out
    f.kappa = kappa
    f.S = S
    return f


def pav_increasing(v):
    """isotonic (non-decreasing) least-squares fit of the sequence v (pool adjacent violators); preserves the sum"""
    v = np.asarray(v, float)
    vals, cnt = [], []
    for x in v:
        vals.append(x)
        cnt.append(1)
        while len(vals) > 1 and vals[-2] > vals[-1]:
            n = cnt[-2] + cnt[-1]
            m = (vals[-2] * cnt[-2] + vals[-1] * cnt[-1]) / n
            vals[-2:] = [m]
            cnt[-2:] = [n]
    return np.concatenate([np.full(c, m) for m, c in zip(vals, cnt)])
