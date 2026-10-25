# saverim.py PHOTO NAME cx cy a,b,phi,band [NAME cx cy ell ...] : append the kept rim-edge points to rims/PHOTO.json
import sys, json, os
import numpy as np
from wheel import lum, edges, robust, conic_params
ph = sys.argv[1]
fn = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rims', '%s.json' % ph)
out = json.load(open(fn)) if os.path.exists(fn) else {}
L = lum(ph)
a = sys.argv[2:]
for i in range(0, len(a), 4):
    nm, cx, cy, ell = a[i], float(a[i + 1]), float(a[i + 2]), tuple(map(float, a[i + 3].split(',')))
    E = edges(L, cx, cy, 0, 0, ell=ell)
    c, keep, d = robust(E[:, :2])
    ctr, ax, v = conic_params(c)
    out[nm] = E[keep, :2].round(2).tolist()
    print(ph, nm, ctr.round(2), ax.round(2), 'kept', keep.sum(), 'of', len(E), 'rms %.2f' % np.sqrt(np.mean(d[keep] ** 2)))
json.dump(out, open(fn, 'w'))
