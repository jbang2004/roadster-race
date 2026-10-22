"""
Shared helpers and constants for the build (P0 split).  Imported by build_game_car.py, the region modules (regions/*.py) and the locked
shell2.py (`import common as V1`).  Pure python + bpy/bmesh; no state of its own.

  interpolation   pchip, pchip_s, smooth, smoother, sstep
  wheels / arches HUBS, HUB_Z, R_ARCH, Y_TUB  (wheel centres x -1.487 / 1.61, z 0.39, arch radius 0.415, wheel-well wall y 0.70)
  intake         INTAKE, cut_intake(ob)   (the --front lower intake pocket; shell2.cut_intake delegates to it)
  small meshes    Mesh, grid, prism        (bmesh helpers used by the front and side parts)
"""
import bpy, bmesh
from mathutils import Vector


# ----------------------------------------------------------------------------- interpolation
def pchip(pts, x):
    """monotone cubic through (x, y) control points."""
    if x <= pts[0][0]:
        return pts[0][1]
    if x >= pts[-1][0]:
        return pts[-1][1]
    n = len(pts)
    h = [pts[i + 1][0] - pts[i][0] for i in range(n - 1)]
    d = [(pts[i + 1][1] - pts[i][1]) / h[i] for i in range(n - 1)]
    m = [d[0]] + [0.0 if d[i - 1] * d[i] <= 0 else 2 * d[i - 1] * d[i] / (d[i - 1] + d[i]) for i in range(1, n - 1)] + [d[-1]]
    for i in range(n - 1):
        if x <= pts[i + 1][0]:
            t = (x - pts[i][0]) / h[i]
            t2, t3 = t * t, t * t * t
            return ((2 * t3 - 3 * t2 + 1) * pts[i][1] + (t3 - 2 * t2 + t) * h[i] * m[i] + (-2 * t3 + 3 * t2) * pts[i + 1][1]
                    + (t3 - t2) * h[i] * m[i + 1])
    return pts[-1][1]


def smooth(a, b, x):
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3.0 - 2.0 * t)


def smoother(a, b, x):
    """quintic smootherstep: C2 at both ends."""
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)


def pchip_s(pts, x, w=0.05):
    """pchip, box-smoothed over +-w/2 (a monotone cubic has curvature jumps at its knots, which glossy paint shows as lines)."""
    return sum(k * pchip(pts, x + (i - 2) * w * 0.5) for i, k in enumerate((1, 2, 3, 2, 1))) / 9.0


def sstep(a, b, x):
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3.0 - 2.0 * t)


# ----------------------------------------------------------------------------- vertex-colour code of the dark carbon / trim parts (rgb + material code, see build_game_car.py header)
W_DARK = (0.030, 0.030, 0.034, 0.15)


# ----------------------------------------------------------------------------- wheels / arches (fixed values: the game's physics depends on them)
HUBS = ((-1.487, -1), (-1.487, 1), (1.61, -1), (1.61, 1))      # (x, side)
HUB_Z = 0.39
R_ARCH = 0.415                                                  # arch radius (tyre 0.39): the arch top is at z 0.805
Y_TUB = 0.70                                                    # inner wall of the wheel well (the tyre's inner face is at 0.743)


# ----------------------------------------------------------------------------- lower intake (R2): a pocket cut into the black front face
INTAKE = dict(y=0.60, z0=0.250, z1=0.378, depth=0.055)       # half width, opening bottom / top (z), depth of the recess (m, towards the tail)


def cut_intake(ob):
    """cut the rectangular lower intake out of the front face of the dense mesh: the outline is cut into the mesh with four bisect planes, then the
    enclosed faces are extruded `depth` towards the tail (a real recess with a floor and four walls, all Trim)."""
    I = INTAKE
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
    eps = 1e-4
    inner = [f for f in bm.faces if f.calc_center_median().x < -2.3 and f.normal.x < -0.4
             and -I['y'] < f.calc_center_median().y < I['y'] and I['z0'] < f.calc_center_median().z < I['z1']]
    ret = bmesh.ops.extrude_face_region(bm, geom=inner)
    newv = [e for e in ret['geom'] if isinstance(e, bmesh.types.BMVert)]
    newf = [e for e in ret['geom'] if isinstance(e, bmesh.types.BMFace)]
    bmesh.ops.translate(bm, verts=newv, vec=(I['depth'], 0, 0))
    bmesh.ops.delete(bm, geom=inner, context='FACES')
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


# ----------------------------------------------------------------------------- small bmesh helpers (front / side parts)
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
