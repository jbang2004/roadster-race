"""
R1d / R1e measuring tool (numpy only, no bpy): the model's key points of the rear buttress projected through the matched press cameras (cam.py) next to the points
read off the press photos, as px and % of the image width.  Also writes the model's rear lines for lines_overlay.py:

  python3 tools/blender/measure_rear.py [--lines out.json] [--csv out.csv]

Photo points were read from 3-4x crops of refs/press/r81.png, official-02, refs/press2/013-1 (see shots/full_rework/r1d/measure/*.jpg) and rechecked by the glass mask
(R-B > 22 | lum < 55) in p013.
"""
import sys, os, json
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import design2 as D
import shell2 as S
from cam import Cam

C = D.CURVES
P1, P3, E = (np.array(C[k], float) for k in ('P1', 'P3', 'E'))
P2 = C['rail'].at(D.X_SEAM)                                            # the crest at the seam (the facet's outer corner)
APEX = max((C['rail'].at(x) for x in np.linspace(-0.4, 2.4, 561)), key=lambda p: p[2])      # the highest point of the crest


def sym(p):
    return np.array([p[0], -p[1], p[2]])


# photo points (px, py) from the top-left of the photo.  L = left in the image = -y of the car's frame (left of the car seen from behind = +y... see cam.py: image right = +y for r81 / high)
PHOTO = {
    'r81': {'apex_L': (828.75, 633.75), 'apex_R': (1080.0, 633.75), 'P3_L': (887.5, 690.0), 'P3_R': (1032.5, 690.5), 'E_L': (852.5, 701.25), 'E_R': (1071.25, 701.25),
            'P1_L': (845.0, 670.0)},
    'high': {'P1_L': (836.7, 521.7), 'P1_R': (1204.0, 519.3), 'P2_L': (831.7, 690.7), 'P2_R': (1205.0, 688.3), 'P3_L': (900.0, 696.0), 'P3_R': (1138.3, 695.0)},
}


def model_points(view):
    cam = Cam(view)
    # image right = +y in r81 / high (camera behind the car looking forward): *_R = +y
    pts = {'apex': APEX, 'P1': P1, 'P2': P2, 'P3': P3, 'E': E}
    out = {}
    for k, p in pts.items():
        out[k + '_R'] = cam.project(p)
        out[k + '_L'] = cam.project(sym(p))
    return out, cam


def report(csv=None):
    rows = []
    for view, ph in PHOTO.items():
        mp, cam = model_points(view)
        w = cam.w
        for k, (px, py) in ph.items():
            m = mp[k]
            rows.append((view, k, px, py, m[0], m[1], 100 * (m[0] - px) / w, 100 * (m[1] - py) / w, 100 * np.hypot(m[0] - px, m[1] - py) / w))
        # widths
        for a, b, nm in (('P3_L', 'P3_R', 'glass base width'), ('E_L', 'E_R', 'ear (facet tip) spacing'), ('P2_L', 'P2_R', 'crest spacing at the seam'), ('apex_L', 'apex_R', 'apex spacing')):
            if a in ph and b in ph:
                wp = ph[b][0] - ph[a][0]
                wm = mp[b][0] - mp[a][0]
                rows.append((view, nm, wp, 0, wm, 0, 100 * (wm - wp) / wp, 0, 0))
    print('%-5s %-26s %8s %8s | %8s %8s | %7s %7s %7s' % ('view', 'point', 'photo x', 'photo y', 'model x', 'model y', 'dx %w', 'dy %w', 'err %w'))
    for r in rows:
        print('%-5s %-26s %8.1f %8.1f | %8.1f %8.1f | %+7.2f %+7.2f %7.2f' % r)
    if csv:
        with open(csv, 'w') as f:
            f.write('view,point,photo_x,photo_y,model_x,model_y,dx_pct_w,dy_pct_w,err_pct_w\n')
            for r in rows:
                f.write('%s,%s,%.1f,%.1f,%.1f,%.1f,%.2f,%.2f,%.2f\n' % r)
    return rows


def rear_lines():
    R = S.Registry()
    out = {}
    cols = {'rail': [1, 1, 0], 'gedge': [1, 0, 1], 'top': [0, 1, 1]}
    for k, col in cols.items():
        P = R._edge(k)
        for sd in (1, -1):
            out[f'{k}_{sd}'] = {'pts': [[float(p[0]), sd * float(p[1]), float(p[2])] for p in P], 'col': col}
    sr = R._edge('seam_row')
    out['seam'] = {'pts': [[float(p[0]), s * float(p[1]), float(p[2])] for s in (-1, 1) for p in (sr if s == 1 else sr[::-1])], 'col': [0, 1, 0]}
    for nm, p in (('P1', P1), ('P3', P3), ('E', E), ('P2', P2)):
        for sd in (1, -1):
            q = np.array([p[0], sd * p[1], p[2]])
            out[f'pt_{nm}_{sd}'] = {'pts': [[q[0] - 0.02, q[1], q[2]], [q[0] + 0.02, q[1], q[2]], [q[0], q[1], q[2]], [q[0], q[1] - 0.02, q[2]], [q[0], q[1] + 0.02, q[2]], [q[0], q[1], q[2] - 0.02], [q[0], q[1], q[2] + 0.02]], 'col': [1, 0.5, 0]}
    return out


if __name__ == '__main__':
    a = sys.argv[1:]
    report(a[a.index('--csv') + 1] if '--csv' in a else None)
    if '--lines' in a:
        json.dump(rear_lines(), open(a[a.index('--lines') + 1], 'w'))
        print('lines written')
