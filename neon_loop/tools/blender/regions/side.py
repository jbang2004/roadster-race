"""
SIDE region: the flank between the wheel arches -- side-marker assembly (blade, reflector, amber lamp, camera) and the carbon side skirt.
Still to come (REGIONS.md section 4): door seams L13, glass splits L8, black arch liners.   Interface: REGIONS.md section 2 and regions/ctx.py.

  build(ctx, level)   level 0 = hi, 1 = lod1, 2 = lod2 -> [objects]:  the skirt always; the side-marker assembly only with --front (as before the split)

The side markers sit behind the top of the front arch (x -1.34 ... -1.00).  Photo 003: a red reflector whose pointed front tip sits on the arch circle, its lower
edge following the arch up to a flat bottom; behind it the gloss-black blade (4.8 cm) with the round camera and, at its rear end, the amber lamp; the top edge is
one straight line from the arch tip down to the door cut.  They are laid on the body by rays, so they inherit whatever the shell does there.
SIDE (like FRONT) casts on ctx.surf_hi at every level, as before the split.
"""
import math, os
import numpy as np
import bpy
from mathutils import Vector
import common as S
import cam as _cam                      # numpy replica of the matched press-photo cameras (Cam(view).ray(px, py))
from common import Mesh, grid, prism, smooth, W_DARK

NAME = 'side'

# the side-marker assembly (R2e): its top edge IS the shell's L curve (ctx.A.D.CURVES['L']), x -1.22 (reflector tip, on the arch circle) ... -0.894 (the door's front cut).
# p018 (near-orthographic, 3.37 mm / px): reflector px 565-604 = x -1.17...-1.03, blade px 604-644 = x -1.03...-0.89
MK_X0 = -1.170                  # the reflector's pointed front tip (p018: the red starts at px 565; the arch circle crosses L at x -1.221, the tyre hides the rest)
MK_BLADE = -1.035               # the blade starts here (p018 px 604: red -> black); p003: the reflector is 0.67 x the blade's length
MK_X1 = -0.894                  # the blade ends at the door's front cut
MK_H = 0.050                    # blade height
REFL_H = 0.70                   # the reflector's greatest height, as a fraction of the blade height (3.5 cm)
MK_AMBER = (-0.985, -0.915)     # the amber strip: along the top edge of the blade's rear half (p003: 41 % ... 87 % of the blade's length)

# door seams, read in p018 (1800 px wide, camera 10 m away: near-orthographic).  Ridge positions measured row by row in the photo (the dark / light hairline of the seam),
# then smoothed ([1 2 1] over the neighbours); the lines are cast from the p018 camera onto the HI body, so they sit exactly where the photo shows them.
P018_FRONT = [(642, 560), (645, 580), (649, 600), (653, 620), (658, 640), (663, 660), (668, 680)]          # front door seam: L (blade's rear end) down to the black zone
P018_REAR = [(1066, 411), (1064, 414), (1062, 417), (1059, 420), (1058, 423), (1056, 428), (1052, 436), (1047, 444), (1043, 452), (1039, 460), (1035, 468), (1031, 476), (1027, 484), (1023, 492),
             (1021, 500), (1017, 520), (1011, 540), (1007, 560), (999, 580), (994, 600), (988, 620), (982, 640), (975, 660)]     # rear seam, continued up the glass as the B-pillar's rear edge
