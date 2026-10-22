"""
Wedge EV concept — Blender rebuild from the four-view reference sheet.

Run:  blender -b --python build_car.py -- <out_dir>
Writes <out_dir>/wedge_car.blend

Units: metres, 1:1.  Axes: X = length (front at -X), Y = width, Z = up, ground at Z = 0.
Overall: L 4.75  W 2.20  H 1.34  wheelbase 3.10  tyre Ø 0.80

The body is a quad control cage under a Subdivision Surface modifier. Cage rows follow the
character lines measured off the side / top / front views; feature lines are held by edge
creases; the wheel arches are modelled into the cage (radial rings around a true circle and a
turned-in flange, no boolean).

Surfacing (faceted, after the Roadster 2 photos): flat facets split by sharp creases; only the
fender over the front wheel, the haunch over the rear wheel and the ledge under the side glass
carry gentle curvature.
  * hood: one plane; the fender ridge stands above it and is one unbroken crease from the nose
    to the A-pillar: in side view a straight line (the lamp's outer edge, carried on past the
    lamp apex), one smooth bend over the front wheel, and a second straight line into the
    A-pillar foot;
  * nose side: two straight creases — the fender ridge above, the nose-corner crease below,
    which runs straight into the front arch — with one smooth convex band between them;
  * every character line is either straight or a fair C2 curve — a smoothed cubic B-spline
    fitted to the measured points — so there are no ripples or curvature jumps between them;
  * the body side follows one section rule: a top leg (lamp band / fender / ledge / C-pillar)
    and a slab leg meet at the shoulder line, a sharp crease from the front door to the tail;
  * the fender over the front wheel is one rounded volume, as on the car: inside the arch
    opening the section corner is lifted over the arch and hidden in a broad round that fades
    into the door shoulder, so over the wheel the arch is cut into the vertical side only;
  * the C-pillar ends in a crease across the body at the glass end, which slants back down the
    side to the tail lamp; behind it the tail band and the tail-corner chamfer are planes;
  * the wheel-arch patches are fitted to the surface the body would have without the arch, so
    the arch cuts the surface instead of denting it.
"""
import bpy, bmesh, math, os, sys
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = argv[0] if argv else os.path.dirname(os.path.abspath(__file__))
os.makedirs(OUT, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'


# ----------------------------------------------------------------- materials
def mat(name, base, metallic=0.0, rough=0.5, coat=0.0, emis=None, estr=0.0, spec=0.5):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = (*base, 1.0)
    b.inputs["Metallic"].default_value = metallic
    b.inputs["Roughness"].default_value = rough
    b.inputs["Specular IOR Level"].default_value = spec
    if coat:
        b.inputs["Coat Weight"].default_value = coat
        b.inputs["Coat Roughness"].default_value = 0.03
    if emis:
        b.inputs["Emission Color"].default_value = (*emis, 1.0)
        b.inputs["Emission Strength"].default_value = estr
    m.diffuse_color = (*base, 1.0)
    return m


M = {
    'paint':     mat('Paint_LiquidSilver', (0.70, 0.71, 0.73), 0.88, 0.30, coat=0.4),
    'glass':     mat('Glass_BronzeTint', (0.12, 0.068, 0.032), 0.0, 0.07, coat=0.3, spec=0.4),
    'black':     mat('Trim_SatinBlack', (0.010, 0.010, 0.011), 0.0, 0.5, spec=0.25),
    'well':      mat('WheelWell', (0.008, 0.008, 0.008), 0.0, 0.85),
    'tire':      mat('Tyre', (0.018, 0.018, 0.018), 0.0, 0.72),
    'rimblack':  mat('Rim_GlossBlack', (0.006, 0.006, 0.007), 0.0, 0.38, coat=0.1, spec=0.3),
    'rimdisc':   mat('Rim_Aero_Silver', (0.78, 0.79, 0.81), 0.55, 0.35),
    'copper':    mat('Rim_Copper', (0.86, 0.50, 0.26), 1.0, 0.28),
    'line':      mat('PanelGap', (0.025, 0.025, 0.028), 0.0, 0.6),
    'red':       mat('TailLamp_Red', (0.45, 0.02, 0.02), 0.0, 0.2, emis=(1.0, 0.04, 0.03), estr=2.5),
    'amber':     mat('SideMarker_Amber', (0.5, 0.06, 0.02), 0.0, 0.25, emis=(1.0, 0.18, 0.05), estr=0.8),
    'lamp':      mat('Headlamp_LED', (0.92, 0.93, 0.95), 0.0, 0.1, emis=(1, 1, 1), estr=2.0),
    'chrome':    mat('Badge_Chrome', (0.92, 0.92, 0.92), 1.0, 0.08),
    'darkmetal': mat('DarkMetal', (0.11, 0.11, 0.12), 0.8, 0.4),
}
MAT_PAINT, MAT_GLASS, MAT_BLACK, MAT_WELL = 0, 1, 2, 3


# ------------------------------------------------------------ interpolation
def lin(s, pts):
    return float(np.interp(s, [p[0] for p in pts], [p[1] for p in pts]))


def pchip(pts):
    xs = np.array([p[0] for p in pts], float)
    ys = np.array([p[1] for p in pts], float)
    h = np.diff(xs)
    d = np.diff(ys) / h
    n = len(xs)
    m = np.zeros(n)
    m[0], m[-1] = d[0], d[-1]
    for i in range(1, n - 1):
        if d[i - 1] * d[i] <= 0:
            m[i] = 0.0
        else:
            w1, w2 = 2 * h[i] + h[i - 1], h[i] + 2 * h[i - 1]
            m[i] = (w1 + w2) / (w1 / d[i - 1] + w2 / d[i])

    def f(x):
        x = min(max(x, xs[0]), xs[-1])
        i = int(np.clip(np.searchsorted(xs, x) - 1, 0, n - 2))
        t = (x - xs[i]) / h[i]
        return ((2 * t**3 - 3 * t**2 + 1) * ys[i] + (t**3 - 2 * t**2 + t) * h[i] * m[i]
                + (-2 * t**3 + 3 * t**2) * ys[i + 1] + (t**3 - t**2) * h[i] * m[i + 1])
    return f


def smoothstep(e0, e1, x):
    t = min(max((x - e0) / (e1 - e0), 0.0), 1.0)
    return t * t * (3 - 2 * t)


def sstep5(e0, e1, x):
    """C2 smootherstep: no curvature jump where a blend starts or ends."""
    t = min(max((x - e0) / (e1 - e0), 0.0), 1.0)
    return t * t * t * (t * (6.0 * t - 15.0) + 10.0)


def ease5(s, s0, y0, m0, s1, y1):
    """Quintic run-out from (s0, y0) with slope m0 to a flat y1 at s1, no curvature at either
    end. Monotone while m0 * (s1 - s0) <= 2.5 * (y1 - y0)."""
    if s <= s0:
        return y0 + m0 * (s - s0)
    if s >= s1:
        return y1
    L = s1 - s0
    u = (s - s0) / L
    h0 = 1 - 10 * u**3 + 15 * u**4 - 6 * u**5
    h1 = u - 6 * u**3 + 8 * u**4 - 3 * u**5
    h3 = 10 * u**3 - 15 * u**4 + 6 * u**5
    return y0 * h0 + y1 * h3 + m0 * L * h1


class Fair:
    """Fair C2 curve y(x): a cubic B-spline fitted to measured points by least squares with a
    curvature penalty (P-spline). The end points are held, and the end slopes when given.
    Continues as straight lines outside the measured range."""

    def __init__(self, pts, n=8, lam=1e-4, d0=None, d1=None):
        xs = np.array([p[0] for p in pts], float)
        ys = np.array([p[1] for p in pts], float)
        self.a, self.b, self.n = float(xs[0]), float(xs[-1]), n
        self.t = np.concatenate([[self.a] * 3, np.linspace(self.a, self.b, n - 2), [self.b] * 3])
        B = np.array([self._basis(x) for x in xs])
        w = np.ones(len(xs))
        w[0] = w[-1] = 1e6
        A = B.T @ (w[:, None] * B)
        r = B.T @ (w * ys)
        for x, d in ((self.a, d0), (self.b, d1)):
            if d is not None:
                g = self._dbasis(x)
                A += 1e6 * np.outer(g, g)
                r += 1e6 * g * d
        D = np.diff(np.eye(n), 2, axis=0)
        h = (self.b - self.a) / (n - 3)
        A += lam / h ** 3 * (D.T @ D)
        self.c = np.linalg.solve(A, r)
        self.ya, self.yb = float(self._basis(self.a) @ self.c), float(self._basis(self.b) @ self.c)
        self.da, self.db = float(self._dbasis(self.a) @ self.c), float(self._dbasis(self.b) @ self.c)
        self.res = float(np.max(np.abs(B @ self.c - ys)))

    def _basis(self, x):
        t, n = self.t, self.n
        x = min(max(x, self.a), self.b)
        i = min(int(np.searchsorted(t, x, side='right')) - 1, n - 1)
        N = np.zeros(len(t) - 1)
        N[i] = 1.0
        for d in range(1, 4):
            M_ = np.zeros(len(t) - 1 - d)
            for j in range(max(0, i - d), min(i, len(M_) - 1) + 1):
                v = 0.0
                if t[j + d] > t[j]:
                    v += (x - t[j]) / (t[j + d] - t[j]) * N[j]
                if t[j + d + 1] > t[j + 1]:
                    v += (t[j + d + 1] - x) / (t[j + d + 1] - t[j + 1]) * N[j + 1]
                M_[j] = v
            N = M_
        return N

    def _dbasis(self, x):
        e = 1e-5 * (self.b - self.a)
        x0, x1 = max(self.a, x - e), min(self.b, x + e)
        return (self._basis(x1) - self._basis(x0)) / (x1 - x0)

    def __call__(self, x):
        if x < self.a:
            return self.ya + self.da * (x - self.a)
        if x > self.b:
            return self.yb + self.db * (x - self.b)
        return float(self._basis(x) @ self.c)

    def d(self, x):
        if x <= self.a:
            return self.da
        if x >= self.b:
            return self.db
        return float(self._dbasis(x) @ self.c)


# ------------------------------------------------------- key stations (X)
XF, XR = -2.375, 2.375        # nose / tail
X_T = -2.05                   # head-lamp triangle apex T / hood point B
X_FF = -1.88                  # front-fender leading face reaches full width
X_NC = -1.96                  # nose-corner facets end (front arch, front cage column)
X_WS = -1.55                  # windscreen base (centre)
X_A0 = -1.40                  # A-pillar foot: rail + side glass start
X_TIP = 1.197                 # side-glass rear tip
X_GE = 2.03                   # glass canopy ends; crease across the C-pillar
X_C6 = 2.156                  # ... slanting back down the side to the silver lower edge here
WHEEL_X = (-1.487, 1.61)
WHEEL_Z, TYRE_R, ARCH_R = 0.39, 0.39, 0.4225   # ARCH_R = arch radius on the body flank

A0P = (0.93, 0.912)           # (Y, Z) side-glass front tip: ridge, rail and belt meet here
TIPP = (0.695, 1.19)          # (Y, Z) side-glass rear tip: rail and belt meet here (top view: Y 0.70)
H0 = (XF, 0.66, 0.50)         # hood front corner
P4 = (X_WS, 0.53, 0.84)       # windscreen-base corner, rear end of the hood edge
SH_W, LO_W = 1.095, 1.07      # shoulder / silver lower edge half-widths along the doors


def HOOD_Y(s):
    """Straight hood edge H0 -> P4 (plan)."""
    return H0[1] + (s - XF) / (X_WS - XF) * (P4[1] - H0[1])


def hood_z(s):
    """Flat wedge hood."""
    return H0[2] + (s - XF) / (X_WS - XF) * (P4[2] - H0[2])


# fender-top facet: one plane through the straight hood edge and the A-pillar foot
_HB = Vector((X_T, HOOD_Y(X_T), hood_z(X_T)))
_FN = (Vector((X_A0, A0P[0], A0P[1])) - _HB).cross(Vector(P4) - _HB)


def fender_z(x, y):
    return _HB.z - (_FN.x * (x - _HB.x) + _FN.y * (y - _HB.y)) / _FN.z


# roof / windscreen centre-line (side-view silhouette); at the A-pillar foot the glass edge
# sits on the fender plane
ZC = [(X_WS, 0.84), (X_A0, fender_z(X_A0, 0.90)), (-1.24, 0.969), (-0.931, 1.086), (-0.623, 1.191),
      (-0.315, 1.283), (-0.006, 1.333), (0.302, 1.339), (0.611, 1.333), (0.919, 1.302),
      (1.228, 1.265), (1.536, 1.209), (1.845, 1.147), (X_GE, 1.105)]
zc_canopy = Fair(ZC, n=11, lam=2e-4)


def Zc(s):
    if s <= X_WS:
        return hood_z(s)
    if s <= X_GE:
        return zc_canopy(s)
    return 1.105 + (s - X_GE) / (XR - X_GE) * (1.03 - 1.105)        # rear deck


def NOSE(t):
    """Point on the front-face side edge: t=0 hood corner H0 ... t=1 silver lower edge."""
    return (XF + 0.02 * t, 0.66 + 0.02 * t, 0.50 - 0.17 * t)


def nose_w(s):
    return 1.0 - smoothstep(XF, X_T, s)


def nose_x(s, t):
    return s + nose_w(s) * (NOSE(t)[0] - XF)


T_DZ = 0.04                   # the fender top rises outward: the lamp apex sits above the plane
T_PT = (X_T, 0.78, fender_z(X_T, 0.78) + T_DZ)     # head-lamp triangle apex

# fender ridge T -> A-pillar foot (side view): the lamp edge runs on straight past the lamp
# apex, bends smoothly over the front wheel and runs straight again into the A-pillar foot:
# two straight lines and one curvature-continuous bend between them
_LAMP_SLOPE = (T_PT[2] - NOSE(0.03)[2]) / (X_T - XF)
RIDGE_S2, RIDGE_H = 0.20, 0.13        # rear slope, half-length of the bend
_RIDGE_XC = X_A0 - (A0P[1] - T_PT[2] - _LAMP_SLOPE * (X_A0 - X_T)) / (RIDGE_S2 - _LAMP_SLOPE)


def RIDGE_Z(s):
    u = min(max((s - _RIDGE_XC + RIDGE_H) / (2 * RIDGE_H), 0.0), 1.0)
    bend = 2 * RIDGE_H * (u ** 6 - 3 * u ** 5 + 2.5 * u ** 4) + max(s - _RIDGE_XC - RIDGE_H, 0.0)
    return T_PT[2] + _LAMP_SLOPE * (s - X_T) + (RIDGE_S2 - _LAMP_SLOPE) * bend


def xstretch(s, x0, x1):
    """Lower rows start / end a little inboard of the nose and tail stations (receding faces)."""
    if s < -2.20:
        return x0 + (s - XF) * (-2.20 - x0) / (-2.20 - XF)
    if s > 2.20:
        return 2.20 + (s - 2.20) * (x1 - 2.20) / (XR - 2.20)
    return s


CANOPY_Y = Fair([(X_A0, 0.90), (-0.299, 0.705), (0.70, 0.62), (1.398, 0.573), (2.068, 0.35)], n=7, lam=1e-4)
RAIL_Z = Fair([(X_A0, A0P[1]), (-0.931, 1.045), (-0.475, 1.19), (-0.068, 1.277), (0.611, 1.298),
               (0.993, 1.255), (X_TIP, TIPP[1])], n=8, lam=1e-4)
BELT_Y = Fair([(X_A0, A0P[0]), (-0.765, 0.97), (-0.068, 0.955), (0.457, 0.93), (0.913, 0.89),
               (1.074, 0.82), (X_TIP, TIPP[0])], n=9, lam=2e-5)
BELT_Z = Fair([(X_A0, A0P[1]), (-0.765, 0.888), (-0.068, 0.944), (0.518, 1.012), (0.913, 1.055),
               (1.074, 1.104), (X_TIP, TIPP[1])], n=9, lam=2e-5)
LO_Z = Fair([(XF, 0.33), (X_T, 0.32), (-1.95, 0.30), (-1.40, 0.302), (-1.0, 0.306), (-0.765, 0.31), (0.08, 0.333), (0.30, 0.352),
             (1.20, 0.413), (2.03, 0.66), (XR, 0.84)], n=11, lam=1e-4)
RK_Y = pchip([(-2.34, 0.74), (X_T, 0.82), (X_FF, 0.925), (-1.6, 0.985), (1.9, 0.99), (2.05, 0.95), (2.29, 0.85)])
RK_Z = pchip([(-2.34, 0.24), (-1.95, 0.19), (-1.6, 0.12), (1.9, 0.12), (2.05, 0.22), (2.29, 0.22)])

# shoulder line. Ahead of the front arch it is the nose-corner crease: a straight line that runs
# into the arch. From there it is one fair curve that rises ever more gently to the tail
# (over the front wheel the section corner is lifted above it, see fender_lift).
SH_NOSE_T = 0.06              # shoulder leaves the front-face edge just under the hood corner
_SZ0 = NOSE(SH_NOSE_T)[2]
_SZ_SLOPE = (0.59 - _SZ0) / (X_T - XF)


def sh_z_nose(s):
    return _SZ0 + (s - XF) * _SZ_SLOPE


X_SB = -1.82                  # the nose-corner crease runs straight until it meets the front arch
SH_Z_FAIR = Fair([(X_SB, sh_z_nose(X_SB)), (-0.907, 0.788), (-0.44, 0.834), (0.30, 0.907),
                  (0.92, 0.968), (1.54, 1.012), (2.20, 1.028), (XR, 1.03)], n=10, lam=1e-4, d0=_SZ_SLOPE)


def SH_Z(s):
    return sh_z_nose(s) if s <= X_SB else SH_Z_FAIR(s)


# Front fender. Ahead of the arch the nose side is two straight creases (fender ridge, nose
# corner) with a smooth convex band between them; the nose-corner crease runs into the arch.
# Over the wheel the fender is one rounded volume: inside the arch opening the section corner
# is lifted over the arch and hidden in a broad round, which closes at the front door, where
# the crisp door shoulder starts.
X_FD = -0.995                 # front door: rear cage column of the front arch
FENDER_RA, FENDER_RB = 0.14, 0.06        # full round: metres along the top leg / down the slab


def fender_lift(s):
    return 0.15 * sstep5(-1.80, -1.45, s) * (1.0 - sstep5(-1.50, -1.05, s))


def fender_round(s):
    """How far the shoulder round is open, 0..1."""
    return sstep5(-1.80, -1.62, s) * (1.0 - sstep5(X_FD - 0.025, -0.66, s))


def SH_ZL(s):
    """Height of the section corner: the shoulder line plus the fender lift."""
    return SH_Z(s) + fender_lift(s)


# nose-corner side facet ahead of the front arch: one plane through the front-face edge and the
# sill point where it meets the arch column
_NA, _NB = Vector(NOSE(SH_NOSE_T)), Vector(NOSE(1.0))
_NQ = Vector((X_NC, 0.97, 0.30))
_NN = (_NB - _NA).cross(_NQ - _NA)


def nose_plane_y(x, z):
    return _NA.y - (_NN.x * (x - _NA.x) + _NN.z * (z - _NA.z)) / _NN.y


def _runout(zfn, width):
    """Plan line leaving the nose-corner plane at X_NC with matching slope, running out to a
    constant half-width (quintic, monotone)."""
    e = 1e-4
    y0 = nose_plane_y(X_NC, zfn(X_NC))
    m0 = (y0 - nose_plane_y(X_NC - e, zfn(X_NC - e))) / e
    s1 = X_NC + 2.4 * (width - y0) / m0
    return y0, m0, s1


_SHR = _runout(SH_ZL, SH_W)
# the silver lower edge turns with the shoulder, so the side facet between them doesn't twist:
# it keeps the shoulder's run-out plus an offset easing from its nose-plane value to the tuck
_LO0 = _runout(LO_Z, LO_W)
_DLR = (_LO0[0] - _SHR[0], _LO0[1] - _SHR[1], LO_W - SH_W)


def lo_plan(s):
    return (ease5(s, X_NC, _SHR[0], _SHR[1], _SHR[2], SH_W)
            + ease5(s, X_NC, _DLR[0], _DLR[1], _SHR[2], _DLR[2]))


def C_pt(s):
    """Shoulder line: the sharp corner between the top leg and the slab leg of the section."""
    x, z = nose_x(s, SH_NOSE_T), SH_ZL(s)
    if s <= X_NC:
        return Vector((x, nose_plane_y(x, z), z))
    if s <= X_GE:
        return Vector((x, ease5(s, X_NC, _SHR[0], _SHR[1], _SHR[2], SH_W), z))
    v = (s - X_GE) / (XR - X_GE)                  # tail band edge, chamfered inward
    return Vector((s, SH_W + v * (0.88 - SH_W), SH_Z(X_GE) + v * (SH_Z(XR) - SH_Z(X_GE))))


def L6_x(x):
    """Silver lower edge as a function of x (ahead of the tail-corner crease)."""
    xx = nose_x(x, 1.0) if x < X_T else x
    z = LO_Z(x)
    if x <= X_NC:
        return (xx, nose_plane_y(xx, z), z)
    return (xx, lo_plan(x), z)


# tail-corner chamfer: one plane through the slanted crease (shoulder at the glass end ->
# silver lower edge at X_C6) and the tail corner of the shoulder
_CA = Vector((X_GE, SH_W, SH_Z(X_GE)))
_CB = Vector((X_C6, LO_W, LO_Z(X_C6)))
_CC = Vector((XR, 0.88, SH_Z(XR)))
_CN = (_CB - _CA).cross(_CC - _CA)
Z6_TAIL = LO_Z(XR)


def chamfer_y(x, z):
    return _CA.y - (_CN.x * (x - _CA.x) + _CN.z * (z - _CA.z)) / _CN.y


def L6_tail(x):
    """Silver lower edge on the chamfer: straight from the crease foot to the tail."""
    v = (x - X_C6) / (XR - X_C6)
    z = _CB.z + v * (Z6_TAIL - _CB.z)
    return (x, chamfer_y(x, z), z)


def L6_any(x):
    return L6_x(x) if x <= X_C6 else L6_tail(x)


def L6b_any(x):
    p = L6_any(x)
    return (p[0], p[1] - 0.035, p[2] - 0.012)


def L7_any(x):
    return (x, RK_Y(x), RK_Z(x))


# ---------------------------------------------------------- character lines
def L0(s):  # centre line
    return (s, 0.0, Zc(s))


def L1(s):  # hood edge -> windscreen diagonal -> canopy glass edge -> deck
    if s <= X_WS:
        return (s, HOOD_Y(s), Zc(s))
    if s <= X_A0:
        t = (s - X_WS) / (X_A0 - X_WS)
        return (s, 0.53 + t * (0.90 - 0.53), 0.84 + t * (Zc(X_A0) - 0.84))
    # canopy crown: the glass edge sits below the centre line, fading out toward the glass end
    drop = 0.022 * sstep5(X_A0, -0.80, s) * (1.0 - sstep5(0.90, X_GE, s))
    if s <= X_GE:
        return (s, CANOPY_Y(s), Zc(s) - drop)
    t = (s - X_GE) / (XR - X_GE)
    return (s, CANOPY_Y(X_GE) + t * 0.04, Zc(X_GE) * (1 - t) + 1.03 * t)


RAIL_OFF = Fair([(X_A0, A0P[0] - 0.90), (0.70, 0.04), (X_TIP, TIPP[0] - CANOPY_Y(X_TIP))], n=5, lam=1e-3)


def L2(s):  # lamp-triangle outer edge -> fender ridge -> roof rail outer edge (s <= X_TIP)
    if s <= X_T:   # straight lamp-triangle edge
        n = NOSE(0.03)
        u = (s - XF) / (X_T - XF)
        return tuple(n[k] + u * (T_PT[k] - n[k]) for k in range(3))
    if s <= X_A0:  # fender ridge T -> A-pillar foot: straight in plan, arched in elevation
        y = lin(s, [(X_T, T_PT[1]), (X_A0, A0P[0])])
        return (s, y, RIDGE_Z(s))
    return (s, L1(s)[1] + RAIL_OFF(s), RAIL_Z(s))


def L3(s):  # belt line (side-glass bottom), X_A0 .. X_TIP
    return (s, BELT_Y(s), BELT_Z(s))


# ------------------------------------------------------------ side section
def _outward(c, mid):
    n = Vector((0.0, -c.z, c.y))
    if n.length < 1e-9:
        return Vector((0.0, 0.0, 0.0))
    n.normalize()
    if n.dot(Vector((0.0, mid.y, mid.z - 0.55))) < 0:
        n = -n
    return n


def _parab(P, Q, k):
    """Leg P -> Q bulging outward by k * |PQ| at its middle: point and tangent at t."""
    c = Q - P
    n = _outward(c, (P + Q) * 0.5)
    L = c.length
    return (lambda t: P + c * t + n * (4 * k * t * (1 - t) * L),
            lambda t: c + n * (4 * k * (1 - 2 * t) * L))


def _tangent_meet(A, TA, B, TB, fb):
    w0 = A - B
    a, b, c = TA.dot(TA), TA.dot(TB), TB.dot(TB)
    d, e = TA.dot(w0), TB.dot(w0)
    den = a * c - b * b
    if abs(den) < 1e-12:
        return fb
    sa, sb = (b * e - c * d) / den, (a * e - b * d) / den
    return ((A + TA * sa) + (B + TB * sb)) * 0.5


class SideCurve:
    """Body-side section P0 -> C -> P6: a top leg and a slab leg (crowns k1, k2) meeting at the
    shoulder C. The corner is sharp, or rounded by a quadratic Bezier that starts r1 (fraction
    of the top leg) before C and ends r2 metres down the slab. u4 = arc length to the corner
    (its middle when rounded), U = total."""

    def __init__(self, P0, C, P6, k1, k2, r1, r2):
        f1, d1 = _parab(P0, C, k1)
        f2, d2 = _parab(C, P6, k2)
        ta = 1.0 - min(max(r1, 0.0), 0.97)
        tb = min(max(r2, 0.0) / max((P6 - C).length, 1e-6), 0.9)
        pts = [f1(t) for t in np.linspace(0.0, ta, 60)]
        if ta < 1.0 - 1e-6 or tb > 1e-6:
            A, B = f1(ta), f2(tb)
            K = _tangent_meet(A, d1(ta), B, d2(tb), C)
            pts += [A * (1 - u) ** 2 + K * (2 * u * (1 - u)) + B * (u * u) for u in np.linspace(0, 1, 61)][1:]
            mid = 59 + 30
        else:
            mid = 59
        pts += [f2(t) for t in np.linspace(tb, 1.0, 60)][1:]
        acc = [0.0]
        for a, b in zip(pts[:-1], pts[1:]):
            acc.append(acc[-1] + (b - a).length)
        self.pts, self.acc = pts, np.array(acc)
        self.u4, self.U = float(self.acc[mid]), float(self.acc[-1])

    def at(self, u):
        u = min(max(u, 0.0), self.U)
        i = int(np.clip(np.searchsorted(self.acc, u) - 1, 0, len(self.pts) - 2))
        seg = self.acc[i + 1] - self.acc[i]
        t = 0.0 if seg < 1e-12 else (u - self.acc[i]) / seg
        return self.pts[i].lerp(self.pts[i + 1], t)

    def project(self, p):
        """Arc length of the polyline point nearest to p."""
        d = [(q - p).length for q in self.pts]
        return float(self.acc[int(np.argmin(d))])


F2_, F3_ = 0.25, 0.5          # C-pillar rows L2 / L3: fractions of the glass-edge -> shoulder leg


CROWN = 0.012


CROWN_NOSE = 0.08


def crown_top(s):
    """Nose side: the band between the two straight lines (fender ridge above, nose-corner crease
    below) is one smooth convex surface. Further back a trace of crown on the ledge, C-pillar and
    tail band so they read convex; it stays constant from the front door back (a crown that
    fades along the car dips)."""
    return CROWN_NOSE * (1.0 - sstep5(-1.75, -1.45, s)) + CROWN * sstep5(-1.60, -0.90, s)


def crown_slab(s):
    """Haunch over the rear wheel; the slab is flat elsewhere."""
    return 0.035 * sstep5(0.75, 1.30, s) * (1.0 - sstep5(1.62, 1.98, s))


def t3_frac(s):
    """Fender mid row L3 (ahead of the A-pillar foot) as a fraction of the top leg."""
    return 0.33 * (1.0 - sstep5(-1.75, X_A0, s))


def side_curve(s, P0):
    C = C_pt(s)
    a = fender_round(s)
    r1 = min(FENDER_RA * a / max((C - P0).length, 1e-6), 0.85)
    return SideCurve(P0, C, Vector(L6_x(s)), crown_top(s), crown_slab(s), r1, FENDER_RB * a)


# glass-tip hand-over: behind the side-glass tip the C-pillar rows L2 / L3 leave the tip point
_cv_tip = side_curve(X_TIP + 1e-6, Vector(L1(X_TIP)))
PHI_TIP = _cv_tip.project(Vector((X_TIP, TIPP[0], TIPP[1]))) / _cv_tip.u4
_TIP_CORR = Vector((X_TIP, TIPP[0], TIPP[1])) - _cv_tip.at(PHI_TIP * _cv_tip.u4)
_TIP_CORR.x = 0.0

# ------------------------------------------------------------- cage rows
ROWS = ['L0', 'C1', 'C2', 'L1', 'L2', 'L3', 'C34', 'L4', 'C45', 'L5', 'C56', 'L6', 'L6b', 'L7',
        'F1', 'F2', 'L8']
R = {n: k for k, n in enumerate(ROWS)}
_SEC = {}


def section(s):
    key = round(s, 9)
    if key in _SEC:
        return _SEC[key]
    P = {'L0': Vector(L0(s)), 'L1': Vector(L1(s))}
    a, b = P['L0'], P['L1']
    for name, t in (('C1', 1 / 3), ('C2', 2 / 3)):          # roof / hood crown: parabolic fall-off
        P[name] = Vector((a.x + (b.x - a.x) * t, b.y * t, a.z - (a.z - b.z) * t * t))
    if s >= X_GE - 1e-9:
        _tail_section(s, P)
    else:
        if s <= X_A0:
            P0 = Vector(L2(s))
        elif s <= X_TIP:
            P0 = Vector(L3(s))
        else:
            P0 = P['L1']
        cv = side_curve(s, P0)
        u4, U = cv.u4, cv.U
        if s <= X_A0:
            P['L2'] = P0
            u3 = t3_frac(s) * u4
            P['L3'] = cv.at(u3)
        elif s <= X_TIP:
            P['L2'] = Vector(L2(s))
            P['L3'] = P0
            u3 = 0.0
        else:
            w = sstep5(X_TIP, X_TIP + 0.7, s)
            corr = _TIP_CORR * (1.0 - w)
            P['L2'] = cv.at((PHI_TIP + (F2_ - PHI_TIP) * w) * u4) + corr
            u3 = (PHI_TIP + (F3_ - PHI_TIP) * w) * u4
            P['L3'] = cv.at(u3) + corr
        P['C34'] = cv.at(0.5 * (u3 + u4))
        P['L4'] = cv.at(u4)
        for name, f in (('C45', 0.25), ('L5', 0.5), ('C56', 0.75)):
            P[name] = cv.at(u4 + (U - u4) * f)
        P['L6'] = Vector(L6_x(s))
        P['L6b'] = P['L6'] + Vector((0.0, -0.035, -0.012))
        x7 = xstretch(s, -2.34, 2.29)
        P['L7'] = Vector(L7_any(x7))
    x7, _, z7 = P['L7']
    P['F1'] = Vector((x7, 0.68, z7))
    P['F2'] = Vector((x7, 0.34, z7))
    P['L8'] = Vector((x7, 0.0, z7))
    _SEC[key] = P
    return P


def _tail_section(s, P):
    """Behind the glass end: flat tail band (L1..L4) and the tail-corner chamfer plane (L4..L6),
    the latter starting on the slanted crease X_GE/shoulder -> X_C6/lower edge."""
    v = (s - X_GE) / (XR - X_GE)
    L4v = C_pt(s)
    P['L4'] = L4v
    L1v = P['L1']
    f1, _ = _parab(L1v, L4v, CROWN)
    P['L2'] = f1(F2_)
    P['L3'] = f1(F3_)
    P['C34'] = f1(0.5 * (1.0 + F3_))
    for name, f in (('C45', 0.25), ('L5', 0.5), ('C56', 0.75), ('L6', 1.0)):
        col = _CA.lerp(_CB, f)
        zt = SH_Z(XR) + f * (Z6_TAIL - SH_Z(XR))
        P[name] = col.lerp(Vector((XR, chamfer_y(XR, zt), zt)), v)
    L6 = P['L6']
    P['L6b'] = Vector((L6.x, L6.y - 0.035, L6.z - 0.012))
    x7 = X_C6 + v * (2.29 - X_C6)
    P['L7'] = Vector(L7_any(x7))


# rows the wheel-arch patches follow into the arch, as functions of x
LINE_FN = {'L4': lambda x: tuple(C_pt(x)), 'L6': L6_any, 'L6b': L6b_any, 'L7': L7_any}

ARCH_COLS = ((X_NC, X_FD), (1.12, X_GE))        # cage columns either side of each arch
FEATURE_X = [XF, X_T, X_NC, X_WS, X_A0, ARCH_COLS[0][1], ARCH_COLS[1][0], X_TIP, X_GE, XR]
STATIONS = []
for _a, _b in zip(FEATURE_X[:-1], FEATURE_X[1:]):
    _n = 4 if _a == X_GE else max(1, int(round((_b - _a) / 0.10)))
    STATIONS += [_a + (_b - _a) * k / _n for k in range(_n)]
STATIONS.append(XR)
def front_arch_top(s):
    """The front arch patch reaches up to the fender ridge, then (behind the glass tip) the belt."""
    return 'L2' if s < X_A0 else 'L3'


ARCHES = [  # (wheel x, first station, last station, top row(s), rows followed into the arch)
    (WHEEL_X[0], ARCH_COLS[0][0], ARCH_COLS[0][1], front_arch_top, {'front': ('L4',)}),
    (WHEEL_X[1], ARCH_COLS[1][0], ARCH_COLS[1][1], 'L4', {}),
]


# Hard edges come in two kinds. Bevelled (a ~4 mm round after subdivision) is used only on edge
# chains that close on themselves or end where other bevelled edges meet — a bevel that stops
# mid-surface leaves a spike. Every other hard edge is a full crease with split normals.
HARD = 1.0          # bevel weight
SHARP = -1.0        # full crease + sharp shading


def row_edge(j, xm, full=False):
    """(bevel weight, crease) for the cage edge of row j between two stations."""
    n = ROWS[j]
    if n == 'L1' and xm < X_T:
        return HARD, 0.0       # head-lamp triangle inner edge
    if n == 'L2' and xm < X_T:
        return SHARP, 0.0      # lamp outer edge: one crease with the fender ridge (no dart at T)
    if n == 'L1':
        return (SHARP, 0.0) if xm < X_GE else (0.0, 0.0)   # hood edge, windscreen base, canopy edge
    if n == 'L2' and xm < X_TIP:
        return SHARP, 0.0      # fender ridge, side-glass top
    if n == 'L3' and X_A0 < xm < X_TIP:
        return SHARP, 0.0      # side-glass bottom (belt)
    if n == 'L6':
        return HARD, 0.0       # silver / black edge
    if n in ('L6b', 'L7'):
        return SHARP, 0.0      # step into the black rocker, rocker edge (too close to L6 to bevel)
    if n == 'L4':              # nose-corner crease, shoulder crease, tail-band edge ...
        a = fender_round(xm)
        if a <= 0.0:
            return SHARP, 0.0
        return 0.0, max(0.0, 1.0 - a / 0.5) ** 2     # ... softening into the front-fender round
    return 0.0, 0.0


def strip_material(j, xm):
    n = ROWS[j]
    if j < R['L1'] and X_WS < xm < X_GE:
        return MAT_GLASS
    if n == 'L2' and X_A0 < xm < X_TIP:
        return MAT_GLASS
    if j >= R['L6']:
        return MAT_BLACK
    return MAT_PAINT


# ------------------------------------------------------------- body cage
def add_body_modifiers(ob):
    bev = ob.modifiers.new("EdgeRadius", 'BEVEL')     # support loops along the hard edges
    bev.limit_method = 'WEIGHT'
    bev.width = 0.004
    bev.segments = 2
    bev.use_clamp_overlap = True
    sub = ob.modifiers.new("Subdivision", 'SUBSURF')
    sub.levels = 3
    sub.render_levels = 3
    sub.use_creases = True
    sub.boundary_smooth = 'PRESERVE_CORNERS'


def temp_object(name, bm):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    ob = bpy.data.objects.new(name, me)
    scene.collection.objects.link(ob)
    add_body_modifiers(ob)
    return ob


def drop_object(ob):
    me = ob.data
    bpy.data.objects.remove(ob)
    bpy.data.meshes.remove(me)


def build_half(holes, ref=None):
    """Right half of the body cage as a bmesh. holes=False: the uncut reference body."""
    bm = bmesh.new()
    CL = bm.edges.layers.float.new("crease_edge")
    BL = bm.edges.layers.float.new("bevel_weight_edge")
    VL = bm.verts.layers.float.new("crease_vert")
    st = STATIONS
    ns, nr = len(st), len(ROWS)
    idx = {s: i for i, s in enumerate(st)}
    secs = [section(s) for s in st]

    missing = set()
    arch_ix = []
    if holes:
        for wx, sa, sb, top, follow in ARCHES:
            ia, ib = idx[sa], idx[sb]
            jt = [R[top(s) if callable(top) else top] for s in st]
            arch_ix.append((wx, ia, ib, jt, follow))
            for i in range(ia + 1, ib):
                for j in range(jt[i] + 1, R['L7'] + 1):
                    missing.add((i, j))

    V = [[None] * nr for _ in range(ns)]
    for i in range(ns):
        for j in range(nr):
            if (i, j) in missing:
                continue
            V[i][j] = bm.verts.new(secs[i][ROWS[j]])
    # glass tips: rail (L2) and belt (L3) end in one vertex
    for s in (X_A0, X_TIP):
        i = idx[s]
        bm.verts.remove(V[i][R['L3']])
        V[i][R['L3']] = V[i][R['L2']]

    def face(vs, m):
        uniq = []
        for v in vs:
            if v is None:
                return None
            if not uniq or uniq[-1] is not v:
                uniq.append(v)
        if len(uniq) > 1 and uniq[0] is uniq[-1]:
            uniq.pop()
        if len(uniq) < 3:
            return None
        f = bm.faces.new(uniq)
        f.material_index = m
        f.smooth = True
        return f

    def crease(a, b, w, bevel=0.0):
        if a is None or b is None or a is b:
            return
        e = bm.edges.get((a, b))
        if e is not None:
            if bevel == SHARP:
                e[CL] = 1.0
                e.smooth = False
            else:
                e[CL] = max(e[CL], w)
                e[BL] = max(e[BL], bevel)

    def hard(a, b):
        crease(a, b, 0.0, HARD)

    def sharp(a, b):
        crease(a, b, 0.0, SHARP)

    # longitudinal strips
    for i in range(ns - 1):
        xm = 0.5 * (st[i] + st[i + 1])
        for j in range(nr - 1):
            face((V[i][j], V[i][j + 1], V[i + 1][j + 1], V[i + 1][j]), strip_material(j, xm))
    for i in range(ns - 1):
        xm = 0.5 * (st[i] + st[i + 1])
        for j in range(nr):
            bw, cw = row_edge(j, xm, full=not holes)
            crease(V[i][j], V[i + 1][j], cw, bw)

    # transverse hard edges: windscreen base, glass end + C-pillar end + slanted tail-corner
    # crease, lamp triangle rear edge, fender facet / roof rail break at the A-pillar foot
    for s, j0, j1, kind in ((X_WS, 0, R['L1'], SHARP), (X_GE, 0, R['L6'], SHARP),
                            (X_T, R['L1'], R['L2'], HARD), (X_A0, R['L1'], R['L2'], SHARP)):
        i = idx[s]
        for j in range(j0, j1):
            crease(V[i][j], V[i][j + 1], 0.0, kind)

    arches = []
    for wx, ia, ib, jt, follow in arch_ix:
        arches.append(build_arch_patch(bm, V, st, wx, ia, ib, jt, follow, face, hard, sharp, ref))

    build_caps(bm, V, face, hard)

    # glass corners stay pointed (crease-rule corners)
    for v in (V[idx[X_A0]][R['L2']], V[idx[X_TIP]][R['L2']], V[idx[X_A0]][R['L1']],
              V[idx[X_GE]][R['L1']], V[idx[X_WS]][R['L1']], V[idx[X_GE]][R['L4']]):
        v[VL] = 1.0
    return bm, arches


def build_body():
    # 1. the uncut body: the surface the arch patches are fitted to
    bm_ref, _ = build_half(False)
    ref_ob = temp_object("BodyRef", bm_ref)
    bm_ref.free()
    ref = BVHTree.FromObject(ref_ob, bpy.context.evaluated_depsgraph_get())
    drop_object(ref_ob)
    # 2. the body with the wheel arches; patch rings fitted to the uncut surface
    bm, arches = build_half(True, ref)
    fit_arches(bm, arches, ref)
    arch_loops = [a['pts'] for a in arches]

    # mirror to the left side; centre-line vertices weld
    geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
    bmesh.ops.mirror(bm, geom=geom, matrix=Matrix(), merge_dist=1e-5, axis='Y')
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    for f in bm.faces:
        f.smooth = True

    me = bpy.data.meshes.new("Body")
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new("Body", me)
    scene.collection.objects.link(ob)
    for k in ('paint', 'glass', 'black', 'well'):
        me.materials.append(M[k])
    add_body_modifiers(ob)
    return ob, arch_loops


def surface_y(ref, x, z, fallback):
    """Y of the uncut body side at (x, z)."""
    hit = ref.ray_cast(Vector((x, 1.6, z)), Vector((0.0, -1.0, 0.0)), 2.0)[0]
    return hit.y if hit is not None else fallback


def build_arch_patch(bm, V, st, wx, ia, ib, jt, follow, face, hard, sharp, ref):
    """Radial ring patch between the cage boundary (outer U) and the arch circle, plus flange.
    Ring points start on the uncut body surface; fit_arches() then refines them."""
    jb = R['L7']
    wz, RR = WHEEL_Z, ARCH_R
    U = ([(ia, j) for j in range(jb, jt[ia] - 1, -1)] + [(i, jt[i]) for i in range(ia + 1, ib)]
         + [(ib, j) for j in range(jt[ib], jb + 1)])
    Mn = len(U)
    outer = [V[i][j] for i, j in U]
    oxz = [(v.co.x, v.co.z) for v in outer]

    def ang(x, z):
        a = math.atan2(z - wz, x - wx)
        if a < -math.pi / 2 and x < wx:
            a += 2 * math.pi            # front-lower quadrant continues past 180 deg
        return a

    def row_hit(fn, x_out):
        def g(x):
            p = fn(x)
            return math.hypot(p[0] - wx, p[2] - wz) - RR
        a, b = x_out, wx
        for i in range(1, 201):                 # first crossing, going in from the cage column
            x = x_out + (wx - x_out) * i / 200
            if (g(x) > 0) != (g(a) > 0):
                b = x
                break
            a = x
        for _ in range(60):
            m = 0.5 * (a + b)
            if (g(m) > 0) == (g(a) > 0):
                a = m
            else:
                b = m
        p = fn(0.5 * (a + b))
        return p[0], p[2]

    # pinned spokes: these rows end exactly where they meet the circle; U corners radial
    pins, row_of, kind = {}, {}, {}
    pinned = [('L7', 'both', sharp), ('L6b', 'both', sharp), ('L6', 'both', hard)]
    pinned += [(n, side, sharp) for side in ('front', 'rear') for n in follow.get(side, ())]
    for name, sides, kfn in pinned:
        k = jb - R[name]
        for kk, x_out, side in ((k, oxz[0][0], 'front'), (Mn - 1 - k, oxz[-1][0], 'rear')):
            if sides not in ('both', side):
                continue
            x, z = row_hit(LINE_FN[name], x_out)
            pins[kk] = ang(x, z)
            row_of[kk] = LINE_FN[name]
            kind[kk] = kfn
    for kk, side in ((jb - jt[ia], 'front'), (Mn - 1 - (jb - jt[ib]), 'rear')):
        if not follow.get(side):
            pins[kk] = ang(*oxz[kk])
    # remaining spokes: distribute by arc length of the outer U between pins
    u = [0.0]
    for k in range(1, Mn):
        u.append(u[-1] + math.hypot(oxz[k][0] - oxz[k - 1][0], oxz[k][1] - oxz[k - 1][1]))
    keys = sorted(pins)
    theta = [0.0] * Mn
    for a, b in zip(keys[:-1], keys[1:]):
        for k in range(a, b + 1):
            t = (u[k] - u[a]) / (u[b] - u[a])
            theta[k] = pins[a] + t * (pins[b] - pins[a])

    D_SUP = 0.018
    rings = [outer, [], [], [], [], []]
    for k in range(Mn):
        th = theta[k]
        c, s = math.cos(th), math.sin(th)
        xa, za = wx + RR * c, wz + RR * s
        xo, zo = oxz[k]
        yo = outer[k].co.y
        if k in row_of:
            fn = row_of[k]
            xs = xa + math.copysign(D_SUP, xo - xa)
            zs = fn(xs)[2]
            xm = 0.5 * (xo + xs)
            zm = fn(xm)[2]
        else:
            xs, zs = xa + D_SUP * c, za + D_SUP * s
            xm, zm = 0.5 * (xo + xs), 0.5 * (zo + zs)
        if k in row_of:     # crease rows: on the line itself
            rings[1].append(bm.verts.new((xm, row_of[k](xm)[1], zm)))
            rings[2].append(bm.verts.new((xs, row_of[k](xs)[1], zs)))
        else:
            rings[1].append(bm.verts.new((xm, surface_y(ref, xm, zm, yo), zm)))
            rings[2].append(bm.verts.new((xs, surface_y(ref, xs, zs, yo), zs)))
        rings[3].append(bm.verts.new((xa, surface_y(ref, xa, za, yo), za)))
    for k in range(Mn):
        rings[4].append(bm.verts.new((0.0, 0.0, 0.0)))
        rings[5].append(bm.verts.new((0.0, 0.0, 0.0)))
    nh = []                                      # horizontal outward normal of the body at the lip
    for v in rings[3]:
        n = ref.find_nearest(v.co)[1] if ref is not None else None
        n = Vector((n.x, n.y, 0.0)) if n is not None else Vector((0.0, 1.0, 0.0))
        if n.y < 0:
            n = -n
        nh.append(n.normalized() if n.length > 1e-6 else Vector((0.0, 1.0, 0.0)))
    nh = [sum(nh[max(0, k - 1):k + 2], Vector()).normalized() for k in range(Mn)]
    arch = {'rings': rings, 'theta': theta, 'Mn': Mn, 'fixed': set(row_of), 'nh': nh}
    update_flange(arch)
    for r in range(5):
        for k in range(Mn - 1):
            m = MAT_BLACK if (k < 2 or k >= Mn - 3) else MAT_PAINT
            face((rings[r][k], rings[r][k + 1], rings[r + 1][k + 1], rings[r + 1][k]), m)
    for k, kfn in kind.items():                    # followed rows run on into the arch ...
        for r in range(3):
            kfn(rings[r][k], rings[r + 1][k])
    for k in range(Mn - 1):                        # ... and end on the bevelled arch lip
        hard(rings[3][k], rings[3][k + 1])
    return arch


def update_flange(arch):
    """Turned-in flange behind the lip, folded in along the body's inward normal (where the arch
    cuts the angled nose facet that is not simply -Y); depth taken from the innermost nearby lip
    point so it never folds back over the sill step. Also refreshes the lip loop for the tubs."""
    rings, theta, Mn, nh = arch['rings'], arch['theta'], arch['Mn'], arch['nh']
    lip = [v.co.copy() for v in rings[3]]
    pts = []
    for k in range(Mn):
        c, s = math.cos(theta[k]), math.sin(theta[k])
        p, n = lip[k], nh[k]
        depth = min((q - p).dot(n) for q in lip[max(0, k - 2):k + 3])     # <= 0
        rad = Vector((c, 0.0, s))
        rings[4][k].co = p + rad * 0.004 + n * (depth - 0.014)
        rings[5][k].co = p + rad * 0.010 + n * (depth - 0.045)
        pts.append((p.x, p.y, p.z, theta[k], n.x, n.y))
    arch['pts'] = pts


def fit_arches(bm, arches, ref, iters=16, gain=1.3, step=0.006):
    """Move the arch ring points along the reference normal until the subdivided patch lies on
    the uncut body surface. Crease-row spokes stay on their lines; the lip point moves with the
    support-ring point of its spoke."""
    jobs = []
    for a in arches:
        rg = a['rings']
        for k in range(a['Mn']):
            if k in a['fixed']:
                continue
            jobs.append((rg[1][k], None))
            jobs.append((rg[2][k], rg[3][k]))
    tmp = temp_object("FitTmp", bm)
    for it in range(iters):
        for a in arches:
            update_flange(a)
        bm.to_mesh(tmp.data)
        tmp.data.update()
        dg = bpy.context.evaluated_depsgraph_get()
        dg.update()
        cur = BVHTree.FromObject(tmp, dg)
        err = []
        for v, follower in jobs:
            q, n, _, _ = ref.find_nearest(v.co)
            if q is None:
                continue
            if n.dot(Vector((0.0, q.y, q.z - 0.55))) < 0:
                n = -n
            hit = cur.ray_cast(q + n * 0.03, -n, 0.06)[0]     # from outside: the outer skin
            if hit is None:
                continue
            e = (q - hit).dot(n)
            if abs(e) > 0.02:
                continue
            err.append(abs(e))
            d = n * max(-step, min(step, gain * e))
            v.co += d
            if follower is not None:
                follower.co += d
        print(f"ARCH FIT {it}: max {max(err) * 1000:.2f} mm  mean {np.mean(err) * 1000:.2f} mm")
    for a in arches:
        update_flange(a)
    drop_object(tmp)


def grid_fill(bm, face, top, bottom, centre, side, m):
    """Half-cap quad grid (Coons patch). top[a], bottom[a]: a=0 centre .. A side;
    centre[b], side[b]: b=0 top .. B bottom. Corner vertices are shared."""
    A, B = len(top) - 1, len(side) - 1
    tp = [v.co.copy() for v in top]
    bp = [v.co.copy() for v in bottom]
    cp = [v.co.copy() for v in centre]
    sp = [v.co.copy() for v in side]
    # v parameter from the side's arc length so cap rows line up with the body rows
    lens = [0.0]
    for b in range(1, B + 1):
        lens.append(lens[-1] + (sp[b] - sp[b - 1]).length)
    G = [[None] * (B + 1) for _ in range(A + 1)]
    for a in range(A + 1):
        G[a][0], G[a][B] = top[a], bottom[a]
    for b in range(B + 1):
        G[0][b], G[A][b] = centre[b], side[b]
    for a in range(1, A):
        u = a / A
        for b in range(1, B):
            v = lens[b] / lens[B]
            p = ((1 - u) * cp[b] + u * sp[b] + (1 - v) * tp[a] + v * bp[a]
                 - ((1 - u) * (1 - v) * tp[0] + u * (1 - v) * tp[A] + (1 - u) * v * bp[0] + u * v * bp[A]))
            G[a][b] = bm.verts.new(p)
    for a in range(A):
        for b in range(B):
            face((G[a][b], G[a + 1][b], G[a + 1][b + 1], G[a][b + 1]), m)
    return G


def build_caps(bm, V, face, hard):
    r = R
    # ---- nose: black front face, 3 x 10 half grid
    n0 = V[0]
    top = [n0[r['L0']], n0[r['C1']], n0[r['C2']], n0[r['L1']]]
    side = [n0[j] for j in range(r['L1'], r['L7'] + 1)]
    bottom = [n0[r['L8']], n0[r['F2']], n0[r['F1']], n0[r['L7']]]
    sp = [v.co for v in side]
    lens = [0.0]
    for b in range(1, len(sp)):
        lens.append(lens[-1] + (sp[b] - sp[b - 1]).length)
    centre = [top[0]]
    for b in range(1, len(side) - 1):
        t = lens[b] / lens[-1]
        p = top[0].co * (1 - t) + bottom[0].co * t
        centre.append(bm.verts.new((p.x, 0.0, p.z)))
    centre.append(bottom[0])
    grid_fill(bm, face, top, bottom, centre, side, MAT_BLACK)
    for chain in (top, side, bottom):
        for a, b in zip(chain[:-1], chain[1:]):
            hard(a, b)

    # ---- tail: silver panel 7 x 4 half grid, black receding diffuser face below
    t0 = V[-1]
    top = [t0[j] for j in range(r['L0'], r['L4'] + 1)]
    side = [t0[j] for j in range(r['L4'], r['L6'] + 1)]
    c_top, l6 = top[0].co, side[-1].co
    cb = Vector((XR, 0.0, l6.z))
    bottom = [bm.verts.new(cb)]
    A = len(top) - 1
    for a in range(1, A):
        p = cb.lerp(l6, a / A)
        bottom.append(bm.verts.new(p))
    bottom.append(side[-1])
    sp = [v.co for v in side]
    lens = [0.0]
    for b in range(1, len(sp)):
        lens.append(lens[-1] + (sp[b] - sp[b - 1]).length)
    centre = [top[0]]
    for b in range(1, len(side) - 1):
        t = lens[b] / lens[-1]
        p = c_top.lerp(cb, t)
        centre.append(bm.verts.new((p.x, 0.0, p.z)))
    centre.append(bottom[0])
    grid_fill(bm, face, top, bottom, centre, side, MAT_PAINT)
    lower = bottom + [t0[r['L6b']], t0[r['L7']], t0[r['F1']], t0[r['F2']], t0[r['L8']]]
    face(lower[::-1], MAT_BLACK)
    for chain in (top, side, bottom, [t0[r['L6']], t0[r['L6b']], t0[r['L7']]],
                  [t0[r['L7']], t0[r['F1']], t0[r['F2']], t0[r['L8']]]):
        for a, b in zip(chain[:-1], chain[1:]):
            hard(a, b)


def build_wheel_tubs(arch_loops):
    """Dark wheel-house liners tucked behind each arch flange (separate, not subdivided)."""
    for n, pts in enumerate(arch_loops):
        for sgn in (1, -1):
            bm = bmesh.new()
            outer, inner = [], []
            for xa, ya, za, th, nx, ny in pts:
                c, s = math.cos(th), math.sin(th)
                rx, rz = xa + 0.012 * c - 0.02 * nx, za + 0.012 * s
                outer.append(bm.verts.new((rx, sgn * (ya - 0.02 * ny), rz)))
                inner.append(bm.verts.new((rx, sgn * 0.60, rz)))
            for k in range(len(pts) - 1):
                bm.faces.new((outer[k], outer[k + 1], inner[k + 1], inner[k]))
            bm.faces.new(inner)
            mesh_obj(f"WheelTub_{n}{'R' if sgn > 0 else 'L'}", bm, M['well'])


# ---------------------------------------------------------- detail helpers
class Surface:
    def __init__(self, ob):
        dg = bpy.context.evaluated_depsgraph_get()
        self.bvh = BVHTree.FromObject(ob, dg)

    def project(self, p, d, off=0.0015):
        d = Vector(d).normalized()
        o = Vector(p) - d * 2.0
        hit, nrm, _, _ = self.bvh.ray_cast(o, d, 5.0)
        if hit is None:
            return None, None
        if nrm.dot(d) > 0:
            nrm = -nrm
        return hit + nrm * off, nrm


def resample(pts, step=0.01):
    pts = [Vector(p) for p in pts]
    out = [pts[0]]
    for a, b in zip(pts[:-1], pts[1:]):
        n = max(1, int((b - a).length / step))
        for i in range(1, n + 1):
            out.append(a.lerp(b, i / n))
    return out


def curve_obj(name, polylines, radius, material, closed=False):
    cu = bpy.data.curves.new(name, 'CURVE')
    cu.dimensions = '3D'
    cu.bevel_depth = radius
    cu.bevel_resolution = 2
    cu.use_fill_caps = True
    for pl in polylines:
        if len(pl) < 2:
            continue
        sp = cu.splines.new('POLY')
        sp.points.add(len(pl) - 1)
        for i, p in enumerate(pl):
            sp.points[i].co = (p[0], p[1], p[2], 1.0)
        sp.use_cyclic_u = closed
    ob = bpy.data.objects.new(name, cu)
    cu.materials.append(material)
    scene.collection.objects.link(ob)
    return ob


def proj_line(surf, pts3, d, step=0.008, off=0.0003):
    out = []
    for p in resample(pts3, step):
        q, _ = surf.project(p, d, off)
        if q is not None:
            out.append(q)
    return out


def both_sides(fn):
    return [fn(1), fn(-1)]


# ------------------------------------------------------------ panel lines
def add_panel_lines(surf):
    side, top = [], []
    # --- side-view lines (X, Z): projected horizontally onto each flank
    side_xz = [
        # front door shut-line: sill -> under side marker -> up to the glass
        [(-0.808, 0.30), (-0.907, 0.753), (-0.80, 0.86), (-0.765, 0.893)],
        # rear door shut-line (B-pillar) from belt to sill
        [(0.481, 1.005), (0.272, 0.364)],
        # side-glass seams: A-pillar double line, B-pillar double line
        [(-0.765, 0.889), (-0.352, 1.225)],
        [(-0.654, 0.889), (-0.253, 1.238)],
        [(0.518, 1.27), (0.333, 1.0)],
        [(0.62, 1.282), (0.44, 1.02)],
    ]
    def on_glass(x, z):  # keep side-glass seam ends inside the glass outline
        return min(max(z, L3(x)[2] + 0.004), L2(x)[2] - 0.004) if X_A0 < x < X_TIP else z
    for k, pl in enumerate(side_xz):
        if k >= 2:
            side_xz[k] = [(x, on_glass(x, z)) for x, z in pl]
    for sgn in (1, -1):
        for pl in side_xz:
            pts = [(x, sgn * 1.4, z) for x, z in pl]
            side.append(proj_line(surf, pts, (0, -sgn, 0)))

    # --- top-view lines (X, Y): projected vertically
    top_xy = [
        # hood shut-line in front of the cowl
        [(-1.86, -0.565), (-1.86, 0.565)],
        # glass roof seams: windscreen/roof V, centre spine, roof/rear-glass
        [(-0.31, 0.70), (-0.251, 0.205), (-0.251, -0.205), (-0.31, -0.70)],
        [(-0.251, 0.205), (0.69, 0.115)],
        [(-0.251, -0.205), (0.69, -0.115)],
        [(0.70, 0.615), (0.70, -0.615)],
        # head-lamp triangle edges (H0-T and T-B) both sides
        [(XF + 0.01, 0.655), (X_T, 0.775), (X_T - 0.005, 0.605)],
        [(XF + 0.01, -0.655), (X_T, -0.775), (X_T - 0.005, -0.605)],
    ]
    # hood side edges (hood panel / fender-top facet crease)
    for sgn in (1, -1):
        top_xy.append([(s, sgn * (L1(s)[1] - 0.003)) for s in np.linspace(XF + 0.02, X_WS - 0.01, 40)])
    for pl in top_xy:
        pts = [(x, y, 2.0) for x, y in pl]
        top.append(proj_line(surf, pts, (0, 0, -1)))

    # glass perimeter outline (canopy edge + windscreen base + rear edge, side glass)
    def canopy_edge(sgn):
        ss = np.linspace(X_WS, X_GE, 160)
        return [(s, sgn * L1(s)[1] - sgn * 0.004, 2.0) for s in ss]
    for sgn in (1, -1):
        top.append(proj_line(surf, canopy_edge(sgn), (0, 0, -1)))
    top.append(proj_line(surf, [(X_WS + 0.004, 0.53, 2), (X_WS + 0.004, -0.53, 2)], (0, 0, -1)))
    yge = L1(X_GE)[1] - 0.004
    top.append(proj_line(surf, [(X_GE - 0.004, yge, 2), (X_GE - 0.004, -yge, 2)], (0, 0, -1)))
    for sgn in (1, -1):
        ss = np.linspace(X_A0 + 0.03, X_TIP - 0.035, 140)   # outline stops short of the glass tips
        up = [(s, sgn * 1.4, L2(s)[2] - 0.004) for s in ss]
        lo = [(s, sgn * 1.4, L3(s)[2] + 0.004) for s in ss]
        side.append(proj_line(surf, up, (0, -sgn, 0)))
        side.append(proj_line(surf, lo, (0, -sgn, 0)))

    curve_obj("PanelLines_Side", side, 0.0013, M['line'])
    curve_obj("PanelLines_Top", top, 0.0013, M['line'])


# --------------------------------------------------------- small details
def shell_from_outline(name, surf, outline_xz, sgn, depth_fn, material):
    """Extrude a side-view outline (X,Z) off the flank surface; depth_fn(x)->protrusion."""
    pts = []
    for x, z in outline_xz:
        q, nrm = surf.project((x, sgn * 1.4, z), (0, -sgn, 0), 0.0)
        pts.append((q, nrm, depth_fn(x)))
    bm = bmesh.new()
    inner = [bm.verts.new(q - nrm * 0.004) for q, nrm, dd in pts]
    outer = [bm.verts.new(q + nrm * dd) for q, nrm, dd in pts]
    bm.faces.new(outer if sgn > 0 else outer[::-1])
    k = len(pts)
    for i in range(k):
        bm.faces.new((inner[i], inner[(i + 1) % k], outer[(i + 1) % k], outer[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    me.materials.append(material)
    scene.collection.objects.link(ob)
    return ob


def add_side_markers(surf):
    for sgn in (1, -1):
        blade = [(-1.178, 0.722), (-1.05, 0.732), (-0.907, 0.756), (-0.907, 0.692), (-1.05, 0.705),
                 (-1.178, 0.716)]
        shell_from_outline("SideBlade", surf, blade, sgn,
                           lambda x: 0.003 + 0.012 * (x + 1.178) / 0.271, M['black'])
        refl = [(-1.165, 0.7215), (-1.06, 0.7305), (-1.06, 0.709), (-1.165, 0.7175)]
        shell_from_outline("SideMarker", surf, refl, sgn,
                           lambda x: 0.0045 + 0.012 * (x + 1.178) / 0.271, M['amber'])


def add_door_handles(surf):
    for sgn in (1, -1):
        cx, cz, w, h, r = 0.475, 0.952, 0.085, 0.034, 0.012
        outline = []
        for k in range(4):
            ccx = cx + (w / 2 - r) * (1 if k in (0, 3) else -1)
            ccz = cz + (h / 2 - r) * (1 if k in (0, 1) else -1)
            for a in np.linspace(0, math.pi / 2, 5):
                ang = a + k * math.pi / 2
                outline.append((ccx + r * math.cos(ang), ccz + r * math.sin(ang)))
        shell_from_outline("DoorHandle", surf, outline, sgn, lambda x: 0.0025, M['paint'])
        ring = []
        for x, z in outline + outline[:1]:
            q, _ = surf.project((x, sgn * 1.4, z), (0, -sgn, 0), 0.0028)
            ring.append(q)
        curve_obj("DoorHandleGap", [ring], 0.0011, M['line'])


def add_lamps(surf):
    # slim LED blade along the T-B edge of each head-lamp triangle
    pls = []
    for sgn in (1, -1):
        pts = [(X_T + 0.006, sgn * 0.765, 2.0), (X_T - 0.001, sgn * 0.615, 2.0)]
        pls.append(proj_line(surf, pts, (0, 0, -1), off=0.002))
    curve_obj("HeadLamp_LED", pls, 0.0035, M['lamp'])
    # rear: full-width red light bar across the tail + wrap along the chamfer
    bar = []
    ys = np.linspace(-0.86, 0.86, 120)
    bar.append(proj_line(surf, [(3.0, y, 0.852) for y in ys], (-1, 0, 0), off=0.001))
    for sgn in (1, -1):
        ss = np.linspace(X_C6 + 0.01, XR - 0.01, 30)
        pts = [(s, sgn * 1.4, L6_tail(s)[2] + 0.018) for s in ss]
        bar.append(proj_line(surf, pts, (0, -sgn, 0), off=0.001))
    curve_obj("TailLamp", bar, 0.0045, M['red'])


def box(name, c, size, material, rot=None):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=size, verts=bm.verts)
    if rot is not None:
        bmesh.ops.rotate(bm, matrix=rot, verts=bm.verts)
    bmesh.ops.translate(bm, vec=c, verts=bm.verts)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    me.materials.append(material)
    scene.collection.objects.link(ob)
    return ob


def add_aero():
    # front splitter lip (full width, proud of the nose face)
    bm = bmesh.new()
    outline = [(-2.388, -0.70), (-2.388, 0.70), (-2.15, 0.84), (-1.95, 0.97), (-1.95, -0.97),
               (-2.15, -0.84)]
    vb = [bm.verts.new((x, y, 0.215)) for x, y in outline]
    vt = [bm.verts.new((x, y, 0.262)) for x, y in outline]
    bm.faces.new(vt)
    bm.faces.new(vb[::-1])
    k = len(outline)
    for i in range(k):
        bm.faces.new((vb[i], vb[(i + 1) % k], vt[(i + 1) % k], vt[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new("FrontSplitter")
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new("FrontSplitter", me)
    me.materials.append(M['black'])
    scene.collection.objects.link(ob)
    # lower intake bar (lighter graphite slot under the nose)
    box("FrontIntakeBar", (-2.30, 0, 0.185), (0.05, 1.30, 0.03), M['darkmetal'])
    # rear diffuser tiers (stepped profile seen in the side view)
    def x_cap(z):  # receding black tail face between L7 (bottom) and L6b (top)
        return 2.29 + (z - 0.22) / (0.828 - 0.22) * (XR - 2.29)
    for z in (0.67, 0.55, 0.364):
        xc = x_cap(z)
        box("DiffuserTier", (xc - 0.0175, 0, z), (0.065, 1.62, 0.016), M['black'])
    for y in (-0.55, -0.28, 0.0, 0.28, 0.55):
        box("DiffuserFin", (2.28, y, 0.30), (0.07, 0.012, 0.16), M['black'])


# ---------------------------------------------------------------- wheels
def spin_profile(bm, prof, steps=96):
    verts = [bm.verts.new((r, y, 0.0)) for r, y in prof]
    edges = [bm.edges.new((verts[i], verts[(i + 1) % len(verts)])) for i in range(len(verts))]
    bmesh.ops.spin(bm, geom=verts + edges, cent=(0, 0, 0), axis=(0, 1, 0),
                   angle=2 * math.pi, steps=steps, use_duplicate=False)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)


def mesh_obj(name, bm, material, smooth=True, parent=None):
    if smooth:
        for f in bm.faces:
            f.smooth = True
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    me.materials.append(material)
    scene.collection.objects.link(ob)
    if parent is not None:
        ob.parent = parent
    return ob


def build_wheel(root):
    # tyre: rounded-rectangle section spun about the axle (axle = local Y, outer face = +Y)
    a, b, ex = 0.045, 0.142, 5.0
    rc = TYRE_R - a
    prof = []
    for th in np.linspace(0, 2 * math.pi, 56, endpoint=False):
        c, s = math.cos(th), math.sin(th)
        prof.append((rc + a * math.copysign(abs(c) ** (2 / ex), c), b * math.copysign(abs(s) ** (2 / ex), s)))
    bm = bmesh.new()
    spin_profile(bm, prof, 96)
    mesh_obj("Tyre", bm, M['tire'], parent=root)

    # aero disc (the light segments between the spokes) + inner barrel
    bm = bmesh.new()
    spin_profile(bm, [(0.0, 0.065), (0.292, 0.065), (0.300, 0.075), (0.300, -0.12), (0.0, -0.12)], 96)
    mesh_obj("RimDisc", bm, M['rimdisc'], parent=root)

    # gloss-black rim lip
    bm = bmesh.new()
    spin_profile(bm, [(0.288, 0.075), (0.312, 0.075), (0.316, 0.105), (0.300, 0.122), (0.288, 0.112)], 96)
    mesh_obj("RimLip", bm, M['rimblack'], parent=root)

    # six-spoke star: constant-width spokes that open into V-notches at the hub
    def P(r, ang):
        return (r * math.cos(ang), r * math.sin(ang))
    hw, r_tip, r_par, r_apex = 0.029, 0.292, 0.150, 0.098
    poly = []
    for k in range(6):
        th = math.radians(90 + 60 * k)
        ux, uy = math.cos(th), math.sin(th)
        px, py = -uy, ux
        # leading side of spoke k (toward k+1): tip corner then parallel run inward
        poly.append((r_tip * ux + hw * px, r_tip * uy + hw * py))
        poly.append((r_par * ux + hw * px, r_par * uy + hw * py))
        poly.append(P(r_apex, th + math.radians(30)))
        th2 = th + math.radians(60)
        ux2, uy2 = math.cos(th2), math.sin(th2)
        px2, py2 = -uy2, ux2
        poly.append((r_par * ux2 - hw * px2, r_par * uy2 - hw * py2))
        poly.append((r_tip * ux2 - hw * px2, r_tip * uy2 - hw * py2))
    # remove duplicated tip corners -> star polygon in the wheel plane (x, z)
    clean = []
    for p in poly:
        if not clean or (abs(p[0] - clean[-1][0]) + abs(p[1] - clean[-1][1])) > 1e-6:
            clean.append(p)
    bm = bmesh.new()
    y0, y1 = 0.072, 0.112
    vb = [bm.verts.new((x, y0, z)) for x, z in clean]
    vt = [bm.verts.new((x, y1 - 0.012 * (math.hypot(x, z) / r_tip), z)) for x, z in clean]
    ct = bm.verts.new((0, y1 + 0.004, 0))
    cb = bm.verts.new((0, y0, 0))
    k = len(clean)
    for i in range(k):
        bm.faces.new((vt[i], vt[(i + 1) % k], ct))
        bm.faces.new((vb[(i + 1) % k], vb[i], cb))
        bm.faces.new((vb[i], vb[(i + 1) % k], vt[(i + 1) % k], vt[i]))
    mesh_obj("Spokes", bm, M['rimblack'], smooth=False, parent=root)

    # copper chevrons tracing each V-notch
    pls = []
    for kk in range(6):
        th = math.radians(90 + 60 * kk)
        th2 = th + math.radians(60)
        mid = th + math.radians(30)
        inset = 0.010

        def side_pt(t_ang, r, sgn):
            ux, uy = math.cos(t_ang), math.sin(t_ang)
            px, py = -uy, ux
            return (r * ux + sgn * (hw + inset) * px, r * uy + sgn * (hw + inset) * py)
        a1 = side_pt(th, 0.215, 1)
        a2 = side_pt(th, r_par + 0.004, 1)
        ap = P(r_apex + inset * 1.9, mid)
        b2 = side_pt(th2, r_par + 0.004, -1)
        b1 = side_pt(th2, 0.215, -1)
        pts = [a1, a2, ap, b2, b1]
        pls.append([(x, 0.0745, z) for x, z in pts])
    cob = curve_obj("CopperChevrons", pls, 0.0024, M['copper'])
    cob.parent = root

    # hub cap + badge
    bm = bmesh.new()
    spin_profile(bm, [(0.0, 0.128), (0.045, 0.126), (0.058, 0.112), (0.058, 0.09), (0.0, 0.09)], 48)
    mesh_obj("HubCap", bm, M['rimblack'], parent=root)
    bm = bmesh.new()
    spin_profile(bm, [(0.0, 0.1295), (0.018, 0.1288), (0.018, 0.124), (0.0, 0.124)], 32)
    mesh_obj("HubBadge", bm, M['chrome'], parent=root)

    # brake disc + calliper (just visible through the gaps)
    bm = bmesh.new()
    spin_profile(bm, [(0.06, 0.03), (0.20, 0.03), (0.20, 0.0), (0.06, 0.0)], 48)
    mesh_obj("BrakeDisc", bm, M['darkmetal'], parent=root)


def build_wheels():
    proto = bpy.data.objects.new("Wheel_Proto", None)
    scene.collection.objects.link(proto)
    build_wheel(proto)
    kids = [c for c in proto.children]
    wheels = []
    for name, wx, sgn in (("Wheel_FL", WHEEL_X[0], -1), ("Wheel_FR", WHEEL_X[0], 1),
                          ("Wheel_RL", WHEEL_X[1], -1), ("Wheel_RR", WHEEL_X[1], 1)):
        root = bpy.data.objects.new(name, None)
        scene.collection.objects.link(root)
        root.location = (wx, sgn * 0.885, WHEEL_Z)
        if sgn < 0:
            root.scale = (1, -1, 1)
        for c in kids:
            d = c.copy()
            d.data = c.data
            scene.collection.objects.link(d)
            d.parent = root
        wheels.append(root)
    for c in kids:
        bpy.data.objects.remove(c)
    bpy.data.objects.remove(proto)
    return wheels



# ------------------------------------------------------------------ main
body, arch_loops = build_body()
build_wheel_tubs(arch_loops)
surf = Surface(body)
add_panel_lines(surf)
add_side_markers(surf)
add_door_handles(surf)
add_lamps(surf)
add_aero()
build_wheels()

# group everything under one collection for export
col = bpy.data.collections.new("WedgeEV")
scene.collection.children.link(col)
for ob in list(scene.collection.objects):
    scene.collection.objects.unlink(ob)
    col.objects.link(ob)

me = body.data
ev = body.evaluated_get(bpy.context.evaluated_depsgraph_get()).data
print("BODY cage verts", len(me.vertices), "faces", len(me.polygons), "| subdivided faces", len(ev.polygons))
path = os.path.join(OUT, "wedge_car.blend")
bpy.ops.wm.save_as_mainfile(filepath=path)
print("SAVED", path)
