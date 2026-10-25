"""
Exterior shell of the 2026 Roadster, version 2 (R1c): PANELS bounded by FAIR 3D SPLINES instead of a Catmull-Clark cage.

  curves   design2.py: every feature line is a fair spline with few control points (cubic B-spline fits of the traced photo data, straight lines where the
           car has straight lines).  They are the only coupling between panels.
  edges    a registry of SAMPLED boundary polylines (Registry.edge): one array per shared boundary, index-aligned to the global station list XS, used verbatim by
           every panel that touches it -> the panels are watertight by construction (no T-junctions, no slivers: panels that meet at a corner END at a real corner point).
  panels   each panel is a named generator that is a pure function of its boundary edges and its own parameters (PANELS below):
             strips      ruled surface between two edges (+ optional bulge / crown profile), the SAME division count in every row (CONST_M), a wedge ends in a point
             fender_top  height field over the hood plane (tangent to the hood along L5, rounded over to the crest U)
             Coons       planar / explicit patches (hood, front face, tail face)
           Crease edges are panel boundaries; they get ONE small fillet (bevel) on the dense mesh; no subdivision surface anywhere.
  lock     tools/blender/shell_lock.json holds a checksum (rounded vertex positions + topology) per ACCEPTED panel; the build fails loudly if a locked panel
           changed, unless it is unlocked for the round (--unlock a,b / SHELL_UNLOCK=a,b).   --check-lock only checks and exits.

Frame: Blender car frame, x aft, y lateral, z up, metres; the right half (y >= 0) is built, the left half is its mirror (centre-line vertices are welded).

  build_shell2(bevel=True) -> bpy object 'Shell' (materials Paint / Glass / Trim as the old shell: 0 / 1 / 2)
  cut_arches(ob), glass_half_width(x), feature_lines(), panel_report() ...
"""
import os, sys, json, math, hashlib
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import design2 as D

LOCK_FILE = os.path.join(HERE, 'shell_lock.json')
PAINT, GLASS, TRIM = 0, 1, 2
C = D.CURVES

# ----------------------------------------------------------------------------- stations
BREAKS = [-2.39, -2.0, -1.625, -1.43, -1.0, -0.4, 0.15, 0.65, 1.2, 1.65, 1.8, 2.05, 2.28, 2.40]
SEG_STEP = [(-2.39, -1.0, 0.0125), (-1.0, 1.2, 0.020), (1.2, 2.40, 0.016)]


# q16: U turns into the plane P1 over its last ~3 cm (design2 QF_Q16_UX0): the last TIP_REF[0] station intervals before the window tip are each split into TIP_REF[1] (the other stations do not move)
TIP_REF = tuple(int(v) for v in os.environ.get('TIP_REF', '3,4' if D.QF_Q16 else '0,1').split(','))


def make_stations():
    xs = [BREAKS[0]]
    for a, b in zip(BREAKS[:-1], BREAKS[1:]):
        h = next(h for (lo, hi, h) in SEG_STEP if lo - 1e-9 <= a and b <= hi + 1e-9)
        n = max(1, int(round((b - a) / h)))
        xs += list(np.linspace(a, b, n + 1)[1:])
    xs = np.array(xs)
    k, m = TIP_REF
    if k > 0 and m > 1:
        it = int(np.argmin(abs(xs - 1.2)))
        sub = np.concatenate([np.linspace(xs[j], xs[j + 1], m + 1)[1:-1] for j in range(it - k, it)])
        xs = np.sort(np.r_[xs, sub])
    return xs


XS = make_stations()
NS = len(XS)


def IX(x):
    i = int(np.argmin(abs(XS - x)))
    assert abs(XS[i] - x) < 1e-9, x
    return i


def IXN(x):
    """the station nearest x (for the stations named by their old index aft of the tip)"""
    i = int(np.argmin(abs(XS - x)))
    assert abs(XS[i] - x) < 1e-3, x
    return i


I_W, I_A, I_DOOR, I_T, I_B, I_TIP, I_SILL, I_SEAM = (IX(v) for v in (-1.625, -1.43, -1.0, -0.4, 0.65, 1.2, 1.8, 2.05))
I_LAST = NS - 1
# rearcrease: the rear-corner facet (SPEC L12).  Its front edge is the straight line E -> S, E = the l3 sample I_FE (x 2.149), S = the L sample I_FS (x 1.972): in p018 the perpendicular distance of
# E, S to the photo's crease is < 2 px.  l3 is already a straight 3D line aft of x 1.99; the facet is the PLANE through that line and the tail face's side edge; L aft of S becomes the straight line S -> L end
# lying in that plane (design: facet_L), so the facet is planar by construction.
I_FS, I_FE = IXN(1.9719), IXN(2.1486)         # (stations 269, 280 without TIP_REF)
I_WF0 = IXN(1.5054)                 # (station 240) the wall's rows start to fan towards S at this station (x 1.80, the wheel arch's rear end; nothing forward of x 1.5 changes, the apillar rule): the rows' L partner lags behind the l3 sample
WALL_BAND = 0.9                     # rearcrease: the share of a wall row (from the l3 end) over which the continuous ruling is kept; the top 40 % absorb the one-station quantisation of the L partner
X_BIRTH = float(os.environ.get('X_BIRTH', '0.0'))        # rearcrease round 4 (VARIANT, off by default: reflect check showed coarser arcs but concentric rings in p018 h and a 18 degree crease fading along U): the ruling rows blend into the fold over D.X_FOLD0 .. X_BIRTH
I_L3K0 = IXN(1.5054)                # (station 240) rearcrease 2: from this station (x 1.505) the l3 plan is replaced forward of the kink (nothing forward of x 1.5 moves)
L3_FRONT_DEG = float(os.environ.get('L3_FRONT_DEG', '3.0'))     # plan angle of l3 just forward of the kink at E (aft of it: 14.85 degrees)
# 2026-10-24 (user: "尾翼两边的梯形平面应该是前面的车身的延伸，模型似乎折了一个角度对吗？"): the facet (the wing's endplate, aft of the side seam) is the side carried on, not a plane folded
#   12 deg off it.  p018: the side's tone and its reflection band run on across the seam unchanged; p017: the trapezoid has the side's tone (the model's was white against grey).  L and l3
#   now turn into the facet's plane SMOOTHLY (G2, plan only) and arrive on its straight lines tangentially; the wall, ruled between them, becomes tangent to the plane, the facet edge
#   E -> S is no crease any more (the wing seam, a hairline aft of it, stays).  The plane, its straight lines, the tail corner and the endplate's hinge (L aft of the seam) do not move.
_fc_ = os.environ.get('QF_FC', '1.88,2.10,2.00,2.30')
QF_FC = tuple(float(v) for v in _fc_.split(',')) if ',' in _fc_ else None      # (x where L leaves its old plan, x where it joins the facet's straight edge, the same two for l3: it
#   leaves the old kinked l3 (rearcrease round 2, its plan curve forward of E kept) and joins its straight line aft of E); 0 = the creased facet (L turned 12.6 deg at S, l3 11.5 deg at E)
#   p013 (top view): the side's top edge turns into the facet's line within ~8 cm at the seam, a tight but round turn; L's turn here runs -2 -> -16 deg over x 1.93 - 2.03 (it cuts in
#   2.1 mm at S), l3's -8 -> -15 deg over 2.05 - 2.28 (5.8 mm in at E; a 1 deg swing out first, where the kinked l3 swung out 4.5 deg).  A 30 cm turn (1.80 - 2.10) read rounder than p013.
                                    # (wall_pairs).  Tried 240 (x 1.51): the integer lag steps are spread thinly over 40 rows and the reflection of the wall is a sawtooth; 258 packs them into 22 rows: squeezed but smooth


def xlist(i0, i1, x0=None, x1=None, K=12, pins=None, K0=None):
    """x of the master stations i0..i1; the first / last K intervals are squeezed so that the list starts at x0 / ends at x1 (a curve that starts or ends on the front /
    tail face, which is raked: its end is not at the station x).  Index alignment between curves is kept."""
    x = XS[i0:i1 + 1].copy()
    if x0 is not None and abs(x0 - x[0]) > 1e-9:
        k = min(K0 or K, len(x) - 2)           # K0: a longer squeeze at the front end only (R1e2: the corner edge E is up to 0.12 m aft of N)
        xa, xb = x[0], x[k]
        x[:k + 1] = x0 + (x[:k + 1] - xa) * (xb - x0) / (xb - xa)
    if x1 is not None and abs(x1 - x[-1]) > 1e-9:
        k = min(K, len(x) - 2)
        xa, xb = x[-1 - k], x[-1]
        x[-1 - k:] = xa + (x[-1 - k:] - xa) * (x1 - xa) / (xb - xa)
    for ia, xv in (pins or {}).items():          # a corner sample whose x is not the station x (the A-pillar foot): shift it there, the neighbours follow with a cos^2 taper
        j = ia - i0
        dx = xv - x[j]
        for t in range(-PIN_K, PIN_K + 1):
            if 0 <= j + t < len(x):
                x[j + t] += dx * math.cos(0.5 * math.pi * abs(t) / (PIN_K + 1)) ** 2
        assert np.all(np.diff(x) > 0), 'xlist pins: stations not monotonic'
    return x


PIN_K = 8


# ----------------------------------------------------------------------------- where the curves meet the raked front / tail faces
def hit(curve, which, x_guess):
    x = x_guess
    for _ in range(40):
        p = curve.at(x)
        x = float(D.face_x(p[1], p[2]) if which == 'face' else D.tail_x(p[1], p[2]))
    return x


class Ends:
    pass


def make_ends():
    e = Ends()
    e.L1 = hit(C['L'], 'tail', 2.38)
    e.l3_0, e.l3_1 = float(D.NOSE['l3_0'][0]), hit(C['l3'], 'tail', 2.36)             # R1e2: the corner edge E ends at the l3 / sill curves' points D.NOSE['l3_0'] / ['sill_0']
    e.sill_0, e.sill_1 = float(D.NOSE['sill_0'][0]), hit(C['sill'], 'tail', 1.79)
    e.rail1 = hit(C['rail'], 'tail', 2.38)
    e.ge1 = hit(C['gedge'], 'tail', 2.38)
    e.top1 = hit(C['top'], 'tail', 2.38)
    return e


# ----------------------------------------------------------------------------- the registry of shared boundary edges
HC = dict(hood=0.020, F=0.0225, shoulder=0.0145, wall=0.030, black=0.030, glass=0.022, door_glass=0.020, pillar=0.018, band=0.020, rear=0.020, ridge=0.020,
          deck=0.020, face=0.020, tail=0.016, E_up=0.020, E_low=0.020)


class Panel:
    def __init__(self, name, fn, mat, deps, hint=None):
        self.name, self.fn, self.mat, self.deps, self.hint = name, fn, mat, set(deps), hint


class Registry:
    def __init__(self):
        self.cache = {}
        self.cur = None
        self.used = {}
        self.E = make_ends()

    def edge(self, name):
        if self.cur is not None and name not in self.cur.deps:
            raise KeyError(f'panel {self.cur.name} uses edge {name} which it does not declare')
        self.used.setdefault(name, set()).add(self.cur.name if self.cur else '-')
        return self._edge(name)

    def _edge(self, name):
        if name not in self.cache:
            self.cache[name] = EDGES[name](self)
        return self.cache[name]


def _lin(a, b, n):
    t = np.linspace(0, 1, n + 1)[:, None]
    return np.asarray(a, float) + (np.asarray(b, float) - np.asarray(a, float)) * t


SNAP_TOL = 3e-3
SNAP_MAX = [0.0]


def snap(P, *pairs):
    """put the end / corner samples of an edge EXACTLY on the shared key points (the curves pass within a fraction of a millimetre; panels that meet there need identical vertices)"""
    for i, pt in pairs:
        d = float(np.linalg.norm(P[i] - np.asarray(pt, float)))
        assert d < SNAP_TOL, ('snap', i, d)
        SNAP_MAX[0] = max(SNAP_MAX[0], d)
        P[i] = pt
    return P


def facet_plane(R, tl):
    """the plane of the rear-corner facet: through the straight l3 line (aft of I_FE) and the tail face's side edge T3 -> TL (tl = the L end).  Returns (unit normal pointing outwards (+y), point T3)."""
    l3 = R._edge('l3')
    d = l3[-1] - l3[l3_line_index()]        # (the straight stretch: aft of E, or with QF_FC aft of the end of l3's bend; the same line)
    d = d / np.linalg.norm(d)
    n = np.cross(d, np.asarray(tl, float) - l3[-1])
    n = n / np.linalg.norm(n)
    return (n if n[1] > 0 else -n), l3[-1]


QF_LB_LEN = float(os.environ.get('QF_LB_LEN', '0.0'))       # m: L turns into the facet's straight segment over this length before S, in plan (q12 item 3; 0 = L keeps its plan corner at S: q12c, a plan
#   bend swelled L out by 9 mm before S and twisted the wall rows that fan into S: a soft dent at the top of the facet edge)
QF_LB_LENZ = float(os.environ.get('QF_LB_LENZ', '0.50'))    # m: ... and in height (side view: L crests before it falls to the tail; a longer bend keeps that crest soft)


def facet_L(R, P):
    """aft of the sample I_FS the character line L runs on a STRAIGHT line S' -> TL that lies in the facet's plane (S' = L[I_FS] moved into the plane: < 1 mm); samples keep their x"""
    P = P.copy()
    q17 = bool(D.QF_Q16 and D.QF_Q17)
    if q17:
        # q17 (the level tail edge): the corner TL is raised to the edge's height.  It moves (in y only, 2.4 mm outboard) into the facet's plane as it was with TL at L's level: raised on its own
        # it tilted the plane about l3, and S, 0.4 m ahead, fell 3 mm outside it (a plan jog in L at S)
        t0 = P[-1].copy()
        t0[2] = D.QF_Q16_L[1]
        n0, t3 = facet_plane(R, t0)
        P[-1, 1] -= float((P[-1] - t3) @ n0) / n0[1]
    n, t3 = facet_plane(R, P[-1])
    s = P[I_FS] - n * float((P[I_FS] - t3) @ n)
    x = P[I_FS:, 0].copy()
    t = (x - x[0]) / (x[-1] - x[0])
    P[I_FS:] = s[None, :] + (P[-1] - s)[None, :] * t[:, None]
    P[I_FS] = s
    if QF_LB_LEN > 0.0 or QF_LB_LENZ > 0.0:
        # q12 (review 2026-10-22, item 3; user: "同意" L bends before S): L turned 10 deg AT S (the facet apex), and the rear shoulder, sheared onto L, had to fold there (x 1.972, full width) or, smoothed,
        # bulge round S.  L now turns over the QF_LB_LEN before S: a quintic offset d(t), t = (x - xb) / (xS - xb), with d = d' = d'' = 0 at xb (G2 with the old L), d = 0 at S (S does not move),
        # d' = the slope change to the straight segment and d'' = - the old curvature at S (so L arrives at S straight: G2 with the segment).  S being fixed, L rises before it (max 6.2 mm, bent over QF_LB_LENZ); the plan corner stays (q12c: the height bend alone removes the shoulder's fold); the segment, S and the facet do not move.
        xS = float(s[0])
        x = P[:I_FS + 1, 0]
        m = (P[I_FS + 1] - P[I_FS]) / (P[I_FS + 1, 0] - P[I_FS, 0])             # slope (per unit x) of the straight segment
        q = P[I_FS - 2:I_FS + 1]
        xo = q[:, 0]
        d1 = (q[2] - q[1]) / (xo[2] - xo[1])
        d0 = (q[1] - q[0]) / (xo[1] - xo[0])
        dd = (d1 - d0) / (0.5 * (xo[2] - xo[0]))                                  # the old curvature vector (second derivative in x) at S
        A = np.array([[1.0, 1.0, 1.0], [3.0, 4.0, 5.0], [6.0, 12.0, 20.0]])
        for ax, ln in ((1, QF_LB_LEN), (2, 0.0 if q17 else QF_LB_LENZ)):          # plan (y) and height (z) are bent over their own lengths (q17: design2's L already bends into the segment, S rising)
            if ln <= 0.0:
                continue
            xb = xS - ln
            M, Cv = (m[ax] - d1[ax]) * ln, -dd[ax] * ln * ln
            a_, b_, e_ = np.linalg.solve(A, np.array([0.0, M, Cv]))                # d(t) = a t^3 + b t^4 + e t^5
            sel = x > xb
            tt = (x[sel] - xb) / ln
            P[:I_FS + 1, ax][sel] += a_ * tt ** 3 + b_ * tt ** 4 + e_ * tt ** 5
        P[I_FS] = s
    if QF_FC:
        # QF_FC: L turns into the facet's straight edge in plan over QF_FC[0] .. QF_FC[1] (G2 with the old L, tangent to the straight edge with no curvature); S moves in
        # with it (a few mm); z, the straight edge aft of QF_FC[1] and the tail corner do not change (the endplate's top edge, aft of the seam at 2.02, is within ~1 mm of its chord)
        m = (P[-1, 1] - P[I_FS, 1]) / (P[-1, 0] - P[I_FS, 0])
        y0_, x0_ = float(P[I_FS, 1]), float(P[I_FS, 0])
        P = plan_join(P, QF_FC[0], QF_FC[1], m, lambda xv: y0_ + m * (xv - x0_))
    return P


def e_L(R):
    P0 = snap(C['L'].at(xlist(0, I_LAST, D.N[0], R.E.L1)), (0, D.N))
    R.cache['L_old'] = P0                       # the character line before the facet straightened it: the rear shoulder's fold is solved from it (p_rear_shoulder)
    return facet_L(R, P0)


def e_U(R):
    return snap(C['U'].at(xlist(0, I_TIP, D.N[0])), (0, D.N), (I_A, D.A_OUT), (I_TIP, D.tip_final(C['L'], C['rail_roof'])))


def e_L5(R):
    return D.l5_points(I_A)                          # I_A + 1 samples, N -> W (the station count of the crest N -> A, so that the fender top pairs row by row); apillar: not uniform, see design2.l5_tau


def e_hood_cen(R):
    hc = np.array(D.HC, float)
    wc = np.array([D.W[0], 0.0, D.W[2]])
    t = D.l5_tau(I_A)
    P = hc + (wc - hc) * t[:, None]                          # the centre line sampled at L5's fractions (the hood's columns; uniform for the first TRI_K) ...
    P[:, 2] += D.hood_sag(t)                                 # ... bowed up like L5 (2026-10-24, design2.QF_HOOD_SAG)
    return P


