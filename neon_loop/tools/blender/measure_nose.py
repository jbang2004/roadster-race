"""
R1e measuring tool (numpy only, no bpy): the model's NOSE silhouette (flat-colour masks of mask_views.py) against the press photos' nose silhouette, in px and in % of the image width (1800 px).

  Blender -b --python tools/blender/mask_views.py -- --glb <car.glb> --out <maskdir> --views p013,p016,p018
  python3 tools/blender/measure_nose.py <maskdir> [--save report.json]

  --detail prints the per-row / per-column series of every measure (px).
  p013   (top view, nose left)  photo silhouette = not-desert (B/R > 0.72 or very dark), closed / opened, flood-filled from the hood.  The nose outline is measured
         front edge : rows 400..800, horizontal gap photo - model (+ = the photo is further aft, i.e. the model nose sticks out further)
         chamfer    : the silhouette between the front edge and the straight side (upper half, columns 170..340): vertical gap of the top edge (+ = the model is wider)
  p018   (left profile)         photo silhouette = bright (lum > 110) nose, first run from the left; rows 610..690 (the near corner of the nose is the leading silhouette)
  p016   (front 3/4)            the light-bar line (hood front edge, projected with cam.py) against the bar's top edge in the photo, columns 320..700;  --r1c uses the R1c bowed edge
"""
import sys, os, json
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import imgio
from measure_masks import _rgba
REFS = os.path.abspath(os.path.join(HERE, '..', '..', '..', 'refs', 'press2'))
PH = {'p013': 'tesla-roadster-2026-013-1.jpg', 'p016': 'telsa-roadster-2026-016.jpg', 'p018': 'tesla-roadster-2026-018.jpg'}
W = 1800.0


def _er(m, n=1):
    for _ in range(n):
        g = m.copy()
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                g &= np.roll(np.roll(m, dy, 0), dx, 1)
        m = g
    return m


def _di(m, n=1):
    for _ in range(n):
        g = m.copy()
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                g |= np.roll(np.roll(m, dy, 0), dx, 1)
        m = g
    return m


def _flood(mask, seed):
    f = np.zeros_like(mask)
    f[seed] = True
    for _ in range(4000):
        g = _di(f, 1) & mask
        if (g == f).all():
            break
        f = g
    return f


def photo_mask_p013():
    cache = os.path.join(HERE, '..', '..', 'shots', 'full_rework', 'r1e', 'work', 'p013_photo_mask.npy')
    if os.path.exists(cache):
        return np.load(cache)
    ph = imgio.read(os.path.join(REFS, PH['p013'])).astype(float)
    R, G, B = ph[..., 0], ph[..., 1], ph[..., 2]
    car = (B / np.maximum(R, 1) > 0.72) | (B + G + R < 130)
    car = _er(_di(car, 2), 2)
    car = _di(_er(car, 4), 4)
    c = car[200:1000, 60:760]
    f = _flood(c, (300, 240))
    out = np.zeros(car.shape, bool)
    out[200:1000, 60:760] = f
    os.makedirs(os.path.dirname(cache), exist_ok=True)
    np.save(cache, out)
    return out


def first_x(mask, r, x0, x1, n=5):
    c = np.convolve(mask[r, x0:x1].astype(int), np.ones(n, int), 'valid')
    i = np.where(c == n)[0]
    return int(i[0]) + x0 if len(i) else None


def stats(name, d, extra=''):
    d = np.array([v for v in d if v is not None], float)
    if '--detail' in sys.argv:
        print('   series:', ' '.join('%+.0f' % v for v in d))
    if not len(d):
        print(name, 'no data'); return {}
    out = dict(mean=float(d.mean()), max_abs=float(np.abs(d).max()), mean_abs=float(np.abs(d).mean()))
    print('%-34s mean %+6.1f px (%+5.2f %%)   mean|d| %5.1f px   max|d| %5.1f px = %4.2f %% of the image width  %s' % (name, out['mean'], 100 * out['mean'] / W, out['mean_abs'], out['max_abs'], 100 * out['max_abs'] / W, extra))
    return out


