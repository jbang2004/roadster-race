"""
Wedge EV concept — Blender rebuild from the four-view reference sheet.

Run:  blender -b --python build_car.py -- <out_dir>
Writes <out_dir>/wedge_car.blend

Units: metres, 1:1.  Axes: X = length (front at -X), Y = width, Z = up, ground at Z = 0.
Overall: L 4.75  W 2.20  H 1.34  wheelbase 3.10  tyre Ø 0.80

v2 body: a quad control cage under a Subdivision Surface modifier.
  * cage rows follow the character lines measured off the side / top / front views,
    now as smooth curves (no piecewise-linear kinks);
  * feature lines are held by edge creases, so they read as crisp edges with a small radius;
  * the wheel arches are modelled into the cage: radial rings around a true circle and a
    turned-in flange (no boolean);
  * the nose / tail caps are quad grids, and lines that used to collapse into one point are
    spread along the front-face edge or end in a proper glass tip.

v3 surfacing (faceted, after the Roadster 2 photos): the body is a set of flat facets split by
sharp creases. Only the fender over each wheel and the ledge under the side glass stay curved.
  * hood + fender top: one plane through the straight hood edge and the A-pillar foot;
    the lamp triangle and fender ridge lie in it;
  * flank: flat ledge under the glass, a sharp shoulder crease (the widest line of the body),
    then a flat, slightly tucked-under slab down to the black sill;
  * nose corner: the lamp triangle, a flat triangle under it and a flat chamfer facet down to
    the sill, all ahead of the front arch;
  * rear: a lightly crowned C-pillar surface between the glass edge and the shoulder crease,
    a flat deck, and a flat tail-corner chamfer behind a vertical crease.
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


def smin(a, b, k):
    """C1 smooth minimum: rounds the corner where two plan-view lines meet (blend width ~k)."""
    h = max(k - abs(a - b), 0.0) / k
    return min(a, b) - h * h * k * 0.25


def smoothstep(e0, e1, x):
    t = min(max((x - e0) / (e1 - e0), 0.0), 1.0)
    return t * t * (3 - 2 * t)


# ------------------------------------------------------- key stations (X)
XF, XR = -2.375, 2.375        # nose / tail
X_T = -2.05                   # head-lamp triangle apex T / hood point B
X_FF = -1.88                  # front-fender leading face reaches full width
X_WS = -1.55                  # windscreen base (centre)
X_A0 = -1.40                  # A-pillar foot: rail + side glass start
X_TIP = 1.197                 # side-glass rear tip
X_GE = 2.03                   # end of the glass canopy
X_CH = 2.11                   # tail-corner chamfer crease (behind the rear arch)
WHEEL_X = (-1.487, 1.61)
WHEEL_Z, TYRE_R, ARCH_R = 0.39, 0.39, 0.4225   # ARCH_R = arch radius on the body flank

A0P = (0.93, 0.912)           # (Y, Z) side-glass front tip: ridge, rail and belt meet here
TIPP = (0.695, 1.19)          # (Y, Z) side-glass rear tip: rail and belt meet here (top view: Y 0.70)
H0 = (XF, 0.66, 0.50)         # hood front corner
P4 = (X_WS, 0.53, 0.84)       # windscreen-base corner, rear end of the hood edge


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


T_PT = (X_T, 0.78, fender_z(X_T, 0.78))     # head-lamp triangle apex, on the fender plane

# roof / windscreen centre-line (side-view silhouette); at the A-pillar foot the glass edge
# sits on the fender plane
ZC = [(X_WS, 0.84), (X_A0, fender_z(X_A0, 0.90)), (-1.24, 0.969), (-0.931, 1.086), (-0.623, 1.191),
      (-0.315, 1.283), (-0.006, 1.333), (0.302, 1.339), (0.611, 1.333), (0.919, 1.302),
      (1.228, 1.265), (1.536, 1.209), (1.845, 1.147), (X_GE, 1.105)]
zc_canopy = pchip(ZC)


def Zc(s):
    if s <= X_WS:
        return hood_z(s)
    if s <= X_GE:
        return zc_canopy(s)
    return 1.105 + (s - X_GE) / (XR - X_GE) * (1.03 - 1.105)        # rear deck


def NOSE(t):
    """Point on the front-face side edge: t=0 hood corner H0 ... t=1 silver lower edge."""
    return (XF + 0.02 * t, 0.66 + 0.02 * t, 0.50 - 0.17 * t)


def crown_fade(s):
    return smoothstep(XF, XF + 0.2, s) * (1.0 - smoothstep(XR - 0.2, XR, s))


def nose_w(s):
    return 1.0 - smoothstep(XF, X_T, s)


def nose_x(s, t):
    return s + nose_w(s) * (NOSE(t)[0] - XF)


def xstretch(s, x0, x1):
    """Lower rows start / end a little inboard of the nose and tail stations (receding faces)."""
    if s < -2.20:
        return x0 + (s - XF) * (-2.20 - x0) / (-2.20 - XF)
    if s > 2.20:
        return 2.20 + (s - 2.20) * (x1 - 2.20) / (XR - 2.20)
    return s


CANOPY_Y = pchip([(X_A0, 0.90), (-0.299, 0.705), (0.70, 0.62), (1.398, 0.573), (2.068, 0.35)])
RAIL_Z = pchip([(X_A0, A0P[1]), (-0.931, 1.045), (-0.475, 1.19), (-0.068, 1.277), (0.611, 1.298),
                (0.993, 1.255), (X_TIP, TIPP[1])])
BELT_Y = pchip([(X_A0, A0P[0]), (-0.765, 0.97), (-0.068, 0.955), (0.457, 0.93), (0.913, 0.89),
                (1.074, 0.82), (X_TIP, TIPP[0])])
BELT_Z = pchip([(X_A0, A0P[1]), (-0.765, 0.888), (-0.068, 0.944), (0.518, 1.012), (0.913, 1.055),
                (1.074, 1.104), (X_TIP, TIPP[1])])
# shoulder: fender crest over the front wheel, then the sharp shoulder crease — a straight line
# from the side marker to behind the doors (side view), level with the tail top at the back.
# It is the widest line of the body; the slab below tucks in slightly.
SH_NOSE_T = 0.06              # shoulder leaves the front-face edge just under the hood corner
SH_PLAN = pchip([(XF, NOSE(SH_NOSE_T)[1]), (-2.2667, 0.7475), (-2.1583, 0.8338), (X_T, 0.92), (-1.96, 0.99),
                 (-1.86, 1.025), (-1.75, 1.045), (-1.65, 1.06), (-1.342, 1.075), (-0.9, 1.09), (-0.5, 1.095),
                 (2.00, 1.095)])
SH_Z = pchip([(XF, NOSE(SH_NOSE_T)[2]), (-2.2667, 0.5232), (-2.1583, 0.5566), (X_T, 0.59), (-1.96, 0.655), (-1.86, 0.72), (-1.65, 0.80),
              (-1.487, 0.825), (-1.20, 0.805), (-0.907, 0.788), (-0.44, 0.834), (0.30, 0.907),
              (0.92, 0.968), (1.54, 1.012), (2.20, 1.028), (XR, 1.03)])
MAXW_PLAN = pchip([(XF, NOSE(0.75)[1]), (-2.2667, 0.772), (-2.1583, 0.869), (X_T, 0.965), (-1.96, 1.035),
                   (-1.86, 1.072), (-1.75, 1.088), (-1.65, 1.095), (-1.342, 1.10), (2.07, 1.10)])
LO_PLAN = pchip([(XF, 0.68), (-2.2667, 0.77), (-2.1583, 0.86), (X_T, 0.95), (-1.96, 1.02), (-1.86, 1.055),
                 (-1.75, 1.068), (-1.65, 1.07), (2.14, 1.07)])
LO_Z = pchip([(XF, 0.33), (X_T, 0.32), (-1.95, 0.30), (-0.765, 0.31), (0.08, 0.333), (0.30, 0.352),
              (1.20, 0.413), (2.03, 0.66), (XR, 0.84)])
RK_Y = pchip([(-2.34, 0.74), (X_T, 0.86), (X_FF, 0.97), (-1.6, 0.99), (1.9, 0.99), (2.05, 0.95), (2.29, 0.85)])
RK_Z = pchip([(-2.34, 0.24), (-1.95, 0.19), (-1.6, 0.12), (1.9, 0.12), (2.05, 0.22), (2.29, 0.22)])


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
    drop = 0.022 * smoothstep(X_A0, -0.95, s) * (1.0 - smoothstep(1.0, X_GE, s))
    if s <= X_GE:
        return (s, CANOPY_Y(s), Zc(s) - drop)
    t = (s - X_GE) / (XR - X_GE)
    return (s, CANOPY_Y(X_GE) + t * 0.04, Zc(X_GE) * (1 - t) + 1.03 * t)


RAIL_OFF = pchip([(X_A0, A0P[0] - 0.90), (0.70, 0.04), (X_TIP, TIPP[0] - CANOPY_Y(X_TIP))])


def cpillar_point(s, f, p_tip):
    """Behind the side-glass tip: point at fraction f across the glass-edge -> shoulder section,
    on a light crown, blended in from the glass tip over 0.6 m."""
    a, b = Vector(L1(s)), Vector(L4(s))
    c = b - a
    q = a.lerp(b, f)
    n = Vector((0.0, -c.z, c.y)).normalized()
    if n.z < 0:
        n = -n
    q += n * (0.015 * 4 * f * (1 - f) * c.length * crown_fade(s))
    w = smoothstep(X_TIP, X_TIP + 0.6, s)
    return (s, p_tip[0] * (1 - w) + q.y * w, p_tip[1] * (1 - w) + q.z * w)


def L2(s):  # lamp-triangle outer edge -> fender ridge -> roof rail outer edge -> C-pillar row
    if s <= X_T:   # straight lamp-triangle edge
        n = NOSE(0.03)
        u = (s - XF) / (X_T - XF)
        return tuple(n[k] + u * (T_PT[k] - n[k]) for k in range(3))
    if s <= X_A0:  # straight fender ridge T -> A-pillar foot, in the fender plane
        y = lin(s, [(X_T, T_PT[1]), (X_A0, A0P[0])])
        return (s, y, fender_z(s, y))
    if s <= X_TIP:
        return (s, L1(s)[1] + RAIL_OFF(s), RAIL_Z(s))
    return cpillar_point(s, 0.30, TIPP)


def L3(s):  # fender mid row -> belt line (side-glass bottom) -> C-pillar row
    if s <= X_A0:
        a, b = Vector(L2(s)), Vector(L4(s))
        f = 0.35 * (1.0 - smoothstep(-1.65, X_A0, s))
        q = a.lerp(b, f)
        c = b - a
        n = Vector((0.0, -c.z, c.y)).normalized()
        if n.z < 0:
            n = -n
        q += n * (0.03 * 4 * f * (1 - f) * c.length * smoothstep(-2.05, -1.90, s))   # round over the wheel only
        return (q.x, q.y, q.z)
    if s <= X_TIP:
        return (s, BELT_Y(s), BELT_Z(s))
    return cpillar_point(s, 0.62, TIPP)


TAN_CH = (SH_PLAN(X_CH) - 0.88) / (XR - X_CH)


def chamfer_y(s, z):
    """Tail-corner chamfer: one plane swept inward off the slab's section line at X_CH."""
    z4, z6 = SH_Z(X_CH), LO_Z(X_CH)
    y4, y6 = SH_PLAN(X_CH), LO_PLAN(X_CH)
    return y4 + (z - z4) * (y6 - y4) / (z6 - z4) - (s - X_CH) * TAN_CH


