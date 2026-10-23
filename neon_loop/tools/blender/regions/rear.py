"""
REAR region: everything behind the cabin -- tail skins (light band, red bar, brake lamps, reflectors, corner lamps), the visor and lip roll, the diffuser module with the
thruster nozzles (flush gold rings in a chamfered black housing with hexagonal mounts) and tunnels, corner fins, the plate backing, camera pod and reverse lamps, the active wing
and the tail colour split (body colour from the lip roll down to the black bar under the plate, black below it and in the lower corners).   Interface: REGIONS.md section 2
and regions/ctx.py.

  shell_post(ctx)             cut the black / body-colour outline into the hi body (refine_tail, cut_boundary); runs BEFORE the wheel-arch cut
  build(ctx, level)           static parts for the Body node (tail skins, lip, diffuser, fins, plate backing; lod2 adds the nozzle ring and walls, but NO wing)
  nodes(ctx, level)           {'Thrusters', 'Wing', 'WingWell'} (levels 0 and 1; Wing carries the child WingPlates; lod2 has none: it is fixed STOWED = the shell's deck)
  decals(ctx, level)          [Decal_plate] (the RDSTR plate patch, joined into the Decals node)
  lod_post(ctx, level, body)  re-colour the tail on the decimated LOD body
  meta(ctx)                   wing (pivot, deploy pose, well, plates) and the plate decal cell for car_meta.json

Wing (DR-1): stowed = the shell's own deck.  `Wing` is a patch cast on the deck faces aft of the seam (deck + ear-inner triangles, |y| up to the ridge) that coincides with them
in its as-built pose; the game hides it while stowed.  `WingWell` (GlossBlack, same footprint, 1.5 mm above the deck) is shown the moment the wing leaves; the wing then lifts and
pitches (meta.wing.deploy) while the child `WingPlates` (tips out to |y| 1.04, endplates, two struts at |y| 0.49) scales in.

Runtime names that must not change: nodes Wing, WingPlates, Thrusters; the lamp glow is driven by the material names TailLamp / BrakeLamp / ReverseLamp; meta.decals.plate.
Everything surface-dependent casts on ctx.surf (this level's own body: the decimated body at lod1 / lod2); FAS_LEAN is computed once from the HI surface (ctx.surf_hi) -- see consts().
`oldbody` (ctx.oldbody) keeps the legacy --oldbody build working; new-shell code paths are the default.

History of the rear (rounds 1-4, from the header of the old build_game_car.py):
------------------------------------------------------------- rear (Roadster 2026 press photos, see the header)
Round-1 rebuild after the official rear shots (r81 straight rear, the low rear-quarter close-up, the high rear view).
Top to bottom: the deck ends in a thin overhanging VISOR (knife edge), under it the gloss-black light band carrying one
continuous red bar that tapers to points, then a convex body-colour LIP ROLL whose outer ends sweep down into pointed
blade tips.  Under the lip the fascia is strongly UNDERCUT (see tail_warp: it tucks in and down, the lower corners are
chamfered), so the lower rear sits recessed in shadow.  Body colour survives only as a bell-shaped lobe carrying the plate;
the corners and the tray under it are black.  The diffuser is one light carbon module hung under / behind the lobe:
a slim tapered crossbeam (chamfered ends) over a dark channel with the four gold nozzles and five ports, a shelf, four
tunnels split by strakes with a dark back wall and small round exhaust openings, a rising ramp floor and tall endplates
with curved trailing edges.  The active wing is deployed LOW: a thin blade just above the visor with tall trapezoid
endplates, on two short struts; its node pivots at the blade so the game can pitch it as an airbrake.
Round 2 (reviewer notes): the tail is convex in plan with rounded corners (tail_bow); the lobe is a proud panel with a rolled
edge over a recessed, scooped flank (flank_depth, geometry not paint); pointed flying-buttress 'ears' (build_buttress) and a black
trailing deck panel with a chevron front edge (DeckPanel) between them; the wing sits right over the visor, has thin light
endplates and a stowed pose (car_meta.json: wing); the nozzles stand on short barrels in a deep dark channel with port tubes behind
them (build_jets / outlet_plate); the diffuser module is rounded and its endplates end near the lip; camera pod + plate lamps.
Round 3: the buttress ears are ridges of the body mesh itself (apply_buttress), not separate wedges; the rear quarter surface is
data-driven and clean (make_ypre / widen_factor: the haunch keeps its full width to the tail corner, no dent, no ripples), the
scoop dies out before the corner (flank_depth), the tuck-in of the black quarter grows in over a wide height window (kp), and the
black / paint boundary on the side wall IS the body's own quarter crease (CREASE) so the paint ends on a clean line; the rear
tyres are covered from above by the wider black quarters; the wing is a dark gloss blade (13 % wider than the body) with thin light
endplates outside the body; the diffuser endplates are curved (sloping top, big radius at the trailing foot).
Round 4: the buttress ears are re-cut (apply_tumblehome: apex |y| 0.465, 38 deg outer plane on a 1.070 shoulder, dark trough and roof
header between them, thrusters-photo skyline fitted by ray-cast: TH_RIDGE); the active wing is 1.14 m half span with 11.5 cm light
endplates HANGING from the blade tips and a stow pose (WING_STOW, car_meta.json); the tail corners are ANGULAR: the tail face is flat in
plan to a near-square corner (BOW_C0), the visor and the lip end square at the band's end with a thin white frame edge (build_tail_lip), and a single
plane (CF_PLANE, apply_corner_facet) cuts a small triangular rear-outward chamfer facet (0.12 m wide at the top, tapering to a point 0.14 m below the band
top; its edges are straight because the tail face and the corner are flat / tight there); the paint / black boundary runs level round the corner (bound_z); the diffuser
endplate foot sweeps forward on a large radius and tapers (build_diffuser); the rear seats have no headrests (build_interior: back=False).
"""
import math, os, types
import bpy, bmesh
from mathutils import Vector, Matrix
from common import smooth, smoother, pchip, W_DARK, Mesh

NAME = 'rear'

# ----------------------------------------------------------------------------- the black / body-colour outline of the tail
# 2026-10-23 (user: "按侧视组" -- the tail's heights from the side group p018 / p017): everything on the tail face below the light band's top and the diffuser module were placed
# with the matched r81 camera, which reads 5 - 10 px high on anchors that have nothing to do with the tail (roof apex, rear glass corners, ear tips, ground; see REFS r81).  p018 puts the
# tail corner at ~0.99 and the diffuser endplates ~6 cm under the old ones; the r81 layout (box, red bar, lip, plate, nozzles, module) keeps its proportions and drops by DZ_TAIL.
REAR_T17 = os.environ.get('REAR_T17', '0') == '1'      # preview switch (with design2 QF_Q16_LT): the side-group tail layout below; off = the accepted tail
# (with design2 QF_Q17 the tail's top edge is level at 1.015, the box's top 1.010: the r81 layout (box top 1.056) drops 4.6 cm; with the side-group corner alone (0.986) it was 6 cm)
DZ_TAIL = -0.046 if REAR_T17 else 0.0
LIP_BOT = 0.893 + DZ_TAIL        # underside of the lip roll


CREASE = [(1.90, 0.580), (1.96, 0.636), (2.00, 0.664), (2.06, 0.708), (2.14, 0.772), (2.20, 0.800), (2.26, 0.840), (2.34, 0.862)]

def cheek_edge(x):
    """z of the top of the black rear quarter on the side wall: the body's own quarter crease (the haunch overhangs the flat
    quarter below it; the crease climbs from the rear of the arch to the tail corner).  The paint ends exactly on it, so the
    crease is a clean colour boundary and no body-colour wedge hangs below it."""
    return pchip(CREASE, min(max(x, 1.90), 2.34))


Z_BAR = LIP_BOT                  # round 5 (user, photos thrust / r81 / high / p017): the tail face is BLACK from the thin body-colour lip right under the lamp band down to the diffuser; the old
                                 # "one body-colour face down to a bar at z 0.69" reading is retired
GLOSS_X0 = 2.00                  # the gloss black starts at the rear end of the rear wheel arch (hub 1.61 + tyre 0.39)
BLACK_SLOT = 3                   # the hi body gets a 4th material slot, GlossBlack (the photos' tail is bright black, not the matt Trim of the rest of the black); lod1 gets it in lod_post, lod2 stays Trim


def lobe_edge(y):
    """z of the boundary between the (thin) body-colour lip and the black tail face below it.  Round 5: a single straight level line across the whole width (the lip roll's underside), so
    the colour split is one crisp horizontal edge and never two lines."""
    return LIP_BOT


def bound_z(x, y, oldbody=False):
    """z of the black / body-colour boundary at a point (x, y) of the tail surface: the lobe outline across the face, the
    cheek line on the side wall ahead of the corners."""
    if not oldbody:         # new shell: the tail face's colour split (lobe_edge); the side wall's line is the shell's own L3 edge
        return lobe_edge(y)
    zl = lobe_edge(y) + 0.17 * smooth(0.90, 1.06, abs(y))      # round-4: the lobe outline runs LEVEL into the cheek line at the corner (the old white blade
    # dropped 0.17 m there against the cheek line, which rises to the rear: a notch / sawtooth on the quarter)
    # on the side wall the boundary is the quarter crease; round the corner it hands over to the lobe outline
    w = smoother(1.00, 1.06, abs(y))
    return zl + (cheek_edge(x) - zl) * w


