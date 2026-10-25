"""
NEON LOOP: game-ready export of the v2 wedge EV.

  /Applications/Blender.app/Contents/MacOS/Blender -b --python tools/blender/build_game_car.py -- \
      [--src ../wedge_car/wedge_car.blend] [--out public/assets/car] [--only hi|lod1|lod2|all]

The source .blend / build_car.py are READ ONLY: this script opens the .blend, never saves it, and exports
derived GLBs.  The exterior design is untouched.  What is added / changed for the game:

  * interior (seats, dash, screens, steering wheel, console, door cards, floor) under the bronze glass;
  * lamps split into HeadLens (new slim projector strip in the black nose face), HeadDRL (the designed LED
    blade), TailLamp / BrakeLamp / ReverseLamp (the Roadster light band, see below), SideMarker (designed);
  * wheels rebuilt as  Wheel_xx (hub pivot: steer + suspension)  ->  Spin_xx (spin) -> Tyre_xx, Rim_xx
    and  Brake_xx (disc + caliper, static) ; left wheels are real mirrored geometry (no negative scale);
  * Rim_xx / Wheel_xx use vertex colours:  rgb = base colour, a = material code
        0.00 rubber  0.15 gloss black  0.42 body colour (aero panels)  0.55 silver  0.80 chrome  1.00 accent (copper)
  * decal patches projected onto the doors and the hood (UVs into a 2048x1024 livery atlas);
  * panel-line tubes simplified; a merged material set (Paint, Glass, Trim, PanelGap, ...);
  * LODs: car_hi.glb (everything), car_lod1.glb (<= 60k tris, <= 20 draw calls), car_lod2.glb (<= 15k tris, <= 10).

Game-version changes toward the Roadster 2026 press photos (the source .blend still holds the original design):
  * the thick black side band is painted in body colour; the black lives in a thin carbon side skirt;
  * the tail rebuilt after the official rear shots: body-colour lip over a gloss-black light band with one continuous
    red bar, body-colour panel with an aluminium plate, black below with a carbon diffuser box (four gold cold-gas
    thruster nozzles + five ports in a recessed plate, four fan bays, strakes, endplates, ramp floor), a black wing
    well behind the glass and the active wing deployed on two struts (node 'Wing', pitches as an airbrake in game);
  * new materials Carbon (procedural twill in game), GlossBlack (light band, wing well), Nozzle (vertex colours);
  * the tail narrows into a boat tail in plan and its lower edge is tucked in over the diffuser;
  * the front splitter is half as thick;
  * wheels rebuilt after the reference close-ups: six spoke frames (gunmetal blades, diamond-cut chamfers, copper
    inner walls) between satin-silver aero panels on a concave face, centre cap with a plain badge, and an open
    brake (disc + caliper) behind them.

GLB frame (same as wedge_car.glb): -X forward, +Z left, +Y up, metres; wheel hubs at x = -1.487 / 1.61.
"""
import bpy, bmesh, math, os, sys, json, random, types
from mathutils import Vector, Matrix, Euler
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
RAW ='--raw' in argv          # uncompressed variants (*.raw.glb) for hosts that block WebAssembly (meshopt decoder)


def arg(name, default):
    return argv[argv.index(name) + 1] if name in argv else default


FRONT_R2 = '--no-front' not in argv    # R2 front end (regions/front.py parts + intake pocket, side markers): ON by default since the region phase (2026-10-19); --no-front = the P0 baseline; --front is accepted and ignored
sys.path.insert(0, HERE)
import common                           # tools/blender/common.py: shared helpers + constants (also what the locked shell2.py reaches through the shell.py shim)
from common import pchip, pchip_s, smooth, smoother, W_DARK
from regions import ctx as ctxmod       # tools/blender/regions/: the FRONT / SIDE / REAR modules and their interface (REGIONS.md)
LIVE = ctxmod.parse_live(arg('--live', 'all'))      # regions taken from regions/<r>.py; the others come from regions/_base/<r>.py (the snapshot at the last integration)
REG = ctxmod.load_regions(LIVE)
import shell2 as shell2mod              # tools/blender/shell2.py: R1c panel shell (fair splines -> per-panel surfaces, fillets, panel registry + lock file)
if '--check-lock' in argv:      # only recompute the per-panel checksums and compare them with shell_lock.json, then stop
    _rep = shell2mod.check_lock(unlock=[u for u in arg('--unlock', '').split(',') if u])
    for _n, _r in _rep.items():
        print('SHELL2 panel %-14s %s sha %s  verts %6d faces %6d%s' % (_n, 'LOCKED ' if _r['locked'] else 'free   ', _r['sha'], _r['verts'], _r['faces'], '   CHANGED vs lock' if _r['changed'] else ''))
    print('SHELL2 lock check passed (%d locked panels)' % sum(1 for r in _rep.values() if r['locked']))
    sys.exit(0)
if '--write-lock' in argv:      # (coordinator accepts panels -> lock them): --write-lock a,b,c  or  --write-lock all
    _names = list(shell2mod.PANELS) if arg('--write-lock', 'all') == 'all' else arg('--write-lock', '').split(',')
    shell2mod.write_lock(_names)
    print('SHELL2 lock written for', _names)
    sys.exit(0)


SRC = os.path.abspath(arg('--src', os.path.join(ROOT, '..', 'wedge_car', 'wedge_car.blend')))
OUT = os.path.abspath(arg('--out', os.path.join(ROOT, 'public', 'assets', 'car')))
ONLY = arg('--only', 'all')
if LIVE != set(ctxmod.REGIONS) and '--out' not in argv:
    raise SystemExit('--live %s builds a mixed car: give --out <scratch dir> (public/assets/car is written by the coordinator\'s --live all build only)' % ','.join(sorted(LIVE)))
os.makedirs(OUT, exist_ok=True)

bpy.ops.wm.open_mainfile(filepath=SRC)           # read only: we never save over it
scene = bpy.context.scene
# keep the source objects / materials under a prefix so the exported nodes get clean names
SRCOB = {ob.name: ob for ob in bpy.data.objects}
for _ob in SRCOB.values():
    _ob.name = 'src_' + _ob.name
for _m in list(bpy.data.materials):
    _m.name = 'src_' + _m.name
for _me in list(bpy.data.meshes):
    _me.name = 'src_' + _me.name
WHEEL_X = (-1.487, 1.61)
WHEEL_Y = 0.885
WHEEL_Z = 0.39
TYRE_R = 0.39


def depsgraph():
    return bpy.context.evaluated_depsgraph_get()


