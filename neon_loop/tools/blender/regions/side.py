"""
SIDE region: the flank between the wheel arches -- side-marker assembly (blade, reflector, amber lamp, camera) and the carbon side skirt.
Still to come (REGIONS.md section 4): door seams L13, glass splits L8, black arch liners.   Interface: REGIONS.md section 2 and regions/ctx.py.

  build(ctx, level)   level 0 = hi, 1 = lod1, 2 = lod2 -> [objects]:  the skirt always; the side-marker assembly only with --front (as before the split)

The side-marker assembly sits on L behind the front arch (x -1.19 ... -0.90, DS-3, constants MK_*): an angular gloss-black housing with a forward-pointing tip, the red
reflector in its front part, the camera lens behind it, a rib, the faceted rear cover and the amber line under its top edge (photo 003).  It is laid on the body by rays,
so it inherits whatever the shell does there.
SIDE (like FRONT) casts on ctx.surf_hi at every level, as before the split.
"""
import math, os
import numpy as np
import bpy
from mathutils import Vector
import common as S
import cam as _cam                      # numpy replica of the matched press-photo cameras (Cam(view).ray(px, py))
from common import Mesh, grid, smooth, W_DARK

NAME = 'side'

# the side-marker assembly (DS-3).  2026-10-25 rebuild from the p003 close-up; x and z from the near-orthographic side views p018 / p001 and the CALIB landmarks
# DFJ (-0.896, 1.064, 0.739) = the top-rear corner and FMc (-1.144, 1.075, 0.657) = the front-lower corner.  ONE angular gloss-black housing: a forward-pointing tip on L, the top
# edge along L (ctx.A.D.CURVES['L']) to the door's front cut, the rear edge down the cut, a straight bottom edge rising rearward to FMc, a straight front edge parallel to the arch
# back up to the tip.  A raised rim (chamfered outer edge) frames a floor holding, front to rear: the red reflector (a trapezoid with prismatic ridges), the camera lens, a diagonal
# rib, and the smoked rear cover (two facets) with the amber line under its top edge.  p003 against p018 / p001 puts the red's edges 2 cm further forward than the housing's at
# the same depth: the reflector / lens sit ~2 cm deeper than the housing's edge.  The body can't be cut here, so the floor is only 0.6 mm under the rim's top and every x below is
# the side views' x (which is also where p003 shows the red: the model's flank there is 2.5 cm outboard of DFJ / FMc, |y| 1.090 / 1.100 against 1.064 / 1.075).
# (until 2026-10-24: MK_TIP -1.197, full height MK_H 0.050 from MK_FULL -1.140 (bottom z 0.664 there), a flat plate with a plain red rectangle MK_REFL (-1.136, -1.037) inset (0.004, 0.007),
#  the camera at MK_CAM_X -0.928 in the lower rear, the amber MK_AMBER (-0.985, -0.915) at MK_AMBER_Z (0.0035, 0.0065) below L)
MK_TIP = -1.190                 # (was -1.197) the tip on L: p018 -1.1875, p001 -1.190, p003 -1.190 (on |y| 1.075)
MK_X1 = -0.894                  # the housing ends at the door's front cut (DFJ x -0.896; its top-rear corner is MK_X1 - 0.004)
MK_FMC = (-1.144, 0.657)        # (new) the front-lower corner (x, z) = CALIB FMc (was x -1.140, z 0.664)
MK_HR = 0.054                   # (was MK_H 0.050) the housing's height at the door cut (p003 62 px = 5.7 cm, p018 16.7 px = 5.6 cm)
MK_LEAN = 0.010                 # the rear edge leans back this much top -> bottom, with the door cut (p018 1.1 cm, p003 1.7 cm, CALIB DS_front 0.6 cm)
MK_R_F = 0.006                  # the front-lower corner is cut back this far along both edges (p003: rounded)
MK_RIM = (0.004, 0.005, 0.005)  # rim width at the top, rear, bottom (p003 3.5 - 5 px); at the front the rim runs back to the reflector (MK_REFL_DX)
MK_RIM_C = 0.0018               # the rim's outer chamfer
MK_O = (0.0010, 0.0020, 0.0014)  # offsets off the body along its normal (m): rim edge, rim top, floor (the rim's chamfers tilt <= 30 deg: steeper, the studio's rim light ran along the top edge as a white line)
MK_REFL_DX = 0.026              # the reflector's front edge (parallel to the housing's): this far behind it in x (p018 / p001: 3.3 cm at its top, 1.9 - 2.5 at mid height; p003 1.8 - 2.0)
MK_REFL_X1 = (-1.043, -1.046)   # the reflector's rear edge at its top / bottom (p018 -1.042, p001 -1.043; p003: leans forward 3 - 7 mm)
MK_REFL_B = (0.0, 0.005)        # the reflector's bottom edge above the floor's at its front / rear end (p003: the black under it widens rearward 5 -> 10 mm)
MK_REFL_RIDGES = 8              # prismatic ridges across the reflector (hi), parallel to its front edge ...
MK_REFL_RH = 0.0003             # ... this high
MK_CAM = (-1.015, 0.0115, 0.0072, 0.0016)  # the lens (was MK_CAM_X -0.928, low in the rear): centre x (p003 1034 px: 2.8 cm behind the red's edge), bezel / glass radius (p003 26 / 17 px), bezel height
MK_DIV = (-0.999, -0.975)       # the diagonal rib between the camera and the rear cover: x at the floor's bottom / top edge (p003 (1047, 427) -> (1067, 385), at the red's depth)
MK_COVER_H = 0.0018             # the rear cover's two facets rise this much to their ridge, which runs parallel to the rib (they tilt fore / aft only: a pyramid's down-facing
                                # facet mirrored the studio's lit floor as a grey triangle in p016)