def refine_tail(ob, lmax=0.030, inside=lambda c: c.x > 1.95):
    """the sub-divided cage leaves the flat tail face in ~12 cm quads: split the edges inside `inside` (a test on the edge
    midpoint) down to lmax so the tail warp, the black / body-colour outline and the projected skins have something to bend
    with."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    for _ in range(5):
        edges = [e for e in bm.edges if e.calc_length() > lmax and inside((e.verts[0].co + e.verts[1].co) * 0.5)]
        if not edges:
            break
        bmesh.ops.subdivide_edges(bm, edges=edges, cuts=1, use_grid_fill=True)
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()


def in_tail_region(c, oldbody=False):
    """the part of the tail where bound_z decides the colour (old body: the whole rear quarter; new shell: the centre of the tail face)"""
    if oldbody:
        return c.x > 1.95 and abs(c.y) < 1.10 and c.z < 1.0
    return c.x > 2.30 and abs(c.y) < 0.915 and c.z < 1.0


def blacken_tail(ob, margin=0.030, strict=False, oldbody=False):
    """everything under the lobe outline is black (the TailLower strip only gives the outline its crisp edge); applied to the
    hi body and again to every decimated LOD body.  strict (LODs): across the face (|y| < 0.98) a polygon turns black only if
    ALL its vertices lie under the outline and turns back to paint if any is above it -- the big collapsed faces would
    otherwise poke black wedges above the outline; the black tray overlay of the LOD covers the white faces left under it.
    Round the corners and on the side wall the outline is decided by the polygon centre (with `margin`), as in the hi body."""
    n = 0
    me = ob.data
    for p in me.polygons:
        c = p.center
        if not in_tail_region(c, oldbody):
            continue
        if strict and abs(c.y) < 0.98:
            under = all(me.vertices[i].co.z < bound_z(me.vertices[i].co.x, me.vertices[i].co.y, oldbody) for i in p.vertices)
            if p.material_index in (0, 2) and under != (p.material_index == 2):
                p.material_index = 2 if under else 0
                n += 1
        elif p.material_index == 0 and c.z < bound_z(c.x, c.y, oldbody) - margin:
            p.material_index = 2
            n += 1
        elif strict and p.material_index == 2 and c.z > bound_z(c.x, c.y, oldbody) + 0.02:
            p.material_index = 0
    return n


def cut_boundary(ob, oldbody=False):
    """split the hi body along the black / body-colour outline (z = bound_z(x, y)): the outline becomes an exact chain of mesh edges,
    so no overlay strip is needed to hide a stair-step, and give every polygon its colour by its centre."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    g = lambda v: v.co.z - bound_z(v.co.x, v.co.y, oldbody)
    sel = {v for v in bm.verts if v.co.x > 1.90 and abs(v.co.y) < 1.12 and v.co.z < 1.0 and abs(g(v)) < 0.25
           and (oldbody or (v.co.x > 2.28 and abs(v.co.y) < 0.93))}
    new = []
    for e in list(bm.edges):
        v0, v1 = e.verts
        if v0 in sel and v1 in sel:
            g0, g1 = g(v0), g(v1)
            if g0 * g1 < 0.0:
                _, nv = bmesh.utils.edge_split(e, v0, g0 / (g0 - g1))
                nv.co.z = bound_z(nv.co.x, nv.co.y, oldbody)             # exactly on the outline
                new.append(nv)
    res = bmesh.ops.connect_verts(bm, verts=new)
    n = 0
    for f in bm.faces:
        c = f.calc_center_median()
        if in_tail_region(c, oldbody) and f.material_index in (0, 2, BLACK_SLOT):
            m = BLACK_SLOT if c.z < bound_z(c.x, c.y, oldbody) else 0
            if m != f.material_index:
                f.material_index = m
                n += 1
    # round 5: ALL the black aft of the rear arch (the lower tail face under the old "bar", the lower rear corners) is the same bright GlossBlack as the new black tail face: one material, no gloss seam
    # across the plate; the seam to the matt black of the side wall sits at the arch's rear end
    for f in bm.faces:
        if f.material_index == 2 and f.calc_center_median().x > GLOSS_X0:
            f.material_index = BLACK_SLOT
            n += 1
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()
    return len(new), n


# ----------------------------------------------------------------------------- surface queries (on a Surf)
def tail_x(surf, y, z):
    """x of the tail face at (y, z) on the Surf `surf` (None when the ray misses)"""
    p, _ = surf.cast((3.5, y, z), (-1, 0, 0), 0.0, 3.0)
    return None if p is None else p.x


def deck_z(surf, x, y):
    """z of the top surface at (x, y) on the Surf `surf`"""
    p, _ = surf.cast((x, y, 3.0), (0, 0, -1), 0.0, 4.0)
    return None if p is None else p.z


# ------------------------------------------------------------- constants
BAND = (0.930 + DZ_TAIL, 1.040)  # gloss-black light band (z): r81 (zoomed, gamma-lifted) black band z 0.93 .. 1.05 under the white top edge; the face ends at the deck, z 1.042
BAND_Y = 0.930                   # half width (column parameter) of band / bar: r81 red bar ends +-236 px = +-0.95 m.  The rays swing round at the corner, so a column at 0.930 lands at |y| 0.949 on the
                                 # tail's corner (0.945): round 3b: the band / bar stop there, so the corner facet seen from the side (p018) is plain paint (it was 0.940 -> 0.965: a black cap on the facet)
BAR_H, BAR_Y = 0.018 if REAR_T17 else 0.015, 0.918            # red bar (2026-10-23: 1.5 -> 1.8 cm, r81 rows 719 - 723.5) (round 7, DR-2: the same width along the whole band, straight to the ends, 1.2 cm short of the band's end, centred in the band: r81): thickness, half width
LIP_Z = (LIP_BOT, 0.930 + DZ_TAIL)   # the convex lip roll under the band (r81: pink roll z 0.90 .. 0.926, thin white line at 0.893)
PLATE = dict(uv=(1024, 512, 1024, 216), y=(-0.17, 0.17), z=(0.668 + DZ_TAIL, 0.838 + DZ_TAIL))
DIFF_W = 0.700                   # half width of the diffuser module (r81 / 012: |y| 0.70 ... 0.72)
JET_X, JET_Z = 2.318, 0.578 + DZ_TAIL      # (src/car/jets.js JET_EXITS follows) nozzle lip face (x) and nozzle centre height (r81: ring centres at y 822.5 px = z 0.579; 012 agrees).  Round 2: recessed 3.4 cm deeper (the crossbeam's rear edge at 2.408
                                 # overhangs the rings by 9 cm, so the housing hides them in p017 as in the photo)
JET_Y = (-0.405, -0.135, 0.135, 0.405)
PORT_Y = (-0.525, -0.27, 0.0, 0.27, 0.525)   # the dark round recessed holes between / outside the nozzles (SPEC DR-7: the mounts)
PORT_R = (0.034, 0.048, 0.048, 0.048, 0.034)      # (the outer two are smaller: the housing's chamfer is close)
CELL = 0.062                     # half height of the nozzle housing's channel
TOP_Z = (JET_Z + CELL, 0.660 + DZ_TAIL)    # crossbeam plate (its underside closes the nozzle channel); its top is the housing's top edge (z 0.66 in r81)
SHELF_Z = (0.4935 + DZ_TAIL, JET_Z - CELL)     # shelf under the channel = ceiling of the tunnels (housing bottom z 0.50)
CH_X = 2.284                     # back wall of the nozzle channel (the beam's rear edge is at 2.408; the nozzle lips stand 3.4 cm proud of the wall)
N_WALL = (0.004, 0.004, 0.0045, 0.62)    # the channel wall / tunnel back wall: round 5b = BLACK ANODISED METAL (a < 0.7 is metal in the game shader and in render_ref_views): its reflectance is the base colour, 0.4 %, so under the studio
                                 # lights it stays pure black (a rough dielectric kept the 4 % Fresnel of the bright floor: grey 25 / 255 against the photo's 7).  (Round 3's grey-pink wall was a metal with base 0.034.)
CH_CHAMF = 0.15                  # the housing's upper end corners fall by this much over their chamfer (r81: the housing outline is a hexagon-like shell)
CH_Y0 = 0.50                     # |y| where the chamfer starts (flat top edge to here)
TUCK = 0.095                     # round 5: the module's lower part is tucked in under the tail (it follows the shell's own undercut instead of hanging off the tail as a box): everything below TUCK_Z0
                                 # is sheared forward LINEARLY (so the flat wall tiles stay exactly planar: just tilted), by TUCK at TUCK_Z1 (tuck_x)
TUCK_Z0, TUCK_Z1 = 0.495 + DZ_TAIL, 0.20 + DZ_TAIL
BATH_R = 0.10                    # round 6: the module's lower outline seen from behind is a bathtub: vertical sides, flat bottom, corners of this radius (bath_z)
BATH_Z0, BATH_Z1 = 0.19 + DZ_TAIL, 0.46 + DZ_TAIL    # the squeeze zone: the bottom z BATH_Z0 rises along the corner arc, the top of the zone (BATH_Z1) stays
SWEEP = (0.045, 0.075)           # round 6: the ends fall forward in plan like a parabola, u^2: SWEEP[0] at the housing, + SWEEP[1] more at the foot: ONE continuous forward-sweeping bottom edge (module_xyz)
DIFF_PLAN = 0.045                # the module's ends fall forward in plan (rounded module, endplate trailing edge ~ at the lip)
WALL_X = 2.25                    # dark back wall of the tunnels (round 3: 10 cm behind the shelf's rear edge, a compact box: it was 20 cm)
BAY_Z0 = 0.215 + DZ_TAIL         # the bays' floor = the tray that closes the box underneath (r81 / thrust: the photo's box ends at z ~0.20)
STRAKE_Y = (-0.315, 0.0, 0.315)
BAY_E = (-DIFF_W + 0.016, -0.315, 0.0, 0.315, DIFF_W - 0.016)   # bay edges
# --- the active wing (DR-1).  Stowed = the shell's own deck faces; the Wing node is a COPY of them (+ tips, endplates, struts in WingPlates) that coincides with the deck in
# its as-built (stowed) pose and is hidden by the game while stowed; WingWell (GlossBlack, same footprint, 1.5 mm above the deck) shows as soon as the wing leaves.
# Deployed pose = as built + meta.wing.deploy (lift dy, pitch rotZ about WING_P, trailing edge up).  Numbers: official-02 (matched `high`): wing tips |y| 1.04..1.09, struts |y| 0.49,
# trailing edge z ~1.15..1.2 at x ~2.43; 012 (rear): blade seen from below, tilt ~15 deg; 001 (side): the panel lifts and tilts on thin dark linkage arms.
WING_P = Vector((2.20, 0.0, 1.07))       # node origin = the stowed panel's mid chord on the deck plane (the pivot of the pitch)
WING_X = (2.052, 2.382)                  # panel chord: from the seam (x 2.05) to the tail edge (the rear edge follows the plan-convex tail: tail_x(|y|))
WING_Y = 0.92                            # panel half width: out to the lip roll's edge (SPEC L11; the body is +-0.945 at the tail)
WING_DEP = dict(dx=0.10, dy=0.04, rot=0.57)   # deploy pose relative to the stowed one: aft slide, lift (m) and pitch (rad = 33 deg, trailing edge up) about WING_P, FITTED TO `high`
                                         # (matched camera, 33 deg above the horizon -> the blade is nearly edge-on): the panel centre line projects to rows 744 (leading edge) .. 762 (trailing edge)
                                         # in the 2048 x 1365 photo, the blade's bright edge / underside are at rows 747 / 767; the trailing edge ends at x 2.47, z 1.185 (012: z ~1.2), the
                                         # leading edge stays at the deck's front (x 2.165, z 1.05) = hinged at the seam, as 001 (side) shows: the top line rises aft from the deck's front
TIP_Y = 1.04                             # half span of the deployed wing: the body is +-0.945 at the tail, 1.06 at the wheels; the photos show ~1.04
STRUT_Y = 0.49                           # the two struts (high, 012: |y| 0.49)
WING_STOW_LEGACY = dict(dy=-0.06, rotZ=0.0, spanScale=1.0)          # for the shot tools that still read meta.wing.stow (they treat the as-built pose as deployed): sink the copy under the deck
BUTT_X = (1.00, 2.06)            # (legacy --oldbody: the deck panel's front edge, see deck_x0)

N_GOLD = (0.93, 0.74, 0.47, 0.16)       # Nozzle vertex colours: rgb = metal base colour, a = roughness
N_BELL = (0.62, 0.42, 0.22, 0.30)
N_DEEP = (0.30, 0.18, 0.09, 0.45)
N_THROAT = (0.03, 0.025, 0.02, 0.85)
N_PORT = (0.04, 0.04, 0.045, 0.45)
N_SHROUD = (0.008, 0.008, 0.009, 0.85)       # the barrel round each nozzle: near-black satin (> 0.7 = non-metal in the game shader); round 3: it read as a pale grey ring
N_BLADE = (0.022, 0.022, 0.025, 0.74)
N_BACK = (0.006, 0.006, 0.007, 0.92)
N_VOID = (0.002, 0.002, 0.002, 1.0)             # hole / duct interiors: near black
N_COVER = (0.10, 0.065, 0.035, 0.30)


