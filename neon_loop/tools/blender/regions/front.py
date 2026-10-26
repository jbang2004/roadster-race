"""
FRONT region (R2, ported to the accepted R1e3 shell): light bar, black face, intake, lower lip, hood / corner-flap seams.  SPEC section 7, DF-1 .. DF-8.
Interface: REGIONS.md section 2 and regions/ctx.py.  Everything is anchored on the shell's named curves (ctx.A.D.NOSE: xe / Fxy / rake / curves bar_top, bar_bot,
face_black_bot, F_bot, tri, tri_seam, L5, hood_seam_L7, cowl_edge ...); nothing uses the old R1b analytic front (common.hood_z / front_x / build_rows).

  shell_post(ctx)        hi only: the intake pocket cut into the (black) front face of the dense body, after the wheel-arch cut
  build(ctx, level)      level 0 = hi, 1 = lod1, 2 = lod2 -> [objects]

2026-10-25 (QF_FACE_LOW / QF_LIP_LOW, below): the panel ends at z 0.352, the intake reaches down to a LOW lip blade (front-top edge 0.232, bottom 0.175, front raked) with a flush black plate above it at the corners;
the layout below is the 2026-10-24 one (both switches 0).
Layout of the face (top -> bottom, all on the raked, bowed front face of the shell; h = distance below the bar_top edge, z = zN - h, zN = design2.NOSE_ZN = 0.541 since 2026-10-24, 0.510 with QF_NOSE_LOW):
  HeadDRL   the light bar, 16 mm tall, tapering to 1.3 mm at the corner vertex, corner to corner along bar_top (r2: the ONLY lit headlight line)  DF-1
  Paint     the thin body-colour lower lip under the bar (not lit)                                                           DF-1
  GlossBlack the bright-black panel down to face_black_bot (z 0.451), HeadLens dark strips on its upper edge, sensor dot    DF-2 DF-3
  intake    pocket cut into the face (hi) with louvre blades / ribs; liner, blades and the frame strips round it are PanelGap  DF-4
  lip       F_Lip, Carbon (lod2: GlossBlack): ONE black skin under the paint edge (z 0.300): a thin blade across the face stepping down just inboard of the crease into the deep side piece (its
            front end a chamfered chin under N), which runs to the front arch; the rounded lower edge F_LipEdge in the same material;  DF-5
            the face under the blade is recessed (UNDER, hi body)
  PanelGap  L7 hood seam (arc, p013), cowl seam, L5 seam (hood | fender top), corner-flap seams                             DF-6 DF-7
No side-marker parts and no door cut here (they belong to side.py).  No other lamps (DF-8).
Diagnostics (build args): --f-skip F_HeadDRL,F_Lip,...  leaves those parts out;  --f-lipmat <Material>  builds the lip in that material.
"""
import math
import os
import bmesh
from mathutils import Vector
import common as S
import design2 as _D2             # (the shell's design curves; already imported by the build)
from common import Mesh, sstep

NAME = 'front'

# 2026-10-25 FRONT audit (calibrated cameras, CALIB.md).  The face stack below the bar was placed with the old p016 camera (p016_v1: 6.8 / 27.8 px, its vertical scale at the face 13 % too
# large); through the calibrated p016 camera (0.99 px) every edge under the bar is 13-35 px LOWER in the photo than in the model.  Edge heights read in p016 (photo edges unprojected onto the face,
# columns u 290-710; check: the same reading on the baseline render returns the model's own 0.536 / 0.426 / ...):  bar centre 0.501-0.511 (model 0.536), gloss panel lower edge 0.343-0.361 (0.428),
# blade top 0.222-0.235 (0.300), blade bottom 0.172-0.186 (0.262).  p018 agrees where it sees the lip (the near half of the face, |y| 0.4-0.65, is its front-most silhouette): nothing stands out
# of the face at z 0.26-0.29, the black's front-most point is at z ~0.24 and its lower edge at 0.172.  p014 (shapes only): bar -> lip top 1.19x the model's, p016 1.24x.
QF_FACE_LOW = os.environ.get('QF_FACE_LOW', '1') == '1'      # gloss panel / intake / radar moved down to the p016 heights (0: the 2026-10-24 face)
QF_LIP_LOW = os.environ.get('QF_LIP_LOW', '1') == '1'        # the lip as a LOW blade under the intake + a flush black plate at the corners (0: the 2026-10-24 thin blade at z .262-.300 + deep chin)