P018_BFRONT = [(1028, 428), (1022, 436), (1015, 444), (1010, 452), (1004, 460), (999, 468), (994, 476), (989, 484), (985, 492)]  # the B-pillar's front edge (a hairline in the glass; the glass between the two lines is NOT filled)
P018_DIAG = [(678, 524), (642, 560)]                   # the front door cut's upper part: the shell crease from the blade's rear top corner up to the A-pillar foot (x + y = 1202 in p018)
BELT_Y = 497.0                  # p018 row of the glass's lower edge (belt) at the B pillar: lines above it lie on the glass
# roof glass splits (DS-6), read in p013 and symmetrised about the centre line; positions are RELATIVE to the glass edge (p013's absolute x has ~10 cm of known slack):
ROOF_X1 = -0.247                # transverse seam 1: its middle section lies at this x ...
ROOF_X1_KINK = 0.182            # ... between |y| = this (where it folds out to the glass edge: x -0.31 at the edge, p013 -0.297 / -0.324)
ROOF_X1_EDGE = -0.310
ROOF_X2 = 0.631                 # transverse seam 2, straight from glass edge to glass edge (p013 0.631; SPEC 0.64); the B pillar's rear line arrives at its ends across the rail
ROOF_LONG = (0.182, 0.099)      # the two longitudinal seams at +-this |y| at x = ROOF_X1 / ROOF_X2 (front 0.364 apart, rear 0.198: SPEC 0.37 / 0.20)
ROOF_W = 0.0045                 # roof seam width (m): 2 px in p013
NOTCH_DX = 0.065                # DS-7: the small U-shaped cut on the shoulder: its rear edge is this far behind the rear door seam (p013 crop: 22 px, p018 stub: 16 px)
NOTCH_REACH = 0.62              # ... and it reaches this fraction of the way from L to the belt (p013: 10 of 16 cm)
SEAM_W = 0.0030                 # hairline width on paint (m); the B-pillar lines in the glass are 2 px = 0.006 wide in the photo
GLASS_W = 0.0060

# skirt: runs from SKIRT_IN behind the front hub to SKIRT_OUT ahead of the rear hub (= 0.082 behind / 0.095 before the arch edges, R_ARCH 0.415)
SKIRT_IN, SKIRT_OUT = 0.497, 0.510


# ----------------------------------------------------------------------------- seams read off a photo
def _emit(ctx, level, objs, M, name, mat, smooth=True):
    if M.empty():
        M.bm.free()
        return
    m = ctx.mat_of(level, mat)
    if m is None:
        M.bm.free()
        return
    objs.append(ctx.mk(M.bm, name, m, smooth))


def _grid(M, P, N):
    """common.grid, but the quads are oriented by their own winding (a new bmesh face has no valid normal yet, so common.grid's flip does nothing): the quad (i,j) (i+1,j) (i+1,j+1) (i,j+1)
    is reversed when its geometric normal points against the sum of the surface normals N.  (Single-sided materials in the game: a wrongly wound strip is invisible.)"""
    nu, nv = len(P), len(P[0])
    V = [[None if P[i][j] is None else M.v(P[i][j]) for j in range(nv)] for i in range(nu)]
    for i in range(nu - 1):
        for j in range(nv - 1):
            q = [(i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1)]
            if any(V[a][b] is None for a, b in q):
                continue
            vs = [V[a][b] for a, b in q]
            nn = sum((N[a][b] for a, b in q), Vector((0, 0, 0)))
            gn = (Vector(vs[1].co) - Vector(vs[0].co)).cross(Vector(vs[3].co) - Vector(vs[0].co)) + (Vector(vs[3].co) - Vector(vs[2].co)).cross(Vector(vs[1].co) - Vector(vs[2].co))
            M.face(vs if gn.dot(nn) >= 0 else vs[::-1])


def _smooth_px(pts):
    """[1 2 1] smoothing of x over the neighbours (the ends stay)"""
    xs = [p[0] for p in pts]
    out = [xs[0]] + [(xs[i - 1] + 2 * xs[i] + xs[i + 1]) / 4.0 for i in range(1, len(xs) - 1)] + [xs[-1]]
    return [(x, p[1]) for x, p in zip(out, pts)]


