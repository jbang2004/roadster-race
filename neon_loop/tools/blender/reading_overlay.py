"""Draw my reading of the roof-to-tail lines (3D, Blender car frame) on the press photos through the matched cameras.
   python3 reading.py <tools/blender dir> <refs dir> <out dir> [json overrides]"""
import sys, os, json
import numpy as np
TB, REFS, OUT = sys.argv[1:4]
sys.path.insert(0, TB)
import cam as C, imgio, design2 as D
D.build_all()
K = D.CURVES
os.makedirs(OUT, exist_ok=True)
PHOTO = {'p017': 'press2/tesla-roadster-2026-017.jpg', 'p018': 'press2/tesla-roadster-2026-018.jpg', 'p013': 'press2/tesla-roadster-2026-013-1.jpg',
         'r81': 'press/r81.png', 'high': 'press/2026-Tesla-Roadster-official-02.jpg'}
# crop boxes in photo px (x0, y0, x1, y1)
CROP = {'p017': (560, 250, 1520, 660), 'p018': (880, 300, 1700, 640), 'p013': (980, 240, 1760, 960), 'r81': (640, 560, 1300, 800), 'high': (560, 360, 1520, 880)}
BOTH = {'p013', 'r81', 'high'}


def bez(P0, P1, P2, P3, n=60):
    t = np.linspace(0, 1, n)[:, None]
    return (1 - t) ** 3 * P0 + 3 * (1 - t) ** 2 * t * P1 + 3 * (1 - t) * t ** 2 * P2 + t ** 3 * P3


def curve(name, x0, x1, n=60):
    xs = np.linspace(x0, x1, n)
    return np.array([K[name].at(x) for x in xs])


ov = json.loads(sys.argv[4]) if len(sys.argv) > 4 else {}
E = np.array(ov.get('E', K['E']), float)          # ear tip
P3 = np.array(ov.get('P3', K['P3']), float)       # glass end corner at the seam
X0 = ov.get('x0', 1.2)                            # crest start on the glass edge
C0 = np.array(K['rail'].at(X0))
U0x = ov.get('u0x', 0.88)
U0 = np.array(K['U'].at(U0x))
du = np.array(K['U'].at(U0x + 0.02)) - np.array(K['U'].at(U0x - 0.02)); du /= np.linalg.norm(du)
arc_mid = ov.get('arc', [[1.55, 0.66, 1.075], [2.15, 0.52, 1.045]])
ARC = bez(U0, np.array(arc_mid[0]), np.array(arc_mid[1]), E)
LINES = [   # name, pts, colour, thickness
    ('U', curve('U', -0.3, 1.2), (60, 140, 255), 2),
    ('wl', curve('wl', -0.3, 1.2), (235, 235, 235), 1),
    ('rail_front', curve('rail', -0.3, X0), (235, 235, 235), 1),
    ('crest', np.linspace(C0, E, 40), (255, 50, 40), 2),
    ('gedge', np.vstack([curve('gedge', 0.65, 1.34), np.linspace(K['P1'], P3, 30)]), (255, 200, 0), 2),
    ('glass_end', np.linspace(P3, P3 * [1, -1, 1], 30), (235, 235, 235), 1),
    ('end_to_ear', np.linspace(P3, E, 30), (60, 220, 90), 2),
    ('arc', ARC, (255, 140, 0), -2),
]


def segs(pts, dashed):
    out = []
    L = np.r_[0, np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))]
    for i, (a, b) in enumerate(zip(pts[:-1], pts[1:])):
        if dashed and int(L[i] // 14) % 2:
            continue
        out.append((a, b))
    return out


def stamp(img, a, b, col, r):
    n = int(max(abs(b[0] - a[0]), abs(b[1] - a[1])) * 2) + 2
    t = np.linspace(0, 1, n)
    xs, ys = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
    for dx in range(-r, r + 1):
        for dy in range(-r, r + 1):
            if dx * dx + dy * dy > r * r + 0.5:
                continue
            xi, yi = np.round(xs).astype(int) + dx, np.round(ys).astype(int) + dy
            ok = (xi >= 0) & (xi < img.shape[1]) & (yi >= 0) & (yi < img.shape[0])
            img[yi[ok], xi[ok]] = col


for v, rel in PHOTO.items():
    img = imgio.read(os.path.join(REFS, rel))
    cm = C.Cam(v)
    sc = img.shape[1] / cm.w
    sides = (-1, 1) if v in BOTH else (-1,)
    jobs = []
    for name, pts, col, th in LINES:
        for sd in sides:
            q = cm.project(pts * [1, sd, 1]) * sc
            jobs.append((segs(np.subtract(q, 0), th < 0), col, abs(th)))
    for sg, col, th in jobs:
        for a, b in sg:
            stamp(img, a, b, (0, 0, 0), th + 1)
    for sg, col, th in jobs:
        for a, b in sg:
            stamp(img, a, b, col, th)
    x0, y0, x1, y1 = CROP[v]
    x0, y0, x1, y1 = (int(c * sc) for c in (x0, y0, x1, y1))
    imgio.write(os.path.join(OUT, f'{v}.png'), img[y0:y1, x0:x1])
    print(v, 'E', np.round(cm.project(E * [1, -1, 1]) * sc), 'U0', np.round(cm.project(U0 * [1, -1, 1]) * sc))