def consts(ctx):
    """FAS_LEAN (lean of the plate panel, deg) from the HI surface, computed once per build.  (The old WING_STOW 'hidden stub' patch is gone: the stowed wing is the deck itself.)"""
    c = ctx.cache.get('rear')
    if c is None:
        surf = ctx.surf_hi
        lean = math.degrees(math.atan2(tail_x(surf, 0.0, 0.83 + DZ_TAIL) - tail_x(surf, 0.0, 0.69 + DZ_TAIL), 0.14))      # (the plate panel's face normal points down)
        c = types.SimpleNamespace(FAS_LEAN=lean)
        ctx.cache['rear'] = c
    return c


def fascia(ctx, z, y=0.0, off=0.0):
    """point on the tail face at height z (centre line), pushed `off` along its normal (back and slightly down)."""
    x = tail_x(ctx.surf, y, z)
    a = math.radians(consts(ctx).FAS_LEAN)
    return Vector((x + off * math.cos(a), y, z - off * math.sin(a)))


def tail_top_z(y, ctx):
    """z of the tail face's top edge (shell edges tail_a / tail_b): the deck level at the ear tip E (|y| 0.403) out to the centre, then falling linearly to the corner (|y| 0.945), where it is
    the shoulder line L's height.  Read from the shell (q16: L runs level aft of the window, the corner fell from 1.005 to 0.976; the old fixed 1.005 let the band's rays pass over the
    tail's top edge and paint jagged black wedges on the rear shoulder).  The black light band must stop under it: above it the rays would paint the rear shoulder (as in the first round)."""
    D = ctx.A.D
    ye, ze, zc = (0.403, 1.042, 1.005) if D is None else (D.E_TARGET[1], float(D.CURVES['rail'].at(D.E_TARGET[0])[2]), float(D.CURVES['L'].at(D.E_TARGET[0])[2]))      # (E's height from R-1's end: q17 levels it)
    t = min(1.0, max(0.0, (abs(y) - ye) / (0.945 - ye)))
    return ze + (zc - ze) * t


def band_top(ctx):
    """round 7 (SPEC DR-2, r81): the light band's top edge is ONE level line across the whole width: the shell's top edge at the corner (tail_top_z at the largest |y|) minus 5 mm.  Computed from
    tail_top_z, so it follows the shell if the lip is changed.  Above it the body-colour lip is 4 cm high in the middle and a thin strip at the corners."""
    return tail_top_z(BAND_Y + 0.05, ctx) - 0.005


SIL_K = 2.37 / (10.0 - 0.944)     # p018 is a pure side view from y = -10: the tail corner (x 2.37, |y| 0.944) is the nearest and aftmost point = the right end of the car's silhouette (px 1570);
                                  # a point (x, y) stays inside it when x <= SIL_K * (10 - |y|) (farther sections project further left)


def sil_x(y):
    """aft limit of anything standing proud of the tail face near the corners (visor, lip roll, end frame) so that it stays inside the shell's end silhouette in the side view"""
    return SIL_K * (10.0 - abs(y))


def ycol(u, y_end):
    """column parameter u in [-1, 1] -> y in [-y_end, y_end], denser towards the ends (the corners are where the surface turns)."""
    return y_end * math.sin(u * math.pi / 2)


def rear_ray(y, z, phi_max=62.0):
    """ray onto the tail from behind; it swings round with |y| so the rounded corners are hit squarely, not at a graze."""
    phi = math.radians(phi_max) * smooth(0.90, 1.05, abs(y))          # (round-4: the band ends at 0.90 on a flat face, so its columns go straight onto it)
    d = Vector((-math.cos(phi), -(1.0 if y >= 0 else -1.0) * math.sin(phi), 0.0))
    return Vector((2.2, y, z)) - d * 3.0, d


def deck_x0(a):
    """front edge of the black trailing deck panel (official-02: a full-width black panel from buttress to buttress, directly
    in front of the visor; its front edge dips a little aft in the middle and runs aft towards the ends -- a shallow chevron)."""
    a = abs(a)
    return BUTT_X[1] - 0.02 + 0.040 * smooth(0.45, 0.28, a) + 0.115 * smooth(0.55, 0.95, a)


def deck_x1(surf, a):
    """aft edge of the panel: the knife edge of the visor."""
    return (tail_x(surf, a, 0.96) or 2.3) - 0.055


def outline_ray(ctx, a, t, lo=0.044, bottom=None):
    """ray for the strip hugging the black / body-colour boundary: column a, row t in [0, 1] (band z in [B - lo, B], or from
    `bottom` up to B).  B is the boundary height at the point the ray actually HITS (the rays swing round at the corners, so
    the hit y differs from a, and B falls steeply with y there), found by a short fixed-point iteration -- the strip then
    agrees with the face-assignment in blacken_tail instead of leaving white teeth under it."""
    zb = lobe_edge(a)
    for _ in range(5):
        zt = zb - lo + lo * t if bottom is None else bottom + (zb - bottom) * t
        o, d = rear_ray(a, zt)
        p, _n = ctx.surf.cast(o, d, 0.0)
        if p is None:
            break
        zn = bound_z(p.x, p.y, ctx.oldbody)
        done = abs(zn - zb) < 1e-4
        zb = zn
        if done:
            break
    zt = zb - lo + lo * t if bottom is None else bottom + (zb - bottom) * t
    return rear_ray(a, zt)


def cheek_ray(ctx, a, t, sd, lo=0.044, bottom=None):
    """same for the cheek strip on the side wall (rays along -sd * y at x = a)."""
    zb = bound_z(a, 1.07, ctx.oldbody)
    zt = lambda: zb - lo + lo * t if bottom is None else bottom + (zb - bottom) * t
    for _ in range(5):
        p, _n = ctx.surf.cast(Vector((a, sd * 2.5, zt())), Vector((0, -sd, 0)), 0.0)
        if p is None:
            break
        zn = bound_z(p.x, p.y, ctx.oldbody)
        done = abs(zn - zb) < 1e-4
        zb = zn
        if done:
            break
    return Vector((a, sd * 2.5, zt())), Vector((0, -sd, 0))


def build_tail_skin(ctx, level):
    """projected skins on the tail face and the deck: black tray + corners, light band, bar, brake / reverse lamps,
    reflectors, the black wing well behind the glass."""
    patch, OLDBODY = ctx.patch, ctx.oldbody
    nu = (110, 40, 20)[level]
    k = 2.0 if level == 2 else 1.0       # the LOD2 body is a coarse decimation: keep the overlays a little further off it
    keep = lambda p: p.x > 1.95
    gb = 'GlossBlack' if level < 2 else 'Trim'
    bt = band_top(ctx)
    bar_z = 0.5 * (BAND[0] + bt)                      # round 7: the red bar sits in the middle of the band (r81), constant width to the ends (the old taper is gone)
    bar_t = lambda a: 1.0
    # TailLower: only a thin strip along the lobe outline (the faces below it are black in the body mesh itself): it hides the
    # stair-step of the face assignment and gives the outline its crisp, smooth edge
    if level == 0:
        out = []                 # (the hi body's outline is cut into its mesh: cut_boundary)
    else:        # LODs: the decimated body has big faces, so the whole black tray is an overlay on its own surface
        # (the decimated body is faceted to a few mm, so the tray rides well off it or the white facets poke through)
        YT = 1.04 if OLDBODY else 0.93      # round 5: the whole tail face under the lip is black now (one straight edge at the lip's underside), so the overlay spans the full width of the face
        out = [patch('TailLower', gb, ((-YT, YT), (0.0, 1.0)), None, None, (0, 0.012, 0.018)[level], (0, 56, 30)[level], (0, 6, 4)[level],
                     ray_fn=lambda a, t: outline_ray(ctx, a, t, bottom=0.28), keep=keep, a_fn=lambda t: ycol(2 * t - 1, YT))]
    if level > 0 and OLDBODY:
        out += [patch(f'TailCheek_{sd}', 'Trim', ((2.30, 1.95), (0.0, 1.0)), None, None, (0.004, 0.012, 0.018)[level], (56, 24, 12)[level], 5,
                      ray_fn=lambda a, t, sd=sd: cheek_ray(ctx, a, t, sd),
                      keep=lambda p: p.x > 1.9) for sd in (-1, 1)]
    out += [
           patch('TailBand', gb, ((-BAND_Y, BAND_Y), BAND), None, None, 0.0025 * k, nu, (6, 3, 2)[level],
                 ray_fn=lambda a, bb: rear_ray(a, BAND[0] + (bb - BAND[0]) / (BAND[1] - BAND[0]) * (bt - BAND[0])),         # round 7: level top edge (band_top)
                 keep=keep, a_fn=lambda t: ycol(2 * t - 1, BAND_Y)),
           patch('TailBar', 'TailLamp', ((-BAR_Y, BAR_Y), (0.0, 1.0)), None, None, 0.0045 * k, nu, 3, unit_uv=True,
                 ray_fn=lambda a, t: rear_ray(a, bar_z + (t - 0.5) * BAR_H * bar_t(a)), keep=keep,
                 a_fn=lambda t: ycol(2 * t - 1, BAR_Y)),
           ]
    if OLDBODY:         # (new shell: the deck behind the seam is the body-colour wing panel carrying the ridges on to the tail edge)
        out.append(patch('DeckPanel', gb, ((-BAND_Y, BAND_Y), (0.0, 1.0)), lambda a, bb: (deck_x0(a) + bb * (deck_x1(ctx.surf, a) - deck_x0(a)), a, 3.0), (0, 0, -1),
                         0.0025 * k, (110, 40, 20)[level], (7, 4, 3)[level], a_fn=lambda t: ycol(2 * t - 1, BAND_Y)))
    if level == 0 and REAR_T17:      # 2026-10-23 (012 / thrust): a dark grey lens strip in each outer half of the band under the red bar (012: |y| 0.41 .. 0.92, 70 .. 87 % of the band's height down from its top)
        zl = lambda f: bt - f * (bt - BAND[0])
        for s_ in (-1, 1):
            out.append(patch('TailLens_%s' % ('L' if s_ < 0 else 'R'), 'Trim', ((0.41, 0.92), (0.0, 1.0)), None, None, 0.0032, 40, 2,
                             ray_fn=lambda a, t, s_=s_: rear_ray(s_ * a, zl(0.87) + t * (zl(0.70) - zl(0.87))), keep=keep))
    if level < 2:
        out.append(patch('BrakeBar', 'BrakeLamp' if level == 0 else 'TailLamp', ((-BAR_Y, BAR_Y), (0.0, 1.0)), None, None, 0.0036, nu, 3,
                         unit_uv=True, ray_fn=lambda a, t: rear_ray(a, bar_z + (t - 0.5) * (BAR_H + 0.003) * bar_t(a)), keep=keep,
                         a_fn=lambda t: ycol(2 * t - 1, BAR_Y)))
    # DR-3 (round 3: p018 / p017 / r81): ONE thin dark-red reflector on each side, ~1.3 cm wide, on the side wall just behind the rear arch, running along the diagonal paint / black
    # boundary of the lower rear corner (p018: (1475, 580) -> (1530, 558) = x 2.01 .. 2.21, z 0.68 .. 0.76 on the shell).  Material `Reflector` (fixed dark red, not emissive; the LODs
    # drop it), hi only.  (The round-2 slit on the tail face and the 5 x 8 cm corner block are gone.)  The reverse lamps are the two small white lamps beside the camera (build()).
    if level == 0:
        zc = lambda x: float(ctx.A.D.CURVES['l3'].at(x)[2])        # G-5: the shell's paint | black boundary l3 now IS the p018 line (straight, x 1.95 .. tail corner): the reflector sits on it (was the fixed line z 0.680 + 0.384 (x - 2.011))
        for s in (-1, 1):
            out.append(patch(f'R_SideReflector_{"L" if s < 0 else "R"}', 'Reflector', ((2.00, 2.24), (0.0, 1.0)), None, None, 0.0030, 9, 2, unit_uv=True,
                             ray_fn=lambda a, bb, s=s: (Vector((a, s * 2.5, zc(a) + (bb - 0.5) * (0.0100 + 0.0060 * (a - 2.0) / 0.24))), Vector((0.0, -s, 0.0)))))
    return out


