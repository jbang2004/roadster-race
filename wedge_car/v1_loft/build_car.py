"""
Wedge EV concept — Blender rebuild from the four-view reference sheet.

Run:  blender -b --python build_car.py -- <out_dir>
Writes <out_dir>/wedge_car.blend

Units: metres, 1:1.  Axes: X = length (front at -X), Y = width, Z = up, ground at Z = 0.
Overall: L 4.75  W 2.20  H 1.34  wheelbase 3.10  tyre Ø 0.80

The body is lofted from longitudinal character lines (L0..L8) measured off the
side / top / front views; every cross-section joins the same lines in order, so
facets and creases run exactly where the reference draws them.
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


# ------------------------------------------------------- key stations (X)
XF, XR = -2.375, 2.375        # nose / tail
X_T = -2.05                   # head-lamp triangle apex T / hood point B
X_FF = -1.88                  # front-fender leading face reaches full width
X_WS = -1.55                  # windscreen base (centre)
X_A0 = -1.40                  # A-pillar foot: rail + side glass start
X_TIP = 1.197                 # side-glass rear tip
X_GE = 2.03                   # end of the glass canopy
WHEEL_X = (-1.487, 1.61)
WHEEL_Z, TYRE_R, ARCH_R = 0.39, 0.39, 0.4225   # ARCH_R = arch radius on the body flank

# roof / windscreen centre-line (side-view silhouette)
ZC = [(X_WS, 0.84), (X_A0, 0.905), (-1.24, 0.969), (-0.931, 1.086), (-0.623, 1.191),
      (-0.315, 1.283), (-0.006, 1.333), (0.302, 1.339), (0.611, 1.333), (0.919, 1.302),
      (1.228, 1.265), (1.536, 1.209), (1.845, 1.147), (X_GE, 1.105)]
zc_canopy = pchip(ZC)


def Zc(s):
    if s <= X_WS:
        return 0.50 + (s - XF) / (X_WS - XF) * (0.84 - 0.50)        # flat wedge hood
    if s <= X_GE:
        return zc_canopy(s)
    return 1.105 + (s - X_GE) / (XR - X_GE) * (1.03 - 1.105)        # rear deck


CANOPY_Y = [(X_A0, 0.90), (-0.299, 0.705), (0.70, 0.62), (1.398, 0.573), (2.068, 0.35)]
RIDGE_Z = pchip([(X_T, 0.72), (-1.857, 0.80), (-1.672, 0.862), (-1.548, 0.888), (X_A0, 0.903)])
RAIL_Z = pchip([(X_A0, 0.903), (-0.931, 1.045), (-0.475, 1.19), (-0.068, 1.277), (0.611, 1.298),
                (0.993, 1.255), (X_TIP, 1.19)])
BELT_Y = pchip([(X_A0, 0.94), (-0.765, 0.97), (-0.068, 0.955), (0.457, 0.93), (0.913, 0.89),
                (1.074, 0.82), (X_TIP, 0.66)])
BELT_Z = pchip([(X_A0, 0.894), (-0.765, 0.888), (-0.068, 0.944), (0.518, 1.012), (0.913, 1.055),
                (1.074, 1.104), (X_TIP, 1.19)])
SH_Y = pchip([(X_T, 0.84), (X_FF, 1.04), (-1.65, 1.06), (-1.342, 1.07), (-0.9, 1.08), (2.00, 1.08)])
SH_Z = pchip([(X_T, 0.59), (X_FF, 0.66), (-1.65, 0.75), (-1.487, 0.785), (-1.30, 0.772),
              (-1.12, 0.756), (-0.907, 0.753), (-0.068, 0.839), (0.457, 0.894), (0.913, 0.968), (1.283, 1.055),
              (2.00, 1.096)])
MAXW_Y = pchip([(X_T, 0.88), (X_FF, 1.085), (-1.65, 1.095), (-1.342, 1.10), (2.07, 1.10)])
LO_Y = [(-2.355, 0.68), (X_T, 0.90), (X_FF, 1.07), (-1.65, 1.07), (2.14, 1.07), (XR, 0.88)]
LO_Z = [(-2.355, 0.33), (X_T, 0.32), (-1.95, 0.30), (-0.765, 0.31), (0.08, 0.333), (0.30, 0.352), (1.20, 0.413),
        (2.03, 0.66), (XR, 0.84)]
RK_Y = [(-2.34, 0.74), (X_T, 0.86), (X_FF, 0.97), (-1.6, 0.99), (1.9, 0.99), (2.05, 0.95), (2.29, 0.85)]
RK_Z = [(-2.34, 0.24), (-1.95, 0.19), (-1.6, 0.12), (1.9, 0.12), (2.05, 0.22), (2.29, 0.22)]
H0 = (XF, 0.66, 0.50)        # hood front corner


# ---------------------------------------------------------- character lines
def L0(s):  # centre line
    return (s, 0.0, Zc(s))


def L1(s):  # hood edge -> windscreen diagonal -> canopy glass edge -> deck
    if s <= XF + 1e-9:
        return H0
    if s <= X_T:
        return (s, lin(s, [(XF, 0.66), (X_T, 0.60)]), Zc(s))
    if s <= X_WS:
        return (s, lin(s, [(X_T, 0.60), (X_WS, 0.53)]), Zc(s))
    if s <= X_A0:
        t = (s - X_WS) / (X_A0 - X_WS)
        return (s, 0.53 + t * (0.90 - 0.53), 0.84 + t * (Zc(X_A0) - 0.84))
    if s <= X_GE:
        return (s, lin(s, CANOPY_Y), Zc(s) - lin(s, [(X_A0, 0.0), (-1.0, 0.012)]))
    t = (s - X_GE) / (XR - X_GE)
    y_ge = lin(X_GE, CANOPY_Y)
    return (s, y_ge + t * 0.04, (Zc(X_GE) - 0.012) * (1 - t) + 1.03 * t)


def L2(s):  # fender ridge -> roof rail outer edge -> C-pillar
    if s <= XF + 1e-9:
        return H0
    if s <= X_T:
        return (s, lin(s, [(XF, 0.66), (X_T, 0.78)]), lin(s, [(XF, 0.50), (X_T, 0.72)]))
    if s <= X_A0:
        return (s, lin(s, [(X_T, 0.78), (X_A0, 0.92)]), RIDGE_Z(s))
    if s <= X_TIP:
        return (s, L1(s)[1] + lin(s, [(X_A0, 0.02), (0.70, 0.04), (X_TIP, 0.08)]), RAIL_Z(s))
    return (s, lin(s, [(X_TIP, 0.66), (1.6, 0.66), (X_GE, 0.64), (XR, 0.62)]),
            lin(s, [(X_TIP, 1.19), (1.6, 1.16), (X_GE, 1.10), (XR, 1.03)]))


def L3(s):  # fender mid-facet -> belt line (side-glass bottom) -> haunch
    if s <= XF + 1e-9:
        return H0
    if s <= X_T:
        return (s, lin(s, [(XF, 0.66), (X_T, 0.80)]), lin(s, [(XF, 0.50), (X_T, 0.655)]))
    if s <= X_A0:
        return (s, lin(s, [(X_T, 0.80), (-1.65, 0.90), (X_A0, 0.94)]),
                lin(s, [(X_T, 0.655), (-1.65, 0.80), (X_A0, 0.894)]))
    if s <= X_TIP:
        return (s, BELT_Y(s), BELT_Z(s))
    return (s, lin(s, [(X_TIP, 0.66), (1.6, 0.86), (X_GE, 0.90), (XR, 0.80)]),
            lin(s, [(X_TIP, 1.19), (1.6, 1.14), (X_GE, 1.10), (XR, 1.03)]))


def L4(s):  # shoulder crease
    if s <= XF + 1e-9:
        return H0
    if s <= X_T:
        return (s, lin(s, [(XF, 0.66), (X_T, 0.84)]), lin(s, [(XF, 0.50), (X_T, 0.59)]))
    if s <= 2.00:
        return (s, SH_Y(s), SH_Z(s))
    return (s, lin(s, [(2.00, 1.08), (XR, 0.90)]), lin(s, [(2.00, 1.096), (XR, 1.03)]))


def L6(s):  # silver lower edge (body / black cladding split)
    x = max(s, -2.355)
    return (x, lin(x, LO_Y), lin(x, LO_Z))


def L5(s):  # widest point of the body side
    x = max(s, -2.36)
    if x <= X_T:
        y = lin(x, [(-2.36, 0.67), (X_T, 0.88)])
    elif x <= 2.07:
        y = MAXW_Y(x)
    else:
        y = lin(x, [(2.07, 1.10), (XR, 0.90)])
    z = 0.5 * (L4(x)[2] + L6(x)[2])
    return (x, y, z)


def L6b(s):  # small inward step into the black rocker
    x = max(s, -2.35)
    return (x, lin(x, LO_Y) - 0.035, lin(x, LO_Z) - 0.012)


def L7(s):  # rocker / splitter / diffuser lower outer edge
    x = min(max(s, -2.34), 2.29)
    return (x, lin(x, RK_Y), lin(x, RK_Z))


def L8(s):  # floor centre
    x, _, z = L7(s)
    return (x, 0.0, z)


LINES = [L0, L1, L2, L3, L4, L5, L6, L6b, L7, L8]


# ------------------------------------------------------------- body loft
def build_body():
    keys = [XF, -2.36, -2.355, -2.35, -2.34, -2.2, X_T, X_FF, -1.857, -1.672, -1.65, X_WS, X_A0,
            -1.342, -1.178, -0.931, -0.765, -0.475, -0.068, 0.611, 0.993, 1.074, X_TIP, 1.6, 1.98,
            X_GE, 2.0, 2.07, 2.14, 2.29, XR]
    uni = np.arange(XF, XR + 1e-9, 0.02)
    st = sorted(set(keys) | {float(u) for u in uni if min(abs(u - k) for k in keys) > 0.007})

    bm = bmesh.new()
    rings = []
    for s in st:
        half = [LINES[k](s) for k in range(10)]
        right = [bm.verts.new((p[0], p[1], p[2])) for p in half]
        left = [bm.verts.new((p[0], -p[1], p[2])) for p in half[1:9]]
        # ring order: L0, L1R..L7R, L8, L7L..L1L  (18 verts)
        rings.append(right + left[::-1])

    def strip_mat(t, xm):
        if t == 0:
            return 1 if X_WS <= xm <= X_GE else 0
        if t == 2:
            return 1 if X_A0 <= xm <= X_TIP else 0
        if t in (6, 7, 8):
            return 2
        return 0

    n = 18
    for i in range(len(st) - 1):
        xm = 0.5 * (st[i] + st[i + 1])
        for j in range(n):
            a, b = rings[i][j], rings[i][(j + 1) % n]
            c, d = rings[i + 1][(j + 1) % n], rings[i + 1][j]
            t = j if j <= 8 else 17 - j
            f = bm.faces.new((a, b, c, d))
            f.material_index = strip_mat(t, xm)

    # front cap (black nose face) and rear caps (silver tail panel / black diffuser)
    r0 = rings[0]
    f = bm.faces.new(r0)
    f.material_index = 2
    rl = rings[-1]
    up = [rl[i] for i in (0, 1, 2, 3, 4, 5, 6, 12, 13, 14, 15, 16, 17)]
    lo = [rl[6], rl[7], rl[8], rl[9], rl[10], rl[11], rl[12]]
    bm.faces.new(up).material_index = 0
    bm.faces.new(lo).material_index = 2

    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    bmesh.ops.dissolve_degenerate(bm, dist=1e-6, edges=bm.edges)
    caps = [f for f in bm.faces if len(f.verts) > 4]
    bmesh.ops.triangulate(bm, faces=caps)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

    me = bpy.data.meshes.new("Body")
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new("Body", me)
    scene.collection.objects.link(ob)
    for k in ('paint', 'glass', 'black', 'well'):
        me.materials.append(M[k])
    return ob


def make_cyl(bm, center, radius, y0, y1, segs=96, radius_top=None):
    # create_cone puts radius1 at local -Z; after the +90deg X rotation that end sits at y1
    ret = bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=segs,
                                radius1=radius, radius2=radius if radius_top is None else radius_top,
                                depth=(y1 - y0))
    rot = Matrix.Rotation(math.radians(90), 4, 'X')
    bmesh.ops.transform(bm, matrix=Matrix.Translation((center[0], 0.5 * (y0 + y1), center[1])) @ rot,
                        verts=ret['verts'])
    return ret['verts']


def cut_wheel_arches(body):
    bm = bmesh.new()
    # tapered cutter: full arch radius on the flank, shrinking inboard so the arch never
    # breaks through the sloping fender tops (keeps the wheel tub closed from above)
    def r_at(y):
        return ARCH_R + (abs(y) - 1.07) * 0.5
    for wx in WHEEL_X:
        for sgn in (1, -1):
            if sgn > 0:
                make_cyl(bm, (wx, WHEEL_Z), r_at(1.40), 0.70, 1.40, radius_top=r_at(0.70))
            else:
                make_cyl(bm, (wx, WHEEL_Z), r_at(0.70), -1.40, -0.70, radius_top=r_at(1.40))
    me = bpy.data.meshes.new("ArchCutter")
    bm.to_mesh(me)
    bm.free()
    cut = bpy.data.objects.new("ArchCutter", me)
    scene.collection.objects.link(cut)
    me.materials.append(M['well'])
    mod = body.modifiers.new("Arches", 'BOOLEAN')
    mod.operation = 'DIFFERENCE'
    mod.solver = 'EXACT'
    mod.object = cut
    try:
        mod.material_mode = 'TRANSFER'
    except Exception:
        pass
    dg = bpy.context.evaluated_depsgraph_get()
    newme = bpy.data.meshes.new_from_object(body.evaluated_get(dg))
    old = body.data
    body.modifiers.clear()
    body.data = newme
    newme.name = "Body"
    bpy.data.meshes.remove(old)
    bpy.data.objects.remove(cut)
    bpy.data.meshes.remove(me)


def finish_shading(ob, angle=24.0):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    lim = math.radians(angle)
    for f in bm.faces:
        f.smooth = True
    for e in bm.edges:
        lf = e.link_faces
        if len(lf) != 2:
            e.smooth = False
            continue
        if lf[0].material_index != lf[1].material_index or e.calc_face_angle(0.0) > lim:
            e.smooth = False
    bm.to_mesh(ob.data)
    bm.free()


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


def proj_line(surf, pts3, d, step=0.008, off=0.0012):
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
        # rear-corner crease into the tail chamfer
        [(2.0, 1.094), (2.07, 0.88), (2.14, 0.717)],
        # side-glass seams: A-pillar double line, B-pillar double line
        [(-0.765, 0.889), (-0.352, 1.225)],
        [(-0.654, 0.889), (-0.253, 1.238)],
        [(0.518, 1.27), (0.333, 1.0)],
        [(0.62, 1.282), (0.44, 1.02)],
    ]
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
        ss = np.linspace(X_A0, X_TIP, 140)
        up = [(s, sgn * 1.4, L2(s)[2] - 0.004) for s in ss]
        lo = [(s, sgn * 1.4, L3(s)[2] + 0.004) for s in ss]
        side.append(proj_line(surf, up, (0, -sgn, 0)))
        side.append(proj_line(surf, lo, (0, -sgn, 0)))

    curve_obj("PanelLines_Side", side, 0.0016, M['line'])
    curve_obj("PanelLines_Top", top, 0.0016, M['line'])


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
        ss = np.linspace(2.09, XR - 0.01, 30)
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
body = build_body()
cut_wheel_arches(body)
finish_shading(body)
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
print("BODY verts", len(me.vertices), "faces", len(me.polygons))
path = os.path.join(OUT, "wedge_car.blend")
bpy.ops.wm.save_as_mainfile(filepath=path)
print("SAVED", path)