# nose-corner side facet ahead of the front arch: one plane through the front-face edge and the
# sill line where it meets the arch column
_NA, _NB = Vector(NOSE(SH_NOSE_T)), Vector(NOSE(1.0))
_NQ = Vector((-1.96, LO_PLAN(-1.96), LO_Z(-1.96)))
_NN = (_NB - _NA).cross(_NQ - _NA)


def nose_plane_y(x, z):
    return _NA.y - (_NN.x * (x - _NA.x) + _NN.z * (z - _NA.z)) / _NN.y


def side_y(s, x, z, plan):
    """Flank Y: nose-corner plane ahead of the front arch, easing into the plan line over the
    front wheel; tail chamfer plane behind X_CH."""
    if s >= X_CH:
        return chamfer_y(s, z)
    w = smoothstep(-1.96, -1.60, s)
    return nose_plane_y(x, z) * (1 - w) + plan(s) * w


def L4(s):  # shoulder
    x, z = nose_x(s, SH_NOSE_T), SH_Z(s)
    return (x, side_y(s, x, z, SH_PLAN), z)


def L6(s):  # silver lower edge (body / black cladding split)
    x, z = nose_x(s, 1.0), LO_Z(s)
    return (x, side_y(s, x, z, LO_PLAN), z)


def bulge_w(s):
    """Where the flank may stay full: over the wheels. Ahead of the front wheel, between the
    wheels and behind the rear wheel it is flat."""
    front = smoothstep(-1.96, -1.60, s) * (1.0 - smoothstep(-1.30, -0.90, s))
    rear = smoothstep(0.80, 1.30, s) * (1.0 - smoothstep(1.85, X_CH, s))
    return max(front, rear)