M_HOOD = int(round(0.67 / HC['hood']))
_NC = D.NOSE['curves']
assert len(_NC['bar_top']) == M_HOOD + 1, 'the hood front edge must have M_HOOD + 1 samples (the cowl line pairs with it)'


def e_LE(R):
    """hood front edge (R1e2): the bowed arc, centre -> N, on the hood plane (35 samples) = the light bar's top edge"""
    return _NC['bar_top'].copy()


def e_LE_str(R):
    return _NC['bar_top'].copy()                    # the front face's top edge: the same arc


def e_LE_ch(R):
    return _NC['L6_top'].copy()                     # the chamfer facet's top edge: no length (the facet starts at N): 9 copies of N


def e_F_bot(R):
    """bottom edge of the front face: the arc swept along the generator down to the sill's level (35 samples, like the top edge)"""
    return _NC['F_bot'].copy()


def e_F_cen(R):
    return _NC['F_cen'].copy()


def e_face_edge_up(R):
    assert len(_NC['face_edge_up']) == len(R._edge('E_up')), 'the crease and the corner edge E_up must have the same sample count'
    return _NC['face_edge_up'].copy()


def e_face_edge_low(R):
    assert len(_NC['face_edge_low']) == len(R._edge('E_low')), 'the crease and the corner edge E_low must have the same sample count'
    return _NC['face_edge_low'].copy()


def e_crease(R):
    """crease front face | chamfer facets, bottom -> top (C1_bot, C1_l3, C1_top): 20 samples"""
    return np.vstack([_NC['face_edge_low'], _NC['face_edge_up'][1:]])


def e_cut_up(R):
    """horizontal edge at the l3 level between the upper and the lower chamfer facet: C1_l3 -> l3_0 (8 intervals; same as the facet's top edge)"""
    nz = D.NOSE
    return _lin(nz['C1_l3'], nz['l3_0'], len(_NC['L6_top']) - 1)


def e_cut_low(R):
    nz = D.NOSE
    return _lin(nz['C1_bot'], nz['sill_0'], len(_NC['L6_top']) - 1)


def e_cowl(R):
    return np.array([[D.W[0], y, D.W[2]] for y in np.linspace(0, D.W[1], M_HOOD + 1)])       # Wc -> W


def e_cowl_diag(R):
    return snap(C['cowl_diag'].at(xlist(I_W, I_A, pins={I_A: D.A_IN[0]})), (0, D.W), (-1, D.A_IN))


def e_F_end(R):
    d = R._edge('cowl_diag')
    a_in, a_out = np.array(D.A_IN), np.array(D.A_OUT)
    return np.vstack([d, 0.5 * (a_in + a_out)[None], a_out[None]])


def e_foot(R):
    return np.array([D.A_IN, 0.5 * (np.array(D.A_IN) + np.array(D.A_OUT)), D.A_OUT])


def quintic_join(x, x0, y0, d0, c0, x1, y1, d1, c1):
    """y(x) on [x0, x1] with value, slope and curvature (d / dx, d2 / dx2) given at both ends"""
    h = x1 - x0
    t = (np.asarray(x, float) - x0) / h
    a0, a1, a2 = y0, d0 * h, 0.5 * c0 * h * h
    b0, b1, b2 = y1, d1 * h, 0.5 * c1 * h * h
    M = np.array([[1.0, 1.0, 1.0], [3.0, 4.0, 5.0], [6.0, 12.0, 20.0]])
    r = np.array([b0 - a0 - a1 - a2, b1 - a1 - 2 * a2, 2 * b2 - 2 * a2])
    c3, c4, c5 = np.linalg.solve(M, r)
    return a0 + a1 * t + a2 * t ** 2 + c3 * t ** 3 + c4 * t ** 4 + c5 * t ** 5


def l3_line_index():
    """the first l3 sample on its straight line aft of E (QF_FC: where the bend ends; else E)"""
    return int(np.argmin(abs(XS - QF_FC[3]))) if QF_FC else I_FE


def plan_join(P, xa, xb, m, y_at):
    """P (samples by x) with y over [xa, xb] replaced by a G2 quintic from the old curve (value, slope, curvature at the first sample >= xa) to the straight line y_at(x) of slope m (no curvature)"""
    P = P.copy()
    x = P[:, 0]
    ia = int(np.searchsorted(x, xa))
    ib = int(np.searchsorted(x, xb, side='right')) - 1
    d0 = (P[ia + 1, 1] - P[ia - 1, 1]) / (x[ia + 1] - x[ia - 1])
    c0 = 2.0 * ((P[ia + 1, 1] - P[ia, 1]) / (x[ia + 1] - x[ia]) - (P[ia, 1] - P[ia - 1, 1]) / (x[ia] - x[ia - 1])) / (x[ia + 1] - x[ia - 1])
    P[ia:ib + 1, 1] = quintic_join(x[ia:ib + 1], x[ia], P[ia, 1], d0, c0, x[ib], y_at(x[ib]), m, 0.0)
    return P


def l3_kink(P):
    """rearcrease round 2 (coordinator ruling B): the paint | black boundary l3 gets a KINK IN PLAN at the corner of the facet edge E = l3[I_FE]: forward of E it runs on a gentle plan curve (L3_FRONT_DEG at E, Hermite from the
    station I_L3K0 on, its value and slope kept there), aft of E it stays the straight line to the tail corner (14.85 degrees in plan).  Only y moves (x, z do not: p018, a pure side view, sees no change; the line stays ONE
    straight line in the side view).  The plan kink is what gives the facet edge its dihedral (the facet plane contains the aft stretch, the wall's tangent plane at E the forward stretch)."""
    P = P.copy()
    i0, i1 = I_L3K0, I_FE
    x = P[:, 0]
    h = x[i1] - x[i0]
    t = (x[i0:i1 + 1] - x[i0]) / h
    y0, y1 = P[i0, 1], P[i1, 1]
    m0 = (P[i0 + 1, 1] - P[i0 - 1, 1]) / (x[i0 + 1] - x[i0 - 1])
    m1 = -math.tan(math.radians(L3_FRONT_DEG))
    line = P[i1:].copy()                        # (aft of E: the straight line, kept)
    P[i0:i1 + 1, 1] = ((2 * t ** 3 - 3 * t ** 2 + 1) * y0 + (t ** 3 - 2 * t ** 2 + t) * h * m0 + (-2 * t ** 3 + 3 * t ** 2) * y1 + (t ** 3 - t ** 2) * h * m1)
    if QF_FC:
        # QF_FC: no kink at E: over QF_FC[2] .. QF_FC[3] a G2 quintic from the curve above onto the straight line aft of E (tangent, no curvature); E moves in with it (a few mm)
        ml = (line[-1, 1] - line[0, 1]) / (line[-1, 0] - line[0, 0])
        P = plan_join(P, QF_FC[2], QF_FC[3], ml, lambda xv: line[0, 1] + ml * (xv - line[0, 0]))
    return P


def e_l3(R):
    return l3_kink(C['l3'].at(xlist(0, I_LAST, R.E.l3_0, R.E.l3_1, K0=D.NOSE_K)))


def y_side(z, ys, zs):
    return ys[0] + (ys[1] - ys[0]) * (z - zs[0]) / (zs[1] - zs[0])


def side_edge_fn(R):
    """the tail face's side edge from the sill end up to the l3 end: z -> (x, y, z), x on the tail face"""
    s1 = C['sill'].at(R.E.sill_1)
    l1 = C['l3'].at(R.E.l3_1)
    zs = np.linspace(s1[2], l1[2], 400)
    ys = s1[1] + (l1[1] - s1[1]) * (zs - s1[2]) / (l1[2] - s1[2])
    xs = D.tail_x(ys, zs)
    return xs, ys, zs


def e_E_side(R):
    """samples of the side edge of the tail face (sill end -> l3 end), aligned with the stations I_SILL .. I_LAST"""
    xs, ys, zs = side_edge_fn(R)
    xl = xlist(I_SILL, I_LAST, R.E.sill_1, R.E.l3_1)
    zq = np.interp(xl, xs, zs)
    yq = np.interp(zq, zs, ys)
    P = np.stack([xl, yq, zq], 1)
    P[0] = C['sill'].at(R.E.sill_1)
    P[-1] = C['l3'].at(R.E.l3_1)
    return P


def e_sill(R):
    return C['sill'].at(xlist(0, I_SILL, R.E.sill_0, R.E.sill_1, K0=D.NOSE_K))


def e_low(R):
    s = R._edge('sill')
    e = R._edge('E_side')
    return np.vstack([s, e[1:]])


def e_E_low(R):
    if D.QF_CF_ON:
        return _NC['face_edge_low'].copy()
    a = R._edge('low')[0]
    b = R._edge('l3')[0]
    return _lin(a, b, min(D.E_CAP_LOW, max(1, int(round(np.linalg.norm(b - a) / HC['E_low'])))))


def e_E_up(R):
    if D.QF_CF_ON:                                  # c10b: the corner edge is the front face's end generator (the wall's first row)
        return _NC['face_edge_up'].copy()
    a = R._edge('l3')[0]
    b = R._edge('L')[0]
    return _lin(a, b, min(D.E_CAP_UP, max(1, int(round(np.linalg.norm(b - a) / HC['E_up'])))))


def e_rail(R):
    return snap(C['rail'].at(xlist(I_W, I_LAST, None, R.E.rail1, pins={I_A: D.A_IN[0]})), (0, D.W), (I_A - I_W, D.A_IN))


def e_rail_roof(R):
    return C['rail_roof'].at(xlist(I_T, I_LAST, None, R.E.rail1))


def e_gedge(R):
    P = C['gedge'].at(xlist(I_W, I_LAST, None, R.E.ge1, pins={I_A: D.A_IN[0]}))
    rail = R._edge('rail')
    P = snap(P, (0, D.W), (I_A - I_W, D.A_IN))
    if np.linalg.norm(P[-1] - rail[-1]) < 2e-3:
        P[-1] = rail[-1]
    return P


def e_top(R):
    P = C['top'].at(xlist(I_W, I_LAST, None, R.E.top1))
    ge = R._edge('gedge')
    P = snap(P, (0, [D.W[0], 0.0, D.W[2]]), (I_SEAM - I_W, [ge[I_SEAM - I_W][0], 0.0, ge[I_SEAM - I_W][2]]))
    return P


def e_wl(R):
    return snap(C['wl'].at(xlist(I_A, I_TIP)), (0, D.A_OUT), (-1, D.tip_final(C['L'], C['rail_roof'])))


def glass_row(ge, top, m):
    """cross-section of the glass at one station: from the glass edge (y_e, z_e) to the centre (0, z_t): a parabolic crown"""
    s = np.linspace(0, 1, m + 1)[:, None]
    y = ge[1] * (1 - s)
    z = top[2] - (top[2] - ge[2]) * (1 - s) ** 2
    x = ge[0] + (top[0] - ge[0]) * s
    return np.hstack([x, y, z])


def e_seam_row(R):
    ge = R._edge('gedge')[I_SEAM - I_W]
    tp = R._edge('top')[I_SEAM - I_W]
    m = max(1, int(round(ge[1] / HC['glass'])))
    r = glass_row(ge, tp, m)
    r[0], r[-1] = ge, tp
    return r


def on_tail(a, b, n):
    r = _lin(a, b, n)
    r[1:-1, 0] = D.tail_x(r[1:-1, 1], r[1:-1, 2])
    return r


def e_tail_a(R):
    a, b = R._edge('L')[-1], R._edge('rail')[-1]
    n = max(1, int(round(np.linalg.norm(b - a) / HC['tail'])))
    if D.QF_TAIL:
        # (tail rebuild: the top edge from the corner to the ear tip is the end section itself, level from E outwards and rolled down to the corner, not the chord)
        sol = D.q16_section(0.5 * (a[0] + b[0]), a[1:], b[1:], a[0], b[0])
        r = D.fold_points(sol, np.linspace(0.0, sol['S'], n + 1), a[0], b[0])
        r[0], r[-1] = a, b
        r[1:-1, 0] = D.tail_x(r[1:-1, 1], r[1:-1, 2])
        return r
    return on_tail(a, b, n)


def e_tail_b(R):
    a, b = R._edge('rail')[-1], R._edge('top')[-1]
    return on_tail(a, b, max(1, int(round(a[1] / HC['tail']))))


def e_tail_side_up(R):
    a, b = R._edge('l3')[-1], R._edge('L')[-1]
    return on_tail(a, b, max(1, int(round(np.linalg.norm(b - a) / HC['tail']))))


def e_facet_edge(R):
    """the facet's front edge: the straight line E (l3 sample I_FE) -> S (L sample I_FS), bottom -> top like the wall's rows; shared by the wall (its last row) and the facet (its first row)"""
    a, b = R._edge('l3')[I_FE], R._edge('L')[I_FS]
    return _lin(a, b, max(1, int(round(np.linalg.norm(b - a) / HC['wall']))))


def e_tail_split(R):
    """the l3 height across the tail face (black below, paint above): centre -> l3 end, nt + 1 samples (the top edge of the face has the same count)"""
    nt = len(R._edge('tail_a')) + len(R._edge('tail_b')) - 1
    a = np.array([0.0, 0.0, R._edge('l3')[-1][2]])
    b = R._edge('l3')[-1]
    r = _lin(a, b, nt - 1)
    r[:, 0] = D.tail_x(r[:, 1], r[:, 2])
    return r


def e_tail_bottom(R):
    nt = len(R._edge('tail_a')) + len(R._edge('tail_b')) - 1
    s = R._edge('sill')[-1]
    r = _lin(np.array([0.0, 0.0, s[2]]), s, nt - 1)
    r[:, 0] = D.tail_x(r[:, 1], r[:, 2])
    return r


EDGES = {
    'L': e_L, 'U': e_U, 'L5': e_L5, 'hood_cen': e_hood_cen, 'LE': e_LE, 'LE_str': e_LE_str, 'LE_ch': e_LE_ch, 'F_bot': e_F_bot, 'F_cen': e_F_cen, 'face_edge_up': e_face_edge_up,
    'face_edge_low': e_face_edge_low, 'crease': e_crease, 'cut_up': e_cut_up, 'cut_low': e_cut_low, 'cowl': e_cowl, 'cowl_diag': e_cowl_diag, 'F_end': e_F_end, 'foot': e_foot,
    'l3': e_l3, 'sill': e_sill, 'E_side': e_E_side, 'low': e_low, 'E_low': e_E_low, 'E_up': e_E_up,
    'rail': e_rail, 'rail_roof': e_rail_roof, 'gedge': e_gedge, 'top': e_top, 'wl': e_wl,
    'seam_row': e_seam_row, 'tail_a': e_tail_a, 'tail_b': e_tail_b, 'tail_side_up': e_tail_side_up, 'tail_split': e_tail_split, 'tail_bottom': e_tail_bottom, 'facet_edge': e_facet_edge,
}


# ----------------------------------------------------------------------------- panel meshes
class PM:
    def __init__(self, name, mat):
        self.name, self.mat = name, mat
        self.verts = []
        self.faces = []

    def add_row(self, pts):
        ids = list(range(len(self.verts), len(self.verts) + len(pts)))
        self.verts.extend(list(map(tuple, pts)))
        return ids


def chord_s(row):
    if len(row) < 2:
        return np.zeros(len(row))
    d = np.r_[0, np.cumsum(np.linalg.norm(np.diff(row, axis=0), axis=1))]
    return d / d[-1] if d[-1] > 0 else np.linspace(0, 1, len(row))


def zipper(ra, rb, sa, sb, faces):
    i = j = 0
    na, nb = len(ra), len(rb)
    tol = 0.25 * min(1.0 / max(na - 1, 1), 1.0 / max(nb - 1, 1))
    while i < na - 1 or j < nb - 1:
        if i == na - 1:
            faces.append((ra[i], rb[j + 1], rb[j])); j += 1
        elif j == nb - 1:
            faces.append((ra[i], ra[i + 1], rb[j])); i += 1
        else:
            da, db = sa[i + 1], sb[j + 1]
            if abs(da - db) < tol:
                faces.append((ra[i], ra[i + 1], rb[j + 1], rb[j])); i += 1; j += 1
            elif da < db:
                faces.append((ra[i], ra[i + 1], rb[j])); i += 1
            else:
                faces.append((ra[i], rb[j + 1], rb[j])); j += 1


def limit_m(m, pin0=None, pinN=None):
    m = np.array(m, int)
    if pin0 is not None:
        m[0] = pin0
    if pinN is not None:
        m[-1] = pinN
    for _ in range(3):
        for i in range(1, len(m)):
            m[i] = max(m[i - 1] - 1, min(m[i - 1] + 1, m[i]))
        for i in range(len(m) - 2, -1, -1):
            m[i] = max(m[i + 1] - 1, min(m[i + 1] + 1, m[i]))
    if pin0 is not None:
        m[0] = pin0
    if pinN is not None:
        m[-1] = pinN
    return m


CONST_M = os.environ.get('CONST_M', '1') == '1'


def strip(name, mat, A, B, hc, prof=None, pin0=None, pinN=None, row_fn=None, minm=1, const_m=None, quads=False):
    """ruled strip between the index-aligned edges A and B.  Row i connects A[i] and B[i] (m_i divisions: the strip is a wedge where the edges converge, a single point where they
    meet).  prof(i, s, P) -> offsets (bulge); row_fn(i, A, B, m) -> custom row (glass crown).  pin0 / pinN: the first / last row is given (shared with another panel)."""
    A, B = np.asarray(A, float), np.asarray(B, float)
    assert len(A) == len(B), (name, len(A), len(B))
    n = len(A)
    Ln = np.linalg.norm(B - A, axis=1)
    m = np.where(Ln < 1e-7, 0, np.maximum(minm, np.round(Ln / hc).astype(int)))
    m = limit_m(m, None if pin0 is None else len(pin0) - 1, None if pinN is None else len(pinN) - 1)
    if CONST_M if const_m is None else const_m:
        # the same number of divisions in every row (apex rows of a wedge stay a single point): a regular grid, no zipper triangles in the middle of the panel
        M = int(max(m.max(), 1 if pin0 is None else len(pin0) - 1, 1 if pinN is None else len(pinN) - 1))
        mm = np.where(Ln < 1e-7, 0, M)
        if pin0 is not None:
            mm[0] = len(pin0) - 1
        if pinN is not None:
            mm[-1] = len(pinN) - 1
        m = mm
    pm = PM(name, mat)
    rows, ids, ss = [], [], []
    for i in range(n):
        if i == 0 and pin0 is not None:
            r = np.asarray(pin0, float)
        elif i == n - 1 and pinN is not None:
            r = np.asarray(pinN, float)
        elif m[i] == 0:
            r = A[i][None, :]
        elif row_fn is not None:
            r = row_fn(i, A[i], B[i], int(m[i]))
        else:
            s = np.linspace(0, 1, m[i] + 1)[:, None]
            r = A[i] + (B[i] - A[i]) * s
            if prof is not None:
                r = r + prof(i, s[:, 0], r)
        if m[i] > 0 and len(r) > 1:
            r = r.copy(); r[0] = A[i]; r[-1] = B[i]
        rows.append(r)
        ids.append(pm.add_row(r))
        ss.append(chord_s(r))
    for i in range(n - 1):
        if quads and len(ids[i]) == len(ids[i + 1]):
            # rows with the same number of nodes (the soft arc's rows, whose node fractions drift from row to row): always a quad grid, never zipper triangles
            pm.faces.extend((ids[i][j], ids[i][j + 1], ids[i + 1][j + 1], ids[i + 1][j]) for j in range(len(ids[i]) - 1))
        else:
            zipper(ids[i], ids[i + 1], ss[i], ss[i + 1], pm.faces)
    pm.rows = rows
    return pm


