"""
FRONT region (R2, ported to the accepted R1e3 shell): light bar, black face, intake, lower lip, hood / corner-flap seams.  SPEC section 7, DF-1 .. DF-8.
Interface: REGIONS.md section 2 and regions/ctx.py.  Everything is anchored on the shell's named curves (ctx.A.D.NOSE: xe / Fxy / rake / curves bar_top, bar_bot,
face_black_bot, F_bot, tri, tri_seam, L5, hood_seam_L7, cowl_edge ...); nothing uses the old R1b analytic front (common.hood_z / front_x / build_rows).

  shell_post(ctx)        hi only: the intake pocket cut into the (black) front face of the dense body, after the wheel-arch cut
  build(ctx, level)      level 0 = hi, 1 = lod1, 2 = lod2 -> [objects]

Layout of the face (top -> bottom, all on the raked, bowed front face of the shell; h = distance below the bar_top edge, z = 0.566 - h):
  HeadDRL   the light bar, 16 mm tall, tapering to 1.3 mm at the corner vertex, corner to corner along bar_top (r2: the ONLY lit headlight line)  DF-1
  Paint     the thin body-colour lower lip under the bar (not lit)                                                           DF-1
  GlossBlack the bright-black panel down to face_black_bot (z 0.451), HeadLens dark strips on its upper edge, sensor dot    DF-2 DF-3
  intake    pocket cut into the face (hi) with louvre blades / ribs; liner, blades and the frame strips round it are PanelGap  DF-4
  lip       F_Lip, PanelGap (lod2: GlossBlack): ONE black blade / skin under the paint edge (z 0.287), round the corner to the front arch   DF-5
  PanelGap  L7 hood seam (arc, p013), cowl seam, L5 seam (hood | fender top), corner-flap seams                             DF-6 DF-7
No side-marker parts and no door cut here (they belong to side.py).  No other lamps (DF-8).
Diagnostics (build args): --f-skip F_HeadDRL,F_Lip,...  leaves those parts out;  --f-lipmat <Material>  builds the lip in that material.
"""
import math
import bmesh
from mathutils import Vector
import common as S
from common import Mesh, sstep

NAME = 'front'

# ----------------------------------------------------------------------------- dimensions (m)
YB = 0.667                      # the bar / panels stop this far from the centre line (the corner crease of the face is at |y| 0.67)
BAR_H = 0.009                   # light bar height; FRONT r2: no thickening and no droop at the ends, the strip tapers instead (p014: it thins out and stops at the corner vertex).  2026-10-23: 16 -> 9 mm
                                # (p016 column profiles: the white line is 4 px = 9 mm at every x, the model's bright band was 11 px)
BAR_TAPER = 0.92                # the bar is this fraction thinner at the vertex (9 mm -> 0.7 mm) ...
BAR_TAPER_Y0 = 0.42             # ... starting at this |y| (smooth step to YB), the top edge stays level with the hood's front edge
BAR_OFF = 0.0006                # the strip stands this far off the face (it was 1.6 mm: edge-on from the side it showed as a glowing tab)
BAR_TOP_GAP = 0.0008            # the bar starts this far below the hood's front edge
LIP_H = 0.0                     # body-colour lip under the bar.  2026-10-23: none (was 7 mm): p016's grey band under the bar sits 4 px below it with a black gap and fades from 220 to 35 / 255 across the
                                # car while the bar stays at 255: it is the bar's reflection in the raked gloss panel, not a part
BAND_BOT_Z = 0.428              # the panel's lower edge: p016 (refit camera) puts it ~2.3 cm below design2's face_black_bot (z 0.451); 0.115 m of black below the bar + lip
LIP_ZA, LIP_ZB = 0.300, 0.235   # heights at which the shell's wall / face is sampled to give the lip its slope (the face / wall exist down to ~0.22)
LIP_FAN = (-2.0, 0.0)           # plan point inside the nose the sampling rays fan out from
LIP_AMAX = 108.0                # fan angle limit (deg, 0 = straight ahead, 90 = sideways)
LIP_X_END = -1.905              # the lip stops here, at the front wheel arch (p018: it runs to the tyre)
LIP_P, LIP_P_Y0, LIP_P_Y1 = 0.060, 0.45, 0.80   # the lip stands out of the face by LIP_P at the middle (p018 2026-10-23: its front 15 px = 5.9 cm ahead of the paint's lower edge), dies out between these |y|
LIP_ZT = 0.300                  # top of the lip: ONE straight line at the paint's lower edge all the way round.  FRONT r3: 0.287 -> 0.300: p018 (paint edge 1.5-4 px higher than the model's at x 240-300 = 0.6-1.5 cm) and p016
                                # (the opening's lower edge / blade attachment at z ~0.318 on the face) both want it higher; 0.300 leaves 0.6 cm in p018 and 1.8 cm in p016 (the two photos disagree by 3 cm)