# ------------------------------------------------------------------ materials
def mat(name, base, metallic=0.0, rough=0.5, emis=None, estr=0.0, coat=0.0, alpha=1.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes.get('Principled BSDF')
    b.inputs['Base Color'].default_value = (*base, 1.0)
    b.inputs['Metallic'].default_value = metallic
    b.inputs['Roughness'].default_value = rough
    if coat:
        b.inputs['Coat Weight'].default_value = coat
    if emis:
        b.inputs['Emission Color'].default_value = (*emis, 1.0)
        b.inputs['Emission Strength'].default_value = estr
    if alpha < 1:
        b.inputs['Alpha'].default_value = alpha
    m.diffuse_color = (*base, 1.0)
    return m


M = {
    'Paint':       mat('Paint', (0.70, 0.71, 0.73), 0.88, 0.30, coat=0.4),
    'Glass':       mat('Glass', (0.12, 0.068, 0.032), 0.0, 0.07, alpha=0.5),
    'Trim':        mat('Trim', (0.010, 0.010, 0.011), 0.0, 0.5),
    'PanelGap':    mat('PanelGap', (0.006, 0.006, 0.007), 0.0, 1.0),          # near-black matte: seams on glass must not read grey (SPEC 8)
    'PanelGapDark': mat('PanelGapDark', (0.0, 0.0, 0.0), 0.0, 1.0),   # q8 front: hi-only, intake insides (no light at all); game: materials.js PanelGapDark
    'HeadLens':    mat('HeadLens', (0.003, 0.0035, 0.0045), 0.0, 0.1),   # FRONT r2: near-black (the game's 0x0b0c0f) and NEVER lit: the night headlight output is all on the light bar (HeadDRL), a second glowing line is wrong (DF-3)
    'HeadDRL':     mat('HeadDRL', (0.92, 0.93, 0.95), 0.0, 0.1, emis=(1, 1, 1), estr=40.0),
    'TailLamp':    mat('TailLamp', (0.45, 0.02, 0.02), 0.0, 0.2, emis=(1.0, 0.04, 0.03), estr=6.0),
    'BrakeLamp':   mat('BrakeLamp', (0.35, 0.01, 0.01), 0.0, 0.15, emis=(1.0, 0.03, 0.02), estr=25.0),
    'ReverseLamp': mat('ReverseLamp', (0.9, 0.92, 0.95), 0.0, 0.15, emis=(1, 1, 1), estr=10.0),
    'SideMarker':  mat('SideMarker', (0.5, 0.06, 0.02), 0.0, 0.25, emis=(1.0, 0.18, 0.05), estr=1.5),
    'Tyre':        mat('Tyre', (0.0045, 0.0045, 0.005), 0.0, 0.58),         # FRONT r3: the photo's rubber is black with a faint satin sheen (p018 sidewall 5-13 / 255; it rendered ~41 with the old 0.018 / 0.72)
    'Rim':         mat('Rim', (1.0, 1.0, 1.0), 0.35, 0.30),
    'BrakeDisc':   mat('BrakeDisc', (0.30, 0.30, 0.32), 0.9, 0.45),
    'Caliper':     mat('Caliper', (0.55, 0.05, 0.02), 0.0, 0.35),
    'Reflector':   mat('Reflector', (0.195, 0.0044, 0.0024), 0.0, 0.22),     # side / rear red reflectors: fixed dark red, not lit, not livery-tinted (Caliper follows livery.rim.accent); = the game's 0x7a0e08 / 0.22 (src/car/materials.js; it was 0.30 linear, half again as bright: p016's front block read 0.45 of the paint, the photo 0.20)
    'IntLeather':  mat('IntLeather', (0.020, 0.020, 0.024), 0.0, 0.5),
    'IntPlastic':  mat('IntPlastic', (0.012, 0.012, 0.014), 0.0, 0.62),
    'IntScreen':   mat('IntScreen', (0.01, 0.02, 0.03), 0.0, 0.2, emis=(0.1, 0.5, 0.8), estr=1.0),
    'IntAccent':   mat('IntAccent', (0.86, 0.50, 0.26), 1.0, 0.3),
    'Decal':       mat('Decal', (1, 1, 1), 0.0, 0.5),
    'Carbon':      mat('Carbon', (0.02, 0.02, 0.022), 0.3, 0.35, coat=0.6),
    'GlossBlack':  mat('GlossBlack', (0.004, 0.004, 0.005), 0.0, 0.1, coat=1.0),
    'Nozzle':      mat('Nozzle', (1, 1, 1), 1.0, 0.26),
}
OLD2NEW = {'src_Paint_LiquidSilver': 'Paint', 'src_Glass_BronzeTint': 'Glass', 'src_Trim_SatinBlack': 'Trim', 'src_WheelWell': 'Trim',
           'src_DarkMetal': 'Trim', 'src_PanelGap': 'PanelGap', 'src_Headlamp_LED': 'HeadDRL', 'src_TailLamp_Red': 'TailLamp',
           'src_SideMarker_Amber': 'SideMarker', 'src_Tyre': 'Tyre'}


# --------------------------------------------------------------------- helpers
def link(ob):
    scene.collection.objects.link(ob)
    return ob


def bake(ob, name=None, world=True):
    """Evaluated copy of an object as a plain mesh object (modifiers / curves applied), optionally in world space."""
    d = depsgraph()
    ev = ob.evaluated_get(d)
    me = bpy.data.meshes.new_from_object(ev, preserve_all_data_layers=True, depsgraph=d)
    nob = bpy.data.objects.new(name or ob.name, me)
    link(nob)
    if world:
        me.transform(ob.matrix_world)
    else:
        nob.matrix_world = ob.matrix_world.copy()
    return nob


def remap_mats(ob):
    for slot in ob.material_slots:
        if slot.material is not None:
            slot.material = M[OLD2NEW.get(slot.material.name, slot.material.name.removeprefix('src_'))]


def set_mat(ob, name):
    ob.data.materials.clear()
    ob.data.materials.append(M[name])


def tri_count(obs):
    n = 0
    d = depsgraph()
    for o in obs:
        if o.type != 'MESH':
            continue
        ev = o.evaluated_get(d)
        me = ev.to_mesh()
        me.calc_loop_triangles()
        n += len(me.loop_triangles)
        ev.to_mesh_clear()
    return n


def obj_from_bm(bm, name, mat_name, smooth=True, sharp_deg=None, parent=None, loc=None):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    me.materials.append(M[mat_name])
    link(ob)
    for p in me.polygons:
        p.use_smooth = smooth
    if smooth and sharp_deg is not None:
        mark_sharp(me, sharp_deg)
    if parent is not None:
        ob.parent = parent
    if loc is not None:
        ob.location = loc
    return ob


def mark_sharp(me, deg):
    bm = bmesh.new()
    bm.from_mesh(me)
    ang = math.radians(deg)
    for e in bm.edges:
        if len(e.link_faces) == 2:
            e.smooth = e.calc_face_angle(0.0) < ang
        else:
            e.smooth = True
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True


def set_color(ob, rgb, a, name='Color'):
    me = ob.data
    if name in me.color_attributes:
        me.color_attributes.remove(me.color_attributes[name])
    ca = me.color_attributes.new(name, 'FLOAT_COLOR', 'POINT')
    for i in range(len(me.vertices)):
        ca.data[i].color = (rgb[0], rgb[1], rgb[2], a)
    me.color_attributes.active_color = ca
    me.attributes.active_color = ca


def join(objs, name):
    objs = [o for o in objs if o is not None]
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    res = bpy.context.view_layer.objects.active
    res.name = name
    res.data.name = name
    return res


def delete(obs):
    for o in obs:
        if o is None:
            continue
        me = o.data if o.type == 'MESH' else None
        bpy.data.objects.remove(o, do_unlink=True)
        if me is not None and me.users == 0:
            bpy.data.meshes.remove(me)


def duplicate(ob, name=None):
    n = ob.copy()
    n.data = ob.data.copy()
    if name:
        n.name = name
    link(n)
    return n


def empty(name, loc=(0, 0, 0), parent=None):
    e = bpy.data.objects.new(name, None)
    e.empty_display_size = 0.1
    link(e)
    e.location = loc
    if parent is not None:
        e.parent = parent
    return e


def dp_simplify(pts, tol):
    """Douglas-Peucker on a 3D polyline."""
    if len(pts) < 3:
        return pts
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        a, b = stack.pop()
        A, B = Vector(pts[a]), Vector(pts[b])
        ab = B - A
        L2 = ab.length_squared
        dmax, idx = 0.0, -1
        for i in range(a + 1, b):
            P = Vector(pts[i])
            t = 0.0 if L2 < 1e-12 else max(0.0, min(1.0, (P - A).dot(ab) / L2))
            d = (P - (A + ab * t)).length
            if d > dmax:
                dmax, idx = d, i
        if dmax > tol and idx >= 0:
            keep[idx] = True
            stack.append((a, idx))
            stack.append((idx, b))
    return [p for p, k in zip(pts, keep) if k]


def simplify_curve(ob, tol, bevel_res=1, depth_scale=1.0):
    cu = ob.data
    lines = []
    for s in cu.splines:
        lines.append(([tuple(p.co[:3]) for p in s.points], s.use_cyclic_u))
    cu.splines.clear()
    for pts, cyc in lines:
        pts = dp_simplify(pts + ([pts[0]] if cyc else []), tol)
        if cyc:
            pts = pts[:-1]
        sp = cu.splines.new('POLY')
        sp.points.add(len(pts) - 1)
        for i, p in enumerate(pts):
            sp.points[i].co = (p[0], p[1], p[2], 1.0)
        sp.use_cyclic_u = cyc
    cu.bevel_resolution = bevel_res
    cu.resolution_u = 1
    cu.bevel_depth *= depth_scale


# ---------------------------------------------------------- rounded-box parts
class Builder:
    """Accumulates small rounded boxes / shapes per material into one bmesh each."""

    def __init__(self):
        self.bms = {}

    def bm(self, matname):
        if matname not in self.bms:
            self.bms[matname] = bmesh.new()
        return self.bms[matname]

    def rbox(self, mat_name, c, size, rot=(0, 0, 0), bev=0.012, seg=2, taper=None, bulge=0.0):
        """c: centre, size: (x, y, z) m, rot: degrees XYZ euler; taper: scale of y at the +z end (1 = none);
        bulge: pushes the +x... face outward (pillow)."""
        b = bmesh.new()
        bmesh.ops.create_cube(b, size=1.0)
        for v in b.verts:
            v.co.x *= size[0]
            v.co.y *= size[1]
            v.co.z *= size[2]
        if taper is not None:
            for v in b.verts:
                t = v.co.z / size[2] + 0.5
                v.co.y *= 1.0 + (taper - 1.0) * t
        if bev > 0:
            bmesh.ops.bevel(b, geom=b.verts[:] + b.edges[:], offset=bev, segments=seg, profile=0.6,
                            affect='EDGES', clamp_overlap=True)
        if bulge:
            for v in b.verts:
                k = 1.0 - (2 * v.co.y / size[1]) ** 2
                k2 = 1.0 - (2 * v.co.z / size[2]) ** 2
                v.co.x += bulge * max(k, 0) * max(k2, 0) * (1 if v.co.x > 0 else -1) * 0.5
        R = Euler([math.radians(a) for a in rot], 'XYZ').to_matrix().to_4x4()
        bmesh.ops.transform(b, matrix=Matrix.Translation(c) @ R, verts=b.verts)
        me = bpy.data.meshes.new('tmp')
        b.to_mesh(me)
        b.free()
        self.bm(mat_name).from_mesh(me)
        bpy.data.meshes.remove(me)

    def tube(self, mat_name, pts, r, sides=6):
        bm = self.bm(mat_name)
        rings = []
        n = len(pts)
        for i, p in enumerate(pts):
            p = Vector(p)
            t = (Vector(pts[min(i + 1, n - 1)]) - Vector(pts[max(i - 1, 0)])).normalized()
            up = Vector((0, 0, 1)) if abs(t.z) < 0.9 else Vector((1, 0, 0))
            a = t.cross(up).normalized()
            b2 = t.cross(a).normalized()
            rings.append([bm.verts.new(p + (a * math.cos(2 * math.pi * k / sides) + b2 * math.sin(2 * math.pi * k / sides)) * r)
                          for k in range(sides)])
        for i in range(n - 1):
            for k in range(sides):
                bm.faces.new((rings[i][k], rings[i][(k + 1) % sides], rings[i + 1][(k + 1) % sides], rings[i + 1][k]))

    def plane(self, mat_name, c, size, rot=(0, 0, 0), uv=True):
        """A quad in the local YZ plane (normal +X) with 0..1 UVs (u along +y, v up)."""
        bm = self.bm(mat_name)
        lay = bm.loops.layers.uv.verify()
        R = Euler([math.radians(a) for a in rot], 'XYZ').to_matrix().to_4x4()
        T = Matrix.Translation(c) @ R
        corners = [(-0.5, -0.5), (0.5, -0.5), (0.5, 0.5), (-0.5, 0.5)]
        vs = [bm.verts.new(T @ Vector((0, cy * size[0], cz * size[1]))) for cy, cz in corners]
        f = bm.faces.new(vs)
        nrm = (T.to_3x3() @ Vector((1, 0, 0)))
        if f.normal.dot(nrm) < 0:
            f.normal_flip()
        for l in f.loops:       # UVs by corner position (stable regardless of winding)
            p = T.inverted() @ l.vert.co
            l[lay].uv = (p.y / size[0] + 0.5, p.z / size[1] + 0.5)
        return f

    def torus(self, mat_name, c, rot, R, r, major=36, minor=10, scale=(1.0, 1.0)):
        bm = self.bm(mat_name)
        Rm = Euler([math.radians(a) for a in rot], 'XYZ').to_matrix().to_4x4()
        T = Matrix.Translation(c) @ Rm
        rings = []
        for i in range(major):
            a = 2 * math.pi * i / major
            ring = []
            for j in range(minor):
                bq = 2 * math.pi * j / minor
                rr = R + r * math.cos(bq)
                p = Vector((rr * math.cos(a) * scale[0], rr * math.sin(a) * scale[1], r * math.sin(bq)))
                ring.append(bm.verts.new(T @ p))
            rings.append(ring)
        for i in range(major):
            for j in range(minor):
                bm.faces.new((rings[i][j], rings[(i + 1) % major][j], rings[(i + 1) % major][(j + 1) % minor], rings[i][(j + 1) % minor]))

    def cylinder(self, mat_name, c, rot, r, h, seg=20):
        b = bmesh.new()
        bmesh.ops.create_cone(b, cap_ends=True, segments=seg, radius1=r, radius2=r, depth=h)
        R = Euler([math.radians(a) for a in rot], 'XYZ').to_matrix().to_4x4()
        bmesh.ops.transform(b, matrix=Matrix.Translation(c) @ R, verts=b.verts)
        me = bpy.data.meshes.new('tmp')
        b.to_mesh(me)
        b.free()
        self.bm(mat_name).from_mesh(me)
        bpy.data.meshes.remove(me)

    def objects(self, prefix, sharp=50, smooth=True):
        out = []
        for m, bm in self.bms.items():
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
            out.append(obj_from_bm(bm, f'{prefix}_{m}', m, smooth=smooth, sharp_deg=sharp))
        self.bms = {}
        return out


# -------------------------------------------------------------------- interior
DRV = -0.40          # driver side (left, -Y); passenger +0.40


def build_interior(level):
    """level 0: full detail (hi);  level 1: simplified (lod1)."""
    b = Builder()
    L, P, A, S = 'IntLeather', 'IntPlastic', 'IntAccent', 'IntScreen'
    seg = 3 if level == 0 else 1
    bv = lambda x: x if level == 0 else x * 1.4

    # floor, tunnel, rear bulkhead, parcel shelf
    b.rbox(P, (0.20, 0, 0.255), (3.45, 1.80, 0.04), bev=0.01, seg=1)
    b.rbox(P, (-0.40, 0, 0.40), (1.55, 0.30, 0.30), bev=bv(0.03), seg=seg)                    # front tunnel / console body
    b.rbox(P, (1.17, 0, 0.38), (0.62, 0.26, 0.26), bev=bv(0.03), seg=seg)                     # rear console
    b.rbox(P, (2.02, 0, 0.93), (0.50, 1.56, 0.03), bev=0.01, seg=1)                           # parcel shelf
    b.rbox(P, (1.80, 0, 0.60), (0.04, 1.62, 0.62), bev=0.01, seg=1)                           # rear bulkhead
    b.rbox(P, (-1.50, 0, 0.50), (0.06, 1.30, 0.44), bev=0.01, seg=1)                          # firewall

    # dash: slab with raised driver binnacle
    b.rbox(P, (-1.16, 0, 0.64), (0.80, 1.80, 0.28), rot=(0, 5, 0), bev=bv(0.035), seg=seg)
    b.rbox(P, (-1.02, 0, 0.76), (0.34, 1.72, 0.05), rot=(0, 8, 0), bev=bv(0.015), seg=seg)    # dash top pad
    b.rbox(P, (-0.92, DRV, 0.80), (0.18, 0.56, 0.11), rot=(0, 8, 0), bev=bv(0.03), seg=seg)   # binnacle hood
    b.rbox(A, (-0.835, 0.0, 0.69), (0.012, 1.55, 0.012), bev=0, seg=1)                          # copper dash line
    for sgn in (-1, 1):                                                                      # side vents
        b.rbox(P, (-0.81, sgn * 0.78, 0.66), (0.025, 0.16, 0.05), bev=0.005, seg=1)
    b.rbox(P, (-0.82, 0.0, 0.88), (0.05, 0.46, 0.20), rot=(0, -12, 0), bev=bv(0.012), seg=max(1, seg - 1))   # screen bezel
    b.plane(S, (-0.795, 0.0, 0.885), (0.42, 0.17), rot=(0, -18, 0))                           # centre screen (u = +y)
    b.plane(S, (-0.835, DRV, 0.835), (0.27, 0.095), rot=(0, -22, 0))                          # cluster screen

    # seats
    def seat(y, x0, z0, headrest=True, big=True, lean=14, front=True, back=True):
        w = 0.50 if big else 0.46
        b.rbox(L, (x0, y, z0), (0.54, w, 0.13), rot=(0, -4, 0), bev=bv(0.035), seg=seg)                   # cushion
        for sy in (-1, 1):
            b.rbox(L, (x0 + 0.02, y + sy * (w / 2 - 0.035), z0 + 0.065), (0.50, 0.075, 0.09), rot=(0, -4, 0), bev=bv(0.03), seg=seg)  # cushion bolsters
        if not back:      # (rear seats: cushion only -- the backs and headrests stood up into / through the lowered rear glass)
            return
        bx, bz = x0 + 0.34, z0 + 0.38
        b.rbox(L, (bx, y, bz), (0.12, w, 0.70 if big else 0.62), rot=(0, lean, 0), taper=0.9, bev=bv(0.04), seg=seg)  # back
        for sy in (-1, 1):
            b.rbox(L, (bx - 0.03, y + sy * (w / 2 - 0.03), bz - 0.04), (0.14, 0.09, 0.50), rot=(0, lean, 0), bev=bv(0.035), seg=seg)  # back bolsters
        b.rbox(A, (bx - 0.07, y, bz - 0.03), (0.006, 0.035, 0.46), rot=(0, lean, 0), bev=0, seg=1)           # centre accent
        if headrest:
            hz = bz + (0.40 if big else 0.34)
            b.rbox(L, (bx + 0.07 * math.sin(math.radians(lean)) * 2, y, hz), (0.11, 0.27, 0.19), rot=(0, lean, 0), bev=bv(0.04), seg=seg)

    seat(DRV, -0.45, 0.43)
    seat(-DRV, -0.45, 0.43)
    seat(-0.40, 1.04, 0.40, big=False, lean=16, back=False)
    seat(0.40, 1.04, 0.40, big=False, lean=16, back=False)

    # armrest pads
    b.rbox(L, (-0.05, 0, 0.575), (0.46, 0.21, 0.05), bev=bv(0.02), seg=seg)
    b.rbox(L, (1.13, 0, 0.52), (0.30, 0.2, 0.05), bev=bv(0.02), seg=seg)
    b.rbox(A, (-0.40, 0, 0.555), (1.10, 0.012, 0.01), bev=0, seg=1)                            # console accent line

    # door cards (both sides) + armrest + accent + pull
    for sgn in (-1, 1):
        b.rbox(P, (-0.05, sgn * 0.915, 0.60), (2.30, 0.07, 0.62), rot=(sgn * 7, 0, 0), bev=bv(0.03), seg=seg)
        b.rbox(L, (-0.05, sgn * 0.865, 0.74), (1.80, 0.09, 0.07), bev=bv(0.03), seg=seg)         # door armrest
        b.rbox(A, (-0.05, sgn * 0.822, 0.835), (1.90, 0.006, 0.012), bev=0, seg=1)               # door accent line
        b.rbox(P, (0.20, sgn * 0.84, 0.62), (0.26, 0.04, 0.05), bev=bv(0.015), seg=seg)           # pull handle
        b.rbox(P, (-1.30, sgn * 0.85, 0.55), (0.04, 0.10, 0.45), rot=(0, 0, sgn * 10), bev=0.01, seg=1)   # kick panel
        b.rbox(P, (1.00, sgn * 0.93, 0.62), (0.36, 0.07, 0.58), rot=(sgn * 8, 0, 0), bev=bv(0.03), seg=seg)  # rear side trim (ends at x 1.18, in front of the rear arch at 1.195: it used to reach x 1.62 and show through the rear wheel)
    objs = b.objects('Int', sharp=48 if level == 0 else 60)
    # steering wheel is separate (rotates): built by build_steering()
    return objs


def build_steering():
    """Steering wheel: origin at the wheel centre, local +Z = column axis towards the driver."""
    centre = Vector((-0.98, DRV, 0.795))
    tilt = 65.0       # degrees about Y: local Z -> (sin65, 0, cos65) = rearwards and up
    b = Builder()
    b.torus('IntLeather', (0, 0, 0), (0, 0, 0), 0.172, 0.0185, major=40, minor=10, scale=(1.0, 0.86))
    for ang in (0, 120, 240):         # three spokes
        a = math.radians(ang + 90)
        b.rbox('IntPlastic', (0.075 * math.cos(a), 0.075 * math.sin(a) * 0.86, 0), (0.15, 0.028, 0.012), rot=(0, 0, ang + 90), bev=0.004, seg=1)
    b.cylinder('IntPlastic', (0, 0, 0.005), (0, 0, 0), 0.052, 0.034, seg=24)
    b.cylinder('IntAccent', (0, 0, 0.024), (0, 0, 0), 0.026, 0.006, seg=20)
    b.rbox('IntAccent', (0, 0.155, 0.0), (0.012, 0.012, 0.03), bev=0, seg=1)                    # 12 o'clock marker
    parts = b.objects('Steer', sharp=40)
    parts = [o for o in parts]
    st = join(parts, 'Steering') if len(parts) > 1 else parts[0]
    st.name = 'Steering'
    st.rotation_euler = Euler((0, math.radians(tilt), 0), 'XYZ')
    st.location = centre
    st.data.name = 'Steering'
    return st


# ------------------------------------------------------------------ main body
body = SRCOB['Body']
surf_level = body.modifiers['Subdivision'].levels

# ---- lamps / panel lines: simplify the curves before baking
for n in ('PanelLines_Side', 'PanelLines_Top'):
    simplify_curve(SRCOB[n], tol=0.00035, bevel_res=1)
simplify_curve(SRCOB['DoorHandleGap'], tol=0.0002, bevel_res=1)
simplify_curve(SRCOB['HeadLamp_LED'], tol=0.0003, bevel_res=2)


# ---- game-version body changes (see the header): thin splitter
_spl =SRCOB['FrontSplitter']
_mi = _spl.matrix_world.inverted()
for _v in _spl.data.vertices:
    _w = _spl.matrix_world @ _v.co
    if _w.z < 0.24:
        _w.z = 0.243
        _v.co = _mi @ _w
_spl.data.update()


class Surf:
    def __init__(self, ob):
        self.bvh = BVHTree.FromObject(ob, depsgraph())

    def cast(self, origin, d, off=0.0, maxd=6.0):
        d = Vector(d).normalized()
        hit, nrm, _, _ = self.bvh.ray_cast(Vector(origin), d, maxd)
        if hit is None:
            return None, None
        if nrm.dot(d) > 0:
            nrm = -nrm
        return hit + nrm * off, nrm


# R1c panel shell (tools/blender/shell2.py): fair spline curves -> one named generator per panel, shared edges, fillets on the creases.  Fails loudly when a LOCKED
# panel (shell_lock.json) changed and was not unlocked for this round (--unlock a,b).
body_hi, _info = shell2mod.build_shell2(bevel='--no-fillet' not in argv, check=True, unlock=[u for u in arg('--unlock', '').split(',') if u])
for _n, _r in _info['report'].items():
    print('SHELL2 panel %-14s %s %s verts %6d faces %6d' % (_n, 'LOCKED ' if _r['locked'] else 'free   ', _r['sha'], _r['verts'], _r['faces']))
print('SHELL2 assembled: open edges %d (the unfinished bottom loops), non-manifold %d, bad winding %d, fillet edges %d' % (_info['open_edges'], _info['nonmanifold'], _info['bad_winding'], _info['beveled']))
body_hi.name = body_hi.data.name = 'Body_hi'
for _m in ('Paint', 'Glass', 'Trim'):
    body_hi.data.materials.append(M[_m])


# the region context (regions/ctx.py): the tools and the surfaces are filled in below, once the functions exist
CTX = ctxmod.Ctx(argv=argv, oldbody=False, front_r2=FRONT_R2, body=body_hi, HUBS=common.HUBS, HUB_Z=common.HUB_Z, R_ARCH=common.R_ARCH, R_TYRE=TYRE_R,
                 WHEEL_Y=WHEEL_Y)       # (oldbody stays on the ctx as False: the region modules still read ctx.oldbody)
# REAR cuts the black / paint outline of the tail (lobe bell + cheek line, see bound_z) into the dense mesh, THEN the arches; FRONT (intake pocket, --front)
# and SIDE follow the arch cut; the floor closes the shell
ctxmod.call(REG, CTX, 'rear', 'shell_post')
if not os.environ.get('NO_ARCH'):        # (debug switch)
    shell2mod.cut_arches(body_hi)
ctxmod.call(REG, CTX, 'front', 'shell_post')
ctxmod.call(REG, CTX, 'side', 'shell_post')
shell2mod.add_floor(body_hi)
mark_sharp(body_hi.data, 30)
bt_E = shell2mod.glass_half_width            # glass half width (replaces the old table lookup; used by glass_cover)
body_dense = duplicate(body_hi, 'Body_dense')     # kept for the LOD bodies (decimated copies)
SURF = Surf(body_hi)


def fit_interior(objs, clr=0.02):
    """new shell: no interior part may cross the glass or the paint.  Every vertex is kept `clr` inside the canopy (ray up to the roof, or
    down onto it when the vertex is above it) and, in the cabin (z > 0.55), inside the side walls (ray outwards / inwards)."""
    moved = 0
    for ob in objs:
        for v in ob.data.vertices:
            x, y, z = v.co
            if z < 0.5:
                continue
            m = False
            p, _ = SURF.cast((x, y, z), (0, 0, 1), 0.0, 4.0)
            if p is not None:
                if p.z - z < clr:
                    v.co.z = p.z - clr
                    m = True
            else:
                p, _ = SURF.cast((x, y, 3.0), (0, 0, -1), 0.0, 4.0)
                if p is not None and z > p.z - clr:
                    v.co.z = p.z - clr
                    m = True
            if z > 0.55 and abs(y) > 0.3:
                sg = 1.0 if y > 0 else -1.0
                q, _ = SURF.cast((x, y, v.co.z), (0, sg, 0), 0.0, 3.0)
                if q is not None:
                    d = abs(q.y - y)
                    if d < clr:
                        v.co.y = q.y - sg * clr
                        m = True
                else:
                    q, _ = SURF.cast((x, sg * 2.5, v.co.z), (0, -sg, 0), 0.0, 3.0)
                    if q is not None and abs(y) > abs(q.y) - clr:
                        v.co.y = q.y - sg * clr
                        m = True
            moved += m
        ob.data.update()
    print('interior vertices pulled inside the canopy / walls:', moved)


def patch(name, mat_name, ranges, origin_fn, direction, off, nu, nv, uv_rect=None, uflip=False, unit_uv=False,
          atlas=(2048, 1024), keep=None, ray_fn=None, a_fn=None, surf=None):
    """Grid projected onto the body along `direction` (conforms to the surface, offset along its normal).
    ranges=((a0,a1),(b0,b1)); origin_fn(a,b) -> ray start.  uv_rect: canvas-pixel cell in the atlas (row 0 = top);
    unit_uv: plain 0..1 UVs (lamps); keep(p): drop hits it rejects.  Faces are oriented to the surface normal.  surf: the Surf to project onto (default: the HI body's)."""
    surf = SURF if surf is None else surf
    bm = bmesh.new()
    lay = bm.loops.layers.uv.verify()
    grid = [[None] * nv for _ in range(nu)]
    nrm = {}
    for i in range(nu):
        for j in range(nv):
            a = a_fn(i / (nu - 1)) if a_fn else ranges[0][0] + (ranges[0][1] - ranges[0][0]) * i / (nu - 1)
            bb = ranges[1][0] + (ranges[1][1] - ranges[1][0]) * j / (nv - 1)
            if ray_fn is not None:
                o_, d_ = ray_fn(a, bb)
                p, n = surf.cast(o_, d_, off)
            else:
                p, n = surf.cast(origin_fn(a, bb), direction, off)
            if p is not None and (keep is None or keep(p)):
                v = bm.verts.new(p)
                grid[i][j] = v
                nrm[v] = n
    for i in range(nu - 1):
        for j in range(nv - 1):
            idx = [(i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1)]
            vs = [grid[ii][jj] for ii, jj in idx]
            if any(v is None for v in vs):
                continue
            f = bm.faces.new(vs)
            nn = sum((nrm[v] for v in vs), Vector((0, 0, 0)))
            if f.normal.dot(nn) < 0:
                f.normal_flip()
            for l in f.loops:
                ii, jj = next((ii, jj) for ii, jj in idx if grid[ii][jj] is l.vert)
                u_t = ii / (nu - 1)
                if uflip:
                    u_t = 1.0 - u_t
                v_t = jj / (nv - 1)
                if uv_rect is not None:
                    x0, y0, w, h = uv_rect
                    px = x0 + w * u_t
                    py = y0 + h * (1.0 - v_t)                      # canvas coords, row 0 at the top
                    l[lay].uv = (px / atlas[0], 1.0 - py / atlas[1])   # blender uv has v up; the exporter flips v
                elif unit_uv:
                    l[lay].uv = (u_t, v_t)
    return obj_from_bm(bm, name, mat_name, smooth=True)


# ---- lamp / decal details projected on the body
details = []                # (the front face / light bar is R2: no head lens strips are re-attached here)

# decal patches (uv rects in canvas pixels of a 2048 x 1024 atlas)
DECALS = {
    'doorL': dict(uv=(0, 0, 1024, 512), x=(-0.70, 0.22), z=(0.40, 0.86), side=-1),
    'doorR': dict(uv=(1024, 0, 1024, 512), x=(-0.70, 0.22), z=(0.40, 0.86), side=1),
    # hood: u runs left->right as seen by the driver (+y), v up = towards the nose (x decreasing)
    'hood':  dict(uv=(0, 512, 1024, 512), x=(-2.26, -1.92), y=(-0.56, 0.56), side=0),
}
decal_objs = []
for name, d in DECALS.items():
    if d['side'] != 0:
        s_ = d['side']
        # left side: the car faces left as seen from outside -> u grows with x (front -> rear) reads correctly;
        # right side: the car faces right -> reverse u.
        rng = ((d['x'][0], d['x'][1]), (d['z'][0], d['z'][1]))
        o = patch(f'Decal_{name}', 'Decal', rng, lambda a, bb, s_=s_: (a, s_ * 1.5, bb), (0, -s_, 0), 0.0014, 40, 22,
                  uv_rect=d['uv'], uflip=(s_ > 0))
    else:
        rng = ((d['y'][0], d['y'][1]), (d['x'][1], d['x'][0]))
        o = patch(f'Decal_{name}', 'Decal', rng, lambda a, bb: (bb, a, 2.0), (0, 0, -1), 0.0014, 40, 20, uv_rect=d['uv'])
    decal_objs.append(o)

# ---- bake the original objects we keep
keep_static = []      # world-space plain meshes
# lamp strip, panel lines and door handles are re-made on the new shell in R2..R5 (they were fitted to the old body)
drl, lines = None, []
others = []
NEW_HIDE = ('DoorHandle', 'FrontIntakeBar', 'WheelTub', 'SideBlade', 'SideMarker', 'FrontSplitter')   # parts fitted to the old body (new shell: re-made in R2 / R5)
for n, ob in SRCOB.items():
    if ob.type != 'MESH':
        continue
    if n.startswith(('DoorHandle', 'FrontIntakeBar', 'FrontSplitter', 'SideBlade', 'SideMarker', 'WheelTub')) \
            and not n.startswith('DoorHandleGap') and not n.startswith(NEW_HIDE):
        o = bake(ob, n)
        remap_mats(o)
        if n.startswith('FrontSplitter'):
            set_mat(o, 'Carbon')
        others.append(o)

# wheel prototypes (right side local geometry)
proto = {}
for part in ('Tyre', 'RimDisc', 'RimLip', 'Spokes', 'HubCap', 'HubBadge', 'BrakeDisc', 'CopperChevrons'):
    ob = SRCOB[f'{part}.002']       # FR wheel, local coordinates, axle = +Y, outer face +Y
    d = depsgraph()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(d), preserve_all_data_layers=True, depsgraph=d)
    proto[part] = me

