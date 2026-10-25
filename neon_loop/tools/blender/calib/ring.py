# ring.py PHOTO name cx cy a,b,phi,band [...] : (nozzles: NO_L NI_L NI_R NO_R) centre of a bright ring (outer edge, bright inside -> dark outside), robust conic fit; prints centre and axes
import sys, numpy as np, json, os
from wheel import lum, edges, robust, conic_params
ph = sys.argv[1]; L = lum(ph); a = sys.argv[2:]
fn = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rings', '%s.json' % ph)
out = json.load(open(fn)) if os.path.exists(fn) else {}
for i in range(0, len(a), 4):
    nm, cx, cy, ell = a[i], float(a[i + 1]), float(a[i + 2]), tuple(map(float, a[i + 3].split(',')))
    E = edges(L, cx, cy, 0, 0, n=120, drop=15, ell=ell)
    c, keep, d = robust(E[:, :2], tol=0.8)
    ctr, ax, v = conic_params(c)
    print('%s %s centre (%.2f, %.2f) axes %.2f %.2f kept %d/%d rms %.2f' % (ph, nm, ctr[0], ctr[1], ax[0], ax[1], keep.sum(), len(E), np.sqrt(np.mean(d[keep] ** 2))))
    out[nm] = [round(ctr[0], 2), round(ctr[1], 2), round(ax[0], 2), round(ax[1], 2)]
json.dump(out, open(fn, 'w'))