def L5(s):  # mid row of the body side: on the shoulder -> sill chord, fuller over the wheels
    flat = (Vector(L4(s)) + Vector(L6(s))) * 0.5
    w = bulge_w(s)
    if w <= 0.0:
        return tuple(flat)
    full = Vector((s, smin(MAXW_PLAN(s), 0.92 + (XR - s) * 0.50, 0.06), 0.5 * (SH_Z(s) + LO_Z(s))))
    return tuple(flat.lerp(full, w))


def L6b(s):  # small inward step into the black rocker
    x, y, z = L6(s)
    return (x, y - 0.035, z - 0.012)


def L7(s):  # rocker / splitter / diffuser lower outer edge
    x = xstretch(s, -2.34, 2.29)
    return (x, RK_Y(x), RK_Z(x))


def L8(s):  # floor centre
    x, _, z = L7(s)
    return (x, 0.0, z)


# ------------------------------------------------------------- cage rows
ROWS = ['L0', 'C1', 'C2', 'L1', 'L2', 'L3', 'C34', 'L4', 'C45', 'L5', 'C56', 'L6', 'L6b', 'L7',
        'F1', 'F2', 'L8']
R = {n: k for k, n in enumerate(ROWS)}
LINE_FN = {'L0': L0, 'L1': L1, 'L2': L2, 'L3': L3, 'L4': L4, 'L5': L5, 'L6': L6, 'L6b': L6b,
           'L7': L7, 'L8': L8}