# ----------------------------------------------------------------------------- dimensions (m)
YB = float(_D2.N[1]) - 0.003    # the bar / panels stop this far from the centre line (the corner crease of the face is at N's |y|: 0.67, 0.70 with design2.QF_NOSE_WIDE)
BAR_H = 0.009                   # light bar height; FRONT r2: no thickening and no droop at the ends, the strip tapers instead (p014: it thins out and stops at the corner vertex).  2026-10-23: 16 -> 9 mm
                                # (p016 column profiles: the white line is 4 px = 9 mm at every x, the model's bright band was 11 px)
BAR_TAPER = 0.92                # the bar is this fraction thinner at the vertex (9 mm -> 0.7 mm) ...
BAR_TAPER_Y0 = 0.42             # ... starting at this |y| (smooth step to YB), the top edge stays level with the hood's front edge
BAR_OFF = 0.0006                # the strip stands this far off the face (it was 1.6 mm: edge-on from the side it showed as a glowing tab)
BAR_TOP_GAP = 0.0008            # the bar starts this far below the hood's front edge
LIP_H = 0.0                     # body-colour lip under the bar.  2026-10-23: none (was 7 mm): p016's grey band under the bar sits 4 px below it with a black gap and fades from 220 to 35 / 255 across the
                                # car while the bar stays at 255: it is the bar's reflection in the raked gloss panel, not a part
BAND_BOT_Z = 0.428              # the panel's lower edge: p016 (refit camera) puts it ~2.3 cm below design2's face_black_bot (z 0.451); 0.115 m of black below the bar + lip
if QF_FACE_LOW:
    BAND_BOT_Z = 0.352          # 2026-10-25: calibrated p016, the panel's lower edge at 0.343-0.361 across the face (median 0.352); was 0.428
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
LIP_ZB_C, LIP_ZB_K, LIP_ZB_SIDE = 0.262, 0.187, 0.168   # lower edge of the lip: across the middle / from the front corner / at the arch.  2026-10-24 (p016 + p018 + p001): a THIN blade across the
                                         # face (3.8 cm: p016 shows the floor and the far tyre under it, p018 sees only 12 px = 4.4 cm of black at the very nose), stepping down at the face's corner into the deep
                                         # side piece (p016: the lower edge's highlight drops between |y| 0.69 and 0.84; p018: down to z 0.19 from 4 cm behind the nose, 0.165 at the arch).  2026-10-23 had ONE
                                         # bar of even height (0.185) all round, read from p018's side alone
LIP_ZB_STEP = (0.64, 0.80)                # (until 2026-10-24) |y| over which the lower edge stepped from LIP_ZB_C to LIP_ZB_K; now from the crease (see LIP_STEP_W): lip_layout()
LIP_STEP_W = 0.11                         # 2026-10-24 (p018: the black is full depth from the front-most end of the lip, z .30 -> .18; p016 near corner: the lower edge steps down just INBOARD of the face's crease and
                                          # is level from the crease on; p003: a tall black piece at the corner): the step from the blade to the deep side piece lies on the face, over this width up to the crease
LIP_P_SIDE = 0.14                         # 2026-10-24: the lip keeps its LIP_P protrusion up to the crease (the deep piece's front end is a chin under N, p018: its lower front 6 cm ahead of the paint corner),
                                          # then fades to the LIP_WALL plate over this much |y| along the side
LIP_CHIN_SLOPE = 0.75                     # 2026-10-24 (p018): the deep piece's top falls from the paint edge to its front by this much per metre of protrusion (a 4.5 cm x 6 cm chamfer); the blade keeps LIP_TOP_SLOPE
LIP_CHIN_IN = 0.06                        # ... starting this far (|y|) inboard of the step
UNDER = dict(y=LIP_ZB_STEP[0], z0=0.10, z1=LIP_ZB_C + 0.003, depth=0.120, zpad=0.02, lean=False)     # the recess under the blade (hi body, like the intake pocket): the black face below the blade is set back 12 cm
                                                                                                    # (its y: the step's start, set in shell_post; vertical sides)
                                                                  # (zpad: only the faces near it are bisected, not the intake's floor above)