def coons_grid(bottom, top, left, right, u=None):
    """transfinite (Coons) interpolation of four index-aligned boundary arrays: bottom[i] / top[i] (i = 0..n) along u, left[j] / right[j] (j = 0..m) along v.
    Returns P[j][i]; the boundary rows are the given arrays verbatim.
    u (apillar): the u value of each column, default uniform.  bottom / top must be the SAME straight or curved edges sampled at these u (a hood whose L5 is not uniformly sampled
    keeps the surface of the uniformly sampled patch: only the columns move)."""
    bottom, top, left, right = (np.asarray(a, float) for a in (bottom, top, left, right))
    n, m = len(bottom) - 1, len(left) - 1
    assert len(top) == n + 1 and len(right) == m + 1
    u = (np.linspace(0, 1, n + 1) if u is None else np.asarray(u, float))[None, :, None]
    v = np.linspace(0, 1, m + 1)[:, None, None]
    c00, c10, c01, c11 = bottom[0], bottom[n], top[0], top[n]
    P = ((1 - v) * bottom[None] + v * top[None] + (1 - u) * left[:, None] + u * right[:, None]
         - ((1 - u) * (1 - v) * c00 + u * (1 - v) * c10 + (1 - u) * v * c01 + u * v * c11))
    P[0], P[-1], P[:, 0], P[:, -1] = bottom, top, left, right
    return P


def grid_faces(pm, P):
    m1, n1 = P.shape[0], P.shape[1]
    ids = [pm.add_row(P[j]) for j in range(m1)]
    for j in range(m1 - 1):
        for i in range(n1 - 1):
            pm.faces.append((ids[j][i], ids[j][i + 1], ids[j + 1][i + 1], ids[j + 1][i]))


# ----------------------------------------------------------------------------- the panels
def p_hood(R):
    LE, L5, COW, CEN = (R.edge(k) for k in ('LE', 'L5', 'cowl', 'hood_cen'))
    pm = PM('hood', PAINT)
    # bottom = centre line (v = 0), top = L5 (v = 1), left = leading edge (u = 0: centre -> N), right = cowl line (u = 1: centre -> W)
    P = coons_grid(CEN, L5, LE, COW, u=D.l5_tau(I_A))          # apillar: the columns sit at L5's (not uniform) fractions, the patch is the uniform one (the L5 sampling is for the fender top's rulings only)
    grid_faces(pm, P)
    return pm


def planar_grid(pm, bottom, top, left, right, plane=None):
    """Coons grid of four boundary polylines that all lie in one plane -> planar quads (exactly, up to rounding)"""
    P = coons_grid(bottom, top, left, right)
    grid_faces(pm, P)
    return P


def p_front_face(R):
    """R1e: the flat (planar, raked) front face between the two corner creases: straight top edge (= hood front edge = light bar top), straight bottom edge.  A placeholder: the black
    face, the light bar and the splitter / intake are hung on it by the front-end agent (named curves: design2.NOSE['curves'])."""
    top, bot, cen, crease = R.edge('LE_str'), R.edge('F_bot'), R.edge('F_cen'), R.edge('crease')
    pm = PM('front_face', TRIM)
    Y = coons_grid(bot[:, 1:], top[:, 1:], cen[:, 1:], crease[:, 1:])          # (y, z)
    X = D.NOSE['Fxy'](Y[..., 0], Y[..., 1])                                    # R1e2: the sheared cylinder x = xe(y) + rake (ze(y) - z); all four boundaries lie on it
    P = np.concatenate([X[..., None], Y], -1)
    P[0], P[-1], P[:, 0], P[:, -1] = bot, top, cen, crease
    grid_faces(pm, P)
    return pm


def p_nose_corner_up(R):
    """R1e: the upper chamfer facet (L6 at the nose): planar, between the front face crease and the corner edge E_up (first row of the locked wall panel); its plane is the wall's tangent plane there"""
    pm = PM('nose_corner_up', PAINT)
    if not D.QF_NC_ON:
        planar_grid(pm, R.edge('cut_up'), R.edge('LE_ch'), R.edge('face_edge_up'), R.edge('E_up'))
        return pm
    # c10 (user: 'the lower face is ONE trapezoid, the small triangle T goes'): the chamfer stays a triangle between the front face crease and the corner edge E_up (its corners are the front face's, shared with front.py), but it is no longer
    # a flat facet 20 degrees off the wall: along every horizontal row from E_up to the crease it is lifted by the cubic d(w) = c w (1 - w / W)^2 off the plane P (c: the slope of the wall's tangent plane at E_up over P): G1 with the wall
    # along E_up (no crease, no fillet: the angle across E_up is < 1 degree), tangent to P at the front crease (which stays the crisp corner edge of the front face).  The rows next to the l3 level (the edge shared with the lower facet) are
    # faded back to P (the shared edge must not move).
    P = coons_grid(R.edge('cut_up'), R.edge('LE_ch'), R.edge('face_edge_up'), R.edge('E_up'))
    Eu, Fu = R.edge('E_up'), R.edge('face_edge_up')
    l3, Lm = R.edge('l3'), R.edge('Lm')
    n = len(Eu) - 1
    nP = np.cross(P[0, -1] - P[0, 0], P[-1, 0] - P[0, 0])
    nP = nP / np.linalg.norm(nP)
    if nP[1] < 0:
        nP = -nP
    for j in range(1, n):                                       # the rows j = 0 (l3 level) and j = n (the apex N) stay
        E, F = Eu[j], Fu[j]
        rv = F - E
        Wr = np.linalg.norm(rv)
        if Wr < 1e-9:
            continue
        rh = rv / Wr
        c_w = (l3[1] + (Lm[1] - l3[1]) * (j / n)) - E             # the wall's second row, same height fraction
        tE = Eu[min(j + 1, n)] - Eu[max(j - 1, 0)]
        nW = np.cross(tE, c_w)
        nW = nW / np.linalg.norm(nW)
        if nW[1] < 0:
            nW = -nW
        c = -float(nW @ rh) / float(nW @ nP)
        env = float(D.sstep(0.0, D.QF_NC_V, j / n))
        for i in range(P.shape[1]):
            w = np.linalg.norm(P[j, i] - E)
            P[j, i] = P[j, i] + env * c * w * (1.0 - w / Wr) ** 2 * nP
    grid_faces(pm, P)
    return pm


def p_nose_corner_low(R):
    """R1e: the lower chamfer facet (black, below the l3 level): planar, between the crease and E_low"""
    pm = PM('nose_corner_low', TRIM)
    planar_grid(pm, R.edge('cut_low'), R.edge('cut_up'), R.edge('face_edge_low'), R.edge('E_low'))
    return pm


LENS_AMP = float(os.environ.get('LENS_AMP', '0.006'))        # max bulge of the fender side surface (the lens) over the straight ruling (m)
LENS_X0 = float(os.environ.get('LENS_X0', '-0.9'))
LENS_X1 = float(os.environ.get('LENS_X1', '0.3'))
BULGE_W = float(os.environ.get('BULGE_W', '0.22'))


def bulge_prof(amp_fn):
    def prof(i, s, P):
        r = P[-1] - P[0]
        nrm = np.array([0.0, r[2], -r[1]])
        nl = np.linalg.norm(nrm)
        if nl < 1e-9:
            return np.zeros_like(P)
        nrm /= nl
        x = P[0, 0]
        return (amp_fn(x) * D.sstep(0.0, BULGE_W, nl) * 4 * s * (1 - s))[:, None] * nrm[None, :]      # the bulge grows with the width of the strip (a narrow strip near the nose stays nearly flat)
    return prof


def lens_amp(x):
    return LENS_AMP * (1 - D.sstep(LENS_X0, LENS_X1, x)) * D.sstep(-1.75, -1.30, x)          # fender3: no bulge on the front fender (the middle face is a cylinder); the rear shoulder keeps it


# ----------------------------------------------------------------------------- q4f2: the fender volume over the front wheel (plateau over the wheel, long monotone fades)
# Between QF_F_X[0] and QF_F_X[3] the OUTER BOUNDARY of the section (wall top + shoulder, as a function y(z) at every station x) is blended with a convex target section T_x:
#   y_new(z) = (1 - w(x)) y_old(z) + w(x) y_T(z)      for z >= the start of T on the wall line (QF_F_D below L), U unchanged (y_T(z_U) = y_U), nothing below the start moves.
# y_old(z) and y_T(z) are both concave in z (a convex body section), a convex combination of concave functions is concave: every section stays convex for every w, there is no tilt hump and no S.
# T_x = cubic Bezier from P0 (on the wall line, QF_F_D below L, tangent along the wall: G1 with the wall) to U (arrival tangent = the chord's direction + QF_F_DA degrees flatter: the crest crease U is softened by that much
# at the plateau and returns monotonically); the tangent lengths are QF_F_K0 / QF_F_K1 times the chord length P0 -> U.  w(x) = the plateau: 1 from QF_F_X[1] to QF_F_X[2] (hub -1.487), C2 (quintic smoothstep)
# monotone fades to 0 at QF_F_X[0] (nose side) and QF_F_X[3] (aft, -0.45): one rise and one fall, no second peak.  Only the vertices of the panels 'wall' and 'shoulder' move (in y only, z fixed): U, fender_top, door_glass,
# glass, rail_band and everything aft of x -0.40 are not touched.
# Why the nose-side fade starts at -1.90 and not earlier: in the p003 v stripe map the reflection vector hits the zenith (the pole of the azimuth stripes, a star) where the section normal is (-0.38, -0.44, 0.81), 54 deg above
# the horizon, at x ~ -1.83: whenever the fill is already substantial there the stripes converge to a point.  A rise starting at -2.30 gives a minimum polar angle of the reflection vector of 1.7 deg (star), -1.90 gives 18-19 deg.
# Defaults = the accepted values (K0 0.55, K1 0.7, DA 25: hub arch-top |y| 1.056, every section convex, 5 stripe boundaries per 5 cm at most).  QF_F_ON=0 gives the old sections.
QF_F_ON = os.environ.get('QF_F_ON', '0') == '1'      # q5: the rounded fill is OFF (the user's reading: the ridge stays sharp); the hump QF_H_* below replaces it
if D.QF_C11_ON:         # c11: the optional round fill (design2.QF_C11_FA > 0; 0 = no-op) acts through the machinery below
    QF_F_ON = True
QF_F_X = tuple(float(v) for v in os.environ.get('QF_F_X', '-1.90,-1.45,-1.30,-0.45').split(','))
QF_F_D = float(os.environ.get('QF_F_D', '0.03'))
QF_F_K0 = float(os.environ.get('QF_F_K0', '0.55'))
QF_F_K1 = float(os.environ.get('QF_F_K1', '0.7'))
QF_F_DA = float(os.environ.get('QF_F_DA', '25'))


def qf_f_w(x):
    a, b, c, d = D.QF_C11_FX if D.QF_C11_ON else QF_F_X
    return (D.QF_C11_FA if D.QF_C11_ON else 1.0) * float((D.sstep(a, b, x) ** (D.QF_C11_FP if D.QF_C11_ON else 1.0)) * (1.0 - D.sstep(c, d, x)))


_QF_F_CACHE = {}


def _hermite5(P0, T0, A0, P1, T1, A1, n=400):
    u = np.linspace(0.0, 1.0, n)[:, None]
    h0 = 1 - 10 * u ** 3 + 15 * u ** 4 - 6 * u ** 5
    h1 = u - 6 * u ** 3 + 8 * u ** 4 - 3 * u ** 5
    h2 = 0.5 * u ** 2 - 1.5 * u ** 3 + 1.5 * u ** 4 - 0.5 * u ** 5
    h3 = 1.0 - h0
    h4 = -4 * u ** 3 + 7 * u ** 4 - 3 * u ** 5
    h5 = 0.5 * u ** 3 - u ** 4 + 0.5 * u ** 5
    return h0 * P0 + h1 * T0 + h2 * A0 + h3 * P1 + h4 * T1 + h5 * A1


_QF_TOP_TILT = [(-2.30, 7.2), (-2.10, 6.8), (-1.95, 6.6), (-1.90, 5.7), (-1.85, 4.3), (-1.80, 3.0), (-1.70, 1.5), (-1.65, 0.8), (-1.60, 0.7), (-1.55, 0.7), (-1.50, 2.0), (-1.45, 3.5)]


def qf_top_tilt(x):
    """angle (deg, outward-up +) of the top face (fender_top, locked) at the crest U: its tangent over the last 3 cm before U, read from exact plane sections of the c10b mesh (the face is a ruled, slightly convex surface:
    7 deg at the nose end, 0.7 deg at x -1.6, 3.5 deg at the pillar foot); held at the pillar foot's value aft of it"""
    return float(np.interp(float(x), [a for a, b in _QF_TOP_TILT], [b for a, b in _QF_TOP_TILT]))


def qf_soft_target(x, L, K, U):
    """c11b: (zs, ys) of the target section above the wall top Lm: a quintic Hermite arc, tangent to the wall at Lm with ZERO curvature there (G2), arriving at U with the dihedral QF_C11_UD to the top face, the curvature at U
    QF_C11_SC1 times that of the circle through the same chord and turn.  The wall top Lm = L raised by the hump (qf_h).  The arc lies outside the old straight face (convex target; the weights blend y(z) linearly, so every
    blended section stays convex)."""
    Lm = L + np.array([0.0, qf_h(float(x))])
    uw = (Lm - K) / np.linalg.norm(Lm - K)                         # the wall's direction at Lm (up, along the wall)
    P0 = Lm - D.QF_C11_SD * uw                                      # where the arc leaves the wall line
    alpha = max(1.0, D.QF_C11_UD - qf_top_tilt(x))                  # the shoulder just below U: degrees below the horizontal, outward
    v = np.array([-math.cos(math.radians(alpha)), math.sin(math.radians(alpha))])      # arrival direction (inboard, up)
    ch = U - P0
    lc = float(np.linalg.norm(ch))
    psi = math.acos(float(np.clip(uw @ v, -1, 1)))                  # the turn from the wall to the arrival direction
    kc = 2.0 * math.sin(0.5 * psi) / lc if psi > 1e-3 else 0.0       # circle through the chord with that turn
    s0 = D.QF_C11_SK * lc
    n1 = np.array([-v[1], v[0]])
    T0, T1 = uw * s0, v * s0
    A0 = np.zeros(2)
    A1 = D.QF_C11_SC1 * kc * s0 * s0 * n1
    c = _hermite5(P0, T0, A0, U, T1, A1)
    zs, ys = c[:, 1], c[:, 0]
    if np.any(np.diff(zs) <= 0):
        return None
    return (zs, ys)


def qf_f_target(x):
    """(zs, ys) of the target section at station x (z increasing), or None"""
    key = round(float(x), 6)
    if key in _QF_F_CACHE:
        return _QF_F_CACHE[key]
    L, K, U = (np.asarray(D.CURVES[n].at(x), float)[1:] for n in ('L', 'l3', 'U'))
    if D.QF_C11_ON and D.QF_C11_SOFT:                # c11b: the swept convex arc from the wall top Lm (G2 with the wall) to U, dihedral QF_C11_UD with the top face at U
        res = qf_soft_target(x, L, K, U)
        _QF_F_CACHE[key] = res
        return res
    if D.QF_C11_ON:                                  # c11: one round section from the foot K (G1 with the wall, leaned outward by QF_C11_LAM so that the widest point lies at lamp height) up to U
        uw = (L - K) / np.linalg.norm(L - K)
        if D.QF_C11_ZF > K[1] + 1e-6:                  # the target starts on the wall line at this height (not at the foot): the widest point does not grow below it
            K = K + uw * (min(D.QF_C11_ZF, float(L[1])) - K[1]) / max(uw[1], 1e-6)
        a0 = math.atan2(uw[1], uw[0]) - math.radians(D.QF_C11_LAM)
        e0 = np.array([math.cos(a0), math.sin(a0)])
        lc = float(np.linalg.norm(U - K))
        cl = U - L
        ang = math.atan2(cl[1], cl[0]) + math.radians(D.QF_C11_DA)
        v = np.array([math.cos(ang), math.sin(ang)])
        wk = float(D.sstep(D.QF_C11_KX[0], D.QF_C11_KX[1], x))         # 2026-10-24: near-circular handles ahead of the wheel, the c11 ones over it (design2 QF_C11_KF)
        P1 = K + (D.QF_C11_KF + (D.QF_C11_K0 - D.QF_C11_KF) * wk) * lc * e0
        P2 = U - (D.QF_C11_KF + (D.QF_C11_K1 - D.QF_C11_KF) * wk) * lc * v
        t = np.linspace(0.0, 1.0, 400)[:, None]
        c = (1 - t) ** 3 * K + 3 * (1 - t) ** 2 * t * P1 + 3 * (1 - t) * t ** 2 * P2 + t ** 3 * U
        zs, ys = c[:, 1], c[:, 0]
        res = None if np.any(np.diff(zs) <= 0) else (zs, ys)
        _QF_F_CACHE[key] = res
        return res
    uw = (L - K) / np.linalg.norm(L - K)
    P0 = L - QF_F_D * uw
    ch = U - P0
    lc = float(np.linalg.norm(ch))
    cl = U - L                                       # the old chamfer's direction (the soft turn aside)
    ang = math.atan2(cl[1], cl[0]) + math.radians(QF_F_DA)
    v = np.array([math.cos(ang), math.sin(ang)])
    P1 = P0 + QF_F_K0 * lc * uw
    P2 = U - QF_F_K1 * lc * v
    t = np.linspace(0.0, 1.0, 400)[:, None]
    c = (1 - t) ** 3 * P0 + 3 * (1 - t) ** 2 * t * P1 + 3 * (1 - t) * t ** 2 * P2 + t ** 3 * U
    zs, ys = c[:, 1], c[:, 0]
    if np.any(np.diff(zs) <= 0):
        res = None
    else:
        res = (zs, ys)
    _QF_F_CACHE[key] = res
    return res