ev_polys = len(body_hi.data.polygons)

report = {}


# ----------------------------------------------------------------------- wheels
def spin_profile(bm, prof, steps):
    verts = [bm.verts.new((r, y, 0.0)) for r, y in prof]
    edges = [bm.edges.new((verts[i], verts[(i + 1) % len(verts)])) for i in range(len(verts))]
    bmesh.ops.spin(bm, geom=verts + edges, cent=(0, 0, 0), axis=(0, 1, 0), angle=2 * math.pi, steps=steps, use_duplicate=False)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)


def tyre_mesh(steps, nprof):
    prof = _tyre_prof(nprof)            # (FRONT r3: the same contour as the lod / hi wheels; this function is only used by the old build_wheel_lod)
    bm = bmesh.new()
    spin_profile(bm, prof, steps)
    return bm


def mirror_mesh(me, left):
    if left:
        me.transform(Matrix.Scale(-1, 4, Vector((0, 1, 0))))
        me.flip_normals()
    return me


def part_obj(me, name, mat_name, left, rgba=None, smooth=True, sharp=None):
    me2 = me.copy()
    mirror_mesh(me2, left)
    ob = bpy.data.objects.new(name, me2)
    link(ob)
    if me2.materials:
        me2.materials.clear()
    me2.materials.append(M[mat_name])
    for p in me2.polygons:
        p.use_smooth = smooth
    if sharp is not None:
        mark_sharp(me2, sharp)
    if rgba is not None:
        set_color(ob, rgba[:3], rgba[3])
    return ob