LIP_SMOOTH = 0.016              # Gaussian smoothing (m of arc length) of the lip's plan outline: the corner is one rounded sweep
LIP_E = 0.0012                  # offset of the lip's skin from the shell
LIP_IN = 0.005                  # how far the lip's top / bottom inner edges sink into the body (hidden; kept small so the ring does not fold at the corner crease)
LIP_SLOPE_MAX = 0.014           # plan displacement of the shell between the two sample heights beyond which they are taken to lie on different faces
FLAP_IN = 0.008                 # the flap's gap lines (rear seam end, outer edge) lie this far inboard of the crest U (p005)
INTAKE = dict(y=0.645, z0=LIP_ZT + 0.0015, z1=0.428 - 0.0010, depth=0.120)      # pocket in the face: half width, bottom, top, depth towards the tail.  FRONT r3 (p016): the black opening runs from the gloss panel's lower edge
                                                                  # (z 0.428) straight down to the lip (z 0.300): 0.126 m high (photo ~52 px = 0.13 m); it was 0.318 .. 0.420 with a 3.7 cm black frame band under it
# QF_LIP_LOW (2026-10-25, calibrated p016 + p018, see the header): the lip is ONE low blade standing LIP_P out of the face under the intake, its top level, its front raked, wrapping the corners and
# running along the sides to the arch (there it stands LIP_BLADE_SIDE out, under the plate); above it at the corners and along the sides a FLUSH black plate (LIP_WALL) from the paint edge (LIP_ZT) down to
# the blade.  Across the face there is no plate: the intake opening reaches down to the blade.  No chin (p016 far corner: nothing stands out of the crease above the blade; p018: the black's upper part
# is cut back, its front-most point is the blade at z ~0.24).  No recess under the blade (the face ends at z 0.218, the blade's bottom is below it).
if QF_LIP_LOW:
    LIP_ZT = 0.292                        # the paint's lower edge at the corners: p018 0.293 (v 684.3 at x -2.40), p016 0.292 (near chamfer's lower edge, v 777-778); was 0.300 (the old cameras disagreed: 0.27-0.29 / 0.31-0.33)
LIP_BT_C, LIP_BT_K = 0.232, 0.192        # blade top (its front-top edge, the front-most line) across the face / from the crease on: p016 0.229-0.235 across, 0.221 / 0.206 / 0.191 at |y| 0.60 / 0.64 / 0.67
                                          # (the "smile"); p018 / p001: the black's front-most point at z 0.240 / 0.233
LIP_BT_Y0 = 0.58                          # ... the blade top starts to fall here
LIP_ZB_LOW = (0.175, 0.170)               # blade bottom across the face / at the crease (then easing to LIP_ZB_SIDE at the arch): p016 0.172-0.186, p018 0.172 at the nose
LIP_BLADE_SIDE = 0.020                    # along the side the blade still stands this far out of the shell (p016 near side: its bright lower edge under the side plate)
LIP_LOW_SLOPE = 0.0                       # the blade's top is level (the opening's floor meets it)
LIP_LOW_RT = 0.004                        # a crisp top-front edge (4 mm round; the 2026-10-24 lip had 12 mm)
LIP_RAKE = 0.020                          # the blade's front leans back by this much from its top edge to its bottom (at LIP_P; less where it stands out less): the p018 / p001 profiles
                                          # recede 1.5 / 2.5 cm from the front-most point to the bottom; p016: the front catches the key light as a band under the top edge
LIP_CHIN_RAMP = os.environ.get('QF_LIP_RAMP', '0') in ('1', 'arc')   # at the corners the black runs from the paint edge down-forward to the blade's front-top edge (no vertical plate), as the side profiles read it:
                                          # p018 (u, z) 239 / .29 -> 229 / .275 -> 222 / .26 -> 218 / .24 (the blade), p001 219 / .275 -> 208 / .26 -> 198 / .233.  '1' = the straight chamfer of 2026-10-25 (a preview, off: p016's far end
                                          # showed it as a slanted wedge); 'arc' (2026-10-26, FRONT-2: p018 / p001 at 12x: the black's top-front outline is one CONVEX round of ~4 - 5 cm radius, vertical at the paint edge,
                                          # horizontal at the blade top, not a straight chamfer) = a quarter ellipse of those two end points; 0: a flush plate down to the blade
