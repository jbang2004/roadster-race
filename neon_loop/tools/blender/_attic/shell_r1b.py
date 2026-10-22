"""
Procedural exterior shell of the 2026 Roadster (R1: primary volumes and main lines).

A low-poly quad cage is lofted from stations (rows) along x.  Every column of the half cross-section is a feature line:
    sill  (bottom edge of the black lower wall)      w1 w2 w3 (helper columns on the wall)      l3 (black / paint boundary)
    l1 (main character line)    l2 (window line = lower edge of the door glass)    wl (upper edge of the door glass / lens)
    rail (hood crease L5 -> roof rail -> buttress ridge L10)   gedge (foot of the ridge's inner wall)   gmid   top (centre line)
Feature edges carry subdivision creases, planar regions are coplanar quads, the front face and the tail face are ladder caps.
R1b (user correction): L1 is NOT continuous (front segment nose -> just ahead of the front arch, soft roll-over - crease weight 0.25 - over the wheel,
rear segment from the door front edge); L2 is the beltline arc; the A-pillar is one straight body-colour strip (cowl corner -> roof) that continues as the
roof rail -> buttress ridge.  Column l1b is a helper 0.12 m under l1 that controls the roll-over radius.
Catmull-Clark (Subsurf modifier, creases) then gives the hi mesh; the wheel arches are cut out of the dense mesh.
Frame: Blender car frame, x aft, y lateral (the right half y >= 0 is built, the left one is its mirror), z up, metres.

  build_shell(levels) -> (object in world space, info)       materials of the object: [Paint, Glass, Trim]
"""
import bpy, bmesh, math, os, sys
from mathutils import Vector

SIDE = 1


# ----------------------------------------------------------------------------- interpolation
def pchip(pts, x):
    """monotone cubic through (x, y) control points."""
    if x <= pts[0][0]:
        return pts[0][1]
    if x >= pts[-1][0]:
        return pts[-1][1]
    n = len(pts)
    h = [pts[i + 1][0] - pts[i][0] for i in range(n - 1)]
    d = [(pts[i + 1][1] - pts[i][1]) / h[i] for i in range(n - 1)]
    m = [d[0]] + [0.0 if d[i - 1] * d[i] <= 0 else 2 * d[i - 1] * d[i] / (d[i - 1] + d[i]) for i in range(1, n - 1)] + [d[-1]]
    for i in range(n - 1):
        if x <= pts[i + 1][0]:
            t = (x - pts[i][0]) / h[i]
            t2, t3 = t * t, t * t * t
            return ((2 * t3 - 3 * t2 + 1) * pts[i][1] + (t3 - 2 * t2 + t) * h[i] * m[i] + (-2 * t3 + 3 * t2) * pts[i + 1][1]
                    + (t3 - t2) * h[i] * m[i + 1])
    return pts[-1][1]


def smooth(a, b, x):
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3.0 - 2.0 * t)


# ----------------------------------------------------------------------------- the design (measured on the press photos)
# rows: x of the stations.  Row 0 is the front face, the last row the tail face (both special).
ROWS = [-2.40, -2.12, -1.85, -1.625, -1.42, -1.26, -1.12, -1.00, -0.55, -0.40, -0.28, 0.15, 0.65, 0.90, 1.20, 1.65, 2.05,
        2.28, 2.41]
# rows: windscreen base (end of L5), A-pillar base (foot), A-pillar top (roof), door front edge, B pillar (lens upper edge leaves the rail), window tip, wing seam
R_COWL, R_APIL, R_PILT, R_DOOR, R_B, R_TIP, R_SEAM = (ROWS.index(v) for v in (-1.625, -1.42, -0.40, -1.00, 0.65, 1.20, 2.05))
COLS = ['sill', 'w1', 'w2', 'w3', 'l3', 'l1b', 'l1', 'fu', 'l2', 'wl', 'rail', 'gedge', 'gmid', 'top']   # l1b / fu: holding loops FIL under / inboard of l1 (they set the radius of the roll-over where L1 is not creased)
CI = {n: i for i, n in enumerate(COLS)}