LIP_WALL = 0.0050               # r3: the lip's skin is at least this thick (raised plate along the wall, 5 mm + the 1.2 mm offset) so that its bottom edge can carry a real rounded edge of constant radius
LIP_R = 0.010                   # r3: radius of that rounded bottom edge, the same all the way from the nose to the arch: the thin bright line of the photos (p018: the lip's lower edge mirrors the floor)
LIP_RT = 0.012                  # 2026-10-23: radius of the rounded top-front edge (p016: the lip's upper front edge catches the light all along; p018: its front end is round, not a blade tip)
LIP_TOP_SLOPE = 0.20            # the blade's top surface falls towards its front edge by this much per metre of protrusion
LIP_ZB_MID, LIP_ZB_SIDE = 0.185, 0.168   # 2026-10-23 (p018): ONE black bar of even height all round, its front face vertical from the paint edge to z 0.19 at the nose (photo px 690 -> 716 at the leading
                                         # edge, rounded at both ends), bottom 0.187 at the front corner -> 0.165 at the arch; the thin blade over a recessed face (fr8) read as a wedge with a sharp tip
LIP_SMOOTH = 0.016              # Gaussian smoothing (m of arc length) of the lip's plan outline: the corner is one rounded sweep
LIP_E = 0.0012                  # offset of the lip's skin from the shell
LIP_IN = 0.005                  # how far the lip's top / bottom inner edges sink into the body (hidden; kept small so the ring does not fold at the corner crease)
LIP_SLOPE_MAX = 0.014           # plan displacement of the shell between the two sample heights beyond which they are taken to lie on different faces
FLAP_IN = 0.008                 # the flap's gap lines (rear seam end, outer edge) lie this far inboard of the crest U (p005)
INTAKE = dict(y=0.645, z0=LIP_ZT + 0.0015, z1=0.428 - 0.0010, depth=0.120)      # pocket in the face: half width, bottom, top, depth towards the tail.  FRONT r3 (p016): the black opening runs from the gloss panel's lower edge
                                                                  # (z 0.428) straight down to the lip (z 0.300): 0.126 m high (photo ~52 px = 0.13 m); it was 0.318 .. 0.420 with a 3.7 cm black frame band under it


# ----------------------------------------------------------------------------- the shell's front face (design2.NOSE): x = Fxy(y, z), bowed + raked
class Geo:
    def __init__(self, D):
        nz = D.NOSE
        self.D, self.nz = D, nz
        self.xe, self.Fxy = nz['xe'], nz['Fxy']
        self.zN = float(nz['N'][2])
        self.rake = float(nz['rake'])
        self.cv = nz['curves']

    def face(self, y, h, off=0.0):
        """(point, outward normal) on the front face at lateral y, h below the top edge, `off` along the normal"""
        z = self.zN - h
        x = float(self.Fxy(y, z))
        e = 1e-3
        dxdy = (float(self.xe(y + e)) - float(self.xe(y - e))) / (2 * e)
        n = Vector((-1.0, dxdy, -self.rake)).normalized()
        return Vector((x, y, z)) + n * off, n


def geo(ctx):
    g = ctx.cache.get('front_geo')
    if g is None:
        g = ctx.cache['front_geo'] = Geo(ctx.A.D)
    return g


def ys_lin(n, y0=-YB, y1=YB):
    return [y0 + (y1 - y0) * i / (n - 1) for i in range(n)]


def face_strip(g, ys, h0, h1, off, nv=2):
    """strip on the front face: rows over y, columns from h0(y) to h1(y) below the top edge"""
    P, N = [], []
    for y in ys:
        a, b = h0(y), h1(y)
        rp, rn = [], []
        for j in range(nv):
            p, n = g.face(y, a + (b - a) * j / (nv - 1), off)
            rp.append(p)
            rn.append(n)
        P.append(rp)
        N.append(rn)
    return P, N


def bar_h(y):
    return BAR_H * (1.0 - BAR_TAPER * float(sstep(BAR_TAPER_Y0, YB, abs(y))))


def bar_top(y):
    """h of the bar's top edge below the hood edge: constant (the strip does not turn down at the corners any more)"""
    return BAR_TOP_GAP


def bar_bot(y):
    return bar_top(y) + bar_h(y)


def ribbon(cast, pts, width, off):
    """gap line of constant width laid on the body: pts = (x, y) in plan, cast down onto the paint"""
    n = len(pts)
    P, N = [], []
    for i in range(n):
        a = Vector(pts[max(i - 1, 0)])
        b = Vector(pts[min(i + 1, n - 1)])
        t = b - a
        t = t.normalized() if t.length > 1e-9 else Vector((1, 0))
        nrm = Vector((-t.y, t.x))
        rp, rn = [], []
        for s in (-0.5, 0.5):
            q = Vector(pts[i]) + nrm * (s * width)
            p, nn = cast((q.x, q.y, 3.0), (0, 0, -1), off)
            rp.append(p)
            rn.append(nn)
        P.append(rp)
        N.append(rn)
    return P, N


