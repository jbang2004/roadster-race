"""
Phase 2 report: the fitted 3D feature lines (lines/fit.json) against the current model, numpy + PIL only.

  python3 tools/blender/calib/lines_report.py OUTDIR

Writes OUTDIR/ortho.png (side elevation, plan and rear view: model curves blue, photo lines red, calibrated landmarks green),
OUTDIR/<photo>_lines.jpg (both sets projected on the photos) and prints the deviation table (max |d| per coordinate, with the jackknife sigma).
"""
import sys, os, json
import numpy as np
from PIL import Image, ImageDraw
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..'))
from cam import Cam
from crop import REF, PH

F = json.load(open(os.path.join(HERE, 'lines', 'fit.json')))
LM = json.load(open(os.path.join(HERE, 'result.json')))['landmarks']
RES = json.load(open(os.path.join(HERE, 'result.json')))
_mf = os.path.join(HERE, 'lines', 'model_feat.json')
MF = json.load(open(_mf)) if os.path.exists(_mf) else {}      # model features from the GLB (model_feat.py) for the lines with no design2 curve


def model_of(ln, f):
    """the model counterpart of a fitted line, sampled at the fit's axis values (None if there is none)"""
    if f['model'] is not None:
        return np.array(f['model'])
    if ln not in MF:
        return None
    P = np.array(f['pts']); Q = np.array(MF[ln]); a = 'xyz'.index(f['axis'])
    o = np.argsort(Q[:, a]); Q = Q[o]
    M = np.stack([np.interp(P[:, a], Q[:, a], Q[:, k], left=np.nan, right=np.nan) for k in range(3)], 1)
    if 'y' in f.get('fixed', ''):
        M[:, 1] = P[:, 1]
    if ln.startswith('arch'):            # the arch ends are near vertical: compare heights only where the lip is flatter than 45 deg
        g = np.abs(np.gradient(M[:, 2], M[:, 0]))
        M[g > 1.0] = np.nan
    return M


def table():
    rows = []
    print('%-9s %-58s  %s' % ('line', 'max |fit - model| (cm) at x / y / z  [jackknife sigma there, cm]', 'per-photo rms px'))
    for ln, f in F.items():
        P = np.array(f['pts']); S = np.array(f.get('sig_cv') or f['sig'])
        per = ' '.join('%s %.1f' % (k.replace(':-1', 'L').replace(':1', 'R'), v[1]) for k, v in f['per_photo'].items())
        M = model_of(ln, f)
        if M is None:
            print('%-9s %-58s  %s' % (ln, '(no model counterpart)', per))
            continue
        d = P - M
        cells = []
        for k in range(3):
            if k == 'xyz'.index(f['axis']) or not np.isfinite(d[:, k]).any():
                cells.append('%s   --         ' % 'xyz'[k]); continue
            i = int(np.nanargmax(np.abs(d[:, k])))
            sig = S[i, k]
            mark = '*' if abs(d[i, k]) > max(0.01, 2 * sig) else ' '
            cells.append('%s%+5.1f%s[%3.1f]' % ('xyz'[k], 100 * d[i, k], mark, 100 * sig))
            rows.append((ln, 'xyz'[k], d[i, k], sig, P[i]))
        print('%-9s %-58s  %s' % (ln, '  '.join(cells), per))
    return rows


def _font(n):
    from PIL import ImageFont
    for f in ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', '/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf'):
        if os.path.exists(f):
            return ImageFont.truetype(f, n)
    return ImageFont.load_default()