# column knots: (x, y, z)  (pchip in x for y and z separately)
K = {
    'sill': [(-2.40, 0.62, 0.22), (-2.12, 0.84, 0.20), (-1.85, 0.93, 0.19), (-1.4, 0.97, 0.19), (0.0, 0.98, 0.19), (1.65, 0.97, 0.19),
             (2.05, 0.95, 0.19), (2.28, 0.90, 0.19), (2.41, 0.82, 0.19)],
    'l3': [(-2.40, 0.66, 0.285), (-2.12, 0.92, 0.29), (-1.85, 1.02, 0.29), (-1.4, 1.05, 0.29), (-1.09, 1.052, 0.29), (0.0, 1.055, 0.399),
           (1.2, 1.055, 0.52), (1.9, 1.045, 0.59), (2.05, 1.035, 0.66), (2.28, 0.99, 0.79), (2.41, 0.90, 0.86)],
    # L1 (R1b spec correction): NOT continuous.  Front segment nose corner -> just ahead of the front arch (rows 0-2; rows <= 3 lie on the plane F),
    # smooth rolled fender over the wheel (rows 3-4: no crease), rear segment from the door front edge / side marker (row 5) to the tail corner.
    # The rear segment is the quadratic fit z = 0.8337 + 0.1029 x - 0.00258 x^2 of the traced photo line (018, residual < 2 mm) up to x 1.65.
    'l1': [(-2.40, 0.67, 0.535), (-2.12, 0.93, 0.60), (-1.85, 1.035, 0.74), (-1.625, 1.06, 0.80), (-1.42, 1.06, 0.883), (-1.30, 1.06, 0.841), (-1.20, 1.06, 0.806), (-1.12, 1.06, 0.778), (-1.06, 1.06, 0.757), (-1.0, 1.06, 0.735),
           (-0.4, 1.06, 0.792), (0.15, 1.06, 0.849), (0.65, 1.06, 0.8995), (1.15, 1.06, 0.9486), (1.65, 1.06, 0.9964), (2.05, 1.05, 1.025),
           (2.28, 1.0, 1.015), (2.41, 0.92, 1.0)],
    # rail = hood crease L5 (front) -> roof rail / hex edge (middle) -> buttress ridge L10 (rear)
    'rail': [(-2.40, 0.67, 0.535), (-2.12, 0.63, 0.70), (-1.85, 0.585, 0.80), (-1.625, 0.545, 0.87), (-1.42, 0.897, 0.905), (-1.00, 0.790, 1.051),
             (-0.40, 0.655, 1.283), (0.15, 0.60, 1.315), (0.65, 0.565, 1.30), (1.20, 0.515, 1.26), (1.65, 0.45, 1.18), (2.05, 0.42, 1.08),
             (2.28, 0.41, 1.06), (2.41, 0.40, 1.04)],
    # window line L2 (lower edge of the door glass = beltline): a gentle arc, flat under the door front, rising to the glass tip (traced on 018 / 013)
    'l2': [(-1.42, 0.92, 0.878), (-1.0, 0.92, 0.874), (-0.4, 0.917, 0.872), (0.15, 0.885, 0.930), (0.65, 0.825, 1.000), (0.90, 0.775, 1.040), (1.20, 0.62, 1.15)],
    'top': [(-2.40, 0.0, 0.565), (-2.12, 0.0, 0.68), (-1.85, 0.0, 0.79), (-1.625, 0.0, 0.87), (-1.42, 0.0, 0.94), (-1.0, 0.0, 1.09),
            (-0.40, 0.0, 1.303), (0.15, 0.0, 1.340), (0.65, 0.0, 1.325), (1.20, 0.0, 1.26), (1.65, 0.0, 1.15), (2.05, 0.0, 1.08),
            (2.28, 0.0, 1.05), (2.41, 0.0, 1.03)],
}

FACE_F = dict(x=-2.48, bow=0.09, rake=0.05)         # front face: x of the top edge at the centre line, plan bow (m at |y| = 0.67), rake (m over 0.3 m height)
# tail face x(z) at y = 0 (measured on the accepted rear), plan bow added
TAIL_X = [(0.19, 1.80), (0.30, 1.98), (0.40, 2.067), (0.50, 2.165), (0.60, 2.241), (0.70, 2.316), (0.80, 2.352), (0.90, 2.374), (1.00, 2.385),
          (1.08, 2.385)]


def kn(name, x):
    pts = K[name]
    return (pchip([(p[0], p[1]) for p in pts], x), pchip([(p[0], p[2]) for p in pts], x))


def front_x(y, z):
    return FACE_F['x'] + FACE_F['bow'] * (y / 0.67) ** 2 + FACE_F['rake'] * (0.545 - z) / 0.3


def tail_x(y, z):
    return pchip(TAIL_X, z) - 0.015 * (y / 0.9) ** 2           # (almost flat in plan: the visor and the lip roll were built for a near-square corner)


# ---- front end (R1b): ONE flat fender-top plane F (L5 -> L1) and a hood plane H with a gentle crown
NOSE_X, CORNER_X = -2.48, -2.39            # front face: x of the top edge at the centre line / at the corners (|y| 0.67): convex plan bow 0.09
HOOD = dict(x0=CORNER_X, z0=0.545, b=0.4248, k0=0.0, k1=0.0, t1=0.765)    # L5 (rail) is the straight line z = z0 + b (x - x0), y = RAIL_Y0 - RAIL_YS (x - x0)
RAIL_Y0, RAIL_YS = 0.67, 0.161
FOOT = (-1.42, 0.897, 0.905)               # the A-pillar's foot (the windscreen's lower side corner): F is the plane through L5 and this point (so it contains the cowl diagonal)
FEND = dict(c=(FOOT[2] - (0.545 + 0.4248 * (FOOT[0] - CORNER_X))) / (FOOT[1] - (0.67 - 0.161 * (FOOT[0] - CORNER_X))))   # fender top plane F: z = z0 + bF (x - x0) + c (y - 0.67)
FEND['b'] = HOOD['b'] + 0.161 * FEND['c']  # it contains L5, so bF = b + RAIL_YS c
FIL = float(os.environ.get('FIL', '0.06'))
# the roll over the front wheel has a VARIABLE radius: it starts as a hair-line where the creased front L1 ends (row 3, the cowl corner) and ends as a hair-line at the
# door cut where the creased rear L1 segment begins (a crease ending in a dart pinched the reflection): holding-loop distance per row
FIL_ROW = {3: 0.012, 4: 0.055, 5: 0.060, 6: 0.045, 7: 0.012}
if os.environ.get('FILROW'):
    FIL_ROW = {int(a.split(':')[0]): float(a.split(':')[1]) for a in os.environ['FILROW'].split(',')}


