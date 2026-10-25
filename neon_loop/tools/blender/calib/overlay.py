"""
Check sheets for the calibration: python3 tools/blender/calib/overlay.py OUTDIR [photo ...]

Per photo: the picked points (green circles), the calibrated landmarks / rims reprojected through the calibrated camera (red crosses / ellipses) and through
the old camera (orange, matched photos only), on a crop around the car.  Reads result.json (solve.py).
"""
import sys, os, json, math
import numpy as np
from PIL import Image, ImageDraw
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from bundle import CamModel, side, base, X_AXLE
from crop import REF, PH

res = json.load(open(os.path.join(HERE, 'result.json')))
picks = json.load(open(os.path.join(HERE, 'picks.json')))
iv = json.load(open(os.path.join(HERE, 'init_views.json')))['matched']
tup = lambda v: (tuple(v[0]), tuple(v[1]), v[2], tuple(v[3]), tuple(v[4])) + tuple(v[5:])
out = sys.argv[1]; os.makedirs(out, exist_ok=True)
names = sys.argv[2:] or sorted(res['cameras'])


def lm(nm):
    p = np.array(res['landmarks'][base(nm)]['xyz'], float)
    if side(nm):
        p[1] *= side(nm)
    return p


def circle(axle, sd, steer, group):
    g = res['rims'].get('RIM' + axle + group) or res['rims']['RIM' + axle]
    s, r = g['abs_y'], g['r']
    st = math.radians(steer) if axle == 'F' else 0.0
    KP = 0.80
    c = np.array([X_AXLE[axle] - math.sin(st) * sd * (s - KP), sd * (KP + math.cos(st) * (s - KP)), res['axle_z'][axle]])
    ex = np.array([math.cos(st), math.sin(st), 0.0]); ez = np.array([0, 0, 1.0])
    t = np.linspace(0, 2 * np.pi, 120)
    return c + r * (np.cos(t)[:, None] * ex + np.sin(t)[:, None] * ez)


for ph in names:
    im = Image.open(REF + PH[ph]).convert('RGB')
    dr = ImageDraw.Draw(im)
    cams = [('new', CamModel('_n', tup(res['cameras'][ph]['view'])), (255, 40, 40))]
    if ph in iv:
        cams.append(('old', CamModel('_o', tup(iv[ph])), (255, 160, 0)))
    pts = picks.get(ph, {})
    ring = os.path.join(HERE, 'rings', ph + '.json')
    rings = json.load(open(ring)) if os.path.exists(ring) else {}
    allp = []
    for nm, (u, v, s) in pts.items():
        if base(nm) in res['landmarks']:
            dr.ellipse([u - 6, v - 6, u + 6, v + 6], outline=(0, 255, 0), width=2); allp.append((u, v))
    for nm, (u, v, a, b) in rings.items():
        dr.ellipse([u - 6, v - 6, u + 6, v + 6], outline=(0, 255, 0), width=2); allp.append((u, v))
    rimf = os.path.join(HERE, 'rims', ph + '.json')
    rims = json.load(open(rimf)) if os.path.exists(rimf) else {}
    for nm, E in rims.items():
        for q in E[::3]:
            dr.point((q[0], q[1]), fill=(0, 255, 0)); allp.append(tuple(q))
    for tag, c, col in cams:
        for nm in list(pts) + list(rings):
            if base(nm) not in res['landmarks']:
                continue
            u, v = c.project(c.p0, lm(nm))[0]
            dr.line([u - 7, v, u + 7, v], fill=col, width=2); dr.line([u, v - 7, u, v + 7], fill=col, width=2)
        for nm in rims:
            P = c.project(c.p0, circle(nm[3], -1.0, res['steer_deg'].get(ph, 0.0), '11' if ph in ('p011', 'p012') else ''))
            dr.line([tuple(p) for p in P], fill=col, width=1)
    if allp:
        a = np.array(allp)
        x0, y0 = a.min(0) - 120; x1, y1 = a.max(0) + 120
        im = im.crop((int(max(0, x0)), int(max(0, y0)), int(min(im.size[0], x1)), int(min(im.size[1], y1))))
    c0 = res['cameras'][ph]
    W = 1400
    if im.size[0] > W:
        im = im.resize((W, int(im.size[1] * W / im.size[0])), Image.LANCZOS)
    hdr = Image.new('RGB', (im.size[0], 22), (25, 25, 25))
    old = (' | old camera %.1f / %.1f px' % (c0['old_rms_px'], c0['old_max_px'])) if c0['old_rms_px'] is not None else ' | new camera'
    ImageDraw.Draw(hdr).text((6, 5), '%s  calibrated rms %.2f / max %.2f px (n %d)%s   green = picked, red = calibrated, orange = old camera' % (ph, c0['rms_px'], c0['max_px'], c0['n'], old), fill=(255, 255, 255))
    s = Image.new('RGB', (im.size[0], im.size[1] + 22)); s.paste(hdr, (0, 0)); s.paste(im, (0, 22))
    s.save(os.path.join(out, '%s_calib.jpg' % ph), quality=90)
    print('wrote', ph)