def crowned(a, b, k):
    """Chord midpoint pushed outward (in the station plane) by k * chord length."""
    mid = (a + b) * 0.5
    c = b - a
    n = Vector((0.0, -c.z, c.y))
    if n.length < 1e-9:
        return mid
    n.normalize()
    if n.dot(Vector((0.0, mid.y, mid.z - 0.55))) < 0:
        n = -n
    return mid + n * (k * c.length)


def quad_mids(a, b, c):
    """Points halfway a-b and b-c on the parabola through a, b, c (chord-length parameter)."""
    t1 = max((b - a).length, 1e-6)
    t2 = t1 + max((c - b).length, 1e-6)

    def P(t):
        return (a * ((t - t1) * (t - t2) / (t1 * t2))
                + b * (t * (t - t2) / (t1 * (t1 - t2)))
                + c * (t * (t - t1) / (t2 * (t2 - t1))))
    return P(0.5 * t1), P(0.5 * (t1 + t2))


def section(s):
    P = {n: Vector(fn(s)) for n, fn in LINE_FN.items()}
    x7, _, z7 = P['L7']
    P['F1'] = Vector((x7, 0.68, z7))
    P['F2'] = Vector((x7, 0.34, z7))
    a, b = P['L0'], P['L1']
    for name, t in (('C1', 1 / 3), ('C2', 2 / 3)):          # roof / hood crown: parabolic fall-off
        P[name] = Vector((a.x + (b.x - a.x) * t, b.y * t, a.z - (a.z - b.z) * t * t))
    front = smoothstep(XF, -1.85, s)        # leading face stays flat
    # fender over the front wheel is rounded; the ledge under the glass and the haunch top
    # are near-flat facets with only a trace of crown
    c34 = 0.008 + 0.027 * smoothstep(-2.05, -1.90, s) * (1.0 - smoothstep(-1.30, -0.95, s))
    # the ledge twists where the glass line kicks up: a little extra fullness keeps it convex
    c34 += 0.04 * smoothstep(0.75, 1.10, s) * (1.0 - smoothstep(1.20, 1.60, s))
    P['C34'] = crowned(P['L3'], P['L4'], c34 * crown_fade(s) * front)
    q45, q56 = quad_mids(P['L4'], P['L5'], P['L6'])
    P['C45'] = (P['L4'] + P['L5']) * 0.5 * (1 - front) + q45 * front
    P['C56'] = (P['L5'] + P['L6']) * 0.5 * (1 - front) + q56 * front
    return P


ARCH_COLS = ((-1.96, -0.995), (1.12, X_CH))     # cage columns either side of each arch
FEATURE_X = [XF, X_T, ARCH_COLS[0][0], X_WS, X_A0, ARCH_COLS[0][1], ARCH_COLS[1][0], X_TIP, X_GE,
             ARCH_COLS[1][1], XR]
STATIONS = []
for _a, _b in zip(FEATURE_X[:-1], FEATURE_X[1:]):
    _n = max(1, int(round((_b - _a) / 0.10)))
    STATIONS += [_a + (_b - _a) * k / _n for k in range(_n)]