def fil_at(i):
    return FIL_ROW.get(i, FIL) * (FIL / 0.06)                                 # holding-loop distance around L1 (roll-over radius ~ FIL / 1.7 where L1 carries no crease)
RAIL_W, RAIL_H = 0.035, 0.022              # slim body-colour roof rail between the roof glass and the door glass (plan width, drop)
HW_K = [(0.15, 0.0), (0.65, 0.02), (1.20, 0.075), (1.65, 0.075), (2.05, 0.075), (2.28, 0.05), (2.41, 0.0)]     # ridge inner wall height (crest -> glass / deck)
DY_K = [(0.15, 0.0), (0.65, 0.017), (1.20, 0.06), (1.65, 0.075), (2.05, 0.12), (2.28, 0.07), (2.41, 0.0)]      # ... and its plan width


PILL_B = (ROWS[R_APIL], FOOT[1], FOOT[2])       # A-pillar: ONE straight line from the windscreen's lower corner (A) to the roof (T), traced on 018 / 013 / 016
PILL_T = (ROWS[R_PILT], 0.655, 1.283)
def l1_weight(i):
    """crease weight of the L1 segment between rows i and i + 1: full on the front segment (nose corner -> x -1.85), fading out over the next segment, none over
    the front wheel (a constant-radius roll made by the holding loops fu / l1b), full again from the door front edge (x -1.0) to the tail"""
    xe = ROWS[i + 1]
    if os.environ.get('L1_SHARP') == '1' and xe <= -1.0 + 1e-6:       # (debug) crease over the wheel too
        return 1.0
    if xe <= -1.85 + 1e-6:
        return 1.0
    if xe <= -1.625 + 1e-6:
        return L1_FADE
    if xe <= -1.0 + 1e-6:
        return 0.0
    return 1.0


L1_FADE = float(os.environ.get('L1_FADE', '1.0'))
FACETS = os.environ.get('FACETS', '1') == '1'          # R2: planar facets between the pillar foot and the door cut (instead of one twisted strip)


def cowl_pt(x):
    """the windscreen's lower-side edge (cowl diagonal): straight from the end of L5 (row R_COWL) to the pillar base"""
    xc = ROWS[R_COWL]
    yc = rail_y_hood(xc)
    a = (xc, yc, hood_z(xc, yc))
    t = (x - a[0]) / (PILL_B[0] - a[0])
    return tuple(a[k] + t * (PILL_B[k] - a[k]) for k in range(3))


def pillar_pt(x):
    t = (x - PILL_B[0]) / (PILL_T[0] - PILL_B[0])
    return tuple(PILL_B[k] + t * (PILL_T[k] - PILL_B[k]) for k in range(3))


def rail_y_hood(x):
    return RAIL_Y0 - RAIL_YS * (x - HOOD['x0'])


def hood_z(x, y):
    t = x - HOOD['x0']
    k = HOOD['k0'] + (HOOD['k1'] - HOOD['k0']) * min(1.0, max(0.0, t / HOOD['t1']))
    yr = rail_y_hood(x)
    return HOOD['z0'] + HOOD['b'] * t + k * max(0.0, 1.0 - (y / yr) ** 2)


def fender_z(x, y):
    return HOOD['z0'] + FEND['b'] * (x - HOOD['x0']) + FEND['c'] * (y - RAIL_Y0)