def build_tail_lip(ctx, level):
    """the thin overhanging visor at the end of the deck (knife edge) and the convex lip roll under the light band, both
    sweeping along the tail face; the roll's outer ends shrink and drop into pointed blade tips."""
    cb = ctx.CB()
    surf = ctx.surf
    n = (64, 28, 14)[level]
    Y_END = 0.944                     # (= the old BAND_Y + 0.004; round-4: the visor and the lip end SQUARE at the band's end (a flat cut, no tapering blade)
    sec_v, sec_r = [], []
    for i in range(n + 1):
        t = -1.0 + 2.0 * i / n
        y = Y_END * math.sin(t * math.pi / 2)          # denser towards the ends
        a = abs(y)
        xb = tail_x(surf, y, 0.96)
        zt = deck_z(surf, xb - 0.02, y)
        if xb is None or zt is None:
            continue
        # visor (round 3: kept inside the shell's end silhouette in the side view p018, sil_x: no tab sticking aft past the corner)
        pr = 0.050 * (1.0 - 0.28 * (a / 0.95) ** 2) * smooth(1.01, 0.93, a)
        pr = min(pr, max(0.0, sil_x(a) - xb - 0.002))
        zv = band_top(ctx) + 0.0005         # round 7: the visor's underside never dips into the band (it was a white wedge across the band's top at the corners): ONE edge there
        # (REAR_T17: the visor's front edge is buried 0.5 mm under the deck where it is.  It stood 1.5 mm proud; the old tail sloped down aft enough to hide that, the raised tail corner
        #  makes the deck there flat, and the step read as a bright line across the shoulder in p013)
        zf = (deck_z(surf, xb - 0.06, y) or zt) - 0.0020 if REAR_T17 else zt
        sec_v.append([(xb - 0.06, y, zf + 0.0015), (xb + pr, y, max(zt - 0.0175, zv + 0.0005)), (xb + pr, y, max(zt - 0.0225, zv)), (xb - 0.06, y, max(zf - 0.0125, zv))])
        # lip roll (bead): base on the band plane, full section to the band's end (its depth tapers to the end face: same clamp)
        sc = 1.0
        xr = tail_x(surf, y, LIP_Z[0] + 0.02)
        zc = 0.5 * sum(LIP_Z)
        H, P = 0.5 * (LIP_Z[1] - LIP_Z[0]), 0.034
        P = min(P, max(0.002, sil_x(a) - xr - 0.002))
        if level == 0:
            prof = [(-0.02 * sc, 1.0), (0.004 * sc, 1.0), (0.59 * P, 0.88), (0.91 * P, 0.55), (P, 0.0), (0.91 * P, -0.55),
                    (0.59 * P, -0.88), (0.004 * sc, -1.0), (-0.02 * sc, -1.0)]
        else:
            prof = [(-0.02 * sc, 1.0), (0.35 * P, 0.8), (P, 0.0), (0.35 * P, -0.8), (-0.02 * sc, -1.0)]
        sec_r.append([(xr + dx, y, zc + H * hv) for dx, hv in prof])
    cb.prism(sec_v, [W_DARK] * 3, cap=W_DARK)
    cb.prism(sec_r, [W_DARK] * (len(sec_r[0]) - 1), cap=W_DARK)
    # (round 7: the end frame, a thin white vertical edge down the band's end, is gone: it doubled the edge the white corner facet already makes against the band's end, with small ticks at both ends;
    #  the photo (r81) shows ONE vertical edge there)
    return ctx.cb_obj(cb, 'TailLip', 'Paint', sharp=35)


def prof_prism(cb, prof, ya, yb, col=W_DARK):
    """closed solid: polygon prof [(x, z)] extruded between y = ya and yb."""
    n = len(prof)
    A = [cb.v((x, ya, z)) for x, z in prof]
    B = [cb.v((x, yb, z)) for x, z in prof]
    for i in range(n):
        j = (i + 1) % n
        cb.face([A[i], B[i], B[j], A[j]], col)
    cb.face(A, col)
    cb.face(B[::-1], col)


def tuck_x(z):
    """forward shift of a point of the diffuser module / its tunnel walls at height z (round 5: the lower module is tucked in under the tail; linear below the housing's bottom edge TUCK_Z0)"""
    return TUCK * max(0.0, TUCK_Z0 - z) / (TUCK_Z0 - TUCK_Z1)


def bath_z(a):
    """z of the module's bottom edge at |y| = a: flat BATH_Z0 up to DIFF_W - BATH_R, then a quarter circle (vertical tangent at the side)"""
    d = max(0.0, min(a, DIFF_W) - (DIFF_W - BATH_R))
    return BATH_Z0 + BATH_R - math.sqrt(max(BATH_R * BATH_R - d * d, 0.0))


def module_xyz(x, y, z):
    """the whole-module deformation (round 6), the same function for the diffuser's own parts and the tunnel node: (1) bathtub: the part below BATH_Z1 is squeezed up so that its bottom edge follows
    bath_z (circular corners seen from behind); (2) the ends sweep forward in plan on a parabola (more at the foot); (3) the lower part is sheared forward (tuck_x)."""
    a = abs(y)
    zb = bath_z(a)
    if z < BATH_Z1:
        z = zb + (z - BATH_Z0) * (BATH_Z1 - zb) / (BATH_Z1 - BATH_Z0)
    if x > 2.10:
        u = min(a / DIFF_W, 1.15)
        x -= (SWEEP[0] + SWEEP[1] * smooth(0.50, 0.22, z)) * u * u * smooth(2.10, 2.30, x)
    return x - tuck_x(z), y, z


def warp_verts(cb, n0):
    """apply module_xyz to the vertices of `cb` created after index n0"""
    for v in list(cb.bm.verts)[n0:]:
        v.co.x, v.co.y, v.co.z = module_xyz(*v.co)


def build_diffuser(cb, level):
    """carbon module: slim tapered crossbeam, thin shelf lip, thin curved strakes, endplates, ramp floor.  The whole module is
    rounded: its ends fall forward in plan (DIFF_PLAN) and its lower corners lift (official-02 / r81: a rounded shape, the
    endplate's trailing edge only a little behind the lip)."""
    yo, t = DIFF_W, 0.011
    # crossbeam plate: thin wedge with a rounded rear edge, ends chamfered down and kicked in
    base = [(2.16, TOP_Z[1]), (2.374, TOP_Z[1] + 0.002), (2.388, TOP_Z[1] - 0.006), (2.388, TOP_Z[0] + 0.006), (2.368, TOP_Z[0]),
            (2.16, TOP_Z[0])]
    stations = [(0.0, 0.0), (CH_Y0, 0.0), (CH_Y0 + 0.07, -0.045), (CH_Y0 + 0.14, -0.10), (yo, -CH_CHAMF)]      # the housing's end corners fall away (r81: chamfered hexagon-like shell)
    secs = []
    for sgn, st in ((-1, stations[::-1]), (1, stations[1:])):
        for ay, dz in st:
            kick = -dz * 0.45
            secs.append([(x - (kick if x > 2.3 else 0.0), sgn * ay, z + dz) for x, z in base])
    cb.prism(secs, [W_DARK] * (len(base) - 1), cap=W_DARK)
    # shelf: a thin carbon lip under the channel = ceiling of the tunnels
    prof_prism(cb, [(2.17, SHELF_Z[1]), (2.368, SHELF_Z[1]), (2.382, SHELF_Z[1] - 0.008), (2.382, SHELF_Z[0] + 0.008), (2.368, SHELF_Z[0]),
                    (2.17, SHELF_Z[0])], -yo + t, yo - t)
    # round 3: a COMPACT BOX.  The tray closes it underneath (bottom edge z 0.19, r81 / thrust); the old ramp floor that stuck out below the walls (a pale plate) is gone, what is left
    # of it hides behind the tray; the strakes are thin ribs in front of the walls (they were big fins hanging 20 cm into the bays).
    # round 5: the conspicuous bottom cross-plate (the rear tray, 10 cm behind the walls) is gone: the floor slab ends flush at the wall, so the module's lower edge is just the wall's rounded foot
    fl = [(x, z + DZ_TAIL) for x, z in ((1.95, 0.176), (WALL_X - 0.01, 0.196), (WALL_X, 0.200), (WALL_X, 0.214), (WALL_X - 0.01, 0.208), (1.95, 0.188), (1.95, 0.176))]
    ys = [-(yo - t), -0.66, -0.63, -0.60, -0.50, 0.50, 0.60, 0.63, 0.66, yo - t]            # (stations along the rounded corner: the warp bends the slab's bottom edge into the arc)
    if level == 1:
        fl, ys = [(x, z + DZ_TAIL) for x, z in ((1.95, 0.176), (WALL_X, 0.200), (WALL_X, 0.214), (1.95, 0.188), (1.95, 0.176))], [-(yo - t), -0.65, -0.60, 0.60, 0.65, yo - t]
    elif level == 2:
        fl, ys = [(x, z + DZ_TAIL) for x, z in ((1.95, 0.176), (WALL_X, 0.200), (WALL_X, 0.214), (1.95, 0.188), (1.95, 0.176))], [-(yo - t), yo - t]
    cb.prism([[(x, y, z) for x, z in fl] for y in ys], [W_DARK] * (len(fl) - 1), cap=W_DARK)
    if level == 0:       # the strakes' bodies are in the Thrusters node (black metal: no floor reflection on their sides); here only their thin bright rear (leading) edges: a 1 cm lip in GlossBlack
        for y in STRAKE_Y:
            prof_prism(cb, [(x, z) for x, z in strake_edge(0.0)] + [(x - 0.007, z) for x, z in strake_edge(0.0)][::-1], y - 0.0040, y + 0.0040)
    warp_verts(cb, 0)
    if level == 2:      # (lod2 has no Thrusters node: the plates are part of the static module)
        build_endplates(cb, level, W_DARK)