# ----------------------------------------------------------------------------- faces oriented by their own winding
# A new bmesh face has no valid normal, so common.grid / common.prism (which flip by f.normal) flip nothing: the face direction is the winding order alone, and the game's single-sided
# materials hide a face that is wound inward.  These two orient every quad by its geometric normal instead (like side.py's _grid).
def _gn(pts):
    """geometric (winding) normal of a polygon, Newell"""
    n = Vector((0, 0, 0))
    for i in range(len(pts)):
        a, b = pts[i], pts[(i + 1) % len(pts)]
        n += Vector(((a.y - b.y) * (a.z + b.z), (a.z - b.z) * (a.x + b.x), (a.x - b.x) * (a.y + b.y)))
    return n


def _grid(M, P, N):
    """strip / grid P[i][j] with surface normals N[i][j]: every quad is wound so that its normal agrees with the sum of the surface normals"""
    nu, nv = len(P), len(P[0])
    V = [[None if P[i][j] is None else M.v(P[i][j]) for j in range(nv)] for i in range(nu)]
    for i in range(nu - 1):
        for j in range(nv - 1):
            q = [(i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1)]
            if any(V[a][b] is None for a, b in q):
                continue
            vs = [V[a][b] for a, b in q]
            nn = sum((N[a][b] for a, b in q), Vector((0, 0, 0)))
            M.face(vs if _gn([Vector(v.co) for v in vs]).dot(nn) >= 0 else vs[::-1])


def _prism(M, rings, closed=True):
    """solid from rings (equal-length point lists) along the extrusion: each side quad faces away from the local ring centre, the two caps away from the solid along the extrusion"""
    vs = [[M.v(p) for p in r] for r in rings]
    cens = [sum((Vector(p) for p in r), Vector((0, 0, 0))) / len(r) for r in rings]
    k = len(rings[0])
    for a in range(len(rings) - 1):
        cc = (cens[a] + cens[a + 1]) * 0.5
        for b in range(k):
            idx = [vs[a][b], vs[a + 1][b], vs[a + 1][(b + 1) % k], vs[a][(b + 1) % k]]
            pts = [Vector(v.co) for v in idx]
            c = sum(pts, Vector((0, 0, 0))) / 4.0
            M.face(idx if _gn(pts).dot(c - cc) >= 0 else idx[::-1])
    if closed:
        for r, away in ((vs[0], cens[0] - cens[1]), (vs[-1], cens[-1] - cens[-2])):
            idx = list(r)
            M.face(idx if _gn([Vector(v.co) for v in idx]).dot(away) >= 0 else idx[::-1])


def _sweep(M, rings, skip=()):
    """solid swept along a path: rings = cross-section polylines [A, B, C, ...] (closed loop), all wound the same way, the first ring's point k and the next ring's point k belonging together.
    The quad wound [v(i,k), v(i+1,k), v(i+1,k+1), v(i,k+1)] has normal ~ T x E (path tangent x ring edge), which is outward for the cross-section order used by the lip (top-inside, top-front,
    bottom-front, bottom-inside); the two end caps are oriented along -T / +T.  Winding is by construction, not by a heuristic, so nothing can be wound inward where the path turns fast."""
    vs = [[M.v(p) for p in r] for r in rings]
    k = len(rings[0])
    for a in range(len(rings) - 1):
        for b in range(k):
            if b in skip:                                                   # (a side band another part covers exactly: the lip's chamfer under its rounded edge strip)
                continue
            M.face([vs[a][b], vs[a + 1][b], vs[a + 1][(b + 1) % k], vs[a][(b + 1) % k]])
    for r_, v_, sgn in ((rings[0], vs[0], -1.0), (rings[-1], vs[-1], 1.0)):
        pts = [Vector(p) for p in r_]
        Tn = (Vector(rings[1][0]) - Vector(rings[0][0])) if sgn < 0 else (Vector(rings[-1][0]) - Vector(rings[-2][0]))
        idx = list(v_)
        M.face(idx if _gn(pts).dot(Tn) * sgn >= 0 else idx[::-1])


def _check(ob, cast, solid):
    """(out, in) face counts of a built object: strips against the body's outward normal under the face, solids by the parity of the crossings of a ray along the face normal"""
    import bmesh as _bm
    from mathutils.bvhtree import BVHTree
    me = ob.data
    bm = _bm.new()
    bm.from_mesh(me)
    bm.normal_update()
    bvh = BVHTree.FromBMesh(bm) if solid else None
    out = inn = 0
    bad = []
    for f in bm.faces:
        c, n = f.calc_center_median(), f.normal
        if solid:
            o, hits = c + n * 1e-4, 0                    # parity of the ray's crossings of the object: even = it leaves the object = the face looks outward
            for _ in range(8):
                h = bvh.ray_cast(o, n)
                if h[0] is None:
                    break
                hits += 1
                o = h[0] + n * 1e-4
            ok = hits % 2 == 0
        else:
            d = (0, 0, -1) if abs(n.z) > abs(n.x) else (1, 0, 0)
            o = (c.x, c.y, 3.0) if d[2] else (-3.6, c.y, c.z)
            p, ns = cast(o, d, 0.0)
            ok = p is None or n.dot(ns) > 0
        out += ok
        inn += not ok
        if not ok:
            bad.append((round(c.y, 2), round(c.x, 2), round(c.z, 3), tuple(round(v, 2) for v in n)))
    bm.free()
    return out, inn, bad[:6]