C_RUBBER = (0.0045, 0.0045, 0.005, 0.0)
C_GLOSS = (0.006, 0.006, 0.007, 0.15)
C_SILVER = (0.78, 0.79, 0.81, 0.55)
C_CHROME = (0.92, 0.92, 0.92, 0.80)
C_ACCENT = (0.86, 0.50, 0.26, 1.0)


def caliper_bm(left):
    """C-shaped brake caliper arc + two pistons, in wheel local coordinates (axle +Y), at the upper rear of the disc."""
    bm = bmesh.new()
    r0, r1, y0, y1 = 0.115, 0.205, -0.030, 0.062
    a0, a1 = math.radians(18), math.radians(78)
    n = 8
    rings = []
    for i in range(n + 1):
        a = a0 + (a1 - a0) * i / n
        ca, sa = math.cos(a), math.sin(a)
        ring = []
        for (r, y) in ((r0, y0), (r1, y0), (r1, y1), (r0, y1)):
            ring.append(bm.verts.new((r * ca, y, r * sa)))
        rings.append(ring)
    for i in range(n):
        for k in range(4):
            bm.faces.new((rings[i][k], rings[i][(k + 1) % 4], rings[i + 1][(k + 1) % 4], rings[i + 1][k]))
    bm.faces.new(rings[0][::-1])
    bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def build_wheel_hi(tag, wx, sgn):
    left = sgn < 0
    hub = empty(f'Wheel_{tag}', (wx, sgn * WHEEL_Y, WHEEL_Z))
    spin = empty(f'Spin_{tag}', (0, 0, 0), hub)
    t = part_obj(proto['Tyre'], f'Tyre_{tag}', 'Tyre', left, smooth=True, sharp=70)
    t.parent = spin
    rim_parts = [
        part_obj(proto['RimDisc'], f'RimDisc_{tag}', 'Rim', left, C_SILVER, sharp=40),
        part_obj(proto['RimLip'], f'RimLip_{tag}', 'Rim', left, C_GLOSS, sharp=40),
        part_obj(proto['Spokes'], f'Spokes_{tag}', 'Rim', left, C_GLOSS, smooth=False),
        part_obj(proto['HubCap'], f'HubCap_{tag}', 'Rim', left, C_GLOSS, sharp=40),
        part_obj(proto['HubBadge'], f'HubBadge_{tag}', 'Rim', left, C_CHROME, sharp=40),
        part_obj(proto['CopperChevrons'], f'Chev_{tag}', 'Rim', left, C_ACCENT, sharp=40),
    ]
    rim = join(rim_parts, f'Rim_{tag}')
    rim.parent = spin
    # brake: disc (code 0) + caliper (code 1) in one mesh, static in the hub node
    disc = part_obj(proto['BrakeDisc'], f'Disc_{tag}', 'BrakeDisc', left, (0.30, 0.30, 0.32, 0.0), sharp=40)
    cal = obj_from_bm(caliper_bm(left), f'Cal_{tag}', 'Caliper', smooth=True, sharp_deg=40)
    mirror_mesh(cal.data, left)
    set_color(cal, (0.62, 0.07, 0.03), 1.0)
    brake = join([disc, cal], f'Brake_{tag}')
    brake.parent = hub
    return hub


def build_wheel_lod(tag, wx, sgn, level):
    """level 1: tyre + simplified rim in one mesh;  level 2: very low poly."""
    left = sgn < 0
    if level == 1:
        steps, nprof = 56, 22
    else:
        steps, nprof = 20, 8
    parts = []
    tb = tyre_mesh(steps, nprof)
    me = bpy.data.meshes.new('t')
    tb.to_mesh(me)
    tb.free()
    parts.append(part_obj(me, 'WT', 'Rim', left, C_RUBBER, sharp=70))
    if level == 1:
        bm = bmesh.new()
        spin_profile(bm, [(0.0, 0.065), (0.292, 0.065), (0.300, 0.075), (0.300, -0.12), (0.0, -0.12)], 40)
        me = bpy.data.meshes.new('d')
        bm.to_mesh(me)
        bm.free()
        parts.append(part_obj(me, 'WD', 'Rim', left, C_SILVER, sharp=60))
        sp = proto['Spokes']
        parts.append(part_obj(sp, 'WS', 'Rim', left, C_GLOSS, smooth=False))
        bm = bmesh.new()
        spin_profile(bm, [(0.288, 0.075), (0.312, 0.075), (0.316, 0.105), (0.300, 0.122), (0.288, 0.112)], 40)
        me = bpy.data.meshes.new('l')
        bm.to_mesh(me)
        bm.free()
        parts.append(part_obj(me, 'WL', 'Rim', left, C_GLOSS, sharp=60))
    else:
        bm = bmesh.new()
        spin_profile(bm, [(0.0, 0.070), (0.30, 0.070), (0.30, -0.1), (0.0, -0.1)], 20)
        me = bpy.data.meshes.new('d')
        bm.to_mesh(me)
        bm.free()
        parts.append(part_obj(me, 'WD', 'Rim', left, C_SILVER, sharp=60))
        sp = proto['Spokes']
        parts.append(part_obj(sp, 'WS', 'Rim', left, C_GLOSS, smooth=False))
    w = join(parts, f'WheelMesh_{tag}')
    if level == 2:
        # decimate the star (it carries 120 tris per wheel) is fine; leave
        pass
    return w