def build_endplates(cb, level, col):
    """the endplates (round 6): big slabs, built AFTER the warp, in the final frame, so that their side silhouette is what the photo (p018) shows: a vertical trailing edge at x ~2.36 from the
    housing's end down to z ~0.40, then one smooth arc into the bottom edge, which curls forward and up.  Their foot (z 0.29) is the end of the bathtub's corner arc (bath_z at |y| = DIFF_W).
    hi / lod1: they are in the Thrusters node, black metal (N_WALL): a big flat GlossBlack plate seen from the side mirrors the studio's softbox as a white sheet (it was blazing white in p018)."""
    yo, t = DIFF_W, 0.011
    R_, xc, zc = 0.095, 2.267, 0.385 + DZ_TAIL          # the corner arc: centre (2.267, 0.385), radius 0.095: from the vertical trailing edge (x 2.362) to the bottom (z 0.29)
    da = 30 if level else 15
    arc = [(xc + R_ * math.cos(math.radians(a)), zc + R_ * math.sin(math.radians(a))) for a in range(0, -91, -da)]
    ep = [(x, z + DZ_TAIL) for x, z in ((1.98, 0.700), (2.10, 0.694), (2.20, 0.680), (2.28, 0.662), (2.335, 0.640), (2.355, 0.612), (2.362, 0.570), (2.362, 0.500))] + arc + \
         [(x, z + DZ_TAIL) for x, z in ((2.170, 0.294), (2.110, 0.304), (2.050, 0.322), (1.998, 0.346), (1.98, 0.360))]
    if level == 2:
        ep = ep[::2]
    for s in (-1, 1):
        prof_prism(cb, ep, s * (yo - t), s * yo, col=col)


def strake_edge(dx):
    """the rear (leading) edge polyline [(x, z)] of the strakes (knife blades), standing 10.8 cm off the tunnel wall at the top and sweeping forward to meet the wall at the foot; dx shifts it in x"""
    zt = SHELF_Z[0] + 0.004
    return [(WALL_X + 0.108 + dx, zt)] + [(WALL_X + ex + dx, z + DZ_TAIL) for ex, z in ((0.107, 0.44), (0.096, 0.375), (0.076, 0.32), (0.048, 0.272), (0.018, 0.236))] + \
           [(WALL_X + 0.004 + dx, BAY_Z0 + 0.004)]


def build_strakes(cb, level):
    """the strake blades (round 6: in the Thrusters node, black metal N_WALL, so their flat sides do not mirror the bright floor; 5 mm thick)"""
    zt = SHELF_Z[0] + 0.004
    prof = [(WALL_X - 0.012, zt)] + strake_edge(0.0) + [(WALL_X - 0.012, BAY_Z0 + 0.004)]
    for y in STRAKE_Y:
        prof_prism(cb, prof, y - 0.0025, y + 0.0025, col=N_WALL)


def holed_tile(cb, x, poly, hole, col, n=24, depth=0.0, bore=None, floor=None, cone=None):
    """one convex tile of a wall at x, polygon poly [(y, z)] (counter-clockwise seen from behind), with a round hole (yc, zc, r) cut out: a ring of quads from the circle to the
    polygon boundary (the polygon's corners are included as angles).  depth > 0: a cylindrical bore of that depth behind the wall (colour bore) closed by a floor disc (colour
    floor); cone = r_throat: the bore narrows to that radius (a funnel) instead of staying cylindrical.  No rim: the hole is flush with the wall."""
    yc, zc, r = hole
    ang = [2 * math.pi * i / n for i in range(n)] + [math.atan2(p[1] - zc, p[0] - yc) % (2 * math.pi) for p in poly]
    ang = sorted(set(round(a, 9) for a in ang)) if True else ang
    def hit(a):
        d = (math.cos(a), math.sin(a)); best = None
        for i in range(len(poly)):
            p, q = poly[i], poly[(i + 1) % len(poly)]
            ex, ey = q[0] - p[0], q[1] - p[1]
            den = d[0] * ey - d[1] * ex
            if abs(den) < 1e-12:
                continue
            t = ((p[0] - yc) * ey - (p[1] - zc) * ex) / den
            u = ((p[0] - yc) * d[1] - (p[1] - zc) * d[0]) / den
            if t > 0 and -1e-9 <= u <= 1 + 1e-9 and (best is None or t < best):
                best = t
        return (yc + best * d[0], zc + best * d[1])
    inner = [cb.v((x, yc + r * math.cos(a), zc + r * math.sin(a))) for a in ang]
    outer = [cb.v((x,) + hit(a)) for a in ang]
    for i in range(len(ang)):
        j = (i + 1) % len(ang)
        if inner[i] is not inner[j]:
            cb.face([inner[i], outer[i], outer[j], inner[j]], col)
    if depth > 0:
        rt = cone if cone is not None else r
        deep = [cb.v((x - depth, yc + rt * math.cos(a), zc + rt * math.sin(a))) for a in ang]
        for i in range(len(ang)):
            j = (i + 1) % len(ang)
            cb.face([inner[j], inner[i], deep[i], deep[j]], bore or col)
        c0 = cb.v((x - depth, yc, zc))
        for i in range(len(ang)):
            j = (i + 1) % len(ang)
            cb.face([c0, deep[j], deep[i]], floor or bore or col)


def outlet_plate(cb, level):
    """the back wall of the nozzle channel: dark satin carbon-grey, a mosaic of tiles (one per 0.135 m lattice cell) so that the round holes of the mounts beside the nozzles are
    real recessed black holes (3.5 cm deep, no rim); the nozzle barrels close their own cells.  The wall is the trapezoid of the housing (the chamfered end corners)."""
    z0, z1 = SHELF_Z[1], TOP_Z[0]
    w = min(CH_Y0 + (DIFF_W - CH_Y0) * (z1 - z0) / CH_CHAMF, DIFF_W - 0.016)         # the chamfer line meets the shelf at |y| = w
    hw = 0.0675
    n = (28, 10, 8)[level]
    holes = {round(y, 3): (y, JET_Z - (0.005 if abs(y) > 0.4 else 0.0), r) for y, r in zip(PORT_Y, PORT_R)}
    for k in range(-4, 5):
        yc = 0.135 * k
        if abs(k) < 4:
            poly = [(yc - hw, z0), (yc + hw, z0), (yc + hw, z1), (yc - hw, z1)]
        else:      # the end tiles follow the chamfer
            sg = 1 if k > 0 else -1
            poly = [(sg * (4 * 0.135 - hw), z0), (sg * w, z0), (sg * CH_Y0, z1), (sg * (4 * 0.135 - hw), z1)]
            poly = poly if sg > 0 else poly[::-1]
        h = next((v for yy, v in holes.items() if abs(yy - yc) < 0.02 or (abs(k) == 4 and abs(yy - yc) < 0.03)), None)
        if h is None:
            cb.face([cb.v((CH_X, p[0], p[1])) for p in poly], N_WALL)
        else:
            holed_tile(cb, CH_X, poly, h, N_WALL, n=n, depth=0.035, bore=N_VOID, floor=N_VOID)


def build_jets(cb, level):
    """main thruster nozzles: a polished gold lip and heat-tinted bell on a black barrel that stands ~6 cm out of the channel wall;
    between them the black PORT TUBES, about the nozzles' diameter, further back and a little higher (their tops tuck behind the
    crossbeam)."""
    st = (40, 20, 10)[level]
    for yc in JET_Y:
        prof = [(0.0500, -0.004), (0.0505, 0.006), (0.0490, 0.0155), (0.0470, 0.0185), (0.0452, 0.0165), (0.0440, 0.009),
                (0.0405, -0.016), (0.032, -0.036), (0.024, -0.048), (0.0, -0.048)]          # round 3: a THIN champagne lip (rim ~5 mm wide, flush with the barrel), not a fat pale ring
        cb.lathe(prof, st, [N_GOLD] * 5 + [N_BELL, N_DEEP, N_DEEP, N_THROAT], axis_x=True, at=(JET_X, yc, JET_Z))
        cb.lathe([(0.0505, -0.0035), (0.0505, -(JET_X - CH_X)), (0.0, -(JET_X - CH_X))], st,
                 [N_SHROUD, N_PORT], axis_x=True, at=(JET_X, yc, JET_Z))


def build_tunnels(cb, level):
    """the back wall of the four tunnels (dark satin, a mosaic of tiles) with one DEEP CONICAL duct per bay, aligned with its nozzle: a SMALL round hole flush with the wall (no rim: r 0.030, thrust / p017 show
    holes ~45 % of a nozzle's diameter), a black funnel narrowing to r 0.014 over 7.5 cm, closed by a black floor (near-black inside)."""
    x = WALL_X
    z0, z1 = BAY_Z0, SHELF_Z[0]
    n = (28, 10, 8)[level]
    nz = (4, 1, 1)[level]           # round 6: the tiles' edges carry extra nodes (hi) so that the module warp's twist is spread over small quads: the walls stay clean
    zs = [z0 + (z1 - z0) * i / nz for i in range(nz + 1)]
    for yc in JET_Y:
        h = 0.135
        poly = [(yc - h, z0), (yc, z0), (yc + h, z0)] + [(yc + h, z) for z in zs[1:-1]] + [(yc + h, z1), (yc, z1), (yc - h, z1)] + [(yc - h, z) for z in zs[-2:0:-1]]
        holed_tile(cb, x, poly, (yc, 0.350 + DZ_TAIL, 0.030), N_WALL, n=n, depth=0.075, bore=N_VOID, floor=N_VOID, cone=0.014)
    w = DIFF_W - 0.016
    ya = [0.54, 0.57, 0.60, 0.62, 0.64, 0.66, w] if level == 0 else [0.54, 0.60, 0.65, w]            # (the outer side piece in strips, so that the bathtub warp can bend the wall's foot into the corner arc)
    for sg in (-1, 1):
        for y0, y1 in zip(ya, ya[1:]):
            for za, zb_ in zip(zs, zs[1:]):
                cb.face([cb.v((x, sg * y0, za)), cb.v((x, sg * y1, za)), cb.v((x, sg * y1, zb_)), cb.v((x, sg * y0, zb_))][::sg], N_WALL)


def glass_cover(ctx, cb, level):
    """dark bronze panel 35 mm under the rear glass (the bay behind the cabin): through the bronze tint it reads as the
    opaque bronze deck of the press shots instead of a see-through hole."""
    nu, nv = ((10, 24), (6, 10))[level]
    x0, x1 = 1.05, 2.07
    hw = lambda x: ctx.A.glass_half_width(x) + 0.004                              # glass half width (the glass edge between the sails), the edges tuck under the paint
    grid = []
    for i in range(nv):
        x = x0 + (x1 - x0) * i / (nv - 1)
        row = []
        for j in range(nu):
            p, _ = ctx.surf.cast((x, (-1 + 2 * j / (nu - 1)) * hw(x), 3.0), (0, 0, -1), 0.0, 4.0)
            row.append(None if p is None else cb.v(p - Vector((0, 0, 0.035))))
        grid.append(row)
    for i in range(nv - 1):
        for j in range(nu - 1):
            vs = [grid[i][j], grid[i][j + 1], grid[i + 1][j + 1], grid[i + 1][j]]
            if all(v is not None for v in vs):
                cb.face(vs, N_COVER)