# ----------------------------------------------------------------------------- the seams (plan polylines)
def L7_arc(g, n):
    """DF-6: the front-trunk lid's rear edge, from L5 to L5 across the hood.  p013 (top view): x(y) = -1.869 at the centre, -1.81 at L5, a flat-bottomed arc, convex forward"""
    D = g.D
    xl7 = float(D.L7_X)
    yl = lambda x: float(D.N[1] + (D.W[1] - D.N[1]) * (x - D.N[0]) / (D.W[0] - D.N[0]))      # L5's y at x
    bow = 0.058
    # the end on L5: x_e with x_e = xl7 (+ tiny drift from the arc itself): solve y(x) on L5
    ye = yl(xl7)
    pts = []
    for i in range(n):
        u = -1 + 2 * i / (n - 1)
        pts.append((xl7 - bow * (1 - (0.6 * u * u + 0.4 * u ** 4)), u * ye))
    return pts


def lerp_pts(a, b, n):
    return [tuple(Vector(a) + (Vector(b) - Vector(a)) * (i / (n - 1))) for i in range(n)]


# ----------------------------------------------------------------------------- the intake pocket (hi body only)
def cut_pocket(ob, I):
    """cut the intake out of the front face of the dense mesh: the outline is bisected into the mesh, the enclosed faces are extruded `depth` towards the tail
    (a recess with a floor and four walls, all Trim).  New vertices only; no existing vertex moves."""
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
    inner = [f for f in bm.faces if f.calc_center_median().x < -2.3 and f.normal.x < -0.4
             and -I['y'] < f.calc_center_median().y < I['y'] and I['z0'] < f.calc_center_median().z < I['z1']]
    ret = bmesh.ops.extrude_face_region(bm, geom=inner)
    newv = [e for e in ret['geom'] if isinstance(e, bmesh.types.BMVert)]
    newf = [e for e in ret['geom'] if isinstance(e, bmesh.types.BMFace)]
    bmesh.ops.translate(bm, verts=newv, vec=(I['depth'], 0, 0))
    bmesh.ops.delete(bm, geom=inner, context='FACES')
    bm.normal_update()                                        # (new faces have no valid normal until now: the wall flip below compares against f.normal)
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
    return len(inner)


def shell_post(ctx):
    """the intake pocket (DF-4), hi body only (the LOD bodies are decimated from this one)"""
    if ctx.front_r2:
        ctx.report('intake_faces', cut_pocket(ctx.body, INTAKE))