WHEELS = (('FL', WHEEL_X[0], -1), ('FR', WHEEL_X[0], 1), ('RL', WHEEL_X[1], -1), ('RR', WHEEL_X[1], 1))


def place_mesh_at_hub(ob, wx, sgn):
    """wheel local mesh -> world (hub position)."""
    ob.data.transform(Matrix.Translation((wx, sgn * WHEEL_Y, WHEEL_Z)))


# ------------------------------------------------- wheels after the reference close-ups (one mesh, corner colours)
# (W_DARK: common.W_DARK)
# vertex colour = rgb + material code in alpha (materials.js 'rim': < 0.075 rubber, 0.15 gloss black, 0.25 graphite satin, 0.42 body colour,
# 0.55 bright satin, 0.8 chrome, 1.0 livery accent).  The rgb of the body-colour and accent codes only matters in the Blender renders (the game replaces it).
W_GLS = (0.004, 0.004, 0.005, 0.15)     # gloss black: the spoke channels
W_BEV = (0.20, 0.205, 0.22, 0.25)       # graphite satin: the bevels along the panel edges (the main line of the wheel in the photo), the lip
W_HUB = (0.06, 0.06, 0.066, 0.25)       # hub star and cap: graphite satin (p003: the star reads ~60-70 / 255)
W_BADGE = (0.15, 0.15, 0.16, 0.25)
W_AERO = (0.95, 0.96, 0.98, 0.42)       # aero panels in body colour, as on the press car (white on white)
W_ACC = (0.86, 0.50, 0.26, 1.0)
W_RUB = (0.0045, 0.0045, 0.005, 0.0)    # FRONT r3: rubber black like the hi tyre's 0x0e0e0f (was 0.018 = 4x brighter, and grey in every render)
W_SS = (0.74, 0.75, 0.77, 0.8)          # 2026-10-24 (user, p003 / p018 / p001): polished stainless: the thin bright ring on the crown of the rim lip
# wheel face after the p003 / p018 close-ups: six flat aero panels in ONE plane (Y_P) between six parallel-sided gloss-black spoke channels; the bevels along
# the panel edges run straight into a graphite six-armed star hub (flat, at the foot of the bevels, Y_B) carrying the small round T cap
N_SPOKE = 6
HUB_R, FACE_R = 0.0815, 0.296           # (hub body radius of the old design) panel outer edge = foot of the lip
Y_P = 0.113                             # the panel plane
CH_A, CH_B, CH_D = 0.0285, 0.011, 0.007  # channel half width (wall to wall 5.7 cm), bevel width and drop: the panel edge lines sit at CH_A + CH_B = 3.95 cm (7.9 cm over the spoke, p003 / p018)
Y_B = Y_P - CH_D                        # foot of the bevel = top of the star hub
BEV_SS = 0.2                            # share of the bevel (from the panel edge down) that is the stainless edge line (p003: ~2.5 mm)
S_ARM = 0.105                           # the star's arms end here along each spoke
Y_FLOOR = (0.064, 0.090, 0.100)         # channel floor per level


class CB:
    """bmesh with a per-corner colour layer."""

    def __init__(self):
        self.bm = bmesh.new()
        self.col = self.bm.loops.layers.float_color.new('Color')

    def v(self, co):
        return self.bm.verts.new(co)

    def face(self, vs, rgba):
        try:
            f = self.bm.faces.new(vs)
        except ValueError:
            return None
        for lo in f.loops:
            lo[self.col] = rgba
        return f

    def lathe(self, prof, steps, cols, closed=False, axis_x=False, at=(0.0, 0.0, 0.0)):
        """surface of revolution of prof [(r, h)] about the wheel axle (+Y) or, with axis_x, about +X through `at`;
        cols: one colour for all, or one per profile segment."""
        n = len(prof)
        segs = n if closed else n - 1
        if not isinstance(cols[0], (tuple, list)):
            cols = [cols] * segs
        ox, oy, oz = at

        def P(r, h, a):
            if axis_x:
                return (ox + h, oy + r * math.cos(a), oz + r * math.sin(a))
            return (ox + r * math.cos(a), oy + h, oz + r * math.sin(a))
        axis_pts = {}
        rings = []
        for k in range(steps):
            a = 2 * math.pi * k / steps
            ring = []
            for i, (r, h) in enumerate(prof):
                if r < 1e-7:
                    if i not in axis_pts:
                        axis_pts[i] = self.v(P(0.0, h, 0.0))
                    ring.append(axis_pts[i])
                else:
                    ring.append(self.v(P(r, h, a)))
            rings.append(ring)
        for k in range(steps):
            A, B = rings[k], rings[(k + 1) % steps]
            for i in range(segs):
                j = (i + 1) % n
                vs = []
                for x in (A[i], B[i], B[j], A[j]):
                    if x not in vs:
                        vs.append(x)
                if len(vs) >= 3:
                    self.face(vs, cols[i])

    def prism(self, sections, cols, cap=None):
        """sections: point lists of equal length (an open profile swept along); cols: one per profile segment."""
        rings = [[self.v(p) for p in sec] for sec in sections]
        for a, b in zip(rings, rings[1:]):
            for i in range(len(a) - 1):
                self.face([a[i], b[i], b[i + 1], a[i + 1]], cols[i])
        if cap is not None:
            self.face(rings[0], cap)
            self.face(rings[-1], cap)

    def facen(self, vs, rgba, hint):
        """a face wound so that its normal points along `hint` (flat sheets: recalc_face_normals cannot orient an open sheet)"""
        n = Vector((0.0, 0.0, 0.0))
        for i in range(len(vs)):
            a, b = vs[i].co, vs[(i + 1) % len(vs)].co
            n += Vector(((a.y - b.y) * (a.z + b.z), (a.z - b.z) * (a.x + b.x), (a.x - b.x) * (a.y + b.y)))
        return self.face(vs if n.dot(Vector(hint)) >= 0 else vs[::-1], rgba)

    def mesh(self, name, keep_color=True, recalc=True):
        if recalc:
            bmesh.ops.recalc_face_normals(self.bm, faces=self.bm.faces)
        if not keep_color:
            self.bm.loops.layers.float_color.remove(self.col)
        me = bpy.data.meshes.new(name)
        self.bm.to_mesh(me)
        self.bm.free()
        return me


def _pl(th, s, t):
    """(x, z) of the point s along and t across the direction th, in the wheel face plane (x, z)."""
    c, sn = math.cos(th), math.sin(th)
    return (s * c - t * sn, s * sn + t * c)


def _sl(R, t):
    """distance along a spoke at which the line t across it meets the circle R."""
    return math.sqrt(max(R * R - t * t, 0.0))


def _spoke_th(k):
    return math.pi / 2 + k * 2 * math.pi / N_SPOKE          # spoke 0 points up (+z), as on the press car


def _v3(cb, th, s, t, y):
    x, z = _pl(th, s, t)
    return cb.v((x, y, z))


def _panel(cb, k, level):
    """aero panel k (between spoke k and k + 1): ONE flat plane (Y_P), a fan from the apex where its two straight edges meet at the hub to the arc at the lip.
    Along both edges: the graphite bevel (from the panel plane down to the star's top, straight on to the rim) and the wall of the channel beside it, from the
    star's arm end to the lip (gloss black, with a copper wedge near the hub)."""
    n6 = math.pi / N_SPOKE
    th0 = _spoke_th(k)
    th1 = th0 + 2 * n6
    c, a = CH_A + CH_B, CH_A
    yf = Y_FLOOR[level]
    nar = (8, 3, 3)[level]
    ap = _v3(cb, th0, c / math.tan(n6), c, Y_P)             # the edge lines (t = +c of spoke k, t = -c of spoke k + 1) meet here
    aa = math.asin(c / FACE_R)
    arc = []
    for i in range(nar + 1):
        ang = th0 + aa + (th1 - th0 - 2 * aa) * i / nar
        arc.append(cb.v((FACE_R * math.cos(ang), Y_P, FACE_R * math.sin(ang))))
    for i in range(nar):
        cb.facen([ap, arc[i], arc[i + 1]], W_AERO, (0, 1, 0))
    s1 = _sl(FACE_R, a)
    val = _v3(cb, th0, a / math.tan(n6), a, Y_B)            # where the two bevels meet at the foot (the star's valley)
    for th, sg, edge_end in ((th0, 1, arc[0]), (th1, -1, arc[-1])):
        into = (sg * math.sin(th), 0.0, -sg * math.cos(th))          # from the wall into its channel
        up_in = (into[0] * 0.5, 0.85, into[2] * 0.5)
        ba = _v3(cb, th, S_ARM, sg * a, Y_B)                         # foot of the bevel at the arm end, and at the lip
        be = _v3(cb, th, s1, sg * a, Y_B)
        # bevel: a triangle along the star arm and a quad out to the lip (one plane, no T-junction).  2026-10-24 (polish, p003): the quad's top fifth (~2.5 mm, along the panel's
        # edge) is the polished stainless W_SS -- the photo's thin bright line between each white panel and the dark spoke (the rim's crown ring is the same metal); the triangle
        # is split at the same point (mt), so the shared edge has no T-junction
        mt, me_ = cb.v(tuple(ap.co.lerp(ba.co, BEV_SS))), cb.v(tuple(edge_end.co.lerp(be.co, BEV_SS)))
        cb.facen([ap, mt, val], W_BEV, up_in)
        cb.facen([mt, ba, val], W_BEV, up_in)
        cb.facen([ap, edge_end, me_, mt], W_SS, up_in)
        cb.facen([mt, me_, be, ba], W_BEV, up_in)
        wf = [_v3(cb, th, S_ARM, sg * a, yf), _v3(cb, th, s1, sg * a, yf)]
        if level >= 1:
            cb.facen([ba, be, wf[1], wf[0]], W_GLS, into)
            continue
        tip, hi0 = _v3(cb, th, 0.265, sg * a, yf), _v3(cb, th, S_ARM, sg * a, yf + 0.032)
        cb.facen([wf[0], tip, hi0], W_ACC, into)                              # copper wedge on the wall, widest at the hub
        cb.facen([hi0, tip, wf[1], be, ba], W_GLS, into)                      # rest of the wall
        top_end = _v3(cb, th, s1, sg * a, Y_P)
        cb.facen([edge_end, top_end, be], W_BEV, (-edge_end.co.x, 0.0, -edge_end.co.z))   # closes the bevel against the lip


def _channel(cb, k, level):
    """spoke channel k: gloss-black floor, the end wall against the lip, and the end of the star's arm at its hub end."""
    th = _spoke_th(k)
    a, yf = CH_A, Y_FLOOR[level]
    asn = math.asin(a / FACE_R)
    nar = (3, 2, 2)[level]
    arc_f, arc_t = [], []
    for i in range(nar + 1):
        ang = th + asn - 2 * asn * i / nar
        x, z = FACE_R * math.cos(ang), FACE_R * math.sin(ang)
        arc_f.append(cb.v((x, yf, z)))
        arc_t.append(cb.v((x, Y_P, z)))
    cb.facen([_v3(cb, th, S_ARM, -a, yf), _v3(cb, th, S_ARM, a, yf)] + arc_f, W_GLS, (0, 1, 0))
    for i in range(nar):
        cb.facen([arc_f[i], arc_f[i + 1], arc_t[i + 1], arc_t[i]], W_GLS, (-arc_f[i].co.x, 0.0, -arc_f[i].co.z))
    cb.facen([_v3(cb, th, S_ARM, -a, Y_B), _v3(cb, th, S_ARM, a, Y_B), _v3(cb, th, S_ARM, a, yf), _v3(cb, th, S_ARM, -a, yf)], W_HUB,
             (math.cos(th), 0.0, math.sin(th)))                     # end of the star arm