STATIONS.append(XR)
ARCHES = [  # (wheel x, first station, last station, top row) — the cage around each arch
    (WHEEL_X[0], ARCH_COLS[0][0], ARCH_COLS[0][1], 'L3'),
    (WHEEL_X[1], ARCH_COLS[1][0], ARCH_COLS[1][1], 'L4'),
]


# Hard edges come in two kinds. Bevelled (a ~4 mm round after subdivision) is used only on edge
# chains that close on themselves or end where other bevelled edges meet — a bevel that stops
# mid-surface leaves a spike. Every other hard edge is a full crease with split normals.
HARD = 1.0          # bevel weight
SHARP = -1.0        # full crease + sharp shading
def row_edge(j, xm):
    """(bevel weight, crease) for the cage edge of row j between two stations."""
    n = ROWS[j]
    if n in ('L1', 'L2') and xm < X_T:
        return HARD, 0.0       # head-lamp triangle outline
    if n == 'L1':
        return SHARP, 0.0      # hood edge, windscreen base diagonal, canopy glass edge, deck edge
    if n == 'L2' and xm < X_TIP:
        return SHARP, 0.0      # fender ridge, side-glass top
    if n == 'L3' and X_A0 < xm < X_TIP:
        return SHARP, 0.0      # side-glass bottom (belt)
    if n == 'L6':
        return HARD, 0.0       # silver / black edge
    if n in ('L6b', 'L7'):
        return SHARP, 0.0      # step into the black rocker, rocker edge (too close to L6 to bevel)
    if n == 'L4':
        # sharp shoulder crease, except for a soft crest over the front wheel
        if ARCH_COLS[0][0] < xm < ARCH_COLS[0][1]:
            return 0.0, 0.35
        if X_T < xm < ARCH_COLS[0][0] or ARCH_COLS[0][1] < xm < ARCH_COLS[0][1] + 0.1:
            return 0.0, 0.7    # last segment either side of the front arch: crease fades out
        return SHARP, 0.0
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
def build_body():
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
    for wx, sa, sb, top in ARCHES:
        ia, ib, jt = idx[sa], idx[sb], R[top]
        arch_ix.append((wx, ia, ib, jt))
        for i in range(ia + 1, ib):
            for j in range(jt + 1, R['L7'] + 1):
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

    # longitudinal strips
    for i in range(ns - 1):
        xm = 0.5 * (st[i] + st[i + 1])
        for j in range(nr - 1):
            face((V[i][j], V[i][j + 1], V[i + 1][j + 1], V[i + 1][j]), strip_material(j, xm))
    for i in range(ns - 1):
        xm = 0.5 * (st[i] + st[i + 1])
        for j in range(nr):
            bw, cw = row_edge(j, xm)
            crease(V[i][j], V[i + 1][j], cw, bw)

    # transverse hard edges: windscreen base, canopy rear edge, lamp triangle rear edge,
    # fender facet / roof rail break at the A-pillar foot
    for s, j0, j1, kind in ((X_WS, 0, R['L1'], SHARP), (X_GE, 0, R['L1'], SHARP),
                            (X_T, R['L1'], R['L2'], HARD), (X_A0, R['L1'], R['L2'], SHARP)):
        i = idx[s]
        for j in range(j0, j1):
            crease(V[i][j], V[i][j + 1], 0.0, kind)
    i = idx[X_CH]                      # tail-corner chamfer crease
    for j in range(R['L4'], R['L6']):
        crease(V[i][j], V[i][j + 1], 0.0, SHARP)

    arch_loops = []
    for wx, ia, ib, jt in arch_ix:
        arch_loops.append(build_arch_patch(bm, V, st, wx, ia, ib, jt, face, hard,
                                           lambda a, b: crease(a, b, 0.0, SHARP)))

    build_caps(bm, V, face, hard)

    # glass corners stay pointed (crease-rule corners)
    for v in (V[idx[X_A0]][R['L2']], V[idx[X_TIP]][R['L2']], V[idx[X_A0]][R['L1']],
              V[idx[X_GE]][R['L1']], V[idx[X_WS]][R['L1']]):
        v[VL] = 1.0

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
    return ob, arch_loops


def flank_y(x, z, top):
    """Body-side surface: Y as a smooth function of Z through the section rows at station x."""
    P = section(x)
    names = ROWS[R[top]:R['L7'] + 1]
    pts = sorted((P[n].z, P[n].y) for n in names)
    clean = [pts[0]]
    for p in pts[1:]:
        if p[0] - clean[-1][0] > 1e-4:
            clean.append(p)
    return pchip(clean)(z)