# --- the wing's seam (REAR_T17; user 2026-10-23: "原车的车尾和玻璃之间有一条贯穿的缝隙，那条缝隙事实上升起来就是车辆的尾翼了").  p013: straight across the whole width at x 2.04
# (the centre, where it is the rear glass's end) .. 2.025 (|y| 0.9), over both ridges and shoulders to the body's side edge; p018: it crosses the shoulder line L at x ~2.01 and runs down
# the side, just aft of the corner facet's front edge, to the black zone (l3) at x 2.145.  The rest of the wing's outline (l3, the tail's side edges, the tail top edge over the light box)
# is a colour boundary or a crease already.  A hairline like the door seams (SIDE): PanelGap, 3 mm on paint.
SEAM_X = (2.05, 2.02)            # top seam: x at the centre (the glass end) and at L
SEAM_SIDE_X = 2.145              # side seam: x where it meets l3
SEAM_W = 0.0030                  # hairline width on paint (m)


def _strip(ctx, M, cl, width, off):
    """hairline along the centre line cl [(point, normal)] laid on the HI surface (as side.strip_along + side._grid): the edges are the centre line moved +-width / 2 across and re-cast"""
    cast = ctx.surf_hi.cast
    P, N = [], []
    for i, (c, n) in enumerate(cl):
        a, b = cl[max(i - 1, 0)][0], cl[min(i + 1, len(cl) - 1)][0]
        w = (b - a).normalized().cross(n).normalized()
        rp, rn = [], []
        for s_ in (-0.5, 0.5):
            q = c + w * (s_ * width)
            p, nn = cast(q + n * 0.02, -n, off, 0.06)
            if p is None:
                p, nn = q + n * off, n
            rp.append(p)
            rn.append(nn)
        P.append(rp)
        N.append(rn)
    V = [[M.v(p) for p in row] for row in P]
    for i in range(len(V) - 1):
        vs = [V[i][0], V[i + 1][0], V[i + 1][1], V[i][1]]
        nn = N[i][0] + N[i + 1][0] + N[i + 1][1] + N[i][1]
        gn = (vs[1].co - vs[0].co).cross(vs[3].co - vs[0].co) + (vs[3].co - vs[2].co).cross(vs[1].co - vs[2].co)
        M.face(vs if gn.dot(nn) >= 0 else vs[::-1])


def wing_seam(ctx, level):
    """-> [object]: the top seam across the whole width (cast down) and the two side seams (cast in from the side), one PanelGap object"""
    if not REAR_T17 or level > 1:
        return []
    D, cast = ctx.A.D, ctx.surf_hi.cast
    step, width, off = (0.005, 0.02)[level], SEAM_W * (1.0, 1.5)[level], (0.0008, 0.0035)[level]
    xs = lambda a: SEAM_X[0] - (SEAM_X[0] - SEAM_X[1]) * smooth(0.30, 1.0, a / yl)
    yl = float(D.CURVES['L'].at(SEAM_X[1])[1]) - 0.002
    M = Mesh()
    top = []
    for i in range(int(2 * yl / step) + 1):
        y = -yl + i * step
        p, n = cast(Vector((xs(abs(y)), y, 2.5)), Vector((0, 0, -1)), 0.0, 5.0)
        if p is not None:
            top.append((p, n))
    _strip(ctx, M, top, width, off)
    zl, z3 = float(D.CURVES['L'].at(SEAM_X[1])[2]), float(D.CURVES['l3'].at(SEAM_SIDE_X)[2])
    m = max(2, int(math.hypot(SEAM_SIDE_X - SEAM_X[1], zl - z3) / step) + 1)
    for sd in (-1, 1):
        side = []
        for i in range(m + 1):
            t = i / m
            p, n = cast(Vector((SEAM_X[1] + t * (SEAM_SIDE_X - SEAM_X[1]), sd * 2.5, zl - 0.004 + t * (z3 + 0.004 - zl))), Vector((0, -sd, 0)), 0.0, 4.0)
            if p is not None:
                side.append((p, n))
        _strip(ctx, M, side, width, off)
    if M.empty():
        M.bm.free()
        return []
    mat = ctx.mat_of(level, 'PanelGap')
    return [ctx.mk(M.bm, 'WingSeam', mat, True)] if mat else []


def wing_footprint(ctx, name, mat, level, off, hi_n=(26, 72), lo_n=(7, 26)):
    """grid cast on the shell's top surface: the whole stowed wing panel = every face aft of the seam (x 2.05) above the lamp band, out to |y| WING_Y: the deck, the ear-inner
    triangles, the ridge and the rear-shoulder (R-6) surface.  (A copy in a NEW object: the locked shell's own vertices stay where they are.)  Rows follow the tail edge, which is
    plan-convex (x of the tail face decreases with |y|)."""
    nu, nv = hi_n if level == 0 else lo_n
    D = ctx.A.D
    xe = lambda y: float(D.tail_x(abs(y), 1.0)) - 0.003
    return ctx.patch(name, mat, ((0.0, 1.0), (-1.0, 1.0)), lambda a, b: (WING_X[0] + a * (xe(b * WING_Y) - WING_X[0]), b * WING_Y, 3.0), (0, 0, -1), off, nu, nv)


def wing_parts(ctx, level):
    """tips (flat blades from the panel's edge out to the tip), endplates (hang from the tips, canted outward) and the two struts, in pivot-local coordinates -> (paint CB, strut CB)"""
    CB = ctx.CB
    cp, cs = CB(), CB()
    P = WING_P
    xs = [WING_X[0] + (WING_X[1] + 0.05 - WING_X[0]) * i / 4 for i in range(5)]
    ze = {x: (deck_z(ctx.surf, min(x, 2.35), WING_Y - 0.01) or 1.0) - 0.004 for x in xs}          # the panel's outer edge height: the tips continue it
    zt = lambda x: pchip([(k, v) for k, v in ze.items()], min(max(x, xs[0]), xs[-1]))
    for s_ in (-1, 1):
        # tip blade: thin wedge from just inside the panel's edge out to the tip, front edge at the seam, trailing edge = the visor's reach
        secs = []
        for y in (WING_Y - 0.05, 0.5 * (WING_Y + TIP_Y), TIP_Y):
            secs.append([(x - P.x, s_ * y, zt(x) - P.z) for x in xs] + [(x - P.x, s_ * y, zt(x) - 0.010 - P.z) for x in xs[::-1]] + [(xs[0] - P.x, s_ * y, zt(xs[0]) - P.z)])
        cp.prism(secs, [W_DARK] * (len(secs[0]) - 1), cap=W_DARK)
        # endplate: trapezoid hanging below the tip, leaning outward (012: the plates flare out at the bottom)
        pl = [(2.07, 0.0), (2.43, 0.0), (2.43, -0.28), (2.30, -0.25), (2.17, -0.14), (2.07, -0.06)]
        sec_a = [(x - P.x, s_ * TIP_Y, zt(x) + dz - P.z) for x, dz in pl + [pl[0]]]
        sec_b = [(x - P.x, s_ * (TIP_Y + 0.004) + s_ * 0.30 * max(0.0, -dz), zt(x) + dz - P.z) for x, dz in pl + [pl[0]]]
        cp.prism([sec_a, sec_b], [W_DARK] * len(pl), cap=W_DARK)
        # strut: thin dark blade under the panel at |y| 0.49.  It sits near the front (x 2.14) so that, after the 33 deg pitch and the 0.10 m slide aft, its foot (0.16 m long) is
        # still inside the body: foot at x ~2.31 (the tail face is at 2.38) and z ~0.92 (the shoulder surface is at 1.04..1.06)
        x0, L = 2.14, 0.16
        z0 = (deck_z(ctx.surf, x0, STRUT_Y) or 1.06) - 0.008
        st = [(x0 - 0.016 - P.x, z0 - P.z), (x0 + 0.016 - P.x, z0 - P.z), (x0 + 0.010 - P.x, z0 - L - P.z), (x0 - 0.010 - P.x, z0 - L - P.z)]
        cs.prism([[(a, s_ * STRUT_Y + dy, b) for a, b in st + [st[0]]] for dy in (-0.008, 0.008)], [W_DARK] * len(st), cap=W_DARK)
    return cp, cs


def build_wing(ctx, level):
    """-> Wing (the stowed panel copy, local coordinates, node at WING_P) with the child WingPlates (tips + endplates + struts)"""
    ob = wing_footprint(ctx, 'Wing', 'Paint', level, 0.0 if level == 0 else 0.002)
    ob.data.transform(Matrix.Translation(-WING_P))
    ob.location = WING_P
    cp, cs = wing_parts(ctx, level)
    kids = ctx.join([ctx.cb_obj(cp, 'WingPlates', 'Paint', sharp=30), ctx.cb_obj(cs, 'WingPosts', 'Carbon' if level == 0 else 'Paint', sharp=30)], 'WingPlates')
    kids.parent = ob            # tips, endplates and struts: the game scales them in (tips slide out, plates drop) as the wing deploys
    return ob


# --- step 3 (REAR_T17; user 2026-10-23: "那条缝隙事实上升起来就是车辆的尾翼"): the wing is the WHOLE piece inside the seam.  001 (side, raised): the deck, the ears, the rear shoulders and the
# rear-corner facets lift as one body-colour shell, the facets hanging from it as its endplates, dark lip and linkage under its front; high / 012 (behind): its trailing edge is one straight
# level blade (the level tail edge, design2 QF_Q17).  Wing = the shell's own surface inside the seam outline (top: seam -> tail edge, out to L; each side: the corner facet aft of the side
# seam, down to l3) with a thickness and a dark underside and rims; WingWell = the same outline in gloss black (the cut-outs down the sides included); WingPlates = the struts and the
# linkage only (they drop in as it deploys; no tips sliding out, no separate endplates).
W17_T, W17_TF = 0.016, 0.010             # thickness of the panel and of the endplates
W17_N = ((24, 64, 9), (7, 22, 4))       # per level: rows seam -> tail edge, columns across, rows down each facet
W17_DEP = dict(dx=0.28, dy=0.13, rot=0.45)   # raised: 0.28 m aft, 0.13 m up, 26 deg trailing edge up about WING_P (001 mapped onto the matched p018 camera by the wheel hubs: the deck's front edge and the
                                            # tail corner of the raised piece); `high` shows it steeper still, ~57 deg = this + the game's airbrake pitch (index.js wingA, up to 0.55 rad)