def _star(cb):
    """the graphite six-armed star hub: flat top at the foot of the bevels, an arm along every channel, valleys where the panels' tips come in."""
    n6 = math.pi / N_SPOKE
    ctr = cb.v((0.0, Y_B, 0.0))
    pts = []
    for k in range(N_SPOKE):
        th = _spoke_th(k)
        pts += [_v3(cb, th, S_ARM, -CH_A, Y_B), _v3(cb, th, S_ARM, CH_A, Y_B), _v3(cb, th + n6, 2 * CH_A, 0.0, Y_B)]
    for i in range(len(pts)):
        cb.facen([ctr, pts[i], pts[(i + 1) % len(pts)]], W_HUB, (0, 1, 0))


def _badge_t(cb, y0, y1, col):
    """the raised Tesla T on the cap: a prism over its outline (x, z; counter-clockwise)."""
    o = [(-0.0035, -0.0150), (0.0035, -0.0150), (0.0035, 0.0045), (0.0135, 0.0045), (0.0135, 0.0105), (-0.0135, 0.0105), (-0.0135, 0.0045), (-0.0035, 0.0045)]
    top = [cb.v((x, y1, z)) for x, z in o]
    bot = [cb.v((x, y0, z)) for x, z in o]
    cb.facen(top, col, (0, 1, 0))
    for i in range(len(o)):
        j = (i + 1) % len(o)
        cb.facen([top[i], top[j], bot[j], bot[i]], col, (o[j][1] - o[i][1], 0.0, o[i][0] - o[j][0]))      # outward = (dz, -dx)


# FRONT r3 (p018 / p017 / p016 measurements): the photo's tyre is a thin black ring round the wheel: outer radius 0.39 (p018: 108.5 px of 109.5), the rim's lit face ends at r 0.294-0.296 (fitted circle,
# FACE_R), the lip / bevel ring that closes it is 0.313 (was 0.324), and the sidewall is flush with the rim, not a fat pillow standing 3 cm out of it: the outboard silhouette in p017 puts the widest
# point of the sidewall at |y| ~ 0.11-0.12 (was 0.142), with a flat, narrow tread.  So: radius 0.39 / 0.30 as before, section half width 0.1185 at r 0.352, shoulder radius ~ 2 cm, tread +-0.055.
# Half contour from the bead on the rim (hidden under the lip) out to the tread centre, (r, |y|); mirrored for the inboard side.
TYRE_HALF = [(0.3000, 0.1040), (0.3090, 0.1105), (0.3200, 0.1145), (0.3360, 0.1180), (0.3520, 0.1185), (0.3660, 0.1160),
             (0.3770, 0.1085), (0.3855, 0.0950), (0.3895, 0.0780), (0.3900, 0.0550), (0.3900, 0.0)]


