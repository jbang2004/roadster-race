"""
Phase 3: model silhouette vs photo silhouette in every calibrated view (numpy + PIL).

  python3 tools/blender/calib/silhouette.py MASKDIR OUTDIR [view ...]

MASKDIR holds <view>_mask.png from mask_views.py (the model through the calibrated cameras).  For every few px of the model's OUTER outline the photo is searched
along the outward normal (+-R px) for the car / background transition: the outermost crossing of the mid level between the car side (inside) and the background
side (outside) of the profile.  Low-contrast places (black lower body on a dark floor ...) are rejected.  Output per view:
  OUTDIR/<view>_sil.jpg   outline coloured by the signed offset (red: the photo reaches further out = model too small, blue: model too big, green |d| < 3 px)
  OUTDIR/sil.json         samples (u, v, nx, ny, offset px, offset cm at the car's distance, contrast)
"""
import sys, os, json
import numpy as np
from PIL import Image, ImageDraw
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..'))
from cam import Cam
from crop import REF, PH
from trace import image, bil, gblur

R = 30           # search half length, px
STEP = 6         # outline sample spacing, px
MIN_C = 18       # minimum car / background contrast (luminance levels)


def outline(mask):
    """outer boundary pixels of a binary mask (holes inside the car are ignored) and the outward normal there"""
    h, w = mask.shape
    out = np.zeros_like(mask)
    # flood the background from the border (4-connected), iterative dilation restricted to ~mask
    bg = ~mask
    seed = np.zeros_like(mask); seed[0, :] = seed[-1, :] = True; seed[:, 0] = seed[:, -1] = True
    seed &= bg
    cur = seed
    while True:
        nxt = cur.copy()
        nxt[1:] |= cur[:-1]; nxt[:-1] |= cur[1:]; nxt[:, 1:] |= cur[:, :-1]; nxt[:, :-1] |= cur[:, 1:]
        nxt &= bg
        if nxt.sum() == cur.sum():
            break
        cur = nxt
    outside = cur
    b = mask & (np.roll(outside, 1, 0) | np.roll(outside, -1, 0) | np.roll(outside, 1, 1) | np.roll(outside, -1, 1))
    ys, xs = np.nonzero(b)
    # thin to ~STEP spacing (grid hashing)
    key = (ys // STEP) * 100000 + xs // STEP
    _, first = np.unique(key, return_index=True)
    ys, xs = ys[first], xs[first]
    g = gblur((~outside).astype(float), 2.0)
    gy, gx = np.gradient(g)
    nx, ny = -gx[ys, xs], -gy[ys, xs]
    nn = np.hypot(nx, ny) + 1e-9
    return xs.astype(float), ys.astype(float), nx / nn, ny / nn


def probe(L, x, y, nx, ny):
    t = np.arange(-R, R + 1e-9, 0.5)
    X = x[:, None] + t[None] * nx[:, None]; Y = y[:, None] + t[None] * ny[:, None]
    I = bil(L, X, Y)
    C = np.median(I[:, :8], 1); B = np.median(I[:, -8:], 1)          # car side (inside) / background side (outside)
    mid = (B + C) / 2
    above = (I - mid[:, None]) * np.sign(C - B)[:, None] > 0          # True on the car side of the mid level
    off = np.full(len(x), np.nan)
    for i in range(len(x)):
        a = above[i]
        if not a[0] or a[-1]:
            continue
        j = len(a) - 1 - np.argmax(a[::-1])                           # the outermost car-side sample
        if j + 1 < len(a):
            d0, d1 = I[i, j] - mid[i], I[i, j + 1] - mid[i]
            f = d0 / (d0 - d1) if d0 != d1 else 0.5
            off[i] = t[j] + f * (t[1] - t[0])
    return off, np.abs(C - B)


def run(maskdir, outdir, views):
    os.makedirs(outdir, exist_ok=True)
    fn = os.path.join(outdir, 'sil.json')
    allr = json.load(open(fn)) if os.path.exists(fn) else {}
    for v in views:
        M = np.asarray(Image.open(os.path.join(maskdir, '%s_mask.png' % v)).convert('RGBA'))[..., 3] > 127
        x, y, nx, ny = outline(M)
        L = image(v, 'lum', 1.0)
        off, con = probe(L, x, y, nx, ny)
        ok = np.isfinite(off) & (con > MIN_C) & (np.abs(off) < R - 2)
        cm = Cam(v)
        dist = np.linalg.norm(cm.loc - np.array([0.0, 0.0, 0.7]))
        mpp = dist / cm.f                                              # m per px at the car's distance
        allr[v] = {'mpp': mpp, 'pts': [[round(float(a), 1), round(float(b), 1), round(float(c), 3), round(float(d), 3), round(float(o), 2) if k else None, round(float(q), 1)]
                                        for a, b, c, d, o, k, q in zip(x, y, nx, ny, off, ok, con)]}
        im = Image.open(REF + PH[v]).convert('RGB'); dr = ImageDraw.Draw(im)
        for a, b, c, d, o, k in zip(x, y, nx, ny, off, ok):
            if not k:
                dr.point((a, b), fill=(150, 150, 150)); continue
            col = (0, 220, 0) if abs(o) < 3 else ((255, 40, 40) if o > 0 else (60, 120, 255))
            dr.line([(a, b), (a + c * o, b + d * o)], fill=col, width=1)
            dr.ellipse([a - 1.5, b - 1.5, a + 1.5, b + 1.5], fill=col)
        ys_, xs_ = np.nonzero(M)
        im = im.crop((max(0, xs_.min() - 60), max(0, ys_.min() - 60), min(im.size[0], xs_.max() + 60), min(im.size[1], ys_.max() + 60)))
        im.save(os.path.join(outdir, '%s_sil.jpg' % v), quality=88)
        o = off[ok]
        print('%-6s samples %4d  used %4d  |offset| median %.1f px  p90 %.1f px  (%.1f / %.1f cm)  outward (photo bigger) %d%%' % (
            v, len(x), ok.sum(), np.median(np.abs(o)), np.percentile(np.abs(o), 90), 100 * mpp * np.median(np.abs(o)), 100 * mpp * np.percentile(np.abs(o), 90), 100 * np.mean(o > 0)))
    json.dump(allr, open(fn, 'w'))


if __name__ == '__main__':
    run(sys.argv[1], sys.argv[2], sys.argv[3:])
