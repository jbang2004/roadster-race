"""
R2: the front end of the 2026 Roadster, built on the new shell (shell.py).  Everything here is a thin detail laid ON the subdivided body (rays cast onto
it, small offsets), except the intake pocket which is cut into the body itself (shell.cut_intake).

  build_front(cast, mk, level, mat_of=None) -> [objects]       level 0 = hi, 1 = lod1 (fewer parts, lamps merged), 2 = lod2 (bar + splitter only)
      cast(origin, direction, off) -> (point, normal) | (None, None)      ray cast onto the body (build_game_car.Surf.cast)
      mk(bm, name, material_name, smooth) -> object                        object factory (build_game_car.obj_from_bm)

Parts (photos 016 / 014 / 005 / 003, see ROADSTER_DESIGN.md "front end"):
  HeadDRL   the light bar: ONE continuous strip 1.7 cm tall along the hood's leading edge, corner to corner (its ends droop to 2.6 cm)
  GlossBlack the black band under the bar (10 cm, on the raked face), with the slim HeadLens strips on it
  the lower intake: pocket cut into the face (shell.cut_intake) with five louvre blades + three ribs inside (GlossBlack / Trim)
  Carbon    the splitter blade: 5 cm proud across the middle, kinked back towards the corners
  PanelGap  the L5 seam (hood | fender top), the corner flap outline, the frunk seam, the cowl line, the door front cut
  side-marker assembly behind the top of the front arch: red reflector, GlossBlack blade with the amber SideMarker lamp, round camera
"""
import bpy, bmesh, math
from mathutils import Vector
import shell as S


def sstep(a, b, x):
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3.0 - 2.0 * t)


# ----------------------------------------------------------------------------- the front geometry (shared with the shell)
def lead(y):
    """(x, z) of the hood's leading edge at lateral position y: the hood plane meets the (bowed, raked) face"""
    y = abs(y)
    xx = S.NOSE_X + S.FACE_F['bow'] * (y / 0.67) ** 2
    for _ in range(8):
        zz = S.hood_z(xx, y)
        xx = S.front_x(y, zz)
    return xx, S.hood_z(xx, y)


YB = 0.666                      # the bar / band stop this far from the centre line (the corner edge of the face is at 0.67)
BAR_H = 0.015                   # bar height (1.5 - 2 cm), the ends droop to BAR_H + BAR_DROOP
BAR_DROOP = 0.007
BAND_H = 0.100                  # the black band under the bar
SPL_Z = (0.198, 0.222)          # splitter blade: bottom / top at the root
SPL_P = 0.050                   # splitter protrusion (m) across the middle
SPL_KINK = 0.40                 # |y| where the blade kinks back towards the corners

# the side-marker assembly (left side shown as x, z in the car frame: x aft): the arch edge crosses z = 0.735 at x -1.255, the door front cut is x = -1.0
MK_TIP = (-1.340, 0.778)        # the reflector's tip: on the arch circle, 8 cm under the crest of L1
MK_END = (-1.000, 0.735)        # the top edge ends at the door cut, where the rear L1 segment starts
MK_BLADE = -1.185               # the blade starts here (reflector in front of it)
MK_H = 0.048                    # blade height
DOOR_X = -1.0


class Mesh:
    def __init__(self):
        self.bm = bmesh.new()

    def v(self, p):
        return self.bm.verts.new((p[0], p[1], p[2]))

    def face(self, vs, want=None):
        u = []
        for v in vs:
            if v not in u:
                u.append(v)
        if len(u) < 3:
            return None
        try:
            f = self.bm.faces.new(u)
        except ValueError:
            return None
        if want is not None and f.normal.dot(want) < 0:
            f.normal_flip()
        return f

    def empty(self):
        return len(self.bm.faces) == 0