def w17_lines(ctx):
    """the shell's own L and l3 (shell2 edges; L aft of the facet apex is the facet's straight edge) as x -> y / z, the tail face's x at the corner, the seam (as wing_seam)"""
    c = ctx.cache.get('w17')
    if c is None:
        import numpy as np
        D, R = ctx.A.D, ctx.A.S2.Registry()
        L, l3 = np.asarray(R.edge('L'), float), np.asarray(R.edge('l3'), float)
        L, l3 = L[L[:, 0] > 1.8], l3[l3[:, 0] > 1.8]
        yl = float(D.CURVES['L'].at(SEAM_X[1])[1]) - 0.002
        zl, z3 = float(np.interp(SEAM_X[1], L[:, 0], L[:, 2])), float(np.interp(SEAM_SIDE_X, l3[:, 0], l3[:, 2]))
        c = types.SimpleNamespace(
            xs=lambda ay: SEAM_X[0] - (SEAM_X[0] - SEAM_X[1]) * smooth(0.30, 1.0, ay / yl),
            xe=lambda ay: float(D.tail_x(ay, 1.0)) - 0.003,
            yL=lambda x: float(np.interp(x, L[:, 0], L[:, 1])) - 0.0015,
            xL1=float(L[-1, 0]),
            zb=lambda x: (zl - 0.004 + (x - SEAM_X[1]) / (SEAM_SIDE_X - SEAM_X[1]) * (z3 + 0.008 - zl)) if x <= SEAM_SIDE_X else float(np.interp(x, l3[:, 0], l3[:, 2])) + 0.004,
            xr=lambda z: float(D.tail_x(0.94, z)) - 0.003)
        ctx.cache['w17'] = c
    return c


def w17_skin(ctx, level, off):
    """the outline's surface, cast on the level's body `off` out along its normal: (top[i][j], fac[s][i][k]) of (point, normal) or None; fac[s][i][0] IS top[i][edge column]"""
    W = w17_lines(ctx)
    nu, nv, nk = W17_N[min(level, 1)]
    cast = ctx.surf.cast
    top = [[None] * nv for _ in range(nu)]
    for i in range(nu):
        u = i / (nu - 1)
        for j in range(nv):
            v = -1.0 + 2.0 * j / (nv - 1)
            x = W.xs(0.9)
            for _ in range(4):
                y = v * W.yL(x)
                x = W.xs(abs(y)) + u * (W.xe(abs(y)) - W.xs(abs(y)))
            p, n = cast(Vector((x, y, 3.0)), Vector((0, 0, -1)), off, 4.0)
            for k in range(12):                 # (L's crease is rounded: the top ends 2 - 3 mm inside L; the edge columns step in until they land on it)
                if p is not None and n.z > 0.3:
                    break
                y -= math.copysign(0.001, v)
                p, n = cast(Vector((x, y, 3.0)), Vector((0, 0, -1)), off, 4.0)
            top[i][j] = None if p is None or n.z <= 0.3 else (p, n)
    fac = {}
    for s in (-1, 1):
        je = nv - 1 if s > 0 else 0
        F = []
        for i in range(nu):
            a = top[i][je]
            col = [a]
            if a is not None:
                zb = min(W.zb(a[0].x), a[0].z - 0.003)
                for k in range(1, nk):
                    z = a[0].z + (zb - a[0].z) * k / (nk - 1)
                    x = min(a[0].x, W.xr(z))
                    p, n = cast(Vector((x, s * 2.5, z)), Vector((0, -s, 0)), off, 3.0)
                    col.append(None if p is None else (p, n))
            else:
                col += [None] * (nk - 1)
            F.append(col)
        fac[s] = F
    return top, fac


def w17_sheets(M, top, fac, IT=None, IF=None):
    """quads of the top grid and both facet grids into Mesh M: outer (the cast points, facing along the normals) or, with IT / IF, the inner points (facing in)"""
    nu, nv = len(top), len(top[0])
    sg = 1.0 if IT is None else -1.0
    VT = [[None if top[i][j] is None else M.v(top[i][j][0] if IT is None else IT[i][j]) for j in range(nv)] for i in range(nu)]
    for i in range(nu - 1):
        for j in range(nv - 1):
            q = [(i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1)]
            if all(VT[a][b] is not None for a, b in q):
                M.face([VT[a][b] for a, b in q], sg * sum((top[a][b][1] for a, b in q), Vector((0, 0, 0))))
    for s, F in fac.items():
        je = nv - 1 if s > 0 else 0
        V = [[VT[i][je] if k == 0 else (None if F[i][k] is None else M.v(F[i][k][0] if IF is None else IF[s][i][k])) for k in range(len(F[i]))] for i in range(nu)]
        for i in range(nu - 1):
            for k in range(len(F[i]) - 1):
                q = [(i, k), (i + 1, k), (i + 1, k + 1), (i, k + 1)]
                if all(V[a][b] is not None for a, b in q):
                    M.face([V[a][b] for a, b in q], sg * sum((F[a][max(b, 1)][1] for a, b in q), Vector((0, 0, 0))))


def build_wing17(ctx, level):
    """-> Wing: the piece inside the seam (paint outside; gloss black underside and rims), pivot-local, with the child WingPlates (struts + linkage)"""
    top, fac = w17_skin(ctx, level, 0.0 if level == 0 else 0.002)
    nu, nv = len(top), len(top[0])
    IT = [[None if q is None else q[0] - q[1] * W17_T for q in row] for row in top]
    IF = {}
    for s, F in fac.items():
        je = nv - 1 if s > 0 else 0
        for i in range(nu):
            if top[i][je] is not None and F[i][1] is not None:          # on L: off along both the panel's and the endplate's normal
                IT[i][je] = top[i][je][0] - top[i][je][1] * W17_T - F[i][1][1] * W17_TF
        IF[s] = [[IT[i][je] if k == 0 else (None if F[i][k] is None else F[i][k][0] - F[i][k][1] * W17_TF) for k in range(len(F[i]))] for i in range(nu)]
    Mo, Mi = Mesh(), Mesh()
    w17_sheets(Mo, top, fac)
    w17_sheets(Mi, top, fac, IT, IF)

    def rim(a, ia, b, ib, ref):
        """a thickness face from the outer edge a -> b to the inner one (dark mesh, own copies), facing away from ref (a point inside the outline)"""
        if a is None or b is None or ia is None or ib is None:
            return
        Mi.face([Mi.v(a[0]), Mi.v(b[0]), Mi.v(ib), Mi.v(ia)], 0.5 * (a[0] + b[0]) - ref)
    for i, i2 in ((0, 1), (nu - 1, nu - 2)):                   # leading edge (the top seam), trailing edge (the tail's top edge)
        for j in range(nv - 1):
            if top[i2][j] is not None:
                rim(top[i][j], IT[i][j], top[i][j + 1], IT[i][j + 1], top[i2][j][0])
    for s, F in fac.items():
        nk = len(F[0])
        for i in range(nu - 1):                                  # each endplate's front (the side seam) and bottom (l3) edge
            if F[i][nk - 2] is not None:
                rim(F[i][nk - 1], IF[s][i][nk - 1], F[i + 1][nk - 1], IF[s][i + 1][nk - 1], F[i][nk - 2][0])
        for i, i2 in ((0, 1), (nu - 1, nu - 2)):                # its first column (at the top seam) and its rear edge (the tail corner)
            for k in range(nk - 1):
                if F[i2][k] is not None:
                    rim(F[i][k], IF[s][i][k], F[i][k + 1], IF[s][i][k + 1], F[i2][k][0])
    o1 = ctx.mk(Mo.bm, 'Wing', 'Paint', True)
    o2 = ctx.mk(Mi.bm, 'WingUnder', ctx.mat_of(level, 'GlossBlack'), True)
    ctx.mark_sharp(o2.data, 30)
    ob = ctx.join([o1, o2], 'Wing')
    ob.data.transform(Matrix.Translation(-WING_P))
    ob.location = WING_P
    kids = ctx.cb_obj(wing17_links(ctx, level), 'WingPlates', 'Carbon' if level == 0 else 'Paint', sharp=30)
    kids.parent = ob            # struts and linkage: the game drops them in (scaleY) as the wing deploys
    return ob


def wing17_links(ctx, level):
    """the two struts (high, 012: |y| 0.49) and the linkage arms under the piece's front (001), pivot-local.  Raised (W17_DEP) the piece hovers behind the tail (001: it slides
    0.28 m aft), so each link runs from the piece's underside near its front forward and down into the body's well: built between the attach point (piece frame) and the body
    anchor carried into the piece's frame by the inverse of the deploy pose, it meets the body exactly when the wing is fully up"""
    cs = ctx.CB()
    P, d = WING_P, W17_DEP
    c, sn = math.cos(d['rot']), math.sin(d['rot'])

    def to_piece(w):                    # world (deployed) -> the piece's own (stowed) frame
        x, z = w.x - d['dx'] - P.x, w.z - d['dy'] - 0.003 - P.z
        return Vector((P.x + x * c + z * sn, w.y, P.z - x * sn + z * c))

    def link(xa, yy, xb, half, depth):
        za = (deck_z(ctx.surf, xa, yy) or 1.05) - W17_T - 0.002
        zb = (deck_z(ctx.surf, xb, yy) or 1.0) - 0.012
        A, B = Vector((xa, yy, za)), to_piece(Vector((xb, yy, zb)))
        t = (B - A).normalized()
        nn = t.cross(Vector((0, 1, 0))).normalized()
        sec = [(A + nn * u - P, B + nn * u * 0.7 - P) for u in (-half, half)]
        ring = lambda dy: [tuple(sec[0][0] + Vector((0, dy, 0))), tuple(sec[1][0] + Vector((0, dy, 0))), tuple(sec[1][1] + Vector((0, dy, 0))), tuple(sec[0][1] + Vector((0, dy, 0)))]
        r0, r1 = ring(-depth), ring(depth)
        cs.prism([r0 + [r0[0]], r1 + [r1[0]]], [W_DARK] * 4, cap=W_DARK)
    for s_ in (-1, 1):
        link(2.13, s_ * STRUT_Y, 2.24, 0.016, 0.008)                  # strut
        if level == 0:
            for yy, xb in ((0.62, 2.17), (0.80, 2.12)):               # linkage arms
                link(2.08, s_ * yy, xb, 0.010, 0.006)
    return cs


def wing17_well(ctx, level):
    """WingWell: the outline (top and the side cut-outs) in gloss black, 1.5 mm off the body"""
    top, fac = w17_skin(ctx, level, 0.0015 if level == 0 else 0.004)
    M = Mesh()
    w17_sheets(M, top, fac)
    return ctx.mk(M.bm, 'WingWell', ctx.mat_of(level, 'GlossBlack'), True)


# ----------------------------------------------------------------------------- region hooks (regions/ctx.py)
def shell_post(ctx):
    """tail colour split on the HI body: the black / body-colour outline (lobe bell + cheek line, see bound_z) is cut into the dense mesh, THEN the arches"""
    body = ctx.body
    if len(body.data.materials) <= BLACK_SLOT:                # the 4th slot: GlossBlack (hi body only; the LOD bodies get theirs in lod_post)
        body.data.materials.append(bpy.data.materials['GlossBlack'])
    refine_tail(body, 0.033)
    refine_tail(body, 0.0165, lambda c: c.x > 2.0 and abs(c.z - lobe_edge(abs(c.y))) < 0.07 and abs(c.y) < 0.92)
    print('outline cut (new vertices, faces recoloured):', cut_boundary(body))
    if os.environ.get('REAR_DEBUG'):
        hi = [p for p in body.data.polygons if p.material_index == 2 and p.center.x > 2.0 and p.center.z > 0.93]
        print('REAR_DEBUG black faces above z 0.93 aft of x 2.0:', len(hi))
        if hi:
            import numpy as np
            c = np.array([tuple(p.center) for p in hi]); print('  x %.3f..%.3f  |y| %.3f..%.3f  z %.3f..%.3f' % (c[:, 0].min(), c[:, 0].max(), abs(c[:, 1]).min(), abs(c[:, 1]).max(), c[:, 2].min(), c[:, 2].max()))


