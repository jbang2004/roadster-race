"""numpy-only: draw model silhouette outlines (mask_views.py masks) on a press photo crop, zoomed:
   python3 outline_overlay.py <view> <x0,y0,x1,y1> <zoom> <out.jpg> <maskdir[:RRGGBB]> [<maskdir2[:RRGGBB]> ...]"""
import sys, os, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import imgio
from measure_masks import _rgba
from measure_nose import REFS, PH
view, box, zoom, out = sys.argv[1], [int(v) for v in sys.argv[2].split(',')], int(sys.argv[3]), sys.argv[4]
img = imgio.read(os.path.join(REFS, PH[view]))
x0, y0, x1, y1 = box
img = np.kron(img[y0:y1, x0:x1], np.ones((zoom, zoom, 1), np.uint8))
for spec in sys.argv[5:]:
    d, _, col = spec.partition(':')
    col = tuple(int(col[i:i + 2], 16) for i in (0, 2, 4)) if col else (255, 0, 0)
    a = _rgba(os.path.join(d, view + '_mask.png'))[..., 3] > 127
    a = np.kron(a[y0:y1, x0:x1], np.ones((zoom, zoom), bool))
    edge = a & ~(np.roll(a, 1, 0) & np.roll(a, -1, 0) & np.roll(a, 1, 1) & np.roll(a, -1, 1))
    edge = edge | np.roll(edge, 1, 0) | np.roll(edge, 1, 1)
    img[edge] = col
imgio.write(out, img)