LIP_RAMP_ARC = os.environ.get('QF_LIP_RAMP', '0') == 'arc'
if QF_LIP_LOW:
    _zr_c = LIP_BT_C + LIP_LOW_SLOPE * (LIP_P + LIP_E - LIP_LOW_RT - LIP_WALL)  # the blade top's back edge at the face (centre)
    INTAKE['z0'] = _zr_c + 0.0015                                               # the opening reaches down to the blade (was LIP_ZT + 0.0015 = 0.3015)
if QF_FACE_LOW:
    INTAKE['z1'] = BAND_BOT_Z - 0.0010                                          # (was 0.428 - 0.001)
RADAR_DZ = (0.0665, 0.1125)               # the radar block (DF-4) from INTAKE z0 + these (= z 0.368 .. 0.414 on the 2026-10-24 face; p016 calibrated: 0.286 .. 0.331)


# ----------------------------------------------------------------------------- the shell's front face (design2.NOSE): x = Fxy(y, z), bowed + raked
class Geo:
    def __init__(self, D):
        nz = D.NOSE
        self.D, self.nz = D, nz
        self.xe, self.Fxy = nz['xe'], nz['Fxy']
        self.zN = float(nz['N'][2])
        self.rake = float(nz['rake'])
        self.cv = nz['curves']
        self.fs_k = float(getattr(D, 'QF_FS_K', 0.0))       # 2026-10-24: the face's corner crease leans outward going down (design2.QF_FS_K)

    def sc(self, z):
        """lateral scale of the face at height z: a nominal |y| (measured at the top edge) lies at |y| * sc(z) there, so YB keeps its distance to the leaning crease"""
        return 1.0 + self.fs_k * (self.zN - z) / YB

    def face(self, y, h, off=0.0):
        """(point, outward normal) on the front face at lateral y, h below the top edge, `off` along the normal"""
        z = self.zN - h
        x = float(self.Fxy(y, z))
        e = 1e-3
        dxdy = (float(self.Fxy(y + e, z)) - float(self.Fxy(y - e, z))) / (2 * e)
        dxdz = (float(self.Fxy(y, z + e)) - float(self.Fxy(y, z - e))) / (2 * e)
        n = Vector((-1.0, dxdy, dxdz)).normalized()
        return Vector((x, y, z)) + n * off, n


def lip_layout(g):
    """|y| stations of the lip (2026-10-24): the step blade -> deep side piece ends at the face's crease at the lip's top height, the protrusion fades along the side after it"""
    ycr = float(g.nz['yc'](LIP_ZT)) if 'yc' in g.nz else float(g.nz['N'][1])
    return dict(ycr=ycr, st0=ycr - LIP_STEP_W, st1=ycr - 0.003, p0=ycr, p1=ycr + LIP_P_SIDE)


def geo(ctx):
    g = ctx.cache.get('front_geo')
    if g is None:
        A = getattr(ctx, 'A', None)
        if A is None:                                       # (shell_post runs before the shell interface A exists: the same design2 module the shell was built from)
            import design2 as D2
        g = ctx.cache['front_geo'] = Geo(A.D if A is not None else D2)
    return g


def ys_lin(n, y0=-YB, y1=YB):
    return [y0 + (y1 - y0) * i / (n - 1) for i in range(n)]