# q12b (review 2026-10-22, item 2; user chose the reading B: "按照你推荐去做"): the full round fill (h5) is G2 with the wall at L, so wherever it reaches the door the crease L goes soft (x -1.0: 39 -> 4 deg,
# a saw-tooth where the 8 mm fillet switches off).  Over the wheel (L hidden in the opening) the fill stays full; over QF_B_XV it hands over to the B section: the face keeps its own (straight) section
# from L up to QF_B_S0 of the height and only above that gets ONE convex arc to U (a quintic: tangent and zero curvature where it leaves the old line, arriving in the full fill's direction at U),
# added as an offset to the old surface (<= ~7 mm).  L keeps its crease (visible from x ~-1.21, aft of the opening); the valley ahead of the door gap stays about the c10b waist (13-21 mm at z .78-.84; it
# cannot be filled without softening L).  QF_B_XV -1.60, -1.20: the hub section keeps ~83 % of the h5 fill (-1.45: 100 % but a 30 mm valley; -1.75: 56 %).
QF_B_ON = os.environ.get('QF_B_ON', '1') == '1'
QF_B_XV = tuple(float(v) for v in os.environ.get('QF_B_XV', '-1.60,-1.20').split(','))
QF_B_S0 = float(os.environ.get('QF_B_S0', '0.33'))
QF_B_M = tuple(float(v) for v in os.environ.get('QF_B_M', '1.6,0.5,2.0').split(','))       # start speed, end speed (x chord), tangential start acceleration (x chord)
_QF_B_CACHE = {}


def qf_b_offset(x):
    """(zs, dys) of the B arc's offset over the straight L -> U line at station x (z increasing), or None"""
    key = round(float(x), 6)
    if key in _QF_B_CACHE:
        return _QF_B_CACHE[key]
    res = None
    L, U = (np.asarray(D.CURVES[n].at(x), float)[1:] for n in ('L', 'U'))
    T = qf_f_target(x)
    if T is not None:
        p0 = L + QF_B_S0 * (U - L)
        t0 = (U - L) / np.linalg.norm(U - L)
        tU = np.array([T[1][-1] - T[1][-6], T[0][-1] - T[0][-6]])
        tU = tU / np.linalg.norm(tU)
        lc = float(np.linalg.norm(U - p0))
        m0, m1, a0 = QF_B_M
        u = np.linspace(0.0, 1.0, 200)[:, None]
        h0 = 1 - 10 * u ** 3 + 15 * u ** 4 - 6 * u ** 5
        h1 = u - 6 * u ** 3 + 8 * u ** 4 - 3 * u ** 5
        h2 = 0.5 * u ** 2 - 1.5 * u ** 3 + 1.5 * u ** 4 - 0.5 * u ** 5
        h4 = -4 * u ** 3 + 7 * u ** 4 - 3 * u ** 5
        c = h0 * p0 + h1 * (t0 * m0 * lc) + h2 * (t0 * a0 * lc) + (1 - h0) * U + h4 * (tU * m1 * lc)
        if np.all(np.diff(c[:, 1]) > 0):
            yl = L[0] + (c[:, 1] - L[1]) * (U[0] - L[0]) / (U[1] - L[1])
            res = (c[:, 1], c[:, 0] - yl)
    _QF_B_CACHE[key] = res
    return res


def qf_f_point(x, y, z):
    w = qf_f_w(x)
    if w <= 0.0:
        return y
    T = qf_f_target(x)
    if T is None or z < T[0][0] or z > T[0][-1]:
        return y
    full = float(np.interp(z, T[0], T[1])) - y
    if not (QF_B_ON and D.QF_C11_ON):
        return y + w * full
    v = 1.0 - float(D.sstep(QF_B_XV[0], QF_B_XV[1], x))          # 1 = the full fill (over the wheel), 0 = the B arc (door)
    dB = 0.0
    if v < 1.0:
        B = qf_b_offset(x)
        if B is not None and B[0][0] <= z <= B[0][-1]:
            dB = float(np.interp(z, B[0], B[1]))
    return y + w * (v * full + (1.0 - v) * dB)


def qf_fill(pm):
    """in-place: blend the outer boundary of a 'wall' / 'shoulder' mesh (vertices and, for the tools, its rows) into the convex target section"""
    if not QF_F_ON:
        return
    for i, v in enumerate(pm.verts):
        x, y, z = float(v[0]), float(v[1]), float(v[2])
        ny = qf_f_point(x, y, z)
        if ny != y:
            pm.verts[i] = (x, ny, z) + tuple(v[3:])
    if getattr(pm, 'rows', None) is not None:
        rows = []
        for r in pm.rows:
            r = np.array(r, float)
            for k in range(len(r)):
                r[k, 1] = qf_f_point(r[k, 0], r[k, 1], r[k, 2])
            rows.append(r)
        pm.rows = rows


# ----------------------------------------------------------------------------- fender3: the soft turn between the middle face (shoulder) and the lower face (wall) along L
# L is a crease of 27-32 degrees between the shoulder (leans back ~54 deg) and the wall (nearly vertical).  Forward of the wheel arch it is turned into a soft roll of radius BLEND_R (a quadratic Bezier through the crease
# with the tangent length h = R tan(phi / 2)): the shared boundary of the two panels is the arc's middle point Lm (edge 'Lm'), each panel carries its half of the arc.  The blend is full to BLEND_X0 and gone aft of BLEND_X1
# (the wheel arch hides x -1.9 .. -1.07), where Lm = L and the crisp line with the 8 mm fillet is as before.
BLEND_R = float(os.environ.get('BLEND_R', '0.0'))                       # q5c (user: 'the outermost crease must be sharp'): 0 = no soft roll, L is a crease with the standard fillet (was 0.08)
BLEND_X0, BLEND_X1 = float(os.environ.get('BLEND_X0', '-1.78')), float(os.environ.get('BLEND_X1', '-1.25'))
BLEND_DENS = 2.5                                         # the arc's nodes are (1 + BLEND_DENS) times denser than the straight parts of the row


# ----------------------------------------------------------------------------- q5: the lower end of the middle face over the front wheel (hidden in the wheel opening)
# The face below the crest U is ONE flat ruling from U to the line Lm.  Over the front wheel the wheel opening removes everything below z ~0.80 at the hub, so Lm (and the soft turn at it) is hidden there; the face
# is only seen above the opening.  Raising Lm in z over the wheel (a C2 plateau, QF_H_DZ between QF_H_X[1] and [2], zero ahead of [0] and aft of [3]) tilts the rulings flatter there:
# the straight face reaches the opening's top edge farther out (the body covers the tyre), the crest U is NOT moved, no section is rounded.  Hidden construction line only: the visible L (side marker, nose) is the L curve.
QF_H_ON = os.environ.get('QF_H_ON', '1') == '1'
QF_H_X = tuple(float(v) for v in os.environ.get('QF_H_X', '-1.85,-1.52,-1.52,-1.17').split(','))      # (QF_H_X=-1.85,-1.50,-1.50,-1.18: one peak without the plateau: no near-zero normal-rate strip at x -1.55, tested)
# (review 2026-10-23, item 3: the fall -1.487 -> -1.20 twisted the face 6.6 cm in 29 cm and left a dish (z_xx +2.4 /m) over the arch's rear end in the p016 zebra; -1.52 -> -1.17 (35 cm): the dish
#  -30 %, the body's edge over the arch 2.4 mm less far out at most (still over the tyre), the visible L aft of the arch (x > -1.211) raised 0.8 mm at most)
QF_H_DZ = float(os.environ.get('QF_H_DZ', '0.066'))


def qf_h(x):
    """the raise of Lm in z: C2 quintic rise from QF_H_X[0] to [1], plateau to [2], quintic fall to [3] (one rise, one fall)"""
    if not QF_H_ON:
        return 0.0
    a, b, c, d = QF_H_X
    return QF_H_DZ * float(D.sstep(a, b, x) * (1.0 - D.sstep(c, d, x)))


def g2_band(U, L, K, ts, tw, ls, lw, phi):
    """c9c fade band (design2 QF_FD_*).  At every station the cross-section between the middle face (straight ruling U -> A) and the wall (straight ruling B -> l3) is a band of tangent length a (A = L - a ts, B = L + a tw) in which
    the TANGENT ANGLE alpha(u) (u: 0 at A .. 1 at B, proportional to arc length) turns by psi = w(x) * phi through the C2 smootherstep S(u): the band's curvature kappa = psi S'(u) / Wb is 0 at both edges with zero slope (G2 with the
    faces), rises smoothly to its maximum at the middle and is proportional to w(x), i.e. grows monotonically along x from 0 at QF_FD_X[0] to its maximum at the arch mouth.  The rest of the dihedral, chi = (1 - w) phi, stays as a
    sharp crease in the middle of the band (the shared edge Lm of the two panels); it is 0 where w = 1.  Rows with w < 1e-4 keep the plain straight rows (= c8).  The two halves are returned as polylines (PS: Lm -> A, PW: Lm -> B)."""
    n = len(L)
    x = L[:, 0]
    w = (D.sstep(D.QF_FD_X[0], D.QF_FD_X[1], x) ** D.QF_FD_WP) * (1.0 - D.sstep(D.QF_FD_X[2], D.QF_FD_X[3], x))
    gw = D.sstep(D.QF_FD_AX[0], D.QF_FD_AX[1], x) if D.QF_FD_AA > D.QF_FD_A else 0.0 * x     # 2026-10-24: the band widens towards the arch mouth (design2 QF_FD_AA)
    aa = D.QF_FD_A + (D.QF_FD_AA - D.QF_FD_A) * gw
    cap = 0.4 + (D.QF_FD_CAP - 0.4) * gw
    if D.QF_C11_ON and D.QF_C11_BA > 0.0:         # c11: the same fade band again aft of the wheel opening (the shoulder is one round over the wheel: the corner behind the arch is no longer a crease at once)
        b0, b1, b2, b3 = D.QF_C11_BX
        w2 = D.sstep(b0, b1, x) * (1.0 - D.sstep(b2, b3, x))
        w = np.maximum(w, w2)
        aa = aa + (D.QF_C11_BA - D.QF_FD_A) * w2
    a = np.minimum(aa, cap * np.minimum(ls, lw))
    N = D.QF_FD_N
    u1 = np.linspace(0.0, 0.5, N + 1)
    u2 = np.linspace(0.5, 1.0, N + 1)
    S1, S2 = D.sstep(0.0, 1.0, u1), D.sstep(0.0, 1.0, u2)
    h = np.where((w > 1e-4) & (ls > 1e-6), a, 0.0)
    A, B, M = L.copy(), L.copy(), L.copy()
    PS, PW = np.repeat(L[:, None, :], N + 1, axis=1), np.repeat(L[:, None, :], N + 1, axis=1)
    cum = lambda f, u: np.r_[0.0, np.cumsum(0.5 * (f[1:] + f[:-1]) * np.diff(u))]
    for i in range(n):
        if h[i] <= 0.0:
            continue
        e1 = ts[i]
        e2 = tw[i] - (tw[i] @ e1) * e1
        e2 = e2 / np.linalg.norm(e2)
        psi = w[i] * phi[i]
        chi = phi[i] - psi
        al1, al2 = psi * S1, chi + psi * S2
        t1 = np.cos(al1)[:, None] * e1 + np.sin(al1)[:, None] * e2
        t2 = np.cos(al2)[:, None] * e1 + np.sin(al2)[:, None] * e2
        c1 = np.stack([cum(t1[:, k], u1) for k in range(3)], 1)        # integral of the tangent from u = 0 (A)
        c2 = np.stack([cum(t2[:, k], u2) for k in range(3)], 1)        # integral of the tangent from u = .5 (Lm)
        m = c1[-1] + c2[-1]
        Wb = 2.0 * h[i] * np.cos(0.5 * phi[i]) / np.linalg.norm(m)     # the band's length: A and B are the ends of the symmetric path
        A[i], B[i] = L[i] - h[i] * ts[i], L[i] + h[i] * tw[i]
        M[i] = A[i] + Wb * c1[-1]
        PS[i] = (A[i] + Wb * c1)[::-1]                                  # Lm -> A
        PW[i] = M[i] + Wb * c2                                          # Lm -> B
    return dict(U=U, L=L, K=K, A=A, B=B, M=M, h=h, phi=phi, w=w, PS=PS, PW=PW)


def blend_data(R):
    if 'blend' in R.cache:
        return R.cache['blend']
    n = I_TIP + 1
    U, L, K = R._edge('U')[:n], R._edge('L')[:n].copy(), R._edge('l3')[:n]
    L[:, 2] += np.array([qf_h(float(v)) for v in L[:, 0]])
    ts, tw = L - U, K - L
    ls, lw = np.linalg.norm(ts, axis=1), np.linalg.norm(tw, axis=1)
    ts = ts / np.maximum(ls, 1e-9)[:, None]
    tw = tw / np.maximum(lw, 1e-9)[:, None]
    phi = np.arccos(np.clip((ts * tw).sum(1), -1, 1))
    if D.QF_FD_ON:
        R.cache['blend'] = g2_band(U, L, K, ts, tw, ls, lw, phi)
        return R.cache['blend']
    w = 1.0 - D.sstep(BLEND_X0, BLEND_X1, L[:, 0])
    h = np.minimum(BLEND_R * np.tan(0.5 * phi) * w, 0.4 * np.minimum(ls, lw))
    h[ls < 1e-6] = 0.0
    h[h < 1e-5] = 0.0
    A = L - h[:, None] * ts
    B = L + h[:, None] * tw
    M = 0.25 * A + 0.5 * L + 0.25 * B
    R.cache['blend'] = dict(U=U, L=L, K=K, A=A, B=B, M=M, h=h, phi=phi)
    return R.cache['blend']


def e_Lm(R):
    P = R._edge('L').copy()
    bd = blend_data(R)
    P[:I_TIP + 1] = bd['M']
    return P


EDGES['Lm'] = e_Lm


def blend_row(bd, i, side, m):
    """the row of the soft turn at station i with m divisions: side 'shoulder' runs Lm -> arc half -> A -> U, side 'wall' runs l3 -> B -> arc half -> Lm; the arc's nodes are denser (BLEND_DENS)"""
    if 'PS' in bd:                                                      # c9c: the G2 band (g2_band)
        nh = bd['PS'].shape[1] - 1
        if side == 'shoulder':
            poly = np.vstack([bd['PS'][i], bd['U'][i][None, :]])         # Lm -> A -> U
        else:
            poly = np.vstack([bd['K'][i][None, :], bd['PW'][i][::-1]])   # l3 -> B -> Lm
    else:
        A, B, L, M = bd['A'][i], bd['B'][i], bd['L'][i], bd['M'][i]
        bez = lambda t: (1 - t) ** 2 * A + 2 * t * (1 - t) * L + t * t * B
        ts = np.linspace(0.0, 0.5, 25)
        nh = len(ts) - 1
        if side == 'shoulder':
            poly = np.vstack([np.array([bez(t) for t in ts[::-1]]), bd['U'][i][None, :]])                   # Lm (t .5) -> A (t 0) -> U
        else:
            poly = np.vstack([bd['K'][i][None, :], np.array([bez(t) for t in np.linspace(1.0, 0.5, 25)])])   # l3 -> B (t 1) -> Lm (t .5)
    seg = np.linalg.norm(np.diff(poly, axis=0), axis=1)
    dens = np.ones(len(seg))
    wd = 1.0
    if 'PS' in bd:        # c9c: the nodes crowd into the band only as the band's curvature grows (the row's node layout passes continuously from the c8 uniform one at the fade start / end: no skewed quads, no ticks at the rim cut)
        wd = float(D.sstep(0.0, D.QF_FD_WD, bd['w'][i]))
    if side == 'shoulder':
        dens[:nh] += BLEND_DENS * wd
    else:
        dens[-nh:] += BLEND_DENS * wd
    wsum = np.r_[0.0, np.cumsum(seg * dens)]
    q = np.linspace(0.0, wsum[-1], m + 1)
    cum = np.r_[0.0, np.cumsum(seg)]
    pos = np.interp(q, wsum, cum)
    r = np.stack([np.interp(pos, cum, poly[:, k]) for k in range(3)], 1)
    return r


def p_shoulder(R):
    """R1d2: unchanged (straight rulings with the lens bulge) up to x = design2.X_FOLD0, aft of it the fold's cross-section (design2.fold_row): the inclined leg leaves U tangent to the door glass,
    the soft roll peels off U and runs on as the soft arc.  fender3: forward of the wheel arch the row starts with the half of the soft turn to the wall (Lm -> arc -> straight ruling to U)."""
    A, B = R.edge('Lm')[:I_TIP + 1], R.edge('U')
    prof = bulge_prof(lens_amp)
    bd = blend_data(R)

    def rf(i, a, b, m):
        if a[0] <= D.X_FOLD0 + 1e-9:
            if bd['h'][i] > 0.0:
                r = blend_row(bd, i, 'shoulder', m)
                return r + prof(i, chord_s(r), r)
            s = np.linspace(0, 1, m + 1)[:, None]
            r = a + (b - a) * s
            return r + prof(i, s[:, 0], r)
        P = D.fold_row(a, b, m)[0]
        w = float(D.sstep(D.X_FOLD0, X_BIRTH, a[0])) if X_BIRTH > D.X_FOLD0 + 1e-6 else 1.0
        if w < 1.0:
            # rearcrease round 4: the ruling rows of x <= X_FOLD0 are blended into the fold over X_FOLD0 .. X_BIRTH (the crease along U fades out, the roll's birth is no longer a 1 cm radius in one station)
            s = np.linspace(0, 1, m + 1)[:, None]
            r = a + (b - a) * s
            r = r + prof(i, s[:, 0], r)
            P = (1.0 - w) * r + w * P
            P[0], P[-1] = a, b
        return P
    return strip('shoulder', PAINT, A, B, HC['shoulder'], prof=prof, row_fn=rf, pinN=R.edge('tip_lo'), quads=True)