MK_AMBER = (-0.972, -0.907)     # (was -0.985 .. -0.915) the amber line along the top of the rear cover, from just behind the rib (p003 1070 -> 1133 px) to 1 cm before the top-rear corner
MK_AMBER_Z = (0.0042, 0.0078)   # (was 0.0035 .. 0.0065) ... this far below L (p003: 3.5 - 4 px thick under a 3 - 4 px black lip)
# 2026-10-26 (MID-2, QF_MID_MK): the housing's top edge is NOT on L.  p003 (a close, sharp view along the flank, landmark residuals <= 2 px) reads the black housing's upper boundary at z 0.679 / 0.692 / 0.710 / 0.729 / 0.737
# at x -1.28 / -1.19 / -1.08 / -0.95 / -0.89 (rays onto |y| 1.07): a straight line of slope 0.149 - 0.157 through DFJ (-0.896, 0.739), which at the tip stands 1.5 cm below L (L's slope there is 0.107; 1.9 cm at
# x -1.28, 0.3 cm at x -0.89).  L itself stays (DFJ -0.5 mm; FMc and the phase-2 L_side fit within 0.3 cm; p018's traced L is 1.2 - 1.5 cm low only because p018's camera sits ~4 px off the landmarks over z 0.3 - 1.0:
# l3 shows the same +4 px, DFJ / DS1b / DS2b -3.9 / -3.9 / -5.2 px).  The tip is lowered by MK_TIP_DZ below L; the top edge, the amber line (it follows the top edge) and everything inset from them move with it.  QF_MID_MK=0: on L.
QF_MID_MK = os.environ.get('QF_MID_MK', '1') == '1'
MK_TIP_DZ = 0.016               # the tip T stands this far below L (p003 15.3 mm at x -1.19, p018 15 - 19 mm)

# door seams, read in p018 (1800 px wide, camera 10 m away: near-orthographic).  Ridge positions measured row by row in the photo (the dark / light hairline of the seam),
# then smoothed ([1 2 1] over the neighbours); the lines are cast from the p018 camera onto the HI body, so they sit exactly where the photo shows them.
P018_FRONT = [(642, 560), (645, 580), (649, 600), (653, 620), (658, 640), (663, 660), (668, 680)]          # front door seam: L (blade's rear end) down to the black zone
P018_REAR = [(1066, 411), (1064, 414), (1062, 417), (1059, 420), (1058, 423), (1056, 428), (1052, 436), (1047, 444), (1043, 452), (1039, 460), (1035, 468), (1031, 476), (1027, 484), (1023, 492),
             (1021, 500), (1017, 520), (1011, 540), (1007, 560), (999, 580), (994, 600), (988, 620), (982, 640), (975, 660)]     # rear seam, continued up the glass as the B-pillar's rear edge
