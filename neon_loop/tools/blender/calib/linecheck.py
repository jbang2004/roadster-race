"""
The current model's feature curves (design2.CURVES, with the QF_* environment of this run) against the lines traced in the photos (calib/lines/traced.json):
rms / max image distance (px) of the traced points to the projected model curve, per line and photo.  numpy only.
The curves also take the shell's position fields (shell2.p3_dy: QF_P3_HIP / QF_P3_FRONT; shell2.p3_dx: QF_P3_TAILX), as the built car does.

  [QF_...=...] python3 tools/blender/calib/linecheck.py [LINE ...]
"""
import sys, os, json
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..'))
from lines import Seed, mirror, dist_to_poly
from linecfg import CFG
from cam import Cam

T = json.load(open(os.path.join(HERE, 'lines', 'traced.json')))


def morph(P):
    import shell2
    P = np.array(P, float)
    for k in range(len(P)):
        x, y, z = P[k]
        P[k, 1] += shell2.p3_dy(x, y, z)
        P[k, 0] += shell2.p3_dx(x, P[k, 1], z)
    return P


def check(names):
    tot = []
    for ln in names:
        c = CFG[ln]
        if not isinstance(c['seed'], str):
            continue
        S = Seed(c)
        t0, t1 = c['range']
        P = morph(S.at(np.linspace(t0, t1, 300)))
        cells = []
        for k, v in T.get(ln, {}).items():
            ph, sd = k.split(':')
            Q = np.array(v['pts'])
            if len(Q) < 5:
                continue
            d = dist_to_poly(Q, Cam(ph).project(mirror(P, int(sd))))
            cells.append('%s%s %.1f' % (ph, 'L' if sd == '-1' else 'R', np.sqrt(np.mean(d ** 2))))
            tot.append(d)
        print('%-8s %s' % (ln, '  '.join(cells)))
    a = np.concatenate(tot)
    print('all lines: rms %.2f px  median %.2f px  (%d points)' % (np.sqrt(np.mean(a ** 2)), np.median(a), len(a)))


if __name__ == '__main__':
    check(sys.argv[1:] or list(CFG))
