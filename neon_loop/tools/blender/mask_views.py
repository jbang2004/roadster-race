"""
Flat-colour mask renders of a car GLB from the matched press-photo cameras (VIEWS in render_ref_views.py), for measuring (silhouette diffs, glass outline, ear tips): Workbench, FLAT light, no
anti-aliasing, transparent background.  Paint = white, Glass = red, everything else = grey (Trim / lamps / wheels ...).

  Blender -b --python tools/blender/mask_views.py -- --glb <car.raw.glb> --out <dir> [--views p013,p018,r81,high] [--wing stow|deploy|hide]

Writes <view>_mask.png (RGBA; alpha = silhouette).  Use measure_masks.py (numpy) to compare two sets.
"""
import bpy, ast, math, os, sys, json
from mathutils import Vector, Euler, Quaternion

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
def arg(n, d): return argv[argv.index(n) + 1] if n in argv else d
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
GLB = os.path.abspath(arg('--glb', os.path.join(ROOT, 'public', 'assets', 'car', 'car_hi.raw.glb')))
OUT = os.path.abspath(arg('--out', os.path.join(ROOT, 'shots', 'full_rework', 'masks'))); os.makedirs(OUT, exist_ok=True)
NAMES = arg('--views', 'p013,p018,r81,high').split(',')
WING = arg('--wing', 'stow')
src = open(os.path.join(HERE, 'render_ref_views.py')).read()
VIEWS = next(ast.literal_eval(n.value) for n in ast.parse(src).body if isinstance(n, ast.Assign) and getattr(n.targets[0], 'id', '') == 'VIEWS')

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=GLB)
sc = bpy.context.scene
sys.path.insert(0, HERE); import wingpose             # the wing pose (stow / deploy / hide, old and new meta.wing format) lives in wingpose.py
wingpose.apply(WING, GLB)
for m in bpy.data.materials:
    col = (1, 1, 1, 1) if m.name.startswith('Paint') else (1, 0, 0, 1) if m.name.startswith('Glass') else (0.25, 0.25, 0.25, 1)
    m.diffuse_color = col
if '--dump-verts' in argv:        # --dump-verts <out.npz>: every mesh vertex in world space (after the wing pose) with its class (0 paint, 1 glass, 2 other) -> cam.py fit (cam_fit.py)
    import numpy as np
    V, C = [], []
    for o in bpy.data.objects:
        if o.type != 'MESH' or o.hide_render:
            continue
        me, M = o.data, o.matrix_world
        cl = np.full(len(me.vertices), 2, np.int8)
        for pl in me.polygons:
            mt = o.material_slots[pl.material_index].material if pl.material_index < len(o.material_slots) else None
            k = 0 if (mt and mt.name.startswith('Paint')) else 1 if (mt and mt.name.startswith('Glass')) else 2
            for v in pl.vertices:
                cl[v] = min(cl[v], k) if cl[v] != 2 else k
        co = np.empty(len(me.vertices) * 3); me.vertices.foreach_get('co', co)
        P = np.asarray(M) @ np.vstack([co.reshape(-1, 3).T, np.ones(len(me.vertices))])
        ed = np.empty(len(me.edges) * 2, int); me.edges.foreach_get('vertices', ed); ed = ed.reshape(-1, 2)
        A, B = P[:3].T[ed[:, 0]], P[:3].T[ed[:, 1]]
        ln = np.linalg.norm(B - A, axis=1)
        nsub = np.ceil(ln / 0.004).astype(int) - 1            # edge samples every <= 4 mm (the silhouette of a sparse panel edge is a line, not its vertices)
        e = np.repeat(np.arange(len(ed)), np.maximum(nsub, 0))
        t = (np.arange(len(e)) - np.repeat(np.cumsum(np.maximum(nsub, 0)) - np.maximum(nsub, 0), np.maximum(nsub, 0)) + 1) / (nsub[e] + 1)
        Q = A[e] + (B[e] - A[e]) * t[:, None]
        cq = np.minimum(cl[ed[e, 0]], cl[ed[e, 1]])
        P = np.hstack([P[:3], Q.T])
        cl = np.concatenate([cl, cq])
        V.append(P[:3].T); C.append(cl)
    np.savez(arg('--dump-verts', 'verts.npz'), v=np.vstack(V), c=np.concatenate(C))
    print('VERTS', len(np.concatenate(C)))
sc.render.engine = 'BLENDER_WORKBENCH'
sc.display.shading.light = 'FLAT'; sc.display.shading.color_type = 'MATERIAL'
sc.display.render_aa = 'OFF'
sc.view_settings.view_transform = 'Standard'
sc.render.film_transparent = True
for n in NAMES:
    loc, tgt, lens, (w, h), (sx, sy), *roll = VIEWS[n]
    cd = bpy.data.cameras.new(n); cd.lens = lens; cd.sensor_width = 36; cd.sensor_fit = 'HORIZONTAL'; cd.shift_x, cd.shift_y = sx, sy
    cam = bpy.data.objects.new(n, cd); sc.collection.objects.link(cam); cam.location = loc
    d = (Vector(tgt) - Vector(loc)).normalized(); r = math.radians(roll[0]) if roll else 0.0
    cam.rotation_euler = Euler((0, 0, r)) if abs(d.z) > 0.999999 else (d.to_track_quat('-Z', 'Y') @ Quaternion((0, 0, 1), r)).to_euler()
    sc.camera = cam; sc.render.resolution_x, sc.render.resolution_y = w, h
    sc.render.filepath = os.path.join(OUT, f'{n}_mask.png'); bpy.ops.render.render(write_still=True)
    print('MASK', n, sc.render.filepath)