def build_rows():
    """-> P[row][col name] = (x, y, z) for the right half"""
    P = []
    for i, x in enumerate(ROWS):
        r = {}
        y, z = kn('sill', x); r['sill'] = (x, y, z)
        y3, z3 = kn('l3', x); r['l3'] = (x, y3, z3)
        for k, f in (('w1', 0.25), ('w2', 0.5), ('w3', 0.75)):
            r[k] = (x, r['sill'][1] + f * (y3 - r['sill'][1]), r['sill'][2] + f * (z3 - r['sill'][2]))
        y, z = kn('l1', x); r['l1'] = (x, y, z)
        y, z = kn('rail', x); r['rail'] = (x, y, z)
        if R_COWL < i < R_APIL:
            r['rail'] = (x, *cowl_pt(x)[1:])
        if R_APIL <= i <= R_PILT:
            r['rail'] = (x, *pillar_pt(x)[1:])
        r['top'] = (x, 0.0, kn('top', x)[1])
        if i <= R_COWL:
            # the front end: L5 is a straight line, the hood is one plane
            xr = x if i > 0 else CORNER_X
            yr_ = rail_y_hood(xr)
            r['rail'] = (x, yr_, hood_z(xr, yr_))
        if i <= R_APIL:
            # the fender top F is ONE plane from the nose to the pillar foot (it contains L5 and the cowl diagonal)
            xr = x if i > 0 else CORNER_X
            r['l1'] = (x, r['l1'][1], fender_z(xr, r['l1'][1]))
        if FACETS and R_APIL < i <= R_DOOR:
            # behind the foot the crest L1 falls in a straight line to the door cut (so the shoulder strip below splits into two PLANAR facets, see below)
            t = (x - ROWS[R_APIL]) / (ROWS[R_DOOR] - ROWS[R_APIL])
            f_l1 = (1.06, fender_z(ROWS[R_APIL], 1.06))
            d_l1 = kn('l1', ROWS[R_DOOR])
            r['l1'] = (x, f_l1[0] + (d_l1[0] - f_l1[0]) * t, f_l1[1] + (d_l1[1] - f_l1[1]) * t)
        y1, z1 = r['l1'][1], r['l1'][2]
        d = math.hypot(r['l3'][1] - y1, r['l3'][2] - z1)
        f = min(fil_at(i) / max(d, 1e-6), 0.4)
        r['l1b'] = (x, y1 + f * (r['l3'][1] - y1), z1 + f * (r['l3'][2] - z1))
        # window line and the lens' upper edge: the lens closes at the A-pillar corner (all merged) and widens from there
        if R_APIL < i <= R_TIP:
            y, z = kn('l2', x); r['l2'] = (x, y, z)
            yr_, zr_ = r['rail'][1], r['rail'][2]
            r['wl'] = (x, yr_ + RAIL_W, zr_ - RAIL_H) if i <= R_B else None       # slim paint rail between the door glass and the roof glass
        else:
            r['l2'] = r['rail']
            r['wl'] = r['rail']
            if i == R_APIL:
                # the A-pillar base: the pillar stripe starts here as a real (3.5 cm) strip; the door glass' front corner sits on its outer edge
                # (a corner where six creased edges meet in ONE vertex gave a swirl in the reflection)
                r['l2'] = r['wl'] = (x, r['rail'][1] + RAIL_W, r['rail'][2] - 0.010)
        if i == R_TIP:
            r['wl'] = r['l2']
        elif R_B < i < R_TIP:
            # the lens' upper edge leaves the rail between the B pillar and the tip, ending on l2 at the tip
            t = (x - ROWS[R_B]) / (ROWS[R_TIP] - ROWS[R_B])
            a = (ROWS[R_B], P[R_B]['rail'][1] + RAIL_W, P[R_B]['rail'][2] - RAIL_H)
            b = (ROWS[R_TIP], *kn('l2', ROWS[R_TIP]))          # straight from the B pillar to the glass tip (the tip is the window's rear point)
            r['wl'] = tuple(a[k] + (b[k] - a[k]) * t for k in range(3))
        # fu: holding loop on the shoulder, FIL from l1 towards l2 (rows <= the foot: l2 is on the rail: the fender top F)
        l1_, l2_ = Vector(r['l1']), Vector(r['l2'])
        dl = (l2_ - l1_).length
        r['fu'] = tuple(l1_ + (l2_ - l1_) * min(fil_at(i) / max(dl, 1e-6), 0.5)) if dl > 1e-6 else r['l1']
        if FACETS and R_APIL <= i <= R_DOOR:
            # the shoulder strip between the foot and the door cut (crest L1 outside, beltline L2 inside) is TWO planar facets split by the diagonal 'fu'
            # (foot corner on L1 -> beltline corner at the door cut): P1 = beltline / foot rung / diagonal (nearly level), P2 = diagonal / crest / door cut
            # (a 45 degree bevel).  Every edge of the two facets is a crease except the crest (the soft roll over the wheel).
            t = (x - ROWS[R_APIL]) / (ROWS[R_DOOR] - ROWS[R_APIL])
            f_l2 = (FOOT[1] + RAIL_W, FOOT[2] - 0.010)
            d_l2 = kn('l2', ROWS[R_DOOR])
            if i > R_APIL:
                r['l2'] = (x, f_l2[0] + (d_l2[0] - f_l2[0]) * t, f_l2[1] + (d_l2[1] - f_l2[1]) * t)
            f_l1 = (1.06, fender_z(ROWS[R_APIL], 1.06))
            r['fu'] = (x, f_l1[0] + (d_l2[0] - f_l1[0]) * t, f_l1[1] + (d_l2[1] - f_l1[1]) * t)
        # glass columns between the rail and the centre line; the ridge's inner wall (height hw, plan width dy) from the roof's rear end on
        yr, zr = r['rail'][1], r['rail'][2]
        zt = r['top'][2]
        hw = pchip(HW_K, x) if x > HW_K[0][0] else 0.0
        dy = pchip(DY_K, x) if x > DY_K[0][0] else 0.0
        ge_y, ge_z = yr - dy, zr - hw
        if i <= R_COWL:      # hood: crowned plane, interior columns at 2/3 and 1/3 of the L5 half width
            xr = x if i > 0 else CORNER_X
            fy = (2 / 3, 1 / 3)
            def hz(yy):
                if i > 0:
                    return hood_z(x, yy)
                xx = NOSE_X + FACE_F['bow'] * (yy / 0.67) ** 2           # row 0 (the leading edge): x on the face, z on the hood plane (a few fixed-point steps)
                for _ in range(4):
                    zz = hood_z(xx, yy)
                    xx = front_x(yy, zz)
                return hood_z(xx, yy)
            r['gedge'] = (x, yr * fy[0], hz(yr * fy[0]))
            r['gmid'] = (x, yr * fy[1], hz(yr * fy[1]))
            r['top'] = (x, 0.0, hz(0.0))
        else:
            if x > 0.65:     # the rear glass is (nearly) flat across: centre only 1.2 cm over the edges (the roof dome is the K table before that)
                crown = 0.045 + (0.012 - 0.045) * smooth(0.65, 1.20, x)
                zt = ge_z + crown
                r['top'] = (x, 0.0, zt)
            r['gedge'] = (x, ge_y, ge_z)
            r['gmid'] = (x, ge_y * 0.5, ge_z + (zt - ge_z) * 0.75)       # (parabolic crown through edge, mid, centre)
            if i >= R_SEAM:
                # behind the wing seam the glass is gone: the stowed wing panel carries the same cross-section as the glass in front of it
                # (centre low, ridges up, the outer plane falling to L1); its crest line runs on to the tail edge where it dies in a point
                r['gedge'] = (x, ge_y, ge_z)
                r['gmid'] = (x, ge_y * 0.5, ge_z)
                r['top'] = (x, 0.0, ge_z)
        P.append(r)
    # the lens tip: l2 / wl after the tip lie on the plane l1 -> rail at the tip's fraction
    tip = P[R_TIP]['l2']
    for i in range(R_TIP + 1, len(P)):
        l1, rl = P[i]['l1'], P[i]['rail']
        f = (P[R_TIP]['l1'][1] - tip[1]) / max(P[R_TIP]['l1'][1] - P[R_TIP]['rail'][1], 1e-6)
        pt = tuple(l1[k] + (rl[k] - l1[k]) * f for k in range(3))
        P[i]['l2'] = pt
        P[i]['wl'] = pt
    for i in range(R_APIL + 1, R_TIP):
        if P[i]['wl'] is None:
            P[i]['wl'] = P[i]['rail']
    # front / tail faces: every vertex of the first / last row lies on the face surface
    P[0] = {c: (front_x(p[1], p[2]), p[1], p[2]) for c, p in P[0].items()}
    P[-1] = {c: (tail_x(p[1], p[2]), p[1], p[2]) for c, p in P[-1].items()}
    return P