P018_BFRONT = [(1028, 428), (1022, 436), (1015, 444), (1010, 452), (1004, 460), (999, 468), (994, 476), (989, 484), (985, 492)]  # the B-pillar's front edge (a hairline in the glass; the glass between the two lines is NOT filled)
P018_DIAG = [(678, 524), (642, 560)]                   # the front door cut's upper part: the shell crease from the blade's rear top corner up to the A-pillar foot (x + y = 1202 in p018)
# the door glass' front frame (2026-10-24, user: "分隔线也加上"): two parallel hairlines in the side glass from the belt to the roof rail, like the B pillar's pair -- the front one continues
# the door cut's diagonal (it starts at P018_DIAG's top), the rear one 32 px (~12 cm) behind it; p016 and p013 show the same pair on the near side.  Ridge of the dark line, read row by row.
P018_QF1 = [(784.0, 436), (773.3, 444), (762.0, 452), (751.3, 460), (740.8, 468), (730.8, 476), (721.3, 484), (712.2, 492), (703.3, 500), (694.8, 508), (686.6, 516), (678.9, 524)]
P018_QF2 = [(802.6, 440), (792.0, 448), (781.9, 456), (772.2, 464), (763.0, 472), (754.2, 480), (745.9, 488), (737.8, 496), (729.9, 504), (722.2, 512), (714.8, 520), (711.2, 524)]
BELT_Y = 497.0                  # p018 row of the glass's lower edge (belt) at the B pillar: lines above it lie on the glass
# the camera the traces are cast with.  The front lines (DoorSeamFront, DoorCutDiag, DoorGlassFront*) stay on the old p018_v1: cast with it they meet the shell's L crease at DFJ
# (the calibrated p018 has a 4 px residual there; it would drop their junction 1.8 cm below L).  2026-10-25: the rear seam, the B pillar's front line and the DS-7 notches use the
# calibrated p018 (was p018_v1): cast with p018_v1 they sat 13 - 20 mm ahead of CALIB's 4-view DS_rear line (5 - 7 px ahead of the photo's in the calibrated p018 render), now 6 - 13 mm behind it
P018_CAM_REAR = 'p018'
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
SEAL_W = 0.009                  # the window's black seal under the pillar / roof-rail band (p018: 2 - 3 px)
SEAL_TIP = 0.35                 # ... at most this fraction of the glass' height (it tapers into the window's two tips)