def photo_line(ctx, view, pts_px, y0, y1, step):
    """polyline [(x_px, y_px)] (a function of y_px, piecewise linear after smoothing) sampled every `step` px of y between y0 and y1; each sample is the camera ray of the matched
    photo cast on the HI body: [(point, normal, y_px)] on the LEFT flank (y < 0), None where the ray misses.  Normals face the camera."""
    cm = _cam.Cam(view)
    sp = _smooth_px(sorted(pts_px, key=lambda p: p[1]))
    ys, xs = [p[1] for p in sp], [p[0] for p in sp]
    n = max(2, int(math.ceil((y1 - y0) / step)) + 1)

    def x_at(y):                                  # linear inside the measured rows, extrapolated with the end slopes outside
        if y < ys[0]:
            return xs[0] + (xs[1] - xs[0]) / (ys[1] - ys[0]) * (y - ys[0])
        if y > ys[-1]:
            return xs[-1] + (xs[-1] - xs[-2]) / (ys[-1] - ys[-2]) * (y - ys[-1])
        return float(np.interp(y, ys, xs))
    out = []
    for i in range(n):
        y = y0 + (y1 - y0) * i / (n - 1)
        o, d = cm.ray(x_at(y), y)
        p, nn = ctx.surf_hi.cast(Vector(o), Vector(d), 0.0, 40.0)
        out.append((p, nn, y) if p is not None and p.y < 0 else None)
    return out


def _mir(p, sd):
    """left-flank point / normal -> side sd (-1 = left, +1 = right: mirror y)"""
    return p if sd < 0 else Vector((p.x, -p.y, p.z))


def strip_along(cast, cl, sd, width, off):
    """hairline along the centre line cl (list of (point, normal, y_px) on the left flank; width = metres or a function of y_px), laid on the surface: the two edges are the
    centre line moved +-width / 2 across (tangent x normal) and re-cast onto the body along the normal.  -> (P, N) for common.grid"""
    cl = [(_mir(p, sd), _mir(n, sd), y) for p, n, y in cl if p is not None]
    P, N = [], []
    for i, (c, n, y) in enumerate(cl):
        a, b = cl[max(i - 1, 0)][0], cl[min(i + 1, len(cl) - 1)][0]
        t = (b - a).normalized()
        w = t.cross(n).normalized()
        wd = width(y) if callable(width) else width
        rp, rn = [], []
        for s_ in (-0.5, 0.5):
            q = c + w * (s_ * wd)
            p, nn = cast(q + n * 0.02, -n, off, 0.06)
            if p is None:
                p, nn = q + n * off, n
            rp.append(p)
            rn.append(nn)
        P.append(rp)
        N.append(rn)
    return P, N


def _resample(pts, step):
    """dense polyline through all the corners of pts [(x, y)], spacing <= step"""
    out = [pts[0]]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        n = max(1, int(math.ceil(math.hypot(x1 - x0, y1 - y0) / step)))
        out += [(x0 + (x1 - x0) * i / n, y0 + (y1 - y0) * i / n) for i in range(1, n + 1)]
    return out


def plan_line(ctx, pts_xy, step, sd=-1):
    """plan polyline [(x, y)] (y as given; sd = +1 mirrors it) cast straight down onto the HI body: [(point, normal, None)]"""
    out = []
    for x, y in _resample(pts_xy, step):
        p, nn = ctx.surf_hi.cast((x, y * (-sd if sd > 0 else 1), 2.5), (0, 0, -1), 0.0, 5.0)
        out.append((p, nn, None) if p is not None else None)
    return out