def _catmull(pts, per):
    """open Catmull-Rom through pts, `per` samples per span (the end points are kept)"""
    P = [pts[0]] + list(pts) + [pts[-1]]
    out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        for k in range(per):
            t = k / per
            out.append(tuple(0.5 * ((2 * p1[j]) + (-p0[j] + p2[j]) * t + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * t * t + (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * t ** 3) for j in range(2)))
    out.append(tuple(pts[-1]))
    return out


def _tyre_prof(nprof):
    """closed (r, y) contour of the tyre with exactly `nprof` points (nprof 8 / 22 are the lod2 / lod1 profiles, anything larger = hi, smoothed)"""
    H = TYRE_HALF
    if nprof == 22:                                           # lod1: 11 points per side, the tread centre point dropped for a second tread point (y 0.025)
        half = H[:-1] + [(0.3900, 0.025)]
    elif nprof == 8:                                          # lod2
        half = [H[0], H[4], H[7], (0.3900, 0.040)]
    else:
        half = _catmull(H[:-1], max(1, (nprof // 2) // (len(H) - 2))) + [(0.3900, 0.0)]
        out = half + [(r, -y) for r, y in reversed(half[:-1])]
        return out
    return half + [(r, -y) for r, y in reversed(half)]


# the rim's lip / bevel ring: its outer edge is the photo's rim edge (p018: bevel ring ends at ~ 88 px = 0.313; was 0.324), standing 6 mm out of the tyre wall like a rim protector
LIP_PROF = [(FACE_R, Y_P), (0.2985, 0.1185), (0.3035, 0.1207), (0.3095, 0.1210), (0.3135, 0.1180), (0.3150, 0.1100), (0.3120, 0.1000)]
LIP_PROF1 = [(FACE_R, Y_P), (0.2995, 0.1190), (0.3075, 0.1210), (0.3140, 0.1075)]
LIP_SS = (2, 2)                         # the lip's profile from this point on (hi, lod1) is the stainless ring W_SS (its crown and outer round, ~1.2 cm seen from the side); the inner slope stays dark


def rim_mesh(level):
    """level 0: hi (tyre is the separate source mesh); 1: lod1 incl. tyre; 2: lod2 incl. tyre (six flat sectors + six recessed black quads)."""
    cb = CB()
    st = (72, 28, 14)[level]
    tyre_tris = 0
    if level > 0:
        cb.lathe(_tyre_prof(22 if level == 1 else 8), 56 if level == 1 else 20, W_RUB, closed=True)
        bmesh.ops.recalc_face_normals(cb.bm, faces=list(cb.bm.faces))
        tyre_tris = sum(len(f.verts) - 2 for f in cb.bm.faces)
    if level == 2:
        n6 = math.pi / N_SPOKE
        for k in range(N_SPOKE):
            th0 = _spoke_th(k)
            th1 = th0 + 2 * n6
            c = CH_A + CH_B
            aa = math.asin(c / FACE_R)
            ap = _v3(cb, th0, c / math.tan(n6), c, Y_P)
            arc = [cb.v((FACE_R * math.cos(a_), Y_P, FACE_R * math.sin(a_))) for a_ in (th0 + aa, (th0 + th1) / 2, th1 - aa)]
            for i in range(2):
                cb.facen([ap, arc[i], arc[i + 1]], W_AERO, (0, 1, 0))
            s0, s1, yf = 0.060, _sl(FACE_R, CH_A), Y_FLOOR[2]
            cb.facen([_v3(cb, th0, s0, -CH_A, yf), _v3(cb, th0, s0, CH_A, yf), _v3(cb, th0, s1, CH_A, yf), _v3(cb, th0, s1, -CH_A, yf)], W_GLS, (0, 1, 0))
        print('WHEEL lod2 per wheel: tyre %d + rim %d tris' % (tyre_tris, sum(len(f.verts) - 2 for f in cb.bm.faces) - tyre_tris))
        return cb.mesh('Rim_l2', recalc=False)
    if level == 0:
        cb.lathe([(0.300, 0.104), (0.300, -0.128), (0.316, -0.134)], st, W_DARK)                    # barrel
    lp, ks = (LIP_PROF, LIP_SS[0]) if level == 0 else (LIP_PROF1, LIP_SS[1])
    cb.lathe(lp, st, [W_HUB if i < ks else W_SS for i in range(len(lp) - 1)])                        # lip (p018 / p003: the outer rim ring reads dark like the hub, not graphite like the bevels), its crown a thin polished stainless ring (2026-10-24)
    hs = 48 if level == 0 else 14
    if level == 0:
        cb.lathe([(0.0, 0.1155), (0.034, 0.1155)], hs, W_HUB)                                       # cap
        cb.lathe([(0.034, 0.1155), (0.0365, 0.1168), (0.039, 0.1155)], hs, W_BEV)                   # cap ring
        cb.lathe([(0.039, 0.1155), (0.044, 0.1108), (0.050, Y_B)], hs, W_HUB)                       # down to the star
    else:
        cb.lathe([(0.0, 0.1155), (0.040, 0.1155), (0.050, Y_B)], hs, W_HUB)
    bmesh.ops.recalc_face_normals(cb.bm, faces=[f for f in cb.bm.faces if f.is_valid])           # (the tyre / lathe faces; the flat sheets below are wound by hand)
    if level == 0:
        _badge_t(cb, 0.1150, 0.1172, W_BADGE)
    _star(cb)
    for k in range(N_SPOKE):
        _panel(cb, k, level)
        _channel(cb, k, level)
    print('WHEEL lod%d per wheel: tyre %d + rim %d tris' % (level, tyre_tris, sum(len(f.verts) - 2 for f in cb.bm.faces) - tyre_tris))
    return cb.mesh(f'Rim_l{level}', recalc=False)


def brake_meshes():
    d = CB()
    d.lathe([(0.104, 0.017), (0.214, 0.017), (0.216, -0.001), (0.214, -0.019), (0.104, -0.019)], 64, W_DARK, closed=True)
    d.lathe([(0.0, 0.056), (0.092, 0.056), (0.104, 0.030), (0.104, 0.008), (0.0, 0.008)], 40, W_DARK, closed=True)
    c = CB()
    r0, r1, y0, y1 = 0.158, 0.252, -0.046, 0.060
    a0, a1, n = math.radians(12), math.radians(82), 12
    secs = []
    for i in range(n + 1):
        a = a0 + (a1 - a0) * i / n
        ca, sa = math.cos(a), math.sin(a)
        secs.append([(r * ca, y, r * sa) for r, y in ((r0, y0), (r1, y0), (r1, y1), (r0, y1), (r0, y0))])
    c.prism(secs, [W_DARK] * 4, cap=W_DARK)
    bmesh.ops.remove_doubles(c.bm, verts=c.bm.verts, dist=1e-6)
    bmesh.ops.bevel(c.bm, geom=c.bm.edges[:], offset=0.005, segments=2, profile=0.6, affect='EDGES', clamp_overlap=True)
    return d.mesh('Disc', keep_color=False), c.mesh('Caliper', keep_color=False)


RIM_ME = {}


def rim_obj(me, name, left, mat_name='Rim', sharp=34):
    me2 = me.copy()
    mirror_mesh(me2, left)
    ob = bpy.data.objects.new(name, me2)
    link(ob)
    me2.materials.clear()
    me2.materials.append(M[mat_name])
    for p in me2.polygons:
        p.use_smooth = True
    mark_sharp(me2, sharp)
    ca = me2.color_attributes.get('Color')
    if ca is not None:      # a bmesh-made layer is neither active nor default (render): set both, or the exporter writes two
        me2.color_attributes.active_color = ca
        me2.attributes.active_color = ca
        me2.color_attributes.active_color_name = 'Color'
        me2.color_attributes.default_color_name = 'Color'
    return ob


# 2026-10-24 (p003 / p018): the press car's tyres carry white sidewall print ("TROFEO RS" large, "P ZERO"); the game's tyre shader only has a faint satin band.  Raised
# letters (0.5 mm) wrapped on the outboard sidewall, in the rim mesh (it spins with the wheel) with the rubber code 0 = matte, the rgb white (materials.js 'rim': no clear coat on rubber).
TYRE_TEXT = (('TROFEO RS', -math.pi / 2, 0.021), ('P ZERO', math.pi / 2, 0.018))      # (label, centre angle in the wheel plane, cap height: p018 (near-orthographic) 5-6 px = 2.1 cm)
TYRE_TEXT_R0 = 0.340                    # baseline radius: the print is centred on the visible sidewall (0.313 lip .. 0.39)
W_PRINT = (0.90, 0.90, 0.91, 0.0)


def _tyre_side_y(r):
    """|y| of the outboard sidewall at radius r (TYRE_HALF, linear between its points)"""
    H = TYRE_HALF[:-1]
    for (r0, y0), (r1, y1) in zip(H, H[1:]):
        if r0 <= r <= r1:
            return y0 + (y1 - y0) * (r - r0) / (r1 - r0)
    return H[-1][1] if r > H[-1][0] else H[0][1]


def tyre_text_mesh(rev):
    """the sidewall print in the right wheel's frame (axle +y = outboard); rev: written backwards, for the left wheels (mirror_mesh turns it round)"""
    cb = CB()
    for label, thc, cap in TYRE_TEXT:
        cu = bpy.data.curves.new('tyre_text', 'FONT')
        cu.body = label
        cu.size = cap / 0.72
        cu.extrude = 0.00025
        cu.resolution_u = 2
        cu.bevel_depth = 0.022 * cap                           # bold: an edge bevel widens the strokes (Blender's bundled font has no bold cut; the press tyre's print is heavy;
        cu.bevel_resolution = 0                                # the outline offset broke the T's fill)
        cu.space_character = 1.12
        cu.align_x = 'CENTER'
        tob = bpy.data.objects.new('tyre_text', cu)
        link(tob)
        me = bpy.data.meshes.new_from_object(tob.evaluated_get(depsgraph()))
        bm = bmesh.new()
        bm.from_mesh(me)
        vm = {}
        for v in bm.verts:
            x, y, z = v.co
            r = TYRE_TEXT_R0 + y
            th = thc + (-x if rev else x) / r                  # clockwise seen from outside, letter tops outward
            vm[v] = cb.v((r * math.cos(th), _tyre_side_y(r) + 0.0006 + z, r * math.sin(th)))
        for f in bm.faces:                                     # (the map keeps the text's own winding for the right wheel and mirrors it when rev: reverse those faces;
            vs = [vm[v] for v in f.verts]                      # recalc_face_normals flipped some letter caps of these open pieces inward, they shaded black)
            cb.face(vs[::-1] if rev else vs, W_PRINT)
        bm.free()
        bpy.data.objects.remove(tob, do_unlink=True)
        bpy.data.meshes.remove(me)
        bpy.data.curves.remove(cu)
    return cb.mesh('TyreText_%s' % ('L' if rev else 'R'), recalc=False)


def build_wheel_hi2(tag, wx, sgn):
    left = sgn < 0
    if 0 not in RIM_ME:
        RIM_ME[0] = rim_mesh(0)
        RIM_ME['brake'] = brake_meshes()
    if 'tyre' not in RIM_ME:                                  # FRONT r3: the hi tyre is the same (r, y) contour as the lod ones, lathed finely (the source wedge_car tyre was the fat 0.142 superellipse)
        _tc = CB()
        _tc.lathe(_tyre_prof(60), 96, W_RUB, closed=True)
        RIM_ME['tyre'] = _tc.mesh('Tyre_hi', keep_color=False)
        print('WHEEL hi per wheel: tyre %d tris' % sum(len(p.vertices) - 2 for p in RIM_ME['tyre'].polygons))
    hub = empty(f'Wheel_{tag}', (wx, sgn * WHEEL_Y, WHEEL_Z))
    spin = empty(f'Spin_{tag}', (0, 0, 0), hub)
    t = rim_obj(RIM_ME['tyre'], f'Tyre_{tag}', left, 'Tyre', sharp=70)
    t.parent = spin
    rim = rim_obj(RIM_ME[0], f'Rim_{tag}', left)
    if ('text', left) not in RIM_ME:
        RIM_ME[('text', left)] = tyre_text_mesh(left)
        print('WHEEL hi per wheel: sidewall print %d tris' % sum(len(p.vertices) - 2 for p in RIM_ME[('text', left)].polygons))
    rim = join([rim, rim_obj(RIM_ME[('text', left)], f'RimText_{tag}', left)], f'Rim_{tag}')
    ca = rim.data.color_attributes.get('Color')
    if ca is not None:
        rim.data.color_attributes.active_color = ca
        rim.data.attributes.active_color = ca
        rim.data.color_attributes.active_color_name = 'Color'
        rim.data.color_attributes.default_color_name = 'Color'
    rim.parent = spin
    disc = rim_obj(RIM_ME['brake'][0], f'Disc_{tag}', left, 'BrakeDisc', sharp=40)
    cal = rim_obj(RIM_ME['brake'][1], f'Cal_{tag}', left, 'Caliper', sharp=40)
    brake = join([disc, cal], f'Brake_{tag}')
    brake.parent = hub
    return hub


def wheel_lod_obj(tag, sgn, level):
    if level not in RIM_ME:
        RIM_ME[level] = rim_mesh(level)
    return rim_obj(RIM_ME[level], f'Wheel_{tag}_mesh', sgn < 0, sharp=40 if level == 1 else 50)


# ------------------------------------------------------------ tools offered to the regions through ctx
def cb_obj(cb, name, mat_name, keep_color=False, sharp=40):
    me = cb.mesh(name, keep_color=keep_color)
    ob = bpy.data.objects.new(name, me)
    link(ob)
    me.materials.append(M[mat_name])
    mark_sharp(me, sharp)
    ca = me.color_attributes.get('Color')
    if ca is not None:
        me.color_attributes.active_color = ca
        me.attributes.active_color = ca
        me.color_attributes.active_color_name = 'Color'
        me.color_attributes.default_color_name = 'Color'
    return ob


# ------------------------------------------------------------------- export
def export_glb(objs, path, compress=True):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    kw = dict(filepath=path, export_format='GLB', use_selection=True, export_apply=True, export_texcoords=True,
              export_normals=True, export_materials='EXPORT', export_vertex_color='ACTIVE', export_cameras=False,
              export_lights=False, export_yup=True, export_extras=False, export_animations=False, export_skins=False,
              export_morph=False)
    if compress:
        kw.update(export_meshopt_compression_enable=True, export_meshopt_extension='EXT_meshopt_compression')
        # q5 item 3: the exporter encodes POSITION / NORMAL with meshopt's exponential filter at a fixed 12-bit mantissa (io/exp/meshopt.py EXP_FILTER_BITS), shared per vertex: a vertex 2-4 m from
        # the origin lands on a 1-2 mm grid.  That broke the 0.7 mm panel-gap strips into dashes and made the crests / reflections ripple in the showroom (the .raw.glb was clean).  18 bits = a grid of
        # <= 0.03 mm out to 4 m; the decoder reads any mantissa width, nothing changes on the game side.
        import io_scene_gltf2.io.exp.meshopt as _mo
        _mo.EXP_FILTER_BITS = int(arg('--exp-bits', '18'))
    bpy.ops.export_scene.gltf(**kw)
    print('EXPORTED', path, os.path.getsize(path) // 1024, 'kB')


def cleanup(objs):
    names = [o.name for o in objs]
    for n in names:
        ob = bpy.data.objects.get(n)
        if ob is None:
            continue
        me = ob.data if ob.type == 'MESH' else None
        bpy.data.objects.remove(ob, do_unlink=True)
        if me is not None and me.users == 0:
            bpy.data.meshes.remove(me)


def p3_post(objs):
    """QF_P3_TAILX (shell2.p3_dx, CALIB.md phase 3): the rear-end extension, applied to the whole built car in world space: every mesh is deformed vertex by vertex except the
    wheels; the wing node (a pivot with its parts as children) moves rigidly by the displacement of its origin.  Meshes shared between objects are made single-user first."""
    if not shell2mod.QF_P3_TAILX:
        return
    from mathutils import Vector

    def under(o, pref):
        while o is not None:
            if o.name.startswith(pref):
                return True
            o = o.parent
        return False
    n = 0
    for o in objs:
        if under(o, 'Wheel_'):
            continue
        if o.name == 'Wing':
            w = o.matrix_world.translation
            d = shell2mod.p3_dx(w.x, w.y, w.z)
            pm = o.parent.matrix_world.inverted() if o.parent else None
            o.location = (pm @ (w + Vector((d, 0.0, 0.0)))) if pm else (w + Vector((d, 0.0, 0.0)))
            continue
        if under(o.parent, 'Wing') or o.type != 'MESH':
            continue
        if o.data.users > 1:
            o.data = o.data.copy()
        mw = o.matrix_world
        inv = mw.inverted()
        for v in o.data.vertices:
            w = mw @ v.co
            if w.x < 1.15:
                continue
            d = shell2mod.p3_dx(w.x, w.y, w.z)
            if d:
                v.co = inv @ Vector((w.x + d, w.y, w.z))
                n += 1
        o.data.update()
    print('P3 rear extension: %d vertices moved (S = %.3f m)' % (n, shell2mod.QF_P3_TX_S))


def collect(root_objs):
    out = []

    def rec(o):
        out.append(o)
        for c in o.children:
            rec(c)
    for r in root_objs:
        rec(r)
    return out


# ============================================================== LOD builders
def decimate_body(src_obj, target, name, sharp=40, level=1):
    """src_obj: cage object with modifiers (Bevel, Subsurf); returns a baked, decimated, symmetric mesh object."""
    ob = duplicate(src_obj, name + '_tmp')
    ob.matrix_world = src_obj.matrix_world.copy()
    dm = ob.modifiers.new('Dec', 'DECIMATE')
    dm.decimate_type = 'COLLAPSE'
    dm.use_collapse_triangulate = True
    dm.use_symmetry = True
    dm.symmetry_axis = 'Y'
    cur = tri_count([ob])
    ratio = min(1.0, target / max(cur, 1))
    for _ in range(4):
        dm.ratio = ratio
        n = tri_count([ob])
        if abs(n - target) / target < 0.04:
            break
        ratio *= target / max(n, 1)
        ratio = min(1.0, ratio)
    res = bake(ob, name)
    remap_mats(res)
    for p in res.data.polygons:
        if p.material_index == 3:
            p.material_index = 2
    ctxmod.call(REG, CTX, 'rear', 'lod_post', level, res)       # the collapse smears the tail's paint / black outline: REAR redoes it on the decimated faces
    mark_sharp(res.data, sharp)
    delete([ob])
    return res


report['body_hi_tris'] = tri_count([body_hi])


def finish_static(objs, name):
    j = join(objs, name)
    # drop empty material slots
    bpy.ops.object.select_all(action='DESELECT')
    j.select_set(True)
    bpy.context.view_layer.objects.active = j
    try:
        bpy.ops.object.material_slot_remove_unused()
    except Exception as e:
        print('slot cleanup', e)
    return j


# ------------------------------------------------------------------------ regions (regions/ctx.py, REGIONS.md section 2)
# material policy per level, for the lamps and detail materials of the FRONT / SIDE parts (draw-call budget: lod1 <= 20, lod2 <= 10); None = drop the part
LEVEL_MATS = {0: {},
              1: {'HeadLens': None, 'Caliper': None, 'SideMarker': None, 'Reflector': None, 'Trim': 'Trim'},
              2: {'HeadLens': None, 'Caliper': None, 'SideMarker': None, 'Reflector': None, 'PanelGap': None, 'GlossBlack': 'Trim', 'Carbon': 'Trim'}}
_s2 = globals().get('shell2mod')
CTX.mk = lambda bm, name, mat, smooth: obj_from_bm(bm, name, mat, smooth=smooth)
CTX.mat = lambda name: M[name]
CTX.mat_of = lambda level, name: LEVEL_MATS[level].get(name, name)
CTX.patch = lambda *a, **k: patch(*a, surf=CTX.surf, **k)          # projects onto ctx.surf (the surface of the level being built)
CTX.CB, CTX.Builder, CTX.W_DARK, CTX.smooth = CB, Builder, W_DARK, smooth
CTX.mark_sharp, CTX.cb_obj, CTX.link, CTX.join = mark_sharp, cb_obj, link, join
CTX.A = types.SimpleNamespace(D=getattr(_s2, 'D', None), S2=_s2, glass_half_width=bt_E)      # the accepted shell's interface (design2 curves / anchors, shell2, glass edge)
CTX.surf = CTX.surf_hi = SURF
print('REGIONS ' + ' '.join('%s=%s' % (r, REG[r].SOURCE) for r in ctxmod.REGIONS))


def run_regions(level, body_obj):
    """Region hooks for one level -> {region: dict(parts=[objects for the Body], nodes={name: object}, decals=[objects for the Decals node])}.
    FRONT and SIDE cast on the HI surface (as before the split, also at the LODs); REAR casts on this level's own body (the decimated one at lod1 / lod2)."""
    CTX.level, CTX.body = level, body_obj
    CTX.surf = SURF if level == 0 else Surf(body_obj)
    out = {}
    for r in ctxmod.REGIONS:
        out[r] = dict(parts=ctxmod.call(REG, CTX, r, 'build', level, default=[]) or [],
                      nodes=ctxmod.call(REG, CTX, r, 'nodes', level, default={}) or {},
                      decals=ctxmod.call(REG, CTX, r, 'decals', level, default=[]) or [])
    return out


def region_stats(R, shell_objs, other_objs):
    """per-region numbers of one output, taken BEFORE the static parts are joined into the Body (the join consumes them): triangles, and the draw calls a region
    ADDS = the materials its Body parts have that no other part of the Body has + the material slots of its own nodes."""
    def mats(objs):
        return {sl.material.name for o in objs for sl in o.material_slots if sl.material}
    groups = {'shell': list(shell_objs), 'common': list(other_objs)}
    groups.update({r: R[r]['parts'] for r in ctxmod.REGIONS})
    st = {}
    for g, objs in groups.items():
        rest = set().union(*[mats(v) for k, v in groups.items() if k != g])
        st[g] = dict(tris=tri_count(objs), calls=len(mats(objs) - rest), mats=sorted(mats(objs)))
    for r in ctxmod.REGIONS:
        nd = collect(list(R[r]['nodes'].values()))
        st[r]['tris'] += tri_count(nd) + tri_count(R[r]['decals'])
        st[r]['calls'] += sum(len(o.data.materials) for o in nd if o.type == 'MESH')
    return st


REGION_REPORT = {}


def finish_stats(name, st, tris, calls):
    """complete the per-region numbers with the totals of the output: 'common' = everything that is neither the shell nor a region part (interior, wheels,
    steering, door / hood decals ...)"""
    reg = sum(st[r]['tris'] for r in ctxmod.REGIONS)
    out = {r: dict(tris=st[r]['tris'], calls=st[r]['calls']) for r in ctxmod.REGIONS}
    out['shell'] = dict(tris=st['shell']['tris'])
    out['common'] = dict(tris=tris - st['shell']['tris'] - reg, calls=calls - sum(st[r]['calls'] for r in ctxmod.REGIONS))
    out['total'] = dict(tris=tris, calls=calls)
    REGION_REPORT[name] = out


# ----------------------------------------------------------------------------- HI
def build_hi():
    interior = build_interior(0)
    fit_interior(interior)
    R = run_regions(0, body_hi)
    _skip = [n for n in os.environ.get('NO_PARTS', '').split(',') if n]          # (debug) leave named rear parts out, e.g. CornerFin,Diffuser
    R['rear']['parts'] = [o for o in R['rear']['parts'] if not any(o.name.startswith(n) for n in _skip)]
    pre = ([duplicate(drl)] if drl else []) + [duplicate(o) for o in lines] + [duplicate(o) for o in others] + [duplicate(o) for o in details]
    st = region_stats(R, [body_hi], pre + interior)
    stat = [body_hi] + pre + R['front']['parts'] + R['side']['parts'] + interior + R['rear']['parts']
    stat_body = finish_static(stat, 'Body')
    dec = [duplicate(o) for o in decal_objs] + [o for r in ctxmod.REGIONS for o in R[r]['decals']]
    decal = join(dec, 'Decals') if len(dec) > 1 else dec[0]
    steer = build_steering()
    wheels = [build_wheel_hi2(t, wx, s) for t, wx, s in WHEELS]
    root = empty('Car')
    allobjs = [root]
    for o in [stat_body, decal, steer] + [n for r in ctxmod.REGIONS for n in R[r]['nodes'].values()] + wheels:
        o.parent = root
    allobjs = collect([root])
    report['hi_tris'] = tri_count([o for o in allobjs if o.type == 'MESH'])
    report['hi_calls'] = sum(len(o.data.materials) for o in allobjs if o.type == 'MESH')
    finish_stats('hi', st, report['hi_tris'], report['hi_calls'])
    p3_post(allobjs)
    export_glb(allobjs, os.path.join(OUT, 'car_hi' + ('.raw.glb' if RAW else '.glb')), compress=not RAW)
    cleanup(allobjs)


def build_lod1():
    # body: subsurf level 2 + collapse to ~32k
    b = decimate_body(body_dense, 31000, 'Body_l1', sharp=38, level=1)
    # lamps merged: lens + DRL -> HeadDRL (the rear skins come as TailLamp at this level)
    tmp = []
    for o in ([drl] if drl else []) + [d for d in details if d.name.startswith('HeadLens')]:
        c = duplicate(o)
        set_mat(c, 'HeadDRL')
        tmp.append(c)
    keep = [duplicate(o) for o in others if not o.name.startswith(('DiffuserFin', 'DoorHandle', 'SideMarker', 'SideBlade'))]
    interior = build_interior(1)
    fit_interior(interior, 0.03)
    for o in interior:
        if o.data.materials[0].name in ('IntScreen', 'IntAccent', 'IntLeather'):       # (one interior material: the call budget went to the front end's lamps)
            set_mat(o, 'IntPlastic')
    R = run_regions(1, b)
    st = region_stats(R, [b], tmp + keep + interior)
    stat = finish_static([b] + tmp + keep + R['front']['parts'] + R['side']['parts'] + interior + R['rear']['parts'], 'Body')
    decal = join([duplicate(o) for o in decal_objs] + [o for r in ctxmod.REGIONS for o in R[r]['decals']], 'Decals')
    wheels = []
    root = empty('Car')
    for t, wx, s in WHEELS:
        hub = empty(f'Wheel_{t}', (wx, s * WHEEL_Y, WHEEL_Z), root)
        spin = empty(f'Spin_{t}', (0, 0, 0), hub)
        w = wheel_lod_obj(t, s, 1)
        w.parent = spin
        wheels.append(hub)
    for o in [stat, decal] + [n for r in ctxmod.REGIONS for n in R[r]['nodes'].values()]:
        o.parent = root
    allobjs = collect([root])
    report['lod1_tris'] = tri_count([o for o in allobjs if o.type == 'MESH'])
    report['lod1_calls'] = sum(len(o.data.materials) for o in allobjs if o.type == 'MESH')
    finish_stats('lod1', st, report['lod1_tris'], report['lod1_calls'])
    p3_post(allobjs)
    export_glb(allobjs, os.path.join(OUT, 'car_lod1' + ('.raw.glb' if RAW else '.glb')), compress=not RAW)
    cleanup(allobjs)


def build_lod2():
    b = decimate_body(body_dense, 5200, 'Body_l2', sharp=35, level=2)
    tmp = []
    for o in ([drl] if drl else []) + [d for d in details if d.name.startswith('HeadLens')]:
        c = duplicate(o)
        set_mat(c, 'HeadDRL')
        tmp.append(c)
    keep = [duplicate(o) for o in others if o.name.startswith(('FrontSplitter',))]
    for o in keep:
        set_mat(o, 'Trim')
    # dark cabin block so the glass does not show the ground through the body
    cab = Builder()
    cab.rbox('IntPlastic', (0.2, 0, 0.62), (3.0, 1.5, 0.7), bev=0.0, seg=1)
    cabo = cab.objects('Cab', sharp=60, smooth=False)
    fit_interior(cabo, 0.04)
    R = run_regions(2, b)               # (lod2 has no nodes and no Decals node: the rear is static, the plate decal is not drawn)
    st = region_stats(R, [b], tmp + keep + cabo)
    stat = finish_static([b] + tmp + keep + R['front']['parts'] + R['side']['parts'] + cabo + R['rear']['parts'], 'Body')
    ws = []
    for t, wx, s in WHEELS:
        w = wheel_lod_obj(t, s, 2)
        place_mesh_at_hub(w, wx, s)
        ws.append(w)
    wheels = join(ws, 'Wheels')
    root = empty('Car')
    stat.parent = root
    wheels.parent = root
    allobjs = collect([root])
    report['lod2_tris'] = tri_count([o for o in allobjs if o.type == 'MESH'])
    report['lod2_calls'] = sum(len(o.data.materials) for o in allobjs if o.type == 'MESH')
    finish_stats('lod2', st, report['lod2_tris'], report['lod2_calls'])
    p3_post(allobjs)
    export_glb(allobjs, os.path.join(OUT, 'car_lod2' + ('.raw.glb' if RAW else '.glb')), compress=not RAW)
    cleanup(allobjs)


if ONLY in ('all', 'hi'):
    build_hi()
if ONLY in ('all', 'lod1'):
    build_lod1()
if ONLY in ('all', 'lod2'):
    build_lod2()

# ---- car_meta.json: only a full build (--only all) writes it (the regions' parts of it come from their meta() hooks)
if ONLY == 'all':
    meta = dict(
        glbFrame='-X forward, +Z left, +Y up, metres',
        hubs={'FL': [WHEEL_X[0], -WHEEL_Y, WHEEL_Z], 'FR': [WHEEL_X[0], WHEEL_Y, WHEEL_Z], 'RL': [WHEEL_X[1], -WHEEL_Y, WHEEL_Z],
              'RR': [WHEEL_X[1], WHEEL_Y, WHEEL_Z]},
        tyreRadius=TYRE_R,
        atlas=[2048, 1024],
        decals={k: dict(uv=list(v['uv']), x=list(v.get('x', [])), y=list(v.get('y', [])), z=list(v.get('z', [])), side=v.get('side', 0))
                for k, v in DECALS.items()},
        steering=dict(pivot=[-0.98, DRV, 0.795], tiltDeg=65),
    )
    CTX.level, CTX.surf, CTX.body = 0, SURF, body_hi
    for r in ctxmod.REGIONS:
        for k, v in (ctxmod.call(REG, CTX, r, 'meta', default={}) or {}).items():
            if k == 'decals':
                meta['decals'].update(v)
            else:
                meta[k] = v
    if shell2mod.QF_P3_TAILX and 'wing' in meta:          # the wing's pivot moves with the rear-end extension (p3_post)
        _pv = meta['wing']['pivot']
        _pv[0] = _pv[0] + shell2mod.p3_dx(_pv[0], -_pv[2], _pv[1])
    meta['report'] = report
    with open(os.path.join(OUT, 'car_meta.json'), 'w') as f:
        json.dump(meta, f, indent=1)
else:
    print('car_meta.json not written (--only %s)' % ONLY)

# ---- build report: totals as before + the per-region breakdown (triangles; draw calls a region adds)
print('REGION BUDGET            ' + ''.join('%-22s' % n for n in REGION_REPORT))
for _k in ('shell', 'common') + tuple(ctxmod.REGIONS) + ('total',):
    print('  %-22s' % _k + ''.join('%-22s' % ('%6d tris%s' % (v[_k]['tris'], '  +%d calls' % v[_k]['calls'] if 'calls' in v[_k] else '')) for v in REGION_REPORT.values()))
for _r, _n in CTX.notes.items():
    print('REGION NOTE', _r, json.dumps(_n))
print('REPORT', json.dumps(dict(report, regions=REGION_REPORT)))