def wall_pairs():
    """rearcrease: L index of the partner of each l3 sample 0..I_FE in the wall's rows.  Row i joins l3[i] with L[i] up to the station I_WF0; from there on the partner lags behind (smoothstep) so that the
    last row joins E = l3[I_FE] with S = L[I_FS]: the rows tilt gradually into the facet edge, which is the wall's last row.  Steps of 0 / 1: every L sample up to S is used (watertight with the shoulder)."""
    i = np.arange(I_FE + 1)
    return i - np.round((I_FE - I_FS) * D.sstep(I_WF0, I_FE, i.astype(float))).astype(int)


def p_wall(R):
    """the wall up to the facet edge: a ruled strip between l3 and Lm whose last row is the facet edge E -> S (R1.. unchanged forward of the station I_WF0)"""
    l3, Lm = R.edge('l3'), R.edge('Lm')
    A, B = l3[:I_FE + 1], Lm[wall_pairs()]
    bd = blend_data(R)
    lagc = (I_FE - I_FS) * D.sstep(I_WF0, I_FE, np.arange(I_FE + 1).astype(float))     # the lag of the partner as a continuous function of the row

    def rf(i, a, b, m):
        if i <= I_TIP and bd['h'][i] > 0.0:
            return blend_row(bd, i, 'wall', m)
        s = np.linspace(0, 1, m + 1)[:, None]
        if lagc[i] <= 1e-9:
            return a + (b - a) * s
        # rearcrease: the partner is an L sample (integer lag: the edge is shared), but the rulings follow the CONTINUOUS lag (the point of the polyline L at the fractional index), the quantisation error
        # (b - t, along L, at most half a station) is absorbed in the top band of the row: a smooth fan in the interior, no zig-zag of 0 / 1 lag steps in the reflections
        f = i - lagc[i]
        k = min(int(np.floor(f)), len(Lm) - 2)
        t = Lm[k] + (f - k) * (Lm[k + 1] - Lm[k])
        w = D.sstep(WALL_BAND, 1.0, s)
        return a + (t - a) * s + (b - t) * w
    return strip('wall', PAINT, A, B, HC['wall'], pin0=R.edge('E_up'), pinN=R.edge('facet_edge'), row_fn=rf, quads=True)


def p_facet(R):
    """rearcrease: the rear-corner facet (SPEC L12), a PLANE between the facet edge E -> S (its first row), l3 (bottom), L (top, straight aft of S) and the tail face's side edge (its last row).  The rows join the l3 and
    L samples along a monotone staircase (b advances faster than a: L has 28 samples here, l3 17): every sample of both edges is a vertex (watertight with wall_black / rear_shoulder), the rows are chords of the planar quad"""
    l3, L = R.edge('l3'), R.edge('L')
    nb = I_LAST - I_FS + 1
    k = np.arange(nb)
    ia = I_FE + np.round(k * (I_LAST - I_FE) / (nb - 1)).astype(int)
    ib = I_FS + k
    pm = strip('facet', PAINT, l3[ia], L[ib], HC['wall'], pin0=R.edge('facet_edge'), pinN=R.edge('tail_side_up'), quads=True)
    return facet_ruled(R, pm, l3, L)


def facet_ruled(R, pm, l3, L):
    """rearcrease round 3 (coordinator, 2026-10-20): the facet is a RULED surface between the edge S -> E (the straight first row) and the tail face's side edge (the last row).  The tail edge lies on the tail face,
    so its vertices stand up to ~2 mm off the facet's plane; as a plane + a one-strip step that was a faint diagonal line inside the facet.  Here every interior vertex is moved along the plane's normal by u * dev(t): (u, t) are the
    bilinear coordinates of the vertex in the quad E, S, TL, T3 (u: 0 at the edge S -> E, 1 at the tail edge; t: 0 on l3, 1 on L) and dev(t) the signed distance of the tail edge's point at t from the plane, so the surface is
    exactly (1 - u) * (S -> E)(t) + u * tail(t) (plus the plane's own part).  Not moved: the first and the last row (the shared edges), the row end vertices on l3 and on L."""
    n, t3 = facet_plane(R, L[-1])
    E, S, T3, TL = l3[I_FE], L[I_FS], l3[-1], L[-1]

    def uv(p):
        u = t = 0.5
        for _ in range(12):
            F = (1 - u) * (1 - t) * E + (1 - u) * t * S + u * (1 - t) * T3 + u * t * TL
            Ju = -(1 - t) * E - t * S + (1 - t) * T3 + t * TL
            Jt = -(1 - u) * E + (1 - u) * S - u * T3 + u * TL
            J = np.stack([Ju, Jt], 1)
            d = np.linalg.lstsq(J, p - F, rcond=None)[0]
            u, t = u + d[0], t + d[1]
            if abs(d).max() < 1e-12:
                break
        return u, t

    tail = np.asarray(pm.rows[-1], float)
    tt = np.array([uv(q)[1] for q in tail])
    dev = (tail - t3) @ n
    o = np.argsort(tt)
    tt, dev = tt[o], dev[o]
    pos = 0
    rows = [np.asarray(r, float).copy() for r in pm.rows]
    for k, r in enumerate(rows):
        if 0 < k < len(rows) - 1:
            for j in range(1, len(r) - 1):
                u, t = uv(r[j])
                r[j] = r[j] + n * (u * float(np.interp(t, tt, dev)))
    ids = 0
    for r in rows:
        for q in r:
            pm.verts[ids] = tuple(q)
            ids += 1
    pm.rows = rows
    return pm


def p_wall_black(R):
    A, B = R.edge('low'), R.edge('l3')
    # rearcrease 2: l3 moves (plan kink) so the longest row got shorter; the row's division count must stay what it was (15: the longest row, 0.451 m, of the locked panel), else every vertex of the panel moves
    return strip('wall_black', TRIM, A, B, HC['black'], pin0=R.edge('E_low'), minm=15)


P_END = 8                 # the rows' node distribution changes from uniform (nose) to the END row's (cowl) with u^P_END; the rows themselves stay straight


def row_pairs():
    """the rows of the flap and the fender top as pairs (L5 index, U index): row k pairs L5[k] with U[k] (a regular grid: no zipper triangles, a row-to-row normal change of 0.3 degrees; the FRONT round-3 attempt to pair
    L5[33] with U[23] so that the seam row was a constant-x line made fan rows and 1-4 degree normal jitter, striped reflections).  apillar: the PAIRING is still index to index, but the SAMPLES of L5 are no longer uniform
    (design2.l5_tau): aft of the flap seam the L5 partner of crest sample U[k] moves to the same x (the rulings are the x-sections of the face, whose lean the eye reads), and where L5 has ended (the cowl corner W, x -1.625)
    the remaining crest samples fan out from a 3.5 cm smear of W.  Returns (pairs, index of the seam row = TRI_K)."""
    n = I_A
    return [(k, k) for k in range(n + 1)], D.TRI_K


def fender_rows(R):
    """the rows of the flap and the fender top between the hood edge L5 and the crest U: row k pairs L5[k] with U[k] (see row_pairs).
    G-5 (user principle, 2026-10-19): the fender top is a RULED surface, every row a straight line from the crisp straight edge L5 to the crest U (no v^2 profile, no tilted plane Q, no blend band behind the
    seam, no lift term): the ramp from the hood up to the crest is straight across, the seam of the corner flap (row TRI_K) is one of these straight rows (a straight line C -> B) and the flap is simply
    the first TRI_K rows of the same surface.  Only the NODES move along the rows: uniform near the nose, the END row's (cowl diagonal + foot rung) towards the windscreen (the last row is shared with the glass)."""
    L5, U, END = R.edge('L5'), R.edge('U')[:I_A + 1], R.edge('F_end')
    n = I_A
    assert len(L5) == n + 1 and len(U) == n + 1 and n == D.TRI_N and abs(XS[D.TRI_K] - D.station_x(D.TRI_K)) < 1e-9
    N0 = np.array(D.N)
    W0, A0 = L5[-1], U[-1]
    m_end = len(END) - 1
    dd = A0 - W0
    s_end = ((END - W0) @ dd) / float(dd @ dd)                    # chord fractions of the END nodes: END lies on the straight line W0 -> A0
    assert np.abs(END - (W0 + np.outer(s_end, dd))).max() < 1e-6, 'F_end is not straight: the last row of the ruled fender top must be'
    pairs, iseam = row_pairs()
    rows = []
    for r_i, (a, b) in enumerate(pairs):
        u = 0.5 * (a + b) / n
        if np.linalg.norm(U[b] - L5[a]) < 1e-7:
            r = N0[None, :]
        elif a == n:
            r = END
        else:
            s = (1.0 - u ** P_END) * np.linspace(0.0, 1.0, m_end + 1) + u ** P_END * s_end
            r = L5[a] + (U[b] - L5[a]) * s[:, None]
            if D.QF_FT_C > 0.0 or D.QF_FT_K > 0.0:                # c10: the fender top is slightly convex (see design2.QF_FT_C): the crown follows the row's chord parameter, its height the envelope over the rows
                if D.QF_FT_K > 0.0:                               # 2026-10-24: constant cross curvature (design2.QF_FT_K): crown height K w^2 / 8 (capped), faded in behind the seam
                    wr = float(np.linalg.norm(U[b] - L5[a]))
                    hc = min(D.QF_FT_CMAX, D.QF_FT_K * wr * wr / 8.0) * float(D.sstep(iseam, iseam + D.QF_FT_R0 * (n - iseam), r_i) * (1.0 - D.sstep(n - D.QF_FT_R1K * (n - iseam), n, r_i)))
                else:
                    hc = D.QF_FT_C * float(D.sstep(iseam, iseam + D.QF_FT_R0 * (n - iseam), r_i) * (1.0 - D.sstep(n - D.QF_FT_R1 * (n - iseam), n, r_i)))
                if hc > 0.0:
                    t = U[b] - L5[a]
                    nrm = np.cross(t, np.array([1.0, 0.0, 0.0]))
                    nrm = nrm / np.linalg.norm(nrm)
                    if nrm[2] < 0:
                        nrm = -nrm
                    cs = chord_s(r)
                    r = r + (hc * 4.0 * cs * (1.0 - cs))[:, None] * nrm
            r[0], r[-1] = L5[a], U[b]
        rows.append(r)
    return rows, iseam


def _rows_panel(name, mat, rows, k0, k1):
    pm = PM(name, mat)
    ids, ss = [], []
    for k in range(k0, k1 + 1):
        ids.append(pm.add_row(rows[k]))
        ss.append(chord_s(rows[k]))
    for i in range(len(ids) - 1):
        zipper(ids[i], ids[i + 1], ss[i], ss[i + 1], pm.faces)
    return pm


def p_fender_top(R):
    rows, iseam = fender_rows(R)
    return _rows_panel('fender_top', PAINT, rows, iseam, len(rows) - 1)


def p_corner_tri(R):
    """R1e: the corner-triangle flap (005 / p013): a small planar facet at the nose corner N between L5, the crest U and the straight seam C -> B (a slight tilt about L5)"""
    rows, iseam = fender_rows(R)
    return _rows_panel('corner_tri', PAINT, rows, 0, iseam)


def p_door_glass(R):
    A, B = R.edge('U')[I_A:], R.edge('wl')
    return strip('door_glass', GLASS, A, B, HC['door_glass'], minm=D.QR_DG_M if D.QR_ON else 1)       # q4-rear: keep the locked division count (the strip is a regular grid: M = the longest chord's; the window line moved)


# A-pillar round 2 (2026-10-24, user: the real pillar is "更厚实更流畅"): p016 shows the pillar and the roof rail with a thin highlight along the windscreen side and a grey outer face, the
# same all along: a ROUNDED section, where the model had a flat strip whose tilt turned from ~7 deg at the foot to ~36 deg under the header.  Each row rail -> wl is now crowned by
# QF_AP_BK x its chord (cap QF_AP_BMAX) along the chord's outward normal, with the shape 27/4 s (1 - s)^2 (peak at a third of the way from the rail): a tight roll leaves the windscreen
# 25 deg above the chord (about the glass' own cross slope) and the outer two thirds are a nearly flat side face meeting the door glass along the chord, so the light picks out a thin
# edge on the windscreen side over a uniform face.  (The first version, a symmetric parabola, lit the whole pillar evenly: 2026-10-24, user: "缺少了点钢柱的立体感".)  The nodes
# are crowded towards the roll (s^QF_AP_SK).  The crown fades in from the foot rung (pinned: the fender top's end row) over QF_AP_BX[0..1] and out over QF_AP_BX[2..3] before the
# window tip (the rail band lies in the beam face there, q16).  QF_AP_M divisions across.
QF_AP_BK = float(os.environ.get('QF_AP_BK', '0.07'))
QF_AP_SK = 1.35
QF_AP_BMAX = float(os.environ.get('QF_AP_BMAX', '0.006'))
QF_AP_M = int(os.environ.get('QF_AP_M', '8'))
QF_AP_BX = (-1.43, -1.33, 0.75, 1.05)


def ap_crown(x):
    x = np.asarray(x, float)
    return D.sstep(QF_AP_BX[0], QF_AP_BX[1], x) * (1.0 - D.sstep(QF_AP_BX[2], QF_AP_BX[3], x))


def ap_off(a, b, tg, s):
    """offsets of the rounded row a (rail) -> b (wl) at the fractions s: the crown along the outward normal of the chord in the plane across the rail's tangent tg"""
    c = b - a
    L = float(np.linalg.norm(c))
    n = np.cross(tg, c)
    nn = float(np.linalg.norm(n))
    if L < 1e-6 or nn < 1e-12:
        return np.zeros((len(s), 3))
    n = n / nn
    if n @ np.array([0.0, np.sign(a[1]), 1.0]) < 0.0:
        n = -n
    h = min(QF_AP_BK * L, QF_AP_BMAX) * float(ap_crown(0.5 * (a[0] + b[0])))
    sr = np.asarray(s, float) ** QF_AP_SK                                     # the node moves along the chord (crowded towards the roll) ...
    return (sr - s)[:, None] * c[None, :] + (6.75 * h * sr * (1.0 - sr) ** 2)[:, None] * n[None, :]      # ... and is lifted off it


def ap_row(a, b, tg, m):
    s = np.linspace(0.0, 1.0, m + 1)
    r = a + (b - a) * s[:, None] + ap_off(a, b, tg, s)
    r[0], r[-1] = a, b
    return r


def ap_prof(rail):
    """strip prof for the rounded pillar / roof rail rows (rail: the rows' rail points, index-aligned with the strip's rows)"""
    tg = np.gradient(np.asarray(rail, float), axis=0)
    return lambda i, s, P: ap_off(P[0], P[-1], tg[i], s)


def p_pillar(R):
    """the A pillar and the roof rail between the pillar foot and the B pillar (round 2: rounded section, see QF_AP_BK)"""
    pin = R.edge('foot')
    A = R.edge('rail')[I_A - I_W:I_B - I_W + 1]
    B = R.edge('wl')[:I_B - I_A + 1]
    if QF_AP_BK > 0.0:
        return strip('pillar', PAINT, A, B, 1.0, pin0=pin, pinN=R.edge('b_rung'), prof=ap_prof(A))      # (hc 1 m: every row takes the b_rung's QF_AP_M divisions, CONST_M)
    return strip('pillar', PAINT, A, B, HC['pillar'], pin0=pin, pinN=R.edge('b_rung'))


def p_rail_band(R):
    A, B = R.edge('wl')[I_B - I_A:], R.edge('rail')[I_B - I_W:I_TIP - I_W + 1]
    if QF_AP_BK > 0.0:
        return strip('rail_band', PAINT, B, A, 1.0, pin0=R.edge('b_rung'), pinN=R.edge('tip_up')[::-1], prof=ap_prof(B))
    return strip('rail_band', PAINT, B, A, HC['band'], pin0=R.edge('b_rung'), pinN=R.edge('tip_up')[::-1])


def tip_row_up(R):
    """the upper part of the rung L -> rail at the window tip (window tip -> rail), shared by the rail band and the rear shoulder"""
    tip = R.edge('U')[-1]
    rail = R.edge('rail')[I_TIP - I_W]
    return _lin(tip, rail, max(1, int(round(np.linalg.norm(rail - tip) / HC['band']))))


QF_RS_SHEAR = float(os.environ.get('QF_RS_SHEAR', '0.5'))      # q16 rear shoulder (review 2026-10-23, item 1): rows solved from the design L and sheared onto the facet's edge within this fraction of the row (0 = rows start on the facet's edge: its 12 deg plan corner at S ran across the platform as a crease)


def p_rear_shoulder(R):
    """R1d2: the soft arc.  Rows aft of the window tip: the fold's cross-section (design2.fold_row: L -> shoulder leg -> ROLL -> inclined leg -> crest, G2), whose nodes start as those of the tip row
    (the pinned first row) and move over X_NODE to the standard distribution (dense across the roll)."""
    A, B = R.edge('L')[I_TIP:], R.edge('rail')[I_TIP - I_W:]
    pin0 = np.vstack([R.edge('tip_lo'), R.edge('tip_up')[1:]])        # the rung L -> rail at the tip: the shoulder's last row + the rail band's last row
    cs = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(pin0, axis=0), axis=1))]
    cs /= cs[-1]

    L_old = R.cache['L_old'][I_TIP:]
    def rf(i, a, c, m):
        x = 0.5 * (a[0] + c[0])
        w = float(D.sstep(D.X_TIP, D.X_TIP + D.X_NODE, x))
        u0 = np.interp(np.arange(m + 1) * (len(pin0) - 1) / m, np.arange(len(pin0)), cs)
        if D.QF_Q16:            # q16: the platform's rulings start on L itself (the facet's straightened L included)
            da = a - L_old[i]
            if QF_RS_SHEAR > 0.0 and np.linalg.norm(da) > 1e-9:
                # (review 2026-10-23, item 1): aft of the facet apex S L is the facet's straight top edge, which turns 12 deg in plan at S (the facet's plane forces it); rows started on it
                # carried that corner across the whole platform as a crease (x 1.97, 1.8 deg).  The row is solved from the design L (smooth in plan; the section angles are taken from it
                # anyway) and sheared onto the facet's edge only within QF_RS_SHEAR of the row next to L (C2 fall-off): the corner stays on L
                P = D.fold_row(L_old[i], c, m, u0=u0, w=w)[0]
                t = np.clip(chord_s(P) / QF_RS_SHEAR, 0.0, 1.0)
                g = 1.0 - t ** 3 * (10.0 - 15.0 * t + 6.0 * t * t)
                P = P + g[:, None] * da[None, :]
            else:
                P = D.fold_row(a, c, m, u0=u0, w=w)[0]
            P[0], P[-1] = a, c
            return P
        # rearcrease: the fold (the soft arc R-6, the crown) is solved from the OLD character line, so that it stays where it was accepted; only the row's start moves onto the new (straightened) L,
        # the displacement dies out over the first half of the row (smoothstep along the chord): the facet's top edge moves, the soft arc does not
        P = D.fold_row(L_old[i], c, m, u0=u0, w=w, ja=(len(R.edge('tip_lo')) - 1 if m == len(pin0) - 1 else None))[0]
        da = a - L_old[i]
        if np.linalg.norm(da) > 1e-9:
            g = 1.0 - chord_s(P)                       # a SHEAR (linear in the arclength): the straight legs stay straight, the roll's curvature does not change (a smoothstep here made an S near L)
            P = P + g[:, None] * da[None, :]
        P[0], P[-1] = a, c
        return P
    return strip('rear_shoulder', PAINT, A, B, HC['rear'], pin0=pin0, pinN=R.edge('tail_a'), row_fn=rf, quads=True)