# skirt (DS-4): runs from SKIRT_IN behind the front hub to SKIRT_OUT ahead of the rear hub.  2026-10-25 (p018 / p001 / p017 / p003): the carbon panel runs from x -1.085 (2 cm
# behind the front arch at its top) to x 1.19 and from z 0.115 (its lip at the front: p018 0.119, p003 0.10 - 0.12, p001 0.115) to 0.225 (p003 0.22 - 0.23): 7 cm lower than the
# body's lowest side face; its lip rises towards the rear wheel (p017: lip highlights 1.5 cm higher at x 1.1 than at the front)
SKIRT_IN, SKIRT_OUT = 0.402, 0.420      # (was 0.497, 0.510: x -0.99 .. 1.10)
SKIRT_Z = (0.115, 0.140, 0.225)         # (new) the lip's bottom at the front / rear end, the panel's top edge (was: the body's lowest side face zb - 0.010 .. zb + 0.084 - 0.112)
SKIRT_LIP = 0.012                       # (was 0.026) the lip's outward step
SKIRT_OFF = 0.006                       # (was 0.003 - 0.010) the face's stand-off from the body at its top edge


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
    sh = [c for c in photo_line(ctx, P018_CAM_REAR, P018_REAR, BELT_Y, 523.0, 1.5) if c is not None]       # the seam's shoulder part, belt -> L
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
    the glass.  The B pillar is only these two hairlines (the glass between them stays glass); so is the door glass' front frame (P018_QF1 / QF2).  Lines come from p018 (photo_line);
    right side = mirror."""
    objs = []
    cast = ctx.surf_hi.cast
    step = (5.0, 14.0, 30.0)[level]
    off = (0.0008, 0.0035, 0.0045)[level]
    k = (1.0, 1.5, 1.8)[level]                    # hairlines are thicker at the LODs (they must survive the decimated body)

    def width(y):                                 # 3 mm on paint, 6 mm in the glass (above the belt), blended over 14 px
        t = min(max((BELT_Y + 7.0 - y) / 14.0, 0.0), 1.0)
        return k * (SEAM_W + (GLASS_W - SEAM_W) * t)
    lines = (('DoorSeamFront', photo_line(ctx, 'p018_v1', P018_FRONT, 560, 686, step)),
             ('DoorCutDiag', photo_line(ctx, 'p018_v1', P018_DIAG, 524, 561, step * 0.7)),
             ('DoorSeamRear', photo_line(ctx, P018_CAM_REAR, P018_REAR, 409, 682, step if level else 1.5)),      # (hi: dense, or its quads sink into the rounded roof-rail band it crosses)
             ('BPillarFront', photo_line(ctx, P018_CAM_REAR, P018_BFRONT, 424, 499, step * 0.7)))
    glass = (('DoorGlassFront', photo_line(ctx, 'p018_v1', P018_QF1, 437, 525, step * 0.7)),        # the door glass' front frame: wholly in the glass (its belt is lower than BELT_Y)
             ('DoorGlassFront2', photo_line(ctx, 'p018_v1', P018_QF2, 441, 525, step * 0.7)))
    for sd in (-1, 1):
        for nm, cl in lines + glass:
            M = Mesh()
            P, N = strip_along(cast, [c for c in cl if c is not None], sd, k * GLASS_W if nm.startswith('DoorGlass') else width, off)
            _grid(M, P, N)
            _emit(ctx, level, objs, M, '%s_%d' % (nm, sd), 'PanelGap')
    if level == 0:
        objs += door_notches(ctx, level)
    return objs


def window_seal(ctx, level):
    """the side window's black seal along its upper edge (2026-10-24, user: "A柱到顶梁似乎都缺少了点钢柱的立体感"): in p018 a near-black line 2 - 3 px (7 - 11 mm) wide runs between the
    pillar / roof-rail band and the door glass all along the glass' upper edge wl (luminance 1 - 10 against the glass' 25 - 45 and the band's 160 - 250; shallower along the A pillar,
    where the glass reflects brightly); p016 shows it too.  It separates the beam from the glass.  A PanelGap strip on the glass from wl SEAL_W down the glass' rulings (wl -> U),
    at most SEAL_TIP of the glass' height towards the two tips; cast onto the HI body like the seams."""
    objs = []
    D = ctx.A.D
    wl, U = D.CURVES['wl'], D.CURVES['U']
    step = (0.008, 0.025, 0.05)[level]
    off = (0.0008, 0.0035, 0.0045)[level]
    k = (1.0, 1.25, 1.5)[level]
    xs = np.arange(float(wl.x0), float(wl.x1) - 0.004, step)
    gh = np.array([float(wl.at(x)[2] - U.at(x)[2]) for x in xs])
    xs = xs[gh > 0.002]                                                      # from the glass' front tip (the pillar foot is paint)
    cl = []
    for x in xs:
        a, u = np.asarray(wl.at(x), float), np.asarray(U.at(x), float)
        d = u - a
        h = float(np.linalg.norm(d))
        d /= h
        t = np.asarray(wl.at(x + 1e-3), float) - np.asarray(wl.at(x - 1e-3), float)
        n = np.cross(t, d)
        n *= np.sign(n[1]) / np.linalg.norm(n)                               # outward (+y on the design side)
        ww = min(k * SEAL_W, SEAL_TIP * h)
        c = a + d * (0.5 * ww)
        cl.append((Vector((c[0], -c[1], c[2])), Vector((n[0], -n[1], n[2])), ww))   # left flank (strip_along mirrors for the right)
    for sd in (-1, 1):
        M = Mesh()
        P, N = strip_along(ctx.surf_hi.cast, cl, sd, lambda w: w, off)
        _grid(M, P, N)
        _emit(ctx, level, objs, M, 'WindowSeal_%d' % sd, 'PanelGap')
    return objs