def roof_splits(ctx, level):
    """DS-6: the glass roof's split lines (hairlines on the glass, PanelGap): seam 1 at x -0.247 folded out to the glass edge (three sections), seam 2 at x 0.631, and two
    longitudinal seams between them that close in towards the back.  Defined in plan from p013 (symmetrised, relative to the glass edge 'gedge'), cast down onto the glass."""
    objs = []
    cast = ctx.surf_hi.cast
    ge = ctx.A.D.CURVES['gedge']
    step = (0.02, 0.12, 0.25)[level]
    off = (0.0010, 0.0040, 0.0050)[level]
    w = ROOF_W * (1.0, 1.4, 1.7)[level]

    def half(x):
        return float(ge.at(x)[1]) - 0.004
    lines = {
        'RoofSeam1': [(ROOF_X1_EDGE, half(ROOF_X1_EDGE)), (ROOF_X1, ROOF_X1_KINK), (ROOF_X1, -ROOF_X1_KINK), (ROOF_X1_EDGE, -half(ROOF_X1_EDGE))],
        'RoofSeam2': [(ROOF_X2, half(ROOF_X2)), (ROOF_X2, -half(ROOF_X2))],
        'RoofSeamL': [(ROOF_X1, ROOF_LONG[0]), (ROOF_X2, ROOF_LONG[1])],
        'RoofSeamR': [(ROOF_X1, -ROOF_LONG[0]), (ROOF_X2, -ROOF_LONG[1])],
    }
    for nm, pts in lines.items():
        M = Mesh()
        P, N = strip_along(cast, [c for c in plan_line(ctx, pts, step) if c is not None], -1, w, off)
        _grid(M, P, N)
        _emit(ctx, level, objs, M, nm, 'PanelGap')
    return objs


def door_notches(ctx, level):
    """DS-7: the small U-shaped cut on each shoulder at the top of the rear door seam (p013: two vertical lines and a rounded bottom hanging from the body edge L; the left one
    is the seam itself).  Here: the cut's rear edge, NOTCH_DX behind the seam, from L inboard to NOTCH_REACH of the way to the belt, closed back to the seam with a rounded corner."""
    objs = []
    cast = ctx.surf_hi.cast
    sh = [c for c in photo_line(ctx, 'p018', P018_REAR, BELT_Y, 523.0, 1.5) if c is not None]       # the seam's shoulder part, belt -> L
    if len(sh) < 6:
        return objs
    sh.reverse()                                                                # L -> belt
    seg = [(c[0].x, c[0].y) for c in sh[:int(NOTCH_REACH * (len(sh) - 1)) + 1]]
    xe, ye = seg[-1]
    r = 0.012
    edge = [(x + NOTCH_DX, y) for x, y in seg if y <= ye - r]               # left-flank coordinates: y < 0, inboard = towards +y
    cx, cy = xe + NOTCH_DX - r, ye - r
    arc = [(cx + r * math.cos(a), cy + r * math.sin(a)) for a in [0.5 * math.pi * i / 5 for i in range(6)]]
    pts = edge + arc + [(xe, ye)]
    for sd in (-1, 1):
        pl = []
        for x, y in _resample(pts, 0.008):
            p, nn = cast((x, y if sd < 0 else -y, 2.5), (0, 0, -1), 0.0, 5.0)
            pl.append((p, nn, None) if p is not None else None)
        M = Mesh()
        P, N = strip_along(cast, [c for c in pl if c is not None], -1, SEAM_W * (1.0, 1.5, 1.8)[level], (0.0008, 0.0035, 0.0045)[level])
        _grid(M, P, N)
        _emit(ctx, level, objs, M, 'DoorNotch_%d' % sd, 'PanelGap')
    return objs


