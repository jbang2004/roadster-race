"""Annotated press photos (front + side): surfaces as translucent fills, feature lines with labels, legend.  Self-contained SVG (photo embedded).
   python3 annot.py <refs dir> <out dir>"""
import sys, os, base64, subprocess
import numpy as np
import cam as C, design2 as D
D.build_all()
K, NO = D.CURVES, D.NOSE['curves']
REFS, OUT = sys.argv[1], sys.argv[2]
os.makedirs(OUT, exist_ok=True)
PHOTO = {'p016': 'press2/telsa-roadster-2026-016.jpg', 'p018': 'press2/tesla-roadster-2026-018.jpg', 'p013': 'press2/tesla-roadster-2026-013-1.jpg'}
HUBS = [(-1.487, 0.39), (1.61, 0.39)]
R_ARCH = 0.415
FONT = "font-family='PingFang SC, Hiragino Sans GB, STHeiti, sans-serif'"


def cv(name, x0=None, x1=None, n=80):
    c = K[name]
    a = c.x0 if x0 is None else max(x0, c.x0)
    b = c.x1 if x1 is None else min(x1, c.x1)
    return np.array([c.at(x) for x in np.linspace(a, b, n)])


def arr(k):
    return np.asarray(NO[k], float)


def rev(a):
    return a[::-1]


def mir(a):
    return np.asarray(a) * [1, -1, 1]


def arch_pts(i, a0=-10, a1=190, y=1.04, n=60):
    hx, hz = HUBS[i]
    a = np.radians(np.linspace(a0, a1, n))
    return np.stack([hx + R_ARCH * np.cos(a), np.full_like(a, y), hz + R_ARCH * np.sin(a)], 1)


def on_arch(P):
    return any(np.hypot(P[0] - hx, P[2] - hz) < R_ARCH for hx, hz in HUBS)


def split_by_arch(P):
    segs, cur = [], []
    for p in P:
        if on_arch(p):
            if len(cur) > 1: segs.append(np.array(cur))
            cur = []
        else:
            cur.append(p)
    if len(cur) > 1: segs.append(np.array(cur))
    return segs


def orient(a, start):
    a = np.asarray(a, float)
    return a if np.linalg.norm(a[0] - start) <= np.linalg.norm(a[-1] - start) else a[::-1]


Nn = np.array(D.N, float)
W = np.array(D.W, float)
AO = np.array(D.A_OUT, float)
AI = np.array(D.A_IN, float)
Lall = cv('L', n=400)
Lsegs = split_by_arch(Lall)                     # front part (N -> front arch), mid (front arch -> rear arch), rear
Lf, Lm = Lsegs[0], Lsegs[1]
L3all = cv('l3', n=400)
L3segs = split_by_arch(L3all)
L3f, L3m = L3segs[0], L3segs[1]
sill = cv('sill', n=200)
Ufront = cv('U', K['U'].x0, -1.43)
Urear = cv('U', -1.43, 1.2)
L5 = orient(arr('L5'), Nn)
cowl_e = orient(arr('cowl_edge'), W)
bar_top = orient(arr('bar_top'), Nn)            # N -> centre
bar_bot = orient(arr('bar_bot'), Nn)
cowl_d = cv('cowl_diag', n=10)

S = {}   # surfaces: name -> (polys3d per side, colour, label no.)
S['hood'] = [np.vstack([L5, cowl_e, rev(mir(cowl_e)), rev(mir(L5)), mir(bar_top), rev(bar_top)])]
S['fender_top'] = [np.vstack([L5, cowl_d, [AO], rev(Ufront)])]
S['lens'] = [np.vstack([Ufront, rev(cv('L', K['L'].x0, -1.43))])]
S['shoulder'] = [np.vstack([Urear, rev(cv('L', -1.43, 1.2))])]
# corner L6 face: L front -> down the front arch edge -> l3 front back to the nose -> up the face corner to N
fa = arch_pts(0, 180, 120)                       # front half of the front arch, from its bottom-front up
S['l6'] = [np.vstack([Lf, orient(fa, Lf[-1]), rev(L3f) if np.linalg.norm(L3f[-1] - fa[-1]) < np.linalg.norm(L3f[0] - fa[-1]) else L3f, [Nn]])]
ra = arch_pts(1, 180, 100)
fr = arch_pts(0, 60, 0)
S['door'] = [np.vstack([Lm, orient(ra, Lm[-1]), rev(L3m) if np.linalg.norm(L3m[-1] - ra[-1]) < np.linalg.norm(L3m[0] - ra[-1]) else L3m, orient(fr, L3m[0])])]
sm = sill[(sill[:, 0] > -1.05) & (sill[:, 0] < 1.2)]
l3m = L3m[(L3m[:, 0] > -1.05) & (L3m[:, 0] < 1.2)]
S['black'] = [np.vstack([l3m, rev(sm)])]
fe = orient(arr('face_edge_up'), bar_bot[0])
S['face'] = [np.vstack([rev(bar_bot), fe, [[fe[-1][0], 0.0, fe[-1][2]]]])]
S['face'].append(mir(S['face'][0]))
S['dglass'] = [np.vstack([cv('wl'), rev(Urear)])]
ge = cv('gedge', -1.625, 0.65)
S['roofglass'] = [np.vstack([ge, rev(mir(ge))])]