# ----------------------------------------------------------------------------- side markers
def _isect(p, d, q, e):
    """intersection of the 2D lines p + t d and q + s e"""
    t = ((q[0] - p[0]) * e[1] - (q[1] - p[1]) * e[0]) / (d[0] * e[1] - d[1] * e[0])
    return (p[0] + t * d[0], p[1] + t * d[1])


def _inset(poly, ds):
    """corners of the closed polygon poly [(x, z)] (clockwise seen from the left: x aft, z up) with edge i (poly[i] -> poly[i + 1]) moved inward by ds[i]"""
    lines = []
    for i, a in enumerate(poly):
        b = poly[(i + 1) % len(poly)]
        d = (b[0] - a[0], b[1] - a[1])
        l = math.hypot(*d)
        lines.append(((a[0] + d[1] / l * ds[i], a[1] - d[0] / l * ds[i]), d))     # (clockwise: the inside is to the right of each edge)
    return [_isect(*lines[i - 1], *lines[i]) for i in range(len(poly))]


def _lerp(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def _split(pts, n):
    """the open polyline pts [(x, z)] cut into n segments (one per edge at least, the rest by length), its corners kept: n + 1 points"""
    ls = [math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:])]
    k = [1] * len(ls)
    for _ in range(n - len(ls)):
        i = max(range(len(ls)), key=lambda j: ls[j] / k[j])
        k[i] += 1
    out = [pts[0]]
    for a, b, m in zip(pts, pts[1:], k):
        out += [_lerp(a, b, j / m) for j in range(1, m + 1)]
    return out


def _z_on(a, b, x):
    """z of the 2D line through a and b at x"""
    return a[1] + (b[1] - a[1]) * (x - a[0]) / (b[0] - a[0])


def _face(M, vs, want):
    """a face through the bmesh verts vs, wound so that its normal points along want (a new bmesh face has no normal yet: common.Mesh.face's flip can't do it)"""
    P = [Vector(v.co) for v in vs]
    n = Vector((0.0, 0.0, 0.0))
    for a, b in zip(P, P[1:] + P[:1]):
        n += a.cross(b)                                              # (Newell: the area vector)
    return M.face(vs if n.dot(Vector(want)) >= 0 else vs[::-1])


def marker_outline(ctx):
    """the housing's outline in the side plane (x, z), clockwise from the left: tip T on L, top-rear R on L at the door cut, bottom-rear B, front-lower F (= FMc)"""
    Lc = ctx.A.D.CURVES['L']
    xr = MK_X1 - 0.004
    zr = float(Lc.at(xr)[2])
    return [(MK_TIP, float(Lc.at(MK_TIP)[2]) - (MK_TIP_DZ if QF_MID_MK else 0.0)), (xr, zr), (xr + MK_LEAN, zr - MK_HR), MK_FMC]