def door_seams(ctx, level):
    """DS-1 / DS-2 / DS-7: the front door cut (black zone up to the blade's rear end, then the shell crease diagonally up to the A-pillar foot), the rear door seam, continued
    up through the shoulder (the small cuts of the top view), the belt and the glass as the rear edge of the B pillar, across the roof rail; and the B pillar's front edge in
    the glass.  The B pillar is only these two hairlines (the glass between them stays glass).  Lines come from p018 (photo_line); right side = mirror."""
    objs = []
    cast = ctx.surf_hi.cast
    step = (5.0, 14.0, 30.0)[level]
    off = (0.0008, 0.0035, 0.0045)[level]
    k = (1.0, 1.5, 1.8)[level]                    # hairlines are thicker at the LODs (they must survive the decimated body)

    def width(y):                                 # 3 mm on paint, 6 mm in the glass (above the belt), blended over 14 px
        t = min(max((BELT_Y + 7.0 - y) / 14.0, 0.0), 1.0)
        return k * (SEAM_W + (GLASS_W - SEAM_W) * t)
    lines = (('DoorSeamFront', photo_line(ctx, 'p018', P018_FRONT, 560, 686, step)),
             ('DoorCutDiag', photo_line(ctx, 'p018', P018_DIAG, 524, 561, step * 0.7)),
             ('DoorSeamRear', photo_line(ctx, 'p018', P018_REAR, 409, 682, step)),
             ('BPillarFront', photo_line(ctx, 'p018', P018_BFRONT, 424, 499, step * 0.7)))
    for sd in (-1, 1):
        for nm, cl in lines:
            M = Mesh()
            P, N = strip_along(cast, [c for c in cl if c is not None], sd, width, off)
            _grid(M, P, N)
            _emit(ctx, level, objs, M, '%s_%d' % (nm, sd), 'PanelGap')
    if level == 0:
        objs += door_notches(ctx, level)
    return objs


# ----------------------------------------------------------------------------- side markers
def side_markers(ctx, level):
    cast = ctx.surf_hi.cast
    objs = []

    def emit(M, name, mat, smooth=True):
        if M.empty():
            M.bm.free()
            return
        m = ctx.mat_of(level, mat)
        if m is None:
            M.bm.free()
            return
        objs.append(ctx.mk(M.bm, name, m, smooth))

    Lc = ctx.A.D.CURVES['L']

    def mk_top(x):
        return float(Lc.at(x)[2])                 # the marker's top edge is the shell's L curve

    def arch_z(x):
        return ctx.HUB_Z + math.sqrt(max(ctx.R_ARCH ** 2 - (x - ctx.HUBS[0][0]) ** 2, 0.0))

    for sd in (-1, 1):
        x_end = MK_X1 - 0.004
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
        _grid(Mk, P, N)
        emit(Mk, 'SideBlade_%d' % sd, 'GlossBlack')
        # reflector: a thin dark-red wedge, no taller than the blade (p018: the red is about 9 px = 3 cm high, the blade 4.6 cm).  Top edge = the blade's (L); the lower edge drops
        # from the front tip to REFL_H x the blade height 55 % of the way back, then runs flat to the blade
        Mr = Mesh()
        P, N = [], []
        for u in (0.0, 0.12, 0.25, 0.37, 0.49, 0.62, 0.75, 0.88, 1.0):
            x = MK_X0 + 0.001 + (x_blade - MK_X0 - 0.001) * u
            zt_ = mk_top(x) - 0.002
            b = REFL_H * min(u / 0.55, 1.0)
            zb = zt_ - max(b, 0.04) * MK_H
            zb = min(zb, zt_ - 0.002)
            rp, rn = [], []
            for t in (0.0, 1.0):
                p, nn = cast((x, sd * 2.5, zt_ + (zb - zt_) * t), (0, -sd, 0), 0.0017)
                rp.append(p)
                rn.append(nn)
            P.append(rp)
            N.append(rn)
        _grid(Mr, P, N)
        emit(Mr, 'SideReflector_%d' % sd, 'Reflector')     # (the red reflector: fixed dark red, not lit, not livery-tinted; dropped at the LODs)
        if level == 0:
            # amber lamp: a thin lit slot along the top of the blade near its rear end
            Ma = Mesh()
            P, N = [], []
            for i in range(9):
                x = MK_AMBER[0] + (MK_AMBER[1] - MK_AMBER[0]) * i / 8
                rp, rn = [], []
                for t in (0.0, 1.0):
                    p, nn = cast((x, sd * 2.5, mk_top(x) - 0.0075 - 0.0075 * t), (0, -sd, 0), 0.0021)
                    rp.append(p)
                    rn.append(nn)
                P.append(rp)
                N.append(rn)
            _grid(Ma, P, N)
            emit(Ma, 'SideLamp_%d' % sd, 'SideMarker')
            # round side camera on the blade
            Mc = Mesh()
            xc = MK_BLADE + 0.012
            p, nn = cast((xc, sd * 2.5, mk_top(xc) - MK_H * 0.55), (0, -sd, 0), 0.0)
            if p is not None:
                rings = []
                for r_, dy in ((0.0105, 0.0), (0.0105, 0.004), (0.0075, 0.0058)):
                    rings.append([(p.x + r_ * math.cos(a), p.y + sd * dy, p.z + r_ * math.sin(a)) for a in [2 * math.pi * i / 14 for i in range(14)]])
                prism(Mc, rings)
            emit(Mc, 'SideCamera_%d' % sd, 'Trim', smooth=True)
    return objs