def grid(M, P, N):
    """P[i][j] = point or None, N[i][j] = surface normal: quads oriented along the normals"""
    nu, nv = len(P), len(P[0])
    V = [[None if P[i][j] is None else M.v(P[i][j]) for j in range(nv)] for i in range(nu)]
    for i in range(nu - 1):
        for j in range(nv - 1):
            q = [(i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1)]
            if any(V[a][b] is None for a, b in q):
                continue
            nn = sum((N[a][b] for a, b in q), Vector((0, 0, 0)))
            M.face([V[a][b] for a, b in q], nn)


def prism(M, rings, closed=True):
    """solid from rings (equal length point lists) along the extrusion; faces oriented away from the solid's centre"""
    vs = [[M.v(p) for p in r] for r in rings]
    cen = Vector((0, 0, 0))
    n = 0
    for r in rings:
        for p in r:
            cen += Vector(p)
            n += 1
    cen /= n

    def add(idx):
        pts = [Vector(v.co) for v in idx]
        c = sum(pts, Vector((0, 0, 0))) / len(pts)
        nrm = (pts[1] - pts[0]).cross(pts[2] - pts[0])
        M.face(idx, nrm if nrm.dot(c - cen) >= 0 else -nrm)
    k = len(rings[0])
    for a in range(len(rings) - 1):
        for b in range(k):
            add([vs[a][b], vs[a + 1][b], vs[a + 1][(b + 1) % k], vs[a][(b + 1) % k]])
    if closed:
        for r in (vs[0], vs[-1]):
            add(list(r))


# ----------------------------------------------------------------------------- projected strips
def face_ray(y, z):
    return (-3.6, y, z), (1, 0, 0)


def ys(n, y0=-YB, y1=YB):
    return [y0 + (y1 - y0) * i / (n - 1) for i in range(n)]


def front_strip(cast, y_list, z_fn, off, nv=2):
    """strip on the front face: for each y the points z_fn(y, t), t in 0..1, cast along +x onto the body"""
    P, N = [], []
    for y in y_list:
        rp, rn = [], []
        for j in range(nv):
            p, n = cast(*face_ray(y, z_fn(y, j / (nv - 1))), off)
            rp.append(p)
            rn.append(n)
        P.append(rp)
        N.append(rn)
    return P, N


def ribbon(cast, pts, width, off, mode='top', closed=False):
    """gap line of constant width laid on the body.  mode 'top': pts = (x, y) in plan, cast down;  mode 'side-L' / 'side-R': pts = (x, z), cast along +y / -y."""
    n = len(pts)
    P, N = [], []
    for i in range(n):
        a = Vector(pts[max(i - 1, 0)])
        b = Vector(pts[min(i + 1, n - 1)])
        t = (b - a)
        t = t.normalized() if t.length > 1e-9 else Vector((1, 0))
        nrm = Vector((-t.y, t.x))
        rp, rn = [], []
        for s in (-0.5, 0.5):
            q = Vector(pts[i]) + nrm * (s * width)
            if mode == 'top':
                p, nn = cast((q.x, q.y, 3.0), (0, 0, -1), off)
            elif mode == 'side-L':
                p, nn = cast((q.x, -2.5, q.y), (0, 1, 0), off)
            else:
                p, nn = cast((q.x, 2.5, q.y), (0, -1, 0), off)
            rp.append(p)
            rn.append(nn)
        P.append(rp)
        N.append(rn)
    return P, N


def sample(p0, p1, step):
    d = (Vector(p1) - Vector(p0))
    n = max(2, int(math.ceil(d.length / step)) + 1)
    return [tuple(Vector(p0) + d * (i / (n - 1))) for i in range(n)]


