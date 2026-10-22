"""numpy-only: the model's front-fender lines (L5 red, U magenta, L blue, the corner flap's seam pink) drawn on a press photo, with the coordinator's reading of the photo lines 1-4 of p016 as dashed lines
(1 yellow = hood edge, 2 cyan = crest, 3 green = middle / lower, 4 orange = wheel arch circle):
    python3 fender_overlay.py <view> <out.png> [--design <dir>] [--crop x0,y0,x1,y1] [--zoom 2]
view p016 (default crop 640,470,1240,830) / p018 (100,420,900,780) / p005 / p003 / p014 (both sides drawn; model lines only)
--design <dir>: take design2.py (and its curves2.py) from this directory instead of tools/blender (the BEFORE picture: ../backup/pre_fender3/blender)
"""
import sys, os
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
argv = sys.argv[1:]
arg = lambda n, d=None: argv[argv.index(n) + 1] if n in argv else d
design = os.path.abspath(arg('--design', HERE))
sys.path.insert(0, design)
sys.path.insert(1, HERE)
import design2 as D
import cam as C, proj_overlay as P, imgio
from fender_report import LINES16

REFS = os.path.abspath(os.path.join(HERE, '..', '..', '..', 'refs', 'press2'))
PHOTO = {'p016': 'telsa-roadster-2026-016.jpg', 'p018': 'tesla-roadster-2026-018.jpg', 'p005': 'tesla-roadster-2026-005.jpg', 'p003': 'tesla-roadster-2026-003.jpg', 'p014': 'tesla-roadster-2026-014.jpg', 'p013': 'tesla-roadster-2026-013-1.jpg'}
CROP = {'p016': (640, 470, 1240, 830), 'p018': (100, 420, 900, 780), 'p005': (0, 0, 1800, 1200), 'p003': (0, 0, 1800, 1200), 'p014': (380, 420, 900, 900)}
view, out = argv[0], argv[1]
crop = tuple(float(v) for v in arg('--crop', ','.join(str(c) for c in CROP[view])).split(','))
zoom = int(arg('--zoom', '2'))
img = imgio.read(os.path.join(REFS, PHOTO[view]))
x0, y0, x1, y1 = (int(c) for c in crop)
img = P.zoom_img(img[y0:y1, x0:x1].copy(), zoom)
cm = C.Cam(view)
U, L = D.CURVES['U'], D.CURVES['L']
n = D.NOSE['curves']
xs, xl = np.linspace(D.N[0], -1.0, 160), np.linspace(D.N[0], -1.3, 120)


def model(pts, col):
    for sd in ((-1, 1) if view == 'p014' else (-1,)):
        q = (cm.project(np.asarray(pts, float) * [1, sd, 1]) - [x0, y0]) * zoom
        for a, b in zip(q[:-1], q[1:]):
            P.stamp(img, a, b, col, 1)


def photo(pts, col):
    q = (np.asarray(pts, float) - [x0, y0]) * zoom
    for a, b in zip(q[:-1], q[1:]):
        k = int(max(abs(b[0] - a[0]), abs(b[1] - a[1]))) + 1
        for j in range(k):
            if (j // 6) % 2:
                continue
            p = a + (b - a) * (j / k)
            xi, yi = int(round(p[0])), int(round(p[1]))
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    if 0 <= yi + dy < img.shape[0] and 0 <= xi + dx < img.shape[1]:
                        img[yi + dy, xi + dx] = col


model(np.array(n['L5']), (255, 40, 40))
model(U.at(xs), (255, 0, 255))
model(L.at(xl), (60, 120, 255))
model(n['tri_seam'], (255, 140, 140))
if view == 'p016':
    for (name, pts), col in zip(LINES16.items(), [(255, 220, 0), (0, 255, 255), (60, 255, 60), (255, 150, 0)]):
        photo(pts, col)
imgio.write(out, img)
print('fender_overlay', view, out)