LINES = {   # name -> list of 3D polylines (left side), mirror flag
    'U': ([np.vstack([Ufront, Urear])], False),
    'L': ([s for s in Lsegs], False),
    'L3': ([s for s in L3segs], False),
    'L5': ([L5], True),
    'L4': ([np.vstack([rev(bar_top), mir(bar_top)])], False),
    'L7': ([orient(arr('hood_seam_L7'), [D.L7_X, 0.6, 0.8])], True),
    'pillar': ([cv('pillar_out', n=10), cv('pillar_in', n=10)], True),
    'wl': ([cv('wl')], False),
    'rail': ([cv('rail', -0.45, 1.2)], True),
    'arch': ([arch_pts(0), arch_pts(1)], False),
    'tri': ([np.vstack([arr('tri'), arr('tri')[:1]])], True),
    'marker': ([cv('L', -1.22, -0.89, 10)], False),
}
SCOL = {'hood': '#ffb000', 'fender_top': '#ff4d6d', 'lens': '#36c9ff', 'shoulder': '#36c9ff', 'l6': '#6bff7a', 'door': '#b18cff', 'black': '#00e0b8',
        'face': '#e8e8e8', 'dglass': '#4f8dff', 'roofglass': '#4f8dff'}
SNUM = {'hood': 1, 'fender_top': 2, 'lens': 4, 'shoulder': 5, 'l6': 6, 'door': 7, 'black': 8, 'face': 9, 'dglass': 10, 'roofglass': 10}
LSTY = {'U': ('#ff3b3b', 4, ''), 'L': ('#00e5ff', 4, ''), 'L3': ('#ffe100', 3, ''), 'L5': ('#ff9a00', 3, ''), 'L4': ('#ffffff', 4, ''),
        'L7': ('#ffffff', 2, '8 6'), 'pillar': ('#ffffff', 2, ''), 'wl': ('#ffffff', 1.5, ''), 'rail': ('#ffffff', 1.5, ''), 'arch': ('#bbbbbb', 2, '6 5'),
        'tri': ('#ff3df2', 3, ''), 'marker': ('#ffa000', 8, '')}
LEG_S = [(1, '#ffb000', '引擎盖中央大平面（前备箱盖 + cowl 窄条）'), (2, '#ff4d6d', '翼子板顶面（L5 与 U 之间，翻过 U）'), (3, '#ff3df2', '车头角三角翻板'),
         (4, '#36c9ff', '前翼子板侧面（U 与 L 之间的透镜，被轮拱切开）'), (5, '#36c9ff', '肩带（窗下沿与 L 之间，向后变宽）'),
         (6, '#6bff7a', '前角斜面 L6（L 以下、前轮之前的白色大平面）'), (7, '#b18cff', '车门 / 侧壁大平面（L 与 L3 之间）'),
         (8, '#00e0b8', '下部黑色楔形区（L3 以下，含碳纤门槛）'), (9, '#e8e8e8', '黑色前脸（灯带下方，含进气口、下扰流板）'), (10, '#4f8dff', '玻璃：挡风 + 车顶 + 侧窗')]
LEG_L = [('#ffffff', 4, '', 'L4 灯带（贯穿车头）'), ('#ff9a00', 3, '', 'L5 引擎盖棱（灯带端 → 挡风玻璃下角）'), ('#ffffff', 2, '8 6', 'L7 前备箱盖缝 / cowl 缝'),
         ('#ff3b3b', 4, '', 'U 翼子板顶棱：拱过前轮 → A 柱根 → 侧窗下沿 → 窗尖'), ('#00e5ff', 4, '', 'L 车身棱线：车头 → 被前轮拱切断 → 侧标 → 车尾'),
         ('#ffe100', 3, '', 'L3 下部黑区上沿（斜直线）'), ('#ffffff', 2, '', 'A 柱 / 窗上沿 / 车顶边梁'), ('#bbbbbb', 2, '6 5', 'L14 轮拱'),
         ('#ffa000', 8, '', '侧标（L 上的亮黑刀片 + 琥珀灯）'), ('#ffffff', 2, '3 4', 'L13 车门缝 / B 柱缝 / 门玻璃前缘（照片描）')]