def ortho(out, s=230):
    """side elevation (top left), rear view (top right), plan (below; both sides mirrored).  blue = model, red = photo lines, green = calibrated landmarks / wheels"""
    m = 40
    sw, sh_, pw = int(5.4 * s), int(1.55 * s), int(2.5 * s)
    W, H = m + sw + m + pw + m, m + sh_ + m + int(2.5 * s) + m + 30
    im = Image.new('RGB', (W, H), (255, 255, 255)); d = ImageDraw.Draw(im)
    F1, F2 = _font(15), _font(12)
    xo = m + int(2.75 * s)
    zs = m + sh_                                   # z = 0 in the side view
    yp = m + sh_ + m + int(1.25 * s)               # y = 0 in the plan
    xr = m + sw + m + pw // 2                      # y = 0 in the rear view
    views = {'side': lambda P: (xo + P[:, 0] * s, zs - P[:, 2] * s),
             'plan': lambda P: (xo + P[:, 0] * s, yp - P[:, 1] * s),
             'rear': lambda P: (xr + P[:, 1] * s, zs - P[:, 2] * s)}
    d.text((m, 8), 'Side elevation (x to the right = rearwards)', fill=(0, 0, 0), font=F1)
    d.text((m + sw + m, 8), 'Rear view (from behind)', fill=(0, 0, 0), font=F1)
    d.text((m, m + sh_ + 14), 'Plan (from above)', fill=(0, 0, 0), font=F1)
    for y0, x0, x1 in ((zs, m, m + sw), (zs, m + sw + m, W - m)):
        d.line([(x0, y0), (x1, y0)], fill=(190, 190, 190))
    d.line([(m, yp), (m + sw, yp)], fill=(220, 220, 220))
    # 0.5 m grid ticks
    for xv in np.arange(-2.5, 2.51, 0.5):
        X = xo + xv * s; d.line([(X, zs), (X, zs + 6)], fill=(150, 150, 150)); d.text((X - 10, zs + 8), '%.1f' % xv, fill=(120, 120, 120), font=F2)
    for zv in np.arange(0.5, 1.51, 0.5):
        Z = zs - zv * s; d.line([(m + sw - 6, Z), (m + sw, Z)], fill=(150, 150, 150)); d.text((m + sw + 9, Z - 7), 'z=%.1f' % zv, fill=(120, 120, 120), font=F2)
    f = views['side']
    for ax, x in (('F', -1.487), ('R', 1.61)):
        z = RES['axle_z'][ax]; r = RES['rims']['RIM' + ax]['r']
        for rr, col in ((r, (120, 200, 120)), (z, (190, 190, 190))):
            t = np.linspace(0, 2 * np.pi, 100); P = np.stack([x + rr * np.cos(t), 0 * t, z + rr * np.sin(t)], 1)
            u, v = f(P); d.line(list(zip(u, v)), fill=col, width=1)
    for ln, fl in F.items():
        P = np.array(fl['pts']); M = model_of(ln, fl)
        SGa = np.array(fl.get('sig_cv') or fl['sig'])
        SGv = {'side': SGa[:, [0, 2]].max(1), 'plan': SGa[:, [0, 1]].max(1), 'rear': SGa[:, [1, 2]].max(1)}       # the sigma of what each view shows
        if M is not None:
            M = M[np.isfinite(M).all(1)]
        for k, f in views.items():
            if k == 'rear' and P[:, 0].min() < 1.3 and ln not in ('L_side', 'rail'):
                continue
            SG = SGv[k]
            for sd in ((-1, 1) if k != 'side' else (1,)):
                if M is not None and len(M):
                    u, v = f(M * [1, sd, 1]); d.line(list(zip(u, v)), fill=(70, 120, 255), width=2)
                u, v = f(P * [1, sd, 1])
                for j in range(len(u) - 1):        # red where the jackknife sigma is <= 3 cm, orange where the photos disagree / do not fix it
                    d.line([(u[j], v[j]), (u[j + 1], v[j + 1])], fill=(225, 30, 30) if SG[j] <= 0.03 else (255, 170, 60), width=2)
            if k == 'side':
                j = len(P) // 2; u, v = f(P[j:j + 1]); d.text((u[0] + 3, v[0] - 15), ln, fill=(150, 0, 0), font=F2)
    for n, l in LM.items():
        p = np.array([l['xyz']])
        for k, f in views.items():
            for sd in ((-1, 1) if k != 'side' else (1,)):
                u, v = f(p * [1, sd, 1]); d.ellipse([u[0] - 3, v[0] - 3, u[0] + 3, v[0] + 3], outline=(0, 150, 0), width=2)
    d.text((m, H - 24), 'blue = current model,  red = lines measured from the photos (orange: leave-one-photo-out sigma > 3 cm),  green = calibrated landmarks and wheels;  1 m = %d px' % s,
           fill=(0, 0, 0), font=F2)
    im.save(out)


def photos(outdir, names=('p018', 'p017', 'p016', 'p011', 'p013', 'r81', 'high')):
    """each line on the photos that saw it: model blue, photo line magenta (only the sides that photo traced)"""
    for ph in names:
        im = Image.open(REF + PH[ph]).convert('RGB'); d = ImageDraw.Draw(im); cm = Cam(ph)
        allp = []
        for ln, fl in F.items():
            sides = [int(k.split(':')[1]) for k in fl['per_photo'] if k.split(':')[0] == ph]
            M = model_of(ln, fl)
            for sd in sides:
                if M is not None:
                    Mm = M[np.isfinite(M).all(1)]
                    d.line([tuple(q) for q in cm.project(Mm * [1, sd, 1])], fill=(70, 120, 255), width=3)
                v = cm.project(np.array(fl['pts']) * [1, sd, 1])
                d.line([tuple(q) for q in v], fill=(255, 40, 200), width=3); allp += list(v)
        if allp:
            a = np.array(allp); x0, y0 = a.min(0) - 60; x1, y1 = a.max(0) + 60
            im = im.crop((int(max(0, x0)), int(max(0, y0)), int(min(im.size[0], x1)), int(min(im.size[1], y1))))
        im.save(os.path.join(outdir, '%s_lines.jpg' % ph), quality=88)


if __name__ == '__main__':
    out = sys.argv[1]; os.makedirs(out, exist_ok=True)
    table()
    ortho(os.path.join(out, 'ortho.png'))
    photos(out)