def p_glass(R):
    ge, tp = R.edge('gedge')[:I_SEAM - I_W + 1], R.edge('top')[:I_SEAM - I_W + 1]
    return strip('glass', GLASS, ge, tp, HC['glass'], pin0=R.edge('cowl')[::-1], pinN=R.edge('seam_row'), row_fn=lambda i, a, b, m: glass_row(a, b, m))


def p_ridge_inner(R):
    i0 = IX(0.15) - I_W
    A, B = R.edge('rail')[i0:], R.edge('gedge')[i0:]
    return strip('ridge_inner', PAINT, A, B, HC['ridge'])


def p_deck(R):
    A = R.edge('gedge')[I_SEAM - I_W:]
    B = R.edge('top')[I_SEAM - I_W:]
    return strip('deck', PAINT, A, B, HC['deck'], pin0=R.edge('seam_row'), pinN=R.edge('tail_b'))


def lift_x(P, fx):
    P = P.copy()
    P[..., 0] = fx(P[..., 1], P[..., 2])
    return P


def p_tail_upper(R):
    split, ta, tb, side = R.edge('tail_split'), R.edge('tail_a'), R.edge('tail_b'), R.edge('tail_side_up')
    top = np.vstack([ta, tb[1:]])[::-1]                                  # centre -> L end
    nj = len(side) - 1
    left = np.array([[D.tail_x(0.0, z), 0.0, z] for z in np.linspace(split[0][2], top[0][2], nj + 1)]).reshape(-1, 3)
    Y = coons_grid(split[:, 1:], top[:, 1:], left[:, 1:], side[:, 1:])
    X = D.tail_x(Y[..., 0], Y[..., 1])
    P = np.concatenate([X[..., None], Y], -1)
    P[0], P[-1], P[:, 0], P[:, -1] = split, top, left, side
    pm = PM('tail_upper', PAINT)
    grid_faces(pm, P)
    return pm


def p_tail_lower(R):
    bot, split, side = R.edge('tail_bottom'), R.edge('tail_split'), R.edge('E_side')
    nj = len(side) - 1
    left = np.array([[D.tail_x(0.0, z), 0.0, z] for z in np.linspace(bot[0][2], split[0][2], nj + 1)]).reshape(-1, 3)
    Y = coons_grid(bot[:, 1:], split[:, 1:], left[:, 1:], side[:, 1:])
    X = D.tail_x(Y[..., 0], Y[..., 1])
    P = np.concatenate([X[..., None], Y], -1)
    P[0], P[-1], P[:, 0], P[:, -1] = bot, split, left, side
    pm = PM('tail_lower', TRIM)
    grid_faces(pm, P)
    return pm


def e_tip_lo(R):
    """the shoulder's last row at the window tip: the fold's cross-section there (design2.fold_row, ends at the tip: the inclined leg arrives tangent to the rail band's last row)"""
    a, b = R._edge('L')[I_TIP], R._edge('U')[-1]
    return D.fold_row(a, b, max(1, int(round(np.linalg.norm(b - a) / HC['shoulder']))))[0]


def e_tip_up(R):
    a, b = R._edge('U')[-1], R._edge('rail')[I_TIP - I_W]
    return _lin(a, b, max(1, int(round(np.linalg.norm(b - a) / HC['band']))))


def e_b_rung(R):
    rail = R._edge('rail')
    a, b = rail[I_B - I_W], R._edge('wl')[I_B - I_A]
    if QF_AP_BK > 0.0:
        return ap_row(a, b, rail[I_B - I_W + 1] - rail[I_B - I_W - 1], QF_AP_M)
    return _lin(a, b, 2)


EDGES['b_rung'] = e_b_rung
EDGES['tip_lo'] = e_tip_lo
EDGES['tip_up'] = e_tip_up

PANEL_LIST = [
    Panel('front_face', p_front_face, TRIM, ['LE_str', 'F_bot', 'F_cen', 'crease']),
    Panel('nose_corner_up', p_nose_corner_up, PAINT, ['cut_up', 'LE_ch', 'face_edge_up', 'E_up', 'l3', 'Lm']),
    Panel('nose_corner_low', p_nose_corner_low, TRIM, ['cut_low', 'cut_up', 'face_edge_low', 'E_low']),
    Panel('hood', p_hood, PAINT, ['LE', 'L5', 'cowl', 'hood_cen']),
    Panel('corner_tri', p_corner_tri, PAINT, ['L5', 'U', 'F_end'], hint=np.array([0.0, 0.0, 1.0])),
    Panel('fender_top', p_fender_top, PAINT, ['L5', 'U', 'F_end'], hint=np.array([0.0, 0.0, 1.0])),
    Panel('shoulder', p_shoulder, PAINT, ['Lm', 'U', 'tip_lo']),
    Panel('wall', p_wall, PAINT, ['l3', 'Lm', 'E_up', 'facet_edge']),
    Panel('facet', p_facet, PAINT, ['l3', 'L', 'facet_edge', 'tail_side_up']),
    Panel('wall_black', p_wall_black, TRIM, ['low', 'l3', 'E_low']),
    Panel('door_glass', p_door_glass, GLASS, ['U', 'wl']),
    Panel('pillar', p_pillar, PAINT, ['rail', 'wl', 'foot', 'b_rung']),
    Panel('rail_band', p_rail_band, PAINT, ['wl', 'rail', 'tip_up', 'b_rung']),
    Panel('rear_shoulder', p_rear_shoulder, PAINT, ['L', 'rail', 'tip_lo', 'tip_up', 'tail_a']),
    Panel('glass', p_glass, GLASS, ['gedge', 'top', 'cowl', 'seam_row']),
    Panel('ridge_inner', p_ridge_inner, PAINT, ['rail', 'gedge'], hint=np.array([0.0, -0.6, 1.0])),
    Panel('deck', p_deck, PAINT, ['gedge', 'top', 'seam_row', 'tail_b']),
    Panel('tail_upper', p_tail_upper, PAINT, ['tail_split', 'tail_a', 'tail_b', 'tail_side_up']),
    Panel('tail_lower', p_tail_lower, TRIM, ['tail_bottom', 'tail_split', 'E_side']),
]
if D.QF_CF_ON:          # c10b: no chamfer facets (the wall / wall_black start at the front face's end generator)
    PANEL_LIST = [p for p in PANEL_LIST if p.name not in ('nose_corner_up', 'nose_corner_low')]
PANELS = {p.name: p for p in PANEL_LIST}

# panel boundaries that are NOT creases (the surface continues smoothly across)
SMOOTH_PAIRS = {frozenset(('nose_corner_up', 'nose_corner_low')), frozenset(('shoulder', 'rear_shoulder')), frozenset(('pillar', 'rail_band')), frozenset(('wall', 'wall')), frozenset(('wall', 'facet')),
                frozenset(('corner_tri', 'fender_top'))}          # the flap's seam is tangent (< 0.3 degrees: flap = plane, the fender top leaves it smoothly); the flap is delimited by the FRONT agent's panel gap
if D.QF_NC_ON:          # c10: the chamfer bends G1 into the wall (p_nose_corner_up): no fillet along E_up (the quads next to it differ by ~5 degrees only because of the discretisation)
    SMOOTH_PAIRS = SMOOTH_PAIRS | {frozenset(('nose_corner_up', 'wall'))}
# boundaries that always get the fillet, whatever the (small) angle: L5, the straight crease between the hood and the corner flap / fender top (G-5: crisp and straight along its whole length; its angle
# changes from a valley of ~7 degrees at the nose through 0 (x ~ -1.8) to a shallow ridge at the cowl, so it must be all or nothing)
FORCE_FILLET = {frozenset(('corner_tri', 'hood')), frozenset(('hood', 'fender_top'))}
# fender3: along the soft turn between the middle and the lower face (the blend of L, see blend_data) the turn per mesh edge is 3-5 degrees: without this the 8 mm fillet would switch on and off along the line (ripples in
# the reflection); the crease aft of the blend (>= 14 degrees where the blend dies out, 32-39 aft of the wheel arch) keeps its fillet
PAIR_MIN_ANGLE = {frozenset(('shoulder', 'wall')): 12.0}
# c9c fade: the residual crease in the middle of the band (g2_band) is filleted by the generic bevel only where it turns more than 12 degrees: the fillet would end in a saw-tooth where the angle falls through the threshold (seen as
# ~1 px teeth at the apex of the reflection fan when the fillet of the pair was switched off).  QF_FD_FORCE=1 (default) keeps the 8 mm fillet along the whole shoulder / wall edge (below ~2 degrees it is invisible)
if D.QF_FD_ON and os.environ.get('QF_FD_FORCE', '1') == '1':
    FORCE_FILLET = FORCE_FILLET | {frozenset(('shoulder', 'wall'))}


# ----------------------------------------------------------------------------- build / orient / checksum
def orient(pm, panel):
    """flip the faces of a panel so that they point outwards (hint: away from the car's centre, or the panel's explicit hint)"""
    V = np.array(pm.verts)
    tot = 0.0
    c0 = np.array([0.0, 0.0, 0.6])
    for f in pm.faces:
        p = V[list(f)]
        n = np.cross(p[1] - p[0], p[2] - p[0]) if len(f) == 3 else np.cross(p[2] - p[0], p[3] - p[1])
        h = panel.hint if panel.hint is not None else (p.mean(0) - c0)
        tot += float(n @ h)
    if tot < 0:
        pm.faces = [tuple(reversed(f)) for f in pm.faces]
    return tot


def checksum(pm):
    V = np.round(np.array(pm.verts) * 1e4).astype(np.int64)             # 0.1 mm
    h = hashlib.sha1()
    h.update(V.tobytes())
    h.update(json.dumps([list(f) for f in pm.faces]).encode())
    return h.hexdigest()[:16]


# ----------------------------------------------------------------------------- P3 (reconstruction phase 3, 2026-10-25): the rear hips and the front widening (CALIB.md phase 3)
# The calibrated top view p013 (a clean white-on-ground outline, both sides alike) puts the body's outline 3-4.3 cm outside the model over the rear wheel (x 1.3 .. 2.0) and ~0 along the doors; the rear views
# (r81, p012, p019) agree (+3..5 cm at z 0.8-0.9).  QF_P3_HIP=1 moves the body outward (y only) by dy = A(x) g(x, z) w(|y|):
#   A(x)  the hip amplitude (QF_P3_HIP_A, x:cm knots; C2 spline with zero end slopes, zero outside the knots);
#   g     0 at QF_P3_HIP_Z0, a smoothstep up to 1 at L's height (the crease that carries the hip: it stays the outermost line), then linear back to 0 at the roof rail (the rear shoulder
#         face, ruled, turns about the rail and stays ruled);
#   w     a smoothstep over |y| 0.30 .. 0.50 (no edge in the field).
# A smooth field of position only: shared vertices of neighbouring panels move alike (no cracks), creases stay creases.  The wheel openings are cut afterwards (unchanged in side view).
# (A was trimmed after the first build: p013 put that build 1 cm wide at x 1.6 .. 2.0.)  The FRONT widening is its own switch, QF_P3_FRONT below.
QF_P3_HIP = os.environ.get('QF_P3_HIP', '1') == '1'
QF_P3_HIP_A = tuple(tuple(float(u) for u in kv.split(':')) for kv in os.environ.get(
    'QF_P3_HIP_A', '1.00:0,1.20:1.6,1.40:3.9,1.60:4.4,1.80:4.3,2.00:3.9,2.20:2.6,2.38:0.9,2.46:0').split(','))
QF_P3_HIP_Z0 = float(os.environ.get('QF_P3_HIP_Z0', '0.40'))                 # bottom of the field (z, m)
QF_P3_HIP_W = tuple(float(v) for v in os.environ.get('QF_P3_HIP_W', '1.00,1.20,2.30,2.46').split(','))   # C2 window on A: in over [0..1], out over [2..3] (value, slope and
#   curvature reach 0 at the ends; the spline alone ended with a curvature step of 1.1 / 4.7 1/m)
# The rear-corner facet (SPEC L12, the wing's endplate side) is a PLANE: the field above would bend it (3.6 -> 7.9 mm off its plane).  Inside the box QF_P3_HIP_FACET (x0, x1, z0, z1, around
# the facet: x 1.97-2.37, z 0.73-0.99) the hip is replaced by its least-squares affine fit a0 + a1 x + a2 z (an affine map keeps planes planar), blended back to the hip over QF_P3_HIP_FM (m)
# outside the box; a pure function of position, so the panels sharing the facet's edges move with it.  '0' = off.
QF_P3_HIP_FACET = os.environ.get('QF_P3_HIP_FACET', '1.95,2.39,0.71,1.00')
QF_P3_HIP_FM = float(os.environ.get('QF_P3_HIP_FM', '0.08'))
# QF_P3_FRONT=1: the front widening (p013: +3..5 cm from just behind the face corner N over the front wheel, tapering along the door to 0 at x ~0.45; L_front fitted 4-5 cm out, the fender
# crest U_front ~unchanged at x -2.3 .. -1.8).  dy = A(x) g w(|y|) as above, with
#   A(x)  a natural C2 spline through QF_P3_FRONT_A (x:cm) times a smoothstep rise from 0 at the face corner over QF_P3_FRONT_RISE (the front face itself stays);
#   g     below L: a smoothstep over QF_P3_FRONT_ZB (only the floor's edge fades: the whole side face moves); above L: 1 - (1 - k) smoothstep(S0, 1, d / |LU|), d the distance from L
#         in the section, |LU| the rung L -> U (the fender top over the wheel moves with L); k(x) is how far the crest U follows L: 1 ahead of QF_P3_FRONT_UK[0] (at the nose L and U meet),
#         0 behind QF_P3_FRONT_UK[1] (U_front is pinned there, sigma 1 mm), so the fender top's tilt grows steadily instead of twisting where the rung is short; inboard of U the
#         remaining k fades out over QF_P3_FRONT_DU (m).
QF_P3_FRONT = os.environ.get('QF_P3_FRONT', '1') == '1'
QF_P3_FRONT_A = tuple(tuple(float(u) for u in kv.split(':')) for kv in os.environ.get(
    'QF_P3_FRONT_A', '-2.46:4.0,-1.85:4.8,-1.30:4.3,-0.80:2.7,-0.30:1.6,0.15:0.5,0.50:0').split(','))
QF_P3_FRONT_RISE = tuple(float(v) for v in os.environ.get('QF_P3_FRONT_RISE', '-2.46,-2.22').split(','))
QF_P3_FRONT_END = tuple(float(v) for v in os.environ.get('QF_P3_FRONT_END', '0.00,0.50').split(','))   # C2 window at the door end (the spline alone ended with a slope:
#   a 0.66 deg corner in L's plan at x 0.50)
QF_P3_FRONT_ZB = tuple(float(v) for v in os.environ.get('QF_P3_FRONT_ZB', '0.10,0.30').split(','))
QF_P3_FRONT_S0 = float(os.environ.get('QF_P3_FRONT_S0', '0.30'))
QF_P3_FRONT_UK = tuple(float(v) for v in os.environ.get('QF_P3_FRONT_UK', '-2.40,-2.00').split(','))
QF_P3_FRONT_DU = float(os.environ.get('QF_P3_FRONT_DU', '0.08'))
_P3_HIP = {}


def _p3_hip_tables():
    if not _P3_HIP:
        k = np.array(QF_P3_HIP_A)
        _P3_HIP['A'] = (D.Spline1D(k[:, 0], k[:, 1], 'clamped', 0.0, 0.0), k[0, 0], k[-1, 0])
        k = np.array(QF_P3_FRONT_A)
        _P3_HIP['AF'] = (D.Spline1D(k[:, 0], k[:, 1], 'natural'), k[0, 0], k[-1, 0])
        for n in ('L', 'rail', 'U'):
            xs = np.linspace(C[n].x0, C[n].x1, 600)
            P = np.asarray(C[n].at(xs))
            _P3_HIP[n] = _tab(xs, P[:, 2])                             # heights tabulated once (evaluating the curves per vertex is slow) and joined by C2 splines
            _P3_HIP[n + 'y'] = _tab(xs, P[:, 1])
    return _P3_HIP


def _tab(xs, v):
    sp = D.Spline1D(xs, v, 'natural')
    return lambda x: float(sp(min(max(x, xs[0]), xs[-1])))


def p3_front_dy(x, y, z):
    T = _p3_hip_tables()
    s, a, b = T['AF']
    if x <= a or x >= b or abs(y) < 0.30:
        return 0.0
    A = 0.01 * max(0.0, float(s(x))) * float(D.sstep(QF_P3_FRONT_RISE[0], QF_P3_FRONT_RISE[1], x)) * (1.0 - float(D.sstep(QF_P3_FRONT_END[0], QF_P3_FRONT_END[1], x)))
    if A <= 0.0:
        return 0.0
    ay = abs(y)
    yl, zl = T['Ly'](x), T['L'](x)
    if z <= zl:
        g = float(D.sstep(QF_P3_FRONT_ZB[0], QF_P3_FRONT_ZB[1], z))
    else:
        yu, zu = T['Uy'](x), T['U'](x)
        r, d = max(math.hypot(yu - yl, zu - zl), 1e-3), math.hypot(ay - yl, z - zl)
        k = 1.0 - float(D.sstep(QF_P3_FRONT_UK[0], QF_P3_FRONT_UK[1], x))
        if d <= r:
            g = 1.0 - (1.0 - k) * float(D.sstep(QF_P3_FRONT_S0, 1.0, d / r))
        else:
            g = k * (1.0 - float(D.sstep(0.0, QF_P3_FRONT_DU, d - r)))
    return math.copysign(A * g * float(D.sstep(0.30, 0.50, ay)), y)