# hand traced (photo px, full res): door cuts / seams that the model does not have yet
TRACE = {
    'p018': [('#ffffff', 2, '3 4', [(639, 579), (665, 684)]), ('#ffffff', 2, '3 4', [(1016, 521), (980, 678)]), ('#ffffff', 2, '3 4', [(1039, 428), (1020, 521)]),
             ('#ffffff', 2, '3 4', [(681, 527), (787, 432)])],
}
MY = lambda pts: [(x, 1189 - y) for x, y in pts]
FRONT_EDGE = [(162, 385), (143, 450), (135, 500), (132, 550), (131, 595)]
FRONT_EDGE = FRONT_EDGE + MY(FRONT_EDGE[::-1][1:])
HOOD13 = [(162, 385), (378, 428), (377, 761), (161, 804)] + FRONT_EDGE[::-1][1:-1]
FTOP13 = [(250, 346), (242, 401), (378, 428), (453, 315), (420, 290), (350, 292), (300, 300)]
TRI13 = [(162, 385), (250, 346), (242, 401)]
SEAM13 = [(313, 418), (303, 500), (300, 595), (303, 690), (313, 772)]
TPOLY = {'p013': [(1, '#ffb000', HOOD13), (2, '#ff4d6d', FTOP13), (2, '#ff4d6d', MY(FTOP13)), (3, '#ff3df2', TRI13), (3, '#ff3df2', MY(TRI13))]}
TRACE['p013'] = [('#ff9a00', 3, '', [(162, 385), (378, 428)]), ('#ff9a00', 3, '', MY([(162, 385), (378, 428)])), ('#ffffff', 2, '8 6', SEAM13),
                 ('#ffffff', 4, '', FRONT_EDGE), ('#ff3df2', 3, '', TRI13 + TRI13[:1]), ('#ff3df2', 3, '', MY(TRI13 + TRI13[:1]))]
VIEW_SURF = {'p016': ['face', 'hood', 'fender_top', 'lens', 'shoulder', 'l6', 'door', 'black', 'dglass', 'roofglass'],
             'p018': ['lens', 'shoulder', 'l6', 'door', 'black', 'dglass', 'fender_top'],
             'p013': ['roofglass', 'dglass']}
VIEW_LINES = {'p016': ['arch', 'L3', 'L', 'U', 'L5', 'L4', 'L7', 'pillar', 'wl', 'rail', 'tri', 'marker'],
              'p018': ['arch', 'L3', 'L', 'U', 'L5', 'pillar', 'wl', 'rail', 'marker'],
              'p013': ['pillar', 'wl', 'rail']}
LEGEND_AT = {'p016': (30, 40), 'p018': (30, 40), 'p013': (30, 40)}


def pts_attr(q):
    return ' '.join(f'{x:.1f},{y:.1f}' for x, y in q)