# ----------------------------------------------------------------------------- the parts
def build_front(cast, mk, level=0, mat_of=None):
    """-> list of objects (already linked to the scene).  mat_of maps a material name to the one used at this level."""
    mat_of = mat_of or {}
    objs = []

    def emit(M, name, mat, smooth=True):
        if M.empty():
            M.bm.free()
            return
        m = mat_of.get(mat, mat)
        if m is None:
            M.bm.free()
            return
        objs.append(mk(M.bm, name, m, smooth))

    nsy = (97, 49, 25)[level]

    # ---- the light bar and the black band under it ------------------------------------------------------------------------------------------
    def bar_h(y):
        return BAR_H + BAR_DROOP * sstep(0.56, YB, abs(y))

    yl = ys(nsy)
    Mb = Mesh()
    P, N = front_strip(cast, yl, lambda y, t: lead(y)[1] - 0.0008 - t * bar_h(y), 0.0016)
    grid(Mb, P, N)
    emit(Mb, 'HeadDRL_bar', 'HeadDRL')

    Mg = Mesh()
    nb = (4, 3, 2)[level]
    P, N = front_strip(cast, yl, lambda y, t: lead(y)[1] - bar_h(y) - 0.0030 - t * BAND_H, 0.0009, nv=nb)
    grid(Mg, P, N)
    emit(Mg, 'FaceBand', 'GlossBlack')

    # HeadLens strips: slim and low-key, on the band (one per side), a thin dark surround is the band itself
    if level <= 1:
        for sd in (-1, 1):
            Ml = Mesh()
            y0, y1 = (0.24, 0.58)
            yy = [sd * (y0 + (y1 - y0) * i / 15) for i in range(16)]
            zc = lambda y: lead(y)[1] - bar_h(y) - 0.0030 - 0.5 * BAND_H
            P, N = front_strip(cast, yy, lambda y, t: zc(y) + 0.0065 - t * 0.013, 0.0022)
            grid(Ml, P, N)
            emit(Ml, 'HeadLens_%d' % sd, 'HeadLens')

    # ---- the splitter blade -------------------------------------------------------------------------------------------------------------------
    def spl_front(y):
        a = abs(y)
        pr = SPL_P if a <= SPL_KINK else max(0.004, SPL_P - 0.19 * (a - SPL_KINK))
        return S.front_x(a, 0.22) - pr

    ysp = [-0.700 + 1.4 * i / 40 for i in range(41)] if level < 2 else [-0.70, -SPL_KINK, 0.0, SPL_KINK, 0.70]
    rings = []
    for y in ysp:
        xf = spl_front(y)
        xr = S.front_x(abs(y), 0.222) + 0.075
        rings.append([(xr, y, SPL_Z[0]), (xf, y, SPL_Z[0]), (xf, y, SPL_Z[0] + 0.011), (xr, y, SPL_Z[1])])
    Ms = Mesh()
    prism(Ms, rings)
    emit(Ms, 'Splitter', 'Carbon', smooth=False)

    # ---- inside the intake pocket: louvre blades and ribs ----------------------------------------------------------------------------------
    if level == 0:
        I = S.INTAKE
        yy = [-I['y'] + 0.018 + (2 * I['y'] - 0.036) * i / 24 for i in range(25)]
        Mf = Mesh()
        nbl = 4
        for k in range(nbl):
            zc = I['z0'] + (k + 0.5) * (I['z1'] - I['z0']) / nbl
            rings = []
            for y in yy:
                xfl = S.front_x(abs(y), zc) + I['depth']            # the floor of the pocket
                rings.append([(xfl - 0.040, y, zc - 0.010), (xfl - 0.004, y, zc + 0.004), (xfl - 0.004, y, zc + 0.009), (xfl - 0.040, y, zc - 0.005)])
            prism(Mf, rings)
        emit(Mf, 'IntakeBlades', 'Trim', smooth=False)
        Mr = Mesh()
        for yc in (0.0,):
            rings = []
            for z in (I['z0'] + 0.002, I['z1'] - 0.002):
                xfl = S.front_x(abs(yc), z) + I['depth']
                rings.append([(xfl - 0.043, yc - 0.004, z), (xfl - 0.003, yc - 0.004, z), (xfl - 0.003, yc + 0.004, z), (xfl - 0.043, yc + 0.004, z)])
            prism(Mr, rings)
        emit(Mr, 'IntakeRibs', 'GlossBlack', smooth=False)
        # the forward camera / radar eye: a small round lens on the band's centre line
        Mc = Mesh()
        zc = lead(0.0)[1] - bar_h(0.0) - 0.0030 - 0.5 * BAND_H
        p, n = cast(*face_ray(0.0, zc), 0.0)
        if p is not None:
            rings = []
            for r_, dx in ((0.0125, 0.0), (0.0125, -0.004), (0.0085, -0.006)):
                rings.append([(p.x + dx, p.y + r_ * math.cos(a), p.z + r_ * math.sin(a)) for a in [2 * math.pi * i / 16 for i in range(16)]])
            prism(Mc, rings)
        emit(Mc, 'FaceEye', 'Trim', smooth=True)

    # ---- panel gaps ---------------------------------------------------------------------------------------------------------------------------
    stp = (0.02, 0.04, 0.08)[level]
    GW, GOFF = 0.0032, 0.0007
    Mp = Mesh()

    def gap(pts, mode='top', w=GW):
        P, N = ribbon(cast, pts, w, GOFF, mode)
        grid(Mp, P, N)

    row = S.build_rows()
    for sd in (-1, 1):
        # L5: the seam between the hood panel and the fender top (nose corner -> windscreen base)
        x0, x1 = S.CORNER_X + 0.006, S.ROWS[S.R_COWL] - 0.004
        n = int((x1 - x0) / stp) + 2
        gap([(x0 + (x1 - x0) * i / (n - 1), sd * S.rail_y_hood(x0 + (x1 - x0) * i / (n - 1))) for i in range(n)])
        # the corner flap: B-C across the fender top (x = row 1), C-A along the front L1 (inset into the flap)
        A = Vector((row[0]['l1'][0], sd * row[0]['l1'][1]))
        B = Vector((row[1]['rail'][0], sd * row[1]['rail'][1]))
        C = Vector((row[1]['l1'][0], sd * row[1]['l1'][1]))
        cen = (A + B + C) / 3.0

        def inset(p, q, d_):                  # the segment p-q moved d_ towards the centroid
            t = (q - p).normalized()
            nn = Vector((-t.y, t.x))
            if nn.dot(cen - (p + q) / 2) < 0:
                nn = -nn
            return p + nn * d_, q + nn * d_
        b1, c1 = inset(B, C, 0.0)
        gap([tuple(Vector(b1) + (Vector(c1) - Vector(b1)) * (0.012 + 0.976 * i / 15)) for i in range(16)])
        c2, a2 = inset(C, A, 0.004)
        gap([tuple(Vector(c2) + (Vector(a2) - Vector(c2)) * (0.02 + 0.96 * i / 15)) for i in range(16)])
        # the door's front cut (the end of the side-marker assembly): from the L1 corner down to the sill, and up the diagonal to the glass corner
        pass
    # the frunk-lid seam: a flat arc across the hood from L5 to L5 (x -1.85 at the L5 lines, 5 cm further forward on the centre line)
    ye = S.rail_y_hood(-1.85)
    n = 41
    gap([(-1.85 - 0.05 * (1 - (t / ye) ** 2), t) for t in [-ye + 2 * ye * i / (n - 1) for i in range(n)]])
    # the cowl line: the windscreen's lower edge (the paint stops 4 mm in front of the glass)
    yc = S.rail_y_hood(S.ROWS[S.R_COWL]) - 0.004
    xcw = S.ROWS[S.R_COWL] - 0.0045
    gap([(xcw, -yc + 2 * yc * i / 20) for i in range(21)], w=0.0026)

    # the door front cut, both sides: from the L1 / fu / l2 corner of row R_DOOR down to the sill (a little raked), and up the diagonal to the glass
    for sd in (-1, 1):
        mode = 'side-L' if sd < 0 else 'side-R'
        j = row[S.R_DOOR]
        zt = j['l1'][2]
        gap([(DOOR_X + 0.135 * (zt - z) / (zt - 0.30), z) for z in [zt - 0.004 - (zt - 0.30 - 0.004) * i / 24 for i in range(25)]], mode)
    emit(Mp, 'PanelGaps', 'PanelGap')

    # ---- the side-marker assembly (behind the top of the front arch, ends at the door's front cut) -----------------------------------------------
    # 003: a red reflector whose pointed front tip sits on the arch circle, its lower edge following the arch up to a flat bottom; behind it the gloss-black
    # blade (4.8 cm) with the round camera and, at its rear end, the amber lamp; the top edge is one straight line from the arch tip down to the door cut.
    def mk_top(x):
        return MK_TIP[1] + (MK_END[1] - MK_TIP[1]) * (x - MK_TIP[0]) / (MK_END[0] - MK_TIP[0])

    def arch_z(x):
        return S.HUB_Z + math.sqrt(max(S.R_ARCH ** 2 - (x - S.HUBS[0][0]) ** 2, 0.0))

    for sd in (-1, 1):
        x_end = MK_END[0] - 0.004
        x_blade = MK_BLADE
        # blade
        Mk = Mesh()
        nx = 10 if level else 14
        P, N = [], []
        for i in range(nx + 1):
            x = x_blade + (x_end - x_blade) * i / nx
            rp, rn = [], []
            for t in (0.0, 0.5, 1.0):
                p, nn = cast((x, sd * 2.5, mk_top(x) - MK_H * t), (0, -sd, 0), 0.0014)
                rp.append(p)
                rn.append(nn)
            P.append(rp)
            N.append(rn)
        grid(Mk, P, N)
        emit(Mk, 'SideBlade_%d' % sd, 'GlossBlack')
        # reflector: from the tip (on the arch circle) to the blade; lower edge = the arch circle (+4 mm) until the blade's height, then flat
        Mr = Mesh()
        P, N = [], []
        for i in range(9):
            x = MK_TIP[0] + 0.001 + (x_blade - MK_TIP[0] - 0.001) * i / 8
            zt_ = mk_top(x) - 0.002
            zb = max(arch_z(x) + 0.004, zt_ - MK_H - 0.008)
            zb = min(zb, zt_ - 0.002)
            rp, rn = [], []
            for t in (0.0, 1.0):
                p, nn = cast((x, sd * 2.5, zt_ + (zb - zt_) * t), (0, -sd, 0), 0.0017)
                rp.append(p)
                rn.append(nn)
            P.append(rp)
            N.append(rn)
        grid(Mr, P, N)
        emit(Mr, 'SideReflector_%d' % sd, mat_of.get('Reflector', 'Caliper'))
        if level == 0:
            # amber lamp: a thin lit slot along the top of the blade near its rear end
            Ma = Mesh()
            P, N = [], []
            for i in range(9):
                x = -1.092 + (-1.030 - -1.092) * i / 8
                rp, rn = [], []
                for t in (0.0, 1.0):
                    p, nn = cast((x, sd * 2.5, mk_top(x) - 0.0075 - 0.0075 * t), (0, -sd, 0), 0.0021)
                    rp.append(p)
                    rn.append(nn)
                P.append(rp)
                N.append(rn)
            grid(Ma, P, N)
            emit(Ma, 'SideLamp_%d' % sd, 'SideMarker')
            # round side camera on the blade
            Mc = Mesh()
            xc = -1.150
            p, nn = cast((xc, sd * 2.5, mk_top(xc) - MK_H * 0.55), (0, -sd, 0), 0.0)
            if p is not None:
                rings = []
                for r_, dy in ((0.0105, 0.0), (0.0105, 0.004), (0.0075, 0.0058)):
                    rings.append([(p.x + r_ * math.cos(a), p.y + sd * dy, p.z + r_ * math.sin(a)) for a in [2 * math.pi * i / 14 for i in range(14)]])
                prism(Mc, rings)
            emit(Mc, 'SideCamera_%d' % sd, 'Trim', smooth=True)
    return objs
