"""
Edge snapping for feature lines (numpy + PIL): a seed polyline (e.g. the model's curve projected through the calibrated camera) is moved, sample by sample along its
normal, onto the strongest image feature within +-r px:

  mode 'step'   a brightness step (the polarity that dominates along the whole line is used everywhere)
       'dark_above' / 'dark_below'   a step with the dark side above / below (mostly horizontal lines; the normal points down)
       'dark_left' / 'dark_right'    the same for mostly vertical lines (the normal points right)
       'valley' / 'peak'   a thin dark / bright line (panel seam, light strip)

Returns the snapped points (sub-pixel), with the robust smoothing pass rejecting jumps.  Used by lines.py.
"""
import numpy as np
from PIL import Image
from crop import REF, PH

_cache = {}


def image(photo, channel='lum', blur=1.0):
    k = (photo, channel, blur)
    if k not in _cache:
        im = Image.open(REF + PH[photo]).convert('RGB')
        a = np.asarray(im, float)
        if channel == 'lum':
            g = a @ np.array([0.299, 0.587, 0.114])
        elif channel == 'red':                      # red lamps: R - (G + B) / 2
            g = a[..., 0] - 0.5 * (a[..., 1] + a[..., 2])
        elif channel == 'sat':                      # glass (brownish) vs paint (grey): chroma
            g = a.max(-1) - a.min(-1)
        else:
            g = a[..., 'rgb'.index(channel)]
        if blur:
            g = gblur(g, blur)
        _cache[k] = g
    return _cache[k]


def gblur(g, s):
    r = int(np.ceil(3 * s)); k = np.exp(-0.5 * (np.arange(-r, r + 1) / s) ** 2); k /= k.sum()
    gp = np.pad(g, ((0, 0), (r, r)), mode='edge')
    g = sum(k[i] * gp[:, i:i + g.shape[1]] for i in range(2 * r + 1))
    gp = np.pad(g, ((r, r), (0, 0)), mode='edge')
    return sum(k[i] * gp[i:i + g.shape[0], :] for i in range(2 * r + 1))


def bil(L, x, y):
    x = np.clip(x, 0, L.shape[1] - 1.001); y = np.clip(y, 0, L.shape[0] - 1.001)
    x0 = np.floor(x).astype(int); y0 = np.floor(y).astype(int)
    fx, fy = x - x0, y - y0
    return (L[y0, x0] * (1 - fx) * (1 - fy) + L[y0, x0 + 1] * fx * (1 - fy) + L[y0 + 1, x0] * (1 - fx) * fy + L[y0 + 1, x0 + 1] * fx * fy)


def resample(P, step):
    P = np.asarray(P, float)
    s = np.r_[0, np.cumsum(np.hypot(*np.diff(P, axis=0).T))]
    t = np.arange(0, s[-1] + 1e-9, step)
    return np.stack([np.interp(t, s, P[:, 0]), np.interp(t, s, P[:, 1])], 1)


def normals(P):
    T = np.gradient(P, axis=0)
    T /= np.maximum(np.hypot(T[:, 0], T[:, 1]), 1e-9)[:, None]
    N = np.stack([-T[:, 1], T[:, 0]], 1)          # tangent turned +90 deg
    # orient: down for a mostly horizontal line, right for a mostly vertical one (so 'dark_above' / 'dark_left' mean the same along the whole line)
    flip = np.where(np.abs(N[:, 1]) >= np.abs(N[:, 0]), N[:, 1] < 0, N[:, 0] < 0)
    N[flip] *= -1
    return N


def score_profiles(L, P, N, r, mode, w=2.0):
    t = np.arange(-r, r + 1e-9, 0.25)
    X = P[:, None, 0] + t[None, :] * N[:, None, 0]
    Y = P[:, None, 1] + t[None, :] * N[:, None, 1]
    I = bil(L, X, Y)
    k = int(round(w / 0.25))
    if mode in ('valley', 'peak'):
        Ip = np.pad(I, ((0, 0), (k, k)), mode='edge')
        S = (Ip[:, :-2 * k] + Ip[:, 2 * k:]) / 2 - I
        if mode == 'peak':
            S = -S
    else:
        Ip = np.pad(I, ((0, 0), (k, k)), mode='edge')
        S = (Ip[:, 2 * k:] - Ip[:, :-2 * k]) / (2 * w)          # dI/dt
    return t, S


def snap(photo, seed, mode='step', r=15.0, step=4.0, channel='lum', blur=1.0, min_score=None, smooth_tol=2.5, w=2.0):
    L = image(photo, channel, blur)
    P = resample(seed, step)
    N = normals(P)
    t, S = score_profiles(L, P, N, r, mode, w)
    if mode in ('dark_above', 'dark_left'):        # brighter along +N (down / right)
        mode = 'pos'
    elif mode in ('dark_below', 'dark_right'):
        mode = 'neg'
    if mode == 'step':
        sgn = 1.0 if np.median(S.max(1)) >= np.median((-S).max(1)) else -1.0
        S = sgn * S
    elif mode == 'neg':
        S = -S
    i = np.argmax(S, 1)
    best = S[np.arange(len(P)), i]
    # sub-pixel: parabola through the peak
    i0 = np.clip(i, 1, len(t) - 2)
    a, b, c = S[np.arange(len(P)), i0 - 1], S[np.arange(len(P)), i0], S[np.arange(len(P)), i0 + 1]
    den = a - 2 * b + c
    off = np.where(np.abs(den) > 1e-9, 0.5 * (a - c) / den, 0.0)
    tt = t[i0] + np.clip(off, -1, 1) * 0.25
    Q = P + tt[:, None] * N
    ok = best > (min_score if min_score is not None else 0.25 * np.median(best))
    ok &= (i > 0) & (i < len(t) - 1)                 # a peak at the window edge is no peak
    # robust smoothing: offsets along the normal must vary smoothly
    for _ in range(4):
        idx = np.nonzero(ok)[0]
        if len(idx) < 5:
            break
        sm = np.interp(np.arange(len(P)), idx, _smooth(tt[idx], 7))
        ok &= np.abs(tt - sm) < smooth_tol
    return Q, ok, best, P, N


def _smooth(v, k):
    if len(v) < k:
        return v
    from numpy.lib.stride_tricks import sliding_window_view
    pad = k // 2
    vp = np.pad(v, pad, mode='edge')
    return np.median(sliding_window_view(vp, k), axis=1)
