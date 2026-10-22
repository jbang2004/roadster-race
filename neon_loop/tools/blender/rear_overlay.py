"""
R1d: the model's OWN rear curves (taken from the built panels' shared edges, not from the design numbers) projected through the matched press cameras (cam.py) onto the press photos
and onto renders of the same view, as photo | render pairs.  Replaces the starting-value drawing of reading_overlay.py (same line set and colours):

  python3 tools/blender/rear_overlay.py --out <dir> [--render-dir <dir with p013.png p017.png ...>] [--views p017,p018,p013,r81,high] [--zoom 2] [--crop-ear]
  lines:  blue U (window lower edge), white wl (glass upper edge) + rail up to the window tip, red CREST (straight, window tip -> ear tip E), yellow glass edge (B seam -> P1 -> P3 -> seam),
          white glass end (seam), green P3 -> E (wing panel edge), orange dashed SOFT ARC (R1d2: the apex of the roll = the centre of the fold's turn, from the solved cross-sections design2.fold_section,
          which are the panels' rows), cyan dashed READING of the arc (design2.ARC_K), orange dotted roll ends (arc_lo: leaves the shoulder leg, arc_hi: joins the inclined leg)
  also prints the key points and, with --csv, writes them (the numbers the report quotes).
"""
import sys, os, argparse
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import design2 as D, shell2 as S, proj_overlay as P
from cam import Cam

REFS = os.path.abspath(os.path.join(HERE, '..', '..', '..', 'refs'))
PHOTO = {'p017': 'press2/tesla-roadster-2026-017.jpg', 'p018': 'press2/tesla-roadster-2026-018.jpg', 'p013': 'press2/tesla-roadster-2026-013-1.jpg',
         'r81': 'press/r81.png', 'high': 'press/2026-Tesla-Roadster-official-02.jpg', 'thrust': 'press/2026-Tesla-Roadster-rear-thrusters.jpg'}
CROP = {'p017': (560, 250, 1520, 660), 'p018': (880, 300, 1700, 640), 'p013': (980, 240, 1760, 960), 'r81': (640, 560, 1300, 800), 'high': (560, 360, 1520, 880), 'thrust': (0, 0, 1800, 1200)}
EAR = {'p017': (1250, 330, 1560, 480), 'p018': (1380, 330, 1700, 520), 'p013': (1480, 380, 1760, 560), 'r81': (780, 590, 1140, 730), 'high': (780, 480, 1260, 760)}
BOTH = {'p013', 'r81', 'high'}
COL = dict(U=(60, 140, 255), wl=(235, 235, 235), rail_front=(235, 235, 235), crest=(255, 50, 40), gedge=(255, 200, 0), glass_end=(235, 235, 235), end_to_ear=(60, 220, 90), arc=(255, 140, 0),
           arc_reading=(0, 220, 255), arc_lo=(255, 190, 120), arc_hi=(255, 190, 120))


def model_lines():
    ix = lambda x: int(np.argmin(abs(S.XS - x)))
    panels, R = S.build_panels()
    E = lambda n: R._edge(n)
    rail, ge = E('rail'), E('gedge')
    i_tip, i_p1, i_seam = S.I_TIP - S.I_W, S.IX(D.X_P1) - S.I_W, S.I_SEAM - S.I_W
    L = {}
    L['U'] = E('U')[ix(0.3):]
    L['wl'] = E('wl')[ix(0.3) - S.I_A:]
    L['rail_front'] = rail[ix(0.3) - S.I_W:i_tip + 1]
    L['crest'] = rail[i_tip:]
    L['gedge'] = ge[ix(0.65) - S.I_W:i_seam + 1]
    se = E('seam_row')
    L['glass_end'] = np.vstack([se[::-1], se[1:] * [1, -1, 1]])
    L['end_to_ear'] = ge[i_seam:]
    xs = np.linspace(D.X_FOLD0, 2.378, 160)
    L['arc'] = np.vstack([D.CURVES['arc'].at(xs), D.CURVES['E'][None]])
    L['arc_reading'] = D.CURVES['arc_reading'].at(np.linspace(D.X_FOLD0, 2.38, 120))
    L['arc_lo'] = D.CURVES['arc_lo'].at(xs[xs > D.X_FOLD0 + 0.02])
    L['arc_hi'] = D.CURVES['arc_hi'].at(xs[xs > D.X_FOLD0 + 0.02])
    return L


def key_points(L):
    C = D.CURVES
    return dict(C0=L['crest'][0], P1=np.array(C['P1']), P3=L['end_to_ear'][0], E=L['crest'][-1], arc_first=L['arc'][0], arc_last=L['arc'][-1])


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--render-dir', default='')
    ap.add_argument('--views', default='p017,p018,p013,r81,high')
    ap.add_argument('--zoom', type=float, default=2)
    ap.add_argument('--ear', action='store_true', help='crop the ear / arc region at zoom 4 instead of the whole rear')
    ap.add_argument('--arc-lines', action='store_true', help='also draw the roll ends (arc_lo / arc_hi)')
    ap.add_argument('--arc-table', action='store_true', help='print the distance (3-D cm, and px / %% of the image width in every view of --views) between the model arc (apex of the roll) and its photo reading (ARC_K), no images')
    a = ap.parse_args()
    if a.arc_table:
        xs = np.linspace(D.X_FOLD0 + 0.02, 2.37, 140)
        A_, R_ = D.CURVES['arc'].at(xs), D.CURVES['arc_reading'].at(xs)
        d3 = np.linalg.norm(A_ - R_, axis=1) * 100
        print('arc (apex of the roll) vs its photo reading ARC_K: 3-D (x-matched) mean %.1f cm, max %.1f cm' % (d3.mean(), d3.max()))

        def _dist(p, Q):
            u, v = Q[:-1], Q[1:]
            w = v - u
            t = np.clip(((p - u) * w).sum(1) / np.maximum((w * w).sum(1), 1e-9), 0, 1)
            return float(np.min(np.linalg.norm(u + t[:, None] * w - p, axis=1)))
        for v in a.views.split(','):
            cm, o = Cam(v), []
            for side in (1, -1):
                dd = np.array([_dist(p, cm.project(R_ * [1, side, 1])) for p in cm.project(A_ * [1, side, 1])])
                o.append((dd.mean(), dd.max()))
            print('  %-5s right side: mean %.1f px (%.2f %%) max %.1f px | left side: mean %.1f px max %.1f px' % (v, o[0][0], 100 * o[0][0] / 1800, o[0][1], o[1][0], o[1][1]))
        sys.exit(0)
    os.makedirs(a.out, exist_ok=True)
    L = model_lines()
    for k, v in key_points(L).items():
        print('%-10s' % k, np.round(v, 4))
    lines = {k: (v, COL[k]) for k, v in L.items() if a.arc_lines or k not in ('arc_lo', 'arc_hi')}
    for v in a.views.split(','):
        crop = (EAR if a.ear else CROP)[v]
        zoom = 4 if a.ear else a.zoom
        ph = os.path.join(REFS, PHOTO[v])
        out = os.path.join(a.out, f'{v}{"_ear" if a.ear else ""}.png')
        if a.render_dir:
            P.pair(v, ph, os.path.join(a.render_dir, v + '.png'), lines, crop, zoom, out, v in BOTH, dashed=('arc', 'arc_reading', 'arc_lo', 'arc_hi'))
        else:
            P.draw(v, ph, lines, crop, zoom, out, v in BOTH, dashed=('arc', 'arc_reading', 'arc_lo', 'arc_hi'))
        print('wrote', out)