def face_strip(g, ys, h0, h1, off, nv=2, lean=True):
    """strip on the front face: rows over y, columns from h0(y) to h1(y) below the top edge.  lean: the nominal y spreads with the leaning crease (y * g.sc(z))"""
    P, N = [], []
    for y in ys:
        a, b = h0(y), h1(y)
        rp, rn = [], []
        for j in range(nv):
            h = a + (b - a) * j / (nv - 1)
            p, n = g.face(y * (g.sc(g.zN - h) if lean else 1.0), h, off)
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
def cut_pocket(ob, I, g):
    """cut the intake out of the front face of the dense mesh: the outline is bisected into the mesh, the enclosed faces are extruded `depth` towards the tail
    (a recess with a floor and four walls, all Trim).  New vertices only; no existing vertex moves.  The side walls lean with the face's crease: |y| = I['y'] * g.sc(z) (planes)."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    lean = I.get('lean', True)
    ky = I['y'] * g.fs_k / YB if lean else 0.0                  # the side plane: |y| = I['y'] + ky (zN - z)
    yw = lambda z: I['y'] * (g.sc(z) if lean else 1.0)

    def region():
        zp = I.get('zpad', 0.15)
        fs = [f for f in bm.faces if f.calc_center_median().x < -2.3 and f.normal.x < -0.4 and abs(f.calc_center_median().y) < I['y'] + 0.15
              and I['z0'] - zp < f.calc_center_median().z < I['z1'] + zp]
        vs = {v for f in fs for v in f.verts}
        es = {e for f in fs for e in f.edges}
        return list(vs) + list(es) + fs
    for co, no in (((0, I['y'], g.zN), (0, 1, ky)), ((0, -I['y'], g.zN), (0, -1, ky)), ((0, 0, I['z0']), (0, 0, 1)), ((0, 0, I['z1']), (0, 0, 1))):
        bmesh.ops.bisect_plane(bm, geom=region(), dist=1e-6, plane_co=co, plane_no=no)
    inner = [f for f in bm.faces if f.calc_center_median().x < -2.3 and f.normal.x < -0.4
             and abs(f.calc_center_median().y) < yw(f.calc_center_median().z) and I['z0'] < f.calc_center_median().z < I['z1']]
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
    zs = [v.co.z for f in caps for v in f.verts]
    zthr = 0.3 * (max(zs) - min(zs)) if zs else 0.04                # (the walls' z test: 0.04 for the 12.6 cm intake; relative, so that the 5 cm recess under the lip works too)
    for f in caps:
        f.material_index = 2
    for f in walls:
        f.material_index = 2
        c = f.calc_center_median()
        want = Vector((0.0, (cen.y - c.y) if abs(c.y) > 0.3 else 0.0, (cen.z - c.z) if abs(c.z - cen.z) > zthr else 0.0))     # a wall faces INTO the pocket
        if f.normal.dot(want) < 0:
            f.normal_flip()
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()
    return len(inner)


def shell_post(ctx):
    """the intake pocket (DF-4) and the recess under the lip's blade (DF-5), hi body only (the LOD bodies are decimated from this one)"""
    if ctx.front_r2:
        g = geo(ctx)
        ctx.report('intake_faces', cut_pocket(ctx.body, INTAKE, g))
        if not QF_LIP_LOW:                                      # (QF_LIP_LOW: the blade is below the face's lower edge, nothing to recess)
            ctx.report('under_lip_faces', cut_pocket(ctx.body, dict(UNDER, y=lip_layout(g)['st0']), g))


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
        yc, zc0, zc1 = (-0.045 if QF_FACE_LOW else -0.125), I0['z1'] - 0.016, I0['z1'] - 0.002      # 2026-10-25: the calibrated p016 puts the box (u 470-487) at y -0.03 .. -0.06 (was -0.125, old camera)
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
        for i in range(25):                                          # (every y below spreads with the leaning crease: y * g.sc(z), as the pocket's side planes)
            y = yl0 + (yl1 - yl0) * i / 24
            P.append([Vector((xfl(y * g.sc(z), z), y * g.sc(z), z)) for z in (zl0 + (zl1 - zl0) * j / 4 for j in range(5))])
            N.append([Vector((-1, 0, 0))] * 5)
        _grid(Ml, P, N)
        for sd in (-1, 1):                                           # side walls, facing the middle
            ywl = lambda z: sd * (I['y'] - E_L) * g.sc(z)
            P = [[Vector((xmo(ywl(z), z), ywl(z), z)), Vector((xfl(ywl(z), z), ywl(z), z))] for z in (zl0 + (zl1 - zl0) * j / 4 for j in range(5))]
            _grid(Ml, P, [[Vector((0, -sd, 0))] * 2] * 5)
        for zw, dn in ((I['z1'] - E_L, -1), (I['z0'] + E_L, 1)):    # top wall faces down, bottom wall faces up
            P = [[Vector((xmo(y, zw), y, zw)), Vector((xfl(y, zw), y, zw))] for y in ((yl0 + (yl1 - yl0) * i / 24) * g.sc(zw) for i in range(25))]
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
        Mr = Mesh()
        xin = lambda y, z, d: float(g.Fxy(y, z)) + d                      # a point d behind the face (towards the tail)
        ys_r = [-0.50 + 0.36 * i / 12 for i in range(13)]
        rings = []
        zr0, zr1 = I['z0'] + RADAR_DZ[0], I['z0'] + RADAR_DZ[1]
        for y_ in ys_r:
            r_ = []
            for zz, dd in ((zr1 - 0.004, 0.050), (zr1, 0.056), (zr1, 0.085), (zr0, 0.085), (zr0, 0.056), (zr0 + 0.004, 0.050)):
                r_.append((xin(y_, zz, dd), y_, zz))
            rings.append(r_)
        _prism(Mr, rings)
        emit(Mr, 'F_IntakeRadar', 'PanelGapDark', smooth=False, solid=True)  # 2026-10-24: the darkest matte (p016: the block reads ~7 / 255, it rendered 19 in PanelGap)
        Mf = Mesh()
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
        z_lip = (I['z0'] - 0.0015) if QF_LIP_LOW else LIP_ZT                 # the top of the lip under the opening
        for (ya, yb, za, zb) in ((-YB, YB, I['z1'], BAND_BOT_Z), (-YB, YB, z_lip - 0.006, I['z0']), (I['y'], YB, I['z0'], I['z1']), (-YB, -I['y'], I['z0'], I['z1'])):
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
            if QF_LIP_LOW and p_ is not None and abs(p_.y) < INTAKE['y'] * g.sc(z) + 0.01 and p_.x > float(g.Fxy(p_.y, z)) + 0.01:
                # (QF_LIP_LOW: the sample heights are inside the intake pocket now; the ray hit its floor: take the front face itself where the ray crosses it)
                lo, hi_ = 0.0, (p_ - o).length
                for _ in range(40):
                    mid = 0.5 * (lo + hi_)
                    q = o - d * mid
                    if q.x > float(g.Fxy(q.y, z)):
                        hi_ = mid
                    else:
                        lo = mid
                q = o - d * (0.5 * (lo + hi_))
                return g.face(q.y, g.zN - z)
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
    ll = lip_layout(g)
    for sd in full:
        b1, b2, u = Vector(sd['b1']), Vector(sd['b2']), Vector(sd['u'])
        ay = abs(b1.y)
        pr = max(LIP_P * (1.0 - float(sstep(ll['p0'], ll['p1'], ay))), LIP_WALL - LIP_E)   # the lip stands out of the face by LIP_P up to the crease (blade, then the deep piece's chin); along the wall a LIP_WALL plate
        zt = LIP_ZT
        wd = float(sstep(ll['st0'], ll['st1'], ay))                       # 0 = the thin blade across the face, 1 = the deep side piece (from the crease on)
        zb = (LIP_ZB_C + (LIP_ZB_K - LIP_ZB_C) * wd                       # thin blade across the face, stepping down just inboard of the crease (2026-10-24) ...
              + (LIP_ZB_SIDE - LIP_ZB_K) * float(sstep(ll['st1'], 1.00, ay)))                # ... and easing to the arch along the wall

        def P(off, z):
            t = min(max((z1 - z) / (z1 - z2), 0.0), 1.0)                # (the shell's slope between the two sample heights; straight down below the lower one)
            q = b1 + (b2 - b1) * t + u * off
            return (q.x, q.y, z)
        e = LIP_E
        if QF_LIP_LOW:                                                    # 2026-10-25: low blade + flush plate (see QF_LIP_LOW)
            pr = max(LIP_P * (1.0 - float(sstep(ll['p0'], ll['p1'], ay))), LIP_BLADE_SIDE)
            wsm = float(sstep(LIP_BT_Y0, ll['ycr'], ay))                  # the smile: the blade falls a little into the corners
            zb = (LIP_ZB_LOW[0] + (LIP_ZB_LOW[1] - LIP_ZB_LOW[0]) * wsm + (LIP_ZB_SIDE - LIP_ZB_LOW[1]) * float(sstep(ll['ycr'], 1.00, ay)))
        ch = min(LIP_R, 0.9 * (pr + e + LIP_IN))                          # bottom chamfer (under the rounded edge strip): never deeper than the lip is thick
        rt = min(LIP_RT, 0.45 * (pr + e + LIP_IN))                        # rounded top-front edge (3 facets of 30 deg), never wider than half the lip's depth
        fb = pr + e                                                       # the front's offset at its bottom (QF_LIP_LOW: raked back)
        if QF_LIP_LOW:
            rt = min(LIP_LOW_RT, rt)
            fb = pr + e - LIP_RAKE * pr / LIP_P
            zto = LIP_BT_C + (LIP_BT_K - LIP_BT_C) * wsm                  # the blade's front-top edge
            zr = zto + LIP_LOW_SLOPE * (pr + e - rt - LIP_WALL)           # its top, at the plate / the face
            zp = max(zr + 0.001, zr + (zt - zr) * float(sstep(ll['st0'], ll['st1'], ay)))      # the plate: none across the face (the opening reaches the blade), the paint edge from the crease on
            angs = (0.0, 30.0, 60.0, 90.0) if level == 0 else (0.0, 90.0)                       # (lod: 2 points, so the ring keeps the 8 points of the 2026-10-24 lip: same budget)
            top = [(pr + e - rt + rt * math.sin(math.radians(a_)), zto - rt + rt * math.cos(math.radians(a_))) for a_ in angs]
            plate = [(LIP_WALL, zp), (LIP_WALL, zr)] if not LIP_CHIN_RAMP else [(LIP_WALL, zp)]       # LIP_CHIN_RAMP: from the paint edge straight down-forward to the blade's front-top edge
            if LIP_RAMP_ARC and level == 0:                                                           # 'arc': a quarter ellipse (a = the lip's depth, b = the paint edge's height over the blade top): vertical at the plate, level at the blade
                _aa, _bb = max((pr + e - rt) - LIP_WALL, 1e-4), max(zp - zto, 1e-3)                     # (the same number of ring points at every station)
                plate = [(LIP_WALL, zp)] + [(LIP_WALL + _aa * (1.0 - math.cos(math.radians(a_))), zp - _bb * math.sin(math.radians(a_))) for a_ in (30.0, 60.0)]
            prm = [(-LIP_IN, zp)] + plate + top + [(fb, zb + ch), (fb - ch, zb), (-LIP_IN, zb)]
        else:
            wc = float(sstep(ll['st0'] - LIP_CHIN_IN, ll['st1'], ay))         # the chamfer starts a little inboard of the step (p018: the side view's front-top corner is cut back)
            zto = zt - min(LIP_CHIN_SLOPE * pr * wc, max(zt - (zb + ch + rt) - 0.004, 0.0))   # 2026-10-24: the deep piece's chin: its top falls from the paint edge to its front edge (p018 chamfer); the blade's front top stays at zt
            slope = LIP_TOP_SLOPE * (1.0 - wc) + LIP_CHIN_SLOPE * wc
            za = zto + slope * (pr + e + LIP_IN - rt)                         # the top of the lip falls towards the front (reads dark, no lit wedge); inside the body / on the wall it is level
            top = [(pr + e - rt + rt * math.sin(math.radians(a_)), zto - rt + rt * math.cos(math.radians(a_))) for a_ in (0.0, 30.0, 60.0, 90.0)]
            prm = [(-LIP_IN, za)] + top + [(pr + e, zb + ch), (pr + e - ch, zb), (-LIP_IN, zb)]
        ring_l.append([P(o_, z_) for o_, z_ in prm])
        ring_p.append((u, prm))
        if level == 0:
            Rr = ch                                                     # 2026-10-20: the strip REPLACES the chamfer (same end lines, no face under it); was ch + 0.3 mm over a kept chamfer: two near-tangent layers z-fought into a jagged edge
            oc, zc = fb - ch, zb + ch
            row_p, row_n = [], []
            for ph_ in (0.0, 30.0, 60.0, 90.0):
                c_, s_ = math.cos(math.radians(ph_)), math.sin(math.radians(ph_))
                row_p.append(Vector(P(oc + Rr * c_, zc - Rr * s_)))
                row_n.append(Vector((u.x * c_, u.y * c_, -s_)))
            edge_P.append(row_p)
            edge_N.append(row_n)
    LIP_SKIP = (len(ring_p[0][1]) - 3,) if level == 0 and ring_p else ()  # hi: the chamfer band (ring edge 5 = the third-last point -> the second-last, after the top round) is covered by F_LipEdge
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
        emit(Me, 'F_LipEdge', ctx.arg('f-edgemat', ctx.arg('f-lipmat', 'Carbon')), smooth=True)      # 2026-10-24: the lip's own material (it was Paint = the livery colour in the game: a coloured pinstripe on the carbon lip;
                                                                                                      # the bright line of p018 is the rounded edge mirroring the floor, which the game's clear-coated Carbon does by itself; the preview's matte Carbon shows no line)
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