def _p3_hip_raw(x, z):
    """the hip displacement (m) at |y| >= 0.5 (w = 1), without the facet blend"""
    T = _p3_hip_tables()
    s, a, b = T['A']
    if x <= a or x >= b:
        return 0.0
    w0, w1, w2, w3 = QF_P3_HIP_W
    A = 0.01 * max(0.0, float(s(x))) * float(D.sstep(w0, w1, x)) * (1.0 - float(D.sstep(w2, w3, x)))
    if A <= 0.0:
        return 0.0
    zl, zr = T['L'](x), T['rail'](x)
    z0 = QF_P3_HIP_Z0
    if z <= z0 or z >= zr:
        return 0.0
    g = float(D.sstep(z0, zl, z)) if z <= zl else (zr - z) / max(zr - zl, 1e-6)
    return A * g


def _p3_facet_aff():
    """(box, coefficients) of the affine fit of the hip over the facet box, or None"""
    if 'aff' not in _P3_HIP:
        _P3_HIP['aff'] = None
        if QF_P3_HIP_FACET != '0':
            bx = tuple(float(v) for v in QF_P3_HIP_FACET.split(','))
            G = [(x, z) for x in np.linspace(bx[0], bx[1], 23) for z in np.linspace(bx[2], bx[3], 15)]
            M = np.array([(1.0, x, z) for x, z in G]); v = np.array([_p3_hip_raw(x, z) for x, z in G])
            _P3_HIP['aff'] = (bx, np.linalg.lstsq(M, v, rcond=None)[0])
    return _P3_HIP['aff']


def p3_hip_dy(x, y, z):
    if abs(y) < 0.30:
        return 0.0
    d = _p3_hip_raw(x, z)
    F = _p3_facet_aff()
    if F is not None:
        (x0, x1, z0, z1), c = F
        m = QF_P3_HIP_FM
        lam = float(D.sstep(x0 - m, x0, x)) * (1.0 - float(D.sstep(x1, x1 + m, x))) * float(D.sstep(z0 - m, z0, z)) * (1.0 - float(D.sstep(z1, z1 + m, z)))
        if lam > 0.0:
            d += lam * (c[0] + c[1] * x + c[2] * z - d)
    return math.copysign(d * float(D.sstep(0.30, 0.50, abs(y))), y)


# QF_P3_TAILX=1: the rear end is QF_P3_TX_S (m) longer (CALIB.md phase 3, "rear deck"): p013's tail edge (+5.3 cm median over the width), the rear window's rear edge (+4.8), the rear
# window corner P3 (+4.9), the facet's front seam (+4.5..5.0) and rear edge (+5..6) and the tail lamp bar all sit further aft in the calibrated photos, while the window tip WT, the rear
# arch (round the fixed hub) and the hips do not.  A field of x displacement, applied to the whole built car at export (build_game_car.p3_post: every mesh but the wheels; the wing node
# moves rigidly), so that the regions' parts go with the shell.  s = S ((1 - b) Rs + b Rd):
#   Rs  the side: a ramp in the slanted coordinate xi = x + K (Zs(z) - QF_P3_TX_Z0) whose level lines are parallel to the facet's front seam (S -> E, dx/dz = -K), from xi1 - W to
#       xi1 (= the seam): the facet and everything aft of it move rigidly by S (the facet stays planar), the stretch lies in the band between the rear arch and the seam (the arch
#       circle and the wheel well stay where they are); Zs = z clamped (C2) to QF_P3_TX_ZC so that the band runs straight down behind the arch and stops tilting above the deck.
#   Rd  the deck / glass: a ramp in x over QF_P3_TX_XD (window tip -> the rear window's rear edge): the rear window gets longer, the deck behind it moves by S.
#   b   0 at and below L, 1 inboard of the roof rail / crest (the lateral position across the rear shoulder from L to the rail), so the rear shoulder blends the two.
#   ramps: linear in their middle, C2 ends (the integral of a smoothstep window, QF_P3_TX_E of the width at each end).
QF_P3_TAILX = os.environ.get('QF_P3_TAILX', '0') == '1'
QF_P3_TX_S = float(os.environ.get('QF_P3_TX_S', '0.05'))
QF_P3_TX_K, QF_P3_TX_Z0, QF_P3_TX_XI1, QF_P3_TX_W = 0.714, 0.733, 2.149, float(os.environ.get('QF_P3_TX_W', '0.20'))
QF_P3_TX_ZC = tuple(float(v) for v in os.environ.get('QF_P3_TX_ZC', '0.50,1.10,0.06').split(','))      # z clamp: low, high, rounding
QF_P3_TX_XD = tuple(float(v) for v in os.environ.get('QF_P3_TX_XD', '1.22,2.10').split(','))
QF_P3_TX_E = float(os.environ.get('QF_P3_TX_E', '0.25'))


def _p3_ramp(t, e):
    """0 for t <= 0, 1 for t >= 1, linear over [e, 1 - e]; C3 (the integral of a C2 window of smoothsteps), normalised"""
    def I(v):                                   # integral of the quintic smoothstep from 0 to v
        return v ** 6 - 3.0 * v ** 5 + 2.5 * v ** 4
    if t <= 0.0:
        return 0.0
    if t >= 1.0:
        return 1.0
    if t < e:
        w = e * I(t / e)
    elif t <= 1.0 - e:
        w = 0.5 * e + (t - e)
    else:
        v = (t - (1.0 - e)) / e
        w = 0.5 * e + (1.0 - 2.0 * e) + e * (v - I(v))
    return w / (1.0 - e)


def _p3_zclamp(z):
    lo, hi, r = QF_P3_TX_ZC
    wd = hi - lo + 2.0 * r
    e = r / wd
    return lo - 0.5 * r + _p3_ramp((z - (lo - r)) / wd, e) * (1.0 - e) * wd


def p3_dx(x, y, z):
    """x displacement (m) of the rear-end extension at (x, y, z) (0 when QF_P3_TAILX is off)"""
    if not QF_P3_TAILX or x < QF_P3_TX_XD[0] - 0.05:
        return 0.0
    T = _p3_hip_tables()
    xi = x + QF_P3_TX_K * (_p3_zclamp(z) - QF_P3_TX_Z0)
    rs = _p3_ramp((xi - (QF_P3_TX_XI1 - QF_P3_TX_W)) / QF_P3_TX_W, QF_P3_TX_E)
    rd = _p3_ramp((x - QF_P3_TX_XD[0]) / (QF_P3_TX_XD[1] - QF_P3_TX_XD[0]), QF_P3_TX_E)
    if rs == rd:
        return QF_P3_TX_S * rs
    xl = min(x, 2.41)
    yl, zl, yr = T['Ly'](xl), T['L'](xl), T['raily'](xl)
    bz = float(D.sstep(zl - 0.01, zl + 0.03, z))
    by = float(D.sstep(0.0, 1.0, (yl - abs(y)) / max(yl - yr, 1e-3))) if bz > 0.0 else 0.0
    b = by * bz
    return QF_P3_TX_S * ((1.0 - b) * rs + b * rd)


def p3_dy(x, y, z):
    return (p3_hip_dy(x, y, z) if QF_P3_HIP else 0.0) + (p3_front_dy(x, y, z) if QF_P3_FRONT else 0.0)


def p3_morph(pm):
    if not (QF_P3_HIP or QF_P3_FRONT):
        return
    for i, v in enumerate(pm.verts):
        d = p3_dy(float(v[0]), float(v[1]), float(v[2]))
        if d:
            pm.verts[i] = (v[0], float(v[1]) + d, v[2]) + tuple(v[3:])
    if getattr(pm, 'rows', None) is not None:
        rows = []
        for r in pm.rows:
            r = np.array(r, float)
            for k in range(len(r)):
                r[k, 1] += p3_dy(r[k, 0], r[k, 1], r[k, 2])
            rows.append(r)
        pm.rows = rows


def build_panels(only=None):
    R = Registry()
    out = {}
    for P in PANEL_LIST:
        if only and P.name not in only:
            continue
        R.cur = P
        pm = P.fn(R)
        R.cur = None
        if P.name in ('wall', 'shoulder'):
            qf_fill(pm)
        p3_morph(pm)
        orient(pm, P)
        out[P.name] = pm
    return out, R


def panel_report(panels=None):
    panels = panels or build_panels()[0]
    lock = json.load(open(LOCK_FILE))['panels'] if os.path.exists(LOCK_FILE) else {}
    rep = {}
    for n, pm in panels.items():
        c = checksum(pm)
        rep[n] = dict(sha=c, verts=len(pm.verts), faces=len(pm.faces), locked=n in lock, changed=(n in lock and lock[n]['sha'] != c))
    return rep


def check_lock(panels=None, unlock=()):
    """fail loudly when a locked panel changed (unless unlocked for this round)"""
    unlock = set(unlock) | set(u for u in os.environ.get('SHELL_UNLOCK', '').split(',') if u)
    rep = panel_report(panels)
    bad = [n for n, r in rep.items() if r['changed'] and n not in unlock]
    if bad:
        raise SystemExit('SHELL LOCK VIOLATED: locked panel(s) changed: ' + ', '.join(bad) + '  (unlock them for this round with --unlock / SHELL_UNLOCK, or restore the curves)')
    return rep


def write_lock(names, panels=None):
    panels = panels or build_panels()[0]
    lock = json.load(open(LOCK_FILE)) if os.path.exists(LOCK_FILE) else {'version': 1, 'panels': {}}
    for n in names:
        lock['panels'][n] = dict(sha=checksum(panels[n]), verts=len(panels[n].verts), faces=len(panels[n].faces))
    json.dump(lock, open(LOCK_FILE, 'w'), indent=1)
    return lock


# ----------------------------------------------------------------------------- assembly (mirror + weld)
def assemble(panels):
    key = lambda p: (round(p[0] * 1e6), round(p[1] * 1e6), round(p[2] * 1e6))
    vid, V, F, M, PID = {}, [], [], [], []
    names = list(panels.keys())
    for pi, name in enumerate(names):
        pm = panels[name]
        for side in (1, -1):
            loc = []
            for p in pm.verts:
                q = (p[0], side * p[1], p[2])
                k = key(q)
                if k not in vid:
                    vid[k] = len(V)
                    V.append(q)
                loc.append(vid[k])
            for f in pm.faces:
                g = [loc[i] for i in f]
                if side < 0:
                    g = g[::-1]
                u = []
                for v in g:
                    if v not in u:
                        u.append(v)
                if len(u) < 3:
                    continue
                F.append(tuple(u)); M.append(pm.mat); PID.append(pi)
    return np.array(V), F, M, PID, names


def mesh_checks(V, F):
    """open (boundary) edges, non-manifold edges, inconsistent windings"""
    use = {}
    for f in F:
        for a, b in zip(f, f[1:] + f[:1]):
            use.setdefault((a, b), 0)
            use[(a, b)] += 1
    und = {}
    for (a, b), n in use.items():
        k = (min(a, b), max(a, b))
        und.setdefault(k, []).append((a, b, n))
    open_e = [k for k, v in und.items() if len(v) == 1]
    nonman = [k for k, v in und.items() if sum(t[2] for t in v) > 2]
    bad_wind = [k for k, v in und.items() if len(v) == 2 and v[0][:2] == v[1][:2]] + [k for k, v in und.items() if len(v) == 1 and v[0][2] > 1]
    return open_e, nonman, bad_wind


# ----------------------------------------------------------------------------- Blender object, fillets, helpers used by build_game_car.py
FILLET = 0.008          # one consistent small fillet on every crease (m)


def to_bpy(V, F, M, PID, names, name='Shell'):
    import bpy
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(map(float, v)) for v in V], [], [list(f) for f in F])
    me.update()
    for i, p in enumerate(me.polygons):
        p.material_index = M[i]
        p.use_smooth = True
    at = me.attributes.new('panel', 'INT', 'FACE')
    at.data.foreach_set('value', PID)
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ob['panel_names'] = list(names)
    return ob


# rearcrease: pairs that get their own, wider roll instead of the 8 mm fillet: pair -> (offset, segments).  EMPTY: a 45 mm roll on the black lower rear corner (tail_lower | wall_black) was tried for the white hairline on
# that corner in p018 and changed nothing: the hairline is not the shell (the bare shell renders without it), it is the diffuser endplate of the REAR region (regions/rear.py build_endplates)
WIDE_FILLET = {}


def bevel_creases(ob, offset=FILLET, segments=2, min_angle=3.0):
    """ONE small fillet on every crease = every boundary between two panels (except the SMOOTH_PAIRS) whose faces turn by more than min_angle degrees (WIDE_FILLET pairs: their own, wider roll)"""
    import bpy, bmesh
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    lay = bm.faces.layers.int.get('panel')
    names = list(ob['panel_names'])
    edges, wide = [], {}
    for e in bm.edges:
        if len(e.link_faces) != 2:
            continue
        f0, f1 = e.link_faces
        p0, p1 = f0[lay], f1[lay]
        if p0 == p1 or frozenset((names[p0], names[p1])) in SMOOTH_PAIRS:
            continue
        pair = frozenset((names[p0], names[p1]))
        if e.calc_face_angle(0.0) < math.radians(0.5 if pair in FORCE_FILLET else PAIR_MIN_ANGLE.get(pair, min_angle)):
            continue
        if pair in WIDE_FILLET:
            wide.setdefault(pair, []).append(e)
        else:
            edges.append(e)
    n = len(edges) + sum(len(v) for v in wide.values())

    def run(geom, off, seg):
        res = bmesh.ops.bevel(bm, geom=geom, offset=off, offset_type='OFFSET', segments=seg, profile=0.5, affect='EDGES', clamp_overlap=True,
                              loop_slide=True, mark_seam=False, mark_sharp=False, material=-1, harden_normals=False)
        for f in res['faces']:                   # bevel faces: the 'frame' material of the two neighbours (Paint < Glass < Trim)
            ms = {n.material_index for e in f.edges for n in e.link_faces if n is not f and n.is_valid}
            f.material_index = 0 if ms <= {0, 1} else 2 if 2 in ms else min(ms) if ms else 0
            f.smooth = True
    for pair, es in wide.items():                # the wide rolls first (their ends run into the 8 mm fillets' edges, which are bevelled next)
        run(es, *WIDE_FILLET[pair])
    run([e for e in edges if e.is_valid], offset, segments)
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()
    return n


def build_shell2(bevel=True, check=True, unlock=()):
    panels, R = build_panels()
    rep = check_lock(panels, unlock) if check else panel_report(panels)
    V, F, M, PID, names = assemble(panels)
    oe, nm, bw = mesh_checks(V, F)
    ob = to_bpy(V, F, M, PID, names)
    nb = bevel_creases(ob) if bevel else 0
    return ob, dict(report=rep, open_edges=len(oe), nonmanifold=len(nm), bad_winding=len(bw), beveled=nb, panels=names)


def glass_half_width(x):
    """y of the glass edge (the foot of the ridge's inner wall) at station x"""
    return float(C['gedge'].at(max(float(x), -1.625))[1])


def feature_lines():
    """polylines (both sides) of the feature curves for lines_overlay.py"""
    out = {}
    col = {'U': [1, 0.3, 0.3], 'L': [0, 1, 1], 'L5': [0, 1, 0], 'cowl_diag': [0, 1, 0], 'rail': [1, 1, 0], 'wl': [1, 0.6, 0], 'gedge': [1, 0, 1], 'top': [1, 1, 1],
           'l3': [1, 0, 1], 'sill': [0.6, 0.6, 1]}
    R = Registry()
    for k, rgb in col.items():
        P = R._edge(k) if k in EDGES else C[k].at(np.linspace(C[k].x0, C[k].x1, 160))
        for sd in (1, -1):
            out[f'{k}_{sd}'] = {'pts': [[float(p[0]), sd * float(p[1]), float(p[2])] for p in P], 'col': rgb}
    return out


# ----------------------------------------------------------------------------- wheel arches (cut from the dense mesh) + tubs: as shell.py, with the new L curve
# q5 (coordinator): the front arch's cut edge gets a 3 .. 5 mm fillet in PAINT (the photos: a thin bright rim round a black well); the tunnel ring behind it stays black (Trim).  The cut leaves a KNIFE EDGE there
# (above the arch top the panel is only ~30 .. 40 deg off the horizontal, the well wall is the cylinder: wedge angle 30 .. 90 deg), and the dense mesh has sliver triangles at the cut (edges of 0.1 mm), so the generic bevel
# collapses or spikes (tested).  The fillet is built directly instead: the paint is cut at the outline Rw(phi) + QF_AR_D (that is where the paint ends and the roll starts, a radial QF_AR_D above the well wall), the apex
# of the wedge A (the paint tangent line meets the well wall) is found from the paint's own surface normal there, and a circle tangent to both the paint line and the well wall's line (equal tangent lengths
# lam = QF_AR_D / sin(wedge angle): 3 .. 4 mm at the arch top, 2 .. 4 mm at the steeper parts) is sampled in QF_AR_SEG steps (the step stays under the 30 deg of build_game_car.mark_sharp, so the roll shades as one
# smooth rim).  The tunnel then hangs on the roll's other end C (on the well wall).  FRONT arches only (the rear arch and everything else is unchanged).  QF_AR_ON=0 gives the old sharp cut.
QF_AR_ON = os.environ.get('QF_AR_ON', '1') == '1'
QF_AR_D = float(os.environ.get('QF_AR_D', '0.002'))
QF_AR_SEG = int(os.environ.get('QF_AR_SEG', '6'))
QF_AR_MERGE = float(os.environ.get('QF_AR_MERGE', '0.002'))

# q5 (coordinator, 2026-10-20): the FRONT arch outline.  The paint edge over the wheel sits BELOW the model's arch circle (R_ARCH 0.415 round the hub): p018 (a pure side view: the row of the
# paint -> black transition is the height, whatever the lateral position) puts it 43 mm lower at the top (z 0.762 at the hub, radius 0.372 from 74 to 111 deg), 20 .. 30 mm lower on the front shoulder, and back on the circle
# at the bottom of the front edge (175 deg); aft of the hub the side marker hides the photo edge, the table lets it rejoin the circle at ~30 deg.  QF_AZ_K = (angle round the hub in deg (0 = aft, 90 = up, 180 = forward), depth
# below the circle in mm), joined by a monotone cubic (C1: one smooth outline, no kink where it rejoins the circle); the well wall (tunnel, black) follows it.  QF_AZ_S scales the depths (0 = the old circle).
QF_AZ_ON = os.environ.get('QF_AZ_ON', '1') == '1'      # q5c: ON again (coordinator 2026-10-21: the lowered arch top follows from the middle face B being one smooth face down to the photo's L)
QF_AZ_S = float(os.environ.get('QF_AZ_S', '1.0'))
QF_TUN_ON = os.environ.get('QF_TUN_ON', '1') == '1'    # q5c: the well roof opens up behind the lowered paint edge so the tyre does not poke through it
QF_TUN_R = float(os.environ.get('QF_TUN_R', '0.410'))   # radius of the well roof (tyre 0.39 + 20 mm)
QF_TUN_K = float(os.environ.get('QF_TUN_K', '1.3'))      # slope of the roof cone behind the paint edge (inboard mm per mm of radius; the skin itself runs at ~1.0, 1.3 keeps the cone inside it)
QF_TUN_YIN = float(os.environ.get('QF_TUN_YIN', '0.62'))  # |y| of the inboard end of the front wells (was Y_TUB 0.70: the turned tyre's inboard front shoulder reached |y| 0.65 and went through the cap)
QF_AZ_K = ((-60.0, 0.0), (28.0, 0.0), (45.0, 9.0), (60.0, 27.0), (74.0, 41.0), (86.0, 44.0), (98.0, 43.0), (110.0, 40.0), (122.0, 31.0), (135.0, 24.0), (150.0, 16.0), (163.0, 7.0), (176.0, 0.0), (260.0, 0.0))