def same(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1]) + abs(a[2] - b[2]) < 1e-9


# ----------------------------------------------------------------------------- cage
def build_cage():
    P = build_rows()
    nR, nC = len(ROWS), len(COLS)
    bm = bmesh.new()
    cr = bm.edges.layers.float.new('crease_edge')
    CAPC = {}                           # ('c', row, rung, j) -> right-half coordinates of a cap-only vertex
    VK = {}

    def canon(i, c):
        p = P[i][COLS[c]]
        for c2 in range(c):
            if same(P[i][COLS[c2]], p):
                return c2
        return c

    def coords(key):
        if key[0] == 't':
            return P[key[1]][COLS[key[2]]]
        return CAPC[key]

    def vtx(sd, key):
        if key[0] == 't':
            key = ('t', key[1], canon(key[1], key[2]))
        p = coords(key)
        s = 0 if abs(p[1]) < 1e-12 else sd
        kk = (s, key)
        if kk not in VK:
            VK[kk] = bm.verts.new((p[0], s * p[1], p[2]))
        return VK[kk]

    def face(keys, mat, sds=(SIDE, -SIDE)):
        for sd in sds:
            vs = [vtx(sd, k) for k in keys]
            if sd != SIDE:
                vs = vs[::-1]
            u = []
            for v in vs:
                if v not in u:
                    u.append(v)
            if len(u) < 3:
                continue
            try:
                f = bm.faces.new(u)
            except ValueError:
                continue
            f.material_index = mat

    def strip_mat(i, c):
        a, b = COLS[c], COLS[c + 1]
        if b in ('w1', 'w2', 'w3', 'l3'):
            return 2                                   # Trim (black lower wall)
        if a == 'l2' and b == 'wl':
            return 1                                   # door glass (lens)
        if a == 'wl':
            return 0                                   # white band between the lens and the rail
        if a == 'rail' and b == 'gedge' and i >= R_B:
            return 0                                   # the ridge's inner wall is body colour
        if a in ('rail', 'gedge', 'gmid'):
            return 1 if R_COWL <= i < R_SEAM else 0    # roof / windscreen glass (the hood before the cowl, the deck behind the seam)
        return 0

    for i in range(nR - 1):
        for c in range(nC - 1):
            face([('t', i, c), ('t', i + 1, c), ('t', i + 1, c + 1), ('t', i, c + 1)], strip_mat(i, c))

    # ---- caps (ladders): rungs at the wall columns and at the top edge
    def cap(i, mat_of):
        row = P[i]
        fx = front_x if i == 0 else tail_x
        top_cols = []
        for cn in ('l1', 'fu', 'l2', 'wl', 'rail', 'gedge', 'gmid', 'top'):
            if not top_cols or not same(row[top_cols[-1]], row[cn]):
                top_cols.append(cn)
        ytop = [row[cn][1] for cn in top_cols]
        Y0 = ytop[0]
        rungs = []
        for k, rc in enumerate(('sill', 'w1', 'w2', 'w3', 'l3', 'l1b')):
            end = row[rc]
            ln = [('t', i, CI[rc])]
            for j, yy in enumerate(ytop):
                if j == 0:
                    continue
                y2 = end[1] * (yy / Y0)
                CAPC[('c', i, k, j)] = (fx(y2, end[2]), y2, end[2])
                ln.append(('c', i, k, j))
            rungs.append(ln)
        rungs.append([('t', i, CI[cn]) for cn in top_cols])
        for k in range(len(rungs) - 1):
            for j in range(len(ytop) - 1):
                face([rungs[k][j], rungs[k][j + 1], rungs[k + 1][j + 1], rungs[k + 1][j]], mat_of(k))
        return top_cols

    cap(0, lambda k: 2)
    cap(nR - 1, lambda k: 2 if k < 4 else 0)

    # ---- creases
    def crease_between(a, b, w=1.0):
        va, vb = vtx(SIDE, a), vtx(SIDE, b)
        for sd in (SIDE, -SIDE):
            va, vb = vtx(sd, a), vtx(sd, b)
            if va is vb:
                continue
            e = bm.edges.get((va, vb))
            if e is not None:
                e[cr] = w
                e.smooth = w < 0.99            # semi-sharp (run-out) edges are not marked sharp: no flat-shading step along them

    for cn in ('sill', 'l3', 'l1', 'l2', 'wl', 'rail'):
        for i in range(nR - 1):
            if cn in ('l2', 'wl') and i >= R_TIP:
                continue                                    # behind the window tip these columns are only construction points on the shoulder (no crease there)
            w = l1_weight(i) if cn == 'l1' else 1.0
            if w > 0:
                crease_between(('t', i, CI[cn]), ('t', i + 1, CI[cn]), w)
    if FACETS:
        for i in range(R_APIL, R_DOOR):                     # the diagonal between the two facets
            crease_between(('t', i, CI['fu']), ('t', i + 1, CI['fu']))
    for i in range(R_B, nR - 1):
        crease_between(('t', i, CI['gedge']), ('t', i + 1, CI['gedge']))
    for c in range(CI['rail'], nC - 1):                     # the cowl line (hood -> windscreen)
        crease_between(('t', R_COWL, c), ('t', R_COWL, c + 1))
    if os.environ.get('FOOT_CREASE', '1') == '1':
        crease_between(('t', R_APIL, CI['rail']), ('t', R_APIL, CI['l2']))       # the rear edge of the fender top F (it ends at the foot): a clean crease against the shoulder
        crease_between(('t', R_APIL, CI['l2']), ('t', R_APIL, CI['fu']))
        crease_between(('t', R_APIL, CI['fu']), ('t', R_APIL, CI['l1']))
    crease_between(('t', R_DOOR, CI['l1']), ('t', R_DOOR, CI['fu']))
    crease_between(('t', R_DOOR, CI['fu']), ('t', R_DOOR, CI['l2']))                          # front edge of the shoulder band (the door's front-top edge, where the rear L1 segment starts)
    for c in range(CI['rail'], nC - 1):                     # the wing seam (glass -> flat deck)
        crease_between(('t', R_SEAM, c), ('t', R_SEAM, c + 1))
    for i in (0, nR - 1):                                    # cap outlines
        for c in range(nC - 1):
            crease_between(('t', i, c), ('t', i, c + 1))
    for f in bm.faces:
        f.smooth = True
    return bm, P