# ----------------------------------------------------------------------------- side skirt
def body_side(surf, x, s):
    """[(z, y)] of the body side at station x on side s (+1 right / -1 left), from the lowest outward-facing hit up."""
    out = []
    z = 0.05
    while z < 0.45:
        p, n = surf.cast((x, s * 1.6, z), (0, -s, 0), 0.0, 3.0)
        if p is not None and abs(n.y) > 0.25:
            out.append((z, p.y))
        z += 0.004
    return out


def _interp(prof, z):
    if z <= prof[0][0]:
        return prof[0][1]
    for (z0, y0), (z1, y1) in zip(prof, prof[1:]):
        if z <= z1:
            return y0 + (y1 - y0) * (z - z0) / max(z1 - z0, 1e-9)
    return prof[-1][1]



def build_skirt(ctx, level):
    """thin black skirt along the sill between the arches, with a small outward lip at the bottom."""
    cb = ctx.CB()
    x0, x1 = round(ctx.HUBS[0][0] + SKIRT_IN, 6), round(ctx.HUBS[2][0] - SKIRT_OUT, 6)      # -0.99 .. 1.10 for hubs at -1.487 / 1.61
    nx = (60, 16, 8)[level]
    rows = (0.0, 0.33, 0.66, 1.0) if level == 0 else (0.0, 1.0)
    for s in (-1, 1):
        secs = []
        for i in range(nx):
            x = x0 + (x1 - x0) * i / (nx - 1)
            prof = body_side(ctx.surf_hi, x, s)
            if len(prof) < 3:
                continue
            zb = prof[0][0]
            end = min(smooth(x0, x0 + 0.12, x), smooth(x1, x1 - 0.12, x))
            H = (0.080 + 0.028 * smooth(-1.0, 1.1, x)) * (0.55 + 0.45 * end)
            off, lip = 0.003 + 0.007 * end, 0.026 * end
            yb = _interp(prof, zb)
            sec = [(x, yb - s * 0.03, zb - 0.004), (x, yb + s * (off + lip), zb - 0.010), (x, yb + s * (off + lip), zb - 0.002)]
            z = zb
            for f in rows:
                z = zb + 0.004 + f * H
                sec.append((x, _interp(prof, z) + s * off, z))
            sec.append((x, _interp(prof, z + 0.004) + s * 0.0005, z + 0.004))
            secs.append(sec)
        if len(secs) > 1:
            cb.prism(secs, [W_DARK] * (len(secs[0]) - 1))
    me = cb.mesh('Skirt', keep_color=False)
    ob = bpy.data.objects.new('Skirt', me)
    ctx.link(ob)
    me.materials.append(ctx.mat('Carbon' if level < 2 else 'Trim'))
    ctx.mark_sharp(me, 40)
    return ob


def build(ctx, level):
    objs = []
    if not (ctx.oldbody or not ctx.front_r2 or os.environ.get('NO_FRONT')):
        objs += side_markers(ctx, level)
        objs += door_seams(ctx, level)
        objs += roof_splits(ctx, level)
    objs.append(build_skirt(ctx, level))
    return objs