def lod_post(ctx, level, body):
    """the collapse smears the tail's paint / black outline: redo it on the decimated faces"""
    blacken_tail(body, 0.06, strict=True, oldbody=ctx.oldbody)
    if level == 1:        # lod1 keeps the gloss black of the tail (GlossBlack is already a lod1 material: the light band); lod2 stays Trim (no new draw call there)
        mats = body.data.materials
        gbm = bpy.data.materials['GlossBlack']
        slot = next((i for i, m in enumerate(mats) if m == gbm), None)
        if slot is None:
            mats.append(gbm)
            slot = len(mats) - 1
        for p in body.data.polygons:
            # round 7: the side facets of the rear corners (normal mostly lateral) and the faces that look steeply down (the lower tail plane, the under-tray) stay matt Trim at lod1: the decimated
            # facets read as teal / pale mirror strips in the game (the hi body keeps the studio's gloss: its facets are clean, and the plane is covered, see plane_cover)
            if p.material_index == 2 and p.center.x > GLOSS_X0 and abs(p.normal.y) < 0.45 and p.normal.z > -0.55:
                p.material_index = slot


def build(ctx, level):
    """-> static objects for the body.  level 2 merges everything static (no node): the nozzle ring, the plain walls and the deployed wing come here too."""
    K = consts(ctx)
    stat = build_tail_skin(ctx, level) + [build_tail_lip(ctx, level)] + wing_seam(ctx, level)
    cm = 'GlossBlack' if level < 2 else 'Trim'          # round 5: the diffuser is black (Carbon read mid-grey in the studio light)
    cb = ctx.CB()
    build_diffuser(cb, level)
    stat.append(ctx.cb_obj(cb, 'Diffuser', cm, sharp=30))
    # (round 7: the dark blade fins at the rear corners, outboard of the diffuser (CornerFin_*), are gone: their flat GlossBlack side mirrored the studio's white panel as the white diagonal sliver and the white
    #  patch in p018, and as black metal they still made facets; p017 / p018 show a smooth black corner there)
    B = ctx.Builder()
    # plate backing and the reversing camera pod (parallel to the leaning tail face)
    pc = fascia(ctx, sum(PLATE['z']) / 2, off=0.006)
    B.rbox('Trim' if level < 2 else 'Paint', tuple(pc), (0.012, 0.356, 0.182), rot=(0, K.FAS_LEAN, 0), bev=0.003 if level < 2 else 0, seg=1)
    if level < 2:        # camera pod above the plate with a small plate lamp each side (thrusters photo)
        zc = 0.866 + DZ_TAIL
        B.rbox('Trim', tuple(fascia(ctx, zc, off=0.014)), (0.030, 0.092, 0.036), rot=(0, K.FAS_LEAN, 0), bev=0.007 if level == 0 else 0.0, seg=2 if level == 0 else 1)
        if level == 0:
            B.cylinder('GlossBlack', tuple(fascia(ctx, zc - 0.004, y=0.018, off=0.0305)), (0, 90 + K.FAS_LEAN, 0), 0.0105, 0.006, seg=16)
        for sy in (-1, 1):
            B.rbox('Trim', tuple(fascia(ctx, zc + 0.002, y=sy * 0.118, off=0.0105)), (0.014, 0.086, 0.020), rot=(0, K.FAS_LEAN, 0), bev=0.003, seg=1)
            if level == 0:      # DR-4: the two reverse lamps (white lens in a dark housing) flank the camera
                B.rbox('ReverseLamp', tuple(fascia(ctx, zc + 0.002, y=sy * 0.118, off=0.0185)), (0.004, 0.070, 0.0095), rot=(0, K.FAS_LEAN, 0), bev=0.0, seg=1)
    stat += B.objects('Rear', sharp=40)
    if level < 2:
        return stat
    ring = ctx.CB()
    for yc in JET_Y:
        ring.lathe([(0.04, -0.004), (0.054, 0.014), (0.045, 0.016), (0.0, 0.0)], 10, N_GOLD, axis_x=True, at=(JET_X, yc, JET_Z))
    stat.append(ctx.cb_obj(ring, 'Thrusters', 'IntAccent'))
    Bn = ctx.Builder()
    Bn.rbox('Trim', (CH_X - 0.005, 0, JET_Z), (0.01, 2 * (DIFF_W - 0.016), 2 * CELL), bev=0, seg=1)      # nozzle channel wall, no holes
    Bn.rbox('Trim', (WALL_X - 0.005 - 0.5 * TUCK, 0, 0.5 * (BAY_Z0 + SHELF_Z[0])), (0.01, 2 * (DIFF_W - 0.016), SHELF_Z[0] - BAY_Z0), bev=0, seg=1)        # tunnels: plain back wall
    stat += Bn.objects('RearN', sharp=40)
    return stat                     # (lod2 has no Wing node: it is fixed in the stowed state = the shell's deck, nothing extra is drawn)


N_PLANE = (0.012, 0.012, 0.0135, 0.62)   # the skin over the lower tail plane: black metal like N_WALL but with a reflectance of 1.2 % (the studio shows the GlossBlack it covers at ~1 %: with 0.4 % it was a darker patch with hard edges in p017 / p018)
PL_C = 1.413                     # round 7: the lower tail plane outboard of the endplates (z 0.29 .. 0.685, normal (0.8, 0, -0.6): it faces aft and steeply DOWN): 0.8 x - 0.6 z = PL_C
PL_Z = (0.285, 0.685)


def plane_cover(ctx, cb, level):
    """round 7 (game, hi and lod1): a clear-coat GlossBlack plane that faces the ground mirrors the street's neon (cyan / magenta / white stripes with stair-stepped edges, read as a pale plate beside the endplate in
    rear34 / rearlow).  The two patches of it outboard of the endplates (|y| 0.70 .. 0.93) are covered by a thin black-metal skin (N_PLANE: reflectance 1.2 %, near-black in the game, where it is blurred (a=0.62), and as dark as the gloss it covers in the studio), cast onto the HI shell's surface (6 mm off; 30 mm at lod1, which clears the lod1 tray: it rides 12 mm off the decimated body)."""
    nu, nv = ((14, 6), (4, 4))[level]
    off = (0.006, 0.030)[level]
    n_pl = Vector((0.8, 0.0, -0.6))
    for s in (-1, 1):
        grid = []
        for i in range(nu):
            row = []
            for j in range(nv):
                z = PL_Z[0] + (PL_Z[1] - PL_Z[0]) * j / (nv - 1)
                y1 = min(0.932, 0.905 + 0.30 * (z - 0.396))                      # the plane ends at the diagonal crease to the side facet of the corner (0.89 at z 0.40 .. 0.92 from z 0.50): the skin runs 1 cm over the crease
                y = (DIFF_W - 0.005) + (y1 - DIFF_W + 0.005) * i / (nu - 1)      # starts tucked into the endplate
                x = (PL_C + 0.6 * z) / 0.8
                p, n = ctx.surf_hi.cast(Vector((x, s * y, z)) + n_pl * 0.15, -n_pl, off, 0.4)
                row.append(cb.v(p) if p is not None and (n.dot(n_pl) > 0.7 or abs(n.y) > 0.7) else None)      # the plane itself, or the side facet it runs into (not the floor)
            grid.append(row)
        for i in range(nu - 1):
            for j in range(nv - 1):
                vs = [grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]]
                if all(v is not None for v in vs):
                    cb.facen(vs, N_PLANE, n_pl)


def nodes(ctx, level):
    """separately exported nodes (levels 0 / 1): the thruster module and the active wing (which carries the child WingPlates)"""
    if level >= 2:
        return {}
    cbj = ctx.CB()
    outlet_plate(cbj, level)
    build_jets(cbj, level)
    n0 = len(cbj.bm.verts)
    build_tunnels(cbj, level)
    build_strakes(cbj, level)
    warp_verts(cbj, n0)                 # the tunnel walls and strakes follow the module's warp (bathtub, plan sweep, tuck: the same function as the diffuser's own parts)
    build_endplates(cbj, level, N_WALL)    # (final frame: not warped)
    plane_cover(ctx, cbj, level)
    glass_cover(ctx, cbj, level)
    thr = ctx.cb_obj(cbj, 'Thrusters', 'Nozzle', keep_color=True, sharp=35)
    if REAR_T17:                    # step 3: the whole piece inside the seam
        return {'Thrusters': thr, 'Wing': build_wing17(ctx, level), 'WingWell': wing17_well(ctx, level)}
    well = wing_footprint(ctx, 'WingWell', 'GlossBlack', level, 0.0015 if level == 0 else 0.004, hi_n=(30, 80), lo_n=(7, 26))
    return {'Thrusters': thr, 'Wing': build_wing(ctx, level), 'WingWell': well}


def decals(ctx, level):
    if level > 1:
        return []            # (lod2 has no Decals node: the plate is not drawn there)
    n = (12, 4) if level == 0 else (6, 3)
    return [ctx.patch('Decal_plate', 'Decal', (PLATE['y'], PLATE['z']), lambda a, bb: (3.5, a, bb), (-1, 0, 0), (0.020, 0.030, 0.034)[level],
                      n[0], n[1], uv_rect=PLATE['uv'])]


def meta(ctx):
    """car_meta.json entries.  Active wing (LOD0 / LOD1 have the nodes 'Wing' and 'WingWell'; LOD2 has neither: it is fixed stowed).
    The model is built STOWED: node 'Wing' is a copy of the shell's deck faces that coincides with them (node origin = pivot, GLB frame: +Y up, +X aft, rotation about +Z).
    Runtime: while deploy = 0 hide 'Wing' and 'WingWell'; as soon as deploy > 0 show both (the well is fully present at once).  Deployed pose = as built +
    deploy: position += (dx, dy, 0) * e, rotation.z += rotZ * e (positive = trailing edge up), e = eased deploy; the child 'WingPlates' (tips, endplates, struts) is
    scaled from plates.stow (scaleZ = lateral: the tips slide out of the panel; scaleY = vertical: the endplates and struts drop) up to 1.
    'stow' = what the older shot tools read (they treat the as-built pose as deployed and sink it): they need updating to the deploy / well scheme, see the report."""
    return dict(
        decals={'plate': dict(uv=list(PLATE['uv']), x=[], y=list(PLATE['y']), z=list(PLATE['z']), side=0)},
        wing=dict(node='Wing', well='WingWell', pivot=[WING_P.x, WING_P.z, -WING_P.y], aoaDeg=0.0,
                  deploy=dict(dx=(W17_DEP if REAR_T17 else WING_DEP)['dx'], dy=(W17_DEP if REAR_T17 else WING_DEP)['dy'], rotZ=(W17_DEP if REAR_T17 else WING_DEP)['rot']),
                  stow=dict(WING_STOW_LEGACY),
                  plates=dict(node='WingPlates', stow=dict(scaleX=1.0, scaleY=0.02, scaleZ=1.0 if REAR_T17 else 0.42))),     # (step 3: only struts and linkage, they drop in; nothing slides out)
    )