# ----------------------------------------------------------------------------- the parts
def build(ctx, level):
    """-> list of objects (already linked to the scene).  ctx.mat_of(level, name) maps a material name to the one used at this level (None = drop)."""
    if ctx.oldbody or not ctx.front_r2:
        return []
    g = geo(ctx)
    cast = ctx.surf_hi.cast
    objs = []

    counts = ctx.cache.setdefault('front_normals', {})

    skip = [s for s in (ctx.arg('f-skip', '') or '').split(',') if s]            # diagnostics: --f-skip F_HeadDRL,F_BarLip leaves those parts out of the build

    def emit(M, name, mat, smooth=True, solid=False):
        if M.empty() or name in skip:
            M.bm.free()
            return
        m = ctx.mat_of(level, mat)
        if m is None or (mat == 'HeadLens' and m != 'HeadLens'):      # a lens strip merged into HeadDRL would glow white by day: drop it instead
            M.bm.free()
            return
        ob = ctx.mk(M.bm, name, m, smooth)
        objs.append(ob)
        if level == 0:
            counts[name] = _check(ob, cast, solid)

    nsy = (97, 49, 25)[level]
    yl = ys_lin(nsy)

    # ---- DF-1 the light bar and the body-colour lip under it ------------------------------------------------------------------------------
    M = Mesh()
    P, N = face_strip(g, yl, bar_top, bar_bot, BAR_OFF)
    _grid(M, P, N)
    emit(M, 'F_HeadDRL', 'HeadDRL')

    if LIP_H > 0.0:
        M = Mesh()
        P, N = face_strip(g, yl, bar_bot, lambda y: bar_bot(y) + LIP_H, 0.0012)
        _grid(M, P, N)
        emit(M, 'F_BarLip', 'Paint')

    # ---- DF-2 the bright-black panel, DF-3 the dark HeadLens strips on its upper edge -----------------------------------------------------------
    h_band0 = lambda y: bar_bot(y) + LIP_H
    h_band1 = lambda y: g.zN - BAND_BOT_Z
    M = Mesh()
    P, N = face_strip(g, yl, h_band0, h_band1, 0.0009, nv=(4, 3, 2)[level])
    _grid(M, P, N)
    emit(M, 'F_FacePanel', 'GlossBlack')

    if level == 0:
        for sd in (-1, 1):
            M = Mesh()
            y0, y1 = 0.20, 0.60
            yy = [sd * (y0 + (y1 - y0) * i / 15) for i in range(16)]
            P, N = face_strip(g, yy, lambda y: bar_bot(y) + LIP_H + 0.004, lambda y: bar_bot(y) + LIP_H + 0.012, 0.0016)
            _grid(M, P, N)
            emit(M, 'F_HeadLens_%d' % sd, 'HeadLens')
        # the forward sensor (p016 (485, 752) = y -0.125): 2026-10-23 a small dark box hanging under the panel's lower edge, just inside the opening (was a round eye on the panel)
        M = Mesh()
        I0 = INTAKE
        yc, zc0, zc1 = -0.125, I0['z1'] - 0.016, I0['z1'] - 0.002
        rings = []
        for y_ in (yc - 0.013, yc + 0.013):
            xm = float(g.Fxy(y_, I0['z1']))
            rings.append([(xm + 0.004, y_, zc1), (xm + 0.004, y_, zc0 + 0.003), (xm + 0.007, y_, zc0), (xm + 0.030, y_, zc0), (xm + 0.030, y_, zc1)])
        _prism(M, rings)
        emit(M, 'F_FaceEye', 'Trim', smooth=False, solid=True)

    # ---- DF-4 inside the intake pocket (hi) ------------------------------------------------------------------------------------------------
    # round 2: the photo's opening is almost pure black with barely visible structure.  A liner of the darkest matte material (PanelGap: base 0.006, roughness 0.9) is laid 0.7 mm inside the
    # pocket's floor and four walls (the body's own pocket faces stay Trim underneath), and the two blades are thin and PanelGap too, so nothing reads as a grey grille slat.
    # (PanelGap is already in the hi build: no new draw call; the lod bodies keep their Trim pocket and get no liner.)
    if level == 0:
        I = INTAKE
        E_L, M_L = 0.0007, 0.0012                                  # liner offset into the pocket; margin from the mouth edges
        yl0, yl1, zl0, zl1 = -I['y'] + M_L, I['y'] - M_L, I['z0'] + M_L, I['z1'] - M_L
        xfl = lambda y, z: float(g.Fxy(y, z)) + I['depth'] - E_L   # the floor plane
        xmo = lambda y, z: float(g.Fxy(y, z)) + 0.0015              # just inside the mouth
        Ml = Mesh()
        P, N = [], []                                                # floor, facing the front
        for i in range(25):
            y = yl0 + (yl1 - yl0) * i / 24
            P.append([Vector((xfl(y, z), y, z)) for z in (zl0 + (zl1 - zl0) * j / 4 for j in range(5))])
            N.append([Vector((-1, 0, 0))] * 5)
        _grid(Ml, P, N)
        for sd in (-1, 1):                                           # side walls, facing the middle
            ywl = sd * (I['y'] - E_L)
            P = [[Vector((xmo(ywl, z), ywl, z)), Vector((xfl(ywl, z), ywl, z))] for z in (zl0 + (zl1 - zl0) * j / 4 for j in range(5))]
            _grid(Ml, P, [[Vector((0, -sd, 0))] * 2] * 5)
        for zw, dn in ((I['z1'] - E_L, -1), (I['z0'] + E_L, 1)):    # top wall faces down, bottom wall faces up
            P = [[Vector((xmo(y, zw), y, zw)), Vector((xfl(y, zw), y, zw))] for y in (yl0 + (yl1 - yl0) * i / 24 for i in range(25))]
            _grid(Ml, P, [[Vector((0, 0, dn))] * 2] * 25)
        ob = None
        if not Ml.empty():
            ob = ctx.mk(Ml.bm, 'F_IntakeLiner', ctx.mat_of(level, 'PanelGapDark'), False)
            objs.append(ob)
            zmid = 0.5 * (I['z0'] + I['z1'])
            o_in = [0, 0]
            for f in ob.data.polygons:                                # every liner face must look into the pocket: floor towards the front, walls towards the middle
                n, c = f.normal, f.center
                ok = n.x < 0 if (abs(n.x) >= abs(n.y) and abs(n.x) >= abs(n.z)) else (n.y * c.y < 0 if abs(n.y) >= abs(n.z) else n.z * (c.z - zmid) < 0)
                o_in[0 if ok else 1] += 1
            counts['F_IntakeLiner'] = (o_in[0], o_in[1], [])
        else:
            Ml.bm.free()

        # 2026-10-23 (p016, shadows lifted x4): no horizontal slats in the opening; what shows is a dark rectangular block left of centre (the radar unit, photo px 487 .. 633 x 753 .. 773 =
        # y -0.50 .. -0.14, z ~0.37 .. 0.41, set back) and, at the right end, a vertical post with a short diagonal brace at its foot (px 320 .. 370 = y +0.38 .. +0.50).
        Mf = Mesh()
        xin = lambda y, z, d: float(g.Fxy(y, z)) + d                      # a point d behind the face (towards the tail)
        ys_r = [-0.50 + 0.36 * i / 12 for i in range(13)]
        rings = []
        for y_ in ys_r:
            r_ = []
            for zz, dd in ((0.410, 0.050), (0.414, 0.056), (0.414, 0.085), (0.368, 0.085), (0.368, 0.056), (0.372, 0.050)):
                r_.append((xin(y_, zz, dd), y_, zz))
            rings.append(r_)
        _prism(Mf, rings)
        for (ya, za), (yb, zb_) in (((0.40, I['z0'] + 0.004), (0.40, I['z1'] - 0.004)), ((0.47, I['z0'] + 0.006), (0.405, I['z0'] + 0.070))):
            rings = []
            for t in (0.0, 1.0):
                y_, z_ = ya + (yb - ya) * t, za + (zb_ - za) * t
                xc = xin(y_, z_, 0.070)
                rings.append([(xc - 0.008, y_ - 0.007, z_), (xc + 0.008, y_ - 0.007, z_), (xc + 0.008, y_ + 0.007, z_), (xc - 0.008, y_ + 0.007, z_)])
            _prism(Mf, rings)
        emit(Mf, 'F_IntakeParts', 'PanelGap', smooth=False, solid=True)       # (PanelGap: near-black with a faint sheen; Trim lit up as grey slabs, the photo shows them only with the shadows lifted)

        # the frame round the opening (the body's own Trim face strips between the panel, the pocket and the lip): the photo's opening runs black right to the corner crease and down to the lip,
        # so these strips are laid over in the matte black (PanelGap).  hi only (the LOD bodies keep their Trim).
        Mfr = Mesh()
        zN = g.zN
        ysf = lambda a, b, n=8: [a + (b - a) * i / (n - 1) for i in range(n)]
        for (ya, yb, za, zb) in ((-YB, YB, I['z1'], BAND_BOT_Z), (-YB, YB, LIP_ZT - 0.006, I['z0']), (I['y'], YB, I['z0'], I['z1']), (-YB, -I['y'], I['z0'], I['z1'])):
            if zb - za < 0.002:                                          # (r3: the strip between the opening and the gloss panel is 1 mm now: skip the sliver)
                continue
            n_y = 49 if (yb - ya) > 0.5 else 4
            P, N = face_strip(g, ysf(ya, yb, n_y), lambda y, zb=zb: zN - zb, lambda y, za=za: zN - za, 0.0009)
            _grid(Mfr, P, N)
        emit(Mfr, 'F_IntakeFrame', 'PanelGapDark')

    # ---- DF-5 the lower lip ---------------------------------------------------------------------------------------------------------------
    # FRONT round 2 (p018 / p016 / p003 / p005): ONE thick glossy-black lip tucked under the body: it starts at the paint's lower edge (L3, z 0.287), continues the shell's own wall / face downward
    # (same slope, offset 1.2 mm), has no gap to the body, no tooth, blade-like at the front (it stands out of the face by up to LIP_P at the middle, 0 at the corner) and runs round the corner
    # along the lower wall to the front wheel arch.  Its plan outline is found by casting a fan of rays onto the shell at two heights (so it follows whatever the shell is), nothing is hard-coded.
    z1, z2 = LIP_ZA, LIP_ZB
    LIP = ctx.cache.get(('front_lip', level))
    if LIP is None:
        cx, cy = LIP_FAN
        def hit(a, z):
            d = Vector((-math.cos(a), math.sin(a), 0.0))
            o = Vector((cx, cy, z)) + d * 3.0
            p_, n_ = cast(o, -d, 0.0, 6.0)
            return p_, n_
        def stn(a):
            p1, n1 = hit(a, z1)
            p2, n2 = hit(a, z2)
            if p1 is None or p2 is None:
                return None
            u = Vector((n1.x + n2.x, n1.y + n2.y, 0.0))
            u = u.normalized() if u.length > 1e-6 else Vector((-1.0, 0.0, 0.0))
            b1, b2 = Vector((p1.x, p1.y)), Vector((p2.x, p2.y))
            if (b2 - b1).length > LIP_SLOPE_MAX:                          # the two samples are on different faces (the corner crease is raked): no slope, a vertical skin
                b2 = b1.copy()
            return dict(b1=tuple(b1), b2=tuple(b2), u=(u.x, u.y))
        NA = (160, 40, 16)[level]
        amax = math.radians(LIP_AMAX)
        sts = []
        for i in range(NA + 1):
            a = amax * i / NA
            sd = stn(a)
            if sd is None:
                continue
            if sd['b1'][0] > LIP_X_END:                                 # reached the wheel arch: bisect to land exactly on x = LIP_X_END
                if sts:
                    lo, hi = amax * (i - 1) / NA, a
                    for _ in range(14):
                        mid = 0.5 * (lo + hi)
                        sm = stn(mid)
                        if sm is None:
                            break
                        if sm['b1'][0] > LIP_X_END:
                            hi = mid
                        else:
                            lo, sd = mid, sm
                    sts.append(sd)
                break
            sts.append(sd)
        LIP = ctx.cache[('front_lip', level)] = sts
    sts = LIP
    # full outline (left | right), then smooth the outline along its arc length so the plan corner (face | chamfer | wall) is ONE rounded sweep, not a mitre: the skin has the same shading all the way round
    full = [dict(b1=(s_['b1'][0], -s_['b1'][1]), b2=(s_['b2'][0], -s_['b2'][1]), u=(s_['u'][0], -s_['u'][1])) for s_ in reversed(sts[1:])] + list(sts)
    n_ = len(full)
    if n_ > 2:
        B1 = [Vector(s_['b1']) for s_ in full]
        B2 = [Vector(s_['b2']) for s_ in full]
        sl = [0.0]
        for i in range(1, n_):
            sl.append(sl[-1] + (B1[i] - B1[i - 1]).length)

        def gsm(P):
            out = []
            for i in range(n_):
                acc, wsum = Vector((0.0, 0.0)), 0.0
                for j in range(n_):
                    d_ = (sl[j] - sl[i]) / LIP_SMOOTH
                    if abs(d_) > 3.0:
                        continue
                    w = math.exp(-0.5 * d_ * d_)
                    acc += P[j] * w
                    wsum += w
                out.append(acc / wsum)
            return out
        S1, S2 = gsm(B1), gsm(B2)
        for i in range(n_):
            tg = S1[min(i + 1, n_ - 1)] - S1[max(i - 1, 0)]
            nn = Vector((-tg.y, tg.x))
            nn = nn.normalized() if nn.length > 1e-9 else Vector(full[i]['u'])
            if nn.dot(Vector(full[i]['u'])) < 0:
                nn = -nn
            full[i] = dict(b1=tuple(S1[i]), b2=tuple(S2[i]), u=tuple(nn))
    ring_l, ring_p = [], []
    edge_P, edge_N = [], []                                               # r3: the rounded bottom edge (hi only): one constant-radius quarter round along the whole outline
    for sd in full:
        b1, b2, u = Vector(sd['b1']), Vector(sd['b2']), Vector(sd['u'])
        ay = abs(b1.y)
        pr = max(LIP_P * (1.0 - float(sstep(LIP_P_Y0, LIP_P_Y1, ay))), LIP_WALL - LIP_E)   # blade stands out of the face at the middle; along the wall it is a LIP_WALL plate (r3)
        zt = LIP_ZT
        zb = LIP_ZB_MID + (LIP_ZB_SIDE - LIP_ZB_MID) * float(sstep(0.62, 1.00, ay))        # fr8 (was 0.40..0.90); r3: p018 has the lip's lower edge at z ~0.19 already at the front corner (was sstep 0.55 .. 1.0: floor showed through)

        def P(off, z):
            t = min(max((z1 - z) / (z1 - z2), 0.0), 1.0)                # (the shell's slope between the two sample heights; straight down below the lower one)
            q = b1 + (b2 - b1) * t + u * off
            return (q.x, q.y, z)
        e = LIP_E
        za = zt + LIP_TOP_SLOPE * (pr + e + LIP_IN)                      # the top of the lip falls towards the front (reads dark, no lit wedge); inside the body / on the wall it is level
        ch = min(LIP_R, 0.9 * (pr + e + LIP_IN))                          # bottom chamfer (under the rounded edge strip): never deeper than the lip is thick
        rt = min(LIP_RT, 0.45 * (pr + e + LIP_IN))                        # rounded top-front edge (3 facets of 30 deg), never wider than half the lip's depth
        top = [(pr + e - rt + rt * math.sin(math.radians(a_)), zt - rt + rt * math.cos(math.radians(a_))) for a_ in (0.0, 30.0, 60.0, 90.0)]
        prm = [(-LIP_IN, za)] + top + [(pr + e, zb + ch), (pr + e - ch, zb), (-LIP_IN, zb)]
        ring_l.append([P(o_, z_) for o_, z_ in prm])
        ring_p.append((u, prm))
        if level == 0:
            Rr = ch                                                     # 2026-10-20: the strip REPLACES the chamfer (same end lines, no face under it); was ch + 0.3 mm over a kept chamfer: two near-tangent layers z-fought into a jagged edge
            oc, zc = pr + e - ch, zb + ch
            row_p, row_n = [], []
            for ph_ in (0.0, 30.0, 60.0, 90.0):
                c_, s_ = math.cos(math.radians(ph_)), math.sin(math.radians(ph_))
                row_p.append(Vector(P(oc + Rr * c_, zc - Rr * s_)))
                row_n.append(Vector((u.x * c_, u.y * c_, -s_)))
            edge_P.append(row_p)
            edge_N.append(row_n)
    LIP_SKIP = (5,) if level == 0 else ()                                # hi: the chamfer band (ring edge 5, after the top round's 4 points) is covered by F_LipEdge
    Ms = Mesh()
    if len(ring_l) > 2:
        _sweep(Ms, ring_l, skip=LIP_SKIP)
    n_before = len(objs)
    # material: PanelGap (matte, no specular in the comparison renders) reads like the photo's black lip in p018 (side lip 14 vs photo 26 of 255, blade 33 vs 17); GlossBlack mirrors the studio's rim / key lights as a grey
    # wedge (blade 68, and a seam where the blade meets the wall).  lod2 drops PanelGap, so it keeps GlossBlack there (-> Trim).
    emit(Ms, 'F_Lip', ctx.arg('f-lipmat', 'Carbon' if level < 2 else 'GlossBlack'), smooth=True, solid=True)      # 2026-10-23: Carbon (the game's clear-coated twill, materials.js 'splitter'; glossy black in p018 / p016)
    lip_ob = objs[n_before] if len(objs) > n_before else None
    if level == 0 and len(edge_P) > 2:                                   # r3: the lip's rounded bottom edge = the thin bright line of p018 / p016, ONE strip from the arch round the nose to the other arch
        Me = Mesh()
        _grid(Me, edge_P, edge_N)
        emit(Me, 'F_LipEdge', ctx.arg('f-edgemat', 'Paint'), smooth=True)      # (tried GlossBlack / Carbon: no line at all; BrakeDisc: 20 % too dim and a new hi draw call; Paint: peak 86-115 vs the photo's 70-112, no new call)
    if lip_ob is not None:
        ctx.mark_sharp(lip_ob.data, 35)                                  # smooth shading, but the top / chamfer / bottom edges stay crisp
        if level == 0:                                                 # orientation check that does not depend on the winding rule: each side quad (ring a, edge b) must face the cross-section's own outward direction
            nk, bad, okc = len(ring_p[0][1]), [], 0
            keep = [b_ for b_ in range(nk) if b_ not in LIP_SKIP]
            for a_ in range(len(ring_p) - 1):
                u_, prm_ = ring_p[a_]
                for j_, b_ in enumerate(keep):
                    o0, z0_ = prm_[b_]
                    o1, z1_ = prm_[(b_ + 1) % nk]
                    want = Vector((u_.x * (-(z1_ - z0_)), u_.y * (-(z1_ - z0_)), o1 - o0))
                    pl = lip_ob.data.polygons[a_ * len(keep) + j_]
                    if pl.normal.dot(want) > 0:
                        okc += 1
                    elif len(bad) < 6:
                        bad.append((round(pl.center.y, 2), round(pl.center.x, 2), round(pl.center.z, 3)))
            counts['F_Lip'] = (okc, (len(ring_p) - 1) * len(keep) - okc, bad)

    # ---- DF-6 / DF-7 panel gaps ---------------------------------------------------------------------------------------------------------------
    D = g.D
    stp = (0.02, 0.04, 0.08)[level]
    GW, GOFF = 0.0030, 0.0007
    Mp = Mesh()

    def gap(pts, w=GW):
        P, N = ribbon(cast, pts, w, GOFF)
        _grid(Mp, P, N)

    n7 = (41, 21, 9)[level]
    gap(L7_arc(g, n7))                                                                      # L7: the front-trunk lid's rear edge, arc, L5 to L5
    ce = g.cv['cowl_edge']
    ycw = float(ce[-1][1]) - 0.004
    gap([(D.COWL_X + 0.0045, -ycw + 2 * ycw * i / 20) for i in range(21)], w=0.0026)       # the cowl line: the windscreen's lower edge (paint stops 4.5 mm in front of the glass)
    for sd in (-1, 1):
        L5 = [tuple(p) for p in g.cv['L5']]
        k0 = 5                                                                              # L5 seam from just behind the corner to the windscreen base
        pts5 = [(p[0], sd * p[1]) for p in L5[k0:]]
        pts5 = pts5[::max(1, int(round(stp / 0.011)))] + [pts5[-1]]
        gap(pts5, w=0.0022)
        # DF-7 the corner flap (p005): a separate small panel, a gap all round.  Left side = L5 (the seam above).  FRONT round 3: the shell's flap is now the plane Q through L5 up to row TRI_K = 33 (design2),
        # so C = L5[33] is the shell's own corner (p005 reads k 33.4) and the surface across the rear seam is flat (0.4 degrees to the fender top, no step): the seam is simply laid on the surface from C to
        # B' = the crest point at x -2.105 (p005 reading; U[23]) moved 8 mm inboard (the photo corner is 23 px inboard of the shell's crest U: 8 mm brings the seam end to 17 px = 0.95 % of W), a constant-x line.  The outer edge runs back along U (just inboard of the crest) to a few cm behind N
        C = L5[D.TRI_K]
        xb = -2.105
        Uc = D.CURVES['U']
        B = [float(v) for v in Uc.at(xb)]
        rear = lerp_pts((C[0], sd * C[1]), (B[0], sd * (B[1] - FLAP_IN)), (16, 8, 4)[level])
        gap(rear, w=0.0024)
        xs_u = [xb + (-2.405 - xb) * i / ((24, 12, 6)[level]) for i in range(((24, 12, 6)[level]) + 1)]
        outer = []
        for xx in xs_u:
            q = [float(v) for v in Uc.at(xx)]
            outer.append((q[0], sd * (q[1] - FLAP_IN)))
        gap(outer, w=0.0024)
    emit(Mp, 'F_PanelGaps', 'PanelGap')
    if level == 0:
        ctx.report('face_normals_out_in', {k: ('%d out / %d in' % v[:2]) + ((' %s' % (v[2],)) if v[1] else '') for k, v in counts.items()})
    return objs