def side_markers(ctx, level):
    """DS-3 (constants MK_*): the housing is laid on the HI flank by rays along y; its parts stand off the body by MK_O along the flank's normal.  hi: rim (chamfer, top, inner wall),
    floor, rib and the rear cover's facets (GlossBlack, flat-shaded), the reflector's ridges (Reflector), the lens bezel (PanelGap) and glass (GlossBlack), the amber line (SideMarker).
    lod1 / lod2: the outline as one plate (GlossBlack; Trim at lod2 by LEVEL_MATS), 12 triangles a side."""
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

    T, R, B, F = outline = marker_outline(ctx)
    d3 = (T[0] - F[0], T[1] - F[1])
    d_front = MK_REFL_DX * d3[1] / math.hypot(*d3)                   # (a shift by dx across the front edge = dx times its normal's x component)

    def chamfer(ring, c):
        """ring corners [T, R, B, F] -> [T, R, B, Fb, Ff]: the F corner cut back by c along both edges"""
        t, r, b, f = ring
        ub = math.hypot(b[0] - f[0], b[1] - f[1])
        uf = math.hypot(t[0] - f[0], t[1] - f[1])
        return [t, r, b, _lerp(f, b, c / ub), _lerp(f, t, c / uf)]
    rings2d = [chamfer(_inset(outline, ds), c) for ds, c in (((0, 0, 0, 0), MK_R_F), ((MK_RIM_C,) * 4, 0.75 * MK_R_F), ((*MK_RIM, d_front), 0.001))]
    for sd in (-1, 1):
        pc, nF = cast((-1.04, sd * 2.5, 0.69), (0, -sd, 0), 0.0)
        if pc is None:
            continue
        cache, vcache = {}, {}

        def hit(q):
            k = (round(q[0], 6), round(q[1], 6))
            if k not in cache:
                p, nn = cast((q[0], sd * 2.5, q[1]), (0, -sd, 0), 0.0)
                cache[k] = (p, nn) if p is not None else (Vector((q[0], pc.y, q[1])), nF)      # (a miss: never seen, the housing lies wholly on the flank)
            return cache[k]

        def P3(q, o):
            return hit(q)[0] + nF * o                                 # (one normal for the whole flat flank: the hit normal tilts up on L's fillet)

        def V(M, q, o):
            k = (id(M), round(q[0], 6), round(q[1], 6), round(o, 6))
            if k not in vcache:
                vcache[k] = M.v(P3(q, o))
            return vcache[k]

        def band(M, ra, oa, rb, ob, want):
            n = len(ra)
            for i in range(n):
                j = (i + 1) % n
                vs = [V(M, ra[i], oa), V(M, ra[j], oa), V(M, rb[j], ob), V(M, rb[i], ob)]
                w = want(vs) if callable(want) else want
                _face(M, vs, w)

        def ladder(M, top, bot, offs, want):
            for i in range(len(top) - 1):
                _face(M, [V(M, top[i], offs[i]), V(M, top[i + 1], offs[i + 1]), V(M, bot[i + 1], offs[i + 1]), V(M, bot[i], offs[i])], want)

        Mk = Mesh()
        if level:
            # LOD: the outline as one plate, a ladder between its top edge and its bottom (front-lower corner -> bottom-rear), standing off the decimated body like the seams
            o = (0.0014, 0.0035, 0.0045)[level]
            r0 = rings2d[0]
            ladder(Mk, _split([r0[0], r0[1]], 3), _split([r0[4], r0[3], r0[2]], 3), [o] * 4, nF)
            emit(Mk, 'SideBlade_%d' % sd, 'GlossBlack', smooth=False)
            continue
        cnt = (10, 2, 8, 1, 2)                                        # segments: top, rear, bottom, corner cut, front
        rings = []
        for r in rings2d:
            loop = []
            for k, m in enumerate(cnt):
                loop += _split([r[k], r[(k + 1) % 5]], m)[:-1]
            rings.append(loop)
        o0, o1, o2 = MK_O
        cen = P3(((T[0] + R[0] + B[0] + F[0]) / 4, (T[1] + R[1] + B[1] + F[1]) / 4), o2)
        band(Mk, rings[0], o0, rings[1], o1, nF)                                  # the rim's outer chamfer
        band(Mk, rings[1], o1, rings[2], o1, nF)                                  # the rim's top (wide at the front: up to the reflector)
        band(Mk, rings[2], o1, rings[2], o2, lambda vs: cen - sum((Vector(v.co) for v in vs), Vector()) / 4)    # the inner wall, facing the floor
        t2, r2, b2, fb2, ff2 = rings2d[2]
        top = _split([t2, r2], 10)
        ladder(Mk, top, _split([ff2, fb2, b2], 10), [o2] * 11, nF)              # the floor
        # the rib between the camera and the rear cover
        db, dt = (MK_DIV[0], _z_on(fb2, b2, MK_DIV[0])), (MK_DIV[1], _z_on(t2, r2, MK_DIV[1]))
        u = (dt[0] - db[0], dt[1] - db[1])
        lu = math.hypot(*u)
        pw = (u[1] / lu * 0.0015, -u[0] / lu * 0.0015)
        quad = [(db[0] - pw[0], db[1] - pw[1]), (dt[0] - pw[0], dt[1] - pw[1]), (dt[0] + pw[0], dt[1] + pw[1]), (db[0] + pw[0], db[1] + pw[1])]
        orib = o1 + 0.0008
        _face(Mk, [V(Mk, q, orib) for q in quad], nF)
        mid = P3(db, o2) * 0.5 + P3(dt, o2) * 0.5
        for a, b in ((0, 1), (2, 3)):
            vs = [V(Mk, quad[a], orib), V(Mk, quad[b], orib), V(Mk, quad[b], o2), V(Mk, quad[a], o2)]
            _face(Mk, vs, sum((Vector(v.co) for v in vs), Vector()) / 4 - mid)
        # the smoked rear cover: two facets meeting in a ridge halfway between the rib and the rear edge (they catch the light differently, p003's "internal facets")
        mt, mb = _lerp(dt, r2, 0.5), _lerp(db, b2, 0.5)
        ob = o2 + 0.0001
        _face(Mk, [V(Mk, dt, ob), V(Mk, mt, o2 + MK_COVER_H), V(Mk, mb, o2 + MK_COVER_H), V(Mk, db, ob)], nF)
        _face(Mk, [V(Mk, mt, o2 + MK_COVER_H), V(Mk, r2, ob), V(Mk, b2, ob), V(Mk, mb, o2 + MK_COVER_H)], nF)
        # the lens: a gloss-black glass disc sunk in a matte black bezel, between the reflector and the rib (p003; a Trim bezel read as a grey ring, a gloss one as a white one)
        xc = MK_CAM[0]
        zc = 0.5 * (_z_on(t2, r2, xc) + _z_on(fb2, b2, xc))
        pcen, _ = hit((xc, zc))
        ex = (Vector((1, 0, 0)) - nF * nF.x).normalized()
        ez = nF.cross(ex) * (1 if nF.cross(ex).z > 0 else -1)
        circ = lambda r_, o: [pcen + nF * o + (ex * math.cos(a) + ez * math.sin(a)) * r_ for a in [2 * math.pi * i / 16 for i in range(16)]]
        rb_, rg_, hb = MK_CAM[1], MK_CAM[2], MK_CAM[3]
        Mc = Mesh()
        rr = [[Mc.v(p) for p in circ(r_, o)] for r_, o in ((rb_, o2), (rb_, o2 + hb), (rg_, o2 + hb), (rg_, o2 + hb - 0.0008))]
        for k, (a, b) in enumerate(zip(rr, rr[1:])):
            for i in range(16):
                vs = [a[i], a[(i + 1) % 16], b[(i + 1) % 16], b[i]]
                c = sum((Vector(v.co) for v in vs), Vector()) / 4 - pcen
                _face(Mc, vs, (c - nF * c.dot(nF)) * (1 if k == 0 else -1) if k != 1 else nF)   # outer wall out, top up, inner wall in
        emit(Mc, 'SideCamera_%d' % sd, 'PanelGap', smooth=True)
        Mg = Mesh()
        cg = Mg.v(pcen + nF * (o2 + hb - 0.0008))
        gl = [Mg.v(p) for p in circ(rg_, o2 + hb - 0.0008)]
        for i in range(16):
            _face(Mg, [cg, gl[i], gl[(i + 1) % 16]], nF)
        emit(Mg, 'SideLens_%d' % sd, 'GlossBlack', smooth=False)
        emit(Mk, 'SideBlade_%d' % sd, 'GlossBlack', smooth=False)
        # the reflector: from the floor's front edge to MK_REFL_X1, its bottom edge rising off the floor's (MK_REFL_B); prismatic ridges across it, from its front edge's slant to its rear edge's
        Mr = Mesh()
        n = 2 * MK_REFL_RIDGES
        tr = (MK_REFL_X1[0], _z_on(t2, r2, MK_REFL_X1[0]))
        bl = (fb2[0], fb2[1] + MK_REFL_B[0])
        br = (MK_REFL_X1[1], _z_on(fb2, b2, MK_REFL_X1[1]) + MK_REFL_B[1])
        ladder(Mr, _split([t2, tr], n), _split([bl, br], n), [o2 + 0.0003 + MK_REFL_RH * (i % 2) for i in range(n + 1)], nF)
        emit(Mr, 'SideReflector_%d' % sd, 'Reflector', smooth=False)   # (fixed dark red, not lit, not livery-tinted; dropped at the LODs)
        # the amber line under the top edge of the rear cover, 0.5 mm over the cover's facets (it bends over their ridge)
        Ma = Mesh()
        Lc = ctx.A.D.CURVES['L']
        xs = sorted({MK_AMBER[0] + (MK_AMBER[1] - MK_AMBER[0]) * i / 6 for i in range(7)} | {mt[0]})
        oc = lambda x: float(np.interp(x, [dt[0], mt[0], r2[0]], [ob, o2 + MK_COVER_H, ob]))
        ztop = (lambda x: _z_on(T, R, x)) if QF_MID_MK else (lambda x: float(Lc.at(x)[2]))      # (the line under which the amber sits: the housing's top edge T -> R, or L)
        ladder(Ma, [(x, ztop(x) - MK_AMBER_Z[0]) for x in xs], [(x, ztop(x) - MK_AMBER_Z[1]) for x in xs], [oc(x) + 0.0005 for x in xs], nF)
        emit(Ma, 'SideLamp_%d' % sd, 'SideMarker', smooth=False)
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
    """DS-4: the carbon sill panel between the arches: a flat vertical face from SKIRT_Z[2] (where it meets the body's tucked-in lower side) down past the body's lowest side
    face (z 0.18 - 0.20) to SKIRT_Z[0] at the front / [1] at the rear, a small outward lip at the bottom, square-cut ends (p003), closed behind (it hangs free below the body).
    (until 2026-10-24: x -0.99 .. 1.10, the face following the body from its lowest side face zb up 8 - 11 cm (z ~0.18 .. 0.29), ends tapered over 12 cm, lip 2.6 cm)"""
    cb = ctx.CB()
    x0, x1 = round(ctx.HUBS[0][0] + SKIRT_IN, 6), round(ctx.HUBS[2][0] - SKIRT_OUT, 6)      # -1.085 .. 1.19 for hubs at -1.487 / 1.61
    nx = (60, 12, 6)[level]
    zf, zr, zt = SKIRT_Z
    for s in (-1, 1):
        secs = []
        for i in range(nx):
            x = x0 + (x1 - x0) * i / (nx - 1)
            prof = body_side(ctx.surf_hi, x, s)
            if len(prof) < 3:
                continue
            lip = SKIRT_LIP * min(smooth(x0, x0 + 0.04, x), smooth(x1, x1 - 0.04, x))
            z0 = zf + (zr - zf) * (x - x0) / (x1 - x0)
            yf = _interp(prof, zt) + s * SKIRT_OFF                       # the face (vertical) stands SKIRT_OFF off the body at its top edge
            secs.append([(x, yf - s * 0.03, z0 + 0.008), (x, yf + s * lip, z0), (x, yf + s * lip, z0 + 0.008), (x, yf, z0 + 0.016), (x, yf, zt),
                         (x, _interp(prof, zt + 0.006) + s * 0.0005, zt + 0.006)])
        if len(secs) > 1:
            cb.prism(secs, [W_DARK] * (len(secs[0]) - 1), cap=W_DARK)
            cb.prism([[sc[-1], sc[0]] for sc in secs], [W_DARK])         # the back (inner) face
    me = cb.mesh('Skirt', keep_color=False)
    ob = bpy.data.objects.new('Skirt', me)
    ctx.link(ob)
    me.materials.append(ctx.mat('Carbon' if level < 2 else 'Trim'))      # (the game draws Carbon as clear-coated twill, src/car/materials.js: the p003 sill; Blender's studio shows it as a grey band)
    ctx.mark_sharp(me, 40)
    return ob


def build(ctx, level):
    objs = []
    if not (ctx.oldbody or not ctx.front_r2 or os.environ.get('NO_FRONT')):
        objs += side_markers(ctx, level)
        objs += door_seams(ctx, level)
        objs += window_seal(ctx, level)
        objs += roof_splits(ctx, level)
    objs.append(build_skirt(ctx, level))
    return objs