def build_arch_patch(bm, V, st, wx, ia, ib, jt, face, hard, sharp):
    """Radial ring patch between the cage boundary (outer U) and the arch circle, plus flange."""
    jb = R['L7']
    wz, RR = WHEEL_Z, ARCH_R
    top = ROWS[jt]
    U = ([(ia, j) for j in range(jb, jt - 1, -1)] + [(i, jt) for i in range(ia + 1, ib)]
         + [(ib, j) for j in range(jt, jb + 1)])
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
        for _ in range(60):
            m = 0.5 * (a + b)
            if (g(m) > 0) == (g(a) > 0):
                a = m
            else:
                b = m
        x = 0.5 * (a + b)
        return x, fn(x)[2]

    # pinned spokes: silver/black rows end exactly where they meet the circle; U corners radial
    nside = jb - jt + 1
    pins = {}
    row_of = {}
    for k, name in ((0, 'L7'), (1, 'L6b'), (2, 'L6')):
        for kk, x_out in ((k, oxz[0][0]), (Mn - 1 - k, oxz[-1][0])):
            x, z = row_hit(LINE_FN[name], x_out)
            pins[kk] = ang(x, z)
            row_of[kk] = LINE_FN[name]
    for kk in (nside - 1, Mn - nside):
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
    arch_pts = []
    for k in range(Mn):
        th = theta[k]
        c, s = math.cos(th), math.sin(th)
        xa, za = wx + RR * c, wz + RR * s
        xo, zo = oxz[k]
        if k in row_of:
            fn = row_of[k]
            xs = xa + math.copysign(D_SUP, xo - xa)
            zs = fn(xs)[2]
            xm = 0.5 * (xo + xs)
            zm = fn(xm)[2]
        else:
            xs, zs = xa + D_SUP * c, za + D_SUP * s
            xm, zm = 0.5 * (xo + xs), 0.5 * (zo + zs)
        ya = flank_y(xa, za, top)
        rings[1].append(bm.verts.new((xm, flank_y(xm, zm, top), zm)))
        rings[2].append(bm.verts.new((xs, flank_y(xs, zs, top), zs)))
        rings[3].append(bm.verts.new((xa, ya, za)))
        arch_pts.append((xa, ya, za, th))
    # turned-in flange; depth measured from the innermost nearby lip point so it never folds
    # back over the sill step
    for k in range(Mn):
        xa, ya, za, th = arch_pts[k]
        c, s = math.cos(th), math.sin(th)
        yr = min(p[1] for p in arch_pts[max(0, k - 2):k + 3])
        rings[4].append(bm.verts.new((xa + 0.004 * c, yr - 0.014, za + 0.004 * s)))
        rings[5].append(bm.verts.new((xa + 0.010 * c, yr - 0.045, za + 0.010 * s)))
    for r in range(5):
        for k in range(Mn - 1):
            m = MAT_BLACK if (k < 2 or k >= Mn - 3) else MAT_PAINT
            face((rings[r][k], rings[r][k + 1], rings[r + 1][k + 1], rings[r + 1][k]), m)
    for k in (0, 1, 2, Mn - 3, Mn - 2, Mn - 1):   # L7 / L6b / L6 edges run on into the arch ...
        for r in range(3):
            (hard if k in (2, Mn - 3) else sharp)(rings[r][k], rings[r + 1][k])
    for k in range(Mn - 1):                       # ... and end on the bevelled arch lip
        hard(rings[3][k], rings[3][k + 1])
    return arch_pts


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
            for xa, ya, za, th in pts:
                c, s = math.cos(th), math.sin(th)
                rx, rz = xa + 0.012 * c, za + 0.012 * s
                outer.append(bm.verts.new((rx, sgn * (ya - 0.02), rz)))
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
        ss = np.linspace(X_CH + 0.01, XR - 0.01, 30)
        pts = [(s, sgn * 1.4, L6(s)[2] + 0.018) for s in ss]
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
print("T_PT", tuple(round(v, 4) for v in T_PT), "ZC_A0", round(fender_z(X_A0, 0.90), 4))
print("BODY cage verts", len(me.vertices), "faces", len(me.polygons), "| subdivided faces", len(ev.polygons))
path = os.path.join(OUT, "wedge_car.blend")
bpy.ops.wm.save_as_mainfile(filepath=path)
print("SAVED", path)