def bm_from_cage():
    bm, P = build_cage()
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm, P


def build_shell(levels=3, arches=True):
    bm, P = bm_from_cage()
    me = bpy.data.meshes.new('ShellCage')
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new('ShellCage', me)
    bpy.context.scene.collection.objects.link(ob)
    return ob, dict(P=P)


def subdivided(cage, levels=3):
    """evaluate the Subsurf (with creases) -> new mesh object (world == local)"""
    md = cage.modifiers.new('Sub', 'SUBSURF')
    md.levels = levels
    md.render_levels = levels
    md.use_creases = True
    md.use_limit_surface = True
    md.quality = 3
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(cage.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
    cage.modifiers.remove(md)
    ob = bpy.data.objects.new('Shell', me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def feature_lines(P):
    out = {}
    col = {'sill': [0.5, 0.5, 1], 'l3': [0, 1, 1], 'l1': [1, 0.3, 0.3], 'l2': [1, 1, 0], 'wl': [1, 0.6, 0], 'rail': [0, 1, 0],
           'gedge': [1, 0, 1], 'gmid': [0.6, 0.6, 0.6], 'top': [1, 1, 1]}
    for c, rgb in col.items():
        for sd in (SIDE, -SIDE):
            out[f'{c}_{sd}'] = {'pts': [[p[c][0], sd * p[c][1], p[c][2]] for p in P], 'col': rgb}
    for i in range(len(P)):
        out[f'row{i}'] = {'pts': [[P[i][c][0], SIDE * P[i][c][1], P[i][c][2]] for c in COLS], 'col': [0.7, 0.7, 0.2]}
    return out


# ----------------------------------------------------------------------------- wheel arches (cut from the dense mesh) + tubs
HUBS = ((-1.487, -1), (-1.487, 1), (1.61, -1), (1.61, 1))      # (x, side)
HUB_Z = 0.39
R_ARCH = 0.415                                                  # arch radius (tyre 0.39): the arch top is at z 0.805
Y_TUB = 0.70                                                    # inner wall of the wheel well (the tyre's inner face is at 0.743)


def _gp(x, z, xh):
    return math.hypot(x - xh, z - HUB_Z) - R_ARCH


def cut_arches(ob, lmax=0.028):
    """cut the four circular wheel arches out of the side walls of the dense shell mesh and line them with a short black tub
    (cylinder from the skin to y = +-Y_TUB, closed by a disc).  The cut circle is exact: new vertices are put on it."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    Pr = build_rows()
    l1pts = [(ROWS[i], Pr[i]['l1'][2]) for i in range(len(ROWS))]
    for xh, sg in HUBS:
        def near(v):
            # only the side wall below L1 is worked on: refining across the L1 crease upset the shoulder / fender-top surface (a swirl in the reflection)
            return (abs(v.co.x - xh) < R_ARCH + 0.12 and v.co.z < HUB_Z + R_ARCH + 0.12 and sg * v.co.y > 0.78
                    and (-1.84 < v.co.x < -1.0 or v.co.z < pchip(l1pts, v.co.x) - 0.006))
        # refine the dense mesh around the circle
        for _ in range(4):
            es = [e for e in bm.edges if e.calc_length() > lmax and near(e.verts[0]) and near(e.verts[1])
                  and abs(_gp(e.verts[0].co.x, e.verts[0].co.z, xh)) < 0.14]
            if not es:
                break
            bmesh.ops.subdivide_edges(bm, edges=es, cuts=1, use_grid_fill=True)
        new = []
        for e in list(bm.edges):
            v0, v1 = e.verts
            if not (near(v0) and near(v1)):
                continue
            g0, g1 = _gp(v0.co.x, v0.co.z, xh), _gp(v1.co.x, v1.co.z, xh)
            if g0 * g1 < 0.0:
                _, nv = bmesh.utils.edge_split(e, v0, g0 / (g0 - g1))
                d = Vector((nv.co.x - xh, 0.0, nv.co.z - HUB_Z))
                d.normalize()
                nv.co.x, nv.co.z = xh + d.x * R_ARCH, HUB_Z + d.z * R_ARCH          # exactly on the circle
                new.append(nv)
        bmesh.ops.connect_verts(bm, verts=new)
        dead = []
        for f in bm.faces:
            c = f.calc_center_median()
            if sg * c.y > 0.78 and _gp(c.x, c.z, xh) < 0.0:
                dead.append(f)
        bmesh.ops.delete(bm, geom=dead, context='FACES')
        arc = [v for v in bm.verts if v.is_valid and v.is_boundary and abs(_gp(v.co.x, v.co.z, xh)) < 2e-5 and sg * v.co.y > 0.78]
        if len(arc) < 4:
            print('ARCH: no arc found for', xh, sg)
            continue

        def ang(v):
            a = math.degrees(math.atan2(v.co.z - HUB_Z, v.co.x - xh))
            return a + 360.0 if a < -90.0 else a
        arc.sort(key=ang)
        yin = sg * Y_TUB
        inner = [bm.verts.new((v.co.x, yin, v.co.z)) for v in arc]
        cen = bm.verts.new((xh, yin, HUB_Z))
        fs = []
        for k in range(len(arc) - 1):
            a, b = arc[k], arc[k + 1]
            if (a.co - b.co).length > 0.2:
                continue
            fs.append(bm.faces.new((a, b, inner[k + 1], inner[k])))
            fs.append(bm.faces.new((cen, inner[k], inner[k + 1])))
        fs.append(bm.faces.new((cen, inner[-1], inner[0])))
        for f in fs:
            f.material_index = 2
            f.smooth = True
            c = f.calc_center_median()
            if len(f.verts) == 4:                                    # lining: faces the wheel axis
                want = Vector((xh - c.x, 0.0, HUB_Z - c.z))
            else:                                                    # disc: faces outwards (towards the tyre)
                want = Vector((0.0, sg, 0.0))
            if f.normal.dot(want) < 0:
                f.normal_flip()
        for k in range(len(arc) - 1):
            e = bm.edges.get((arc[k], arc[k + 1]))
            if e is not None:
                e.smooth = False
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()


# ----------------------------------------------------------------------------- lower intake (R2): a pocket cut into the black front face
INTAKE = dict(y=0.60, z0=0.250, z1=0.378, depth=0.055)       # half width, opening bottom / top (z), depth of the recess (m, towards the tail)


def cut_intake(ob):
    """cut the rectangular lower intake out of the front face of the dense mesh: the outline is cut into the mesh with four bisect planes, then the
    enclosed faces are extruded `depth` towards the tail (a real recess with a floor and four walls, all Trim)."""
    I = INTAKE
    bm = bmesh.new()
    bm.from_mesh(ob.data)

    def region():
        g = [f for f in bm.faces if f.calc_center_median().x < -2.3 and f.normal.x < -0.4 and abs(f.calc_center_median().y) < I['y'] + 0.15
             and I['z0'] - 0.15 < f.calc_center_median().z < I['z1'] + 0.15]
        vs = {v for f in g for v in f.verts}
        es = {e for f in g for e in f.edges}
        return list(vs) + list(es) + g
    for co, no in (((0, I['y'], 0), (0, 1, 0)), ((0, -I['y'], 0), (0, 1, 0)), ((0, 0, I['z0']), (0, 0, 1)), ((0, 0, I['z1']), (0, 0, 1))):
        bmesh.ops.bisect_plane(bm, geom=region(), dist=1e-6, plane_co=co, plane_no=no)
    eps = 1e-4
    inner = [f for f in bm.faces if f.calc_center_median().x < -2.3 and f.normal.x < -0.4
             and -I['y'] < f.calc_center_median().y < I['y'] and I['z0'] < f.calc_center_median().z < I['z1']]
    ret = bmesh.ops.extrude_face_region(bm, geom=inner)
    newv = [e for e in ret['geom'] if isinstance(e, bmesh.types.BMVert)]
    newf = [e for e in ret['geom'] if isinstance(e, bmesh.types.BMFace)]
    bmesh.ops.translate(bm, verts=newv, vec=(I['depth'], 0, 0))
    bmesh.ops.delete(bm, geom=inner, context='FACES')
    nv_set = set(newv)
    caps = [f for f in newf if f.is_valid and all(v in nv_set for v in f.verts)]
    walls = [f for f in newf if f.is_valid and not all(v in nv_set for v in f.verts)]
    cen = Vector((0, 0, 0))
    for f in caps:
        cen += f.calc_center_median()
    cen /= max(len(caps), 1)
    for f in caps:
        f.material_index = 2
    for f in walls:
        f.material_index = 2
        c = f.calc_center_median()
        want = Vector((0.0, (cen.y - c.y) if abs(c.y) > 0.3 else 0.0, (cen.z - c.z) if abs(c.z - cen.z) > 0.04 else 0.0))     # a wall faces INTO the pocket
        if f.normal.dot(want) < 0:
            f.normal_flip()
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()


def add_floor(ob, z=0.188):
    """flat black underbody between the sills (hidden from every game camera, but closes the shell)."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    xs = [-2.36 + 0.15 * i for i in range(int((1.80 + 2.36) / 0.15) + 1)] + [1.80]
    rows = []
    for x in xs:
        y = max(0.0, pchip([(p[0], p[1]) for p in K['sill']], x) - 0.012)
        rows.append([bm.verts.new((x, -y, z)), bm.verts.new((x, 0.0, z)), bm.verts.new((x, y, z))])
    for a, b in zip(rows, rows[1:]):
        for j in range(2):
            f = bm.faces.new((a[j], a[j + 1], b[j + 1], b[j]))
            f.material_index = 2
            if f.normal.z > 0:
                f.normal_flip()
    bm.to_mesh(ob.data)
    bm.free()


def glass_half_width(x):
    """y of the glass edge (foot of the ridge's inner wall) at station x, from the design rows"""
    P = build_rows()
    pts = [(ROWS[i], min(P[i]['gedge'][1], P[i]['rail'][1])) for i in range(len(ROWS))]
    return pchip(pts, x)


def sharp_lines(ob):
    """polylines (one per edge) of the sharp edges and the material boundaries of a shell mesh, for the overlay tool"""
    me = ob.data
    out = {}
    face_mat = {}
    for p in me.polygons:
        for k in p.edge_keys:
            face_mat.setdefault(k, set()).add(p.material_index)
    n = 0
    for e in me.edges:
        k = tuple(sorted(e.vertices))
        sharp = e.use_edge_sharp
        mb = len(face_mat.get(k, ())) > 1
        if not (sharp or mb):
            continue
        a, b = me.vertices[e.vertices[0]].co, me.vertices[e.vertices[1]].co
        side = 'L' if (a.y + b.y) < 0 else 'R'
        out[f'sharp_{side}_{n}'] = {'pts': [[a.x, a.y, a.z], [b.x, b.y, b.z]], 'col': [1, 0.2, 0.2] if sharp else [0.2, 0.6, 1]}
        n += 1
    return out