def _pchip(xs, ys):
    """monotone piecewise cubic Hermite interpolant (Fritsch-Carlson): C1, no overshoot"""
    n = len(xs)
    h = [xs[i + 1] - xs[i] for i in range(n - 1)]
    d = [(ys[i + 1] - ys[i]) / h[i] for i in range(n - 1)]
    m = [0.0] * n
    for i in range(1, n - 1):
        if d[i - 1] * d[i] > 0.0:
            w1, w2 = 2.0 * h[i] + h[i - 1], h[i] + 2.0 * h[i - 1]
            m[i] = (w1 + w2) / (w1 / d[i - 1] + w2 / d[i])
    m[0], m[-1] = 0.0, 0.0

    def f(x):
        if x <= xs[0]:
            return ys[0]
        if x >= xs[-1]:
            return ys[-1]
        i = max(k for k in range(n - 1) if xs[k] <= x)
        t = (x - xs[i]) / h[i]
        t2, t3 = t * t, t * t * t
        return (2 * t3 - 3 * t2 + 1) * ys[i] + (t3 - 2 * t2 + t) * h[i] * m[i] + (-2 * t3 + 3 * t2) * ys[i + 1] + (t3 - t2) * h[i] * m[i + 1]
    return f


if D.QF_C11_ON and D.QF_C11_AZD != 0.0:    # c11: the wider c9c fade band pulls the wall in front of the arch ~0.4 mm inboard at the tyre's tightest steered point (phi 165); the rim moves back by this (QF_C11_AZD mm at the 163 deg knot)
    QF_AZ_K = tuple((a, d - D.QF_C11_AZD) if a == 163.0 else (a, d) for a, d in QF_AZ_K)
_AZ_F = _pchip([k[0] for k in QF_AZ_K], [k[1] for k in QF_AZ_K])


# P3 (reconstruction phase 3, 2026-10-25): the REAR arch outline.  The arch lip fitted from p018 + p001 (calib/lines fit.json arch_R, sigma 1-4 mm) lies OUTSIDE the R_ARCH circle round the rear hub:
# +27 mm at 40 deg (its lowest fitted point aft of the hub), +5..7 mm just behind the top (63-78 deg), +12..14 mm from 85 to 136 deg, +10 mm at 148 deg.  QF_P3_ARR_K = (angle in deg as
# qf_az_depth, mm outside the circle): consecutive knots are joined by quintic smoothsteps (slope and 2nd derivative 0 at every knot: the outline is C2 and never overshoots the
# knots), held at the end values beyond them; within 2 mm of every fitted point.  The well wall follows the cut (it is extruded from the cut ring).
QF_P3_ARR = os.environ.get('QF_P3_ARR', '1') == '1'
QF_P3_ARR_K = tuple(tuple(float(u) for u in kv.split(':')) for kv in os.environ.get('QF_P3_ARR_K', '38:27,66:5.5,94:13,128:13,150:10').split(','))


def _arr_mm(p):
    K = QF_P3_ARR_K
    if p <= K[0][0]:
        return K[0][1]
    for (a0, v0), (a1, v1) in zip(K, K[1:]):
        if p <= a1:
            return v0 + (v1 - v0) * float(D.sstep(a0, a1, p))
    return K[-1][1]


def p3_arr(phi_deg):
    """how far (m) the rear arch outline lies outside the R_ARCH circle at the angle phi (deg, as qf_az_depth)"""
    p = phi_deg + 360.0 if phi_deg < -90.0 else phi_deg
    return 1e-3 * _arr_mm(p) if QF_P3_ARR else 0.0


def qf_az_depth(phi_deg):
    """depth (m) of the front arch outline below the circle at the angle phi (deg, atan2(z - hub, x - hub), the bottom part of the front edge counted as +180 .. +270)"""
    p = phi_deg + 360.0 if phi_deg < -90.0 else phi_deg
    return 1e-3 * QF_AZ_S * _AZ_F(p)


def _arch_rim(bm, arc, xh, sg, hub_z, Rw, Rc, nseg, info=None):
    """roll the cut edge `arc` (boundary verts on the outline Rc(phi) round (xh, hub_z), sorted by angle) down to the well wall (outline Rw(phi)): returns (ring of verts the tunnel hangs on, the roll's faces)"""
    from mathutils import Vector
    bm.normal_update()
    K = len(arc)
    pos = [Vector(v.co) for v in arc]
    runs, cur = [], [0]
    for k in range(1, K):                                     # runs of the arc (the tunnel skips a gap > 0.2 as well)
        if (pos[k] - pos[k - 1]).length > 0.2:
            runs.append(cur)
            cur = []
        cur.append(k)
    runs.append(cur)
    t = Vector((0.0, -sg, 0.0))
    P, NN = [], []
    for k, v in enumerate(arc):
        phi = math.atan2(pos[k].z - hub_z, pos[k].x - xh)
        r, s = Vector((math.cos(phi), 0.0, math.sin(phi))), Vector((-math.sin(phi), 0.0, math.cos(phi)))
        h = 1e-3
        dR = (Rc(phi + h) - Rc(phi - h)) / (2.0 * h)          # the outline is not a circle: its tangent / outward normal in the xz plane
        Tn = (r * dR + s * Rc(phi)).normalized()
        Nn = (r * Rc(phi) - s * dR).normalized()
        n = Vector((0.0, 0.0, 0.0))
        for f in v.link_faces:
            n += f.normal * f.calc_area()
        p = n.cross(Tn) if n.length > 1e-14 else Nn
        p = p.normalized() if p.length > 1e-12 else Nn
        P.append(p if p.dot(Nn) >= 0.0 else -p)
        NN.append(Nn)
    for _ in range(3):                                        # smooth the in-section paint direction along each run
        Q = list(P)
        for run in runs:
            for i, k in enumerate(run):
                if 0 < i < len(run) - 1:
                    q = P[run[i - 1]] + 2.0 * P[k] + P[run[i + 1]]
                    Q[k] = q.normalized() if q.length > 1e-12 else P[k]
        P = Q
    ring, faces, fc = [], [], []
    for k, v in enumerate(arc):
        p = P[k]
        phi = math.atan2(pos[k].z - hub_z, pos[k].x - xh)
        cth = max(-0.985, min(0.985, p.dot(t)))
        th = math.acos(cth)                                   # the wedge angle between the paint (going in) and the well wall (going in)
        lam = (Rc(phi) - Rw(phi)) / max(p.dot(NN[k]), 0.2)
        A = pos[k] - lam * p                                  # apex: the paint line meets the well wall
        pa = math.atan2(A.z - hub_z, A.x - xh)
        rho = math.hypot(A.x - xh, A.z - hub_z)
        A.x, A.z = xh + (A.x - xh) * Rw(pa) / rho, hub_z + (A.z - hub_z) * Rw(pa) / rho
        C = A + lam * t                                       # the well wall's end of the roll
        b = (p + t).normalized()
        cc = A + b * (lam / math.cos(0.5 * th))
        rr = lam * math.tan(0.5 * th)
        up, uc = (pos[k] - cc) / rr, (C - cc) / rr
        om = math.acos(max(-1.0, min(1.0, up.dot(uc))))
        row = [v]
        for j in range(1, nseg):
            u = j / nseg
            w = (up * math.sin((1.0 - u) * om) + uc * math.sin(u * om)) / math.sin(om)
            row.append(bm.verts.new(cc + w * rr))
        row.append(bm.verts.new(C))
        ring.append(row)
        fc.append(cc)
        if info is not None:
            info.append((math.degrees(phi), math.degrees(th), lam, rr))
    for k in range(K - 1):
        if (pos[k] - pos[k + 1]).length > 0.2:
            continue
        for j in range(nseg):
            f = bm.faces.new((ring[k][j], ring[k + 1][j], ring[k + 1][j + 1], ring[k][j + 1]))
            f.material_index = 0
            f.smooth = True
            want = f.calc_center_median() - 0.5 * (fc[k] + fc[k + 1])
            if f.normal.dot(want) < 0:
                f.normal_flip()
            faces.append(f)
    return [row[-1] for row in ring], faces


def cut_arches(ob, lmax=0.028):
    import bpy, bmesh
    from mathutils import Vector
    import common as V1
    HUBS, HUB_Z, R_ARCH, Y_TUB = V1.HUBS, V1.HUB_Z, V1.R_ARCH, V1.Y_TUB
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    Lc = C['L']
    # 2026-10-24: L's height tabulated once (0.5 mm steps, linear interpolation: < 1 micron off) instead of evaluated per vertex: each evaluation runs the whole chain of nose corrections (~55 ms) and near()
    # asks for it for every vertex round the rear arches, which made this step take ~20 minutes
    _lx = np.linspace(Lc.x0, Lc.x1, int(round((Lc.x1 - Lc.x0) / 0.0005)) + 1)
    _lzt = np.asarray(Lc.fz(_lx), float)

    def lz(x):
        return float(np.interp(x, _lx, _lzt))
    for xh, sg in HUBS:
        rim = QF_AR_ON and xh < 0.0 and QF_AR_D > 0.0           # q5: the front arches get the rolled edge (see _arch_rim)
        az = QF_AZ_ON and xh < 0.0                              # q5: ... and the photo outline (QF_AZ_K)
        Rw = (lambda phi: R_ARCH - qf_az_depth(math.degrees(phi))) if az else (lambda phi: R_ARCH + p3_arr(math.degrees(phi))) if xh > 0.0 else (lambda phi: R_ARCH)  # the well wall's outline (rad)
        Rc = (lambda phi: Rw(phi) + QF_AR_D) if rim else Rw                                                  # where the paint is cut
        gp = lambda x, z, xh, Rc=Rc: math.hypot(x - xh, z - HUB_Z) - Rc(math.atan2(z - HUB_Z, x - xh))

        def near(v):
            return (abs(v.co.x - xh) < R_ARCH + 0.12 and v.co.z < HUB_Z + R_ARCH + 0.12 and sg * v.co.y > 0.78 and (-1.84 < v.co.x < -1.0 or v.co.z < lz(v.co.x) - 0.006))
        for _ in range(4):
            es = [e for e in bm.edges if e.calc_length() > lmax and near(e.verts[0]) and near(e.verts[1]) and abs(gp(e.verts[0].co.x, e.verts[0].co.z, xh)) < 0.14]
            if not es:
                break
            bmesh.ops.subdivide_edges(bm, edges=es, cuts=1, use_grid_fill=True)
        new = []
        for e in list(bm.edges):
            v0, v1 = e.verts
            if not (near(v0) and near(v1)):
                continue
            g0, g1 = gp(v0.co.x, v0.co.z, xh), gp(v1.co.x, v1.co.z, xh)
            if g0 * g1 < 0.0:
                _, nv = bmesh.utils.edge_split(e, v0, g0 / (g0 - g1))
                d = Vector((nv.co.x - xh, 0.0, nv.co.z - HUB_Z))
                d.normalize()
                rc = Rc(math.atan2(d.z, d.x))
                nv.co.x, nv.co.z = xh + d.x * rc, HUB_Z + d.z * rc
                new.append(nv)
        bmesh.ops.connect_verts(bm, verts=new)
        dead = []
        for f in bm.faces:
            c = f.calc_center_median()
            if sg * c.y > 0.78 and gp(c.x, c.z, xh) < 0.0:
                dead.append(f)
        bmesh.ops.delete(bm, geom=dead, context='FACES')
        arc = [v for v in bm.verts if v.is_valid and v.is_boundary and abs(gp(v.co.x, v.co.z, xh)) < 2e-5 and sg * v.co.y > 0.78]
        if len(arc) < 4:
            print('ARCH: no arc found for', xh, sg)
            continue

        def ang(v):
            a = math.degrees(math.atan2(v.co.z - HUB_Z, v.co.x - xh))
            return a + 360.0 if a < -90.0 else a
        arc.sort(key=ang)
        cring = arc
        if rim:
            bmesh.ops.remove_doubles(bm, verts=arc, dist=QF_AR_MERGE)       # the cut leaves sliver edges (0.1 mm) on the arc: merge them, so the roll's stations are evenly spaced
            arc = [v for v in arc if v.is_valid]
            arc.sort(key=ang)
            cring = arc
            rim_info = []
            cring, _rf = _arch_rim(bm, arc, xh, sg, HUB_Z, Rw, Rc, QF_AR_SEG, rim_info)
            if os.environ.get('QF_AR_LOG'):
                print('ARCH RIM', xh, sg, 'stations', len(arc))
                for i in range(0, len(rim_info), 6):
                    print('   phi %7.1f  wedge %6.1f deg  tangent %.2f mm  radius %.2f mm' % (rim_info[i][0], rim_info[i][1], rim_info[i][2] * 1e3, rim_info[i][3] * 1e3))
        yin = sg * (QF_TUN_YIN if (az and QF_TUN_ON) else Y_TUB)
        # q5c tunnel clearance: the lowered outline (QF_AZ) pulled the well wall (a straight extrusion of the rim ring along y) to a radius of 0.371 over the top of the wheel, i.e. 19 mm inside the tyre (R 0.39).
        # Behind the paint edge the well roof now follows the underside of the skin (the B face slopes outward ~45 deg towards the lowered edge: radius +1 mm per 1/QF_TUN_K mm inboard) up to QF_TUN_R and runs on
        # at that radius to the inboard end: the roof stays inside the skin (no black poking through the paint) and the tread has >= 7 mm at full steering lock.  Where the rim is already wider, nothing changes.
        Rt = QF_TUN_R if (az and QF_TUN_ON) else 0.0
        chains = []                                                 # per rim station: [rim, B (where the roof reaches its radius), C (inboard end)]
        for v in cring:
            dx, dz = v.co.x - xh, v.co.z - HUB_Z
            rho = math.hypot(dx, dz)
            if Rt > rho + 5e-4:
                s_ = Rt / rho
                B = bm.verts.new((xh + dx * s_, v.co.y - sg * (Rt - rho) * QF_TUN_K, HUB_Z + dz * s_))
                Cn = bm.verts.new((xh + dx * s_, yin, HUB_Z + dz * s_))
            else:
                B = v
                Cn = bm.verts.new((v.co.x, yin, v.co.z))
            chains.append([v, B, Cn])
        inner = [ch[2] for ch in chains]
        cen = bm.verts.new((xh, yin, HUB_Z))
        fs = []

        def _face(vs):
            u = []
            for w in vs:
                if not u or u[-1] is not w:
                    u.append(w)
            while len(u) > 1 and u[0] is u[-1]:
                u.pop()
            if len(u) >= 3:
                fs.append(bm.faces.new(u))
        for k in range(len(arc) - 1):
            a, b = cring[k], cring[k + 1]
            if (a.co - b.co).length > 0.2:
                continue
            ca, cb = chains[k], chains[k + 1]
            for j in range(2):                                      # skin-underside cone, well wall (a part that is not there collapses away)
                _face((ca[j], cb[j], cb[j + 1], ca[j + 1]))
            fs.append(bm.faces.new((cen, inner[k], inner[k + 1])))
        fs.append(bm.faces.new((cen, inner[-1], inner[0])))
        for f in fs:
            f.material_index = 2
            f.smooth = True
            c = f.calc_center_median()
            ys = [v.co.y for v in f.verts]
            if len(f.verts) == 3 and any(v is cen for v in f.verts):
                want = Vector((0.0, sg, 0.0))
            else:
                want = Vector((xh - c.x, 0.0, HUB_Z - c.z))
            if f.normal.dot(want) < 0:
                f.normal_flip()
        for k in range(len(arc) - 1):
            e = bm.edges.get((cring[k], cring[k + 1]))
            if e is not None:
                e.smooth = False
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()


def cut_intake(ob):
    import common as V1
    return V1.cut_intake(ob)


def add_floor(ob, z=0.188):
    """flat black underbody between the sills (hidden from every game camera, but closes the shell); the sill curve is the shell's own."""
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    R = Registry()
    s = R._edge('sill')
    x0, x1 = float(s[0][0]), float(s[-1][0])
    xs = list(np.arange(x0 + 0.01, x1 - 0.1, 0.15)) + [x1 - 0.02]
    rows = []
    for x in xs:
        y = max(0.0, float(C['sill'].at(min(max(x, C['sill'].x0), C['sill'].x1))[1]) - 0.012)
        rows.append([bm.verts.new((x, -y, z)), bm.verts.new((x, 0.0, z)), bm.verts.new((x, y, z))])
    for a, b in zip(rows, rows[1:]):
        for j in range(2):
            f = bm.faces.new((a[j], a[j + 1], b[j + 1], b[j]))
            f.material_index = TRIM
            if f.normal.z > 0:
                f.normal_flip()
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()


if __name__ == '__main__':
    import time
    t0 = time.time()
    panels, R = build_panels()
    print('panels built in %.1f s' % (time.time() - t0))
    for n, pm in panels.items():
        print(f'{n:14s} verts {len(pm.verts):6d} faces {len(pm.faces):6d} mat {pm.mat}')
    V, F, M, PID, names = assemble(panels)
    print('assembled verts', len(V), 'faces', len(F), 'tris', sum(len(f) - 2 for f in F))
    oe, nm, bw = mesh_checks(V, F)
    print('open edges', len(oe), 'non-manifold', len(nm), 'bad winding', len(bw))
    if oe:
        P = np.array([(V[a] + V[b]) / 2 for a, b in oe])
        print(' open edge extents x', P[:, 0].min().round(2), P[:, 0].max().round(2), 'y', P[:, 1].min().round(2), P[:, 1].max().round(2), 'z', P[:, 2].min().round(2), P[:, 2].max().round(2))