def build(v):
    rel = PHOTO[v]
    src = os.path.join(REFS, rel)
    jpg = os.path.join(OUT, f'_{v}.jpg')
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-i', src, '-q:v', '4', jpg], check=True)
    b64 = base64.b64encode(open(jpg, 'rb').read()).decode()
    cm = C.Cam(v)
    w, h = cm.w, cm.h
    sides = (-1, 1) if v == 'p013' else (-1,)
    P = lambda a, s=-1: cm.project(np.asarray(a, float) * [1, -s if False else 1, 1] * [1, 1 if s == 1 else 1, 1])
    H = w
    o = [f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {w} {H}' width='{w}' height='{H}' {FONT}>", f"<rect x='0' y='0' width='{w}' height='{H}' fill='#111'/>",
         f"<image href='data:image/jpeg;base64,{b64}' x='0' y='0' width='{w}' height='{h}'/>",
         "<defs><mask id='noarch'><rect x='0' y='0' width='100%' height='100%' fill='white'/>"]
    for i in (0, 1):
        for s in sides:
            ap = arch_pts(i, -20, 200, n=60)
            ap = np.vstack([ap, [[HUBS[i][0], 1.04, -0.2]]])
            o.append(f"<polygon points='{pts_attr(cm.project(ap * [1, s, 1]))}' fill='black'/>")
    o.append("</mask></defs><g mask='url(#noarch)'>")
    cents = []
    for k in VIEW_SURF[v]:
        for poly in S[k]:
            for s in sides:
                q = cm.project(poly * [1, s, 1])
                o.append(f"<polygon points='{pts_attr(q)}' fill='{SCOL[k]}' fill-opacity='0.30' stroke='none'/>")
                cents.append((SNUM[k], q.mean(0), SCOL[k]))
    for n, col, pts in TPOLY.get(v, []):
        q = np.array(pts, float)
        o.append(f"<polygon points='{pts_attr(q)}' fill='{col}' fill-opacity='0.34' stroke='none'/>")
        cents.append((n, q.mean(0), col))
    o.append('</g>')
    for k in VIEW_LINES[v]:
        polys, mirror = LINES[k]
        col, wd, da = LSTY[k]
        for poly in polys:
            for s in (sides if not mirror else (-1, 1)):
                if v != 'p013' and mirror and s == 1 and k not in ('L5', 'L7', 'tri', 'pillar', 'rail'):
                    continue
                if v == 'p018' and s == 1:
                    continue
                q = cm.project(poly * [1, s, 1])
                o.append(f"<polyline points='{pts_attr(q)}' fill='none' stroke='#000' stroke-opacity='0.55' stroke-width='{wd + 3}' stroke-linecap='round' stroke-linejoin='round'{f' stroke-dasharray={chr(39)}{da}{chr(39)}' if da else ''}/>")
                o.append(f"<polyline points='{pts_attr(q)}' fill='none' stroke='{col}' stroke-width='{wd}' stroke-linecap='round' stroke-linejoin='round'{f' stroke-dasharray={chr(39)}{da}{chr(39)}' if da else ''}/>")
    for col, wd, da, pts in TRACE.get(v, []):
        q = np.array(pts, float)
        o.append(f"<polyline points='{pts_attr(q)}' fill='none' stroke='#000' stroke-opacity='0.55' stroke-width='{wd + 3}' stroke-dasharray='{da}'/>")
        o.append(f"<polyline points='{pts_attr(q)}' fill='none' stroke='{col}' stroke-width='{wd}' stroke-dasharray='{da}'/>")
    seen = set()
    for n, c, col in cents:
        key = (n, int(c[0] // 120), int(c[1] // 120))
        if key in seen:
            continue
        seen.add(key)
        o.append(f"<circle cx='{c[0]:.0f}' cy='{c[1]:.0f}' r='17' fill='{col}' stroke='#000' stroke-width='2'/>"
                 f"<text x='{c[0]:.0f}' y='{c[1] + 7:.0f}' text-anchor='middle' font-size='20' font-weight='700' fill='#000'>{n}</text>")
    if LEGEND_AT[v]:
        top = h + 70
        x0 = 30
        o.append(f"<text x='{x0}' y='{top}' font-size='26' fill='#fff' font-weight='700'>面（编号 = 图中圆点）</text>")
        y = top + 50
        for n, col, t in LEG_S:
            o.append(f"<circle cx='{x0 + 11}' cy='{y - 6}' r='11' fill='{col}' stroke='#000'/><text x='{x0 + 11}' y='{y - 1}' text-anchor='middle' font-size='13' font-weight='700'>{n}</text>"
                     f"<text x='{x0 + 32}' y='{y}' font-size='22' fill='#fff'>{t}</text>")
            y += 46
        x0 = 930
        o.append(f"<text x='{x0}' y='{top}' font-size='26' fill='#fff' font-weight='700'>线</text>")
        y = top + 50
        for col, wd, da, t in LEG_L:
            o.append(f"<line x1='{x0}' y1='{y - 6}' x2='{x0 + 26}' y2='{y - 6}' stroke='{col}' stroke-width='{min(wd, 6)}'{f' stroke-dasharray={chr(39)}{da}{chr(39)}' if da else ''}/>"
                     f"<text x='{x0 + 34}' y='{y}' font-size='22' fill='#fff'>{t}</text>")
            y += 46
    o.append('</svg>')
    path = os.path.join(OUT, f'{v}_annot.svg')
    open(path, 'w').write('\n'.join(o))
    os.remove(jpg)
    return path


for v in sys.argv[3].split(',') if len(sys.argv) > 3 else PHOTO:
    print(build(v))