def run(mdir):
    rep = {}
    # ---- p013
    ph = photo_mask_p013()
    a = _rgba(os.path.join(mdir, 'p013_mask.png'))[..., 3] > 127
    d = []
    for r in range(400, 801, 10):
        p, m = first_x(ph, r, 40, 900), first_x(a, r, 40, 900)
        if p is not None and m is not None and abs(p - m) < 60:
            d.append(p - m)
    rep['p013_front_edge'] = stats('p013 front edge (rows 400-800)', d, ' [+: photo further aft]')
    rep['p013_front_edge_shape'] = stats('  shape only (mean offset removed)', list(np.array(d, float) - np.mean(d)), ' [the bow: the front edge in plan]')
    def chamfer(am):
        out = []
        for c in range(170, 341, 10):
            pr, mr = np.where(ph[200:700, c])[0], np.where(am[200:700, c])[0]
            if len(pr) and len(mr):
                out.append(pr.min() - mr.min())        # photo top edge row - model top edge row (> 0: the model is wider)
        return out
    dc = chamfer(a)
    rep['p013_chamfer'] = stats('p013 corner chamfer (cols 170-340)', dc, ' [+: model wider than the photo]')
    dx = int(round(float(np.mean(d)))) if len(d) else 0
    rep['p013_chamfer_shape'] = stats('  shape only (model moved aft %d px)' % dx, chamfer(np.roll(a, dx, 1)), ' [the chamfer curve, nose x offset removed]')
    dcen = []
    for r in (590, 600, 610):
        p, m = first_x(ph, r, 40, 900), first_x(a, r, 40, 900)
        if p is not None and m is not None:
            dcen.append(p - m)
    rep['p013_centre'] = stats('p013 nose centre (rows 590-610)', dcen)
    # ---- p018
    if os.path.exists(os.path.join(mdir, 'p018_mask.png')):
        lum = imgio.read(os.path.join(REFS, PH['p018'])).astype(float).mean(-1)
        a = _rgba(os.path.join(mdir, 'p018_mask.png'))[..., 3] > 127
        d = []
        for r in range(625, 681, 5):
            p, m = first_x(lum > 110, r, 150, 700), first_x(a, r, 150, 700)
            if p is not None and m is not None:
                d.append(p - m)
        rep['p018_nose'] = stats('p018 nose silhouette (rows 625-680)', d, ' [+: photo further aft]')
    # ---- p016 FAR nose corner silhouette (R1e3): the left edge of the car at the corner's vertical edge, rows 700..750 (photo: first column with lum > 70, the thin bright edge line; model mask: first opaque column)
    if os.path.exists(os.path.join(mdir, 'p016_mask.png')):
        lum16 = imgio.read(os.path.join(REFS, PH['p016'])).astype(float).mean(-1)
        a16 = _rgba(os.path.join(mdir, 'p016_mask.png'))[..., 3] > 127
        d = []
        for r in range(700, 751, 10):
            p, m = first_x(lum16 > 70, r, 150, 700, n=1), first_x(a16, r, 150, 700)
            if p is not None and m is not None:
                d.append(p - m)
        rep['p016_far_corner'] = stats('p016 far corner silhouette (rows 700-750)', d, ' [+: photo further right = the model sticks out further]')
    # ---- p016: the light-bar line (the hood's front edge) projected through cam.py against the bar's top edge in the photo (steepest rise before the brightest row), columns 320..700
    try:
        import design2 as D
        from cam import Cam
        ph16 = imgio.read(os.path.join(REFS, PH['p016'])).astype(float).mean(-1)
        if '--r1c' in sys.argv:           # the R1c hood front edge (bowed: x = -2.48 + 0.09 (y / 0.67)^2 meets the raked R1c face)
            def le(y):
                x = -2.48 + D.FACE['bow'] * (y / 0.67) ** 2
                for _ in range(30):
                    x = float(D.face_x(y, float(D.hood_z(x))))
                return [x, y, float(D.hood_z(x))]
            b = np.array([le(y) for y in np.linspace(0, 0.67, 35)])
        else:
            b = D.NOSE['curves']['bar_top']
        P = Cam('p016').project(np.vstack([b * [1, -1, 1], b * [1, 1, 1]]))
        o = np.argsort(P[:, 0])
        d, dc = [], []
        for col in range(320, 701, 20):
            p = ph16[640:740, col]
            ip = int(np.argmax(p))
            top = 640 + int(np.argmax(np.gradient(p)[:ip + 1]))
            mrow = float(np.interp(col, P[o, 0], P[o, 1]))
            d.append(top - mrow)
        rep['p016_bar'] = stats('p016 light-bar top edge (cols 320-700)', d, ' [+: photo lower]')
        rep['p016_bar_centre'] = stats('p016 bar, centre columns (480-520)', [x for x, c in zip(d, range(320, 701, 20)) if 480 <= c <= 520])
    except Exception as e:
        print('p016 bar measure failed:', e)
    return rep


if __name__ == '__main__':
    rep = run(sys.argv[1])
    if '--save' in sys.argv:
        json.dump(rep, open(sys.argv[sys.argv.index('--save') + 1], 'w'), indent=1)
