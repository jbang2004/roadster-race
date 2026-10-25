"""
Fast preview of the panel shell (~20 s instead of the 8 min shell2_view / build_game_car runs): builds the panels with shell2 (pure numpy), welds them, marks every panel boundary
that build_shell2 would fillet as a sharp edge (smooth pairs stay smooth), smooth-shades the rest and exports a GLB that render_ref_views.py can render (studio or --reflect h|v).
No fillets, no arch cuts, no wheels / lamps / wing: for judging surfaces and creases, not for the game.

  Blender -b --python tools/blender/fast_preview.py -- --out <dir>        (writes <dir>/car.glb and a copy of public/assets/car/car_meta.json)
  Blender -b --python tools/blender/render_ref_views.py -- --glb <dir>/car.glb --out <dir>/studio --views high,p018 [--reflect h]
"""
import bpy, bmesh, math, os, sys, shutil
argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
OUT = os.path.abspath(argv[argv.index('--out') + 1] if '--out' in argv else '/tmp/fast_preview')
os.makedirs(OUT, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
import shell2 as S2

panels, R = S2.build_panels()
V, F, M, PID, names = S2.assemble(panels)
if S2.QF_P3_TAILX:          # the rear-end extension is applied to the built car at export (build_game_car.p3_post): the preview takes it too
    V = [tuple(float(c) for c in p[:3]) if p[0] < 1.15 else tuple(float(a + b) for a, b in zip(p[:3], S2.p3_dxyz(*p[:3]))) for p in V]
me = bpy.data.meshes.new('Shell')
me.from_pydata([tuple(map(float, p)) for p in V], [], [list(f) for f in F])
me.update()
for k, n in ((S2.PAINT, 'Paint'), (S2.GLASS, 'Glass'), (S2.TRIM, 'Trim')):
    me.materials.append(bpy.data.materials.new(n))
order = {S2.PAINT: 0, S2.GLASS: 1, S2.TRIM: 2}
me.polygons.foreach_set('material_index', [order[m] for m in M])
for p in me.polygons:
    p.use_smooth = True
bm = bmesh.new()
bm.from_mesh(me)
nsharp = 0
for e in bm.edges:
    if len(e.link_faces) != 2:
        continue
    a, b = e.link_faces
    pa, pb = names[PID[a.index]], names[PID[b.index]]
    if pa != pb and frozenset((pa, pb)) not in S2.SMOOTH_PAIRS and a.normal.angle(b.normal) > math.radians(1.5):
        e.smooth = False
        nsharp += 1
bm.to_mesh(me)
bm.free()
ob = bpy.data.objects.new('Shell', me)
bpy.context.scene.collection.objects.link(ob)
bpy.context.view_layer.objects.active = ob
ob.select_set(True)
glb = os.path.join(OUT, 'car.glb')
bpy.ops.export_scene.gltf(filepath=glb, export_format='GLB', use_selection=True)
meta = os.path.join(HERE, '..', '..', 'public', 'assets', 'car', 'car_meta.json')
if os.path.exists(meta):
    shutil.copy(meta, OUT)
print('FAST_PREVIEW', glb, 'verts', len(V), 'faces', len(F), 'sharp edges', nsharp)
