"""
The design of the panel shell (R1c): key points and the fair feature curves (numpy only; no bpy).  Everything in shell2.py is built from this registry.

Frame: Blender car frame, x aft, y lateral (right half y >= 0 is built, the left one is its mirror), z up, metres.

Two side lines that never merge (user correction, R1c):
  U  the fender crest / beltline: nose corner N -> ONE arch over the front wheel (top silhouette of the fender volume in 018) -> the A-pillar base (the glass corner) ->
     WITHOUT a kink the lower edge of the side glass (L2) -> window tip.
  L  the body character line: nose corner N -> ONE gentle, nearly straight rising curve; the front wheel opening cuts it, it reappears behind the wheel at the
     side-marker blade and runs along the door top to the tail-lip corner; front and rear parts lie on ONE fair curve.
Between them: the fender volume (a lens from N to the pillar base) that continues behind the wheel as the shoulder band (L2 - L), widening rearward.
"""
import math
import os
import numpy as np
from curves2 import Spline1D, BFit1D, Line1D, XCurve, line3, spline3, fit3, curvature_report

# ----------------------------------------------------------------------------- helpers
def pchip(pts, x):
    pts = [tuple(p) for p in pts]
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
            return ((2 * t3 - 3 * t2 + 1) * pts[i][1] + (t3 - 2 * t2 + t) * h[i] * m[i] + (-2 * t3 + 3 * t2) * pts[i + 1][1] + (t3 - t2) * h[i] * m[i + 1])
    return pts[-1][1]


def dense(knots_yz, x0, x1, n=60):
    """dense (x, y, z) samples of pchip'd (x, y, z) knots, to be fitted by a few-control-point B-spline"""
    k = np.asarray(knots_yz, float)
    xs = np.linspace(x0, x1, n)
    return np.stack([xs, [pchip(list(zip(k[:, 0], k[:, 1])), x) for x in xs], [pchip(list(zip(k[:, 0], k[:, 2])), x) for x in xs]], 1)


def sstep(a, b, x):
    t = np.clip((np.asarray(x, float) - a) / (b - a), 0, 1)
    return t * t * t * (t * (6 * t - 15) + 10)


# ----------------------------------------------------------------------------- key points (right half)
# R1e2: the nose corner N moves aft along the hood plane (the bowed front edge ends there): p013 puts the end of the bowed edge / the start of the corner at x -2.32, p018 sees the bowed
# CENTRE of the edge further forward.  N_OLD is the R1c / R1e corner: every legacy curve below (L, U, l3, sill knots) is still defined from it and is then modified near the nose (build_all).
N_OLD = (-2.39, 0.670, 0.545)
NOSE_XN = float(os.environ.get('NOSE_XN', '-2.46'))
NOSE_ZN = float(os.environ.get('NOSE_ZN', '0.541'))      # R1e3: the corner's height is the light bar's (p016 bar fit, R1e2: 0.566); it is no longer on the old hood plane when N moves forward.
#   2026-10-24 (user: the real car's front is more nose-down): 0.566 -> 0.541.  p018's silhouette (the primary height reference) has the crest 7 px = 2.5 cm lower than the model's at x -2.40, 2.2 / 1.8 / 1.1 /
#   0.4 cm at -2.31 / -2.22 / -2.13 / -2.04, 0 by -1.95 and 0.4 - 0.7 cm HIGHER over -1.9 .. -1.5; the crest as rebuilt on the lower N (zfix, tilt, flap plane) is 2.1 / 1.6 / 1.2 / 0.7 / 0.3 cm lower there and
#   0.4 - 0.5 cm higher at -1.9 .. -1.7 (within 0.6 cm everywhere).  p016's gloss band under the bar is ~15 % shorter than the model's, which the lower bar also gives (its lower edge stays at z 0.428)
N = (NOSE_XN, 0.670, NOSE_ZN)      # nose corner: end of the bowed front edge / light bar; U, L, L5, the corner edge E start here
PILL_FOLLOW = float(os.environ.get('PILL_FOLLOW', '0.65'))   # (see build_all: how much of the foot point's move the straight pillar line follows)
W_DZ = float(os.environ.get('W_DZ', '-0.030'))   # apillar round: the cowl corner is LOWERED by this much (m, negative = down); the hood is a recessed plane and the top face must lean up all the way to the window
W = (-1.625, 0.547, 0.870 + W_DZ)          # cowl corner (end of L5)
import os
U_TIP_BLEND, U_TIP_LEN = 1.0, float(os.environ.get('U_TIP_LEN', '0.40'))      # how far the beltline's arrival at the window tip is moved into the rear shoulder's tangent plane / over which length (m)
XB0, XB1 = -0.62, -0.18                       # the roof header: the A-pillar line is rounded over into the roof rail between these x
A_IN = (-1.43, 0.890, 0.887)               # A-pillar base, inner edge (the windscreen's lower side corner)
PILL_W, PILL_DZ = 0.035, -0.012            # pillar strip: outer edge = inner edge + (0, 0.035, -0.012) at the foot ...
T = (-0.40, 0.655, 1.283)                  # A-pillar top (it continues as the roof rail)
T_DZ = -0.022                              # ... and -0.022 at the top (the door-glass bevel under the roof rail)
A_OUT = (A_IN[0], A_IN[1] + PILL_W, A_IN[2] + PILL_DZ)
T_OUT = (T[0], T[1] + PILL_W, T[2] + T_DZ)
HC = (-2.48, 0.0, 0.507)                   # leading edge, centre (R1c value; build_nose() replaces it with the straight front edge's centre)
HOOD_B = 0.4248                            # hood plane z = 0.545 + b (x + 2.39)
X_DOOR = -1.0                              # door front cut (a seam, no crease)
X_B, X_TIP = 0.65, 1.20                    # B pillar (the lens' upper edge leaves the rail), window tip
TIP_F = 0.77                               # the window tip lies at this fraction of the rung L -> rail at x = X_TIP
# --- q4-rear (QR_*): window-lower line U (x >= QR_U_X0) = ONE smooth design function (ramp -> straight cruise -> hook); the roof rail from QR_ROOF_X0 to the window tip = a quintic that
# arrives at C0 with the slope of the straight crest R-1 (G2: curvature 0); C0 slides along the rung L -> T towards T (T stays) so that the crest/roofline follow the photo
QR_ON = int(os.environ.get('QR_ON', '1'))
QR_U_X0 = float(os.environ.get('QR_U_X0', '-0.60'))      # U: splice with the traced fit (C2)
QR_U_S1 = float(os.environ.get('QR_U_S1', '0.14'))       # U: cruise slope dz/dx
QR_U_WR = float(os.environ.get('QR_U_WR', '0.40'))       # U: length over which the slope goes from the traced one to the cruise slope (smootherstep)
QR_U_XH = float(os.environ.get('QR_U_XH', '0.84'))       # U: the hook (a quintic in z from the cruise line to the window tip) starts here
QR_U_STIP = float(os.environ.get('QR_U_STIP', '0.52'))   # U: slope dz/dx at the window tip (the in-plane tangent that has it fixes the plan slope there)
QR_U_X1 = float(os.environ.get('QR_U_X1', '0.65'))      # U: the plan (y) arc to the tip starts here (a quintic; its end curvature is the one that keeps y' monotone with the smallest peak curvature unless QR_U_YAT is given)
QR_U_YAT = os.environ.get('QR_U_YAT', 'auto')
QR_U_ZH = os.environ.get('QR_U_ZH', 'q')                 # hook in z: 'q' quintic (tip slope QR_U_STIP) or 's' smootherstep slope (the tip slope follows from the tip height)
QR_U_YA = os.environ.get('QR_U_YA', 'q')                 # plan arc: 'q' quintic, 'c' cubic Hermite
QR_U_DY = float(os.environ.get('QR_U_DY', '0.004'))         # U: outward plan shift (m, bump 64 t^3 (1-t)^3, C2) over QR_U_DX0 .. QR_U_DX1 (the plan hook starts earlier and the glass strip's normal keeps a plateau)
QR_U_DX0, QR_U_DX1 = float(os.environ.get('QR_U_DX0', '0.70')), float(os.environ.get('QR_U_DX1', '1.20'))
QR_PB = int(os.environ.get('QR_PB', '1'))      # U follows the photo's window sill line b (outer edge of the dark groove = where the body paint starts, p013 two-sided reading) at x 0.4 / 0.6 / 0.8: an extra smooth offset (clamped spline) so that the net y is the target there
QR_PB_X = (0.0, 0.2, 0.4, 0.6, 0.8, 0.9, 1.0, 1.1, 1.15, 1.2)
QR_PB_Y = tuple(None if v == 'None' else float(v) for v in os.environ.get('QR_PB_Y', 'None,None,0.8542,0.8240,0.7847,None,None,None,None,None').split(','))      # None = no offset there (x <= 0.2 stays on the design curve; from x 0.9 the p013 groove is closing and the photo reading is not usable, the arc to the tip is the design curve)
QR_P1_DY = float(os.environ.get('QR_P1_DY', '0.003'))      # glass edge: how far outboard of the locked position its P1 may be (the crest start moved out by 29 mm there; high / r81 readings allow about 10)
QR_P1_X0 = float(os.environ.get('QR_P1_X0', '1.0'))
QR_DG_M = int(os.environ.get('QR_DG_M', '23'))             # door glass: the locked number of divisions across the strip
QR_ROOF_X0 = float(os.environ.get('QR_ROOF_X0', '0.40'))  # roof rail: quintic from here to the window tip.  q12 (review 2026-10-22, roof rail; user: "都同意"): 0.65 -> 0.40.  From 0.65 the quintic had to swing out to the
#   q4r crest start C0 within 55 cm: an S in plan with 6 sign changes of y'' (-0.75 .. +0.57).  From 0.40: one smooth inflection (-0.42 .. +0.29); the rail moves out <= 13 mm at x 0.81 (wl 10.5 mm).
QR_SC_D = float(os.environ.get('QR_SC_D', '0.002'))      # fold: the roll's centre sc(x) moves toward L by this much over the first rows (the chord L -> U is 6-11 mm shorter than the locked one behind the new window line start: the inclined leg would vanish and th spike to 37 deg in the first fold row; 2 mm is enough), fading out between QR_SC_X1 and QR_SC_X2
QR_SC_X1, QR_SC_X2 = float(os.environ.get('QR_SC_X1', '0.90')), float(os.environ.get('QR_SC_X2', '0.94'))
QR_WL_B0, QR_WL_B1 = float(os.environ.get('QR_WL_B0', '1.10')), float(os.environ.get('QR_WL_B1', '1.17'))      # window line: its end (the glass sliver's upper edge) bends by < 1 mm so that the chord U -> wl is the direction of the rail rung (U -> rail) from QR_WL_B1 on (blend from QR_WL_B0): the shoulder's end direction and the tip rows then agree (G1 at the window tip)
QR_TIP_F0 = 0.77                                          # (the locked TIP_F)
if QR_ON:
    TIP_F = float(os.environ.get('QR_TIP_F', '0.82'))    # C0 = T seen from L at this fraction (T itself stays where it was: L + 0.77 (C0_old - L))

HUB_X = (-1.487, 1.61)
HUB_Z = 0.39

# R1c front face x(y, z): bowed in plan, raked.  Since R1e it is NOT the front face any more (that is the flat plane NOSE['F'], see build_nose); it only places the
# corner edge E where l3 / sill meet the old face, and E is the first row of the LOCKED panels wall / wall_black -> do not change these three numbers.
FACE = dict(x=-2.48, bow=0.09, rake=0.05)
def face_x(y, z):
    return FACE['x'] + FACE['bow'] * (np.asarray(y) / 0.67) ** 2 + FACE['rake'] * (0.545 - np.asarray(z)) / 0.3

TAIL_X = [(0.19, 1.80), (0.30, 1.98), (0.40, 2.067), (0.50, 2.165), (0.60, 2.241), (0.70, 2.316), (0.80, 2.352), (0.90, 2.374), (1.00, 2.385), (1.08, 2.385)]
def tail_x(y, z):
    z = np.asarray(z, float)
    xs = np.array([pchip(TAIL_X, v) for v in z.ravel()]).reshape(z.shape)
    return xs - 0.015 * (np.asarray(y) / 0.9) ** 2


def hood_z(x):
    return 0.545 + HOOD_B * (np.asarray(x) + 2.39)


# ----------------------------------------------------------------------------- the longitudinal curves (graphs over x)
CURVES = {}
NOSE_FIT = {}
FLAP_INFO = {}


def reg(c):
    CURVES[c.name] = c
    return c


# --- L (character line).  y: chamfer in plan over the nose, then the flat side; z: traced tonal edge in 018 (front), the rear fit of R1b (z = .8337 + .1029 x - .00258 x^2), the tail
L_Y = [(-2.39, 0.670), (-2.12, 0.930), (-1.85, 1.035), (-1.625, 1.060), (-1.0, 1.060), (1.65, 1.060), (2.05, 1.050), (2.28, 1.000), (2.41, 0.920)]
L_Z_FRONT = [(-2.39, 0.536), (-2.30, 0.556), (-2.20, 0.578), (-2.10, 0.600), (-2.00, 0.621), (-1.90, 0.642), (-1.86, 0.650)]     # tonal edge in 018 (see shots/full_rework/r1c/lines)
L_Z_FRONT = [(x, z + (N_OLD[2] - 0.536) * (1 - float(sstep(-2.39, -1.86, x)))) for x, z in L_Z_FRONT]     # ... lifted (9 mm at the nose, 0 at x -1.86) so that L starts exactly at the nose corner N
def l_z_rear(x):
    return 0.8337 + 0.1029 * x - 0.00258 * x * x
L_Z_TAIL = [(2.05, 1.025), (2.28, 1.015), (2.41, 1.000)]


def build_L():
    xs = np.linspace(-2.39, 2.41, 97)
    yy = np.array([pchip(L_Y, x) for x in xs])
    zk = [(x, z) for x, z in L_Z_FRONT] + [(x, l_z_rear(x)) for x in np.linspace(-1.2, 1.65, 12)] + L_Z_TAIL
    zz = np.array([pchip(zk, x) for x in xs])
    c = fit3(np.stack([xs, yy, zz], 1), 9, 'L', ncp_z=10)
    return reg(c)


# --- U (fender crest -> beltline)
def _u_front_y(x):
    return 0.935 - 0.647 * (-1.75 - x) ** 2          # plan of the crest over the nose: a parabola from N (y .67) to the plateau y .935 at x -1.75 (slope .83 at N)


U_Y = [(x, _u_front_y(x)) for x in np.linspace(-2.39, -1.85, 7)] + [(-1.75, 0.935), (-1.60, 0.938), (-1.43, A_OUT[1]), (-1.00, 0.920), (-0.40, 0.917), (0.15, 0.885), (0.65, 0.825), (0.90, 0.775)]
U_Z = [(-2.39, 0.545), (-2.20, 0.640), (-2.00, 0.735), (-1.80, 0.810), (-1.60, 0.862), (-1.43, A_OUT[2]), (-1.00, 0.874), (-0.40, 0.872), (0.15, 0.930), (0.65, 1.000), (0.90, 1.040)]


def tip_point(L, rail, q13=True):
    a, b = L.at(X_TIP), np.array(rail.at(X_TIP), float)
    if not q13:
        return a + TIP_F * (b - a)
    if QF_R1_ZK > 0.0 and QF_R1_Y <= 0.0:
        b[2] = QF_R1_ZK          # q13: the ridge starts lower (see build_all); the tip keeps its place on the rung L -> ridge start ...
    t = a + TIP_F * (b - a)
    t[1] -= QF_TIP_D[0]          # ... less these offsets (q13): the rung above the tip then rises steeper than the chord L -> tip, so the tip row carries the soft arc's roll (see QF_TIP_D)
    t[2] -= QF_TIP_D[1]
    if QF_Q14 and QF_Q15 and QF_R1_ZK > 0.0 and QF_R1_Y > 0.0:
        # q15: the tip sits on the beam plane (R-1 and the tip row's outer edge L; 7 mm lower), so the band under the window runs into the plane behind it without a step
        c0, e = np.array([X_TIP, QF_R1_Y, QF_R1_ZK]), np.asarray(E_TARGET, float)
        n = np.cross(e - c0, np.asarray(a, float) - c0)
        t[2] = c0[2] - (n[0] * (t[0] - c0[0]) + n[1] * (t[1] - c0[1])) / n[2]
    return t


class _QRz:
    """q4-rear: z(x) of the window-lower line for x >= xq: slope = (s0 + k0 u)(1 - S(u/wr)) + s1 S(u/wr) (C2 with the traced fit at xq, smootherstep S); from xh on a quintic that reaches the
    window tip (xt, zt) with the slope stip and zero curvature (C2 with the cruise at xh)"""

    def __init__(self, xq, p0, s0, k0, s1, wr, xh, xt, zt, stip):
        self.xq, self.p0, self.s0, self.k0, self.s1, self.wr, self.xh, self.xt = xq, p0, s0, k0, s1, wr, xh, xt
        e = 1e-4
        v, d = float(self._cr(xh)), float(self._cr_d1(xh))
        a = float(self._cr_d1(xh + e) - self._cr_d1(xh - e)) / (2 * e)
        self.sm = (QR_U_ZH == 's')
        if self.sm:                                           # slope + Delta smootherstep((x - xh)/(xt - xh)); Delta from the tip height
            self.dl = (zt - float(self._cr(xt))) / ((xt - xh) * 0.5)
        else:
            self.q = _Quin1D(xh, v, d, a, xt, zt, stip, 0.0)

    @staticmethod
    def _I1(t):
        return 2.5 * t ** 4 - 3 * t ** 5 + t ** 6

    @staticmethod
    def _J(t):
        return 2 * t ** 5 - 2.5 * t ** 6 + 6.0 / 7.0 * t ** 7

    @staticmethod
    def _S(t):
        return t ** 3 * (10 - 15 * t + 6 * t * t)

    def _cr(self, x):
        x = np.asarray(x, float); u = x - self.xq; wr = self.wr
        tc = np.clip(u / wr, 0.0, 1.0); ex = np.maximum(u - wr, 0.0)
        A = u - (wr * self._I1(tc) + ex)
        B = u * u / 2 - (wr * wr * self._J(tc) + np.maximum((u * u - wr * wr) / 2, 0.0))
        return self.p0 + self.s0 * A + self.k0 * B + self.s1 * (wr * self._I1(tc) + ex)

    def _cr_d1(self, x):
        x = np.asarray(x, float); u = x - self.xq
        S = self._S(np.clip(u / self.wr, 0.0, 1.0))
        return (self.s0 + self.k0 * u) * (1 - S) + self.s1 * S

    def __call__(self, x):
        x = np.asarray(x, float)
        if self.sm:
            w = self.xt - self.xh
            return self._cr(x) + self.dl * w * self._I1(np.clip((x - self.xh) / w, 0.0, 1.0))
        return np.where(x < self.xh, self._cr(x), self.q(x))

    def d1(self, x):
        x = np.asarray(x, float)
        if self.sm:
            return self._cr_d1(x) + self.dl * self._S(np.clip((x - self.xh) / (self.xt - self.xh), 0.0, 1.0))
        return np.where(x < self.xh, self._cr_d1(x), self.q.d1(x))

    def d2(self, x, e=1e-4):
        x = np.asarray(x, float)
        if self.sm:
            return (self.d1(x + e) - self.d1(x - e)) / (2 * e)
        return np.where(x < self.xh, (self._cr_d1(x + e) - self._cr_d1(x - e)) / (2 * e), self.q.d2(x))


class _QRy:
    """q4-rear: y(x) (plan) of U from x1 to the tip: the traced curve's value / slope / curvature carried on as a parabola, then (from xhy, solved so that the tip height is hit) a smootherstep
    hook of the slope up to the tip slope (C2 everywhere; the plan turn is synchronous with the hook in z)"""

    def __init__(self, x1, v1, d1, a1, xt, yt, st):
        self.x1, self.v1, self.d1_, self.a1, self.xt, self.st = x1, v1, d1, a1, xt, st
        lo, hi = x1, xt - 0.02
        for _ in range(60):
            mid = 0.5 * (lo + hi)
            self.xh = mid
            if self(xt) < yt:          # went too far inboard -> start the hook later
                lo = mid
            else:
                hi = mid
        self.xh = 0.5 * (lo + hi)

    def _par(self, x):
        u = np.asarray(x, float) - self.x1
        return self.v1 + self.d1_ * u + 0.5 * self.a1 * u * u

    def _par_d1(self, x):
        return self.d1_ + self.a1 * (np.asarray(x, float) - self.x1)

    def __call__(self, x):
        x = np.asarray(x, float)
        xh = self.xh
        w = self.xt - xh
        sl = self._par_d1(xh)
        dl = self.st - (self._par_d1(xh) + self.a1 * (self.xt - xh))          # the hook adds Delta to the parabola's slope at the tip
        th = np.clip((x - xh) / w, 0.0, 1.0)
        return self._par(x) + dl * w * (2.5 * th ** 4 - 3 * th ** 5 + th ** 6)

    def d1(self, x, e=1e-5):
        x = np.asarray(x, float)
        return (self(x + e) - self(x - e)) / (2 * e)

    def d2(self, x, e=1e-4):
        x = np.asarray(x, float)
        return (self.d1(x + e) - self.d1(x - e)) / (2 * e)


class _Bump1D:
    """A (64 t^3 (1-t)^3), t = (x - x0)/(x1 - x0): C2, zero outside [x0, x1]"""

    def __init__(self, x0, x1, A):
        self.x0, self.x1, self.A = x0, x1, A

    def __call__(self, x):
        t = np.clip((np.asarray(x, float) - self.x0) / (self.x1 - self.x0), 0.0, 1.0)
        return self.A * 64 * t ** 3 * (1 - t) ** 3

    def d1(self, x):
        t = np.clip((np.asarray(x, float) - self.x0) / (self.x1 - self.x0), 0.0, 1.0)
        return self.A * 64 * (3 * t ** 2 * (1 - t) ** 3 - 3 * t ** 3 * (1 - t) ** 2) / (self.x1 - self.x0)

    def d2(self, x):
        t = np.clip((np.asarray(x, float) - self.x0) / (self.x1 - self.x0), 0.0, 1.0)
        return self.A * 64 * (6 * t * (1 - t) ** 3 - 18 * t ** 2 * (1 - t) ** 2 + 6 * t ** 3 * (1 - t)) / (self.x1 - self.x0) ** 2


class _Sum1D:
    def __init__(self, a, b):
        self.a, self.b = a, b

    def __call__(self, x):
        return self.a(x) + self.b(x)

    def d1(self, x):
        return self.a.d1(x) + self.b.d1(x)

    def d2(self, x):
        return self.a.d2(x) + self.b.d2(x)


class _Quin1D:
    """quintic y(x) on [x0, x1] from end values, slopes and second derivatives"""

    def __init__(self, x0, v0, d0, a0, x1, v1, d1_, a1):
        h = x1 - x0
        self.x0, self.h = x0, h
        M = np.array([[1, 0, 0, 0, 0, 0], [0, 1, 0, 0, 0, 0], [0, 0, 2, 0, 0, 0], [1, 1, 1, 1, 1, 1], [0, 1, 2, 3, 4, 5], [0, 0, 2, 6, 12, 20]], float)
        self.c = np.linalg.solve(M, np.array([v0, d0 * h, a0 * h * h, v1, d1_ * h, a1 * h * h], float))

    def __call__(self, x):
        return np.polyval(self.c[::-1], (np.asarray(x, float) - self.x0) / self.h)

    def d1(self, x):
        return np.polyval(np.polyder(self.c[::-1]), (np.asarray(x, float) - self.x0) / self.h) / self.h

    def d2(self, x):
        return np.polyval(np.polyder(self.c[::-1], 2), (np.asarray(x, float) - self.x0) / self.h) / self.h ** 2


class _Pw1D:
    """pieces [(x_lo, x_hi, f)] following each other; f has __call__, d1, d2 (clamped to the first / last piece outside)"""

    def __init__(self, pcs):
        self.pcs = pcs

    def _ev(self, x, m):
        x = np.asarray(x, float)
        out = np.zeros_like(x)
        n = len(self.pcs)
        for k, (lo, hi, f) in enumerate(self.pcs):
            sel = ((x >= lo) if k > 0 else np.ones(x.shape, bool)) & ((x < hi) if k < n - 1 else np.ones(x.shape, bool))
            out = np.where(sel, getattr(f, m)(x) if m else f(x), out)
        return out

    def __call__(self, x):
        return self._ev(x, None)

    def d1(self, x):
        return self._ev(x, 'd1')

    def d2(self, x):
        return self._ev(x, 'd2')


def _qr_roof(base, L):
    """q4-rear: the roof rail aft of QR_ROOF_X0 = a quintic (C2 with the fit at its start) that reaches C0 with the straight crest's slope and zero curvature; then the crest line to E"""
    a, b0 = np.asarray(L.at(X_TIP), float), np.asarray(base.at(X_TIP), float)
    T0 = a + QR_TIP_F0 * (b0 - a)
    b1 = a + (T0 - a) / TIP_F                                    # C0: slides along the rung L -> T towards T
    E = np.asarray(E_TARGET, float)
    sl = (E - b1) / (E[0] - X_TIP)
    xq = QR_ROOF_X0
    fs = []
    for k, bf in ((1, base.fy), (2, base.fz)):
        v0, d0, a0 = float(bf(xq)), float(bf.d1(xq)), float(bf.d2(xq))
        q = _Quin1D(xq, v0, d0, a0, X_TIP, float(b1[k]), float(sl[k]), 0.0)
        ln = Line1D(X_TIP, float(b1[k]), E[0], float(E[k]))
        fs.append(_Pw1D([(base.x0, xq, bf), (xq, X_TIP, q), (X_TIP, base.x1 + 1.0, ln)]))
    c = XCurve(base.x0, base.x1, fs[0], fs[1], 'rail_roof')
    c.resid = getattr(base, 'resid', None)
    return c


def _qr_U(c, tip, x1, D_re, r):
    """q4-rear: U = traced fit up to QR_U_X0, then the design function _QRz in z (y: the traced fit up to x1, then the Hermite arc to the tip, whose tangent is the one in the rear shoulder's plane
    that has the design's tip slope: t = D_re + lam r)"""
    from curves2 import SubCurve, XCurve, _Herm1D
    xq = QR_U_X0
    x1 = QR_U_X1
    p0, s0 = float(c.fz(xq)), float(c.fz.d1(xq))
    k0 = float(c.fz.d1(xq + 1e-3) - c.fz.d1(xq - 1e-3)) / 2e-3
    zq = _QRz(xq, p0, s0, k0, QR_U_S1, QR_U_WR, QR_U_XH, X_TIP, float(tip[2]), QR_U_STIP)
    s_tip = float(zq.d1(X_TIP))
    lam = (s_tip - D_re[2]) / r[2]
    t_new = D_re + lam * r
    v1, d1y = float(c.fy(x1)), float(c.fy.d1(x1))
    a1 = float(c.fy.d1(x1 + 1e-3) - c.fy.d1(x1 - 1e-3)) / 2e-3
    ats = np.linspace(-14.0, 2.0, 161)                           # the plan arc is a quintic; its end curvature = the one with the smallest peak curvature
    cand = [_Quin1D(x1, v1, d1y, a1, X_TIP, float(tip[1]), float(t_new[1]), at) for at in ats]
    xs_ = np.linspace(x1, X_TIP, 81)
    ay = min(cand, key=lambda q: (round(max(0.0, float(np.max(q.d2(xs_)))), 2), float(np.max(np.abs(q.d2(xs_))))))      # no upward bump of the slope (y'' <= 0), then the smallest peak curvature
    if QR_U_YA == 'h':
        ay = _QRy(x1, v1, d1y, a1, X_TIP, float(tip[1]), float(t_new[1]))
    if QR_U_YA == 'c':
        ay = _Herm1D(x1, v1, d1y, X_TIP, float(tip[1]), float(t_new[1]))
    if QR_U_YAT != 'auto' and QR_U_YA == 'q':
        ay = _Quin1D(x1, v1, d1y, a1, X_TIP, float(tip[1]), float(t_new[1]), float(QR_U_YAT))
    if QR_U_DY != 0.0:
        bmp = _Bump1D(QR_U_DX0, QR_U_DX1, QR_U_DY)
        ay = _Sum1D(ay, bmp)
        cy = _Sum1D(c.fy, bmp) if QR_U_DX0 < x1 else c.fy
    else:
        cy = c.fy
    if QR_PB:
        from curves2 import Spline1D
        xk = list(QR_PB_X)
        dk = [0.0 if yk is None else float(yk) - float((cy if xv <= x1 else ay)(xv)) for xv, yk in zip(xk, QR_PB_Y)]
        dsp = Spline1D(xk, dk, 'clamped', 0.0, 0.0)
        class _Dl:
            def __call__(self, x): return np.where(np.asarray(x, float) > xk[0], dsp(np.clip(x, xk[0], xk[-1])), 0.0)
            def d1(self, x): return np.where(np.asarray(x, float) > xk[0], dsp.d1(np.clip(x, xk[0], xk[-1])), 0.0)
            def d2(self, x): return np.where(np.asarray(x, float) > xk[0], dsp.d2(np.clip(x, xk[0], xk[-1])), 0.0)
        dl = _Dl()
        cy = _Sum1D(cy, dl)
        ay = _Sum1D(ay, dl)
    U = Composite([SubCurve(c, c.x0, xq, 'U_main'), XCurve(xq, x1, cy, zq, 'U_qr'), XCurve(x1, X_TIP, ay, zq, 'U_end')], 'U')
    U.resid = c.resid
    U.dbg = dict(t_end=None, t_proj=None, t_new=t_new, zq=zq, lam=lam, s_tip=s_tip, ay=ay)
    return U


def build_U(L, rail):
    tip = tip_point(L, rail)
    tip0 = tip_point(L, rail, q13=False)          # q13: the global fit keeps the q12 tip (nothing forward of the end arc moves); the end arc goes to the q13 tip
    xs = np.linspace(-2.39, X_TIP, 80)
    yk = U_Y + [(X_TIP, float(tip0[1]))]
    zk = U_Z + [(X_TIP, float(tip0[2]))]
    yy = np.array([pchip(yk, x) for x in xs])
    zz = np.array([pchip(zk, x) for x in xs])
    c = fit3(np.stack([xs, yy, zz], 1), 11, 'U')
    # the window tip: U arrives there on the surface of the rear shoulder (the ruling L -> rail).  The traced approach is 24 degrees off that surface's tangent plane
    # (a crease along the rung L -> tip); the last 0.25 m are replaced by a Hermite arc that reaches the tip with a tangent moved U_TIP_BLEND of the way into the plane
    from curves2 import herm3, SubCurve
    x1 = X_TIP - U_TIP_LEN
    t_end = (c.at(X_TIP) - c.at(X_TIP - 0.01)) / 0.01                      # the fit's true end slope (one-sided)
    a, b = L.at(X_TIP), rail.at(X_TIP)
    st = float(np.linalg.norm(tip - a) / np.linalg.norm(b - a))
    dR = (rail.at(X_TIP + 1e-3) - rail.at(X_TIP - 1e-3)) / 2e-3
    D_re = (1 - st) * L.tan(X_TIP) + st * dR
    r = (b - a) / np.linalg.norm(b - a)
    if QF_R1_ZK > 0.0:
        # q13: the rear shoulder's tangent plane at the (moved) tip: the lengthwise direction runs to the lowered ridge start, the row direction is the rung tip -> ridge start
        b = np.array(b, float); b[2] = QF_R1_ZK
        E_ = np.asarray(E_TARGET, float)
        dR = np.array([1.0, dR[1], (E_[2] - b[2]) / (E_[0] - X_TIP)])
        D_re = (1 - st) * L.tan(X_TIP) + st * dR
        r = (b - tip) / np.linalg.norm(b - tip)
    t_proj = D_re + float((t_end - D_re) @ r) * r                          # the tangent closest to the traced one that lies in the rear shoulder's plane
    t_new = t_end + U_TIP_BLEND * (t_proj - t_end)
    from curves2 import XCurve, _Herm1D
    if QR_ON:
        return reg(_qr_U(c, tip, x1, D_re, r))
    arc = XCurve(x1, X_TIP, _Herm1D(x1, float(c.at(x1)[1]), float(c.fy.d1(x1)), X_TIP, float(tip[1]), float(t_new[1])),
                 _Herm1D(x1, float(c.at(x1)[2]), float(c.fz.d1(x1)), X_TIP, float(tip[2]), float(t_new[2])), 'U_end')
    U = Composite([SubCurve(c, c.x0, x1, 'U_main'), arc], 'U')
    U.resid = c.resid
    U.dbg = dict(t_end=t_end, t_proj=t_proj, t_new=t_new)
    return reg(U)


# --- the lower lines
SILL_K = [(-2.40, 0.62, 0.22), (-2.12, 0.84, 0.20), (-1.85, 0.93, 0.19), (-1.4, 0.97, 0.19), (0.0, 0.98, 0.19), (1.3, 0.97, 0.19), (1.8, 0.88, 0.19)]      # ends where the tail face meets z .19 (x 1.8)
L3_K = [(-2.40, 0.66, 0.285), (-2.12, 0.92, 0.29), (-1.85, 1.02, 0.29), (-1.4, 1.05, 0.29), (-1.09, 1.052, 0.29), (0.0, 1.055, 0.399), (1.2, 1.055, 0.52), (1.9, 1.045, 0.59), (2.05, 1.035, 0.66),
        (2.28, 0.99, 0.79), (2.41, 0.90, 0.86)]
ROOF_RAIL_K = [(-0.40, 0.655, 1.283), (0.15, 0.60, 1.315), (0.65, 0.565, 1.30), (1.20, 0.515, 1.26), (1.65, 0.45, 1.18), (2.05, 0.42, 1.08), (2.28, 0.41, 1.06), (2.41, 0.40, 1.04)]
TOP_K = [(-1.625, 0.0, W[2]), (-1.42, 0.0, 0.94), (-1.0, 0.0, 1.09), (-0.40, 0.0, 1.303), (0.15, 0.0, 1.34), (0.65, 0.0, 1.325), (1.20, 0.0, 1.26), (1.65, 0.0, 1.15), (2.05, 0.0, 1.08), (2.28, 0.0, 1.05), (2.41, 0.0, 1.03)]


# --- the greenhouse: ridge (inner wall) height / plan width, the glass crown
HW_K = [(0.15, 0.0), (0.65, 0.02), (1.20, 0.075), (1.65, 0.075), (2.05, 0.075), (2.25, 0.05), (2.38, 0.0), (2.42, 0.0)]       # ridge inner wall height (crest -> glass edge)
DY_K = [(0.15, 0.0), (0.65, 0.017), (1.20, 0.06), (1.65, 0.075), (2.05, 0.12), (2.25, 0.07), (2.38, 0.0), (2.42, 0.0)]        # ... and its plan width
X_SEAM = 2.05                                                                                                  # wing seam: glass ends, the (stowed wing) deck begins
RAIL_OFF = (PILL_W, T_DZ)                                                                                      # lens upper edge = rail + (0.035, -0.022)


def crown(x):
    """centre of the rear glass above its edge: .045 at the B pillar -> .012 over the rear window -> 0 at the wing seam (a flat deck)"""
    x = np.asarray(x, float)
    c = 0.045 + (0.012 - 0.045) * sstep(0.65, 1.20, x)
    return np.where(x < 0.65, 0.045, c * (1 - sstep(1.65, X_SEAM, x)))


# ----------------------------------------------------------------------------- R1d: roof to tail (the rear quarter)
# User correction 3 (ROADSTER_DESIGN.md), measured on p013 / p017 / p018 / r81 / official-02 through the matched cameras (cam.py; reading_overlay.py draws the model's own curves back on them):
#   crest   ONE straight line from the window tip C0 (end of the locked rail band) to the ear tip E on the tail face (E = the old rail's end, so the tail face is unchanged)
#   glass   its edge hugs the crest (2 cm inboard, ~1 cm lower) up to P1 (a station), then runs STRAIGHT in plan to the seam corner P3 (x 2.05, |y| Y_P3); the pane is flat across the car
#           behind the window tip (the crown dies out between the B seam and the tip) and descends smoothly to the seam; the wing panel (deck) continues it flush (G1) to the tail edge
#   ear     the narrow body-colour triangle between the crest, the seam and the edge P3 -> E (panel ridge_inner = crest -> glass edge, from x 0.15 to the tail)
#   arc     the SOFT roll from U's rear segment (x 0.88) round to E: the side-window body (above / inboard, steep) rolls over into the horizontal tail shoulder (below / outboard).
#           It is a variable-radius roll in the cross-section of panel rear_shoulder (L -> arc -> crest), not the 8 mm fillet; its amplitude is 0 at the window tip (the locked
#           rows there are straight) and full from X_ROLL1 on.
E_TARGET = (2.381997, 0.402721, 1.042049)       # ear tip = where the R1c rail met the tail face (so the tail face and everything behind it stay as they were)
X_P1 = 1.2 + 9 * 0.45 / 28              # a shell2.XS station: the glass edge leaves the crest here
Y_P3 = 0.290                            # glass half width at the seam (p013 .28-.29, official-02 .286, r81 .30)
DY_P1, HW_P1, HW_P3 = 0.020, 0.007, 0.013      # glass edge: plan offset / drop under the crest at P1; drop under the crest at P3 (the photos put the glass base at the crest height)
X_BL0 = 0.65                            # the glass edge eases from its R1c shape at the B seam to the hugging strip at P1
X_CR = X_TIP                            # the glass crown (centre above the edge) has died out by the window tip: a flat pane behind it
ARC_K = [(0.88, None, None), (1.20, 0.725, 1.060), (1.55, 0.660, 1.075), (2.15, 0.520, 1.045), (2.38, E_TARGET[1], E_TARGET[2]), (2.41, 0.4000, 1.0400)]    # the arc as READ from p013 / p017 / p018 / r81 (U at 0.88 comes from U): the reference of the fold (CURVES['arc_reading'])
REAR = {}


def quint1(x, x0, f0, d0, c0, x1, f1, d1, c1):
    """quintic Hermite in x (vectorised, clamped): value / slope / second derivative at both ends"""
    h = x1 - x0
    t = np.clip((np.asarray(x, float) - x0) / h, 0.0, 1.0)
    h0 = 1 - 10 * t ** 3 + 15 * t ** 4 - 6 * t ** 5
    h1 = t - 6 * t ** 3 + 8 * t ** 4 - 3 * t ** 5
    h2 = 0.5 * t ** 2 - 1.5 * t ** 3 + 1.5 * t ** 4 - 0.5 * t ** 5
    h4 = -4 * t ** 3 + 7 * t ** 4 - 3 * t ** 5
    h5 = 0.5 * t ** 3 - t ** 4 + 0.5 * t ** 5
    return h0 * f0 + h1 * h * d0 + h2 * h * h * c0 + (1 - h0) * f1 + h4 * h * d1 + h5 * h * h * c1


QF_WT_LAM = float(os.environ.get('QF_WT_LAM', '2e-5'))     # q12d: fairness weight of the window line refit, B pillar .. QF_WT_X1 (0 = off)
QF_WT_X1 = float(os.environ.get('QF_WT_X1', '1.17'))
QF_RT_LAM = float(os.environ.get('QF_RT_LAM', '2e-5'))     # q12d: fairness weight of the roof rail refit, XB1 .. window tip (0 = off)
QF_AP_STRAIGHT = os.environ.get('QF_AP_STRAIGHT', '1') == '1'     # q12d: the A pillar's outer edge near-straight from the foot to the header (see design_curves)
QF_UB_X1 = float(os.environ.get('QF_UB_X1', '1.2' if os.environ.get('QF_Q13B', '1') == '1' else '1.12'))      # q12 item 4: the U crease softens into the fold over X_FOLD0 .. this x (<= X_FOLD0: off)
# (q13b: up to the window tip, 1.12 before: the roll now reaches 33 deg at the tip and grew from 1 to 35 deg over 0.92 .. 1.1, a closed loop in the reflections ahead of the tip)
QF_GE_FAIR = os.environ.get('QF_GE_FAIR', '1') == '1'     # q12: glass edge / window line fairing (see design_curves)
QF_GE_X0 = float(os.environ.get('QF_GE_X0', '0.85'))
QF_HDR_G2 = os.environ.get('QF_HDR_G2', '1') == '1'       # q12: the roof header as a G2 quintic (see build_all)
QF_TOP_FAIR = os.environ.get('QF_TOP_FAIR', '1') == '1'     # q12: the centre line / glass edge behind the B seam with one smooth curvature step (see design_curves)
QF_TOP_X = tuple(float(v) for v in os.environ.get('QF_TOP_X', '0.65,0.85').split(','))     # where the centre line's curvature steps from the roof's to the constant rear value
QF_GE_CORNER = os.environ.get('QF_GE_CORNER', '1') == '1'     # q13: glass edge straight from the B seam to a short corner into the diagonal (see design_curves)
QF_GE_R = float(os.environ.get('QF_GE_R', '0.025'))        # q13: half length (m, along x) of the glass edge's corner blend
QF_R1_ZK = float(os.environ.get('QF_R1_ZK', '1.232'))      # q13: height of the ridge R-1 at the window tip (0 = off: the q12 rail)
QF_R1_Y = float(os.environ.get('QF_R1_Y', '0.525'))        # q13b: |y| of the ridge R-1 at the window tip (0 = keep the q12 plan)
QF_R1_YX0 = float(os.environ.get('QF_R1_YX0', '0.30'))     # q13b: the roof rail's plan is re-blended from here to the window tip
QF_R1_X0 = float(os.environ.get('QF_R1_X0', '0.45'))       # q13: the roof rail's side curve is re-blended from here to the window tip
QF_TIP_D = tuple(float(v) for v in os.environ.get('QF_TIP_D', '0,0.011').split(','))     # the window tip moved inboard / down by these (m); q13b: from its q12 place, to the p018 tip (z ~1.180)
QF_DG_X = tuple(float(v) for v in os.environ.get('QF_DG_X', '0.5,51').split(','))     # q13b: U's plan re-drawn from this x so that the door glass meets the tip at this angle (deg; 0 = off)


def herm1(x, x0, f0, d0, x1, f1, d1):
    """cubic Hermite in x (vectorised, clamped to [x0, x1]): value f0 / slope d0 at x0, f1 / d1 at x1"""
    h = x1 - x0
    t = np.clip((np.asarray(x, float) - x0) / h, 0.0, 1.0)
    t2, t3 = t * t, t * t * t
    return (2 * t3 - 3 * t2 + 1) * f0 + (t3 - 2 * t2 + t) * h * d0 + (-2 * t3 + 3 * t2) * f1 + (t3 - t2) * h * d1


# ----------------------------------------------------------------------------- R1d2: the soft arc = a FOLD that peels off U at x ~ 0.88 and runs to the ear tip E
# Topology (user correction 3, as relayed for R1d2): aft of x ~ 0.88 the steeply rising rear part of U is only the glass / paint boundary INSIDE the inclined side surface (the door glass
# plane); the fold between that inclined body and the shoulder leaves U there and becomes the soft arc to E.  The sliver between U's rising part and the arc is part of the inclined body
# (tangent-continuous with the door-glass strip along U, G1 and the curvature of the flat glass, 0, at U).
# Cross-section at every station x (the panels' rows, shell2.shoulder for x <= X_TIP and shell2.rear_shoulder aft of it): ONE fair curve from the character line L (s = 0) to the upper end c
# (U for x <= X_TIP, the crest aft of it), given by its CURVATURE kappa(s), so it is G2 by construction:
#       kappa = bowl(B1) over the shoulder leg  +  ROLL (theta, length ell, peak radius ell / (1.875 theta), bump 30 t^2 (1-t)^2)  +  barrel(B2) from the roll's centre to the end of the inclined leg
# T(x) (the NET turn across the fold: the rise of the section's tangent angle from the start of the roll to its steepest point), B1(x) and sc(x) (arclength of the fold's centre from L) are smooth
# DESIGN FUNCTIONS (FOLD_K; tools/blender/fold_fit.py chose sc so that the apex of the roll stays as near to the reading ARC_K as T allows); the roll's own turn theta, the start direction phi0 and
# the length S follow from the equations: the two end points, the net turn T, and (forward of the tip) the tangent of the inclined leg at U = the door-glass strip's direction (then the barrel B2 is
# a result).  Aft of the tip the barrel B2 dies out (sstep over X_B2) and the whole row is blended into the standard node distribution.
X_FOLD0 = 0.65 + 11 * 0.55 / 27     # = 0.8741, a shell2.XS station: the fold leaves U here (the rows up to and including this station are untouched: the R1d rows)
FOLD_BAND = 0.030                # target: the apex of the roll within this distance of the reading
FOLD_RHO = 1.3                   # the nodes of a row are denser across the roll (local densification: density 1 + RHO over the roll +- 3 cm)
FOLD_ELL = (0.12, 0.22, 1.2, 1.8)    # length of the roll (m): 0.12 up to the window tip, growing (quintic) to 0.22 by x 1.8 (the soft end)
FOLD_CAP = 1.7                   # the roll is at most this times the length of the inclined leg (the roll's second half must lie on it)
X_B2 = 0.35                      # aft of the tip the barrel (B2) dies out over this distance
X_B2_SLOPE = float(os.environ.get('X_B2_SLOPE', '0.08'))     # ... but its rate of change (and its length's) at the tip is continued over this distance (G1 across tip_lo)
X_B2_H = 0.02                    # the forward family's rates are taken over this stretch before the tip
B2_RATE, LAM_RATE = float(os.environ.get('B2_RATE', '0.15')), float(os.environ.get('LAM_RATE', '0.8'))     # the fractions of those rates the aft family continues (tuned: the G1 break across tip_lo, tools/blender/shell2 rows, is then <= 0.5 deg; the full rates over-shoot)
X_NODE = 0.25                    # ... and the nodes move from the tip row's distribution to the standard one over this distance
T_AFT_CUT, X_T_AFT = float(os.environ.get('T_AFT_CUT', '0.5')), 0.45      # rearcrease: aft of the window tip the roll's net turn T is cut by this fraction (reached X_T_AFT behind the tip): a nearly flat, slightly concave face

# rearcrease round 2 (coordinator ruling D, 2026-10-20): NO BARREL.  The convex barrel B2 (the inclined leg bowed outward right behind the roll, up to -10 degrees at the window tip) made the S-shaped section and the "curled
# leaf" in the rear view; it only existed to bring the leg's end direction down to the glass strip's.  The section is now a straight shoulder leg, ONE concave roll and a straight inclined leg: the roll's turn is the NET
# turn (forward of the tip: the end direction is the door glass strip's, G1; aft of it: the design function FOLD_NET, from the tip's own net turn).  The rows at x <= X_KEEP are the old ones (nothing forward of x 0.9 moves);
# over X_NB the old section blends into the new one (both have the same end points and the same end direction at U).
FOLD_NOBARREL = os.environ.get('FOLD_NOBARREL', '1') == '1'
X_KEEP, X_NB, X_NB_AFT = float(os.environ.get('X_KEEP', '0.874')), float(os.environ.get('X_NB', '0.0205')), 0.30      # round 4: no barrel from the first fold row on (x_keep = X_FOLD0; the old rows' barrel left inflection lines = the concentric arcs)
X_NB_SLOPE = float(os.environ.get('X_NB_SLOPE', '0.05' if QR_ON else '0.15'))      # (q4r: the aft th continues the tip rate for 5 cm instead of 15: the roll dips < 0.1 deg below flat behind the tip, not 0.4)
FOLD_NET_OLD = [(1.2, 0.0), (1.4, 2.2), (1.6, 3.4), (1.8, 2.8), (2.0, 1.6), (2.2, 0.7), (2.382, 0.0)]     # th (degrees) of the roll aft of the window tip (blended in from the tip's own value and rate over X_NB_AFT): a slightly concave face
# q12 (review 2026-10-22, R-6 face; user: "都同意", the face behind the window slightly concave and smooth): the old table fell off as a flattening tail (2.8 -> 1.6 -> 0.7 -> 0, positive second
# derivative), which lifts the middle of the face along x: lengthwise convex (-0.3 .. -0.4 /m) at x 1.8 - 2.1, a saddle over 76 % of the face.  An arch th = TH 4u(1 - u) over the same span (even
# negative second derivative) keeps the face concave across AND slightly concave along.  QF_R6_TH = 0 restores the old table.
QF_R6_TH = float(os.environ.get('QF_R6_TH', '3.4'))
FOLD_NET = [(x, QF_R6_TH * 4.0 * u * (1.0 - u)) for x, u in ((x, (x - 1.2) / (2.382 - 1.2)) for x in np.linspace(1.2, 2.382, 13))] if QF_R6_TH > 0 else FOLD_NET_OLD
# q13 (review 2026-10-22, the face behind the window; user: "都同意"): the roll of the soft arc was 22 deg at x 0.92, 0 at the window tip (the tip row was straight), then grew back to the arch's 3.4 deg at
# x 1.8 and died at E: concave, flat, concave again along x (the "bulge" right behind the window and the waves in the reflections), and its centre sc(x) wobbled between the spline's knots
# (1.4 / 1.7 / 2.0: the inflections of the lengthwise lines).  With the window tip a few mm lower / inboard (QF_TIP_D) the tip row keeps a roll of ~7 deg; aft of it the roll now goes from that
# value towards QF_TH13[0] (exponential, leaving the tip with the forward family's rate) and tapers to 0 at E from QF_TH13[2] (smootherstep): one-signed, no dip.  Its centre: one quintic from the tip (C2 with the spline)
# to E.  The larger roll near the ridge also keeps R-1 crisp further aft (it was 5 - 10 deg over x 2.0 - 2.35).
QF_RS13 = os.environ.get('QF_RS13', '1') == '1'
QF_TH13 = tuple(float(v) for v in os.environ.get('QF_TH13', '6.0,0.25,1.95').split(','))     # roll aft of the tip: plateau (deg), decay length (m) if the tip rate gives none, x where the taper to E starts
QF_SC13_END = tuple(float(v) for v in os.environ.get('QF_SC13_END', '0.53,0.03').split(','))     # roll centre (arclength from L) and its slope at E


def fold_th13(x, th_tip, dth_tip=0.0):
    """q13: the roll's turn (rad) aft of the window tip: an exponential approach to the plateau that leaves the tip with the forward family's rate (G1 along x, no inflection; a length of
    QF_TH13[1] m if that rate is not falling), then the taper to E"""
    th_inf, x2 = math.radians(QF_TH13[0]), QF_TH13[2]
    lam = (th_tip - th_inf) / -dth_tip if dth_tip < 0.0 and th_tip > th_inf else QF_TH13[1]
    lam = min(max(lam, 0.08), 0.6)
    return (th_inf + (th_tip - th_inf) * math.exp(-(x - X_TIP) / lam)) * (1.0 - float(sstep(x2, E_TARGET[0], x)))


def fold_sc13(x):
    """q13: the roll's centre (arclength from L) aft of the window tip: a quintic, C2 with the design spline at the tip"""
    if 'sc13' not in _FOLD:
        f, e = fold_fn('sc'), 1e-3
        v = float(f(X_TIP))
        _FOLD['sc13'] = (X_TIP, v, (float(f(X_TIP + e)) - float(f(X_TIP - e))) / (2 * e), (float(f(X_TIP + e)) - 2 * v + float(f(X_TIP - e))) / e ** 2,
                         E_TARGET[0], QF_SC13_END[0], QF_SC13_END[1], 0.0)
    return float(quint1(x, *_FOLD['sc13']))


# q13b (the bold variant, user: "你的调整太保守了吧"): aft of the window tip the soft arc follows the photo reading ARC_K (it ran 4 - 5 cm above it): the tip row carries the roll of the pane's
# 51 deg side (~33 deg) and a convex turn into the beam top; aft of it the roll's turn / centre follow these knots (pchip) and the convex turn fades out over QF_CV[0]: at the tip it is the crease
# of the glass edge (length QF_CV[1] = 0) and it rounds off at once (length 1 - (1 - t)^QF_CV_P of the way to QF_CV[2]); its turn starts to fade with the rate QF_CV_A (see fold_q13b_params)
QF_Q13B = os.environ.get('QF_Q13B', '1') == '1'
QF_TH13B = [tuple(float(u) for u in k.split(':')) for k in os.environ.get('QF_TH13B', '1.45:22.5,1.6:21.2,1.8:21.3,2.0:20.5,2.15:15.5,2.27:7,2.382:0').split(',')]
QF_SC13B = [tuple(float(u) for u in k.split(':')) for k in os.environ.get('QF_SC13B', '1.4:0.383,1.6:0.416,1.8:0.456,2.0:0.497,2.2:0.522,2.382:0.53').split(',')]
QF_CV = tuple(float(v) for v in os.environ.get('QF_CV', '0.38,0.0,0.18').split(','))
QF_CV_P = float(os.environ.get('QF_CV_P', '2'))
QF_CV_A = float(os.environ.get('QF_CV_A', '0.6'))
QF_CV_RHO = tuple(float(v) for v in os.environ.get('QF_CV_RHO', '2.5,0.012').split(','))      # weight and margin (m) of the node densification over the convex turn
# the shoulder leg's angle phi0(x) is PRESCRIBED from QF_PHI13B_X0 on (clamped cubic spline through the solved value there and these knots): one smooth decline, so the lower face is fair along x;
# the roll's centre sc follows from the end conditions (forward: end points + the pane's direction; aft: end points with the turn th prescribed)
QF_PHI13B_X0 = float(os.environ.get('QF_PHI13B_X0', '1.0'))
QF_PHI13B = [tuple(float(u) for u in k.split(':')) for k in os.environ.get('QF_PHI13B', '1.2:17.6,1.35:15.4,1.5:12.3,1.7:8.2,1.9:5.2,2.1:4.2,2.382:4.0').split(',')]
# q14 (user 2026-10-23: "将窗框和窗后的铁皮做成一个光滑平面，窗下方的平台也做成一个平面，在两个平面相交处做光滑曲面过渡"; chose: platform = ruled, twisting evenly; the edge behind the tip: a
# small, crisp round).  Aft of X_FOLD0 every row of the shoulder / rear shoulder is built directly from three faces: (3) the PLATFORM, straight from L at the angle phi3(x) (a clamped spline
# from the ruled row's chord at X_FOLD0 through QF_P3 to L -> E at the tail: one monotone twist); (2) the steep PANE plane through the window tip T and U(X_FOLD0) at the glass's angle at the tip
# (the frame below the window and the small triangle behind it; forward of the tip the same angle through U); (1) the BEAM plane through the window tip, the start of R-1 and the ear tip E (the
# metal behind the window up to R-1, ~25 deg).  Section = smooth max(3, smooth min(2, 1)) (cubic, C2): the fold (3 | 2, 1) is a soft round QF_FW wide (across, m), the edge (2 | 1) a small one
# QF_WE[0] wide that grows from the crease at the tip over QF_WE[1].  QF_KUP: x range over which the fold passes from the pane to the beam plane (its blend size follows the slope difference).
QF_Q14 = os.environ.get('QF_Q14', '1') == '1'
QF_P3 = [tuple(float(u) for u in k.split(':')) for k in os.environ.get('QF_P3', '1.2:17.9,1.55:11.8,1.8:6.6,2.0:4.4,2.15:3.97').split(',')]
QF_FW = [tuple(float(u) for u in k.split(':')) for k in os.environ.get('QF_FW', '1.0:0.035,1.2:0.06,1.6:0.09,2.0:0.10').split(',')]
QF_KUP = tuple(float(v) for v in os.environ.get('QF_KUP', '1.45,1.75').split(','))
QF_WE = tuple(float(v) for v in os.environ.get('QF_WE', '0.007,0.05').split(','))
QF_P2E = float(os.environ.get('QF_P2E', '2'))
QF_P2R = float(os.environ.get('QF_P2R', '1.2'))      # forward of the tip the pane face steepens from the ruled row's chord (X_FOLD0: no fold yet) to the glass's angle at the tip by this x (1 - (1 - t)^QF_P2E)
# q15 (user 2026-10-23: "窗尖后的三角形不应该存在，而是应该窗后的平面顺滑过渡到窗下的平面"): no pane behind the tip.  The beam plane (1) now holds R-1 and the tip row's outer edge L(X_TIP)
# (27.6 deg; the window tip is 0.7 cm above it), so the band under the window (straight rows L -> U up to the tip, 28.4 deg at the tip row) runs into it without a step; aft of the tip
# every row = smooth max(platform, beam plane), the platform's angle falls from the beam plane's at the tip (QF_P3B_D0 deg / m) through QF_P3B to L -> E at the tail.
QF_Q15 = os.environ.get('QF_Q15', '0') == '1'      # VARIANT (off): experiment; see HISTORY q15
QF_P3B = [tuple(float(u) for u in k.split(':')) for k in os.environ.get('QF_P3B', '1.4:19.5,1.55:13.8,1.7:8.8,1.85:5.0,2.0:4.2').split(',')]
QF_P3B_D0 = os.environ.get('QF_P3B_D0', 'auto')      # the platform's twist rate at the tip (deg / m); auto: the one that makes the rows C1 with the band under the window there
QF_TK = float(os.environ.get('QF_TK', '4'))
QF_KMIN = float(os.environ.get('QF_KMIN', '0.12'))     # q15: the fold's round is sized for at least this slope difference
QF_U15 = float(os.environ.get('QF_U15', '0'))        # VARIANT (off: it bent the window line's hook down into the tip and folded the door glass): U's side view re-drawn over this length, tangent to the beam plane at the tip
QF_TF = float(os.environ.get('QF_TF', '0.08'))       # behind the tip the plane first carries on the window line's rise (a tent L -> T -> C0, C1 with the band under the window) and lets it go over this length
QF_WE_K = int(os.environ.get('QF_WE_K', '3'))       # nodes on each side of the edge (2 | 1) that sit at a fixed spacing across it: the edge runs along one grid line from the tip on
# q16 (user 2026-10-23: rebuild from first principles, "按推荐的做，开始重构出预览"; see HISTORY q16).  Surfaces first, lines from them:
#   P1  the PLANE through R-1 at the tip (C0), the ear tip E and L at the tip (27.6 deg in section): R-1 aft of the tip lies in it, the rail band ahead of it within 5 mm;
#   P2  the PLATFORM: straight rulings from L, one ruled surface from the B pillar to the tail.  Under the window the rows run L -> U; aft of the tip L -> R-1 with the angle q16_p2(x), which
#       falls monotonically from the plane's at the tip (C1 with the rows under the window) through QF_Q16_P2 to L -> E at the tail;
#   ONE soft arc where P2 and P1 meet: cubic smooth max (C2) of constant radius QF_Q16_R (it grows from nothing at the tip, where the two are one plane).
# The side window is a recess in P1: the rail band above it lies in P1 (wl moved onto it, plan only, QF_Q16_WL) and U's depth below P1 closes with zero slope at the tip (U moved in plan
# only, QF_Q16_UX0 .. tip): the rows under the window run into the plane with no step, no crease and no triangle.  No solving, no switches.
QF_Q16 = os.environ.get('QF_Q16', '1') == '1'      # the q16 rear (accepted 2026-10-23, "可以，开始定稿"); QF_Q16=0 rebuilds the q14 rear
# q16 'ruled' (option 1b, user 2026-10-23 "按方案 1b 建模，出预览"): the arc READING (ARC_K, y and z) is the soft arc itself.  The photos put it on no plane through R-1 (through C0, E and the
# reading at x 1.2 / 1.55 / 2.15: 42.8 / 32.7 / 21.6 deg), so P1 becomes the RULED surface reading -> R-1 (43 -> 22 deg aft of the tip, monotone) and the platform the ruled surface
# L -> reading (24 -> 7 deg, monotone): no face twists back anywhere.  Under the window the strip reading -> U is part of the beam face; the window is an opening in it (U and wl close onto
# it, plan only): the window tip moves 4.3 cm inboard, its side view does not change.
QF_Q16_P1 = os.environ.get('QF_Q16_P1', 'ruled')      # 'ruled' (option 1b, accepted) | 'plane' (preview 3)
QF_Q16_KD = float(os.environ.get('QF_Q16_KD', '0.15'))      # 'ruled': the roll under the window takes on the rate of the roll behind the tip over this length before the tip
QF_Q16_XC = float(os.environ.get('QF_Q16_XC', '2.2'))      # 'ruled': both faces follow the reading up to here; aft of it a C2 continuation (the reading's fit bends off near the ear tip)
QF_Q16_WLP = float(os.environ.get('QF_Q16_WLP', '0.6' if QF_Q16_P1 == 'ruled' else '0'))      # 'ruled': > 0 = wl's plan moves by one quintic from this x onto the beam face at the tip (instead of QF_Q16_WL's depth closure); 0 = off
QF_Q16_UP = float(os.environ.get('QF_Q16_UP', '0.95' if QF_Q16_P1 == 'ruled' else '0'))      # 'ruled': > 0 = U's plan is one quintic from this x onto the beam face at the tip (instead of QF_Q16_UX0's depth closure); 0 = off
QF_Q16_GB = tuple(float(v) for v in os.environ.get('QF_Q16_GB', '0.3,0.55,0.05,0.005,0.005,0.1' if QF_Q16_P1 == 'ruled' else '0').split(','))      # 'ruled': the beam's inner edge: the glass edge [3] m inboard and [4] m under R-1, reached over [0] .. [1], back to the old edge round the glass corner (+-[2] in plan, +-[5] in height); 0 = off
QF_Q16_DR = float(os.environ.get('QF_Q16_DR', str(1.2 - (0.65 + 11 * 0.55 / 27))))      # 'ruled': the rows under the window take on the densification over the arc over this length from X_FOLD0
QF_Q16_WL = tuple(float(v) for v in os.environ.get('QF_Q16_WL', '0.9' if QF_Q16_P1 == 'ruled' else '1.0').split(','))      # wl: one value = its distance to P1 closes with zero slope from this x to the tip (plan only); two = the old sstep ramp onto P1
QF_Q16_UX0 = float(os.environ.get('QF_Q16_UX0', '0.9' if QF_Q16_P1 == 'ruled' else '1.14'))
QF_Q16_L = tuple(float(v) for v in os.environ.get('QF_Q16_L', '1.65,0.976').split(','))      # L aft of the window tip (p018, user 2026-10-23 "原车窗[后肩线]应该是水平的"): rises from the tip (G2) to this x / height and runs level to the tail; 0 = off
QF_Q16_LT = tuple(float(v) for v in os.environ.get('QF_Q16_LT', '0,2.37,0.986').split(','))      # the tail corner (user 2026-10-23, "按侧视组"): p018's corner top reads 0.993 (0.984 less the same tonal-edge offset as the level part): L leaves its level at [0] and reaches [2] at [1] (quintic, level at both ends); the light box's top is 5 mm under it; [0] = 0: off (preview: QF_Q16_LT=2.15,2.37,0.986, with REAR_T17=1)
_q17_ = os.environ.get('QF_Q17', '1')
# 2026-10-24 (user: "车尾在斜前视角看去也翘起得比实车更多更尖，不够浑厚专业"): the level edge 1.015 -> 0.995 with the corner (QF_Q17_ZC), R-1 leaves its line at 2.22 (was 2.10) and the deck
# drop is end-loaded (QF_Q17_N 9, 12 with the platform roll QF_Q17_ROLL): the deck and R-1 stay up to ~2.3 and roll down to the edge.  p018: the corner read 0.987 (the 1.015 corner stood 2 - 3 cm over the photo, with L rising
# 3.9 cm into it: the upturned, pointed tail of p016); r81 keeps its level edge (the light band follows it down 2 cm; regions/rear.py DZ_TAIL)
# 2026-10-25 (user: "车尾上方的面还有一处梯形的拱起，应该是两只耳朵延伸到尾端时仍未结束所以突兀结束了……原车是非常自然，不会拱起的"): the wing's top no longer holds the body's
#   height and rolls off in the last 10 cm (QF_Q17_N 12 + QF_Q17_ROLL 2.05, 12, 1: from above a trapezoid plateau with a bright rolled edge, the ear crests R-1 held to 2.22 and fell
#   8 cm in 12 cm).  Deck, R-1 and platform now all leave at the seam (QF_Q17[2] 2.05, QF_Q17_XT 2.05, QF_Q17_N 3 = 2t^3 - t^4: G2 with the body at the seam) and descend
#   gradually to the level edge; the ears fade into the deck before the edge (011 / 002: no step, no plateau).  Deck centre -9.9 -> -16.5 (2.2) -> -24.7 deg at the edge.  The cost:
#   p018's tail outline at x ~2.3 lies ~2 cm under the photo's straight line again (6 - 7 px; 2 px with the end roll).
# 2026-10-25, later (user, after the ear step: "是不是把尾边抬起了之后，就可以很像原图一样，没有一个小台阶？" -> previews -> "按 A 方案做"): the edge between the ears goes up to R-1's
#   own end height (1.0424 = R-1 at E on its line): R-1 runs straight to E (p018: +1 .. +2 px on the photo's straight outline, was -6 px), the deck alone closes the ear step (design2
#   QF_EAR, the straight branch); the corner stays at QF_Q17_ZC 0.995 (p016 / p018) and the platform's end chord rises from it to E; the light box stays under the corner (regions/rear.py
#   DZ_TAIL), so from straight behind a body-colour band shows over it between the ears (up to ~5 cm in the middle, the r81 'trapezoid' of 2026-10-23, accepted for the straight outline).
QF_Q17 = (1.0424, 2.345, 2.05) if _q17_ == '1' else (tuple(float(v) for v in _q17_.split(',')) if ',' in _q17_ else None)      # the level tail top edge (user 2026-10-23, "取中 ≈1.015": the tail seen from behind is flat in r81, the model showed a trapezoid of paint over the light box): (height of the tail's top edge, x where R-1 meets the deck = p013's ear triangle closing 4.6 cm before the tail edge, x where R-1 leaves its line and the platform's angle leaves the reading); QF_Q17=0: off (the tail before 2026-10-23)
_tw_ = os.environ.get('QF_Q17_TW', '1')
QF_Q17_TW = (0.05, 1e-6) if _tw_ == '1' else (tuple(float(v) for v in _tw_.split(',')) if ',' in _tw_ else None)      # q17 tail twist (review 2026-10-23, item 2): (the beam face's width at the level edge, third-difference weight of the platform angle's fit); 0: the platform meets the ruling L -> R-1 at the edge and the face lies down onto it
QF_Q17_L = tuple(float(v) for v in os.environ.get('QF_Q17_L', '1.9709,2.3685,0.25,0,2.20').split(','))      # q17, L to the raised corner: (x of the facet apex S = shell2 L sample I_FS, x of the tail corner = L's last sample, length of L's bend into the facet's straight edge before S, the platform's pivot: the width from L over which it rises into the corner with L, inboard of it it falls to the tail edge (0: where a ruling L -> R-1 at the edge has it); x from which the beam face lies down onto the platform, flat at the edge)
QF_Q17_ZC = float(os.environ.get('QF_Q17_ZC', '0.995'))      # q17, the tail corner's height (L's end). 2026-10-24 (user: "车尾在斜前视角看去也翘起得比实车更多更尖，不够浑厚"): it was QF_Q17[0], the level edge's
#   1.015: L rose 3.9 cm from its level over the last 0.6 m into a pointed corner (p018's tail end lies up to 7.6 px under it, more towards the near corner: the corner reads 0.987).
#   Now the corner and the level edge are both 0.995 (a lower corner alone left a 2.5 cm paint strip over the light band in the middle, the r81 trapezoid of 2026-10-23); L rises
#   1.9 cm from S instead of 3.9.  (A separate value keeps the option of a corner under the edge: the platform's end chord then rises from the corner to E.)
QF_Q17_N = float(os.environ.get('QF_Q17_N', '3'))      # q17 deck drop w(t) = (n+1)/2 t^n - (n-1)/2 t^(n+1) (seam -> edge): n = 3 is the original 2t^3 - t^4; larger n holds the deck up longer and rolls it
#   down at the end (convex throughout, no curvature at the edge)
QF_Q17_XT = float(os.environ.get('QF_Q17_XT', '2.05'))      # q17, where the platform leaves the reading and starts its twist to the level edge (_q17_twist).  It was QF_Q17[2] (capped by
#   QF_Q16_XC 2.2).  With R-1 leaving its line at 2.22 and the edge at 0.995 the platform kept the reading's angle to 2.2 and had 17 cm to lie flat: its lengthwise profiles went flatter,
#   then steeper (y 0.65: -4.8 -> -3.7 -> -11.9 deg; 1 - 2 inflections at y 0.55 - 0.92, the S of review item 2).  From 2.00 they steepen steadily (y 0.65: -4.9 -6.3 -7.3 -7.7 -8.1 deg,
#   y 0.65 - 0.85 without inflection; 2.05 / 2.10 keep one); the cost: the arc leaves the reading by up to 3.9 cm out / 2 cm down at x 2.2 - 2.25 (2.2: 1.7 cm at 2.3; tolerance 6 cm, and
#   at 0.5 m radius the arc is no line).  R-1 holds its line to QF_Q17[2] all the same.
_roll_ = os.environ.get('QF_Q17_ROLL', '0')
QF_Q17_ROLL = tuple(float(v) for v in _roll_.split(',')) if ',' in _roll_ else None      # q17 platform roll (2026-10-24, user: "尾翼的上方也是车身上方的延伸，而且平缓过渡"): (x where the roll starts,
#   its exponent n, the share k of the reading's rate of turn the platform keeps aft of QF_Q16_XC).  The platform keeps the body's angle across the seam (the reading's to QF_Q16_XC, then
#   its own trend) times (1 - W(t)), W = the deck's end-loaded roll (n+1)/2 t^n - (n-1)/2 t^(n+1) from [0] to the edge: the wing's top is the body's top carried on and rolled down
#   to the level edge in the last few cm, as the deck is.  p018: the bright band of the platform (seen from below at 2 deg) runs on past the seam to the tail; the twist from 2.0
#   (QF_Q17_XT, the least-squares 'straightest' law) laid it flat from the seam on: the band stopped there and the near shoulder fell 1.4 cm under the photo's outline at x 2.3.
#   With the roll QF_Q17_XT is not used (both faces follow the reading to QF_Q16_XC).  0: off
QF_EAR = float(os.environ.get('QF_EAR', '7.5'))      # q17 ear step (deg; 0 = off, the window and deck flush with R-1).  2026-10-25 (user: "车后的两个耳朵是不是有一条折线往里折……不是平滑过渡，
#   而是有一个阶梯的" -> "按方案执行"): the ear's inner face (R-3 band beside the rear window and the R-5 triangle on the wing panel) is ONE face folded down inward from R-1.  p013 (sun from one
#   side): it is darker than the deck beside it on the shaded ear (166 / 191) and brighter on the lit one (197 / 178), with the same tone ahead of and behind the seam; r81 at the seam:
#   R-1 4 px (1.7 cm) over the window's corner P3, P3 level with the centre.  The window and the deck sit that much under R-1 (the face ~7.5 deg, 1.75 cm at the seam, 0 at the glass
#   corner and at E); the model had them flush (q13, "三角带与后窗玻璃共面").
QF_Q16_R1 = tuple(float(v) for v in os.environ.get('QF_Q16_R1', '0.80,0.013,1.50').split(','))      # R-1 raised (p018 top outline, user 2026-10-23 "R-1 和后窗玻璃边一起抬高"): by [1] at the tip, a quintic from [0] (G2), straight to E aft; the rear glass edge and centre line rise with it; 0 = off.
#   [2] (2026-10-24, user: "顶梁尾部上边还是有点拱起，应该调成跟实车一样完全平滑"): the quintic runs on past the tip to x [2], G2 with R-1's raised straight line there (the line itself, E and
#   the raise at E unchanged).  Ending at the tip with the line's slope, it flattened the roof rail to -0.074 at x 1.0 before steepening to -0.172 (a hump; p018's top outline is 6 - 9 mm
#   lower over x 1.1 - 1.25); now the slope steepens monotonically from the rail's -0.11 to -0.172.
QF_Q16_U = os.environ.get('QF_Q16_U', 'depth' if QF_Q16_P1 == 'ruled' else 'face')      # 'face': U = where the one ruled face from L (under and behind the window) reaches U's side view (the window is an opening in it); 'depth': U's depth below P1 closes (preview 1)
QF_Q16_FX0 = float(os.environ.get('QF_Q16_FX0', str(0.65 + 11 * 0.55 / 27)))      # 'face': the face's angle law starts here (G2 with the ruled rows L -> U ahead of it)
QF_Q16_AX = os.environ.get('QF_Q16_AX', 'y')      # wl / U move in plan ('y', the user's choice) or in side view ('z', variant)
QF_Q16_UC = os.environ.get('QF_Q16_UC', 'auto')      # the depth's curvature (1/m) at the tip: 'auto' = the one with the smallest peak; 0 = U meets the plane to second order
QF_Q16_P2 = [tuple(float(u) for u in k.split(':')) for k in os.environ.get('QF_Q16_P2', '1.4:20.7,1.55:16.1,1.7:12.6,1.85:9.7,2.0:7.7').split(',')]
# 2026-10-24 (user: "窗尖下方的过渡地带似乎也不够平缓"): 0.12 / 0.25 -> 0.45 / 0.50 m.  p017 has the same tone from the beam face over the arc to the platform under the window tip (175 -> 179,
#   a 5 - 8 level dip at the bottom); the model stepped by 20 levels over 12 px there (blend 10 cm wide at x 1.25), at 0.30 / 0.50 over ~24 px (25 cm), at 0.45 over 37 cm: the reflection lines
#   run on long and regular instead of closing in blobs.  Aft not over 0.50: at 0.60 the arc reaches R-1 at the ear and lowers the beam face 18 mm at x 2.3 (11.5 mm at 0.50, 1 mm at 0.25)
QF_Q16_R = tuple(float(v) for v in os.environ.get('QF_Q16_R', '0.45,0.50,0.5' if QF_Q16_P1 == 'ruled' else '0.25,0.25').split(','))      # radius (m) of the soft arc at the tip and aft (smoothstep between, over the 3rd value's length or to E); 'ruled' (user 2026-10-23 "按第 1 种做，窗尖处圆角收紧"): 0.12 m at the tip, 0.25 m from x 1.7 on: the front rim light's reflection on the roll under the window (p017) is half as wide
QF_Q16_RHO = tuple(float(v) for v in os.environ.get('QF_Q16_RHO', '1.3,6').split(','))      # node densification over the arc, reached when the turn is this many degrees
FOLD_SC_D = float(os.environ.get('FOLD_SC_D', '0.0'))            # extra slope (m/m) of the roll's centre sc(x) at the window tip, a smooth bump of half width X_SC_W (a free parameter for the G1 across tip_lo)
X_SC_W = 0.25
# rearcrease round 4: the roll's BIRTH.  Behind the window the roll peels off U with a radius of 1-6 cm over x 0.9 - 1.05 and its mirror image is a family of fine concentric arcs (p018 v) and a closed oval (p016 h).  The roll
# is now long from the start (ELLW0 at x0 growing to the design length at X_ELLW; its centre moves away from U to make room, sc = S - leg) and the shell blends the straight ruling rows of x <= X_FOLD0 into the fold over
# X_FOLD0 .. X_BIRTH (shell2.p_shoulder): the crease along U fades out instead of turning into a 1 cm roll in one station.
ELLW0 = float(os.environ.get('ELLW0', '0.06'))
X_ELLW = float(os.environ.get('X_ELLW', '0.0'))        # VARIANT (off): the long roll from the start, see X_BIRTH in shell2
FOLD_NB_RATE = float(os.environ.get('FOLD_NB_RATE', '0.55' if QR_ON else '0.65'))      # the fraction of the forward family's rate of th that the aft family continues over X_NB_SLOPE
FOLD_VARIANTS = {
    # 'smooth' (default): the inclined leg leaves U tangent to the glass strip (G1) with a barrel of at most ~12 deg and the net turn T of the roll starts at the crease angle of U (25 deg) and
    #    decreases smoothly to 0 at E.  The apex is 5-6 cm off the reading around the window tip (x 1.1 - 1.3: the glass strip's direction there is 30-38 deg, the reading's fold sits 9 cm
    #    below the glass plane), <= 3.6 cm elsewhere.  No ripple.
    'smooth': dict(T=[(X_FOLD0, 25.5), (0.94, 24.5), (1.0, 21.0), (1.057, 17.0), (1.1, 15.0), (1.15, 13.5), (1.2, 13.0), (1.3, 13.0), (1.45, 12.8), (1.7, 11.5), (1.95, 7.8), (2.2, 3.0), (2.382, 0.0)],
                   b1=[(X_FOLD0, 0.0), (2.382, 0.0)],
                   sc=[(X_FOLD0, 0.305), (0.935, 0.3066), (0.996, 0.3098), (1.057, 0.3156), (1.118, 0.3241), (1.2, 0.339), (1.4, 0.3775), (1.7, 0.4301), (2.0, 0.4927), (2.2, 0.5237), (2.382, 0.53)]),
    # 'path': the apex within 3.2 cm of the reading everywhere; the net turn is 25 deg at the start, 40 deg over the window tip and then dies out; the inclined leg is tangent to the glass strip
    #    at U, so it has to be an S (barrel B2 down to -37 deg) over the window tip: a visible ripple in the shading.  Kept for the record (FOLD_VARIANT=path).
    'path': dict(T=[(X_FOLD0, 25.5), (0.94, 25.0), (1.0, 26.0), (1.057, 32.0), (1.1, 37.0), (1.15, 40.0), (1.2, 40.0), (1.3, 38.0), (1.45, 33.5), (1.7, 25.0), (1.95, 12.5), (2.2, 3.5), (2.382, 0.0)],
                 b1=[(X_FOLD0, 0.0), (2.382, 0.0)],
                 sc=[(X_FOLD0, 0.305), (0.935, 0.3065), (0.996, 0.3094), (1.057, 0.3149), (1.118, 0.3246), (1.2, 0.3399), (1.4, 0.3854), (1.7, 0.4353), (2.0, 0.4924), (2.2, 0.5236), (2.382, 0.53)]),
}
FOLD_VARIANT = os.environ.get('FOLD_VARIANT', 'smooth')
FOLD_K = FOLD_VARIANTS[FOLD_VARIANT]
_FOLD = {}


def _bump(t):
    t = np.clip(np.asarray(t, float), 0.0, 1.0)
    return 30.0 * t * t * (1.0 - t) ** 2            # unit area on [0, 1]; value, slope vanish at both ends (the curvature is continuous)


def _softmin(a, b, k=0.01):
    m = min(a, b)
    return m - k * math.log(math.exp(-(a - m) / k) + math.exp(-(b - m) / k))


def fold_fn(name):
    """smooth design function of x (natural cubic spline through FOLD_K[name]); 'T', 'b1' in radians, 'sc' in metres"""
    if name not in _FOLD:
        k = np.array(FOLD_K[name], float)
        _FOLD[name] = Spline1D(k[:, 0], np.radians(k[:, 1]) if name in ('T', 'b1') else k[:, 1])
    return _FOLD[name]


def fold_ell(x):
    return FOLD_ELL[0] + (FOLD_ELL[1] - FOLD_ELL[0]) * float(sstep(FOLD_ELL[2], FOLD_ELL[3], x))


def fold_curve(S, sc, ell, phi0, th, B1, B2, lam, n=800):
    """the section curve (y, z relative to the lower end L) of arclength S whose curvature is the sum of the three bumps; direction (-cos phi, sin phi): inboard and up"""
    s = np.linspace(0.0, S, n + 1)
    s0 = sc - 0.5 * ell
    kap = np.zeros_like(s)
    if abs(B1) > 0 and s0 > 1e-6:
        kap += (B1 / s0) * _bump(s / s0)
    if abs(th) > 0:
        kap += (th / ell) * _bump((s - s0) / ell)
    if abs(B2) > 0 and lam > 1e-6:
        kap += (B2 / lam) * _bump((s - sc) / lam)            # the barrel starts at the roll's centre (the two bumps overlap over the second half of the roll: a smooth S, no tight radius)
    ds = np.diff(s)
    phi = phi0 + np.r_[0.0, np.cumsum(0.5 * (kap[1:] + kap[:-1]) * ds)]
    dy, dz = -np.cos(phi), np.sin(phi)
    y = np.r_[0.0, np.cumsum(0.5 * (dy[1:] + dy[:-1]) * ds)]
    z = np.r_[0.0, np.cumsum(0.5 * (dz[1:] + dz[:-1]) * ds)]
    return s, y, z, phi, kap


def fold_turn(s, phi, sc, ell):
    """the net turn T of a section: tangent angle at its steepest point minus the angle where the roll starts"""
    i0 = int(np.searchsorted(s, max(sc - 0.5 * ell, 0.0)))
    return float(phi.max() - phi[min(i0, len(phi) - 1)])


def fold_solve(x, a, c, phir=None, sc=None):
    """the cross-section at station x between a = L(x) and c (both (y, z)); phir = the required end direction (the door glass strip's angle at U, forward of / at the tip), else the aft family.
    Newton on (phi0, S, theta [, B2]): end points, net turn T(x) [, tangent at the end]; returns the solution dict (s, y, z, phi, kap grids + parameters)."""
    a, c = np.asarray(a, float), np.asarray(c, float)
    T, B1 = float(fold_fn('T')(x)), float(fold_fn('b1')(x))
    if phir is None:
        # rearcrease (user 2026-10-20: the whole rear shoulder face is nearly flat, slightly concave): aft of the window tip the roll's net turn dies out faster than the design function T
        T *= 1.0 - T_AFT_CUT * float(sstep(X_TIP, X_TIP + X_T_AFT, x))
    sc = float(fold_fn('sc')(x)) if sc is None else float(sc)
    ed = fold_ell(x)
    fwd = phir is not None
    if not fwd:
        tip = fold_tip()
        vv = 1.0 - float(sstep(X_TIP, X_TIP + X_B2_SLOPE, x))             # R1d2: the barrel and its length keep their rate of change across the window tip for a few cm (G1 across tip_lo), then B2 dies out
        B2a = tip['B2'] * (1.0 - float(sstep(X_TIP, X_TIP + X_B2, x))) + tip['dB2'] * (x - X_TIP) * vv
        lama = tip['lam'] + tip['dlam'] * (x - X_TIP) * vv

    def build(q):
        phi0, S, th = q[0], q[1], q[2]
        leg = max(S - sc, 1e-4)
        ell = max(_softmin(ed, FOLD_CAP * leg), 2e-3)
        b2, lam = (q[3], leg) if fwd else (B2a, min(lama, leg))
        return ell, b2, lam, fold_curve(S, sc, ell, phi0, th, B1, b2, lam)

    def f(q):
        ell, b2, lam, (s, y, z, phi, kap) = build(q)
        r = [a[0] + y[-1] - c[0], a[1] + z[-1] - c[1], fold_turn(s, phi, sc, ell) - T]
        if fwd:
            r.append(phi[-1] - phir)
        return np.array(r)

    ch = c - a
    n = 4 if fwd else 3
    q = np.array([math.atan2(ch[1], -ch[0]) - 0.3 * T, float(np.hypot(*ch)) * 1.03, T, -0.5 * T][:n])
    eps = 1e-4 * np.ones(n)                       # tiny ridge on theta / B2: where the inclined leg is a few mm long they are not independent
    eps[0] = eps[1] = 0.0
    for _ in range(80):
        r = f(q)
        if np.abs(r).max() < 1e-10:
            break
        J = np.zeros((len(r), n))
        for k in range(n):
            dq = np.zeros(n); dq[k] = 1e-6
            J[:, k] = (f(q + dq) - r) / 1e-6
        dq = np.linalg.lstsq(np.vstack([J, np.diag(eps)]), -np.r_[r, eps * (q - np.array([0, 0, T, -0.5 * T][:n]))], rcond=None)[0]
        t = 1.0
        for _ in range(12):                       # damped: never accept a step that makes the residual worse
            if np.abs(f(q + t * dq)).max() < np.abs(r).max() or t < 1e-3:
                break
            t *= 0.5
        q = q + t * dq
    ell, b2, lam, (s, y, z, phi, kap) = build(q)
    return dict(x=float(x), a=a, c=c, phi0=float(q[0]), S=float(q[1]), sc=sc, ell=ell, th=float(q[2]), T=T, B1=B1, B2=float(b2), lam=float(lam), s=s, y=y, z=z, phi=phi, kap=kap,
                res=float(np.abs(f(q)).max()))


def fold_solve_nb(x, a, c, phir=None, sc=None, free=False):
    """the BARREL-FREE section at station x (rearcrease round 3): straight shoulder leg, ONE roll (turn th), straight inclined leg.  Forward of / at the tip (phir given): unknowns (phi0, S, th) from the end points and the end
    direction phir (G1 with the door glass strip / the rail band's rung).  Aft of the tip: th is PRESCRIBED: it continues the forward family's value and RATE at the tip (the roll flattens there at about -100 degrees / m, a
    concave-only aft family cannot follow, so th dips a few degrees below 0 over a few cm: G1 across the tip row), and then blends to the design function FOLD_NET (slightly concave face)."""
    if QF_Q13B and not free and phir is None and x > X_TIP:
        return fold_solve_q13b(x, a, c)
    if QF_Q13B and not free and phir is not None and x > QF_PHI13B_X0 and sc is None:
        return fold_solve_fwd13b(x, a, c, phir)
    a, c = np.asarray(a, float), np.asarray(c, float)
    sc_free = sc is None
    sc = float(fold_fn('sc')(x)) if sc is None else float(sc)
    if QF_RS13 and sc_free and phir is None and x > X_TIP:
        sc = fold_sc13(x)
    if QR_ON:
        sc -= QR_SC_D * (1.0 - float(sstep(QR_SC_X1, QR_SC_X2, x)))
    t_ = (x - X_TIP) / X_SC_W
    if abs(t_) < 1.0:
        sc += FOLD_SC_D * (x - X_TIP) * (1.0 - t_ * t_) ** 2
    ed = fold_ell(x)
    fwd = phir is not None
    tth = None
    if not fwd:
        tp = fold_tip_nb()
        g = float(sstep(X_TIP, X_TIP + X_NB_AFT, x))
        vv = 1.0 - float(sstep(0.0, X_NB_SLOPE, x - X_TIP))
        kn = np.array(FOLD_NET, float)
        Nd = float(np.radians(np.interp(x, kn[:, 0], kn[:, 1])))
        tth = (tp['th'] + FOLD_NB_RATE * tp['dth'] * (x - X_TIP) * vv) * (1.0 - g) + Nd * g
        if QF_RS13:
            tth = fold_th13(x, tp['th'], tp['dth'])

    ew =(ELLW0 + (FOLD_ELL[0] - ELLW0) * float(sstep(X_FOLD0, X_ELLW, x))) if (fwd and x < X_ELLW) else 0.0

    def build(q):
        phi0, S, th = q
        if ew > 0.0:
            leg = max(S - sc, ew / FOLD_CAP, 1e-4)
            scx, edx = S - leg, ed
        else:
            leg, scx, edx = max(S - sc, 1e-4), sc, ed
        ell = max(_softmin(edx, FOLD_CAP * leg), 2e-3)
        return ell, scx, fold_curve(S, scx, ell, phi0, th, 0.0, 0.0, leg)

    def f(q):
        ell, scx, (s, y, z, phi, kap) = build(q)
        r = [a[0] + y[-1] - c[0], a[1] + z[-1] - c[1]]
        r.append(phi[-1] - phir if fwd else q[2] - tth)
        return np.array(r)

    ch = c - a
    q = np.array([math.atan2(ch[1], -ch[0]) - 0.1, float(np.hypot(*ch)) * 1.02, 0.1 if tth is None else tth])
    for _ in range(80):
        r = f(q)
        if np.abs(r).max() < 1e-10:
            break
        J = np.zeros((3, 3))
        for k in range(3):
            dq = np.zeros(3); dq[k] = 1e-6
            J[:, k] = (f(q + dq) - r) / 1e-6
        dq = np.linalg.solve(J, -r) if abs(np.linalg.det(J)) > 1e-14 else np.linalg.lstsq(J, -r, rcond=None)[0]
        t = 1.0
        for _ in range(12):
            if np.abs(f(q + t * dq)).max() < np.abs(r).max() or t < 1e-3:
                break
            t *= 0.5
        q = q + t * dq
    ell, scx, (s_, y, z, phi, kap) = build(q)
    return dict(x=float(x), a=a, c=c, phi0=float(q[0]), S=float(q[1]), sc=scx, ell=ell, th=float(q[2]), T=float(q[2]), B1=0.0, B2=0.0, lam=max(q[1] - sc, 1e-4), s=s_, y=y, z=z, phi=phi, kap=kap,
                res=float(np.abs(f(q)).max()), net=float(phi[-1] - q[0]))


def fold_tip_nb():
    """the barrel-free forward family at the window tip: the roll's turn th and its rate there (the aft family continues them)"""
    if 'tip_nb' not in _FOLD:
        L, c, r = CURVES['L'].at(X_TIP), CURVES['U'].at(X_TIP), CURVES['rail'].at(X_TIP)
        phir = math.atan2(r[2] - c[2], -(r[1] - c[1]))
        t = fold_solve_nb(X_TIP, L[1:], c[1:], phir=phir)
        hh = X_B2_H
        b = fold_solve_nb(X_TIP - hh, CURVES['L'].at(X_TIP - hh)[1:], CURVES['U'].at(X_TIP - hh)[1:], phir=fold_glass_dir(X_TIP - hh))
        _FOLD['tip_nb'] = dict(th=t['th'], dth=(t['th'] - b['th']) / hh)
    return _FOLD['tip_nb']


def fold_tip():
    """the forward family at the window tip: B2 / lam / ell there (the aft family continues the barrel from them)"""
    if 'tip' not in _FOLD:
        L, c, r = CURVES['L'].at(X_TIP), CURVES['U'].at(X_TIP), CURVES['rail'].at(X_TIP)
        phir = math.atan2(r[2] - c[2], -(r[1] - c[1]))              # the rail band's last row (tip -> rail) leaves the tip in this direction
        t = fold_solve(X_TIP, L[1:], c[1:], phir=phir)
        hh = X_B2_H
        b = fold_solve(X_TIP - hh, CURVES['L'].at(X_TIP - hh)[1:], CURVES['U'].at(X_TIP - hh)[1:], phir=fold_glass_dir(X_TIP - hh))
        t['dB2'], t['dlam'] = B2_RATE * (t['B2'] - b['B2']) / hh, LAM_RATE * (t['lam'] - b['lam']) / hh      # the forward family's rates of change at the tip (the aft family continues them: G1 across tip_lo)
        _FOLD['tip'] = t
    return _FOLD['tip']


def fold_glass_dir(x):
    """angle (rad) of the door glass strip U -> wl in the cross-section at x (the direction the sliver must leave U in); at the tip: the rail band's last row"""
    U, wl = CURVES['U'].at(x), CURVES['wl'].at(x)
    d = wl - U
    if float(np.hypot(d[1], d[2])) < 1e-6:
        if QF_DG_X[1] > 0.0:          # q13b: at the tip the pane's own angle (the tip row meets the beam top with a convex turn, see build_all)
            return fold_glass_dir(x - 5e-3)
        r = CURVES['rail'].at(x)
        d = r - U
    return math.atan2(d[2], -d[1])


# rearcrease round 4: the glass strip's normal along U has an extremum of its x component at x ~ 0.976 (n_x -0.092 -> -0.119 -> +0.053); a surface that is G1 to the strip along U inherits it, and the contours of the reflection
# bands wrap round it: the concentric arcs (p018 v) and the closed oval (p016 h).  Tilting the shoulder's end direction by a few degrees (FOLD_TILT_DEG, a bump over X_TILT0 .. X_TILT1; VARIANT, off by default: 3 degrees did not remove the loops in the reflect check) was tried.
FOLD_TILT_DEG = float(os.environ.get('FOLD_TILT_DEG', '0.0'))
X_TILT0, X_TILT1 = float(os.environ.get('X_TILT0', '0.894')), float(os.environ.get('X_TILT1', '1.06'))


def fold_end_dir(x):
    """the end direction (rad) of the shoulder's section at U: the glass strip's, plus the small tilt (FOLD_TILT_DEG, a bump over X_TILT0 .. X_TILT1)"""
    ph = fold_glass_dir(x)
    if FOLD_TILT_DEG != 0.0 and X_TILT0 < x < X_TILT1:
        ph += math.radians(FOLD_TILT_DEG) * float(_bump((x - X_TILT0) / (X_TILT1 - X_TILT0))) / 1.875
    return ph


def fold_phi13b(x):
    """q13b: the prescribed shoulder-leg angle (rad) at station x >= QF_PHI13B_X0"""
    if 'phi13b' not in _FOLD:
        x0 = QF_PHI13B_X0
        def free(xv):                   # the rows' own solve forward of x0 (end direction as in fold_row: the crease at U still softening into the roll up to QF_UB_X1)
            L, U = CURVES['L'].at(xv), CURVES['U'].at(xv)
            return fold_solve_nb(xv, L[1:], U[1:], phir=fold_row_dir(xv, L, U), free=True)['phi0']
        v0, d0 = free(x0), (free(x0 + 0.01) - free(x0 - 0.01)) / 0.02
        kn = [(x0, v0)] + [(k[0], math.radians(k[1])) for k in QF_PHI13B if k[0] > x0]
        _FOLD['phi13b'] = Spline1D([k[0] for k in kn], [k[1] for k in kn], 'clamped', d0, 0.0)
    return float(_FOLD['phi13b'](min(x, QF_PHI13B[-1][0])))


def fold_solve_fwd13b(x, a, c, phir):
    """q13b: the forward family with the shoulder leg's angle prescribed: unknowns (sc, S, th) from the end points and the end direction (the pane's)"""
    a, c = np.asarray(a, float), np.asarray(c, float)
    phi0 = fold_phi13b(x)
    ed = fold_ell(x)

    def build(q):
        sc, S, th = q
        leg = max(S - sc, 1e-4)
        ell = max(_softmin(ed, FOLD_CAP * leg), 2e-3)
        return ell, fold_curve(S, sc, ell, phi0, th, 0.0, 0.0, leg)

    def f(q):
        ell, (s, y, z, phi, kap) = build(q)
        return np.array([a[0] + y[-1] - c[0], a[1] + z[-1] - c[1], phi[-1] - phir])
    ref = fold_solve_nb(x, a, c, phir=phir, free=True)
    q = np.array([ref['sc'], ref['S'], ref['th']])
    for _ in range(80):
        r = f(q)
        if np.abs(r).max() < 1e-10:
            break
        J = np.zeros((3, 3))
        for k in range(3):
            dq = np.zeros(3); dq[k] = 1e-7
            J[:, k] = (f(q + dq) - r) / 1e-7
        dq = np.linalg.lstsq(J, -r, rcond=None)[0]
        t = 1.0
        for _ in range(14):
            if np.abs(f(q + t * dq)).max() < np.abs(r).max() or t < 1e-4:
                break
            t *= 0.5
        q = q + t * dq
    ell, (s_, y, z, phi, kap) = build(q)
    return dict(x=float(x), a=a, c=c, phi0=phi0, S=float(q[1]), sc=float(q[0]), ell=ell, th=float(q[2]), T=float(q[2]), B1=0.0, B2=0.0, lam=max(q[1] - q[0], 1e-4), s=s_, y=y, z=z,
                phi=phi, kap=kap, res=float(np.abs(f(q)).max()), net=float(phi[-1] - phi0))


def fold_tip13b():
    """q13b: the tip row (the forward family at the window tip: L -> roll -> tip, arriving at the pane's angle) and the convex turn at the tip into the rung tip -> ridge start"""
    if 'tip13b' not in _FOLD:
        L, U, r = CURVES['L'].at(X_TIP), CURVES['U'].at(X_TIP), CURVES['rail'].at(X_TIP)
        t = fold_solve_nb(X_TIP, L[1:], U[1:], phir=fold_end_dir(X_TIP))
        rung = math.atan2(r[2] - U[2], -(r[1] - U[1]))
        _FOLD['tip13b'] = dict(th=t['th'], sc=t['sc'], ell=t['ell'], S=t['S'], cv=float(t['phi'][-1] - rung), dc=float(np.hypot(r[1] - U[1], r[2] - U[2])))
    return _FOLD['tip13b']


def fold_curve2(S, sc, ell, phi0, th, sc2, ell2, th2, n=800):
    """q13b: fold_curve with ONE concave roll (th at sc, length ell) and one convex roll (-th2 at sc2, length ell2)"""
    s = np.linspace(0.0, S, n + 1)
    if th2 > 0.0 and ell2 > 1e-6:          # a few mm wide just aft of the tip: its own fine grid, so the turn integrates to th2 exactly
        s = np.union1d(s, np.clip(np.linspace(sc2 - 0.5 * ell2, sc2 + 0.5 * ell2, 41), 0.0, S))
    kap = (th / ell) * _bump((s - (sc - 0.5 * ell)) / ell)
    if th2 > 0.0 and ell2 > 1e-6:
        kap -= (th2 / ell2) * _bump((s - (sc2 - 0.5 * ell2)) / ell2)
    ds = np.diff(s)
    phi = phi0 + np.r_[0.0, np.cumsum(0.5 * (kap[1:] + kap[:-1]) * ds)]
    dy, dz = -np.cos(phi), np.sin(phi)
    y = np.r_[0.0, np.cumsum(0.5 * (dy[1:] + dy[:-1]) * ds)]
    z = np.r_[0.0, np.cumsum(0.5 * (dz[1:] + dz[:-1]) * ds)]
    return s, y, z, phi, kap


def fold_q13b_params(x):
    """q13b: the aft family's design functions at station x: concave roll (th, sc, ell), convex roll (th2, ell2, its distance dc from the ridge end)"""
    tp = fold_tip13b()
    t = min(max((x - X_TIP) / QF_CV[0], 0.0), 1.0)
    # the convex turn fades from the tip on with the initial rate QF_CV_A (du/dt): with a zero start rate the beam-top strip (convex turn -> ridge) first tipped back by ~0.7 deg as the
    # leg's angle and the roll declined, and that dip was a closed loop in the reflections just aft of the tip
    u0 = float(sstep(X_TIP, X_TIP + QF_CV[0], x))
    u = u0 + QF_CV_A * t * (1.0 - t) ** 2
    kn = np.array([(X_TIP, math.degrees(tp['th']))] + [k for k in QF_TH13B if k[0] > X_TIP], float)
    th = math.radians(float(np.interp(x, kn[:, 0], kn[:, 1]) if len(kn) < 3 else pchip([tuple(k) for k in kn], x)))
    if 'sc13b' not in _FOLD:            # the roll's centre aft of the tip: clamped spline from the tip row's (with the forward family's rate) through QF_SC13B
        e = 0.02
        Lm_, Um_ = CURVES['L'].at(X_TIP - e), CURVES['U'].at(X_TIP - e)
        d0 = (tp['sc'] - fold_solve_nb(X_TIP - e, Lm_[1:], Um_[1:], phir=fold_end_dir(X_TIP - e))['sc']) / e
        kn = [(X_TIP, tp['sc'])] + [k for k in QF_SC13B if k[0] > X_TIP]
        _FOLD['sc13b'] = Spline1D([k[0] for k in kn], [k[1] for k in kn], 'clamped', d0, 0.0)
    sc = float(_FOLD['sc13b'](min(x, QF_SC13B[-1][0])))
    ell = tp['ell'] + (fold_ell(x) - tp['ell']) * u0
    th2 = tp['cv'] * (1.0 - u)
    ell2 = QF_CV[1] + (QF_CV[2] - QF_CV[1]) * (1.0 - (1.0 - t) ** QF_CV_P)
    return th, sc, ell, th2, ell2, tp['dc']


def fold_solve_q13b(x, a, c, th=None, sc=None, phi0=None):
    """q13b: the aft family: the concave roll of the soft arc (prescribed turn and centre: QF_TH13B / QF_SC13B, from the tip row's) and the convex turn at the window tip fading out over QF_CV[0];
    unknowns phi0, S from the two end points"""
    a, c = np.asarray(a, float), np.asarray(c, float)
    th_, sc_, ell, th2, ell2, dc = fold_q13b_params(x)
    fit = th is not None                   # (the arc fit passes th and sc: then phi0 is the unknown; the design passes neither: th is the unknown)
    th0 = th_ if th is None else th
    sc = sc_ if sc is None else sc
    p0 = fold_phi13b(x) if phi0 is None else phi0

    def build(q):
        u, S = q
        th, phi0 = (th0, u) if fit else (u, p0)
        e = max(_softmin(ell, FOLD_CAP * max(S - sc, 1e-3)), 2e-3)
        s2 = S - dc                      # (the two rolls may overlap: their curvatures add)
        return e, s2, fold_curve2(S, sc, e, phi0, th, s2, ell2, th2)

    def f(q):
        e, s2, (s, y, z, phi, kap) = build(q)
        return np.array([a[0] + y[-1] - c[0], a[1] + z[-1] - c[1]])
    ch = c - a
    q = np.array([math.atan2(ch[1], -ch[0]) - 0.4 * (th0 - th2) if fit else th0, float(np.hypot(*ch)) * 1.02])
    for _ in range(60):
        r = f(q)
        if np.abs(r).max() < 1e-11:
            break
        J = np.zeros((2, 2))
        for k in range(2):
            dq = np.zeros(2); dq[k] = 1e-7
            J[:, k] = (f(q + dq) - r) / 1e-7
        dq = np.linalg.lstsq(np.vstack([J, 1e-6 * np.eye(2)]), np.r_[-r, 0.0, 0.0], rcond=None)[0]
        t = 1.0
        for _ in range(14):
            qn = q + t * dq
            if np.abs(f(qn)).max() < np.abs(r).max() or t < 1e-4:
                break
            t *= 0.5
        q = qn
    e, s2, (s, y, z, phi, kap) = build(q)
    th, phi0 = (th0, float(q[0])) if fit else (float(q[0]), p0)
    return dict(x=float(x), a=a, c=c, phi0=phi0, S=float(q[1]), sc=sc, ell=e, th=th, T=th, B1=0.0, B2=0.0, lam=max(q[1] - sc, 1e-4), s=s, y=y, z=z, phi=phi, kap=kap,
                res=float(np.abs(f(q)).max()), net=float(phi[-1] - phi0), th2=th2, s2=s2, ell2=ell2)


def q14_faces():
    """q14: the two planes and the platform's twist (cached): beam plane n1 . p = d1, pane plane n2 . p = d2 (normals pointing up), their section angles ph1, ph2, phi3(x)"""
    if 'q14' not in _FOLD:
        T, U0 = np.asarray(CURVES['U'].at(X_TIP), float), np.asarray(CURVES['U'].at(X_FOLD0), float)
        C0, E = np.asarray(REAR['C0'], float), np.asarray(REAR['E'], float)
        n1 = np.cross(E - C0, (np.asarray(CURVES['L'].at(X_TIP), float) if QF_Q15 else T) - C0)
        n1 *= np.sign(n1[2]) / np.linalg.norm(n1)
        ph2 = fold_glass_dir(X_TIP)
        sn, cs = math.sin(ph2), math.cos(ph2)
        kx = ((sn * T[1] + cs * T[2]) - (sn * U0[1] + cs * U0[2])) / (U0[0] - T[0])
        n2 = np.array([kx, sn, cs])

        def chord(x):
            L, U = CURVES['L'].at(x), CURVES['U'].at(x)
            return math.atan2(U[2] - L[2], L[1] - U[1])
        e = 0.005
        LE = CURVES['L'].at(E[0])
        kn = [(X_FOLD0, chord(X_FOLD0))] + [(k[0], math.radians(k[1])) for k in QF_P3 if X_FOLD0 < k[0] < E[0]] + [(E[0], math.atan2(E[2] - LE[2], LE[1] - E[1]))]
        p3 = Spline1D([k[0] for k in kn], [k[1] for k in kn], 'clamped', (chord(X_FOLD0) - chord(X_FOLD0 - e)) / e, 0.0)
        if QF_Q15:
            kn = [(X_TIP, math.atan2(n1[1], n1[2]))] + [(k[0], math.radians(k[1])) for k in QF_P3B if X_TIP < k[0] < E[0]] + kn[-1:]
            if QF_P3B_D0 == 'auto':
                # the band under the window (straight L -> U, U tangent to the plane at the tip) leaves the plane with the rate (1 - t) h_L' along the row (h_L: L above the plane):
                # the platform's rows match it to first order with d tan(phi3) / dx = -h_L' / (L_y - T_y)
                hl = lambda xv: float(CURVES['L'].at(xv)[2] - (n1 @ C0 - n1[0] * xv - n1[1] * CURVES['L'].at(xv)[1]) / n1[2])
                dt = -(hl(X_TIP) - hl(X_TIP - e)) / e / float(CURVES['L'].at(X_TIP)[1] - T[1])
                d0 = dt * math.cos(kn[0][1]) ** 2
            else:
                d0 = math.radians(float(QF_P3B_D0))
            p3 = Spline1D([k[0] for k in kn], [k[1] for k in kn], 'clamped', d0, 0.0)
        _FOLD['q14'] = dict(n1=n1, d1=float(n1 @ C0), n2=n2, d2=float(n2 @ T), ph1=math.atan2(n1[1], n1[2]), ph2=ph2, p3=p3, xe=float(E[0]))
    return _FOLD['q14']


def _smin(a, b, k):
    """cubic smooth minimum (C2) of two graphs; k = the blend size in their difference"""
    if k <= 1e-9:
        return np.minimum(a, b)
    h = np.maximum(k - np.abs(a - b), 0.0) / k
    return np.minimum(a, b) - h ** 3 * k / 6.0


def fold_solve_q14(x, a, c, ax=None, cx=None):
    """q14: the row between a = L (y, z) and c = U (forward of / at the tip) or the crest R-1 (aft): smooth max(platform, smooth min(pane, beam)); returns a solution dict like fold_solve_nb's"""
    g = q14_faces()
    a, c = np.asarray(a, float), np.asarray(c, float)
    ax = x if ax is None else ax
    cx = x if cx is None else cx
    fwd = x <= X_TIP + 1e-9
    if QF_Q15 and fwd:                  # under the window: the straight ruling L -> U (the band runs into the beam plane at the tip)
        u = np.linspace(0.0, 1.0, 2401)
        y, z = a[0] + (c[0] - a[0]) * u, a[1] + (c[1] - a[1]) * u
        s = u * float(np.hypot(*(c - a)))
        ph = math.atan2(c[1] - a[1], a[0] - c[0])
        return dict(x=float(x), a=a, c=c, phi0=ph, S=float(s[-1]), sc=float(s[-1]), ell=0.0, th=0.0, T=0.0, B1=0.0, B2=0.0, lam=1e-4, s=s, y=y - a[0], z=z - a[1],
                    phi=np.full_like(s, ph), kap=np.zeros_like(s), res=0.0, net=0.0, th2=0.0, s2=float(s[-1]), ell2=0.0, cv=g['ph2'] - g['ph1'], straight=True)
    ph3 = float(g['p3'](min(x, g['xe'])))
    ph2 = g['ph2']
    if fwd and x < QF_P2R:
        L_, U_ = CURVES['L'].at(x), CURVES['U'].at(x)
        ch = math.atan2(U_[2] - L_[2], L_[1] - U_[1])
        tr = min(max((x - X_FOLD0) / (QF_P2R - X_FOLD0), 0.0), 1.0)
        ph2 = ch + (ph2 - ch) * (1.0 - (1.0 - tr) ** QF_P2E)     # (a linear start: the fold peels off U, not off L)
    t1, t2, t3 = math.tan(g['ph1']), math.tan(ph2), math.tan(ph3)
    u = np.linspace(0.0, 1.0, 2401)
    y = a[0] + (c[0] - a[0]) * u
    xs = ax + (cx - ax) * u
    z3 = a[1] + (a[0] - y) * t3
    n1, n2 = g['n1'], g['n2']
    z2 = c[1] + (c[0] - y) * t2 if fwd else (g['d2'] - n2[0] * xs - n2[1] * y) / n2[2]
    kw, tent = 0.0, None
    if fwd:
        up = z2
    else:
        z1 = (g['d1'] - n1[0] * xs - n1[1] * y) / n1[2]
        if QF_Q15:
            z2 = z1 + 1.0                # (no pane: the beam plane alone)
            tent = None
            wt = 1.0 - float(sstep(X_TIP, X_TIP + QF_TF, x))
            if wt > 0.0:
                # the window line U rises through the plane into the tip (its height above the plane grows ~0.45 m / m there) and the band under it with it (the share t of the row
                # from L), while the rail band above the window lies in the plane: right behind the tip the row carries the band's rise on (its height t * rate * (x - tip)) and lets it go
                # over QF_TF; inboard of the tip's row point it drops to nothing over a width growing from 0 at the tip (QF_TK (x - tip)): C1 with the band, nothing on the rail band
                T_, L_ = (np.asarray(CURVES[k].at(X_TIP), float) for k in ('U', 'L'))
                hU = lambda xv: float(CURVES['U'].at(xv)[2] - (g['d1'] - n1[0] * xv - n1[1] * CURVES['U'].at(xv)[1]) / n1[2])
                amp = wt * (hU(X_TIP) + (x - X_TIP) * (hU(X_TIP) - hU(X_TIP - 0.005)) / 0.005)
                dk = _softmin(QF_TK * (x - X_TIP), 0.7 * (T_[1] - c[0]), 0.005) + 1e-4      # (and it is gone well before R-1)
                lin, drop = (L_[1] - y) / (L_[1] - T_[1]), 1.0 - (T_[1] - y) / dk
                tent = amp * -_smin(-_smin(lin, drop, 0.3), np.zeros_like(y), 0.15)
        else:
            tw = min(max((x - X_TIP) / QF_WE[1], 0.0), 1.0)
            kw = QF_WE[0] * (t2 - t1) * (1.0 - (1.0 - tw) ** 2)
        up = _smin(z2, z1, kw)
    sup = t1 if QF_Q15 else t2 + (t1 - t2) * float(sstep(QF_KUP[0], QF_KUP[1], x))
    kf = max(pchip([(X_FOLD0, 0.0)] + QF_FW, x), 0.0) * (max(sup - t3, QF_KMIN) if QF_Q15 else max(sup - t3, 0.0))
    # (q15: near the tip the platform and the plane are nearly one plane: there the round is spread wide instead of becoming a fine line that sweeps across the face)
    # where the round reaches the row's end (at its birth on U, at the ear where the beam plane runs out on R-1) the face it rounds into is lowered there just enough for the row to
    # end on its end point: the crease at U softens into the fold, the fold fades into R-1 at the ear, and the round is never squeezed into a crease the mesh cannot carry
    za, zc = z3[-1], up[-1]

    def endz(dl):
        return float(-_smin(np.array([-za]), np.array([-(zc - dl)]), kf)[0])
    dl = 0.0
    if kf > 0.0 and endz(0.0) > c[1] + 1e-12:
        lo, hi = 0.0, kf + abs(zc - za)
        for _ in range(60):
            dl = 0.5 * (lo + hi)
            lo, hi = (dl, hi) if endz(dl) > c[1] else (lo, dl)
        dl = 0.5 * (lo + hi)
    if dl > 0.0:
        if fwd:
            up = up - dl
        else:
            up = _smin(z2, z1 - dl, kw)
    z = -_smin(-z3, -up, kf)
    if QF_Q15 and not fwd and tent is not None:
        z = z + tent
    dy, dz = np.diff(y), np.diff(z)
    s = np.r_[0.0, np.cumsum(np.hypot(dy, dz))]
    phi = np.arctan2(np.gradient(z), -np.gradient(y))
    kap = np.gradient(phi) / np.maximum(np.gradient(s), 1e-12)
    i = int(np.argmax(up >= z3)) if np.any(up >= z3) else len(s) - 1
    blend = np.abs(z3 - up) < kf
    sc, ell = float(s[i]), (float(s[blend].max() - s[blend].min()) if blend.any() else 0.0)
    out = dict(x=float(x), a=a, c=c, phi0=ph3, S=float(s[-1]), sc=sc, ell=ell, th=float(math.atan(sup) - ph3), T=0.0, B1=0.0, B2=0.0, lam=max(float(s[-1]) - sc, 1e-4),
               s=s, y=y - a[0], z=z - a[1], phi=phi, kap=kap, res=0.0, net=float(phi[-1] - phi[0]), th2=0.0, s2=sc, ell2=0.0, cv=g['ph2'] - g['ph1'])
    if not fwd and not QF_Q15:
        j = int(np.argmax(z2 >= z1)) if np.any(z2 >= z1) else len(s) - 1
        we = np.abs(z2 - z1) < kw
        s2, ell2 = float(s[j]), (float(s[we].max() - s[we].min()) if we.any() else 0.0)
        # how much of the edge is left: it fades as the platform's round runs over it (where the pane runs out); a continuous measure (the solved turn left of it jumps when the fold crosses it)
        r = min(max((up[j] - z3[j]) / max(kf, 1e-6), -1.0), 1.0)
        f = 1.0 - 0.5 * (1.0 - r) ** 2 if r >= 0.0 else 0.5 * (1.0 + r) ** 2        # the share of the edge's turn that the platform's round lets through (d smax / d upper)
        out.update(th2=f * (g['ph2'] - g['ph1']), s2=s2, ell2=ell2, anc=min(1.0, f / 0.15))
    return out


_Q16 = {}


def q16_plane():
    """q16: the plane P1 (unit normal n pointing up, n . p = d)"""
    if 'n' not in _Q16:
        c0, e = np.asarray(CURVES['rail'].at(X_TIP), float), np.asarray(E_TARGET, float)
        n = np.cross(e - c0, np.asarray(CURVES['L'].at(X_TIP), float) - c0)
        n *= np.sign(n[2]) / np.linalg.norm(n)
        _Q16.update(n=n, d=float(n @ c0))
    return _Q16['n'], _Q16['d']


def q16_p2(x):
    """q16: the platform's section angle (rad) aft of the tip: a clamped spline from the plane's angle at the tip, leaving it with the rate of the rows under the window (L -> U, C1 across the
    tip row), through QF_Q16_P2 to the chord L -> E at the tail"""
    if 'p2' not in _Q16:
        n, _ = q16_plane()
        E = np.asarray(E_TARGET, float)

        def chord(xv):
            L, U = CURVES['L'].at(xv), CURVES['U'].at(xv)
            return math.atan2(U[2] - L[2], L[1] - U[1])
        th1, e = math.atan2(n[1], n[2]), 1e-3
        LE = CURVES['L'].at(E[0])
        kn = [(X_TIP, th1)] + [(k[0], math.radians(k[1])) for k in QF_Q16_P2 if X_TIP < k[0] < E[0]] + [(E[0], math.atan2(E[2] - LE[2], LE[1] - E[1]))]
        _Q16['p2'] = Spline1D([k[0] for k in kn], [k[1] for k in kn], 'clamped', (chord(X_TIP) - chord(X_TIP - e)) / e, 0.0)
        _Q16['xe'] = float(E[0])
    return float(_Q16['p2'](min(x, _Q16['xe'])))


def _e_tail():
    """the ear tip E; with QF_Q17 at the level tail top edge's height"""
    return np.array([E_TARGET[0], E_TARGET[1], QF_Q17[0] if QF_Q17 else E_TARGET[2]], float)


def _q16_raw(x):
    """q16 'ruled': the section angles (rad) of L -> reading (platform) and reading -> R-1 (beam face) at x"""
    L, A, R = CURVES['L'].at(x), _Q16['rd'].at(x), CURVES['rail'].at(x)
    return np.arctan2(A[..., 2] - L[..., 2], L[..., 1] - A[..., 1]), np.arctan2(R[..., 2] - A[..., 2], A[..., 1] - R[..., 1])


def _q17_twist(xc, xe, thE):
    """QF_Q17_TW: the platform's angle over xc .. xe (a Spline1D of rad), least squares: the platform's lengthwise profiles (z = L_z + (L_y - y) tan(angle), y from the reading to L) as
    straight as they can be (sum of z_xx^2) plus QF_Q17_TW[1] times the angle's third difference; the reading's own angle (and so its rate and curvature) up to xc, thE at the edge.
    (review 2026-10-23, item 2: going on to the ruling L -> R-1 at the edge, the platform had to turn at 0.76 rad/m there -- L rises 4 deg into the corner, R-1 falls 19 deg to E --
    and its profiles ran -4 -> -1 -> -8 deg between S and the edge, an S in the zebra at the tail corners; R-1's height over the platform is the beam face's, to the edge)"""
    h = 2.5e-3
    xg = np.arange(xc - 3 * h, xe + 0.5 * h, h)
    xg[-1] = xe
    n = len(xg)
    Lg, Ag = CURVES['L'].at(xg), np.asarray(_Q16['rd'].at(xg), float)
    g = np.tan(_q16_raw(np.minimum(xg, xc))[0])
    g[-1] = math.tan(thE)
    i0 = int(np.searchsorted(xg, xc + 1e-9))
    rows, rhs = [], []
    for i in range(i0 - 1, n - 1):
        lyp, lypp = (Lg[i + 1, 1] - Lg[i - 1, 1]) / (2 * h), (Lg[i + 1, 1] - 2 * Lg[i, 1] + Lg[i - 1, 1]) / h ** 2
        lzpp = (Lg[i + 1, 2] - 2 * Lg[i, 2] + Lg[i - 1, 2]) / h ** 2
        for y in np.arange(Ag[i, 1] + 0.03, Lg[i, 1] - 0.01, 0.01):
            dd_ = Lg[i, 1] - y
            c = np.zeros(n)
            c[i - 1], c[i], c[i + 1] = -lyp / h + dd_ / h ** 2, lypp - 2 * dd_ / h ** 2, lyp / h + dd_ / h ** 2
            rows.append(c); rhs.append(-lzpp)
    for i in range(i0 - 2, n - 2):
        c = np.zeros(n)
        c[i - 1], c[i], c[i + 1], c[i + 2] = -1.0, 3.0, -3.0, 1.0
        rows.append(math.sqrt(QF_Q17_TW[1]) * c / h ** 3); rhs.append(0.0)
    M, b = np.array(rows), np.array(rhs)
    fr = np.arange(i0, n - 1)
    fx = np.setdiff1d(np.arange(n), fr)
    g[fr] = np.linalg.lstsq(M[:, fr], b - M[:, fx] @ g[fx], rcond=None)[0]
    return Spline1D(xg, np.arctan(g))


def q16_ruled(x):
    """q16 'ruled': (platform angle, beam face angle) in section at x (rad, arrays like x): the reading's own up to QF_Q16_XC; aft of it the platform goes on (C2) to L -> E at the ear tip
    (zero rate there, as in 'plane') and the beam face carries on its own trend (C2, quadratic)"""
    x = np.asarray(x, float)
    if 'rc' not in _Q16:
        # (q17: the platform leaves the reading where R-1 and L start to move, and reaches the level tail edge still turning: at the rate that keeps the platform's lengthwise profiles
        # monotone, rising into the corner with L within QF_Q17_L[3] of it, falling to the edge inboard of that; arriving flat (rate 0) it put a 0.9 mm trough before the edge)
        xc, e = (min(QF_Q16_XC, QF_Q17_XT) if QF_Q17 and not QF_Q17_ROLL else QF_Q16_XC), 5e-3
        t2, t1 = _q16_raw(np.array([xc - e, xc, xc + e]))
        dd = lambda t: (float(t[1]), float(t[2] - t[0]) / (2 * e), float(t[2] - 2 * t[1] + t[0]) / e ** 2)
        E = _e_tail()
        LE = CURVES['L'].at(E[0])
        xe = 0.5 * (QF_Q17_L[1] + float(E[0])) if QF_Q17 else float(E[0])      # (q17: flat at the tail edge's own row, L's end -> E, mid x 2.375: at E's x the last rows met the edge 1 mm low)
        se = 0.0
        if QF_Q17 and 'l17' in _Q16:
            # the platform's rate of turn at the edge: its lengthwise slope goes from L's (rising into the corner) to R-1's (falling to E) linearly across, as a ruling L -> R-1 would (with a
            # fixed pivot R-1 fell faster than the platform beside it, the beam face kept a height to the edge and, laid flat, stood over the platform: a 2 mm lip before the edge)
            Rr, Rl = CURVES['rail'].at(np.array([xe - e, xe + e])), CURVES['L'].at(min(xe, QF_Q17_L[1]))
            sr = float(Rr[1, 2] - Rr[0, 2]) / (2 * e)
            se = -_Q16['l17'][2] / QF_Q17_L[3] if QF_Q17_L[3] > 0.0 else (sr - _Q16['l17'][2]) / float(Rl[1] - 0.5 * (Rr[0, 1] + Rr[1, 1]))
        _Q16['rc'] = (xc, dd(t2), dd(t1), xe, math.atan2(E[2] - LE[2], LE[1] - E[1]), se)
        if QF_Q17 and QF_Q17_TW:
            _Q16['tw'] = _q17_twist(xc, xe, _Q16['rc'][4])
    xc, p2, p1, xe, thE, se = _Q16['rc']
    t2, t1 = _q16_raw(np.minimum(x, xc))
    dx = np.maximum(x - xc, 0.0)
    if 'tw' in _Q16:
        a2 = np.where(x <= xc, t2, _Q16['tw'](np.clip(x, xc, xe)))
    else:
        a2 = np.where(x <= xc, t2, quint1(np.minimum(x, xe), xc, *p2, xe, thE, se, 0.0))
    if QF_Q17 and QF_Q17_ROLL:
        # QF_Q17_ROLL: the reading's angle to xc, its own trend aft (k of its rate), rolled down to the level edge by the deck's end-loaded W
        x0, n_, k_ = QF_Q17_ROLL
        base = np.where(x <= xc, t2, p2[0] + k_ * p2[1] * dx)
        t_ = np.clip((x - x0) / (xe - x0), 0.0, 1.0)
        W_ = 0.5 * (n_ + 1) * t_ ** n_ - 0.5 * (n_ - 1) * t_ ** (n_ + 1)
        a2 = np.arctan(np.tan(base) * (1.0 - W_) + np.tan(thE) * W_)
    a1 = np.where(x <= xc, t1, p1[0] + p1[1] * dx + 0.5 * p1[2] * dx * dx)
    if 'tw' in _Q16 and len(QF_Q17_L) > 4:
        # QF_Q17_TW: R-1 stands over the platform (gap) to the edge; the beam face takes it: its width (from R-1 to where it meets the platform) goes from the one its own trend gives
        # to QF_Q17_TW[0] at the edge, from QF_Q17_L[4] on (G2 with the trend there).  Both angles reach thE at the edge, the arc between them fades there
        xw = QF_Q17_L[4]
        Lx, Rx = CURVES['L'].at(np.clip(x, xw, xe)), CURVES['rail'].at(np.clip(x, xw, xe))
        g2 = np.tan(a2)
        gap = np.maximum(Rx[..., 2] - Lx[..., 2] - (Lx[..., 1] - Rx[..., 1]) * g2, 0.0)
        wt = gap / np.maximum(np.tan(a1) - g2, 1e-6)
        w = wt + (QF_Q17_TW[0] - wt) * sstep(xw, xe, x)
        a1 = np.where(x <= xw, a1, np.arctan(g2 + gap / np.maximum(w, 1e-6)))
    elif QF_Q17 and len(QF_Q17_L) > 4:
        # q17: the beam face's height (R-1 over the platform) goes to nothing at the level edge; at its own angle it ended as a 9 deg crease beside R-1, so it lies down onto the platform
        wf = quint1(np.minimum(x, xe), QF_Q17_L[4], 0.0, 0.0, 0.0, xe, 1.0, 0.0, 0.0)
        a1 = a1 + (a2 - a1) * wf
    return a2, a1


def q16_face(x):
    """q16 'ruled': the beam face's line in section x: (y_R, z_R, slope) with z = z_R + (y_R - y) * slope"""
    R = CURVES['rail'].at(x)
    return R[..., 1], R[..., 2], np.tan(q16_ruled(x)[1])


def q16_section_ruled(x, a, c):
    """q16 'ruled': the row between a = L and c = U (forward of / at the tip) or R-1 (aft): smooth max of the platform (through L) and the beam face (through c), which meet on the arc
    reading.  Forward of the tip the face is the strip reading -> U (the window is an opening in the face); the roll there is sized to the strip (kf of its width, the size behind the tip
    at the tip) and so grows from nothing where the reading leaves U"""
    u = np.linspace(0.0, 1.0, 2401)
    y = a[0] + (c[0] - a[0]) * u
    if x <= X_TIP + 1e-9:
        A = np.asarray(_Q16['rd'].at(x), float)[1:]
        ws = A[0] - c[0]
        if ws < 2e-4 or a[0] - A[0] < 2e-4:
            return None
        t2, t1 = (A[1] - a[1]) / (a[0] - A[0]), (c[1] - A[1]) / ws
        if 'kf' not in _Q16:
            # kf: the roll's size under the window per strip width and slope step, so that it equals the size behind the tip at the tip; and a bump (C1) in the last QF_Q16_KD before
            # the tip that hands its RATE over too (the strip widens fast there, the roll behind the tip shrinks: kf alone left a 2.2 deg lengthwise kink across the roll at the tip row)
            def gap(xv):
                L_, A_, U_ = CURVES['L'].at(xv), np.asarray(_Q16['rd'].at(xv), float), CURVES['U'].at(xv)
                g2_, g1_ = (A_[2] - L_[2]) / (L_[1] - A_[1]), (U_[2] - A_[2]) / (A_[1] - U_[1])
                return (A_[1] - U_[1]) * (g1_ - g2_)

            def kaft(xv):
                th2_, th1_ = q16_ruled(xv)
                g2_, g1_ = math.tan(float(th2_)), math.tan(float(th1_))
                w_ = float(sstep(X_TIP, X_TIP + QF_Q16_R[2] if len(QF_Q16_R) > 2 else float(E_TARGET[0]), xv))
                return (QF_Q16_R[0] + (QF_Q16_R[1] - QF_Q16_R[0]) * w_) * (g1_ - g2_) ** 2 / (1.0 + (0.5 * (g1_ + g2_)) ** 2) ** 1.5
            e = 2e-3
            kt, gt = kaft(X_TIP), gap(X_TIP)
            _Q16['kf'] = kt / gt
            _Q16['kc'] = (kt / gt * (gt - gap(X_TIP - e)) / e - (kaft(X_TIP + e) - kt) / e) / kt
        um = X_TIP - x
        k = _Q16['kf'] * ws * max(t1 - t2, 0.0) * ((1.0 + _Q16['kc'] * um * (1.0 - um / QF_Q16_KD) ** 2) if um < QF_Q16_KD else 1.0)
    else:
        th2, th1 = q16_ruled(x)
        t2, t1 = math.tan(float(th2)), math.tan(float(th1))
        w = float(sstep(X_TIP, X_TIP + QF_Q16_R[2] if len(QF_Q16_R) > 2 else float(E_TARGET[0]), x))
        r = QF_Q16_R[0] + (QF_Q16_R[1] - QF_Q16_R[0]) * w
        k = r * max(t1 - t2, 0.0) ** 2 / (1.0 + (0.5 * (t1 + t2)) ** 2) ** 1.5
    z2 = a[1] + (a[0] - y) * t2
    z1 = c[1] + (c[0] - y) * t1
    smax = lambda p, q: -_smin(-np.atleast_1d(p), -np.atleast_1d(q), k)
    dl = 0.0
    if float(smax(z2[-1], z1[-1])[0]) > c[1] + 1e-12:
        lo, hi = 0.0, k + abs(z1[-1] - z2[-1])
        for _ in range(60):
            dl = 0.5 * (lo + hi)
            lo, hi = (dl, hi) if float(smax(z2[-1], z1[-1] - dl)[0]) > c[1] else (lo, dl)
        dl = 0.5 * (lo + hi)
    z = smax(z2, z1 - dl)
    s = np.r_[0.0, np.cumsum(np.hypot(np.diff(y), np.diff(z)))]
    up = z1 - dl
    i = int(np.argmax(up >= z2)) if np.any(up >= z2) else len(s) - 1
    blend = np.abs(z2 - up) < k
    sc, ell = float(s[i]), (float(s[blend].max() - s[blend].min()) if blend.any() else 0.0)
    return dict(x=float(x), a=a, c=c, phi0=math.atan(t2), S=float(s[-1]), sc=sc, ell=ell, th=math.atan(t1) - math.atan(t2), s=s, y=y - a[0], z=z - a[1], dl=dl, k=k)


def q16_section(x, a, c, ax=None, cx=None):
    """q16: the row between a = L (y, z) and c = U (forward of / at the tip: the straight ruling) or R-1 (aft: smooth max(platform, plane), the plane lowered by dl only where the arc reaches
    R-1 at the ear, so that the row ends on it); a solution dict like fold_solve_q14's"""
    a, c = np.asarray(a, float), np.asarray(c, float)
    ax = x if ax is None else ax
    cx = x if cx is None else cx
    u = np.linspace(0.0, 1.0, 2401)
    y = a[0] + (c[0] - a[0]) * u
    if QF_Q16_P1 == 'ruled':
        sol = q16_section_ruled(x, a, c)
        if sol is not None:
            return sol
        z = a[1] + (c[1] - a[1]) * u
        s = u * float(np.hypot(*(c - a)))
        return dict(x=float(x), a=a, c=c, phi0=math.atan2(c[1] - a[1], a[0] - c[0]), S=float(s[-1]), sc=float(s[-1]), ell=0.0, th=0.0, s=s, y=y - a[0], z=z - a[1], straight=True)
    n, d = q16_plane()
    th1 = math.atan2(n[1], n[2])
    if x <= X_TIP + 1e-9:
        z = a[1] + (c[1] - a[1]) * u
        s = u * float(np.hypot(*(c - a)))
        ph = math.atan2(c[1] - a[1], a[0] - c[0])
        return dict(x=float(x), a=a, c=c, phi0=ph, S=float(s[-1]), sc=float(s[-1]), ell=0.0, th=0.0, s=s, y=y - a[0], z=z - a[1], straight=True)
    th2 = q16_p2(x)
    t1, t2 = math.tan(th1), math.tan(th2)
    xs = ax + (cx - ax) * u
    z2 = a[1] + (a[0] - y) * t2
    z1 = (d - n[0] * xs - n[1] * y) / n[2]
    w = float(sstep(X_TIP, X_TIP + QF_Q16_R[2] if len(QF_Q16_R) > 2 else _Q16['xe'], x))
    r = QF_Q16_R[0] + (QF_Q16_R[1] - QF_Q16_R[0]) * w
    k = r * max(t1 - t2, 0.0) ** 2 / (1.0 + (0.5 * (t1 + t2)) ** 2) ** 1.5      # (the cubic smooth max of two lines: peak curvature dt^2 / k)
    smax = lambda p, q: -_smin(-np.atleast_1d(p), -np.atleast_1d(q), k)
    dl = 0.0
    if float(smax(z2[-1], z1[-1])[0]) > c[1] + 1e-12:
        lo, hi = 0.0, k + abs(z1[-1] - z2[-1])
        for _ in range(60):
            dl = 0.5 * (lo + hi)
            lo, hi = (dl, hi) if float(smax(z2[-1], z1[-1] - dl)[0]) > c[1] else (lo, dl)
        dl = 0.5 * (lo + hi)
    z = smax(z2, z1 - dl)
    s = np.r_[0.0, np.cumsum(np.hypot(np.diff(y), np.diff(z)))]
    up = z1 - dl
    i = int(np.argmax(up >= z2)) if np.any(up >= z2) else len(s) - 1
    blend = np.abs(z2 - up) < k
    sc, ell = float(s[i]), (float(s[blend].max() - s[blend].min()) if blend.any() else 0.0)
    return dict(x=float(x), a=a, c=c, phi0=th2, S=float(s[-1]), sc=sc, ell=ell, th=th1 - th2, s=s, y=y - a[0], z=z - a[1], dl=dl, k=k)


def tip_final(L, rail):
    """the window tip as the panels see it (q16: moved onto the plane P1, see build_all)"""
    return np.asarray(_Q16['tip'], float) if QF_Q16 and 'tip' in _Q16 else tip_point(L, rail)


def fold_section(x, sc=None):
    """the solved cross-section of the fold at station x (L -> U forward of / at the tip, L -> crest aft of it)"""
    L = CURVES['L'].at(x)
    if QF_Q16 and x > X_FOLD0 + 1e-9:
        return q16_section(x, L[1:], (CURVES['U'] if x <= X_TIP + 1e-9 else CURVES['rail']).at(x)[1:])
    if QF_Q14 and x > X_FOLD0 + 1e-9:
        return fold_solve_q14(x, L[1:], (CURVES['U'] if x <= X_TIP + 1e-9 else CURVES['rail']).at(x)[1:])
    nb = FOLD_NOBARREL and x >= X_KEEP + X_NB
    if x <= X_TIP + 1e-9:
        return (fold_solve_nb if nb else fold_solve)(x, L[1:], CURVES['U'].at(x)[1:], phir=fold_end_dir(x), sc=sc)
    return (fold_solve_nb if nb else fold_solve)(x, L[1:], CURVES['rail'].at(x)[1:], sc=sc)


def fold_nodes(sol, M, rho=None):
    """arclengths of the M + 1 nodes of a row: uniform, denser over the roll (local densification)"""
    rho = FOLD_RHO if rho is None else rho
    s, S, sc, ell = sol['s'], sol['S'], sol['sc'], sol['ell']
    dens = 1.0 + rho * _bump((s - (sc - 0.5 * ell - 0.03)) / (ell + 0.06))
    if sol.get('th2', 0.0) > 0.0:          # q13b: the convex turn behind the window tip (a crease fading into a roll: only mm wide at first) gets its own, tighter densification
        # (its weight fades with the turn: switched off at once where th2 reaches 0 it moved the nodes of one row and left a 5 - 7 deg kink across the roll there)
        m = QF_CV_RHO[1]
        dens += QF_CV_RHO[0] * min(1.0, sol['th2'] / (sol['cv'] if 'cv' in sol else fold_tip13b()['cv'])) * _bump((s - (sol['s2'] - 0.5 * sol['ell2'] - m)) / (sol['ell2'] + 2.0 * m))
    cdf = np.r_[0.0, np.cumsum(0.5 * (dens[1:] + dens[:-1]) * np.diff(s))]
    return np.interp(np.linspace(0.0, 1.0, M + 1), cdf / cdf[-1], s)


def q14_nodes(sol, M, ja=None):
    """q14: the row's nodes; aft of the tip node ja (the window tip's index in the tip row) sits on the edge between the pane and the beam plane, with QF_WE_K nodes at a fixed spacing on each
    side (a crisp round on a grid line: no saw teeth from nodes drifting across it from row to row)"""
    sj = fold_nodes(sol, M)
    K = QF_WE_K
    if ja is None or 'anc' not in sol or ja - K < 1 or ja + K > M - 1:
        return sj
    S, s2 = sol['S'], sol['s2']
    F = np.linspace(0.0, 1.0, M + 1)
    lam = sol.get('anc', 1.0)
    # where the edge has gone (the platform's round covers it) the node keeps following its line, but the spacing round it relaxes to the standard one: no switch, no jump
    hb = float(np.interp(np.interp(s2, sj, F), F[:-1] + 0.5 / M, np.diff(sj)))
    h = lam * max(sol['ell2'], 0.004) / (2 * K - 2) + (1.0 - lam) * hb
    lo, hi = s2 - K * h, s2 + K * h
    if lo <= 1e-3 or hi >= S - 1e-3:
        return sj

    def part(a_, b_, n):
        Fa, Fb = np.interp([a_, b_], sj, F)
        return np.interp(np.linspace(Fa, Fb, n + 1), F, sj)
    an = np.r_[part(0.0, lo, ja - K)[:-1], s2 + h * np.arange(-K, K + 1), part(hi, S, M - ja - K)[1:]]
    wt = max(lam, float(sstep(0.12, 0.3, s2 / S)))       # (aft of the pane the edge's line runs out over the platform towards L: let go of it gradually, long after it has faded)
    return (1.0 - wt) * sj + wt * an


def fold_points(sol, sj, ax=None, cx=None):
    """(len(sj), 3) points of the section at arclengths sj (x = the station; between the end points' x ax, cx when they differ: the edges of a panel can be a few mm apart in x near the ear)"""
    P = np.zeros((len(sj), 3))
    ax = sol['x'] if ax is None else ax
    cx = sol['x'] if cx is None else cx
    P[:, 0] = ax + (cx - ax) * np.asarray(sj) / sol['S']
    P[:, 1] = sol['a'][0] + np.interp(sj, sol['s'], sol['y'])
    P[:, 2] = sol['a'][1] + np.interp(sj, sol['s'], sol['z'])
    return P


def fold_row_dir(x, a, c):
    """the end direction (rad) of a row at U between the 3-D edge points a, c (None aft of the window tip)"""
    phir = fold_end_dir(x) if x <= X_TIP + 1e-9 else None
    if phir is not None and QF_UB_X1 > X_FOLD0 and x < QF_UB_X1:
        # q12 (review 2026-10-22, item 4, user: approach A): the rows up to X_FOLD0 meet the door glass at U with the 25 deg crease; the first fold row arrived TANGENT to the glass (crease 0) and put the
        # whole turn into a 2 mm roll right beside U (radius 1 -> 30 mm over 8 cm: a second line along U).  Over X_FOLD0 .. QF_UB_X1 the end direction now goes smoothly from the row's chord (the
        # ruled row: the crease at U, no roll) to the glass strip's: the crease at U softens while the roll grows from nothing
        ch = np.asarray(c, float)[1:] - np.asarray(a, float)[1:]
        wcr = 1.0 - float(sstep(X_FOLD0, QF_UB_X1, x))
        phir = phir + wcr * (math.atan2(ch[1], -ch[0]) - phir)
    return phir


def fold_row(a, c, M, u0=None, w=0.0, ja=None):
    """M + 1 points of the fold's cross-section between the 3-D edge points a (on L) and c (on U forward of / at the window tip, on the crest aft of it): the row of a panel.  u0 / w: the node
    fractions of the window-tip row (the first row aft of the tip keeps its nodes) and the weight of the standard (dense over the roll) distribution."""
    a, c = np.asarray(a, float), np.asarray(c, float)
    x = 0.5 * (a[0] + c[0])
    if QF_Q16 and x > X_FOLD0 + 1e-9:
        sol = q16_section(x, a[1:], c[1:], a[0], c[0])
        if sol.get('straight'):
            sj = np.linspace(0.0, sol['S'], M + 1)
        else:
            # ('ruled': under the window the densification grows with the strip, from the uniform rows ahead of X_FOLD0)
            wr = float(sstep(X_FOLD0, X_FOLD0 + QF_Q16_DR, x)) if QF_Q16_P1 == 'ruled' and x <= X_TIP + 1e-9 else 1.0
            sj = fold_nodes(sol, M, rho=QF_Q16_RHO[0] * min(1.0, sol['th'] / math.radians(QF_Q16_RHO[1])) * wr)
        if u0 is not None:
            sj = sol['S'] * ((1.0 - w) * np.asarray(u0) + w * sj / sol['S'])
        P = fold_points(sol, sj, a[0], c[0])
        P[0], P[-1] = a, c
        return P, sol
    if QF_Q14 and x > X_FOLD0 + 1e-9:
        sol = fold_solve_q14(x, a[1:], c[1:], a[0], c[0])
        sj = np.linspace(0.0, sol['S'], M + 1) if sol.get('straight') else q14_nodes(sol, M, ja)
        if u0 is not None:
            sj = sol['S'] * ((1.0 - w) * np.asarray(u0) + w * sj / sol['S'])
        P = fold_points(sol, sj, a[0], c[0])
        P[0], P[-1] = a, c
        return P, sol
    phir = fold_row_dir(x, a, c)
    wb = float(sstep(X_KEEP, X_KEEP + X_NB, x)) if FOLD_NOBARREL else 0.0
    sol = fold_solve(x, a[1:], c[1:], phir=phir) if wb < 1.0 else fold_solve_nb(x, a[1:], c[1:], phir=phir)
    sj = fold_nodes(sol, M)
    if u0 is not None:
        sj = sol['S'] * ((1.0 - w) * np.asarray(u0) + w * sj / sol['S'])
    P = fold_points(sol, sj, a[0], c[0])
    if 0.0 < wb < 1.0:
        solN = fold_solve_nb(x, a[1:], c[1:], phir=phir)
        PN = fold_points(solN, solN['S'] * sj / sol['S'], a[0], c[0])
        P = (1.0 - wb) * P + wb * PN
    P[0], P[-1] = a, c
    return P, sol


def fold_apex(sol):
    """(x, y, z) of the fold's centre (the turn's half way point) and of the roll's two ends"""
    out = []
    for sv in (sol['sc'], sol['sc'] - 0.5 * sol['ell'], sol['sc'] + 0.5 * sol['ell']):
        out.append(fold_points(sol, np.array([sv]))[0])
    return out


class Poly3:
    """x -> (x, y, z) by linear interpolation of a dense polyline (the derived fold curves)"""

    def __init__(self, P, name=''):
        self.P = np.asarray(P, float)
        self.x0, self.x1, self.name = float(self.P[0, 0]), float(self.P[-1, 0]), name

    def at(self, x):
        x = np.asarray(x, float)
        return np.stack([x, np.interp(x, self.P[:, 0], self.P[:, 1]), np.interp(x, self.P[:, 0], self.P[:, 2])], -1)

    def __call__(self, x):
        return self.at(x)

    @property
    def fy(self):
        return _Proj(self, 1)

    @property
    def fz(self):
        return _Proj(self, 2)


class Composite:
    """a curve made of XCurve pieces that follow each other in x"""

    def __init__(self, pieces, name=''):
        self.pieces = pieces
        self.x0, self.x1, self.name = pieces[0].x0, pieces[-1].x1, name

    def at(self, x):
        x = np.asarray(x, float)
        out = np.zeros(x.shape + (3,))
        done = np.zeros(x.shape, bool)
        for p in self.pieces:
            m = (x >= p.x0 - 1e-9) & (x <= p.x1 + 1e-9) & ~done
            if np.any(m):
                out[m] = p.at(x[m]); done |= m
        # outside: clamp to the ends
        lo = x < self.x0
        if np.any(lo):
            out[lo] = self.pieces[0].at(x[lo])
        hi = x > self.x1
        if np.any(hi):
            out[hi] = self.pieces[-1].at(x[hi])
        return out

    def __call__(self, x):
        return self.at(x)

    def tan(self, x, eps=1e-4):
        """(1, dy/dx, dz/dx) by one-sided / central differences inside the curve's domain"""
        x = np.asarray(x, float)
        a = np.maximum(x - eps, self.x0)
        b = np.minimum(x + eps, self.x1)
        d = (self.at(b) - self.at(a)) / (b - a)[..., None]
        return d

    @property
    def fy(self):
        return _Proj(self, 1)

    @property
    def fz(self):
        return _Proj(self, 2)


class _Proj:
    def __init__(self, c, k):
        self.c, self.k = c, k

    def __call__(self, x):
        return self.c.at(x)[..., self.k]


class Fn:
    """x -> (x, y, z) from two plain callables (for the derived curves)"""

    def __init__(self, x0, x1, fy, fz, name=''):
        self.x0, self.x1, self.fy_, self.fz_, self.name = x0, x1, fy, fz, name

    def at(self, x):
        x = np.asarray(x, float)
        return np.stack([x, np.asarray(self.fy_(x), float), np.asarray(self.fz_(x), float)], -1)

    def tan(self, x, eps=1e-4):
        x = np.asarray(x, float)
        a, b = np.maximum(x - eps, self.x0), np.minimum(x + eps, self.x1)
        return (self.at(b) - self.at(a)) / (b - a)[..., None]

    def __call__(self, x):
        return self.at(x)

    @property
    def fy(self):
        return _Proj(self, 1)

    @property
    def fz(self):
        return _Proj(self, 2)


# ----------------------------------------------------------------------------- R1e2: the nose corner moves; L / U / l3 / sill are modified near the nose only
X_JL = float(os.environ.get('X_JL', '-1.90'))       # the new plan of L joins the old L here, G2 (value, slope, curvature): the front edge of the wheel arch (hub x -1.487 - arch radius 0.415 = -1.902)
U_WIN = float(os.environ.get('U_WIN', '0.30'))       # the crest U is refitted (plan and height) within this distance of N
X_ZFIX = -2.10                                       # heights of L and U are the old ones (to 1 mm) aft of this x
# R1e3: the p013 outline of the nose corner through the RE-MATCHED p013 camera (cam_fit.py --corner; z along L), metres (x aft, y out).  p013 only gives the SHAPE (chamfer curve, bow): its absolute
# nose x disagrees with p016 / p018 by 5-8 cm, so photo_corner() translates the points in x until the chamfer's straight part starts at N.
PHOTO_CORNER_RAW = [(-2.367, 0.709), (-2.326, 0.738), (-2.285, 0.766), (-2.244, 0.798), (-2.203, 0.823), (-2.162, 0.848), (-2.121, 0.876), (-2.081, 0.901), (-2.04, 0.923), (-1.999, 0.948),
                    (-1.959, 0.969), (-1.919, 0.991), (-1.878, 1.015), (-1.838, 1.034), (-1.798, 1.052), (-1.758, 1.064), (-1.718, 1.072)]


def photo_corner(xN, yN):
    P = np.array(PHOTO_CORNER_RAW, float)
    k = np.polyfit(P[:8, 0], P[:8, 1], 1)                       # the chamfer's straight part: y = k0 x + k1
    xc = (yN - k[1]) / k[0]                                      # where it reaches the corner's y
    return [(float(x + (xN - xc)), float(y)) for x, y in P]


def quintic_h(a, b, y0, s0, k0, y1, s1, k1):
    """quintic Hermite y(x) on [a, b] from value / slope / second derivative at both ends (clamped outside): G2 with whatever curve supplies (y1, s1, k1)"""
    h = b - a

    def f(x):
        t = np.clip((np.asarray(x, float) - a) / h, 0.0, 1.0)
        t2, t3, t4, t5 = t ** 2, t ** 3, t ** 4, t ** 5
        h0, h1, h2 = 1 - 10 * t3 + 15 * t4 - 6 * t5, t - 6 * t3 + 8 * t4 - 3 * t5, 0.5 * t2 - 1.5 * t3 + 1.5 * t4 - 0.5 * t5
        g0, g1, g2 = 10 * t3 - 15 * t4 + 6 * t5, -4 * t3 + 7 * t4 - 3 * t5, 0.5 * t3 - t4 + 0.5 * t5
        return h0 * y0 + h1 * h * s0 + h2 * h * h * k0 + g0 * y1 + g1 * h * s1 + g2 * h * h * k1
    return f


def _end_state(fy, x, e=2e-3):
    return float(fy(x)), float((fy(x + e) - fy(x - e)) / (2 * e)), float((fy(x + e) - 2 * fy(x) + fy(x - e)) / e ** 2)


U_XJ = float(os.environ.get("U_XJ", "-1.92"))         # the crest U joins the legacy U (G2) at x = max(N + U_WIN, U_XJ)
U_S0 = float(os.environ.get("U_S0", "0.9"))   # the crest U keeps its plan slope at N (R1e2 value 0.90; the legacy parabola has 0.828 at N_OLD)
MONO_TOL = float(os.environ.get('MONO_TOL', '0.01'))        # geometric curvature (1/m) changes smaller than this per sample do not count as a rise / fall


# q4 front (2026-10-20, user: the fender line is a uniform parabola in p016, the model runs straight and then bends once): p016 (the crisp crest edge, fender3 'line 2') together with the p018 heights of U
# needs the PLAN of U between the nose corner N and the pillar foot to be a near-straight diagonal (slope 0.32 at N instead of 0.90, up to 7.6 cm further inboard than the old parabola: U-3 was read too wide) that
# rounds over into the foot's tangent (|y| .927, slope -.037, curvature k1: unchanged, G2).  The slope falls from its start value s_N to the foot's slope s1 along the monotone shape g (pchip through the knots
# QF_U_GK / QF_U_G, flat over the last 0.1 m); s_N follows from the foot's position.  Two things were measured: (1) the plan bend must be DONE before x -1.55: where the plan still bends (y'' < 0) over the stretch in
# which the side view's roll-off is weak (z'' > -0.2) the p016 image curvature of U changes sign (fender_report: 2 changes with a late bend, 0 with this g); (2) the p016 crest line is 5.9 px mean / 10.8 px max
# (perpendicular, camera as is) away from the photo with this plan; QF_U_AZ (a C2 lift of U between N and QF_U_XE, p018 allows 8 px = 28 mm) brings it to 2.7 / 7.6 px, but the crest then rises again before the foot
# (z'' > 0 over x -1.6 .. -1.45: 2 curvature sign changes in p016, an island in the reflection): off (0) by default.
QF_U_ON = os.environ.get('QF_U_ON', '1') == '1'
QF_U_XF = -1.43                                   # the pillar foot A_OUT: U's position, tangent and curvature there do not change
QF_U_BLEND = float(os.environ.get('QF_U_BLEND', '0.35'))   # the foot's curvature (k1) is blended in over this stretch before the foot (C2)
QF_U_GK = tuple(float(v) for v in os.environ.get('QF_U_GK', '-2.2,-2.0,-1.9,-1.8,-1.7,-1.6').split(','))     # knots of the slope shape g (x)
QF_U_G = tuple(float(v) for v in os.environ.get('QF_U_G', '1.0,1.0,0.99,0.99,0.797,0.141').split(','))          # g at the knots (1 at N, 0 at the foot; non-increasing)
QF_U_AZ = float(os.environ.get('QF_U_AZ', '0.0'))     # height (m) of the C2 lift of U between N and QF_U_XE (p018 gives U's height 2-3 px low, p016 14 px: z may use the p018 tolerance); 0 at N and at XE with value, slope, curvature
QF_U_BA, QF_U_BB = float(os.environ.get('QF_U_BA', '4')), float(os.environ.get('QF_U_BB', '3'))        # lift ~ t^BA (1-t)^BB, t from N to QF_U_XE (BA, BB >= 3: C2 at both ends)
QF_U_XE = float(os.environ.get('QF_U_XE', '-1.55'))     # where the lift is gone again (not later than the foot)
QF_U_MIX = float(os.environ.get('QF_U_MIX', '0.25'))     # 0..1: share of the q4 plan correction (1 = full, 0 = the old plan; the foot's position / tangent / curvature are the same for every value, so G2 there holds).  0.25 = accepted: a mix >= 0.3 twists the chamfer ruling in x -2.1 .. -1.9 into a C hook in the p016 v stripes (0.5: big hook); residuals vs the photos: p005 crest max 16 / mean 10 px (mix 0: 31 / 24), p016 line mean 10.4 px (mix 0: 11.9)


# q4f2: the character line L moves OUTWARD by QF_L_DY (m) as ONE long wave, widest above the front wheel (QF_L_XC = the wheel centre) and receding smoothly to zero at QF_L_XC +- QF_L_H:
#     dy(x) = QF_L_DY cos^4(pi/2 (x - XC) / H)   for |x - XC| < H, else 0     (C3 at the ends, one maximum, symmetric so the curvature is continuous across the peak)
# Where the wheel-arch circle hides it (L is at z 0.685; the arch top is above that for x -1.777 .. -1.197) the model's outline is narrower than the photo's (p013 |y| 1.076-1.079 at x -1.55 .. -1.24, L 1.059-1.063).
# The curvature the wave adds peaks at the maximum: |k| = QF_L_DY pi^2 / H^2 = 0.56 1/m for 0.024 / 0.65 (cap 0.6 1/m).  Only the L curve moves (l3, sill, the ruling heights stay), so the wall rows between l3 and L tilt
# slightly there (inside the arch).  QF_L_DY = 0 switches the wave off.
QF_L_DY = float(os.environ.get('QF_L_DY', '0.024'))
QF_L_XC = float(os.environ.get('QF_L_XC', '-1.487'))
QF_L_H = float(os.environ.get('QF_L_H', '0.65'))
QF_A_DZ = float(os.environ.get('QF_A_DZ', '0.025'))                           # q4f2: height of the A-pillar strip (rail - wl) from x QF_A_X1 on (m); 0 = off
QF_A_X0, QF_A_X1, QF_A_X2 = (float(v) for v in os.environ.get('QF_A_X', '-1.43,-1.03,-0.65').split(','))      # wedge tip (the foot), full height reached, start of the return to the roof-header value
QF_A_R = float(os.environ.get('QF_A_R', '0.08'))      # half length of the C2 rounding where the linear wedge meets the full height


def qf_a_ramp(x):
    """0 at QF_A_X0 (the wedge tip at the foot) -> 1 at QF_A_X1: LINEAR (constant rate: the strip's normal turns evenly along the wedge, 40 cm long: 3-4 straight stripes in the reflection maps instead of 11 crowded ones),
    rounded C2 over QF_A_X1 +- QF_A_R"""
    x = np.asarray(x, float)
    a, b = QF_A_X1 - QF_A_R, QF_A_X1 + QF_A_R
    u = np.clip((x - a) / (b - a), 0.0, 1.0)
    f = u ** 6 - 3.0 * u ** 5 + 2.5 * u ** 4                       # integral of the quintic smoothstep over u
    run = np.where(x < b, (x - QF_A_X0) - (b - a) * f, (QF_A_X1 - QF_A_X0))
    run = np.where(x < QF_A_X0, 0.0, run)
    return np.clip(run / (QF_A_X1 - QF_A_X0), 0.0, 1.0)


# A-pillar round 2 (2026-10-24, user: "A 柱的宽度和线条似乎实车更厚实更流畅" -> "全部都批准，以最优方式修改"), p018 read column by column (photo vs the model rendered from the same camera):
# QF_AW, the width: the band between the rail and the door glass' upper edge wl is 30 - 32 mm high in p018 from the foot to the roof (the model's: 8 mm at x -1.29 growing to 25 mm, 22 mm along
#     the rail) and grows aft of x 0 to ~50 mm at x 0.9 (the model's: 20 - 22 mm; the photo's window top edge runs straight into the tip, the model's bowed up); p013 sees the band wider in plan
#     too (pillar ~3.9 cm against 3.5, the roof rail aft of x 0.3 1.5x).  wl now lies QF_AW_H(x) under the rail and is moved there ALONG the door glass' rulings (U -> wl): the glass surface stays,
#     the band gets taller and wider.  Near the foot it reaches U (the glass ends in a tip at x ~-1.355, p018: -1.35; ahead of it the pillar's foot lands on the crest at full width: the glass
#     rows are single points there), through a C2 smooth maximum (QF_AW_EPS) so that the pillar's outer edge has no corner.  Over QF_AW_XT the line hands over to the old wl (the window tip
#     and the rows next to it, beam face and rear shoulder, do not change): one faired curve (least squares to rail - QF_AW_H with a third-derivative weight QF_AW_LAM, G2 with it at
#     XT[0] and with the old wl at XT[1]).  It does not follow the rail's rise into R-1 there (q16) nor blend the two heights (2026-10-24, user: "顶梁的尾段一小部分...线条有点抖": the
#     first version did both and put a 1 px hump into the window line at x 1.03; p018's edge is within 0.3 px of a quadratic, now 0.2).
QF_AW = os.environ.get('QF_AW', '1') == '1'
QF_AW_H0 = float(os.environ.get('QF_AW_H0', '0.0305'))       # band height (m) along the pillar and the header (photo 29 - 32 mm, mean 30.4)
QF_AW_K = float(os.environ.get('QF_AW_K', '0.021'))          # its growth aft of QF_AW_X0 (m per m; photo: 31.8 at x 0, 37.4 at 0.29, 42.4 at 0.59, 50.1 at 0.89 mm)
QF_AW_X0, QF_AW_B = 0.0, 0.12                                  # start of the growth, half length of its C2 rounding
QF_AW_XT = (0.80, 1.17)                                        # the faired hand-over to the old wl (the window tip region)
QF_AW_LAM = float(os.environ.get('QF_AW_LAM', '1e-7'))
QF_AW_EPS = float(os.environ.get('QF_AW_EPS', '0.004'))      # half width (m, in height) of the smooth maximum with U at the glass tip


def qf_smax(g, eps):
    """C2 smooth max(g, 0): 0 for g <= -eps, g for g >= eps (eps * phi(g / eps), phi the integral of the cubic smoothstep over [-1, 1])"""
    t = np.asarray(g, float) / eps
    u = np.clip((t + 1.0) * 0.5, 0.0, 1.0)
    return eps * np.where(t >= 1.0, t, 2.0 * u ** 3 - u ** 4)


def qf_aw_h(x):
    """the band height rail - wl (see QF_AW)"""
    return QF_AW_H0 + QF_AW_K * qf_smax(np.asarray(x, float) - QF_AW_X0, QF_AW_B)


def qf_aw_tz(rz, wz):
    """the height of the new wl (see QF_AW): rz(x) the rail's, wz(x) the old wl's (both vectorised).  Returns tz(x)."""
    xa, xb, e = QF_AW_XT[0], QF_AW_XT[1], 4e-3
    fa = lambda x: rz(x) - qf_aw_h(x)
    d = lambda f, x: ((f(x + e) - f(x - e)) / (2 * e), (f(x + e) - 2 * f(x) + f(x - e)) / e ** 2)
    (da, ca), (db, cb) = d(fa, xa), d(wz, xb)
    xs = np.linspace(xa, xb, 600)
    t = (xs - xa) / (xb - xa)
    h = quint1(xs, xa, float(fa(xa)), da, ca, xb, float(wz(xb)), db, cb)
    B = np.stack([t ** 3 * (1 - t) ** 3 * t ** j for j in range(8)], 1)        # zero value / slope / curvature at both ends
    d3 = lambda f: np.gradient(np.gradient(np.gradient(f, xs, axis=0), xs, axis=0), xs, axis=0)
    c = np.linalg.lstsq(np.vstack([B, math.sqrt(QF_AW_LAM) * d3(B)]), np.r_[fa(xs) - h, -math.sqrt(QF_AW_LAM) * d3(h)], rcond=None)[0]
    zf = h + B @ c

    def tz(x):
        x = np.asarray(x, float)
        return np.where(x <= xa, fa(x), np.where(x < xb, np.interp(x, xs, zf), wz(x)))
    return tz


def qf_l_dy(x):
    x = np.asarray(x, float)
    u = np.clip((x - QF_L_XC) / QF_L_H, -1.0, 1.0)
    return QF_L_DY * np.cos(0.5 * math.pi * u) ** 4


# q5c (user, 2026-10-21: "最外面的棱" = L): in PLAN (p013) the outermost crease is a STRAIGHT line from the nose corner N going back and outward, a short bend just before the front wheel, then the straight body line along the door.
# Photo p013 outline (x, |y| at L's height): -2.30 .750, -2.20 .821, -2.10 .882, -2.00 .937, -1.90 .988, -1.80 1.042, -1.70 1.066, -1.60 1.076, -1.50 1.080 (the old L ran 50 mm outside that on the nose side and bulged 24 mm over the hub).
# New plan of L for x < QF_LP_XA: leg = the straight line y = N_y + QF_LP_D + QF_LP_S0 (x - N_x) (fit to the photo, <= 19 mm at x -2.2 .. -1.9), line 1 = the old L's own tangent line at QF_LP_XA (the door segment aft of it is NOT touched), joined by
# a bend of length QF_LP_W centred on the intersection of the two lines (the slope changes by a quintic smoothstep: G2, one bend, no wave); from N to QF_LP_XJ a concave G2 corner curve (slope 0.90 at N falling to the leg's).  The leg
# passes QF_LP_D outside N: with the leg through N itself the crest U (fixed) would cross OUTSIDE L next to the corner (the middle face would overhang) and the turn at L would be < 1 deg there (no line).  Height z(x) is not touched (p018 sees height).
QF_LP_ON = os.environ.get('QF_LP_ON', '1') == '1'
QF_LP_S0 = float(os.environ.get('QF_LP_S0', '0.54'))
QF_LP_D = float(os.environ.get('QF_LP_D', '0.030'))          # the straight leg's offset from N at x N (m): it passes 30 mm outside N: the corner curve N -> XJ is concave and the crease at L keeps a turn >= 15 deg right from the corner (0.5 deg with 12 mm: no visible line there)
QF_LP_XJ = float(os.environ.get('QF_LP_XJ', '-2.25'))
QF_LP_SN = float(os.environ.get('QF_LP_SN', '0.90'))
QF_LP_KN = float(os.environ.get('QF_LP_KN', '-1.5'))
QF_LP_W = float(os.environ.get('QF_LP_W', '0.36'))
QF_LP_XA = float(os.environ.get('QF_LP_XA', '-0.89'))
# q5c8 (coordinator, 2026-10-21): the nose-side wall is ONE plane.  The new L (QF_LP_*) sits up to 45 mm inboard of the old one while l3 (the wall's foot, shared with wall_black) stayed, so the wall leaned out at the
# bottom (+6 deg at x -2.1) and swung to -4 deg at x -1.7: a twist, visible as a light streak.  l3 now slides inboard too, over x -2.34 .. -1.8 only (the corner edge E ends at x -2.34 and the nose corner panels keep
# it; from x -1.8 on l3 is untouched): QF_L3_K = x:mm knots (inboard shift of l3's plan; C2 cubic spline through them with zero end slopes; 0 outside the first / last knot).  QF_L3_ON=0 restores the old l3.
QF_L3_ON = os.environ.get('QF_L3_ON', '1') == '1'
QF_L3_K = tuple((float(a.split(':')[0]), float(a.split(':')[1])) for a in os.environ.get('QF_L3_K', '-2.34:0,-2.28:11,-2.22:25,-2.14:38,-2.06:44,-1.98:38,-1.90:22,-1.80:0').split(','))


def _qf_spline(xs, ys):
    """clamped (zero end slopes) C2 cubic spline through the knots; constant outside them"""
    xs = np.asarray(xs, float)
    ys = np.asarray(ys, float)
    n = len(xs)
    h = np.diff(xs)
    A = np.zeros((n, n))
    b = np.zeros(n)
    A[0, 0], A[0, 1], b[0] = 2 * h[0], h[0], 3 * (ys[1] - ys[0]) / h[0]
    A[-1, -1], A[-1, -2], b[-1] = 2 * h[-1], h[-1], -3 * (ys[-1] - ys[-2]) / h[-1]
    for i in range(1, n - 1):
        A[i, i - 1], A[i, i], A[i, i + 1] = h[i - 1], 2 * (h[i - 1] + h[i]), h[i]
        b[i] = 3 * ((ys[i + 1] - ys[i]) / h[i] - (ys[i] - ys[i - 1]) / h[i - 1])
    c = np.linalg.solve(A, b)
    bb = (ys[1:] - ys[:-1]) / h - h * (2 * c[:-1] + c[1:]) / 3
    d = (c[1:] - c[:-1]) / (3 * h)

    def f(x):
        x = np.asarray(x, float)
        i = np.clip(np.searchsorted(xs, x, side='right') - 1, 0, n - 2)
        t = x - xs[i]
        return np.where(x <= xs[0], ys[0], np.where(x >= xs[-1], ys[-1], ys[i] + bb[i] * t + c[i] * t * t + d[i] * t ** 3))
    return f


_QF_L3_F = _qf_spline([k[0] for k in QF_L3_K], [k[1] for k in QF_L3_K])


def qf_l3_dy(x):
    """plan shift of l3 (m, negative = inboard)"""
    return -1e-3 * _QF_L3_F(x) if QF_L3_ON else 0.0 * np.asarray(x, float)


# c9c (coordinator, 2026-10-21) "fade": the L crease in front of the wheel arch fades into one smooth surface at the arch mouth.  L is EXACTLY c8's ahead of QF_FD_X[0] (x -1.95).  From there on the cross-section between the middle
# face (the straight ruling U -> A: the face above the band is c8's, z 0.80 tilt unchanged) and the wall (straight ruling B -> l3) is a BAND (shell2.g2_band) of tangent length QF_FD_A (A = L - a ts, B = L + a tw) in which the tangent
# angle turns by psi = w(x) * phi through the C2 smootherstep: the band's curvature is 0 at both edges (G2 with the faces: no kink, no blob at the band edges), has its maximum in the middle and is proportional to w(x), i.e. it grows
# monotonically along x from 0 at QF_FD_X[0] to its maximum at the arch mouth QF_FD_X[1] (x -1.80; the visible crease ends at x -1.795).  The rest of the dihedral (1 - w) * phi stays as the (filleted) crease in the middle of the band
# (the shared edge Lm of the shoulder and the wall); it is 0 where w = 1, so the rim cuts one smooth surface.  w is held to QF_FD_X[2] and falls back to 0 between QF_FD_X[2] and [3] inside the wheel opening (hidden; tyre clearance).
# QF_FD_ON=0: c8.
QF_FD_ON = os.environ.get('QF_FD_ON', '1') == '1'
QF_FD_A = float(os.environ.get('QF_FD_A', '0.045'))     # tangent length of the band (m): the band reaches 45 mm up the face and down the wall from the crease
# 2026-10-24 (user: "the side panel bends gently all the way into the wheel's plane; the model stays flat and bends only just before the wheel"; the sections at x -1.95 / -1.85 were a 55-58 deg plane for 12-14 cm
# and a 30-37 deg roll within 4-7 cm): the band's tangent length grows from QF_FD_A to QF_FD_AA over QF_FD_AX (x) and may take QF_FD_CAP of the shorter face (was 0.4), so towards the arch mouth the roll spreads over
# most of the middle face (the crest U itself is not touched: it is the band's upper end that moves up towards it).  QF_FD_AA = QF_FD_A: the c9c / c11 band.
QF_FD_AA = float(os.environ.get('QF_FD_AA', '0.120'))
QF_FD_AX = tuple(float(v) for v in os.environ.get('QF_FD_AX', '-2.20,-1.85').split(','))
QF_FD_CAP = float(os.environ.get('QF_FD_CAP', '0.85'))
QF_FD_N = int(os.environ.get('QF_FD_N', '48'))          # polyline nodes per half band
QF_FD_WD = float(os.environ.get('QF_FD_WD', '1.0'))        # the row's nodes crowd into the band as sstep(0, QF_FD_WD, w) (continuous node layout from the c8 uniform rows)
QF_FD_WP = float(os.environ.get('QF_FD_WP', '1.0'))     # exponent of the weight's C2 rise (1: curvature starts at 0 with zero slope)
QF_FD_X = tuple(float(v) for v in os.environ.get('QF_FD_X', '-1.95,-1.80,-1.74,-1.58').split(','))

# c10 (user, 2026-10-21, annotated p016): L's plan is ONE even gentle arc from the corner N to the wheel arch (the c7 plan was a straight leg + a bend before the wheel: 'wavy and pieced together').  Ahead of QF_LA_XB the plan is the cubic
#   y(x) = N_y + S d + K d^2 / 2 + J d^3 / 6   (d = x - N_x; slope S at N, curvature y'' = K + J d: one sign, magnitude falling from 0.75 to 0.42 1/m over the visible crease; fitted to stay within 12 mm of the c9c plan, which p013 and the
# photo trace agree with, and outboard of the crest U by > 1 mm from x -2.44 on: the middle face keeps a positive width).  Aft of QF_LA_XB (inside the wheel opening, the crease ends at x -1.795) a stretch of the same sign of curvature (y'' = -c(t), c C2 at both ends, solved for its
# peak and its length) carries it to the door line (the c9c line 1: its y and slope; zero curvature): hidden, curvature peak ~3.5 1/m.  l3, the foot of the wall, follows the change (QF_LA_L3: weight of the follow, ramp over x -2.34 .. -2.20) so the wall keeps its lean.
# QF_LA_ON=0: the c9c plan.
QF_LA_ON = os.environ.get('QF_LA_ON', '1') == '1'
QF_LA_S = float(os.environ.get('QF_LA_S', '0.755'))
QF_LA_K = float(os.environ.get('QF_LA_K', '-0.75'))
QF_LA_J = float(os.environ.get('QF_LA_J', '0.80'))
QF_LA_XB = float(os.environ.get('QF_LA_XB', '-1.83'))
QF_LA_L3 = float(os.environ.get('QF_LA_L3', '1.0'))
QF_LA_R = float(os.environ.get('QF_LA_R', '-2.26'))        # end of the ramp of l3's follow
QF_LA_INFO = {}


def qf_la_dy(L0fy, dy_old, xN, yN):
    """dy(x) of L for the single arc (see QF_LA_ON): arc -> hidden quintic -> the c9c door line (line 1 through (xa, ya) with the slope s1) -> the old dy aft of xa."""
    xa = QF_LP_XA
    ya = float(L0fy(xa)) + float(dy_old(xa))
    e = 1e-4
    s1 = (float(L0fy(xa + e)) + float(dy_old(xa + e)) - float(L0fy(xa - e)) - float(dy_old(xa - e))) / (2 * e)
    S, K, J, xb = QF_LA_S, QF_LA_K, QF_LA_J, QF_LA_XB
    arc = lambda x: yN + S * (x - xN) + 0.5 * K * (x - xN) ** 2 + J * (x - xN) ** 3 / 6.0
    d1 = lambda x: S + K * (x - xN) + 0.5 * J * (x - xN) ** 2
    d2 = lambda x: K + J * (x - xN)
    y0, v0, kb = arc(xb), d1(xb), -d2(xb)                      # the hidden stretch: y'' = -c(t), c = (kb + A sin(pi t)) (1 - sstep(t)), t = (x - xb) / h: c >= 0 (one sign), C2 at both ends (kb at xb, 0 with zero slope at xd)
    nq = 801
    tq = np.linspace(0.0, 1.0, nq)
    sq = tq ** 3 * (tq * (6 * tq - 15) + 10)

    def hid(p):
        A, h = p
        c = (kb + A * np.sin(np.pi * tq)) * (1.0 - sq)
        s = v0 - h * np.r_[0.0, np.cumsum(0.5 * (c[1:] + c[:-1]) * np.diff(tq))]
        y = y0 + h * np.r_[0.0, np.cumsum(0.5 * (s[1:] + s[:-1]) * np.diff(tq))]
        return s, y
    # (A, h) from the two end conditions: slope s1 and the height of the door line at xb + h (Newton, numerical Jacobian)
    p = np.array([4.5, 0.24])
    for _ in range(40):
        s, y = hid(p)
        f = np.array([s[-1] - s1, y[-1] - (ya + s1 * (xb + p[1] - xa))])
        if np.abs(f).max() < 1e-9:
            break
        Jm = np.zeros((2, 2))
        for j in range(2):
            q = p.copy()
            q[j] += 1e-6
            s2, y2 = hid(q)
            Jm[:, j] = (np.array([s2[-1] - s1, y2[-1] - (ya + s1 * (xb + q[1] - xa))]) - f) / 1e-6
        p = p - np.linalg.solve(Jm, f)
    A, h = float(p[0]), float(p[1])
    assert abs(f).max() < 1e-6 and 0.05 < h < 0.6, ('L plan: the hidden stretch did not converge', A, h, f)
    xd = xb + h
    sH, yH = hid(p)
    xq = xb + h * tq

    def herm(x):
        return np.interp(np.asarray(x, float), xq, yH)

    def yT(x):
        x = np.asarray(x, float)
        return np.where(x <= xb, arc(np.maximum(x, xN)), np.where(x < xd, herm(x), ya + s1 * (x - xa)))

    def dy(x):
        x = np.asarray(x, float)
        xc = np.maximum(x, xN)
        return np.where(x < xa, yT(xc) - np.asarray(L0fy(xc), float), np.asarray(dy_old(x), float))
    dy.info = dict(S=S, K=K, J=J, ya=ya, s1=s1, A=A, xd=xd, cpk=float(((kb + A * np.sin(np.pi * tq)) * (1.0 - sq)).max()))
    return dy


# c10 (user, 2026-10-21, annotated p016 / p005): the fender top (between the hood seam L5 and the crest U) is slightly CONVEX: the photo shows a smooth crowned surface with slowly changing shading.  This overrides the 2026-10-19 G-5 ruling
# (ruled rows, zero sag) for this face only.  Every row from the flap seam to the end row gets a parabolic crown 4 s (1 - s) QF_FT_C (s = the row's chord parameter, the offset along the row's normal): L5, U and N stay, the flap (corner_tri,
# rows up to the seam) is untouched and planar, the crown envelope rises by a C2 smoothstep over the first QF_FT_R0 of the rows behind the seam (G1 with the flap) and falls to 0 over the last QF_FT_R1 (the end row is shared with the glass).
# QF_FT_C = 0 restores the ruled surface.
QF_FT_C = float(os.environ.get('QF_FT_C', '0.005'))
# 2026-10-24 (user: the real fender top rises as a gentle, visibly curved surface; the model read as a flat plane): QF_FT_K > 0 replaces the fixed crown by a constant CROSS curvature: crown = K w^2 / 8 for a row of
# chord w (capped at QF_FT_CMAX), so the face is evenly curved across and the crown follows the face's width along x instead of the envelope's own rise and fall (a 10 mm envelope crown made a dome: closed rings in
# p005's reflection lines).  The rise behind the flap seam (QF_FT_R0) stays; the fall to the end row is the face's narrowing plus QF_FT_R1K.  QF_FT_K = 0: the c10 crown QF_FT_C.
QF_FT_K = float(os.environ.get('QF_FT_K', '0.9'))
QF_FT_CMAX = float(os.environ.get('QF_FT_CMAX', '0.012'))
QF_FT_R1K = float(os.environ.get('QF_FT_R1K', '0.25'))
QF_FT_R0 = float(os.environ.get('QF_FT_R0', '0.35'))
QF_FT_R1 = float(os.environ.get('QF_FT_R1', '0.7'))
# q12 (review 2026-10-22, item 1): QF_FT_R1 0.25 -> 0.7.  Over the last 11 rows the 5 mm crown fell to 0 within ~13 cm: two fold pulses across the face in front of the pillar foot (row-to-row normal turn 1.4 / 1.9 deg
# against 0.3); spread over 0.7 of the rows they are gone (<= 0.4 deg)

# c10 (user: the lower face C is ONE trapezoid, no small triangle T): T is the shell's nose_corner_up (the upper chamfer facet, a planar triangle N - R_l3 - l3_0, 20 degrees off the wall).  QF_NC_ON=1 bends it G1 into the wall (shell2.p_nose_corner_up):
# its corners (front.py's front face crease) do not move.  QF_NC_V: the fraction of the height over which the lift fades in above the l3 level.  QF_NC_ON=0: the flat facet.
QF_NC_ON = os.environ.get('QF_NC_ON', '1') == '1'
QF_NC_V = float(os.environ.get('QF_NC_V', '0.30'))
# c10b (coordinator: the lower face C, the area where T was included, is ONE clean surface, no blended patch): the chamfer facets (nose_corner_up / nose_corner_low) are removed.  The wall's and wall_black's FIRST row is the front
# face's end generator itself (R_bot -> R_l3 -> N), the l3 and sill curves START at R_l3 / R_bot (their plan is bent so that they pass through them, the bend fades out within QF_CF_DL / QF_CF_DS m): the lower face is the ruled
# sweep of L's plan arc down to the foot, front boundary = the front face's vertical edge (the crease stays crisp).  QF_CF_ON=0 gives c10.
QF_CF_ON = os.environ.get('QF_CF_ON', '1') == '1'
QF_CF_DL = float(os.environ.get('QF_CF_DL', '0.30'))
QF_CF_DS = float(os.environ.get('QF_CF_DS', '0.25'))
_CF_PRE = {}

# ----------------------------------------------------------------------------- c11: a rounder shoulder over the front wheel, smooth creases, lower edge outboard (coordinator + user, 2026-10-21/22)
# (a) over the wheel the shoulder's lower end (the rim of the wheel opening) is pinned by the tyre: every mm of inboard pull of the rim costs ~0.5 mm of clearance at full lock, and the budget is zero (+12.7 mm steered, +19.6 mm static
#     as in c10b).  What c11 does instead: the c9c fade band that softens L into one surface starts earlier (QF_C11_FDX: from x -2.25 instead of -1.95; the tangent length QF_C11_FDA stays 45 mm: 60 mm raised the turning of the paint rim in p016 at phi 119 from 8.7 to 12.9 deg), so the
#     crease angle decreases gradually over 45 cm before the arch mouth (no step, no notch: the band is the same G2 band); L itself is faired (QF_C11_LP: the curvature that rose 10-fold within 10 cm at the arch mouth is smoothed, <= 3.7 mm).
#     c11b (coordinator: the front-view outline from U down to the widest point is ONE convex arc; USER RULING 2026-10-22, SPEC U-1: over the front wheel the upper crease is softened into a round shoulder, dihedral <= 10 deg,
#     the nose segment keeps the crisp crease): QF_C11_FA = 1 (c11: 0) blends the outer boundary y(z) of the wall + shoulder section into a swept convex ARC (shell2.qf_soft_target: quintic Hermite from the wall line
#     QF_C11_SD = 5 cm below the wall top Lm, tangent AND curvature 0 there = G2 with the wall, to U, where it arrives QF_C11_UD = 5 deg to the measured top face (the mesh reads 6 - 9 deg); QF_C11_SOFT=0 gives the old Bezier
#     target with QF_C11_DA).  The arc lies OUTSIDE the old straight chamfer above the rim, so the rim, the tyre clearance and the plan outline do not move inboard; U, the lip's skin edge, the Trim flange and the side-view
#     height are untouched.  The weight is the quintic ramp QF_C11_FX = -2.30 .. -1.45 raised to the power QF_C11_FP = 2 (delayed: the y-blend is front-loaded, a weight of 0.1 already flattens a 55 deg ruling to 30 deg), so the
#     dihedral at U falls as ONE monotone curve: 69 deg at x -2.10 (= c10b, crisp), 52 at -1.98, 33 at -1.90, 24 at -1.85, 18 at -1.80, 12 at -1.70, 7 at -1.60 (<= 14 deg per 5 cm), and the nose-side surface moves by at most
#     0.2 of slope (a steeper ramp, -1.90 .. -1.75 etc., tilts the surface 20 deg toward the nose and folds the reflection map: closed rings / bull's eyes in reflect_v at x -1.7 .. -1.8, tested with 12 variants).  Measured
#     (orthographic front outline, x <= -1.15): minimum radius 1.2 cm at z .759 (c10b / c11) -> 7.9 cm, no sign change of the curvature from U to the widest point.  CHORD THEOREM: with the old U tangent of ~52 deg the convex arc
#     cannot reach the lip with a tangent below ~40 deg unless U softens too (lip tangent + U tangent = 2 x chord angle = ~93 deg): the rounded shoulder IS the softened U.  Reflection: no ring in reflect_v; reflect_h shows the nested
#     turn-backs of a round-over (the el ridge of a section whose normal sweeps 0 .. 90 deg), open to the nose, not islands.  QF_C11_FA=0: the straight face of c11.
#     OPTION (default off): QF_C11_BA > 0 repeats the band aft of the arch.
# (b) [c11b: OFF by default, QF_C11_DU=0.007 gives c11] the crest U moves inboard (QF_C11_DU, one C2 bump over x -1.975 .. -1.43: U ahead of -1.975 (the flap's seam row, station 33) and at A_OUT x -1.43 (a key point) is exactly the old one, its z(x) is untouched).  The cap is
#     the one-signed curvature of the plan (the bump's curvature must stay below the old curvature of U): 7 mm at x -1.70 (9 mm is the limit, the curvature steps grow with it).
# (c) every crease is a smooth line: L's height has no dent (QF_C11_LZ: the slope dz/dx is made monotone up to its maximum at x -1.95 (<= 2.6 mm) and faired (QF_C11_LZP)), L / l3 plans are faired (QF_C11_LP / L3P: no step of the
#     curvature where the line dips into the wheel opening); check.py smooth (crease_smooth.py) lists the turning angle per 5 cm along every crease.
# (d) the bottom edge of the lower face (l3) is moved outboard by QF_C11_DL3 between the front corner and the wheel arch (C stands more vertical; the front face and the lip centre are unchanged).
# QF_C11_ON=0 gives c10b.
QF_C11_ON = os.environ.get('QF_C11_ON', '1') == '1'
QF_C11_DU = float(os.environ.get('QF_C11_DU', '0.0'))                            # inboard shift of U (m) at its maximum.  c11b: DEFAULT 0 (the 7 mm local move bent the reflect_h stripes at x -1.70 and gave no p016 gain, G-5); 0.007 gives c11
QF_C11_UX = tuple(float(v) for v in os.environ.get('QF_C11_UX', '-1.975,-1.70,-1.70,-1.43').split(','))   # start of the shift (U fixed ahead), full shift reached, begins to return, end (U old aft of it)
QF_C11_LZ = os.environ.get('QF_C11_LZ', '1') == '1'
QF_C11_DL3 = float(os.environ.get('QF_C11_DL3', '0.010'))                        # l3 (the bottom edge of the lower face) outboard
QF_C11_L3X = tuple(float(v) for v in os.environ.get('QF_C11_L3X', '-2.40,-2.15,-1.75,-1.25').split(','))
QF_C11_FDX = tuple(float(v) for v in os.environ.get('QF_C11_FDX', '-2.25,-1.80,-1.74,-1.58').split(','))   # c9c fade band weight (QF_FD_X) under c11: starts at -2.25 (was -1.95)
QF_C11_FDA = float(os.environ.get('QF_C11_FDA', '0.045'))                          # c9c band tangent length (QF_FD_A) under c11 (unchanged; 0.06 gives a 12.9 deg turn of the paint rim in p016)
if QF_C11_ON:
    QF_FD_X, QF_FD_A = QF_C11_FDX, QF_C11_FDA
# the optional round section (used by shell2.qf_f_target): cubic Bezier from the wall line at height ZF (tangent: the wall direction leaned outward by LAM degrees) to U (arrival: the old chord direction + DA degrees flatter)
QF_C11_ZF = float(os.environ.get('QF_C11_ZF', '0.65'))                            # height (m) at which the round target section leaves the wall line (0 = at the foot l3)
QF_C11_LAM = float(os.environ.get('QF_C11_LAM', '2.0'))
QF_C11_K0 = float(os.environ.get('QF_C11_K0', '0.5'))
QF_C11_K1 = float(os.environ.get('QF_C11_K1', '0.5'))
# 2026-10-24: ahead of the wheel (x < QF_C11_KX[0]) both handles are QF_C11_KF (near-circular arc: the middle face bends evenly from just below U into the wall), over the wheel (x > QF_C11_KX[1]) they are K0 / K1 as before.
# (0.35 over the wheel as well spread the hub section's turn evenly, 33 37 39 42 45 deg per 2 cm, but with U crisp and its arrival angle fixed the rounder section stands 4-12 mm further inboard above the rim:
#  full-lock tyre clearance 11.4 -> 4.5 mm and less of the tyre covered from above; the boxier K 0.5 section is what covers the tyre)
QF_C11_KF = float(os.environ.get('QF_C11_KF', '0.35'))
QF_C11_KX = tuple(float(v) for v in os.environ.get('QF_C11_KX', '-1.80,-1.62').split(','))
QF_C11_DA = float(os.environ.get('QF_C11_DA', '20.0'))
QF_C11_AZD = float(os.environ.get('QF_C11_AZD', '0.3'))                            # mm: the paint edge of the front arch at the 163 deg knot of shell2.QF_AZ_K is 'this much' LESS far below the circle (rim moves away from the tyre)
QF_C11_SOFT = os.environ.get('QF_C11_SOFT', '0') == '1'                              # c11b (user ruling 2026-10-22): the target section over the wheel is the swept convex arc: G2 with the wall at the lip, dihedral QF_C11_UD at U (0 = the old Bezier target with QF_C11_DA)
QF_C11_UD = float(os.environ.get('QF_C11_UD', '5.0'))                                # deg: the dihedral between the top face and the shoulder at U over the wheel (the user: <= 10)
QF_C11_SD = float(os.environ.get('QF_C11_SD', '0.05'))                              # m: the arc leaves the wall line this far BELOW the wall top Lm (tangent, curvature 0)
QF_C11_SK = float(os.environ.get('QF_C11_SK', '1.2'))                                # speed of the quintic Hermite arc at both ends, as a multiple of the chord Lm -> U
QF_C11_SC1 = float(os.environ.get('QF_C11_SC1', '0.0'))                              # curvature of the arc at U, as a multiple of the circle through the same chord and turn (0 at the lip: G2 with the wall)
QF_C11_FA = float(os.environ.get('QF_C11_FA', '1.0'))                              # amplitude of the round fill (0 = off: the old straight face = c11; 1 = the target section = c11b)
QF_C11_FX = tuple(float(v) for v in os.environ.get('QF_C11_FX', '-2.10,-1.35,-1.00,-0.20').split(','))   # fill weight: 0 at [0], 1 at [1] .. [2], 0 at [3] (quintic; the ramp-in raised to QF_C11_FP).  h5: -1.82,-1.35,-1.25,-0.45.
#   2026-10-24: the ramp-in starts at -2.10 (was -1.82): ahead of the arch the middle face bends from just below U into the wall (x -1.85: 50 50 52 53 54 56 59 63 70 76 79 85 deg per 2 cm) instead of a 55 deg plane and a 4-7 cm roll; L ahead of -2.10 is untouched
#   q12 (review 2026-10-22, item 2; user: "都同意", criterion: no valley along x, monotone lean): the h5 fill retreated from x -1.25 while the untouched door (c10b) only widens from -1.05 on: a 13-14 mm
#   valley in y at z .78 - .84 ahead of the door gap (the c11c soft shadow).  Held to -1.00 and retreating to -0.20 (where the door has caught up), the valley is 1.6 - 3.7 mm (z .86: 9.9 mm, the
#   waist of U's plan, c10b 12.7); the door's plan width is L's and does not change.
QF_C11_FP = float(os.environ.get('QF_C11_FP', '1.0'))                                # c11b: exponent of the ramp-in (w = sstep ** FP): > 1 delays the fill so the dihedral at U falls as one monotone curve (the y-blend is front-loaded: a small weight already flattens the ruling a lot); 1 = plain quintic
QF_C11_LB = tuple(float(v) for v in os.environ.get('QF_C11_LB', '2.0,-2.46,-1.90').split(','))      # c11b: L's height gets one C2 bump (amplitude mm, window start, end; zero value / slope / curvature at both ends) so that the front-view turning of L rises in a bell (no step > 45 % of the peak at x -2.28); 0 = off
QF_C11_BA = float(os.environ.get('QF_C11_BA', '0.0'))                                # tangent length (m) of the c9c fade band aft of the wheel opening (0 = none)
QF_C11_BX = tuple(float(v) for v in os.environ.get('QF_C11_BX', '-1.34,-1.22,-0.95,-0.55').split(','))   # its weight: 0 at [0], 1 at [1] .. [2], 0 at [3]
QF_C11_LP = tuple(float(v) for v in os.environ.get('QF_C11_LP', '-2.25,-1.25,0.035').split(','))    # L plan fairing: window start, window end (L is straight aft of it), sigma (m) of the curvature smoothing; sigma 0 = off
QF_C11_LZP = tuple(float(v) for v in os.environ.get('QF_C11_LZP', '-2.40,-1.75,0.08').split(','))    # L height fairing (after the monotone slope fit): window start, end, sigma
QF_C11_L3P = tuple(float(v) for v in os.environ.get('QF_C11_L3P', '-2.15,-1.55,0.08').split(','))    # l3 plan fairing: window start, end, sigma (0 = off)
QF_C11_INFO = {}


def qf_c11_u_dy(Ufy, xN):
    """plan correction (new - old) of the crest U: -QF_C11_DU * one C2 bump (quintic smoothstep up from QF_C11_UX[0] to [1], down from [2] to [3]); exactly zero ahead of [0] (the flap's seam row) and aft of [3] (A_OUT), with
    zero slope and curvature at both ends.  The bump's curvature (<= 76 * DU 1/m) stays below the one of U's plan (0.7 .. 1.0 1/m over the wheel): U stays concave (one-signed curvature) for DU <= 0.009."""
    xs, x1, x2, xe = QF_C11_UX
    prof = lambda x: sstep(xs, x1, x) * (1.0 - sstep(x2, xe, x))

    def dy(x):
        return -QF_C11_DU * prof(np.asarray(x, float))
    dy.fit = None
    return dy


def qf_c11_fair(fn, xa, xb, sig, xlo=None, mono=False, bumps=None):
    """c11 fairing of a crease line: correction (new - old) of the function fn(x) (plan y or height z of a crease): the second derivative of fn is smoothed (Gaussian, sigma sig) on [xa, xb], two raised-cosine bumps of the second
    derivative restore the old slope and the old value at xb, so the correction and its slope vanish at both ends (G2 join: the line is as it was ahead of xa and aft of xb) and its size is a few mm.  Removes the step where a
    bend starts (a curvature that rises 10-fold within 5 cm) and the small notches of the second derivative."""
    h = 0.0005
    xg = np.arange(xa - 0.3, xb + 0.3 + 1e-9, h)
    if sig <= 0:
        z = lambda x: np.zeros_like(np.asarray(x, float))
        z.info = dict(max_mm=0.0)
        return z
    y = np.asarray(fn(xg if xlo is None else np.maximum(xg, xlo)), float)
    k = np.zeros_like(y)
    k[1:-1] = (y[2:] - 2 * y[1:-1] + y[:-2]) / h ** 2
    m0 = int(4 * 0.004 / h)                                    # the second difference at 0.5 mm of the old curve carries its rounding noise: a light smoothing (4 mm) keeps that noise out of the correction
    k0 = np.exp(-0.5 * (np.arange(-m0, m0 + 1) * h / 0.004) ** 2)
    k = np.convolve(np.pad(k, m0, mode='edge'), k0 / k0.sum(), mode='valid')
    m = int(4 * sig / h)
    kern = np.exp(-0.5 * (np.arange(-m, m + 1) * h / sig) ** 2)
    kern /= kern.sum()
    ks = np.convolve(np.pad(k, m, mode='edge'), kern, mode='valid')
    sel = (xg >= xa) & (xg <= xb)
    if mono:                                   # the curvature falls monotonically aft of its peak (one curvature peak: check.py plan): isotonic fit of |k| aft of the peak
        from fitlib import pav_increasing
        sg = np.sign(ks[sel][np.argmax(np.abs(ks[sel]))])
        a_ = np.abs(ks)
        ipk = int(np.argmax(np.where(sel, a_, -1.0)))
        iend = int(np.searchsorted(xg, xb))
        a_[ipk:iend + 1] = -pav_increasing(-a_[ipk:iend + 1])
        ks = np.where(np.arange(len(xg)) >= ipk, sg * a_, ks)
    dk = sstep(xa, xa + 0.12, xg) * (1 - sstep(xb - 0.10, xb, xg)) * (ks - k)
    bump = lambda c, w: 0.5 * (1 + np.cos(np.pi * np.clip((xg - c) / w, -1, 1)))
    c1, c2 = bumps if bumps else (xa + 0.12 + 0.25 * (xb - xa - 0.22), xa + 0.12 + 0.75 * (xb - xa - 0.22))
    b1, b2 = bump(c1, 0.10), bump(c2, 0.10)
    A = np.array([[(b1 * sel).sum() * h, (b2 * sel).sum() * h], [((xb - xg) * b1 * sel).sum() * h, ((xb - xg) * b2 * sel).sum() * h]])
    r = -np.array([(dk * sel).sum() * h, ((xb - xg) * dk * sel).sum() * h])
    a = np.linalg.solve(A, r)
    dkk = (dk + a[0] * b1 + a[1] * b2) * sel
    ctr = lambda f: np.concatenate([[0.0], np.cumsum(0.5 * (f[1:] + f[:-1])) * h])         # cumulative trapezoid
    d1 = ctr(dkk)
    d0 = ctr(d1)
    ie = int(np.searchsorted(xg, xb))
    d0 = d0 - d0[ie]                                           # exactly zero at the end of the window (the numerical residual is below 1e-9 m)
    d0 = np.where(xg >= xb, 0.0, d0)
    d1 = np.where(xg >= xb, 0.0, d1)
    d2 = np.where(xg >= xb, 0.0, dkk)

    def dyf(x):                                                # quintic Hermite through the nodes (value, slope, curvature): no ripple in the second derivative
        x = np.asarray(x, float)
        i = np.clip(np.floor((x - xg[0]) / h).astype(int), 0, len(xg) - 2)
        t = (x - xg[i]) / h
        t3, t4, t5 = t ** 3, t ** 4, t ** 5
        v = ((1 - 10 * t3 + 15 * t4 - 6 * t5) * d0[i] + (t - 6 * t3 + 8 * t4 - 3 * t5) * h * d1[i] + (0.5 * t * t - 1.5 * t3 + 1.5 * t4 - 0.5 * t5) * h * h * d2[i]
             + (10 * t3 - 15 * t4 + 6 * t5) * d0[i + 1] + (-4 * t3 + 7 * t4 - 3 * t5) * h * d1[i + 1] + (0.5 * t3 - t4 + 0.5 * t5) * h * h * d2[i + 1])
        return np.where((x > xa) & (x < xb), v, 0.0)
    dyf.info = dict(max_mm=float(1000 * np.abs(d0).max()))
    return dyf


def qf_c11_dy_L(Lfy, xN):
    """plan correction of L: the curvature rises from 0.3 to 3.9 1/m within 0.1 m at the arch mouth (a kink of the line where it dips into the wheel opening): qf_c11_fair on QF_C11_LP"""
    xa, xb, sig = QF_C11_LP
    return qf_c11_fair(Lfy, xa, xb, sig, mono=True, bumps=(xa + 0.10, xa + 0.28))


def qf_c11_dz_L(Lfz, xN):
    """height correction (new - old) of L: the slope dz/dx between N and its first maximum is made monotone (isotonic fit: the same height at the maximum), so the dent of the slope near x -2.3 goes"""
    from fitlib import pav_increasing
    h = 0.005
    xg = np.arange(xN, -1.60 + 1e-9, h)
    z = np.asarray(Lfz(xg), float)
    dz = np.gradient(z, xg)
    ipk = int(np.argmax(dz[: int((-1.80 - xN) / h)]))
    dzn = dz.copy()
    dzn[: ipk + 1] = pav_increasing(dz[: ipk + 1])
    zn = z[0] + np.concatenate([[0.0], np.cumsum(0.5 * (dzn[1:] + dzn[:-1]) * h)])
    corr = np.where(np.arange(len(xg)) <= ipk, zn - z, 0.0)
    corr[ipk:] = corr[ipk]
    corr = np.where(np.arange(len(xg)) <= ipk, corr, 0.0)
    xp = xg[ipk]

    def dzp(x):
        x = np.asarray(x, float)
        return np.where(x < xp, np.interp(x, xg, corr), 0.0)
    xa, xb, sig = QF_C11_LZP
    fair = qf_c11_fair(lambda x: np.asarray(Lfz(x), float) + dzp(x), xa, xb, sig)

    def dzf(x):
        return dzp(x) + fair(x)
    dzf.info = dict(x_peak=float(xp), max_mm=float(1000 * np.abs(corr).max()), fair_mm=fair.info['max_mm'])
    return dzf
QF_CF_XJ3 = float(os.environ.get('QF_CF_XJ3', '-2.00'))      # the l3 / sill plan starts at the generator and joins the old curve (value, slope, curvature) here
QF_CF_XJS = float(os.environ.get('QF_CF_XJS', '-2.00'))


def qf_cf_start(fy, x0, y0, xj, name=''):
    """c10b: plan correction d(x) (new - old) of a curve that must START at (x0, y0): on [x0, xj] the new plan is the quintic Hermite from (y0, s0, k0) to the OLD curve's value / slope / curvature at xj, with the free start slope s0 and
    curvature k0 chosen to minimise the integral of the squared third derivative (the fairest single sweep); beyond xj d = 0 (G2 join).  Returns (d, info)."""
    h = xj - x0
    e = 1e-3
    y1 = float(fy(xj))
    s1 = float((fy(xj + e) - fy(xj - e)) / (2 * e))
    k1 = float((fy(xj + e) - 2 * y1 + fy(xj - e)) / e ** 2)
    tt = np.linspace(0.0, 1.0, 81)

    def coef(s0, k0):
        # y(t) = sum c_i t^i, t in [0, 1], derivatives w.r.t. x scaled by h
        A = np.array([[1, 0, 0, 0, 0, 0], [0, 1, 0, 0, 0, 0], [0, 0, 2, 0, 0, 0], [1, 1, 1, 1, 1, 1], [0, 1, 2, 3, 4, 5], [0, 0, 2, 6, 12, 20]], float)
        b = np.array([y0, s0 * h, k0 * h * h, y1, s1 * h, k1 * h * h])
        return np.linalg.solve(A, b)

    def jerk2(c):
        j = 6 * c[3] + 24 * c[4] * tt + 60 * c[5] * tt ** 2
        return float(np.sum(0.5 * (j[1:] ** 2 + j[:-1] ** 2)) * (tt[1] - tt[0]))
    best = None
    s_lo, s_hi, k_lo, k_hi = 0.0, 2.5, -12.0, 12.0
    for it in range(6):
        for s0 in np.linspace(s_lo, s_hi, 21):
            for k0 in np.linspace(k_lo, k_hi, 21):
                v = jerk2(coef(s0, k0))
                if best is None or v < best[0]:
                    best = (v, s0, k0)
        ds, dk = (s_hi - s_lo) / 10, (k_hi - k_lo) / 10
        s_lo, s_hi, k_lo, k_hi = best[1] - ds, best[1] + ds, best[2] - dk, best[2] + dk
    c = coef(best[1], best[2])

    def d(x):
        x = np.asarray(x, float)
        t = np.clip((x - x0) / h, 0.0, 1.0)
        yn = c[0] + t * (c[1] + t * (c[2] + t * (c[3] + t * (c[4] + t * c[5]))))
        return np.where(x < xj, yn - np.asarray(fy(np.maximum(x, x0)), float), 0.0)
    return d, dict(s0=best[1], k0=best[2], s1=s1, k1=k1, xj=xj, name=name)


QF_LP_INFO = {}


def qf_lp_dy(L0fy, dy_old, xN, yN, Ufy=None):
    """dy(x) for L: new plan y_T(x) - L0.fy(x) for x < QF_LP_XA, the old dy (dyL + wave) aft of it.  N -> QF_LP_XJ: a quintic Hermite (start slope QF_LP_SN, curvature QF_LP_KN, G2 into the leg): the headlamp corner,
    where the crest U runs outside the photo line for a few cm and the middle face must keep a positive plan width; QF_LP_XJ -> bend: the straight leg (slope QF_LP_S0, offset QF_LP_D at N)."""
    xa = QF_LP_XA
    ya = float(L0fy(xa)) + float(dy_old(xa))
    e = 1e-4
    s1 = (float(L0fy(xa + e)) + float(dy_old(xa + e)) - float(L0fy(xa - e)) - float(dy_old(xa - e))) / (2 * e)
    s0, d0 = QF_LP_S0, QF_LP_D
    yl0 = yN + d0                                             # the leg's value at N
    c = (ya - yl0 - s1 * xa + s0 * xN) / (s0 - s1)           # intersection of the leg and line 1 (through (xa, ya) with slope s1)
    a0, b0 = c - 0.5 * QF_LP_W, c + 0.5 * QF_LP_W
    xj = QF_LP_XJ

    def yT0(x):
        x = np.asarray(x, float)
        t = np.clip((x - a0) / (b0 - a0), 0.0, 1.0)
        G = t - (2.5 * t ** 4 - 3.0 * t ** 5 + t ** 6)
        return np.where(x <= a0, yl0 + s0 * (x - xN), yl0 + s0 * (a0 - xN) + s1 * (x - a0) + (s0 - s1) * (b0 - a0) * G)

    h = xj - xN
    y1 = float(yT0(xj))

    def hermite(x):
        t = np.clip((np.asarray(x, float) - xN) / h, 0.0, 1.0)
        h00 = 1 - 10 * t ** 3 + 15 * t ** 4 - 6 * t ** 5
        h10 = t - 6 * t ** 3 + 8 * t ** 4 - 3 * t ** 5
        h20 = 0.5 * t ** 2 - 1.5 * t ** 3 + 1.5 * t ** 4 - 0.5 * t ** 5
        h01 = 10 * t ** 3 - 15 * t ** 4 + 6 * t ** 5
        h11 = -4 * t ** 3 + 7 * t ** 4 - 3 * t ** 5
        h21 = 0.5 * t ** 3 - t ** 4 + 0.5 * t ** 5
        return h00 * yN + h10 * h * QF_LP_SN + h20 * h * h * QF_LP_KN + h01 * y1 + h11 * h * s0 + 0.0 * h21

    def yT(x):
        x = np.asarray(x, float)
        return np.where(x < xj, hermite(x), yT0(x))

    def dy(x):
        x = np.asarray(x, float)
        xc = np.maximum(x, xN)
        return np.where(x < xa, yT(xc) - np.asarray(L0fy(xc), float), np.asarray(dy_old(x), float))
    dy.info = dict(c=c, a0=a0, b0=b0, s1=s1, ya=ya)
    return dy


# q5 (coordinator ruling, 2026-10-20): the pale vertical band on the front fender (user's showroom view) is the step in U's and L's side-view curvature at x ~ -1.9 (U: z'' -0.05 -> -1.1 within 6 cm, the flap
# plane's G2 continuation + the tilt lift's fade; L: the ruling rule's fade-in).  FAIR it: inside a window the height is replaced by the quintic Hermite G2-matched to the curve at both window ends, so z'' ramps
# over the window (|dz| <= a few mm) instead of stepping.  The flap plane (U up to B, x -1.975) is not touched: the window of U starts at B.
QF_G_ON = os.environ.get('QF_G_ON', '1') == '1'
QF_G_U = tuple(float(v) for v in os.environ.get('QF_G_U', '-1.975,-1.45').split(','))     # 2026-10-24: window end -1.54 -> -1.45 (the lower nose corner lifts U by 0.4 - 0.5 cm over x -1.9 .. -1.7 through the
#   flap plane's continuation, as p018 reads it; with the old window its fade gave z'' > 0 (+0.07) just ahead of the foot, two curvature sign changes; now z'' <= -0.05 all the way)
QF_G_L = tuple(float(v) for v in os.environ.get('QF_G_L', '-2.11,-1.55').split(','))


def qf_fair_dz(fz, xa, xb):
    """correction dz(x) that replaces z(x) = fz(x) inside (xa, xb) by the quintic Hermite with fz's value / slope / curvature at both ends (G2 join), 0 outside"""
    z0, s0, k0 = _end_state(fz, xa)
    z1, s1, k1 = _end_state(fz, xb)
    q = quintic_h(xa, xb, z0, s0, k0, z1, s1, k1)

    def dz(x):
        x = np.asarray(x, float)
        return np.where((x > xa) & (x < xb), q(np.clip(x, xa, xb)) - np.asarray(fz(x), float), 0.0)
    return dz


# q5 (coordinator, 2026-10-20): below the crest the nose side of the fender is ONE plane in the photo (p016), no fold.  In the model the middle face U -> L (cylinder rule, 48 .. 52 deg) meets the wall
# L -> l3 (vertical) in a 42 deg crease that the soft turn rounds into a dark wedge.  L slides INBOARD (its height stays: p018 sees height only; l3, sill and the p013 outline below stay) onto the straight line U -> l3
# of the section, so the face and the wall are one plane and the crease and the wedge are gone: weight 1 forward of QF_P_X[0], 0 aft of QF_P_X[1] (the arch hides the rest; the crest U never moves).
QF_P_ON = os.environ.get('QF_P_ON', '0') == '1'      # OFF: on hold (coordinator, 2026-10-20: the U -> L section / face is being re-briefed)
QF_P_X = tuple(float(v) for v in os.environ.get('QF_P_X', '-1.95,-1.72').split(','))


def qf_u_lift(xN):
    ta = QF_U_BA / (QF_U_BA + QF_U_BB)
    nrm = ta ** QF_U_BA * (1.0 - ta) ** QF_U_BB

    def dz(x):
        t = np.clip((np.asarray(x, float) - xN) / (QF_U_XE - xN), 0.0, 1.0)
        return QF_U_AZ * t ** QF_U_BA * (1.0 - t) ** QF_U_BB / nrm
    return dz


def qf_u_plan(dy_old, fy_old, xN, yN):
    """dy_old(x) + the q4 correction: U's plan y(x) on [xN, QF_U_XF] is y_new, G2 into the old curve at the pillar foot"""
    xb = QF_U_XF
    y1, s1, k1 = _end_state(fy_old, xb)
    L = xb - xN
    kn = [(xN, 1.0)] + list(zip(QF_U_GK, QF_U_G)) + [(xb - 0.10, 0.0), (xb, 0.0)]
    xs_ = np.linspace(xN, xb, 1201)
    gs_ = np.array([pchip(kn, x) for x in xs_])
    Gi = np.concatenate([[0.0], np.cumsum(0.5 * (gs_[1:] + gs_[:-1]) * np.diff(xs_))])           # integral of g from N
    # the k1 blend adds 0.5 k1 (x - xb)^2 sstep(.) to y: its value at N is 0.5 k1 (xN - xb)^2 sstep(xN) = 0 for blends shorter than L
    A = (y1 - yN - s1 * L) / Gi[-1]                                                          # s(x) = s1 + A g(x): the integral reproduces the foot's y

    def y_new(x):
        x = np.clip(np.asarray(x, float), xN, xb)
        y = yN + s1 * (x - xN) + A * np.interp(x, xs_, Gi)
        return y + 0.5 * k1 * (x - xb) ** 2 * sstep(xb - QF_U_BLEND, xb, x)

    def dy(x):
        x = np.asarray(x, float)
        xe = np.maximum(x, xN)
        return dy_old(x) + QF_U_MIX * np.where(x < xb, y_new(xe) - np.asarray(fy_old(xe), float), 0.0)
    dy.info = dict(sN=s1 + A, k1=k1, s1=s1, y1=y1)
    return dy


def _unimodal(kg, tol):
    """True when the (positive) curvature samples kg rise and then fall only: no fall followed by a rise (one peak, no dip, no wobble)"""
    d = np.diff(np.asarray(kg, float))
    iu, idn = np.where(d > tol)[0], np.where(d < -tol)[0]
    return not (len(iu) and len(idn) and iu.max() > idn.min())


def fit_plan(fy_old, xN, yN, xj, pts=None, mono=True, kmin=-9.0, s0_fix=None):
    """plan y(x) of a nose curve on [xN, xj]: a quintic that starts at (xN, yN) and joins the old curve fy_old at xj with the same value, slope AND curvature (G2).  The free start slope / curvature are
    chosen with the curve CONVEX the whole way (no inflection) and, if mono, with ONE curvature peak only (the geometric curvature y'' / (1 + y'^2)^1.5 rises and then falls, never dips and rises again;
    a strictly decreasing curvature from N cannot follow the photo: its chamfer is straight then rounds into the side), by least squares against the photo outline `pts` (list of (x, y)); without pts: the
    least bending energy.  Returns (callable, info)."""
    y1, s1, k1 = _end_state(fy_old, xj)
    xs = np.linspace(xN, xj, 100)
    px = np.array([p for p in (pts or []) if xN + 0.015 < p[0] < xj])
    best = None
    for s0 in (np.linspace(0.3, 2.2, 77) if s0_fix is None else [s0_fix]):
        for k0 in np.linspace(kmin, -0.3, 156):
            f = quintic_h(xN, xj, yN, s0, k0, y1, s1, k1)
            y = f(xs)
            d1 = np.gradient(y, xs)
            kk = np.gradient(d1, xs)[2:-2]
            kg = -kk / (1 + d1[2:-2] ** 2) ** 1.5
            if kk.max() > -0.02 or (mono and not _unimodal(kg, MONO_TOL)):          # convex, and one curvature peak
                continue
            if len(px):
                e = np.abs(f(px[:, 0]) - px[:, 1])
                sc = float(e.mean())
            else:
                sc = float(np.sum(kk ** 2))
            if best is None or sc < best[0]:
                best = (sc, s0, k0, f)
    if best is None:
        raise RuntimeError('fit_plan: no convex curve with one curvature peak')
    return best[3], dict(score=best[0], s0=best[1], k0=best[2], join=(y1, s1, k1))


class _Fn1:
    """callable y(x) with numerical d1 / d2 (so a modified curve behaves like a fit3 curve where d1 / d2 are used)"""

    def __init__(self, f):
        self.f = f

    def __call__(self, x):
        return self.f(np.asarray(x, float))

    def d1(self, x, e=1e-4):
        x = np.asarray(x, float)
        return (self.f(x + e) - self.f(x - e)) / (2 * e)

    def d2(self, x, e=1e-3):
        x = np.asarray(x, float)
        return (self.f(x + e) - 2 * self.f(x) + self.f(x - e)) / e ** 2


class PlanMod:
    """an old curve (x -> y, z) + a plan (y) and a height (z) correction dy(x), dz(x) that vanish (value, slope, curvature) beyond the modified stretch; starts at x0 (the new nose corner)"""

    def __init__(self, old, x0, dy, dz, name=''):
        self.old, self.x0, self.x1, self.name, self.dy, self.dz = old, x0, old.x1, name, dy, dz
        self.fy = _Fn1(lambda x: np.asarray(old.fy(x), float) + dy(np.maximum(x, x0)))
        self.fz = _Fn1(lambda x: np.asarray(old.fz(x), float) + dz(np.maximum(x, x0)))
        self.resid = getattr(old, 'resid', None)

    def at(self, x):
        x = np.asarray(x, float)
        return np.stack([x, self.fy(x), self.fz(x)], -1)

    def tan(self, x, eps=1e-4):
        x = np.asarray(x, float)
        a, b = np.maximum(x - eps, self.x0), x + eps
        return (self.at(b) - self.at(a)) / (b - a)[..., None]

    def __call__(self, x):
        return self.at(x)


class ExtCurve:
    """R1e3: a legacy curve (starts at x -2.39 / -2.40) continued FORWARD to x_new along its end tangent (a straight line in 3-D); aft of the legacy start it is the legacy curve itself, so nothing aft
    changes.  Needed because the nose corner N may lie forward of the legacy start.  Returns `old` unchanged when x_new is not forward of it."""

    def __new__(cls, old, x_new):
        if x_new >= old.x0 - 1e-12:
            return old
        return super().__new__(cls)

    def __init__(self, old, x_new):
        self.old, self.x0, self.x1, self.name = old, float(x_new), old.x1, old.name
        xa = float(old.x0)
        # 2026-10-24: the end tangent as a forward difference over 1 mm.  old.tan(x0) of a fitted curve (BFit1D) is a central difference across the clamped start: HALF the slope (L: dz/dx 0.121 for 0.24,
        # dy/dx 0.665 for 1.30), so every continued curve had a kink at x0 = -2.39; the corner's old height hid it in L's monotone-slope fit (qf_c11_dz_L), the lower corner N of 2026-10-24 does not
        _h = 1e-3
        t = (np.asarray(old.at(np.array(xa + _h)), float) - np.asarray(old.at(np.array(xa)), float)) / _h
        p = np.asarray(old.at(np.array(xa)), float)
        self.fy = _Fn1(lambda x: np.asarray(old.fy(np.maximum(np.asarray(x, float), xa)), float) + t[1] * np.minimum(np.asarray(x, float) - xa, 0.0))
        self.fz = _Fn1(lambda x: np.asarray(old.fz(np.maximum(np.asarray(x, float), xa)), float) + t[2] * np.minimum(np.asarray(x, float) - xa, 0.0))
        self.resid = getattr(old, 'resid', None)

    def at(self, x):
        x = np.asarray(x, float)
        return np.stack([x, self.fy(x), self.fz(x)], -1)

    def tan(self, x, eps=1e-4):
        x = np.asarray(x, float)
        a, b = np.maximum(x - eps, self.x0), x + eps
        return (self.at(b) - self.at(a)) / (b - a)[..., None]

    def __call__(self, x):
        return self.at(x)


# G-5 (2026-10-19): the paint | black boundary of the rear quarter is ONE straight line in the side view, from where it comes out behind the rear wheel arch to the tail corner (p018: the shell's l3 was 2.4-4 cm
# (7-12 px) too low at x 1.95-2.3).  p018 reading: the boundary through cam.py (unproject at |y| 1.045), metres (x, z).  The tail-corner end of l3 (where it meets the tail face; the locked tail panels
# start from that point) does not move: the line is fitted through it (least squares for the slope), and the old curve is blended into it inside the wheel-arch hole (x 1.45 - 1.93, the part of l3
# that is cut away), so that the straight line is what you see.
L3_REAR_READ = [(1.947, 0.648), (2.017, 0.680), (2.087, 0.714), (2.198, 0.764), (2.338, 0.834)]
L3_REAR_BLEND = (1.45, 1.93)


def l3_rear_dz(l30, dyL):
    """-> (dy, dz): the corrections of the old l3 (plan and height) that make its rear stretch ONE straight 3-D line from the wheel-arch hole to the (unmoved) tail-corner end"""
    x = 2.36
    for _ in range(60):                                                  # the tail-corner end of the OLD l3: where it meets the tail face
        x = float(tail_x(float(l30.fy(x)) + float(dyL(x)), float(l30.fz(x))))
    ze, ye = float(l30.fz(x)), float(l30.fy(x))
    xs = np.array([p[0] for p in L3_REAR_READ]) - x
    zs = np.array([p[1] for p in L3_REAR_READ]) - ze
    slope = float((xs * zs).sum() / (xs * xs).sum())                     # the line passes through the end point
    xa = L3_REAR_BLEND[1]
    ya = float(l30.fy(xa))
    sy = (ya - ye) / (xa - x)                                            # plan: the chord from the old l3 at the end of the blend to the end point (it was 13 mm bowed outward)
    w = lambda xx: sstep(L3_REAR_BLEND[0], L3_REAR_BLEND[1], np.asarray(xx, float))
    dz = lambda xx: w(xx) * (ze + slope * (np.asarray(xx, float) - x) - np.asarray(l30.fz(np.asarray(xx, float)), float))
    dy = lambda xx: w(xx) * (ye + sy * (np.asarray(xx, float) - x) - np.asarray(l30.fy(np.asarray(xx, float)), float))
    return dy, dz


# G-5 (coordinator ruling Q1 b, 2026-10-19): the corner flap is a TRUE PLANE.  The crest U between N and B (U[0..TRI_K], the flap's outer edge) is moved in z so that it lies in a plane through the straight edge
# L5.  N and C (on L5) do not move; B keeps its x, y and its z within FLAP_B_TOL (the p005 seam corner stays put); of the planes through L5 that do that, the one with the smallest largest move of U is
# taken (the best plane about L5 misses U by 9.84 mm along its normal = 10.5 mm in z, but then B would have to drop 10 mm; with B held the largest move is ~16 mm, at x -2.2).  Behind B the correction
# is continued with the plane's value, slope AND curvature (so U is G2 at B) and dies out smoothly (quintic, FLAP_BLEND metres: long enough that the fender top's tilt keeps falling monotonically behind the
# flap; the correction behind B stays under 6 mm), so U, and with it the
# door-glass strip, is untouched from x -1.43 on.
FLAP_B_TOL, FLAP_BLEND = 0.003, 0.50


def flap_plane_dz(Uc, xN):
    N_, W_ = np.array(N, float), np.array(W, float)
    xs = np.array([squeezed_x(xN, k) for k in range(TRI_K + 1)])
    P = np.asarray(Uc.at(xs), float)
    t5 = _unit(W_ - N_)
    nH = _unit(np.array([-HOOD_B, 0.0, 1.0]))
    nH0 = _unit(nH - (nH @ t5) * t5)
    mm = _unit(np.cross(nH0, t5))
    best = None
    for th in np.linspace(-0.3, 0.3, 6001):
        nn = math.cos(th) * nH0 + math.sin(th) * mm
        if nn[2] < 0:
            nn = -nn
        dz = -((P - N_) @ nn) / nn[2]
        if abs(dz[-1]) > FLAP_B_TOL:
            continue
        if best is None or np.abs(dz).max() < best[0]:
            best = (float(np.abs(dz).max()), th, nn)
    if best is None:
        raise RuntimeError('flap plane: no plane through L5 keeps B within %.1f mm' % (FLAP_B_TOL * 1e3))
    nn = best[2]
    dq = float(nn @ N_)
    xB = float(xs[-1])

    def dzp(x):
        x = np.asarray(x, float)
        return (dq - nn[0] * x - nn[1] * np.asarray(Uc.fy(x), float)) / nn[2] - np.asarray(Uc.fz(x), float)
    h = 2e-3
    dB = float(dzp(xB))
    m = float((dzp(xB + h) - dzp(xB - h)) / (2 * h))
    c = float((dzp(xB + h) - 2 * dzp(xB) + dzp(xB - h)) / (h * h))

    def dz(x):
        x = np.asarray(x, float)
        t = x - xB
        return np.where(x <= xB, dzp(x), (dB + m * t + 0.5 * c * t * t) * (1.0 - sstep(xB, xB + FLAP_BLEND, x)))
    dz.info = dict(tilt=best[1], dz_B=dB, dz_max=best[0])
    return dz


# fender3 (2026-10-20, user: the real fender has three faces, the upper one leans up, the middle and the lower one are nearly flat and meet softly):
#   TILT_DEG  the top face (L5 -> U) leans outward-up by this angle: U is lifted by tan(TILT) (y_U - y_L5) over the hood-plane height (the hood is flat across the car, so the model's top face was level).  The lift grows with a concave
#             ramp from the nose corner (U's side-view slope keeps falling), is full to TILT_X_A (-1.9) and fades to 0 (value, slope, curvature) at the pillar foot x -1.43, which stays where it is (the glass / pillar panels are locked); the fade has a long flat tail so that U's side-view slope stays monotone.
#             The A-pillar end of the top face is the straight cowl diagonal W -> A (level) and U (monotone slope, pinned foot) cannot rise above the hood plane there: the face leans up by TILT_DEG at x -2.0 and by ~2.8 deg at -1.8, and is 12 mm BELOW the hood edge at the cowl (was 14 mm).
#   RULING_DEG  the rulings U -> L of the middle face have this angle (to the horizontal) at every station from x -1.8 on: L's height is z_U - (y_L - y_U) tan(RULING_DEG), so the face is a cylinder (developable: straight
#             reflection stripes, no twist: the traced rulings went 91 -> 50 -> 57 degrees); it fades back to the traced L aft of x RULING_X0 (the wheel arch hides x -1.9 .. -1.07)
TILT_DEG = float(os.environ.get('TILT_DEG', '3.0'))
TILT_X_A, TILT_X_B, TILT_RAMP = float(os.environ.get('TILT_X_A', '-1.9')), -1.43, 0.45
TILT_FADE_M = float(os.environ.get('TILT_FADE_M', '5.0'))          # the fade of the lift into the pillar foot: its curvature must stay below the crest's own roll-off (|z''| <= 1.3 1/m at x -1.7), or U's slope dips and rises again (the cowl end of the top face then shows an island)
RULING_DEG = float(os.environ.get('RULING_DEG', '55.0'))
RULING_XN0, RULING_XN1 = -2.00, -1.80                 # the ruling rule fades in over this stretch (forward of it the face is a narrow sliver whose rulings already fall smoothly 91 -> 54 degrees: it keeps the traced L)
RULING_X0, RULING_X1 = -1.85, -1.25


def tilt_lift(Uc):
    N_, W_ = np.array(N, float), np.array(W, float)
    tt = math.tan(math.radians(TILT_DEG))

    def dz(x):
        x = np.asarray(x, float)
        yl5 = N_[1] + (W_[1] - N_[1]) * (x - N_[0]) / (W_[0] - N_[0])
        t = np.clip((x - N_[0]) / TILT_RAMP, 0.0, 1.0)
        ramp = 1.0 - (1.0 - t) ** 3
        tf = np.clip((x - TILT_X_A) / (TILT_X_B - TILT_X_A), 0.0, 1.0)
        m = TILT_FADE_M                                                      # g(t) = (1-t)^m (1 + m t + m(m+1)/2 t^2): value, slope AND curvature 0 at the start; flat (m >= 3: curvature 0 too) at the pillar foot; m > 3 front-loads the fall and gives a long gentle tail
        fade = (1.0 - tf) ** m * (1.0 + m * tf + m * (m + 1) / 2.0 * tf ** 2)
        return tt * (np.asarray(Uc.fy(np.maximum(x, N_[0])), float) - yl5) * ramp * fade
    return dz


def ruling_dz(Uc, Lc):
    """the correction of L's HEIGHT (its plan, and with it the p013 outline and the wall below, stay) that gives the rulings U -> L the angle RULING_DEG; it starts at the nose with the traced L (the face is a thin sliver there) and fades
    back to it aft of RULING_X1 (the wheel arch hides x -1.9 .. -1.07)"""
    tn = math.tan(math.radians(RULING_DEG))

    def dz(x):
        x = np.asarray(x, float)
        xe = np.clip(x, N[0], RULING_X1)                                    # (the weight is 0 aft of RULING_X1: nothing is evaluated out of the curves' range)
        u, l = Uc.at(xe), Lc.at(xe)
        w = sstep(RULING_XN0, RULING_XN1, x) * (1.0 - sstep(RULING_X0, RULING_X1, x))
        return w * (u[..., 2] - (l[..., 1] - u[..., 1]) * tn - l[..., 2])
    return dz


def build_all():
    CURVES.clear()
    L = build_L()
    rail_roof = reg(fit3(dense(ROOF_RAIL_K, -0.40, 2.41, 50), 8, 'rail_roof'))
    rail_roof_lk = rail_roof                                              # the locked fit (the R1c glass fit below must not move: nothing at x <= 0.5 changes)
    global QR_C0_OLD
    QR_C0_OLD = np.asarray(rail_roof.at(X_TIP), float)                  # the locked C0 (the deck behind the wing seam and the tail face must not feel the new crest)
    if QR_ON:
        rail_roof = reg(_qr_roof(rail_roof, L))
    U = build_U(L, rail_roof)
    global A_IN, A_OUT, T_OUT, A_IN_L
    A_OUT = tuple(float(v) for v in U.at(-1.43))                      # the pillar foot lies exactly on the crest curve
    # the foot rung lies ON the straight cowl diagonal W -> A_OUT (the end row of the fender top is ONE straight line: no kink where the crest surface runs into the pillar foot)
    _d = np.array(A_OUT, float) - np.array(W, float)
    _d /= np.linalg.norm(_d)
    A_IN = tuple(float(v) for v in (np.array(A_OUT, float) - PILL_W * _d))
    # apillar: lowering W by 30 mm turns the cowl diagonal W -> A_OUT, and with it the foot point A_IN (on that line, 3.5 cm before A_OUT), by 2.4 mm.  The straight A-pillar line pivots about its top T, so a full 2.4 mm at the foot
    # would still be 1.4 mm at x -1.0: the pillar line (and the roof-header / glass edge that grow out of it) starts from a point that follows only PILL_FOLLOW of the move (<= 1 mm at x > -1.0); the foot corner A_IN itself
    # moves in full and the edges that meet there are snapped onto it (shell2.snap, tolerance 3 mm).
    _dold = np.array(A_OUT, float) - np.array((W[0], W[1], 0.870), float)
    _dold /= np.linalg.norm(_dold)
    _a_old = np.array(A_OUT, float) - PILL_W * _dold
    A_IN_L = tuple(float(v) for v in (_a_old + PILL_FOLLOW * (np.array(A_IN, float) - _a_old)))
    A_IN_L = (A_IN[0], A_IN_L[1], A_IN_L[2])
    sill0 = reg(fit3(dense(SILL_K, -2.40, 1.80, 60), 7, 'sill'))
    l30 = reg(fit3(dense(L3_K, -2.40, 2.41, 80), 9, 'l3'))
    # ---- R1e2: the nose corner N moved aft along the hood plane: L, U (and l3, sill, which follow L's plan) are modified between N and a join, nowhere else
    #   L    plan: a convex quintic from N, G2 into the old L at X_JL (the front edge of the wheel arch), fitted to the p013 corner outline; height: lifted to N at the nose, the old one aft of X_ZFIX
    #   U    plan and height: the same, within U_WIN of N
    #   l3, sill: the same plan displacement as L (the wall below L keeps its shape, slid inboard)
    xN = float(N[0])
    L0, U0 = ExtCurve(CURVES['L'], xN), ExtCurve(CURVES['U'], xN)          # R1e3: continued forward by their end tangent when N lies forward of the legacy start x -2.39
    l30, sill0 = ExtCurve(l30, xN - 0.03), ExtCurve(sill0, xN - 0.03)
    fyL, infoL = fit_plan(L0.fy, xN, N[1], X_JL, photo_corner(xN, N[1]), mono=True)
    xjU = max(xN + U_WIN, U_XJ)                                               # the crest's window: U_WIN from N, but not shorter than up to U_XJ (a corner forward of the legacy one needs the longer window)
    for ds in [0.0] + [sg * 0.025 * k for k in range(1, 25) for sg in (-1, 1)]:      # the start slope nearest to U_S0 for which a convex G2 curve exists (a corner further forward needs a lower one)
        try:
            fyU, infoU = fit_plan(U0.fy, xN, N[1], xjU, None, mono=False, s0_fix=U_S0 + ds)
            break
        except RuntimeError:
            continue
    else:
        raise RuntimeError('U: no convex G2 curve from N to the legacy crest')       # U keeps the user-corrected slope 0.828 (the legacy crest parabola at N_OLD) at N

    mk = lambda fnew, fold, xj: (lambda x: np.where(np.asarray(x, float) < xj, fnew(np.maximum(x, xN)) - fold(np.maximum(x, xN)), 0.0))
    dyL, dyU = mk(fyL, L0.fy, X_JL), mk(fyU, U0.fy, xjU)
    if QF_U_ON:                                               # q4 front: U's plan over the wheel (see qf_u_plan)
        _dyU0 = dyU
        dyU = qf_u_plan(_dyU0, lambda x: np.asarray(U0.fy(np.maximum(np.asarray(x, float), xN)), float) + _dyU0(x), xN, float(N[1]))
    zfix = lambda c: (lambda x: (N[2] - float(c.fz(xN))) * (1.0 - sstep(xN, X_ZFIX, np.asarray(x, float))))
    zero = lambda x: 0.0 * np.asarray(x, float)
    CURVES['L_old'], CURVES['U_old'] = L0, U0
    L_cur = PlanMod(L0, xN, dyL, zfix(L0), 'L')
    U_pre0 = PlanMod(U0, xN, dyU, zfix(U0), 'U')
    dzT = tilt_lift(U_pre0)                                   # fender3: the top face leans outward-up (U lifted over the hood-plane height)
    dzQ = qf_u_lift(xN) if QF_U_ON else zero                  # q4 front: U's height (see QF_U_AZ)
    U_pre = PlanMod(U0, xN, dyU, lambda x: zfix(U0)(x) + dzT(x) + dzQ(x), 'U')
    dzF = flap_plane_dz(U_pre, xN)
    CURVES['U'] = PlanMod(U0, xN, dyU, lambda x: zfix(U0)(x) + dzT(x) + dzQ(x) + dzF(x), 'U')
    if QF_G_ON:                                               # q5: fair the curvature step of U's height (see qf_fair_dz)
        _Uc = CURVES['U']
        _dzG = qf_fair_dz(_Uc.fz, QF_G_U[0], QF_G_U[1])
        CURVES['U'] = PlanMod(U0, xN, dyU, lambda x: zfix(U0)(x) + dzT(x) + dzQ(x) + dzF(x) + _dzG(x), 'U')
    FLAP_INFO.clear(); FLAP_INFO.update(dzF.info)
    Ur = CURVES['U']
    if QF_U_ON:                                               # q4 front: the character line L stays exactly where it was: its ruling rule is evaluated on the OLD crest (the middle face simply gets wider where U moved in)
        _zo = lambda x: zfix(U0)(x)
        _dzTo = tilt_lift(PlanMod(U0, xN, _dyU0, _zo, 'U'))
        _pre = PlanMod(U0, xN, _dyU0, lambda x: _zo(x) + _dzTo(x), 'U')
        _dzFo = flap_plane_dz(_pre, xN)
        Ur = PlanMod(U0, xN, _dyU0, lambda x: _zo(x) + _dzTo(x) + _dzFo(x), 'U')
    dzR = ruling_dz(Ur, L_cur)                                # fender3: the middle face U -> L has parallel rulings (a cylinder): L moves in height only (plan, l3, sill, wall_black stay)
    _dyLw = (lambda x: dyL(x) + qf_l_dy(x)) if QF_L_DY != 0.0 else dyL
    if QF_LP_ON:                                              # q5c: the outermost crease in plan: straight from N, a bend before the wheel, the straight body line (see QF_LP_ON); the ruling rule above used the OLD plan (height only)
        _dyLw = qf_lp_dy(L0.fy, _dyLw, xN, float(N[1]), CURVES['U'].fy)
        QF_LP_INFO.clear(); QF_LP_INFO.update(_dyLw.info)
        _dyLc9 = _dyLw
        if QF_LA_ON:                                          # c10: one even arc instead of the straight leg + the bend (QF_LA_*)
            _dyLw = qf_la_dy(L0.fy, _dyLc9, xN, float(N[1]))
            QF_LA_INFO.clear(); QF_LA_INFO.update(_dyLw.info)
    CURVES['L'] = PlanMod(L0, xN, _dyLw, lambda x: zfix(L0)(x) + dzR(x), 'L')      # q4f2: L moves outward in the stretch the wheel arch hides (see QF_L_DY)
    if QF_G_ON:                                               # q5: fair the curvature wave of L's height (the ruling rule's fade-in, x -2.0 .. -1.8)
        _Lc = CURVES['L']
        _dzGL = qf_fair_dz(_Lc.fz, QF_G_L[0], QF_G_L[1])
        CURVES['L'] = PlanMod(L0, xN, _dyLw, lambda x: zfix(L0)(x) + dzR(x) + _dzGL(x), 'L')
    _l3dy, _l3dz = l3_rear_dz(l30, dyL)
    if QF_LP_ON and QF_LA_ON:                                 # c10: l3 follows the change of L's plan (ramp over x -2.34 .. -2.20: the corner edge E ends at -2.34), the wall keeps its lean
        _l3fo = lambda x: QF_LA_L3 * sstep(-2.34, QF_LA_R, x) * (_dyLw(x) - _dyLc9(x))
    else:
        _l3fo = lambda x: 0.0 * np.asarray(x, float)
    CURVES['l3'] = PlanMod(l30, l30.x0, lambda x: dyL(x) + _l3dy(x) + qf_l3_dy(x) + _l3fo(x), _l3dz, 'l3')
    CURVES['sill'] = PlanMod(sill0, sill0.x0, dyL, zero, 'sill')
    _CF_PRE.clear()
    _CF_PRE['l3'], _CF_PRE['sill'] = CURVES['l3'], CURVES['sill']
    if QF_CF_ON:                                              # c10b: l3 / sill start at the front face's end generator (see QF_CF_ON); the keys R_l3 / R_bot come from the UNMODIFIED curves (the front face must not move)
        _xsp = _CF_PRE['l3'].at(xN + NOSE_D)
        _zl3 = float(_xsp[2])
        _xR = float(xN + NOSE_RAKE * (float(N[2]) - _zl3))
        _l3a, _sla = _CF_PRE['l3'], _CF_PRE['sill']
        _dyl3, _dzl3 = _l3a.dy, _l3a.dz
        _ez3 = _zl3 - float(_l3a.fz(_xR))
        if QF_C11_ON:                                         # c11: the bottom edge of the lower face moves outboard (a smooth bump, C stands more vertical)
            _a3, _b3, _c3, _d3 = QF_C11_L3X
            _h3 = lambda x: QF_C11_DL3 * sstep(_a3, _b3, np.asarray(x, float)) * (1.0 - sstep(_c3, _d3, np.asarray(x, float)))
            _l3tgt = lambda x: np.asarray(_l3a.fy(x), float) + _h3(x)
        else:
            _h3 = lambda x: 0.0 * np.asarray(x, float)
            _l3tgt = _l3a.fy
        _ey3, _cfi3 = qf_cf_start(_l3tgt, _xR, float(N[1]) + QF_FS_K * (float(N[2]) - _zl3), QF_CF_XJ3, 'l3')     # (the leaning crease's foot, QF_FS_K)
        _g3 = lambda x: 1.0 - sstep(_xR, QF_CF_XJ3, x)
        _dy3a = lambda x: _dyl3(x) + _h3(x) + _ey3(x)
        if QF_C11_ON:                                         # c11: the bend where l3 dips into the wheel opening starts without a step (qf_c11_fair)
            _f3 = qf_c11_fair(lambda x: np.asarray(l30.fy(x), float) + _dy3a(x), *QF_C11_L3P, xlo=float(l30.x0))
            QF_C11_INFO['l3_fair'] = _f3.info
            _dy3 = lambda x: _dy3a(x) + _f3(x)
        else:
            _dy3 = _dy3a
        CURVES['l3'] = PlanMod(l30, l30.x0, _dy3, lambda x: _dzl3(x) + _ez3 * _g3(x), 'l3')
        _CF_PRE['info_l3'] = _cfi3
        _CF_PRE['xR'] = _xR
        _CF_PRE['zl3'] = _zl3
        _CF_PRE['z_l3_err'] = _ez3
    if QF_P_ON:                                               # q5: the nose side below the crest is one plane (see QF_P_ON)
        _Lpre, _Upl, _l3c = CURVES['L'], CURVES['U'], CURVES['l3']
        _xlo = max(float(_l3c.x0), float(xN))

        def _qf_p_shift(x):
            x = np.asarray(x, float)
            w = 1.0 - sstep(QF_P_X[0], QF_P_X[1], x)
            xe = np.clip(x, _xlo, QF_P_X[1])
            u, l, k = _Upl.at(xe), _Lpre.at(xe), _l3c.at(xe)
            t = (u[..., 2] - l[..., 2]) / np.maximum(u[..., 2] - k[..., 2], 1e-6)
            return w * ((u[..., 1] + (k[..., 1] - u[..., 1]) * t) - l[..., 1])
        _dyLb = _dyLw
        _dzLb = (lambda x: zfix(L0)(x) + dzR(x) + _dzGL(x)) if QF_G_ON else (lambda x: zfix(L0)(x) + dzR(x))
        CURVES['L'] = PlanMod(L0, xN, lambda x: _dyLb(x) + _qf_p_shift(x), _dzLb, 'L')
    if QF_C11_ON:                                             # c11: U inboard (smooth, single-signed), L's height without the dent
        _Ubase = CURVES['U']
        _dyUc = qf_c11_u_dy(_Ubase.fy, xN)
        CURVES['U'] = PlanMod(_Ubase, xN, _dyUc, zero, 'U')
        QF_C11_INFO['U_fit'] = _dyUc.fit
        _Lbase = CURVES['L']
        _dzLc = qf_c11_dz_L(_Lbase.fz, xN) if QF_C11_LZ else zero
        if QF_C11_LB[0] != 0.0:                                 # c11b: the front-view bell of L (see QF_C11_LB)
            _dzLc0 = _dzLc

            def _dzLc(x, _f=_dzLc0, _A=QF_C11_LB[0], _xa=max(xN, QF_C11_LB[1]), _xb=QF_C11_LB[2]):
                t = np.clip((np.asarray(x, float) - _xa) / (_xb - _xa), 0.0, 1.0)
                return np.asarray(_f(x), float) + 1e-3 * _A * 64.0 * (t * (1.0 - t)) ** 3
            _dzLc.info = getattr(_dzLc0, 'info', None)
        _dyLc = qf_c11_dy_L(_Lbase.fy, xN)
        CURVES['L'] = PlanMod(_Lbase, xN, _dyLc, _dzLc, 'L')
        QF_C11_INFO['L_dz'] = getattr(_dzLc, 'info', None)
        QF_C11_INFO['L_dy'] = getattr(_dyLc, 'info', None)
    NOSE_FIT.clear(); NOSE_FIT.update(L=infoL, U=infoU, dyL=dyL, dyU=dyU, fyL=fyL, fyU=fyU, xjU=xjU)
    _tl5 = lambda x: (np.asarray(x, float) - N[0]) / (W[0] - N[0])
    reg(Fn(N[0], W[0], lambda x: N[1] + (W[1] - N[1]) * _tl5(x), lambda x: N[2] + (W[2] - N[2]) * _tl5(x) + hood_sag(_tl5(x)), 'L5'))      # 2026-10-24: bowed like l5_points (QF_HOOD_SAG)
    reg(line3(W, A_IN, 'cowl_diag'))
    reg(line3(A_IN_L, T, 'pillar_in'))
    reg(line3(A_OUT, T_OUT, 'pillar_out'))
    # ridge inner wall height / plan width (smooth, few control points)
    from curves2 import Spline1D
    sh = Spline1D([p[0] for p in HW_K], [p[1] for p in HW_K])
    sd = Spline1D([p[0] for p in DY_K], [p[1] for p in DY_K])
    HW = lambda x: np.where(np.asarray(x) < 0.15, 0.0, np.where(np.asarray(x) > 2.38, 0.0, np.maximum(sh(np.maximum(x, 0.15)), 0.0)))
    DY = lambda x: np.where(np.asarray(x) < 0.15, 0.0, np.where(np.asarray(x) > 2.38, 0.0, np.maximum(sd(np.maximum(x, 0.15)), 0.0)))
    # the rail: cowl diagonal (straight), A-pillar line (straight), a G1 round-over of the 19 degree bend at the roof header over 0.44 m (radius ~1.2 m), the roof rail (fitted B-spline)
    from curves2 import herm3, SubCurve
    pil = CURVES['pillar_in']
    reg(line3(A_IN_L, tuple(pil.at(XB0)), 'pillar_lo'))
    if QF_HDR_G2:
        # q12 (review 2026-10-22, roof rail): the header was a cubic Hermite (G1): its curvature stepped from the straight A pillar's 0 to ~0.29 / -0.6 at XB0 and back at XB1 (the rail's
        # highlight kinked at the A-pillar top and at x -0.2).  A quintic Hermite matches the curvature at both ends (G2): 0 on the pillar line, the roof rail's own at XB1.
        def _c2(c, x, e=2e-3):
            return (np.asarray(c.at(x + e), float) - 2.0 * np.asarray(c.at(x), float) + np.asarray(c.at(x - e), float)) / (e * e)
        p0, p1 = np.asarray(pil.at(XB0), float), np.asarray(rail_roof.at(XB1), float)
        t0, t1 = np.asarray(pil.tan(XB0), float), np.asarray(rail_roof.tan(XB1), float)
        a1 = _c2(rail_roof, XB1)
        reg(Fn(XB0, XB1, lambda x: quint1(x, XB0, p0[1], t0[1], 0.0, XB1, p1[1], t1[1], a1[1]),
               lambda x: quint1(x, XB0, p0[2], t0[2], 0.0, XB1, p1[2], t1[2], a1[2]), 'header'))
    else:
        reg(herm3(pil, XB0, rail_roof, XB1, 'header'))
    reg(SubCurve(rail_roof, XB1, X_TIP, 'roof_tail'))                                    # the roof rail up to the window tip (the locked rail band ends there)
    rail_r1c = Composite([CURVES['cowl_diag'], CURVES['pillar_lo'], CURVES['header'], SubCurve(rail_roof, XB1, 2.41, 'roof_tail_r1c')], 'rail_r1c')       # the R1c rail (smooth reference)
    C0 = np.asarray(rail_roof.at(X_TIP), float)
    _ex = lambda x: (np.asarray(x, float) - X_TIP) / (E_TARGET[0] - X_TIP)
    crest = reg(Fn(X_TIP, 2.41, lambda x: C0[1] + (E_TARGET[1] - C0[1]) * _ex(x), lambda x: C0[2] + (E_TARGET[2] - C0[2]) * _ex(x), 'crest'))     # R1d: ONE straight line window tip -> ear tip
    if QR_ON:           # aft of the ear tip E the crest keeps the locked line (the tail face and everything behind E stay as they were)
        _ey = lambda x: np.where(np.asarray(x, float) <= E_TARGET[0], C0[1] + (E_TARGET[1] - C0[1]) * _ex(x), E_TARGET[1] + (E_TARGET[1] - QR_C0_OLD[1]) / (E_TARGET[0] - X_TIP) * (np.asarray(x, float) - E_TARGET[0]))
        _ez = lambda x: np.where(np.asarray(x, float) <= E_TARGET[0], C0[2] + (E_TARGET[2] - C0[2]) * _ex(x), E_TARGET[2] + (E_TARGET[2] - QR_C0_OLD[2]) / (E_TARGET[0] - X_TIP) * (np.asarray(x, float) - E_TARGET[0]))
        crest = reg(Fn(X_TIP, 2.41, _ey, _ez, 'crest'))
    if QF_RT_LAM > 0.0:
        # q12d (review 2026-10-22, the beam; user: "都同意"): the roof rail from the header end XB1 to the window tip rolled in curvature (0.28 / 0.15 / 0.28 / 0.15 / 0.52 /m, a torsion spike at x 0.40 where
        # the q4r quintic starts).  It is refitted here: G2 with the header at XB1 and with the straight crest at the tip (ends, slopes, curvatures kept), in between a least-squares fit to the old
        # rail with a penalty on the third derivative (fairness, weight QF_RT_LAM): max move 5.6 mm (out / up at x 0.5 - 0.6); the 0.40 dip and its twist go, one shallow trough (0.13) at x 0.7
        # remains before the turn into the tip (removing it moves the rail 13+ mm).  The window line follows (it is the rail + the strip offset).
        _rt0 = CURVES['roof_tail']
        _xa, _xb = XB1, X_TIP
        _xs = np.linspace(_xa, _xb, 600)
        _t = (_xs - _xa) / (_xb - _xa)
        _h = _xb - _xa
        _e = 2e-3
        _P = np.asarray(_rt0.at(_xs), float)
        _pa = np.asarray(_rt0.at(_xa), float)
        _da = (np.asarray(_rt0.at(_xa + _e), float) - np.asarray(_rt0.at(_xa), float)) / _e
        _ca = (np.asarray(_rt0.at(_xa + 2 * _e), float) - 2 * np.asarray(_rt0.at(_xa + _e), float) + _pa) / _e ** 2
        _pb = np.asarray(crest.at(_xb), float)
        _db = (np.asarray(crest.at(_xb + 0.01), float) - _pb) / 0.01
        _h0 = 1 - 10 * _t ** 3 + 15 * _t ** 4 - 6 * _t ** 5
        _h1 = _t - 6 * _t ** 3 + 8 * _t ** 4 - 3 * _t ** 5
        _h2 = 0.5 * _t ** 2 - 1.5 * _t ** 3 + 1.5 * _t ** 4 - 0.5 * _t ** 5
        _h4 = -4 * _t ** 3 + 7 * _t ** 4 - 3 * _t ** 5
        _Bm = np.stack([_t ** 3 * (1 - _t) ** 3 * _t ** j for j in range(10)], 1)          # zero value / slope / curvature at both ends
        _rt_d3 = lambda f: np.gradient(np.gradient(np.gradient(f, _xs, axis=0), _xs, axis=0), _xs, axis=0)
        _B3 = _rt_d3(_Bm)
        _fit = {}
        for _k in (1, 2):
            _b0 = _h0 * _pa[_k] + _h1 * _h * _da[_k] + _h2 * _h * _h * _ca[_k] + (1 - _h0) * _pb[_k] + _h4 * _h * _db[_k]
            _A = np.vstack([_Bm, math.sqrt(QF_RT_LAM) * _B3])
            _y = np.r_[_P[:, _k] - _b0, -math.sqrt(QF_RT_LAM) * _rt_d3(_b0)]
            _c = np.linalg.lstsq(_A, _y, rcond=None)[0]
            _fit[_k] = _b0 + _Bm @ _c
        _fy, _fz = _fit[1], _fit[2]
        CURVES['roof_tail'] = Fn(_xa, _xb, lambda x: np.interp(np.asarray(x, float), _xs, _fy), lambda x: np.interp(np.asarray(x, float), _xs, _fz), 'roof_tail')
        rail_r1c = Composite([CURVES['cowl_diag'], CURVES['pillar_lo'], CURVES['header'], CURVES['roof_tail'], SubCurve(rail_roof, X_TIP, 2.41, 'roof_tail_r1c')], 'rail_r1c')   # the glass edge (= the rail where the ridge wall is 0) follows
    if QF_R1_ZK > 0.0:
        # q13 (review 2026-10-22, the beam seen from behind; user: "都同意"): the ridge R-1 started 12 mm above the rear glass (the triangle between R-1 and the glass edge rolled 23 -> 1 deg along x,
        # its highlight swept round the glass edge), and the rail turned into it over x 0.85 .. 1.2 (side curvature -0.30 /m next to the tip).  R-1 now starts QF_R1_ZK high, so that it runs 0 - 5 mm
        # above the glass edge from the tip to the seam (the triangle lies in the glass' plane), and the rail's side curve is one quintic from QF_R1_X0 to the tip: G2 with the old rail there and
        # with R-1 at the tip, curvature one-signed (peak -0.25 /m at x 0.83).  In plan nothing moves (R-1 keeps its start and the ear tip E); the glass edge keeps its R1c reference (rail_r1c).
        # q13b (user: "你的调整太保守了吧" -> the bold variant): R-1 also starts QF_R1_Y out (in plan), next to the glass edge's corner (p013: the triangle starts at the corner with no width), and the
        # roof rail converges on it steadily from QF_R1_YX0 (one quintic, |y''| <= 0.17 /m instead of the parallel stretch at the B pillar and the -0.35 /m turn at x 1.0): seen from behind the
        # beam runs straight into the tail.  The window line keeps the q12 rail (rail_wl below): the beam top widens towards the window tip, as in official-02.
        _rail_wl_pieces = (CURVES['roof_tail'], crest)
        C0 = np.array([C0[0], QF_R1_Y if QF_R1_Y > 0.0 else C0[1], QF_R1_ZK])
        if QF_R1_Y > 0.0:
            _cy = lambda x: C0[1] + (E_TARGET[1] - C0[1]) * _ex(x)
            if QR_ON:
                _cy = lambda x: np.where(np.asarray(x, float) <= E_TARGET[0], C0[1] + (E_TARGET[1] - C0[1]) * _ex(x), E_TARGET[1] + (E_TARGET[1] - QR_C0_OLD[1]) / (E_TARGET[0] - X_TIP) * (np.asarray(x, float) - E_TARGET[0]))
        else:
            _cy = lambda x, _c=crest: _c.at(x)[..., 1]
        crest = reg(Fn(X_TIP, 2.41, _cy, lambda x: C0[2] + (E_TARGET[2] - C0[2]) * _ex(x), 'crest'))
        if QR_ON:
            _ez = lambda x: np.where(np.asarray(x, float) <= E_TARGET[0], C0[2] + (E_TARGET[2] - C0[2]) * _ex(x), E_TARGET[2] + (E_TARGET[2] - QR_C0_OLD[2]) / (E_TARGET[0] - X_TIP) * (np.asarray(x, float) - E_TARGET[0]))
            crest = reg(Fn(X_TIP, 2.41, _cy, _ez, 'crest'))
        _rq = CURVES['roof_tail']
        if QF_R1_Y > 0.0:
            _xy, _ey = QF_R1_YX0, 1e-2
            _y0 = float(_rq.at(_xy)[1])
            _qy = (_xy, _y0, float(_rq.at(_xy + _ey)[1] - _rq.at(_xy - _ey)[1]) / (2 * _ey), float(_rq.at(_xy + _ey)[1] - 2 * _y0 + _rq.at(_xy - _ey)[1]) / _ey ** 2,
                   X_TIP, float(C0[1]), (E_TARGET[1] - C0[1]) / (E_TARGET[0] - X_TIP), 0.0)
            _rq = Fn(_rq.x0, X_TIP, lambda x, _r=_rq, _q=_qy: np.where(np.asarray(x, float) < _q[0], _r.at(x)[..., 1], quint1(x, *_q)), lambda x, _r=_rq: _r.at(x)[..., 2], 'roof_tail')
        _x0, _e = QF_R1_X0, 1e-2          # (the refit rail is sampled every 2.3 mm: wider differences)
        _z0 = float(_rq.at(_x0)[2])
        _d0 = float(_rq.at(_x0 + _e)[2] - _rq.at(_x0 - _e)[2]) / (2 * _e)
        _k0 = float(_rq.at(_x0 + _e)[2] - 2 * _z0 + _rq.at(_x0 - _e)[2]) / _e ** 2
        _s1 = (E_TARGET[2] - C0[2]) / (E_TARGET[0] - X_TIP)
        _q = (_x0, _z0, _d0, _k0, X_TIP, float(C0[2]), _s1, 0.0)             # bound now: the names are reused further down
        CURVES['roof_tail'] = Fn(_rq.x0, X_TIP, lambda x, _r=_rq: _r.at(x)[..., 1],
                                 lambda x, _r=_rq, _q=_q: np.where(np.asarray(x, float) < _q[0], _r.at(x)[..., 2], quint1(x, *_q)), 'roof_tail')
    rail = Composite([CURVES['cowl_diag'], CURVES['pillar_lo'], CURVES['header'], CURVES['roof_tail'], crest], 'rail'); CURVES['rail'] = rail
    rail_wl = Composite([CURVES['cowl_diag'], CURVES['pillar_lo'], CURVES['header']] + list(_rail_wl_pieces), 'rail_wl') if QF_R1_ZK > 0.0 and QF_R1_Y > 0.0 else rail
    rail_r1c_lk = Composite([CURVES['cowl_diag'], CURVES['pillar_lo'], CURVES['header'], SubCurve(rail_roof_lk, XB1, 2.41, 'roof_tail_r1c')], 'rail_r1c')
    gedge_r1c = Fn(-1.625, 2.41, lambda x: rail_r1c_lk.at(x)[..., 1] - DY(x), lambda x: rail_r1c_lk.at(x)[..., 2] - HW(x), 'gedge_r1c')          # the R1c edge (rebuilds the R1c glass fit)
    # ---- R1d glass edge: R1c forward of the B seam, an ease to the hugging strip (P1), a straight edge to P3, then the edge P3 -> E on the wing panel (quadratic in z: G1 with the glass)
    ry_o, rz_o = (lambda x: rail_r1c.at(x)[..., 1]), (lambda x: rail_r1c.at(x)[..., 2])
    ry, rz = (lambda x: rail.at(x)[..., 1]), (lambda x: rail.at(x)[..., 2])
    _s = lambda f, x, e=1e-4: float((f(x + e) - f(x - e)) / (2 * e))
    X_E = E_TARGET[0]
    dy_b = lambda x: herm1(x, X_BL0, float(DY(X_BL0)), _s(DY, X_BL0), X_P1, DY_P1, 0.0)
    hw_b = lambda x: herm1(x, X_BL0, float(HW(X_BL0)), _s(HW, X_BL0), X_P1, HW_P1, 0.0)
    zP1 = float(rz(X_P1)) - HW_P1
    z3 = float(rz(X_SEAM)) - HW_P3
    s_g = (z3 - zP1) / (X_SEAM - X_P1)                                          # the glass edge's slope (it is straight from P1 to P3)
    k_d = 2.0 * ((float(rz(X_E)) - z3) - s_g * (X_E - X_SEAM)) / (X_E - X_SEAM) ** 2        # wing panel edge: z'' (concave up) so that it reaches E and leaves P3 tangent to the glass edge
    y_p1 = float(ry_o(X_P1)) - DY_P1
    qr_dz, qr_y = 0.0, 0.0
    if QR_ON:           # the straight part of the glass edge (P1 -> seam) and the wing panel's edge keep the locked line behind P1; at P1 the edge follows the new crest and returns to the locked line
        rz_lk = lambda x: QR_C0_OLD[2] + (E_TARGET[2] - QR_C0_OLD[2]) * (x - X_TIP) / (E_TARGET[0] - X_TIP)          # (C2 at the seam: the deck stays)
        zP1_lk = float(rz_lk(X_P1)) - HW_P1
        z3 = float(rz_lk(X_SEAM)) - HW_P3
        s_g = (z3 - zP1_lk) / (X_SEAM - X_P1)
        k_d = 2.0 * ((float(E_TARGET[2]) - z3) - s_g * (X_E - X_SEAM)) / (X_E - X_SEAM) ** 2
        qr_dz = float(rz(X_P1)) - HW_P1 - zP1_lk
        ry_lk = lambda x: QR_C0_OLD[1] + (E_TARGET[1] - QR_C0_OLD[1]) * (x - X_TIP) / (E_TARGET[0] - X_TIP)
        qr_y = float(ry_o(X_P1)) - float(ry_lk(X_P1)) - QR_P1_DY                                                   # inboard correction of the edge at P1 (the crest start moved out more than the p017 / high / r81 readings follow)
        y_p1 -= qr_y

    def ge_z(x):
        x = np.asarray(x, float)
        fwd = rz_o(x) - np.where(x < X_BL0, HW(x), hw_b(x))
        b = sstep(1.0, 1.5, x)                                                  # the edge's z leaves the R1c shape smoothly (no crease across the pane at the window tip)
        z = (1 - b) * fwd + b * (z3 + s_g * (x - X_SEAM) + qr_dz * (1.0 - sstep(X_P1, X_SEAM, x)))
        z = np.where(x <= X_SEAM, z, z3 + s_g * (x - X_SEAM) + 0.5 * k_d * (x - X_SEAM) ** 2)
        return np.where(x >= X_E, rz(x), z)

    def ge_y0(x):
        x = np.asarray(x, float)
        return ry_o(x) - np.where(x < X_BL0, DY(x), dy_b(x)) - qr_y * sstep(QR_P1_X0, X_P1, x)
    if QF_GE_FAIR:
        # q12 (review 2026-10-22, glass edge): before P1 the edge was the rail minus a cubic offset minus a smoothstep correction, then at P1 the straight edge to P3 with another slope: in plan
        # its curvature swung -1.6 / +1.1 over x 0.9 .. 1.35 and kinked at P1.  Over QF_GE_X0 .. P1 it is now a quintic: G2 with the old edge at QF_GE_X0, at P1 the straight edge's slope and zero
        # curvature (G2 with it); P1, P3 and the straight edge (R-4) do not move
        _e = 2e-3
        _v0 = float(ge_y0(QF_GE_X0)); _d0 = (float(ge_y0(QF_GE_X0 + _e)) - float(ge_y0(QF_GE_X0 - _e))) / (2 * _e)
        _c0 = (float(ge_y0(QF_GE_X0 + _e)) - 2 * _v0 + float(ge_y0(QF_GE_X0 - _e))) / _e ** 2
        _sl1 = (Y_P3 - y_p1) / (X_SEAM - X_P1)
        ge_y_mid = lambda x: quint1(x, QF_GE_X0, _v0, _d0, _c0, X_P1, y_p1, _sl1, 0.0)
    if QF_GE_CORNER:
        # q13 (review 2026-10-22, the beam seen from behind; user: "都同意"): in p013 (both sides averaged, scale 1.05) the glass edge runs STRAIGHT from the B seam to a crisp corner at x ~1.25 and
        # then on the diagonal to P3; the q12 edge bowed out up to 12 mm at x 1.0 and turned over 0.5 m (x 0.85 .. 1.35), which from behind read as the beam folding inward.  Now: the straight
        # line leaving the B seam with the seam's slope (G1 there, as before: it is the roof glass' transverse seam), a quintic corner over +-QF_GE_R about the vertex where it meets the diagonal
        # P1 -> P3 (G2 with both lines), the diagonal unchanged.  The straight part matches p013 to 1 mm at x 0.8 / 0.9 / 1.0.
        _e = 2e-3
        _gx0 = X_BL0
        _gv0 = float(ge_y0(_gx0))
        _gs1 = (_gv0 - float(ge_y0(_gx0 - _e))) / _e
        _gs2 = (Y_P3 - y_p1) / (X_SEAM - X_P1)
        _gxv = (y_p1 - _gs2 * X_P1 - _gv0 + _gs1 * _gx0) / (_gs1 - _gs2)
        _ga, _gb = _gxv - QF_GE_R, _gxv + QF_GE_R
        _gl1 = lambda x: _gv0 + _gs1 * (x - _gx0)
        _gl2 = lambda x: y_p1 + _gs2 * (x - X_P1)
        ge_y_cor = lambda x: np.where(x < _ga, _gl1(x), np.where(x > _gb, _gl2(x), quint1(x, _ga, _gl1(_ga), _gs1, 0.0, _gb, _gl2(_gb), _gs2, 0.0)))

    def ge_y(x):
        x = np.asarray(x, float)
        a = ge_y0(x)
        if QF_GE_FAIR:
            a = np.where(x >= QF_GE_X0, ge_y_mid(x), a)
        if QF_GE_CORNER:
            a = np.where(x >= X_BL0, ge_y_cor(x), a)
        l1 = y_p1 + (Y_P3 - y_p1) * (x - X_P1) / (X_SEAM - X_P1)
        l2 = Y_P3 + (float(ry(X_E)) - Y_P3) * (x - X_SEAM) / (X_E - X_SEAM)
        return np.where(x < X_P1, a, np.where(x < X_SEAM, l1, np.where(x < X_E, l2, ry(x))))
    gedge = Fn(-1.625, 2.41, ge_y, ge_z, 'gedge'); CURVES['gedge'] = gedge
    # the lens' upper edge = the rail's outer parallel: 3.5 cm outboard, dropping from the crest level at the foot to -0.022 under the roof header, to the B pillar; then straight to the window tip
    tip = tip_point(L, rail_roof)
    dz0 = A_OUT[2] - A_IN[2]
    off_z0 = lambda x: dz0 + (T_DZ - dz0) * sstep(-1.43, -0.40, np.asarray(x, float))
    # q4f2 (user: the lower half of the A pillar is not equally wide): the strip's height rail - wl is only 1-6 mm for x -1.43 .. -1.0 (22 mm under the roof header); the photo (p018) has 8-9 px = ~25 mm all along.  With QF_A_DZ > 0
    # wl is pushed DOWN so that the strip is QF_A_DZ (m) high from x QF_A_X1 on, rising from the foot's own value over QF_A_X0 .. QF_A_X1 (C2) and returning to the old 22 mm under the roof header over QF_A_X2 .. -0.40
    # (nothing changes at x >= -0.40; the foot, A_OUT, stays where it was).
    def off_z(x):
        x = np.asarray(x, float)
        if QF_A_DZ <= 0.0:
            return off_z0(x)
        a, b = qf_a_ramp(x), sstep(QF_A_X2, -0.40, x)
        return -(((1.0 - a) * (-dz0) + a * QF_A_DZ) * (1.0 - b) - T_DZ * b)
    e0 = np.array(A_OUT, float) - rail.at(A_OUT[0]) - np.array([0.0, PILL_W, dz0])           # the foot is a skew rung (A_IN is 1.6 cm ahead of A_OUT): this small offset fades out within 0.4 m
    fade = lambda x: 1.0 - sstep(A_OUT[0], A_OUT[0] + 0.40, x)
    wl_main = Fn(A_OUT[0], X_B, lambda x: rail_wl.at(x)[..., 1] + PILL_W + e0[1] * fade(x), lambda x: rail_wl.at(x)[..., 2] + off_z(x) + e0[2] * fade(x), 'wl_main')
    if QF_AP_STRAIGHT:
        # q12d (review 2026-10-22, the beam; user: "都同意"): the pillar strip's height ramp (a linear wedge rounded over +-8 cm at x -1.03) and the 0.4 m smoothstep fade of the foot offset bent the OUTER
        # edge of the A pillar (curvature bumps 0.2 / 0.6 /m at x -1.34 / -1.03, a knee at the pillar foot in a grazing view) while the inner edge is straight.  From the foot to the header start XB0
        # the outer edge is now one near-straight quintic: the foot point A_OUT kept, leaving it along the chord with zero curvature, G2 with the old edge at XB0 (the strip's height then grows
        # evenly instead of reaching its full 25 mm at -1.03: side view "equal width" is relaxed there, approved).
        _wl0 = wl_main
        _xa, _xb = float(A_OUT[0]), XB0
        _pa, _pb = np.asarray(_wl0.at(_xa), float), np.asarray(_wl0.at(_xb), float)
        _ch = (_pb - _pa) / (_xb - _xa)
        _e = 2e-3
        _db = (np.asarray(_wl0.at(_xb + _e), float) - np.asarray(_wl0.at(_xb - _e), float)) / (2 * _e)
        _cb = (np.asarray(_wl0.at(_xb + _e), float) - 2 * _pb + np.asarray(_wl0.at(_xb - _e), float)) / _e ** 2

        def _wl_ap(x, k):
            x = np.asarray(x, float)
            q = quint1(x, _xa, _pa[k], _ch[k], 0.0, _xb, _pb[k], _db[k], _cb[k])
            return np.where(x < _xb, q, _wl0.at(x)[..., k])
        wl_main = Fn(A_OUT[0], X_B, lambda x: _wl_ap(x, 1), lambda x: _wl_ap(x, 2), 'wl_main')
    b_out = wl_main.at(X_B)
    # B pillar -> window tip: a Hermite arc, tangent to the lens edge at B and leaving along the chord at the tip (a smooth, slightly convex end of the side window)
    from curves2 import _Herm1D
    eps = 1e-4
    sl = lambda f, x: float((f(x + eps) - f(x - eps)) / (2 * eps))
    dyb, dzb = sl(wl_main.fy_, X_B), sl(wl_main.fz_, X_B)
    dyc, dzc = (tip[1] - b_out[1]) / (tip[0] - b_out[0]), (tip[2] - b_out[2]) / (tip[0] - b_out[0])
    wl_tip = XCurve(X_B, tip[0], _Herm1D(X_B, b_out[1], dyb, tip[0], tip[1], dyc), _Herm1D(X_B, b_out[2], dzb, tip[0], tip[2], dzc), 'wl_tip')
    if QF_GE_FAIR:
        # q12 (review 2026-10-22, window line): the cubic arc B -> tip stepped in curvature at B (side 0 -> -0.7, plan +0.45); a quintic with the window line's own curvature at B and the cubic's at the
        # tip (the tip and its slope do not change)
        _c2 = lambda f, x, e=2e-3: float((f(x + e) - 2.0 * f(x) + f(x - e)) / (e * e))
        _hy, _hz = _Herm1D(X_B, b_out[1], dyb, tip[0], tip[1], dyc), _Herm1D(X_B, b_out[2], dzb, tip[0], tip[2], dzc)
        _cyB, _czB = _c2(wl_main.fy_, X_B - 3e-3), _c2(wl_main.fz_, X_B - 3e-3)
        _cyT, _czT = _c2(_hy, tip[0] - 3e-3), _c2(_hz, tip[0] - 3e-3)
        wl_tip = Fn(X_B, tip[0], lambda x: quint1(x, X_B, b_out[1], dyb, _cyB, tip[0], tip[1], dyc, _cyT),
                    lambda x: quint1(x, X_B, b_out[2], dzb, _czB, tip[0], tip[2], dzc, _czT), 'wl_tip')
    if QR_ON and QR_WL_B1 > QR_WL_B0 and not QF_DG_X[1] > 0.0:
        _wt0, _Uc, _rl = wl_tip, CURVES['U'], rail

        def _wl_c(x):
            x = np.asarray(x, float)
            w0, u, r = _wt0.at(x)[..., 1:], _Uc.at(x)[..., 1:], _rl.at(x)[..., 1:]
            wd = np.hypot(*(w0 - u).T) if w0.ndim > 1 else float(np.hypot(*(w0 - u)))
            e = r - u
            e = e / np.maximum(np.hypot(e[..., 0], e[..., 1]), 1e-9)[..., None]
            b = sstep(QR_WL_B0, QR_WL_B1, x)
            return w0 + np.asarray(b)[..., None] * (u + np.asarray(wd)[..., None] * e - w0)
        wl_tip = Fn(X_B, tip[0], lambda x: _wl_c(x)[..., 0], lambda x: _wl_c(x)[..., 1], 'wl_tip')
    wl = Composite([wl_main, wl_tip], 'wl'); CURVES['wl'] = wl
    if QF_WT_LAM > 0.0:
        # q12d (review 2026-10-22, the beam): the door glass' upper edge from the B pillar to the tip had a curvature hump (0.83 /m at x 0.79) and a spike (1.7 - 2.2 /m at x 1.14, the q4r end blend
        # over 7 cm).  X_B .. QF_WT_X1 is refitted like the roof rail: G2 with the old line at both ends (the last 3 cm to the tip, which align the tip rows, are kept), a least-squares fit with a
        # third-derivative penalty in between
        _wwl0_ = wl
        _wxa_, _wxb_ = X_B, QF_WT_X1
        _wxs_ = np.linspace(_wxa_, _wxb_, 500)
        _wt_ = (_wxs_ - _wxa_) / (_wxb_ - _wxa_)
        _wh_ = _wxb_ - _wxa_
        _we_ = 2e-3
        _wP_ = np.asarray(_wwl0_.at(_wxs_), float)
        _wpa_, _wpb_ = np.asarray(_wwl0_.at(_wxa_), float), np.asarray(_wwl0_.at(_wxb_), float)
        _wda_ = (np.asarray(_wwl0_.at(_wxa_ + _we_), float) - _wpa_) / _we_
        _wca_ = (np.asarray(_wwl0_.at(_wxa_ + 2 * _we_), float) - 2 * np.asarray(_wwl0_.at(_wxa_ + _we_), float) + _wpa_) / _we_ ** 2
        _wdb_ = (np.asarray(_wwl0_.at(_wxb_ + _we_), float) - np.asarray(_wwl0_.at(_wxb_ - _we_), float)) / (2 * _we_)
        _wcb_ = (np.asarray(_wwl0_.at(_wxb_ + _we_), float) - 2 * _wpb_ + np.asarray(_wwl0_.at(_wxb_ - _we_), float)) / _we_ ** 2
        _wh0_ = 1 - 10 * _wt_ ** 3 + 15 * _wt_ ** 4 - 6 * _wt_ ** 5
        _wh1_ = _wt_ - 6 * _wt_ ** 3 + 8 * _wt_ ** 4 - 3 * _wt_ ** 5
        _wh2_ = 0.5 * _wt_ ** 2 - 1.5 * _wt_ ** 3 + 1.5 * _wt_ ** 4 - 0.5 * _wt_ ** 5
        _wh4_ = -4 * _wt_ ** 3 + 7 * _wt_ ** 4 - 3 * _wt_ ** 5
        _wh5_ = 0.5 * _wt_ ** 3 - _wt_ ** 4 + 0.5 * _wt_ ** 5
        _wBm_ = np.stack([_wt_ ** 3 * (1 - _wt_) ** 3 * _wt_ ** j for j in range(10)], 1)
        _wt_d3 = lambda f: np.gradient(np.gradient(np.gradient(f, _wxs_, axis=0), _wxs_, axis=0), _wxs_, axis=0)
        _wB3_ = _wt_d3(_wBm_)
        _wfit_ = {}
        for _wk_ in (1, 2):
            _wb0_ = _wh0_ * _wpa_[_wk_] + _wh1_ * _wh_ * _wda_[_wk_] + _wh2_ * _wh_ * _wh_ * _wca_[_wk_] + (1 - _wh0_) * _wpb_[_wk_] + _wh4_ * _wh_ * _wdb_[_wk_] + _wh5_ * _wh_ * _wh_ * _wcb_[_wk_]
            _wA_ = np.vstack([_wBm_, math.sqrt(QF_WT_LAM) * _wB3_])
            _wy_ = np.r_[_wP_[:, _wk_] - _wb0_, -math.sqrt(QF_WT_LAM) * _wt_d3(_wb0_)]
            _wfit_[_wk_] = _wb0_ + _wBm_ @ np.linalg.lstsq(_wA_, _wy_, rcond=None)[0]
        _wgy_, _wgz_ = _wfit_[1], _wfit_[2]
        _wfit = Fn(_wxa_, _wxb_, lambda x: np.interp(np.asarray(x, float), _wxs_, _wgy_), lambda x: np.interp(np.asarray(x, float), _wxs_, _wgz_), 'wl_fair')
        wl = Composite([wl_main, _wfit, SubCurve(_wwl0_, _wxb_, tip[0], 'wl_end')], 'wl'); CURVES['wl'] = wl
    if QF_DG_X[1] > 0.0:
        # q13b (the bold variant): the door glass' cross angle (U -> wl) fell from 51 deg at x 0.85 to 35 deg at the tip (the pane twisted as it narrowed), so the side below the window could not
        # rise steeply into the tip and the soft arc stayed 4 - 7 cm above the photo's (ARC_K).  From QF_DG_X[0] U's plan (the window's lower edge; p013 does not see it there, a design curve) is one
        # quintic to the tip: G2 with the old U at its start, arriving at the tip with the slope that gives the pane the angle QF_DG_X[1] (deg) there, the end curvature the one with the smallest
        # peak curvature.  Nothing moves in side view.
        _dgU0_, _dgW0_ = CURVES['U'], CURVES['wl']
        _dgxa_, _dge_ = QF_DG_X[0], 1e-2
        _dgv_ = float(_dgU0_.at(_dgxa_)[1])
        _dgd_ = float(_dgU0_.at(_dgxa_ + _dge_)[1] - _dgU0_.at(_dgxa_ - _dge_)[1]) / (2 * _dge_)
        _dgc_ = float(_dgU0_.at(_dgxa_ + _dge_)[1] - 2 * _dgv_ + _dgU0_.at(_dgxa_ - _dge_)[1]) / _dge_ ** 2
        _dgT_, _dgh_ = np.asarray(_dgU0_.at(X_TIP), float), 2e-3
        _dgwy_ = float(_dgW0_.at(X_TIP)[1] - _dgW0_.at(X_TIP - _dgh_)[1]) / _dgh_
        _dgwz_ = float(_dgW0_.at(X_TIP)[2] - _dgW0_.at(X_TIP - _dgh_)[2]) / _dgh_
        _dguz_ = float(_dgU0_.at(X_TIP)[2] - _dgU0_.at(X_TIP - _dgh_)[2]) / _dgh_
        _dgs1_ = _dgwy_ + (_dgwz_ - _dguz_) / math.tan(math.radians(QF_DG_X[1]))
        _dgUz_ = None
        if QF_Q14 and QF_Q15 and QF_U15 > 0.0:
            # q15: U also arrives TANGENT to the beam plane n . p = d (side view: the slope z' with n . (1, y', z') = 0, solved together with the plan slope y' of the pane angle), so
            # the band under the window and the plane behind it meet at the tip with no crease along the tip row; the side view changes over the last QF_U15 m only (G2 there)
            _c0_, _e_ = np.array([X_TIP, QF_R1_Y, QF_R1_ZK]), np.asarray(E_TARGET, float)
            _n_ = np.cross(_e_ - _c0_, np.asarray(CURVES['L'].at(X_TIP), float) - _c0_)
            _tg_ = math.tan(math.radians(QF_DG_X[1]))
            _A_ = _dgwy_ + _dgwz_ / _tg_
            _zs_ = -(_n_[0] + _n_[1] * _A_) / (_n_[2] - _n_[1] / _tg_)
            _dgs1_ = _A_ - _zs_ / _tg_
            _ua_, _ue_ = X_TIP - QF_U15, 1e-3
            _uzv_ = float(_dgU0_.at(_ua_)[2])
            _uzd_ = float(_dgU0_.at(_ua_ + _ue_)[2] - _dgU0_.at(_ua_ - _ue_)[2]) / (2 * _ue_)
            _uzc_ = float(_dgU0_.at(_ua_ + 1e-2)[2] - 2 * _uzv_ + _dgU0_.at(_ua_ - 1e-2)[2]) / 1e-4
            _uxs_ = np.linspace(_ua_, X_TIP, 161)
            _ubest_ = min(((float(np.abs(np.gradient(np.gradient(quint1(_uxs_, _ua_, _uzv_, _uzd_, _uzc_, X_TIP, float(_dgT_[2]), _zs_, _ct), _uxs_), _uxs_))[2:-2].max()), _ct)
                            for _ct in np.linspace(-12.0, 12.0, 121)))
            _dgUz_ = (_ua_, _uzv_, _uzd_, _uzc_, X_TIP, float(_dgT_[2]), _zs_, _ubest_[1])
        _dgxs_ = np.linspace(_dgxa_, X_TIP, 241)
        _dgbest_ = None
        for _ct in np.linspace(-4.0, 4.0, 81):
            _yy = quint1(_dgxs_, _dgxa_, _dgv_, _dgd_, _dgc_, X_TIP, float(_dgT_[1]), _dgs1_, _ct)
            _pk = float(np.abs(np.gradient(np.gradient(_yy, _dgxs_), _dgxs_))[2:-2].max())
            if _dgbest_ is None or _pk < _dgbest_[0]:
                _dgbest_ = (_pk, _ct)
        _dgq_ = (_dgxa_, _dgv_, _dgd_, _dgc_, X_TIP, float(_dgT_[1]), _dgs1_, _dgbest_[1])
        _dgUn_ = Fn(_dgU0_.x0, _dgU0_.x1, lambda x, _u=_dgU0_, _q=_dgq_: np.where(np.asarray(x, float) < _q[0], _u.at(x)[..., 1], quint1(x, *_q)),
                    (lambda x, _u=_dgU0_: _u.at(x)[..., 2]) if _dgUz_ is None else
                    (lambda x, _u=_dgU0_, _q=_dgUz_: np.where(np.asarray(x, float) < _q[0], _u.at(x)[..., 2], quint1(x, *_q))), 'U')
        _dgUn_.resid, _dgUn_.dbg = getattr(_dgU0_, 'resid', None), getattr(_dgU0_, 'dbg', None)
        CURVES['U'] = _dgUn_
    if QF_Q16:
        # q16: the window as a recess in the plane P1 (user's choice 2026-10-23: side views of wl and U unchanged, plan only).  wl moves onto P1 (QF_Q16_WL; it was within 2 - 6 mm of it,
        # 14 mm at the tip); U keeps its side view and its plan follows its depth below P1, which closes with zero slope at the tip: a quintic in x from QF_Q16_UX0 (G2 with the old depth
        # there, end curvature the one with the smallest peak) -> U arrives tangent to P1, the tip moves 14 mm inboard onto it
        _Q16.clear()
        if QF_Q16_R1[1] > 0.0:
            # R-1 as p018 shows it (its top outline, column by column): 13 mm higher at the window tip, still the straight line to E aft of the tip (the plane P1 holds it); ahead of the tip
            # the roof rail takes the rise up over QF_Q16_R1[0] .. tip (G2 at the start, the crest's new slope and zero curvature at the tip).  The window tip does not move (it hangs off
            # rail_roof); the rear glass edge and the centre line get the same rise (below, where they are built): R-1 stays flush with the glass
            _R0_, _Ex_ = CURVES['rail'], float(E_TARGET[0])
            _ra_, _rz_ = QF_Q16_R1[:2]
            _rx_ = QF_Q16_R1[2] if len(QF_Q16_R1) > 2 else X_TIP
            _rl_ = lambda x: _rz_ * np.clip((_Ex_ - np.asarray(x, float)) / (_Ex_ - X_TIP), 0.0, 1.0)      # the raise along R-1's straight line (0 at E)
            _rq_ = (_ra_, 0.0, 0.0, 0.0, _rx_, float(_rl_(_rx_)), -_rz_ / (_Ex_ - X_TIP), 0.0)

            def _q16_r1d(x, _q=_rq_, _rl=_rl_):
                x = np.asarray(x, float)
                return np.where(x < _q[0], 0.0, np.where(x <= _q[4], quint1(np.clip(x, _q[0], _q[4]), *_q), _rl(x)))
            _Q16['r1d'] = _q16_r1d
            CURVES['rail'] = Fn(_R0_.x0, _R0_.x1, lambda x, _r=_R0_: _r.at(x)[..., 1], lambda x, _r=_R0_: _r.at(x)[..., 2] + _q16_r1d(x), 'rail')
        if QF_Q16_L[0] > 0.0:
            # the shoulder line L aft of the tip as p018 shows it (its tonal edge, read column by column, less the 7 mm by which that edge runs above L ahead of the window): it rises
            # from the tip to 0.976 by x 1.65 and runs level to the tail (the old fit kept rising to 1.024 at x 2.1, 4 - 5 cm above the photo).  Ahead of the tip L does not change.
            _L0_ = CURVES['L']
            _la_, _le_ = X_TIP, 2e-3
            _lv_ = float(_L0_.at(_la_)[2])
            _ls_ = float(_L0_.at(_la_ + _le_)[2] - _L0_.at(_la_ - _le_)[2]) / (2 * _le_)
            _lc_ = float(_L0_.at(_la_ + 1e-2)[2] - 2 * _lv_ + _L0_.at(_la_ - 1e-2)[2]) / 1e-4
            _lq_ = (_la_, _lv_, _ls_, _lc_, QF_Q16_L[0], QF_Q16_L[1], 0.0, 0.0)

            _lt_ = (QF_Q16_LT[0], QF_Q16_L[1], 0.0, 0.0, QF_Q16_LT[1], QF_Q16_LT[2], 0.0, 0.0) if QF_Q16_LT[0] > 0.0 and not QF_Q17 else None
            _l17_ = None
            if QF_Q17:
                # q17: the corner goes up to the level tail edge.  Aft of the facet apex S the shell runs L on a STRAIGHT line to the corner (shell2.facet_L: the facet's top edge, straight in
                # p018 too); L bends into that line over QF_Q17_L[2] before S (sextic offset, G2 at both ends: level -> the line's slope) and S rises with it by half the slope times the bend.  (A
                # quintic rise near the tail did not reach the shell, which straightens L from S, and with S held the bend before S had to sag: 12 mm at x 1.8, a dip in p018's shoulder line.)
                _xs_, _xl_, _lb_ = QF_Q17_L[:3]
                _l17_ = (_xs_ - _lb_, _lb_, (QF_Q17_ZC - QF_Q16_L[1]) / (_xl_ - _xs_ + 0.5 * _lb_), _xs_, _xl_)
                _Q16['l17'] = _l17_

            def _q16_lz(x, _l=_L0_, _q=_lq_, _t=_lt_, _u=_l17_):
                x = np.asarray(x, float)
                z0 = _l.at(x)[..., 2]
                aft = _q[5] if _t is None else np.where(x <= _t[0], _q[5], quint1(np.clip(x, _t[0], _t[4]), *_t))
                if _u is not None:
                    tb = np.clip((x - _u[0]) / _u[1], 0.0, 1.0)
                    aft = _q[5] + _u[2] * (_u[1] * (2.5 * tb ** 4 - 3.0 * tb ** 5 + tb ** 6) + np.clip(x, _u[3], _u[4]) - _u[3])
                return np.where(x <= _q[0], z0, np.where(x <= _q[4], quint1(np.clip(x, _q[0], _q[4]), *_q), aft))
            CURVES['L'] = Fn(_L0_.x0, _L0_.x1, lambda x, _l=_L0_: _l.at(x)[..., 1], _q16_lz, 'L')
        _qn_, _qd_ = q16_plane()
        _yon_ = lambda x, z: (_qd_ - _qn_[0] * x - _qn_[2] * z) / _qn_[1]
        _pz_ = lambda x, y: (_qd_ - _qn_[0] * x - _qn_[1] * y) / _qn_[2]
        if QF_Q16_P1 == 'ruled':
            # option 1b: the reading of the soft arc (built here from the unchanged U, exactly as CURVES['arc_reading'] below) carries both faces; wl and U close onto the beam face
            _u0_ = np.asarray(CURVES['U'].at(X_FOLD0), float)
            _Q16['rd'] = fit3(dense([(X_FOLD0, _u0_[1], _u0_[2])] + [k for k in ARC_K[1:]], X_FOLD0, 2.41, 60), 6, 'arc_reading')

            def _yon_(x, z):
                yr, zr, t = q16_face(x)
                return yr - (z - zr) / t

            def _pz_(x, y):
                yr, zr, t = q16_face(x)
                return zr + (yr - y) * t
        _qW_, _qU_ = CURVES['wl'], CURVES['U']

        def _q16_wly(x, _w=_qW_):
            x = np.asarray(x, float)
            p = _w.at(x)
            return p[..., 1] + (_yon_(x, p[..., 2]) - p[..., 1]) * sstep(QF_Q16_WL[0], QF_Q16_WL[1], x)

        def _q16_wlz(x, _w=_qW_):
            x = np.asarray(x, float)
            p = _w.at(x)
            return p[..., 2] + (_pz_(x, p[..., 1]) - p[..., 2]) * sstep(QF_Q16_WL[0], QF_Q16_WL[1], x)
        if QF_Q16_AX == 'z':          # (variant: side view instead of plan)
            _qWn_ = Fn(_qW_.x0, _qW_.x1, lambda x, _w=_qW_: _w.at(x)[..., 1], _q16_wlz, 'wl')
        elif len(QF_Q16_WL) == 1:
            # wl's depth below P1 (vertical) closes with zero slope at the tip, from QF_Q16_WL[0] (G2 there; the end curvature with the smallest peak): wl arrives at the tip on P1 and
            # tangent to it (G1 of the rail band with the plane behind the tip); its side view does not change
            _qwdep_ = lambda x: float(_pz_(x, float(_qW_.at(x)[1])) - _qW_.at(x)[2])
            _qwa_, _qwe_ = QF_Q16_WL[0], 1e-3
            _qwv_ = _qwdep_(_qwa_)
            _qws_ = (_qwdep_(_qwa_ + _qwe_) - _qwdep_(_qwa_ - _qwe_)) / (2 * _qwe_)
            _qwc_ = (_qwdep_(_qwa_ + 1e-2) - 2 * _qwv_ + _qwdep_(_qwa_ - 1e-2)) / 1e-4
            _qwxs_ = np.linspace(_qwa_, X_TIP, 201)
            _qwct_ = min(((float(np.abs(np.gradient(np.gradient(quint1(_qwxs_, _qwa_, _qwv_, _qws_, _qwc_, X_TIP, 0.0, 0.0, _ct), _qwxs_), _qwxs_))[3:-3].max()), _ct)
                         for _ct in np.linspace(-20.0, 20.0, 401)))[1]
            _qwq_ = (_qwa_, _qwv_, _qws_, _qwc_, X_TIP, 0.0, 0.0, _qwct_)

            def _q16_wly2(x, _w=_qW_, _q=_qwq_):
                x = np.asarray(x, float)
                p = _w.at(x)
                return np.where(x < _q[0], p[..., 1], _yon_(x, p[..., 2] + quint1(np.clip(x, _q[0], _q[4]), *_q)))
            _qWn_ = Fn(_qW_.x0, _qW_.x1, _q16_wly2, lambda x, _w=_qW_: _w.at(x)[..., 2], 'wl')
        else:
            _qWn_ = Fn(_qW_.x0, _qW_.x1, _q16_wly, lambda x, _w=_qW_: _w.at(x)[..., 2], 'wl')
        if QF_Q16_P1 == 'ruled' and QF_Q16_WLP > 0.0:
            # the roof beam (user 2026-10-23 "这个顶梁有点不规则"): closing wl's depth from x 0.9 pulled it 4.3 cm inboard over the last 0.3 m and the beam strip (wl -> R-1 -> rear glass)
            # first widened, then narrowed, then widened again (a waist seen from behind; official-02 shows both edges straight, the strip widening steadily to the window's end).  wl's plan
            # moves instead by ONE quintic in x from QF_Q16_WLP (G2, nothing changes ahead of it) onto the beam face at the tip, arriving along it (the depth and its slope 0 there)
            _we_ = 1e-3
            _wyT_ = float(_yon_(X_TIP, float(_qW_.at(X_TIP)[2])))
            _fzx_ = (float(_pz_(X_TIP + _we_, _wyT_)) - float(_pz_(X_TIP - _we_, _wyT_))) / (2 * _we_)
            _fzy_ = (float(_pz_(X_TIP, _wyT_ + _we_)) - float(_pz_(X_TIP, _wyT_ - _we_))) / (2 * _we_)
            _wzp_ = float(_qW_.at(X_TIP)[2] - _qW_.at(X_TIP - _we_)[2]) / _we_
            _wyp_ = float(_qW_.at(X_TIP)[1] - _qW_.at(X_TIP - _we_)[1]) / _we_
            _wpD_, _wpS_ = _wyT_ - float(_qW_.at(X_TIP)[1]), (_wzp_ - _fzx_) / _fzy_ - _wyp_
            _wpx_ = np.linspace(QF_Q16_WLP, X_TIP, 301)
            _wpc_ = min(((float(np.abs(np.gradient(np.gradient(quint1(_wpx_, QF_Q16_WLP, 0.0, 0.0, 0.0, X_TIP, _wpD_, _wpS_, _ct), _wpx_), _wpx_))[3:-3].max()), _ct)
                         for _ct in np.linspace(-40.0, 40.0, 801)))[1]
            _wpq_ = (QF_Q16_WLP, 0.0, 0.0, 0.0, X_TIP, _wpD_, _wpS_, _wpc_)
            _qWn_ = Fn(_qW_.x0, _qW_.x1, lambda x, _w=_qW_, _q=_wpq_: _w.at(x)[..., 1] + np.where(np.asarray(x, float) < _q[0], 0.0, quint1(np.clip(x, _q[0], _q[4]), *_q)),
                       lambda x, _w=_qW_: _w.at(x)[..., 2], 'wl')
        _qdep_ = lambda x: float(_pz_(x, float(_qU_.at(x)[1]))) - float(_qU_.at(x)[2])
        _qa_, _qe_ = QF_Q16_UX0, 1e-3
        _qv_ = _qdep_(_qa_)
        _qs_ = (_qdep_(_qa_ + _qe_) - _qdep_(_qa_ - _qe_)) / (2 * _qe_)
        _qc_ = (_qdep_(_qa_ + 1e-2) - 2 * _qv_ + _qdep_(_qa_ - 1e-2)) / 1e-4
        _qxs_ = np.linspace(_qa_, X_TIP, 201)
        if QF_Q16_UC == 'auto':
            _qct_ = min(((float(np.abs(np.gradient(np.gradient(quint1(_qxs_, _qa_, _qv_, _qs_, _qc_, X_TIP, 0.0, 0.0, _ct), _qxs_), _qxs_))[3:-3].max()), _ct)
                         for _ct in np.linspace(-20.0, 20.0, 401)))[1]
        else:
            _qct_ = float(QF_Q16_UC)
        _qq_ = (_qa_, _qv_, _qs_, _qc_, X_TIP, 0.0, 0.0, _qct_)
        _Q16['uq'] = _qq_

        def _q16_uy(x, _u=_qU_, _q=_qq_):
            x = np.asarray(x, float)
            p = _u.at(x)
            return np.where(x < _q[0], p[..., 1], _yon_(x, p[..., 2] + quint1(np.clip(x, _q[0], _q[4]), *_q)))
        if QF_Q16_U == 'face':
            # the window as an opening in ONE face: rows from L at the angle th(x) (a quintic in x: G2 with the ruled rows L -> U at QF_Q16_FX0, the plane's angle at the tip with the rate
            # that makes the face tangent to P1 at the tip (the platform's twist rate there, so the soft arc is born at the tip) and the platform's curvature there (C2 across the tip
            # row)); U keeps its side view and lies on the face: its plan follows (y = L_y - (U_z - L_z) / tan th)
            _qL_ = CURVES['L']
            _th1_ = math.atan2(_qn_[1], _qn_[2])
            _ch_ = lambda x: math.atan2(float(_qU_.at(x)[2] - _qL_.at(x)[2]), float(_qL_.at(x)[1] - _qU_.at(x)[1]))
            _fa_, _fe_ = QF_Q16_FX0, 1e-3
            _fv_ = _ch_(_fa_)
            _fs_ = (_ch_(_fa_ + _fe_) - _ch_(_fa_ - _fe_)) / (2 * _fe_)
            _fc_ = (_ch_(_fa_ + 1e-2) - 2 * _fv_ + _ch_(_fa_ - 1e-2)) / 1e-4
            _hl_ = lambda x: float(_qL_.at(x)[2]) - float(_pz_(x, float(_qL_.at(x)[1])))
            _Tz_ = float(_qU_.at(X_TIP)[2])
            _wT_ = float(_qL_.at(X_TIP)[1]) - _yon_(X_TIP, _Tz_)
            _rT_ = -(_hl_(X_TIP + _fe_) - _hl_(X_TIP - _fe_)) / (2 * _fe_) / _wT_ * math.cos(_th1_) ** 2
            _E_ = np.asarray(E_TARGET, float)
            _LE_ = _qL_.at(_E_[0])
            _kn_ = [(X_TIP, _th1_)] + [(k[0], math.radians(k[1])) for k in QF_Q16_P2 if X_TIP < k[0] < _E_[0]] + [(_E_[0], math.atan2(_E_[2] - _LE_[2], _LE_[1] - _E_[1]))]
            _sp_ = Spline1D([k[0] for k in _kn_], [k[1] for k in _kn_], 'clamped', _rT_, 0.0)
            _cR_ = float((_sp_(X_TIP + 2e-3) - 2 * _sp_(X_TIP + 1e-3) + _sp_(X_TIP)) / 1e-6)
            _fq_ = (_fa_, _fv_, _fs_, _fc_, X_TIP, _th1_, _rT_, _cR_)
            _Q16['fq'] = _fq_

            def _q16_uy(x, _u=_qU_, _l=_qL_, _q=_fq_):
                x = np.asarray(x, float)
                p, l = _u.at(x), _l.at(x)
                th = quint1(np.clip(x, _q[0], _q[4]), *_q)
                return np.where(x < _q[0], p[..., 1], l[..., 1] - (p[..., 2] - l[..., 2]) / np.tan(th))

        if QF_Q16_P1 == 'ruled' and QF_Q16_UP > 0.0:
            # the bright spot under the window tip (user 2026-10-23 "先处理窗尖下的小亮斑"; p017, the front rim light mirrored in the strip reading -> U): the strip's normal follows U's
            # direction, and closing U's depth from x 0.9 kept it 5 - 8 deg less aft-facing than the beam face behind the tip until the last few cm.  U's plan is instead ONE quintic
            # from QF_Q16_UP (G2 with U there) to the beam face at the tip, arriving along it: U turns inboard from about x 1.0 and runs almost straight into the tip (p017 shows the
            # window's lower edge as a straight diagonal into the tip), and the strip faces aft like the beam face from x 1.06 on
            _ue_ = 1e-3
            _uyT_ = float(_yon_(X_TIP, float(_qU_.at(X_TIP)[2])))
            _ufx_ = (float(_pz_(X_TIP + _ue_, _uyT_)) - float(_pz_(X_TIP - _ue_, _uyT_))) / (2 * _ue_)
            _ufy_ = (float(_pz_(X_TIP, _uyT_ + _ue_)) - float(_pz_(X_TIP, _uyT_ - _ue_))) / (2 * _ue_)
            _usT_ = (float(_qU_.at(X_TIP)[2] - _qU_.at(X_TIP - _ue_)[2]) / _ue_ - _ufx_) / _ufy_
            _ua_ = QF_Q16_UP
            _uv_ = float(_qU_.at(_ua_)[1])
            _us_ = float(_qU_.at(_ua_ + _ue_)[1] - _qU_.at(_ua_ - _ue_)[1]) / (2 * _ue_)
            _uc_ = float(_qU_.at(_ua_ + 1e-2)[1] - 2 * _uv_ + _qU_.at(_ua_ - 1e-2)[1]) / 1e-4
            _upx_ = np.linspace(_ua_, X_TIP, 301)
            _upc_ = min(((float(np.abs(np.gradient(np.gradient(quint1(_upx_, _ua_, _uv_, _us_, _uc_, X_TIP, _uyT_, _usT_, _ct), _upx_), _upx_))[3:-3].max()), _ct)
                         for _ct in np.linspace(-60.0, 60.0, 1201)))[1]
            _upq_ = (_ua_, _uv_, _us_, _uc_, X_TIP, _uyT_, _usT_, _upc_)

            def _q16_uy(x, _u=_qU_, _q=_upq_):
                x = np.asarray(x, float)
                return np.where(x < _q[0], _u.at(x)[..., 1], quint1(np.clip(x, _q[0], _q[4]), *_q))

        def _q16_uz(x, _u=_qU_, _q=_qq_):
            x = np.asarray(x, float)
            p = _u.at(x)
            return np.where(x < _q[0], p[..., 2], _pz_(x, p[..., 1]) - quint1(np.clip(x, _q[0], _q[4]), *_q))
        if QF_Q16_AX == 'z':
            _qUn_ = Fn(_qU_.x0, _qU_.x1, lambda x, _u=_qU_: _u.at(x)[..., 1], _q16_uz, 'U')
        else:
            _qUn_ = Fn(_qU_.x0, _qU_.x1, _q16_uy, lambda x, _u=_qU_: _u.at(x)[..., 2], 'U')
        _qUn_.resid, _qUn_.dbg = getattr(_qU_, 'resid', None), getattr(_qU_, 'dbg', None)
        CURVES['wl'], CURVES['U'] = _qWn_, _qUn_
        _Q16['tip'] = np.asarray(_qUn_.at(X_TIP), float)
    if QF_AW:
        # A-pillar round 2 (see QF_AW): wl = the point of the door glass' ruling U -> wl at the height qf_aw_tz (smooth maximum with U: the glass ends in a tip near the foot)
        _aww_, _awu_, _awr_ = CURVES['wl'], CURVES['U'], CURVES['rail']
        _awtz_ = qf_aw_tz(lambda x, _r=_awr_: np.asarray(_r.at(x), float)[..., 2], lambda x, _w=_aww_: np.asarray(_w.at(np.minimum(x, _w.x1)), float)[..., 2])

        def _aw_wl(x, _w=_aww_, _u=_awu_):
            x = np.asarray(x, float)
            w, u = np.asarray(_w.at(x), float), np.asarray(_u.at(x), float)
            h = w[..., 2] - u[..., 2]
            f = qf_smax(_awtz_(x) - u[..., 2], QF_AW_EPS)
            k = np.where(h > 1e-9, f / np.maximum(h, 1e-9), 0.0)
            k = np.where(x >= QF_AW_XT[1], 1.0, k)                    # the old wl exactly (the smooth maximum would lift it off U in the window tip's last mm)
            return u + k[..., None] * (w - u)
        CURVES['wl'] = Fn(_aww_.x0, _aww_.x1, lambda x: _aw_wl(x)[..., 1], lambda x: _aw_wl(x)[..., 2], 'wl')
    # centre line of the glass: the windscreen plane, the dome, then (rear window) the glass edge + crown (-> 0 at the wing seam), then the flat deck (= the glass edge level)
    xs = np.linspace(-1.625, X_SEAM, 80)
    zt = np.array([pchip([(p[0], p[2]) for p in TOP_K], x) for x in xs])
    zg = gedge_r1c.at(xs)[:, 2]
    zt2 = np.where(xs < 0.65, zt, zg + crown(xs))
    zt2[0] = W[2]
    top1 = fit3(np.stack([xs, np.zeros_like(xs), zt2], 1), 10, 'top1')           # (the R1c fit, kept verbatim forward of the B seam)
    # R1d: behind the B seam the centre line is the glass edge level + a crown that dies out by the window tip (the pane is flat behind it), then the flat deck (= the glass edge level)
    zT0, zG0 = float(top1.at(0.65)[2]), float(gedge.at(0.65)[2])
    dc0 = _s(lambda x: top1.at(x)[2], 0.65) - _s(ge_z, 0.65)                     # the crown leaves the B seam with the R1c slope of the centre line
    top_front = SubCurve(top1, top1.x0, 0.65, 'top_front')
    crown_mid = lambda x: herm1(x, 0.65, zT0 - zG0, dc0, X_CR, 0.0, 0.0)
    if QF_TOP_FAIR:
        # q12 (review 2026-10-22, fastback; user: "都同意"): the centre line behind the B seam was the glass edge level (itself a smoothstep blend of the R1c curve into the P1 -> seam line, plus the
        # q4r offset qr_dz (1 - sstep)) + the dying crown: its side curvature changed sign 5 times (convex humps at x 1.20-1.36 and 1.76-2.00 between concave dips).  A monotone-curvature least-squares
        # fit (NNLS over smooth curvature steps) used ONE step: the curvature goes from the old value just aft of the B seam (G1 there: it is the roof glass' transverse seam) to a constant slight concavity over QF_TOP_X and stays there.  Glass and
        # deck are now that one curve from the B seam to E (E's height kept, the step height solved for it; the seam P3 follows the curve, G2 across it); the glass edge is centre - crown, the crown
        # dying out by the window tip as a quintic (zero curvature there).  In plan nothing moves.  Up to ~14 mm lower at the window tip (the old hump); the side silhouette aft of x 0.9 is the
        # R-1 ridge, which does not change.
        xa, xs_ = 0.65, QF_TOP_X
        za = float(top1.at(xa)[2])
        da_ = _s(lambda x: top1.at(x)[2], xa)
        # the start curvature is the OLD rear centre line's (one-sided, aft of 0.65): x 0.65 is the transverse seam of the roof glass (0.64), where the old curves already stepped in curvature;
        # G1 there keeps the change minimal (taking the roof's own -0.33 would lower the window tip by ~21 mm instead of ~14)
        f_old = lambda x: float(ge_z(x) + crown_mid(x))
        e_ = 5e-3
        ca = (f_old(xa + 2 * e_) - 2.0 * f_old(xa + e_) + f_old(xa)) / e_ ** 2
        zE = float(ge_z(X_E))
        xg = np.linspace(xa, X_E, 1801)
        stp = sstep(xs_[0], xs_[1], xg)
        dxg = np.diff(xg)
        cint = lambda f: np.r_[0.0, np.cumsum(0.5 * (f[1:] + f[:-1]) * dxg)]
        s2 = cint(cint(stp))                                                    # height contributed by a unit curvature step
        t_ = xg - xa
        z_base = za + da_ * t_ + 0.5 * ca * t_ * t_
        dc = (zE - z_base[-1]) / s2[-1]                                         # glass and deck: one curve from the B seam to E (E's height kept; the seam height follows)
        zg_ = z_base + dc * s2
        zc_mid = lambda x: np.interp(np.asarray(x, float), xg, zg_)
        z3 = float(zc_mid(X_SEAM))
        # the crown (centre above the edge) dies out by the window tip with zero curvature there (a cubic left a curvature step on the glass edge at x 1.2)
        c0_cr = 6.0 * (0.0 - (zT0 - zG0)) / (X_CR - 0.65) ** 2 - 2.0 * (2.0 * dc0 + 0.0) / (X_CR - 0.65)      # the cubic's own second derivative at 0.65 (kept)
        crown_mid = lambda x: quint1(x, 0.65, zT0 - zG0, dc0, c0_cr, X_CR, 0.0, 0.0, 0.0)
        ge_z_old = ge_z

        def ge_z(x):
            x = np.asarray(x, float)
            z = np.where(x < 0.65, ge_z_old(x), zc_mid(x) - crown_mid(x))
            return np.where(x >= X_E, ge_z_old(x), z)
        gedge = Fn(-1.625, 2.41, ge_y, ge_z, 'gedge'); CURVES['gedge'] = gedge
        top_mid = Fn(0.65, X_SEAM, lambda x: 0.0 * np.asarray(x), zc_mid, 'top_mid')
    else:
        top_mid = Fn(0.65, X_SEAM, lambda x: 0.0 * np.asarray(x), lambda x: ge_z(x) + crown_mid(x), 'top_mid')
    top2 = Fn(X_SEAM, 2.41, lambda x: 0.0 * np.asarray(x), ge_z, 'top2')
    CURVES['top'] = Composite([top_front, top_mid, top2], 'top')
    if QF_Q16 and 'r1d' in _Q16:
        # q16: the rear glass edge and the centre line rise with R-1 (see QF_Q16_R1)
        for _k_ in ('gedge', 'top'):
            _c_ = CURVES[_k_]
            CURVES[_k_] = Fn(_c_.x0, _c_.x1, lambda x, _c=_c_: _c.at(x)[..., 1], lambda x, _c=_c_: _c.at(x)[..., 2] + _Q16['r1d'](x), _k_)
        gedge = CURVES['gedge']
    if QF_Q16 and QF_Q16_P1 == 'ruled' and QF_Q16_GB[0] > 0.0:
        # the beam beside the window (user 2026-10-23: "这个位置可以彻底收进去吗？就像实车图那样", then "我只是希望像原车一样顶梁是笔直的，像真的钢梁一样，可以有点厚度体现").  The
        # strip between R-1 and the glass edge (the beam's inner edge) changed all along: 9 - 14 mm wide and 15 - 20 mm deep (steep, unseen) ahead of x 0.9, nearly flat beside the window's
        # end (a bright sliver there), and the edge bent.  official-02 (x3) shows each beam's inner edge as ONE thin straight face down to the window's end, lit on the right beam and in
        # shadow on the left: the beam's thickness.  The glass edge now keeps a constant offset under R-1 (QF_Q16_GB[3] inboard, [4] down: a constant inner face), reached over [0] .. [1]
        # from the old edge, and returns to the old edge round the glass corner (the vertex of R-1 and the diagonal P1 -> P3: in plan over +-[2], in height over +-[5]).  The diagonal,
        # P1, P3 and everything aft of the corner are unchanged.
        _ge0_, _rl_ = CURVES['gedge'], CURVES['rail']
        _gd_ = lambda x: y_p1 + (Y_P3 - y_p1) * (np.asarray(x, float) - X_P1) / (X_SEAM - X_P1)
        _xg_ = np.linspace(1.0, X_P1, 2001)
        _xv_ = float(_xg_[np.argmin(np.abs(_rl_.at(_xg_)[:, 1] - _gd_(_xg_)))])
        _ga_, _gb_, _gr_, _gwy_, _gwz_, _grz_ = QF_Q16_GB
        _Q16['gb'] = (_ga_, _gb_, _xv_, _gr_, _grz_, _gwy_, _gwz_)

        def _q16_gbw(x, r, _q=_Q16['gb']):
            x = np.asarray(x, float)
            return quint1(x, _q[0], 0.0, 0.0, 0.0, _q[1], 1.0, 0.0, 0.0) * (1.0 - quint1(x, _q[2] - r, 0.0, 0.0, 0.0, _q[2] + r, 1.0, 0.0, 0.0))

        def _q16_gby(x, _g=_ge0_, _r=_rl_, _q=_Q16['gb']):
            w = _q16_gbw(x, _q[3])
            ry_, gy_ = _r.at(x)[..., 1], _g.at(x)[..., 1]
            return ry_ - ((ry_ - gy_) * (1.0 - w) + _q[5] * w)

        def _q16_gbz(x, _g=_ge0_, _r=_rl_, _q=_Q16['gb']):
            w = _q16_gbw(x, _q[4])
            rz_, gz_ = _r.at(x)[..., 2], _g.at(x)[..., 2]
            return rz_ - ((rz_ - gz_) * (1.0 - w) + _q[6] * w)

        CURVES['gedge'] = Fn(_ge0_.x0, _ge0_.x1, _q16_gby, _q16_gbz, 'gedge')
        gedge = CURVES['gedge']
    if QF_Q16 and QF_Q17:
        # q17 (user 2026-10-23: "实车图中的尾部顶面在后视图中似乎是平的，但是模型却是有个梯形的凸起" -> "取中 ≈1.015"): the tail's top edge is ONE level line at QF_Q17[0] from corner to corner
        # (r81: the light box reaches the top edge everywhere; the model's top edge rose from 0.99 at the corners to 1.04 between the ears and left a paint trapezoid over the box).  The deck
        # (centre line and the wing panel's edge P3 -> E) keeps the seam and drops to it by the tail (convex: below); R-1 keeps its line to QF_Q17[2] and
        # meets the deck by QF_Q17[1] (p013: the ear triangle between R-1 and the panel edge closes 4.6 cm before the tail edge; R-1 stays within 1.2 mm of the panel edge, as it was); the corner
        # (L, straight from the facet apex S: QF_Q17_L) and the platform's end chord (_e_tail) go to the same height.  Plan views do not change (but for the corner, 2.4 mm: shell2.facet_L).
        _ze_, _xa_, _xb_ = QF_Q17
        _xe_ = float(E_TARGET[0])
        _r0_, _g0_, _t0_ = CURVES['rail'], CURVES['gedge'], CURVES['top']
        _dg_ = float(_g0_.at(_xe_)[2]) - _ze_
        # (the drop is CONVEX all the way: w = 2t^3 - t^4, G2 with the body at the seam, steepest at the edge and no curvature there, carried on straight past E; a quintic, flat in its
        # rate at both ends, ran -10 -> -18 -> -10 deg in side view: an S, a little ducktail at the edge)
        _wn_ = QF_Q17_N
        _wg_ = lambda x: (lambda t: np.where(t <= 1.0, 0.5 * (_wn_ + 1) * t ** _wn_ - 0.5 * (_wn_ - 1) * t ** (_wn_ + 1), 1.0 + 0.5 * (_wn_ + 1) * (t - 1.0)))(np.maximum((np.asarray(x, float) - X_SEAM) / (_xe_ - X_SEAM), 0.0))
        _Dg_ = lambda x: _dg_ * _wg_(x)
        _e_ = 1e-3
        _da_ = (float(_Dg_(_xa_)), float(_Dg_(_xa_ + _e_) - _Dg_(_xa_ - _e_)) / (2 * _e_), float(_Dg_(_xa_ + _e_) - 2 * _Dg_(_xa_) + _Dg_(_xa_ - _e_)) / _e_ ** 2)
        _qr_ = (_xb_, 0.0, 0.0, 0.0, _xa_) + _da_

        def _Dr_(x, _q=_qr_):
            x = np.asarray(x, float)
            return np.where(x <= _q[0], 0.0, np.where(x < _q[4], quint1(np.clip(x, _q[0], _q[4]), *_q), _Dg_(x)))
        _Ld_ = lambda x: np.where(np.asarray(x, float) >= X_SEAM, _Dg_(x), 0.0)
        if QF_EAR > 0.0:
            # the ear step (QF_EAR): the window and the deck go down by L(x) under R-1 (the window: tan(QF_EAR) x the band's width over the 5 mm beam face, laterally unchanged; past the seam
            # that carried on (value and rate) plus the rest of the old drop, w(t) as before, to the level edge at E).  R-1 keeps its line to the seam, then a quintic (G2 at the seam) brings
            # it down onto the deck at E with the face at its own angle there (s'(E) = tan(QF_EAR) * w'(E), s = R-1 over the panel edge, w = their distance in plan)
            _tn_ = np.tan(np.radians(QF_EAR))
            _wf_ = lambda x: (lambda x: np.maximum(_r0_.at(x)[..., 1] - _g0_.at(x)[..., 1] - 0.005, 0.0) * sstep(0.95, 1.10, x))(np.maximum(np.asarray(x, float), 0.95))
            _sb0_ = _tn_ * float(_wf_(X_SEAM))
            _sb1_ = _tn_ * float(_wf_(X_SEAM) - _wf_(X_SEAM - _e_)) / _e_
            _rest_ = _dg_ - (_sb0_ + _sb1_ * (_xe_ - X_SEAM))

            def _Ld_(x):
                x = np.asarray(x, float)
                return np.where(x <= X_SEAM, _tn_ * _wf_(np.minimum(x, X_SEAM)), _sb0_ + _sb1_ * (x - X_SEAM) + _rest_ * _wg_(x))
            _rg_ = lambda x: float(_r0_.at(x)[2] - _g0_.at(x)[2])
            _wr_ = lambda x: float(_r0_.at(x)[1] - _g0_.at(x)[1])
            _DrE_ = float(_r0_.at(_xe_)[2]) - _ze_
            _rgp_, _wrp_ = (_rg_(_xe_) - _rg_(_xe_ - _e_)) / _e_, (_wr_(_xe_) - _wr_(_xe_ - _e_)) / _e_
            if _DrE_ < 5e-4:
                # the edge at R-1's own end height (QF_Q17[0] = R-1 at E, the corner may stay lower: QF_Q17_ZC): R-1 runs on its line to E and the deck alone closes the step, a quintic
                # from the window's lowering (value, rate) at the seam to R-1's height at E with the face at its own angle there
                _LE_, _LpE_ = -_rg_(_xe_), _tn_ * _wrp_ - _rgp_

                def _Ld_(x):
                    x = np.asarray(x, float)
                    q = quint1(np.clip(x, X_SEAM, _xe_), X_SEAM, _sb0_, _sb1_, 0.0, _xe_, _LE_, _LpE_, 0.0)
                    return np.where(x <= X_SEAM, _tn_ * _wf_(np.minimum(x, X_SEAM)), np.where(x <= _xe_, q, _LE_ + _LpE_ * (x - _xe_)))
                _DrE_ = _DrpE_ = 0.0
            else:
                # (QF_EAR_MONO: at least 5/3 of the mean rate, below which the quintic's slope peaks before E and R-1 sags, then flattens, in side view; off keeps the 2026-10-25 export)
                _DrpE_ = _rgp_ + float(_Ld_(_xe_) - _Ld_(_xe_ - _e_)) / _e_ - _tn_ * _wrp_
                if os.environ.get('QF_EAR_MONO', '0') == '1':
                    _DrpE_ = max(_DrpE_, 5.0 / 3.0 * _DrE_ / (_xe_ - X_SEAM))

            def _Dr_(x):
                x = np.asarray(x, float)
                q = quint1(np.clip(x, X_SEAM, _xe_), X_SEAM, 0.0, 0.0, 0.0, _xe_, _DrE_, _DrpE_, 0.0)
                return np.where(x <= X_SEAM, 0.0, np.where(x <= _xe_, q, _DrE_ + _DrpE_ * (x - _xe_)))
        _Q16['q17'] = (_dg_, _Ld_, _Dr_)

        def _q17_deck(c, name):
            return Fn(c.x0, c.x1, lambda x, _c=c: _c.at(x)[..., 1], lambda x, _c=c: _c.at(x)[..., 2] - _Ld_(x), name)
        CURVES['gedge'], CURVES['top'] = _q17_deck(_g0_, 'gedge'), _q17_deck(_t0_, 'top')
        CURVES['rail'] = Fn(_r0_.x0, _r0_.x1, lambda x, _r=_r0_: _r.at(x)[..., 1], lambda x, _r=_r0_: _r.at(x)[..., 2] - _Dr_(x), 'rail')
        gedge = CURVES['gedge']
        for _k_ in ('rc', 'tw'):
            _Q16.pop(_k_, None)            # (the section angles are taken again from the moved rail and deck)
    # ---- the READING of the soft arc (x-graph, fair B-spline through ARC_K) and the named rear curves
    _FOLD.pop('tip', None)
    u0 = np.asarray(CURVES['U'].at(X_FOLD0), float)
    kn = [(X_FOLD0, u0[1], u0[2])] + [k for k in ARC_K[1:]]
    CURVES['arc_reading'] = fit3(dense(kn, X_FOLD0, 2.41, 60), 6, 'arc_reading')
    P1 = np.array([X_P1, y_p1, float(ge_z(X_P1))])
    P3 = np.array([X_SEAM, Y_P3, z3])
    E = np.array([E_TARGET[0], E_TARGET[1], E_TARGET[2]])
    REAR.clear()
    REAR.update(dict(C0=C0, P1=P1, P3=P3, E=E, X_E=X_E, s_g=s_g, k_d=k_d))
    CURVES['P1'], CURVES['P3'], CURVES['E'] = P1, P3, E
    # ---- R1d2: the FOLD (soft arc): the apex of the roll and its two ends, as x-graphs sampled from the solved cross-sections (the same sections the panels' rows are made of)
    xs_a = np.r_[np.linspace(X_FOLD0, X_TIP, 41), np.linspace(X_TIP, 2.378, 200)[1:]]
    pa, plo, phi_ = [], [], []
    for x in xs_a:
        if x <= X_FOLD0 + 1e-9:
            pa.append(u0); plo.append(u0); phi_.append(u0); continue
        ap, lo, hi = fold_apex(fold_section(float(x)))
        pa.append(ap); plo.append(lo); phi_.append(hi)
    CURVES['arc'] = Poly3(np.vstack([np.array(pa), E[None]]), 'arc')                    # the apex of the roll (centre of the turn): ends at the ear tip E
    CURVES['arc_lo'] = Poly3(np.array(plo), 'arc_lo')                                    # where the roll leaves the shoulder leg
    CURVES['arc_hi'] = Poly3(np.array(phi_), 'arc_hi')                                   # where the roll joins the inclined leg
    return CURVES



# ----------------------------------------------------------------------------- R1e2: the nose, a BOWED front edge in plan, corner triangle, chamfer facet
# p013 (top): the front edge across the car is ONE gentle arc (centre forward by NOSE_BOW), it ends at the nose corner N where the corner begins (L's plan: a convex quintic, see build_all); each
# corner carries the small corner-triangle flap.  Everything on the front is a plane or a developable cylinder:
#   H  the hood plane (z = .545 + .4248 (x + 2.39));   the hood front edge is the arc  x = xe(y)  on it (the light bar's top edge)
#   F  the FRONT FACE: the arc swept along the generator (rake, 0, -1) = a raked, sheared cylinder (developable); its end generator through N is the crease with the chamfer facet
#   P  the chamfer facet(s): ONE plane through that generator and the corner edge E (N -> l3_0 -> sill_0, the first row of the wall / wall_black); nose_corner_up is its triangle above the l3 level
#      (apex N), nose_corner_low its quadrilateral below
#   Q  the corner triangle (flap): tilted about L5, as in R1e
# The NAMED boundary curves a front-end agent attaches to:   NOSE['curves'][name] = right-half polyline (x, y, z) (mirror y for the left half)
NOSE_BOW = float(os.environ.get('NOSE_BOW', '0.110'))        # the front edge's bow: the centre is this much ahead of N (p013 .083 between the centre and the arc's end, p018 sees the centre further forward)
NOSE_RAKE = float(os.environ.get('NOSE_RAKE', '0.20'))       # front face: x grows by this per metre of height below the hood edge (p018: ~0.22, R1c: 0.167)
NOSE_D = float(os.environ.get('NOSE_D', '0.12'))              # the corner edge E ends (l3 level) this far aft of N
# 2026-10-24 (p014 both corners, p016 both corners; the four image slopes fit k = 0.21 / 0.22 / 0.26 / 0.26): the face's end generator (the crease front face | lower face C) leans OUTWARD going down by QF_FS_K m per m
# of drop: |y| 0.67 at N, 0.728 at the l3 level.  Its side view (x(z) on the raked line N + t (rake, 0, -1)) does not change (p018 matches it).  The face is the old sheared cylinder bent forward near the lower corners
# (fs_bend: a cubic in |y| from QF_FS_Y0 out) so that it reaches the leaning crease.  QF_FS_K = 0: the vertical generator of R1e.
QF_FS_K = float(os.environ.get('QF_FS_K', '0.23'))
QF_FS_Y0 = float(os.environ.get('QF_FS_Y0', '0.40'))
E_CAP_UP, E_CAP_LOW = 15, 14                                  # the wall's / wall_black's divisions per row (R1d): the corner edge E may not have more samples (aft of the arch the grids stay identical)
NOSE_K = 24                                                  # the corner edge's curves l3 / sill start at E: their first NOSE_K station intervals are squeezed (shell2.xlist K)
BAR_H, FACE_BLACK_H = 0.035, 0.115  # light bar height on the face; black face height below the hood edge (design doc L4: 0.10-0.12)
TRI_K, TRI_N = 33, 77               # FRONT round 3: the corner triangle = rows 0..TRI_K of the fender top's grid (row k pairs L5[k] with U[k]); TRI_N = I_A (stations N -> A_OUT).  TRI_K 33 = the p005 position of the
                                    # flap's rear corner C on L5 (k 33.4, x -2.10); the flap is the plane Q (through L5) up to that row, the fender top continues it (no wedge, no step)
L7_X, COWL_X = -1.81, -1.625        # hood seam (front-trunk lid's rear edge) and the cowl strip's rear edge (windscreen line)
NOSE = {}


def station_x(k):
    """x of master station k in the first segment [-2.39, -2.0] (shell2.make_stations)"""
    if k > 31:                                       # (FRONT round 3: TRI_K 33 needs the stations past the first segment: 0.0125 spacing, as shell2.XS)
        return -2.0 + 0.0125 * (k - 31)
    return float(np.linspace(-2.39, -2.0, int(round(0.39 / 0.0125)) + 1)[k])


def squeezed_x(x0, k, K=12):
    """x of sample k of shell2.xlist(0, ..., x0, K): the master stations squeezed so that the list starts at x0 (first K intervals)"""
    if k > K:
        return station_x(k)
    xa, xb = station_x(0), station_x(K)
    return float(x0 + (station_x(k) - xa) * (xb - x0) / (xb - xa))


# apillar: the SAMPLES of the hood edge L5 (the edge itself is the straight line N -> W).  The fender top is a ruled surface whose row k joins L5[k] to the crest sample U[k].  With L5 sampled uniformly the rulings
# slant aft by 0.17-0.19 m at the window end (L5 ends at x -1.625, the crest runs on to the pillar foot at x -1.43), and the face's section at constant x leans DOWN there.  Here the L5 partner of U[k] eases (over PAIR_BLEND
# rows from the flap seam, row TRI_K) to the point of L5 at the same x, so that the rulings are the x-sections; where L5 has ended at the cowl corner W the remaining crest samples fan out from a short smear of W (the last L5
# samples are PAIR_STEP apart: a cone, not a point, so that the normals stay continuous).
PAIR_MODE = os.environ.get('PAIR_MODE', 'cx')              # 'cx' (default) or 'uni' (the fender3 uniform sampling)
PAIR_BLEND = float(os.environ.get('PAIR_BLEND', '15'))
PAIR_STEP = float(os.environ.get('PAIR_STEP', '2.5')) * 1e-3
PAIR_SOFT = float(os.environ.get('PAIR_SOFT', '0.01'))
PAIR_LEAD = float(os.environ.get('PAIR_LEAD', '0.0'))
PAIR_SMOOTH = float(os.environ.get('PAIR_SMOOTH', '4'))   # rows: Gaussian smoothing of the L5 sample steps aft of the same-x blend (0 = off)


def l5_tau(n=TRI_N):
    """fractions along L5 (N -> W) of its n + 1 samples"""
    k = np.arange(n + 1, dtype=float)
    uni = k / n
    if PAIR_MODE == 'uni':
        return uni
    xu = np.array([squeezed_x(float(N[0]), int(i)) for i in range(n + 1)])
    t = np.clip((xu - N[0]) / (W[0] - N[0]) + PAIR_LEAD, 0.0, 1.0)
    w = np.clip((k - TRI_K) / PAIR_BLEND, 0.0, 1.0)
    w = w * w * (3 - 2 * w)
    base = uni * (1 - w) + t * w
    line = 1.0 - (n - k) * PAIR_STEP / float(np.linalg.norm(np.array(W, float) - np.array(N, float)))
    m = np.minimum(base, line)
    r = m - PAIR_SOFT * np.log(np.exp(-(base - m) / PAIR_SOFT) + np.exp(-(line - m) / PAIR_SOFT))
    r = r + (1.0 - r[-1]) * np.clip((k - TRI_K) / (n - TRI_K), 0.0, 1.0) ** 6          # (the soft minimum stays PAIR_SOFT ln 2 under 1 at the end: lift it there, over the last rows)
    r = np.where(k <= TRI_K, uni, np.minimum(r, 1.0))
    r[-1] = 1.0
    if PAIR_SMOOTH > 0:
        # q12 (review 2026-10-22, item 1): the soft minimum drops the sample step from 13 to 2.5 mm over ~4 rows (k 56 .. 60): the rulings' turning rate jumps there and the fender top shows a fold
        # line across it (row-to-row normal turn 1.6 deg against 0.3 around it).  The steps aft of the same-x blend are smoothed (Gaussian, PAIR_SMOOTH rows) with their sum kept: L5, W, the flap
        # (k <= TRI_K) and the end row do not move, only the samples between.
        k0 = int(TRI_K + PAIR_BLEND)
        d = np.diff(r)[k0:]
        pad = int(4 * PAIR_SMOOTH) + 1
        dp = np.r_[np.full(pad, d[0]), d, np.full(pad, d[-1])]
        g = np.exp(-0.5 * (np.arange(-pad, pad + 1) / PAIR_SMOOTH) ** 2)
        ds = np.convolve(dp, g / g.sum(), mode='same')[pad:-pad]
        ds *= d.sum() / ds.sum()
        r[k0 + 1:] = r[k0] + np.cumsum(ds)
        r[-1] = 1.0
    assert np.all(np.diff(r) > 0), 'l5_tau must be strictly increasing'
    return r


# 2026-10-24 (user: the hood and the fender planes beside it run down to the nose in a gentle arc, not as flat planes): the hood edge L5 and the hood's centre line are no longer straight but bow UP by
# QF_HOOD_SAG at their middle (a parabola 4 t (1 - t) over each line's own fraction t; the ends N / W and the front edge / cowl corner do not move).  The hood (Coons patch between them) and the fender top
# (straight rulings L5 -> U) take the arc over; the flap's part of L5 (t <= TRI_K / TRI_N = 0.43) is off its chord by 0.18 QF_HOOD_SAG.
QF_HOOD_SAG = float(os.environ.get('QF_HOOD_SAG', '0.012'))


def hood_sag(t):
    t = np.asarray(t, float)
    return QF_HOOD_SAG * 4.0 * t * (1.0 - t)


def l5_points(n=TRI_N):
    t = l5_tau(n)[:, None]
    P = np.array(N, float) + (np.array(W, float) - np.array(N, float)) * t
    P[:, 2] += hood_sag(t[:, 0])
    P[0], P[-1] = N, W
    return P


def legacy_hit(curve, x_guess):
    """x where `curve` meets the R1c face (the corner edge E of the locked panels; R1e)"""
    x = x_guess
    for _ in range(40):
        p = curve.at(x)
        x = float(face_x(p[1], p[2]))
    return x


def _unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


def hood_surface_z(cv, x, y):
    """height of the hood (the Coons patch of shell2.p_hood: bottom = centre line HC -> (W_x, 0, W_z), top = L5, left = the front edge bar_top, right = the cowl line) at plan point (x, y)"""
    tau = l5_tau(TRI_N)
    bottom = np.asarray([np.array(cv['bar_top'][0], float) + (np.array([W[0], 0.0, W[2]]) - np.array(cv['bar_top'][0], float)) * t + np.array([0.0, 0.0, float(hood_sag(t))]) for t in tau])
    top = l5_points(TRI_N)
    left = np.asarray(cv['bar_top'], float)
    right = np.array([[W[0], yy, W[2]] for yy in np.linspace(0, W[1], len(left))])
    n, m = len(bottom) - 1, len(left) - 1
    u = tau[None, :, None]                                                  # (the patch is the uniformly sampled one; the columns sit at L5's fractions, see shell2.p_hood)
    v = np.linspace(0, 1, m + 1)[:, None, None]
    c00, c10, c01, c11 = bottom[0], bottom[n], top[0], top[n]
    P = ((1 - v) * bottom[None] + v * top[None] + (1 - u) * left[:, None] + u * right[:, None] - ((1 - u) * (1 - v) * c00 + u * (1 - v) * c10 + (1 - u) * v * c01 + u * v * c11))
    q = np.array([x, y])
    best = None
    for j in range(m):
        for i in range(n):
            quad = P[j:j + 2, i:i + 2]
            for tri in ((quad[0, 0], quad[0, 1], quad[1, 1]), (quad[0, 0], quad[1, 1], quad[1, 0])):
                a, b, c = (np.asarray(t, float) for t in tri)
                M = np.array([[b[0] - a[0], c[0] - a[0]], [b[1] - a[1], c[1] - a[1]]])
                det = np.linalg.det(M)
                if abs(det) < 1e-14:
                    continue
                s_t = np.linalg.solve(M, q - a[:2])
                if s_t[0] >= -1e-9 and s_t[1] >= -1e-9 and s_t.sum() <= 1 + 1e-9:
                    return float(a[2] + s_t[0] * (b[2] - a[2]) + s_t[1] * (c[2] - a[2]))
    raise RuntimeError('hood_surface_z: (%.3f, %.3f) is not on the hood' % (x, y))


def build_nose():
    global HC
    Cv = CURVES
    N_ = np.array(N, float)
    zN = float(N_[2])
    xc = float(N_[0]) - NOSE_BOW
    shape = lambda e: 0.59 * e ** 2 + 0.41 * e ** 4                                  # the bow's shape: y^2 and y^4 (p013: .59 / .41)
    xe = lambda y: xc + NOSE_BOW * shape(np.asarray(y, float) / N_[1])               # the hood front edge in plan, x(y)
    ze = lambda y: zN + 0.0 * np.asarray(y, float)                                   # R1e2: the front edge is HORIZONTAL (the light bar is straight in the photos); the hood is the Coons surface between it, the centre line and L5
    yc = lambda z: N_[1] + QF_FS_K * (zN - np.asarray(z, float))                     # 2026-10-24: |y| of the leaning crease at height z (QF_FS_K)
    psi = lambda y: np.clip((np.abs(np.asarray(y, float)) - QF_FS_Y0) / (N_[1] - QF_FS_Y0), 0.0, None) ** 3
    cz = lambda z: np.where(np.asarray(z, float) < zN, (xe(yc(z)) - N_[0]) / psi(yc(z)), 0.0)     # the forward bend that brings the face to the crease's x at |y| = yc(z)
    Fxy = lambda y, z: xe(y) + NOSE_RAKE * (ze(y) - np.asarray(z, float)) - cz(z) * psi(y)      # the front face: sheared cylinder, bent forward near the lower corners
    rr = np.array([NOSE_RAKE, 0.0, -1.0])                                            # its generator (the side view of the crease)
    crz = lambda z: np.array([N_[0] + NOSE_RAKE * (zN - z), float(yc(z)), z])        # the crease point at height z
    # the chamfer facet: plane through the end generator N + t rr and the corner edge's point l3_0 (on the l3 curve, NOSE_D aft of N)
    _l3src = _CF_PRE.get('l3', Cv['l3']) if QF_CF_ON else Cv['l3']                  # c10b: the keys of the (now removed) chamfer come from the unmodified curves
    _slsrc = _CF_PRE.get('sill', Cv['sill']) if QF_CF_ON else Cv['sill']
    l3_0 = _l3src.at(N_[0] + NOSE_D)
    nP = _unit(np.cross(rr, l3_0 - N_))
    if nP[0] > 0:
        nP = -nP
    dP = float(nP @ N_)
    lo, hi = N_[0] - 0.02, N_[0] + 0.5                                               # sill_0: the sill curve's point on that plane
    f = lambda x: float(nP @ _slsrc.at(x)) - dP
    assert f(lo) * f(hi) < 0, ('the sill does not cross the chamfer facet plane', f(lo), f(hi))
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if f(lo) * f(mid) <= 0:
            hi = mid
        else:
            lo = mid
    sill_0 = _slsrc.at(0.5 * (lo + hi))
    z_bot = float(sill_0[2])
    R_l3 = crz(float(l3_0[2]))                                                       # the face's end generator (the crease) at the l3 level / at the sill level
    R_bot = crz(z_bot)
    if QF_CF_ON:                                                                     # c10b: sill starts at R_bot (plan and height bent, fading out within QF_CF_DS), l3 starts at R_l3 (see build_all)
        _xb = float(R_bot[0])
        _ya = float(_slsrc.fy(_xb))
        _za = float(_slsrc.fz(_xb))
        _ez = float(R_bot[2]) - _za
        _eys, _cfis = qf_cf_start(_slsrc.fy, _xb, float(R_bot[1]), QF_CF_XJS, 'sill')
        _gs = lambda x: 1.0 - sstep(_xb, QF_CF_XJS, x)
        _sd = _slsrc
        CURVES['sill'] = PlanMod(_sd.old, _sd.x0, lambda x: _sd.dy(x) + _eys(x), lambda x: _sd.dz(x) + _ez * _gs(x), 'sill')
        _CF_PRE['info_sill'] = _cfis
    n_up = min(E_CAP_UP, max(1, int(round(float(np.linalg.norm(N_ - l3_0)) / 0.020))))              # sample counts of the corner edge E (same rule as shell2.e_E_up / e_E_low: one per 0.020 m,
    n_low = min(E_CAP_LOW, max(1, int(round(float(np.linalg.norm(l3_0 - sill_0)) / 0.020))))          # capped at the division counts of the old wall / wall_black rows: their grids (aft of the arch) must not change)
    # ---- the corner triangle (flap): apex N, C on L5, B on the crest U; the plane Q contains the line L5 and B
    W_ = np.array(W, float)
    C_ = N_ + (W_ - N_) * (TRI_K / TRI_N) + np.array([0.0, 0.0, float(hood_sag(TRI_K / TRI_N))])     # (on the bowed L5)
    xsU = np.array([squeezed_x(N_[0], k) for k in range(TRI_K + 1)])
    B_ = Cv['U'].at(xsU[-1])
    nH = _unit(np.array([-HOOD_B, 0.0, 1.0]))
    t5 = _unit(W_ - N_)
    # FRONT round 3: Q is a plane THROUGH THE LINE L5 (N -> W) (it used to be a plane through N only, tilted about an axis that was not L5: it stood up to 18 mm above L5 at C, a ramp along
    # the flap's L5 edge).  Its tilt about L5 is the one that minimises the largest distance of the crest samples U[0..TRI_K] from Q (Q_dev).
    nH0 = _unit(nH - (nH @ t5) * t5)                                                 # the plane through L5 that is flat across the car (hood-like); Q is this plane tilted about L5 by th
    mm = _unit(np.cross(nH0, t5))
    Us = Cv['U'].at(xsU) - N_
    best = None
    for th in np.linspace(-0.3, 0.3, 6001):
        nn = math.cos(th) * nH0 + math.sin(th) * mm
        e = float(np.abs(Us @ nn).max())
        if best is None or e < best[0]:
            best = (e, th, nn)
    nQ = best[2] if best[2][2] > 0 else -best[2]
    pQ = (nQ, float(nQ @ N_))
    # ---- named curves (right half, from the centre line outwards / from the front backwards)
    lin = lambda p, q, n: np.asarray(p, float) + (np.asarray(q, float) - np.asarray(p, float)) * np.linspace(0, 1, n + 1)[:, None]
    ys = np.linspace(0.0, N_[1], 35)                                                 # 35 = shell2.M_HOOD + 1 samples across the face (uniform in y)
    cv = {}
    cv['bar_top'] = np.stack([xe(ys), ys, ze(ys)], 1)
    cv['bar_top'][-1] = N_                                                           # the hood front edge = the light bar's top edge, centre -> N
    zb = cv['bar_top'][:, 2] - BAR_H
    yb = ys * float(yc(zb[0])) / N_[1]                                               # (each edge across the face runs out to the leaning crease at its own height)
    cv['bar_bot'] = np.stack([Fxy(yb, zb), yb, zb], 1)                               # the bar's lower edge: BAR_H below the top edge along the generator (on the face)
    zbk = float(ze(0.0)) - FACE_BLACK_H
    yk = ys * float(yc(zbk)) / N_[1]
    cv['face_black_bot'] = np.stack([Fxy(yk, zbk), yk, np.full_like(ys, zbk)], 1)    # lower edge of the black face (constant height)
    yf = ys * float(yc(z_bot)) / N_[1]
    cv['F_bot'] = np.stack([Fxy(yf, z_bot), yf, np.full_like(ys, z_bot)], 1)
    cv['F_bot'][-1] = R_bot
    zc = np.linspace(z_bot, float(ze(0.0)), n_low + n_up + 1)
    cv['F_cen'] = np.stack([Fxy(0.0 * zc, zc), 0.0 * zc, zc], 1)
    cv['face_edge_up'] = lin(R_l3, N_, n_up)             # the face's end generator above the l3 level = crease front face | chamfer facet
    cv['face_edge_low'] = lin(R_bot, R_l3, n_low)        # ... below it
    cv['E_up'] = lin(N_, l3_0, n_up)                     # corner edge (the wall's first row, upper part)
    cv['E_low'] = lin(l3_0, sill_0, n_low)
    if QF_CF_ON:                                         # c10b: the corner edge IS the face's end generator
        cv['face_edge_up'] = lin(R_l3, N_, n_up)
        cv['face_edge_low'] = lin(R_bot, R_l3, n_low)
        cv['E_up'] = cv['face_edge_up'][::-1].copy()
        cv['E_low'] = cv['face_edge_low'][::-1].copy()
    cv['L6_top'] = np.tile(N_, (9, 1))                   # the chamfer facet's top edge has no length (it starts at N): nose_corner_up is a triangle
    cv['L6_poly'] = np.array([N_, l3_0, R_l3])           # corner points of the upper chamfer facet (a planar triangle)
    cv['tri'] = np.array([N_, C_, B_])                   # corner triangle N, C (on L5), B (on U)
    cv['tri_seam'] = lin(C_, B_, 18)                     # the flap's rear seam C -> B (a straight line)
    cv['L5'] = lin(N_, W_, TRI_N)
    cv['L5'][:, 2] += hood_sag(np.linspace(0.0, 1.0, TRI_N + 1))
    yl = lambda x: float(N_[1] + (W_[1] - N_[1]) * (x - N_[0]) / (W_[0] - N_[0]))
    # apillar: the seams lie on the hood AS BUILT (the Coons patch of shell2.p_hood between the centre line, L5, the front edge and the cowl line), no longer on the old flat plane hood_z (the cowl corner W is 30 mm lower than it)
    cv['hood_seam_L7'] = np.array([[L7_X, y, float(hood_surface_z(cv, L7_X, y))] for y in np.linspace(0, yl(L7_X), 14)])      # x = -1.81: the front-trunk lid's rear edge (across the hood, centre -> L5)
    cv['cowl_edge'] = np.array([[COWL_X, y, float(W[2])] for y in np.linspace(0, yl(COWL_X), 14)])                          # x = -1.625: cowl strip -> windscreen (the cowl line is a straight edge of the hood at the height of W)
    NOSE.clear()
    NOSE.update(dict(N=N_, l3_0=(R_l3 if QF_CF_ON else l3_0), sill_0=(R_bot if QF_CF_ON else sill_0), C1_top=N_.copy(), C1_l3=R_l3, C1_bot=R_bot, HC_top=cv['bar_top'][0], HC_bot=cv['F_bot'][0], xe=xe, ze=ze, Fxy=Fxy, rake=NOSE_RAKE, xc=xc,
                     P=(nP, dP), Q=pQ, Q_dev=best[0], Q_tilt_deg=math.degrees(best[1]), C=C_, B=B_, x_top=xc, z_top=float(ze(0.0)), z_bot=z_bot, curves=cv, n_up=n_up, n_low=n_low,
                     yc=yc, crz=crz))
    HC = tuple(float(v) for v in cv['bar_top'][0])
    return NOSE


build_all()
build_nose()

if __name__ == '__main__':
    for k, c in CURVES.items():
        r = getattr(c, 'resid', None)
        print(f'{k:10s} x[{c.x0:6.2f},{c.x1:5.2f}]', 'resid', None if r is None else tuple(round(v * 1000, 1) for v in r), 'mm', {a: (b[0], round(b[1], 2), round(b[2], 2)) for a, b in curvature_report(c).items()})
